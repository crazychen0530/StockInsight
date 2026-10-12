"""Acceptance-only private SSH and trusted HTTPS receiver; never publish its ports."""

import json
import os
import shutil
import ssl
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Path("/backup/last-alert.json").write_text(json.dumps(body))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_):
        pass


os.chown("/backup", 10001, 10001)
os.chmod("/backup", 0o700)
shutil.copyfile("/test-keys/id_ed25519.pub", "/home/app/.ssh/authorized_keys")
os.chown("/home/app/.ssh", 10001, 10001)
os.chown("/home/app/.ssh/authorized_keys", 10001, 10001)
os.chmod("/home/app/.ssh", 0o700)
os.chmod("/home/app/.ssh/authorized_keys", 0o600)
shutil.copyfile("/test-keys/host_key", "/tmp/host_key")
os.chmod("/tmp/host_key", 0o600)
subprocess.Popen(
    [
        "/usr/sbin/sshd",
        "-D",
        "-e",
        "-h",
        "/tmp/host_key",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "UsePAM=no",
        "-o",
        "PermitRootLogin=no",
        "-o",
        "AllowUsers=app",
    ]
)
server = HTTPServer(("0.0.0.0", 8443), Receiver)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain("/test-keys/alert.crt", "/test-keys/alert.key")
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
