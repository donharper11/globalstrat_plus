// Minimal static + /api proxy server for CR-017 A1 re-verification.
// Serves the fixed production build with SPA fallback; proxies /api -> backend.
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = Number(process.env.PORT || 18080);
const BUILD = process.env.BUILD_DIR || '/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend/build';
const API_HOST = process.env.API_HOST || '127.0.0.1';
const API_PORT = Number(process.env.API_PORT || 8002);

const MIME = { '.html':'text/html', '.js':'application/javascript', '.css':'text/css', '.json':'application/json',
  '.png':'image/png', '.jpg':'image/jpeg', '.svg':'image/svg+xml', '.ico':'image/x-icon', '.map':'application/json',
  '.woff':'font/woff', '.woff2':'font/woff2', '.ttf':'font/ttf', '.txt':'text/plain' };

const server = http.createServer((req, res) => {
  if (req.url.startsWith('/api')) {
    const proxyReq = http.request({ host: API_HOST, port: API_PORT, path: req.url, method: req.method, headers: req.headers },
      (proxyRes) => { res.writeHead(proxyRes.statusCode, proxyRes.headers); proxyRes.pipe(res); });
    proxyReq.on('error', (e) => { res.writeHead(502); res.end('proxy error: ' + e.message); });
    req.pipe(proxyReq);
    return;
  }
  let urlPath = decodeURIComponent(req.url.split('?')[0]);
  let filePath = path.join(BUILD, urlPath);
  if (!filePath.startsWith(BUILD)) { res.writeHead(403); res.end('forbidden'); return; }
  fs.stat(filePath, (err, stat) => {
    if (!err && stat.isFile()) return send(filePath, res);
    // SPA fallback
    send(path.join(BUILD, 'index.html'), res);
  });
});

function send(filePath, res) {
  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'content-type': MIME[path.extname(filePath)] || 'application/octet-stream' });
    res.end(data);
  });
}

server.listen(PORT, '127.0.0.1', () => console.log(`cr017 serve on http://127.0.0.1:${PORT} build=${BUILD} api=${API_HOST}:${API_PORT}`));
