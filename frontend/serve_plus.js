// globalstrat+ frontend server: serves the CRA build and proxies /api to the
// globalstrat+ backend (gunicorn on :8002). Same-origin, so the app's relative
// '/api' calls and the real login flow work unchanged.
const http = require('http'); const fs = require('fs'); const path = require('path');
const BUILD = '/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend/build';
const PORT = Number(process.env.GLOBALSTRAT_PLUS_FRONTEND_PORT || 8014); const BACKEND = { host: '127.0.0.1', port: Number(process.env.GLOBALSTRAT_PLUS_BACKEND_PORT || 8002) };
const MIME = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon', '.map': 'application/json', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf' };

http.createServer((req, res) => {
  const u = req.url.split('?')[0];
  if (req.url.startsWith('/api/')) {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      const body = Buffer.concat(chunks);
      const headers = { ...req.headers, host: `${BACKEND.host}:${BACKEND.port}` };
      const preq = http.request({ host: BACKEND.host, port: BACKEND.port, method: req.method, path: req.url, headers }, (pres) => {
        res.writeHead(pres.statusCode, pres.headers); pres.pipe(res);
      });
      preq.on('error', (e) => { res.writeHead(502); res.end('proxy error: ' + e.message); });
      if (body.length) preq.write(body);
      preq.end();
    });
    return;
  }
  let fp = path.join(BUILD, decodeURIComponent(u));
  if (u === '/' || !fs.existsSync(fp) || fs.statSync(fp).isDirectory()) {
    if (path.extname(u)) { res.writeHead(404); return res.end('nf'); }
    fp = path.join(BUILD, 'index.html');
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(fp)] || 'application/octet-stream' });
  fs.createReadStream(fp).pipe(res);
}).listen(PORT, '0.0.0.0', () => console.log('globalstrat+ frontend serving on 0.0.0.0:' + PORT + ' -> backend :' + BACKEND.port));
