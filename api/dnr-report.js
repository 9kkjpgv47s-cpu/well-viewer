/**
 * Fetches Indiana DNR well report HTML and extracts Well Log (material by footage)
 * and test rate / bail rate / static water — same fields as the official PDF/report.
 * Deploy with Vercel; call as GET /api/dnr-report?refNo=174349
 */
function stripTags(s) {
  return String(s || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function parseReportHtml(html) {
  const out = {
    lithology: [],
    testRateGpm: '',
    bailTestRateGpm: '',
    staticWaterFt: '',
    rawError: null,
  };
  if (!html || html.length < 200) {
    out.rawError = 'empty';
    return out;
  }
  const lower = html.toLowerCase();
  // --- Test rate (e.g. "Test rate: 8.0 gpm for hrs.") — JSP or plain text ---
  const testPatterns = [
    /Test\s+rate\s*:\s*[^0-9<]*([\d.]+)\s*gpm/i,
    /Test\s+rate\s*:\s*<\/[^>]+>\s*<[^>]+>\s*([\d.]+)\s*gpm/i,
    /Well\s+Capacity\s+Test[\s\S]{0,1200}?Test\s+rate\s*:\s*[^0-9]*([\d.]+)\s*gpm/i,
  ];
  for (const re of testPatterns) {
    const m = html.match(re);
    if (m && m[1]) {
      out.testRateGpm = m[1] + ' gpm';
      break;
    }
  }
  // --- Bail / Test rate second line ---
  const bailPatterns = [
    /Bail[^<]*?\/\s*Test\s+rate\s*:\s*([\d.]+)\s*gpm/i,
    /Bail[^<]{0,40}rate[^:]*:\s*([\d.]+)\s*gpm/i,
    /Bailer[^<]{0,60}?([\d.]+)\s*gpm/i,
  ];
  for (const re of bailPatterns) {
    const m = html.match(re);
    if (m && m[1]) {
      out.bailTestRateGpm = m[1] + ' gpm';
      break;
    }
  }
  // --- Static water ---
  const sw = html.match(/Static\s+water\s+level\s*:\s*([\d.]+)/i) || html.match(/Static\s+water[^:]*:\s*([\d.]+)/i);
  if (sw) out.staticWaterFt = sw[1];

  // --- Well Log table: Top | Bottom | Formation — capture ALL data rows ---
  let slice = html;
  const logIdx = lower.indexOf('well log');
  if (logIdx >= 0) slice = html.slice(logIdx, logIdx + 100000);
  const trRe = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
  let trMatch;
  while ((trMatch = trRe.exec(slice)) !== null) {
    const rowHtml = trMatch[1];
    const tds = rowHtml.match(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi);
    if (!tds || tds.length < 3) continue;
    const cells = tds.map((td) => stripTags(td));
    const c0 = (cells[0] || '').toLowerCase().replace(/\s/g, '');
    const c2 = (cells[2] || '').toLowerCase();
    if (c0 === 'top' || (c0.includes('top') && c2.includes('formation'))) continue;
    const topS = (cells[0] || '').replace(/\s/g, '');
    const bottomS = (cells[1] || '').replace(/\s/g, '');
    const formation = (cells[2] || '').trim();
    if (!/^[\d.]+$/.test(topS) || !/^[\d.]+$/.test(bottomS)) continue;
    const topNum = parseFloat(topS);
    const bottomNum = parseFloat(bottomS);
    if (isNaN(topNum) || isNaN(bottomNum)) continue;
    if (formation.length >= 0) out.lithology.push({ top: topS, bottom: bottomS, formation: formation || '—' });
  }
  // Plain text after "Well Log" (some pages put rows as text)
  if (!out.lithology.length && logIdx >= 0) {
    const block = slice.replace(/<script[\s\S]*?<\/script>/gi, '').replace(/<style[\s\S]*?<\/style>/gi, '');
    const plain = block.replace(/<br\s*\/?>/gi, '\n').replace(/<\/tr>/gi, '\n').replace(/<[^>]+>/g, ' ');
    const lines = plain.split(/[\n\r]+/);
    for (const line of lines) {
      const m = line.trim().match(/^([\d.]+)\s+([\d.]+)\s+(.+)$/);
      if (m && parseFloat(m[1]) < parseFloat(m[2]) + 200) {
        const form = m[3].trim();
        if (form.length > 1 && !/^(top|bottom|formation)$/i.test(form))
          out.lithology.push({ top: m[1], bottom: m[2], formation: form });
      }
    }
  }
  if (!out.lithology.length) {
    const altRe = /<td[^>]*>([\d.]+)<\/td>\s*<td[^>]*>([\d.]+)<\/td>\s*<td[^>]*>([^<]*)<\/td>/gi;
    let am;
    while ((am = altRe.exec(slice)) !== null) {
      const form = stripTags(am[3]).trim();
      if (/^(top|bottom|formation)$/i.test(form)) continue;
      out.lithology.push({ top: am[1], bottom: am[2], formation: form || '—' });
    }
  }
  if (!out.lithology.length) {
    const looseRe = /<td[^>]*>\s*([\d.]+)\s*<\/td>\s*<td[^>]*>\s*([\d.]+)\s*<\/td>\s*<td[^>]*>\s*([\s\S]*?)<\/td>/gi;
    let lm;
    while ((lm = looseRe.exec(slice)) !== null) {
      const form = stripTags(lm[3]).trim();
      if (/^(top|bottom|formation)$/i.test(form)) continue;
      out.lithology.push({ top: lm[1], bottom: lm[2], formation: form || '—' });
    }
  }
  const seen = new Set();
  out.lithology = out.lithology.filter((row) => {
    const k = row.top + '|' + row.bottom + '|' + row.formation;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  out.lithology.sort((a, b) => parseFloat(a.top) - parseFloat(b.top));
  return out;
}

async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') {
    res.status(204).end();
    return;
  }
  const refNo = req.query.refNo || req.query.refno;
  if (!refNo || !/^\d+$/.test(String(refNo))) {
    res.status(400).json({ error: 'refNo required (numeric)' });
    return;
  }
  const url = `https://secure.in.gov/apps/dnr/water/dnr_waterwell?refNo=${refNo}&_from=SUMMARY&_action=Details`;
  try {
    const r = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        Accept: 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
      },
      redirect: 'follow',
    });
    if (!r.ok) {
      res.status(502).json({ error: 'DNR returned ' + r.status, lithology: [], testRateGpm: '', bailTestRateGpm: '' });
      return;
    }
    const html = await r.text();
    const parsed = parseReportHtml(html);
    res.setHeader('Cache-Control', 'public, s-maxage=86400, stale-while-revalidate=604800');
    res.status(200).json(parsed);
  } catch (e) {
    res.status(502).json({
      error: String(e.message || e),
      lithology: [],
      testRateGpm: '',
      bailTestRateGpm: '',
    });
  }
}

export default handler;
module.exports = handler;
