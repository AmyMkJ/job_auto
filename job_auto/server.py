import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .core import ROOT, db, jobs, refresh

class Handler(BaseHTTPRequestHandler):
    def respond(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/jobs':
            return self.respond(jobs())
        if path == '/':
            body = (ROOT / 'static/index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)
        else:
            self.respond({'error': 'not found'}, 404)

    def do_POST(self):
        # Prevent cross-origin sites from triggering local mutations.
        if self.headers.get('Origin') not in (None, 'http://' + self.headers.get('Host', '')):
            return self.respond({'error': 'invalid origin'}, 403)
        if self.headers.get('Content-Type') != 'application/json':
            return self.respond({'error': 'JSON required'}, 415)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length > 10000:
                return self.respond({'error': 'too large'}, 413)
            data = json.loads(self.rfile.read(length) or b'{}')
            if self.path == '/api/refresh':
                return self.respond(refresh())
            if self.path == '/api/status' and data.get('status') in ['new', 'saved', 'applied', 'dismissed']:
                with db() as c:
                    cur = c.execute('UPDATE jobs SET status=? WHERE id=?', (data['status'], data['id']))
                return self.respond({'updated': cur.rowcount})
            self.respond({'error': 'invalid request'}, 400)
        except (ValueError, KeyError):
            self.respond({'error': 'invalid JSON or missing field'}, 400)

if __name__ == '__main__':
    print('Job Auto listening on 127.0.0.1:8000', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
