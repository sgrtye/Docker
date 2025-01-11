import time
import threading
import http.server
import socketserver

import logging

logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

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


def start_health_server():
    with socketserver.TCPServer(("0.0.0.0", 80), HealthCheckHandler) as httpd:
        httpd.serve_forever()


health_thread = threading.Thread(target=start_health_server)
health_thread.daemon = True
health_thread.start()

logger.info("Starting")

while True:
    time.sleep(10)
