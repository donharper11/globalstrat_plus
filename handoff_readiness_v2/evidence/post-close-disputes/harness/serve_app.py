#!/usr/bin/env python3
"""Serve the built frontend and proxy /api to the backend, on one origin.

Same-origin on purpose. The frontend's default API base is `/api`, so serving
both from one port is what the deployed app does and avoids introducing a CORS
configuration that exists only for this walkthrough. A walkthrough that needs
the product configured differently to pass is not a walkthrough of the product.
"""
import http.server
import socketserver
import sys
import urllib.error
import urllib.request

BUILD = sys.argv[1]
BACKEND = sys.argv[2]          # e.g. http://127.0.0.1:8002
PORT = int(sys.argv[3])
HOP = {'connection', 'keep-alive', 'transfer-encoding', 'content-encoding',
       'content-length'}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BUILD, **kw)

    def log_message(self, *a):
        pass

    def _proxy(self, method):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else None
        request = urllib.request.Request(
            BACKEND + self.path, data=body, method=method)
        for name, value in self.headers.items():
            if name.lower() not in HOP and name.lower() != 'host':
                request.add_header(name, value)
        try:
            with urllib.request.urlopen(request, timeout=120) as upstream:
                payload, status, headers = (upstream.read(), upstream.status,
                                            upstream.headers)
        except urllib.error.HTTPError as exc:
            payload, status, headers = exc.read(), exc.code, exc.headers
        except Exception as exc:                      # backend down
            payload, status, headers = str(exc).encode(), 502, {}
        self.send_response(status)
        for name, value in (headers.items() if headers else []):
            if name.lower() not in HOP:
                self.send_header(name, value)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith('/api/'):
            return self._proxy('GET')
        # Single-page app: any unknown path is a client route, not a 404.
        import os
        target = os.path.join(BUILD, self.path.lstrip('/').split('?')[0])
        if self.path != '/' and not os.path.isfile(target):
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        return self._proxy('POST')

    def do_PATCH(self):
        return self._proxy('PATCH')

    def do_PUT(self):
        return self._proxy('PUT')

    def do_DELETE(self):
        return self._proxy('DELETE')


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    with Server(('127.0.0.1', PORT), Handler) as httpd:
        print(f'serving {BUILD} on {PORT}, /api -> {BACKEND}', flush=True)
        httpd.serve_forever()
