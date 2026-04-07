/**
 * Runtime config for the static viewer (Vercel env → browser).
 * Set in Vercel: Project Settings → Environment Variables
 *   DNR_CHUNK_BASE_URL = https://your-bucket.r2.dev/wells/  (trailing slash optional)
 */
export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') {
    res.status(204).end();
    return;
  }
  const base = (process.env.DNR_CHUNK_BASE_URL || '').trim();
  res.setHeader('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=300');
  res.status(200).json({
    chunkBaseUrl: base ? base.replace(/\/?$/, '/') : '',
  });
}

if (typeof module !== 'undefined' && module.exports) module.exports = handler;
