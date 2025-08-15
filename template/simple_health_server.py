import time
import threading
import http.server
import socketserver


lastUpdatedTime: float = time.time()


class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args) -> None:
        # Override the log_message method to do nothing
        pass

    def do_GET(self) -> None:
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


def start_api_server() -> None:
    with socketserver.TCPServer(("0.0.0.0", 80), HealthCheckHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    threading.Thread(target=start_api_server, daemon=True).start()

    print("API server started on port 80")

    while True:
        time.sleep(10)
