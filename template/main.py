import time
import threading
import http.server
import socketserver


lastUpdatedTime = time.time()


class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override the log_message method to do nothing
        pass

    def do_GET(self):
        if self.path == "/health":
            if (time.time() - lastUpdatedTime) > 60:
                self.send_response(500)
            else:
                self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")


def start_api_server():
    with socketserver.TCPServer(("0.0.0.0", 80), HealthCheckHandler) as httpd:
        httpd.serve_forever()


threading.Thread(target=start_api_server, daemon=True).start()

while True:
    time.sleep(10)
