#!/usr/bin/env python3
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

START_TIME = time.time()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            ready = (time.time() - START_TIME) >= 30
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ready": ready}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args):
        pass  # suppress logs

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 9111), Handler)
    print("Server running on port 9111")
    server.serve_forever()
