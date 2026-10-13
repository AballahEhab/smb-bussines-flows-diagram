"""Loopback preview of one generated artifact; no directory/file browsing."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from flow_builder import PACKAGE


class ViewerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split('?')[0] not in ('/', '/index.html'):
            self.send_error(404)
            return
        body = (PACKAGE / 'index.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


if __name__ == '__main__':
    print('Viewer-only preview: http://127.0.0.1:18769/ (Ctrl+C to stop)', flush=True)
    HTTPServer(('127.0.0.1', 18769), ViewerHandler).serve_forever()
