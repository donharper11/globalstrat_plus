#!/usr/bin/env python3
"""OpenAI-compatible stub that returns deliberately different prose.

Used by the GSP-CRV2-01 replay evidence: run the same round against a
different "model" whose output is nothing like the real one, and show the
competitive hash does not move.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PROSE = (
    'STUB MODEL OUTPUT — this narrative was produced by a deliberately '
    'different endpoint for determinism evidence. It shares no wording with '
    'the production model. Lorem ipsum dolor sit amet, consectetur adipiscing '
    'elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(length)
        payload = json.dumps({
            'id': 'stub', 'object': 'chat.completion', 'model': 'stub-divergent-1',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': PROSE}}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
        }).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    HTTPServer(('127.0.0.1', 8791), Handler).serve_forever()
