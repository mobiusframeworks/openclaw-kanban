#!/usr/bin/env python3
"""
Dashboard Server - Serves the dashboard on local network.

Access from any device on the same network:
  http://<mac-mini-ip>:8080

For remote access, use:
  - Tailscale: Install on Mac Mini + phone, access via Tailscale IP
  - ngrok: ngrok http 8080 (creates public URL)
  - Cloudflare Tunnel: cloudflared tunnel

Usage: python3 serve.py
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket
import os

PORT = 8080

class CORSHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except:
        return '127.0.0.1'
    finally:
        s.close()

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    local_ip = get_local_ip()
    server = HTTPServer(('0.0.0.0', PORT), CORSHandler)

    print("=" * 50)
    print("OpenClaw Dashboard Server")
    print("=" * 50)
    print(f"Local:   http://localhost:{PORT}/dashboard.html")
    print(f"Network: http://{local_ip}:{PORT}/dashboard.html")
    print("")
    print("For remote access:")
    print("  Tailscale: Install on both devices, use Tailscale IP")
    print("  ngrok:     ngrok http 8080")
    print("=" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
