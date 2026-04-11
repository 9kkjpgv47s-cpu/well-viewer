"""
Fetch Indiana DNR well Details HTML and extract Well Log intervals + modal meta.

Used by build_statewide_data.py when DNR_FILL_LITHO_HTML=1 or DNR_FILL_MODAL_HTML=1.
Parsing mirrors api/dnr-report.js (Well Log table, test/bail rates) plus drill rig / test method labels.

Cache: dnr_html_litho_cache.json in out_dir (resume-friendly).

Env (optional): DNR_HTTP_COOKIE, DNR_HTTP_MINIMAL_HEADERS=1, DNR_HTML_DEBUG=1,
DNR_HTML_LITHO_REFRESH=1 (ignore cache entries and refetch), DNR_HTML_LITHO_PROGRESS=N
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from dnr_env_local import ensure_dnr_env_local_loaded

CACHE_NAME = "dnr_html_litho_cache.json"


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _cache_path(out_dir: str) -> str:
    return os.path.join(out_dir, CACHE_NAME)


def _load_cache(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(path: str, data: dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
    os.replace(tmp, path)


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = s.replace("&nbsp;", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _details_url(ref: str) -> str:
    return (
        "https://secure.in.gov/apps/dnr/water/dnr_waterwell?"
        f"refNo={ref}&_from=SUMMARY&_action=Details"
    )


def _fetch_html(ref: str, out_dir: str, *, debug_first: bool) -> str:
    ensure_dnr_env_local_loaded()
    url = _details_url(ref)
    chrome_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    headers = {
        # Mirror api/dnr-report.js fetch profile (browser-like, not custom bot UA).
        "User-Agent": chrome_ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        # Prefer plain text payload to avoid brotli/encoding surprises in urllib.
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
    }
    if _env_truthy("DNR_HTTP_MINIMAL_HEADERS"):
        headers = {
            "User-Agent": chrome_ua,
            "Accept": "text/html,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }
    cookie = (os.environ.get("DNR_HTTP_COOKIE") or "").strip()
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        if debug_first and out_dir:
            try:
                raw_err = e.read()
                txt_err = raw_err.decode("utf-8", errors="replace")
                dbg = os.path.join(out_dir, "dnr_debug_first_fetch.http_error.html")
                if not os.path.isfile(dbg):
                    with open(dbg, "w", encoding="utf-8", errors="replace") as f:
                        f.write(txt_err)
            except Exception:
                pass
        return ""
    except urllib.error.URLError:
        return ""
    try:
        html = raw.decode("utf-8", errors="replace")
    except Exception:
        html = raw.decode("latin-1", errors="replace")

    if debug_first and out_dir:
        dbg = os.path.join(out_dir, "dnr_debug_first_fetch.html")
        if not os.path.isfile(dbg):
            try:
                with open(dbg, "w", encoding="utf-8", errors="replace") as f:
                    f.write(html)
            except OSError:
                pass
    return html


def parse_report_html(html: str) -> dict[str, Any]:
    """
    Return lithology rows [{top,bottom,formation},...] and optional meta.
    Mirrors api/dnr-report.js parseReportHtml + extra modal fields.
    """
    out: dict[str, Any] = {
        "lithology": [],
        "drill_rig_type": "",
        "test_method": "",
        "raw_error": None,
    }
    if not html or len(html) < 200:
        out["raw_error"] = "empty"
        return out
    lower = html.lower()

    # --- Drill rig / method of testing (JSP often wraps values in tags) ---
    def _label_val(label: str) -> str:
        i = lower.find(label.lower())
        if i < 0:
            return ""
        chunk = html[i : i + 2500]
        # Prefer table cell after label
        m = re.search(
            r"(?is)" + re.escape(label) + r"[^<]{0,200}?</[^>]+>\s*<[^>]+>\s*([^<]+)",
            chunk,
        )
        if m:
            return _strip_tags(m.group(1))
        m2 = re.search(r"(?is)" + re.escape(label) + r"\s*:?\s*([^\n<]{2,120})", chunk)
        if m2:
            return _strip_tags(m2.group(1)).strip(" :")
        return ""

    out["drill_rig_type"] = _label_val("Drill rig type") or _label_val("Drill Rig Type")
    out["test_method"] = _label_val("Method of testing") or _label_val("Method of Testing")

    # --- Well Log table ---
    slice_html = html
    log_idx = lower.find("well log")
    if log_idx >= 0:
        slice_html = html[log_idx : log_idx + 100_000]

    litho: list[dict[str, str]] = []
    for tr_m in re.finditer(r"<tr[^>]*>([\s\S]*?)</tr>", slice_html, re.I):
        row_html = tr_m.group(1)
        tds = re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", row_html, re.I)
        if len(tds) < 3:
            continue
        cells = [_strip_tags(t) for t in tds]
        row_text = " ".join(cells).lower()
        if "top" in row_text and "bottom" in row_text and "formation" in row_text:
            continue
        # DNR pages often include a blank leading column before top/bottom.
        # Find first adjacent numeric pair anywhere in the row.
        pair_i = None
        for i in range(0, len(cells) - 1):
            a = re.sub(r"\s", "", cells[i] or "")
            b = re.sub(r"\s", "", cells[i + 1] or "")
            if re.match(r"^[\d.]+$", a) and re.match(r"^[\d.]+$", b):
                pair_i = i
                break
        if pair_i is None:
            continue
        top_s = re.sub(r"\s", "", cells[pair_i] or "")
        bottom_s = re.sub(r"\s", "", cells[pair_i + 1] or "")
        formation = ""
        for j in range(pair_i + 2, len(cells)):
            c = (cells[j] or "").strip()
            if c:
                formation = c
                break
        if not formation:
            formation = "—"
        litho.append({"top": top_s, "bottom": bottom_s, "formation": formation})

    if not litho:
        block = re.sub(r"<script[\s\S]*?</script>", " ", slice_html, flags=re.I)
        block = re.sub(r"<style[\s\S]*?</style>", " ", block, flags=re.I)
        plain = re.sub(r"<br\s*/?>", "\n", block, flags=re.I)
        plain = re.sub(r"</tr>", "\n", plain, flags=re.I)
        plain = re.sub(r"<[^>]+>", " ", plain)
        for line in plain.splitlines():
            line = line.strip()
            m = re.match(r"^([\d.]+)\s+([\d.]+)\s+(.+)$", line)
            if not m:
                continue
            form = m.group(3).strip()
            if len(form) <= 1 or re.match(r"^(top|bottom|formation)$", form, re.I):
                continue
            try:
                if float(m.group(1)) >= float(m.group(2)) + 200:
                    continue
            except ValueError:
                continue
            litho.append({"top": m.group(1), "bottom": m.group(2), "formation": form})

    if not litho:
        alt_re = re.compile(
            r"<td[^>]*>([\d.]+)</td>\s*<td[^>]*>([\d.]+)</td>\s*<td[^>]*>([^<]*)</td>",
            re.I,
        )
        for am in alt_re.finditer(slice_html):
            form = _strip_tags(am.group(3)).strip()
            if re.match(r"^(top|bottom|formation)$", form, re.I):
                continue
            litho.append({"top": am.group(1), "bottom": am.group(2), "formation": form or "—"})

    if not litho:
        loose_re = re.compile(
            r"<td[^>]*>\s*([\d.]+)\s*</td>\s*<td[^>]*>\s*([\d.]+)\s*</td>\s*"
            r"<td[^>]*>\s*([\s\S]*?)</td>",
            re.I,
        )
        for lm in loose_re.finditer(slice_html):
            form = _strip_tags(lm.group(3)).strip()
            if re.match(r"^(top|bottom|formation)$", form, re.I):
                continue
            litho.append({"top": lm.group(1), "bottom": lm.group(2), "formation": form or "—"})

    seen: set[str] = set()
    uniq: list[dict[str, str]] = []
    for row in litho:
        k = row["top"] + "|" + row["bottom"] + "|" + row["formation"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(row)
    uniq.sort(key=lambda r: float(r["top"] or 0))
    out["lithology"] = uniq
    if not out["lithology"]:
        out["raw_error"] = "no_table"
    return out


def fill_rows_from_dnr_html(
    out_rows: list[dict[str, Any]],
    *,
    out_dir: str,
    delay_sec: float,
    max_fetches: int | None,
    apply_fn: Callable[[dict[str, Any], list, str, dict[str, Any] | None], None],
) -> tuple[int, int, int, int]:
    """
    For rows with empty lithology_json, fetch Details HTML (or use cache), then call apply_fn.

    Returns (log_table_from_html, placeholder_rows, capped_no_fetch, drill_or_method_only).
    """
    ensure_dnr_env_local_loaded()
    os.makedirs(out_dir, exist_ok=True)
    path = _cache_path(out_dir)
    cache = _load_cache(path)
    refresh = _env_truthy("DNR_HTML_LITHO_REFRESH")
    progress = max(1, int(os.environ.get("DNR_HTML_LITHO_PROGRESS", "25") or "25"))
    debug_first = _env_truthy("DNR_HTML_DEBUG")

    nh = nph = ncap = nmeta = 0
    http_count = 0
    cache_hits = 0
    missing = [r for r in out_rows if not str(r.get("lithology_json") or "").strip()]
    total_missing = len(missing)
    processed = 0
    print(
        f"  HTML lithology cache: {len(cache):,} ref key(s) on disk; "
        f"DNR_HTML_LITHO_REFRESH={'1 (refetch all)' if refresh else '0 (reuse cache)'}",
        flush=True,
    )

    def persist() -> None:
        try:
            _save_cache(path, cache)
        except OSError:
            pass

    for row in out_rows:
        if str(row.get("lithology_json") or "").strip():
            continue
        ref = str(row.get("refno") or "").strip()
        if not ref:
            continue

        processed += 1
        if processed % progress == 0 or processed == 1:
            print(
                f"    … {processed:,}/{total_missing:,} HTTP={http_count:,} cache_hit≈{cache_hits:,} "
                f"log_table≈{nh:,} placeholder≈{nph:,} meta_only≈{nmeta:,}",
                flush=True,
            )

        key = ref
        entry = cache.get(key) if isinstance(cache.get(key), dict) else None
        if refresh or not entry or entry.get("error") == "force_refresh":
            entry = None

        need_http = entry is None
        if need_http:
            if max_fetches is not None and http_count >= max_fetches:
                ncap += 1
                continue
            html = _fetch_html(ref, out_dir, debug_first=debug_first)
            http_count += 1
            if delay_sec > 0:
                time.sleep(delay_sec)
            if not html:
                parsed = {"lithology": [], "drill_rig_type": "", "test_method": "", "raw_error": "fetch_fail"}
            else:
                parsed = parse_report_html(html)
            cache[key] = {"parsed": parsed, "fetched_at": int(time.time())}
            persist()
        else:
            cache_hits += 1
            parsed = entry.get("parsed") or {}

        litho = parsed.get("lithology") or []
        meta = {
            "drill_rig_type": str(parsed.get("drill_rig_type") or "").strip(),
            "test_method": str(parsed.get("test_method") or "").strip(),
        }
        has_meta = bool(meta["drill_rig_type"] or meta["test_method"])
        if litho:
            apply_fn(row, litho, "html", meta)
            nh += 1
        elif has_meta:
            apply_fn(row, [], "none", meta)
            nmeta += 1
        else:
            apply_fn(row, [], "none", meta)
            nph += 1

    persist()
    print(
        f"  HTML lithology fetch summary: new_HTTP={http_count:,} cache_hits={cache_hits:,} "
        f"(log_table={nh:,} placeholder={nph:,} meta_only={nmeta:,} capped={ncap:,})",
        flush=True,
    )
    if nh == 0 and total_missing > 500 and cache_hits > total_missing * 0.9 and http_count < max(50, total_missing // 100):
        print(
            "  WARNING: Almost all rows used cache but zero Well Log tables parsed. "
            "Your dnr_html_litho_cache.json likely stores WAF/empty/error pages from an earlier run.\n"
            "  Fix: mv dnr_html_litho_cache.json dnr_html_litho_cache.json.bak  then re-run with "
            "DNR_HTTP_COOKIE (browser Cookie for secure.in.gov), or DNR_HTML_LITHO_REFRESH=1 once "
            "after fixing network/cookie; see build_statewide_data.py header.",
            flush=True,
        )
    return nh, nph, ncap, nmeta


def fill_modal_meta_from_dnr_html(
    out_rows: list[dict[str, Any]],
    *,
    out_dir: str,
    delay_sec: float,
    max_fetches: int | None,
) -> tuple[int, int, int]:
    """
    Fill drill_rig_type / test_method from cache or HTTP for rows still missing either field.
    Returns (apply_ops, still_missing_rows, capped_no_fetch).
    """
    ensure_dnr_env_local_loaded()
    os.makedirs(out_dir, exist_ok=True)
    path = _cache_path(out_dir)
    cache = _load_cache(path)
    refresh = _env_truthy("DNR_HTML_LITHO_REFRESH")
    debug_first = _env_truthy("DNR_HTML_DEBUG")
    progress = max(1, int(os.environ.get("DNR_MODAL_HTML_PROGRESS", os.environ.get("DNR_HTML_LITHO_PROGRESS", "25")) or "25"))

    mu = mcap = 0
    http_count = 0
    candidates = [
        r
        for r in out_rows
        if (not str(r.get("drill_rig_type") or "").strip())
        or (not str(r.get("test_method") or "").strip())
    ]
    total_c = len(candidates)
    seen = 0

    def persist() -> None:
        try:
            _save_cache(path, cache)
        except OSError:
            pass

    for row in candidates:
        ref = str(row.get("refno") or "").strip()
        if not ref:
            continue
        need_drill = not str(row.get("drill_rig_type") or "").strip()
        need_test = not str(row.get("test_method") or "").strip()
        if not need_drill and not need_test:
            continue

        key = ref
        entry = cache.get(key) if isinstance(cache.get(key), dict) else None
        need_http = refresh or entry is None

        if need_http:
            if max_fetches is not None and http_count >= max_fetches:
                mcap += 1
                continue
            html = _fetch_html(ref, out_dir, debug_first=debug_first)
            http_count += 1
            if delay_sec > 0:
                time.sleep(delay_sec)
            if not html:
                parsed = {"lithology": [], "drill_rig_type": "", "test_method": "", "raw_error": "fetch_fail"}
            else:
                parsed = parse_report_html(html)
            # merge: keep prior lithology in cache if we only extend meta
            old = entry.get("parsed") if entry else {}
            if isinstance(old, dict) and old.get("lithology") and not parsed.get("lithology"):
                parsed = {**parsed, "lithology": old.get("lithology") or []}
            cache[key] = {"parsed": parsed, "fetched_at": int(time.time())}
            persist()
        else:
            parsed = entry.get("parsed") or {}

        dr = str(parsed.get("drill_rig_type") or "").strip()
        tm = str(parsed.get("test_method") or "").strip()
        changed = False
        if need_drill and dr:
            row["drill_rig_type"] = dr
            changed = True
        if need_test and tm:
            row["test_method"] = tm
            changed = True
        if changed:
            mu += 1

        seen += 1
        if seen % progress == 0 or seen == 1:
            print(
                f"    … {seen:,}/{total_c:,} HTTP={http_count:,} meta_applied≈{mu:,} capped≈{mcap:,}",
                flush=True,
            )

    persist()
    mmiss = sum(
        1
        for r in out_rows
        if (not str(r.get("drill_rig_type") or "").strip())
        or (not str(r.get("test_method") or "").strip())
    )
    return mu, mmiss, mcap
