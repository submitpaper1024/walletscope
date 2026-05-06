#!/usr/bin/env python3
import http.server
import socketserver
import webbrowser
import os
from urllib.parse import urlparse

def find_free_port(start_port=8000):
    """Find a free port starting from start_port"""
    import socket
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise OSError("No free ports found")

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        """Translate URL path to local file path with custom routing"""
        url_parts = urlparse(path)
        path = url_parts.path

        # Root path serves index.html from public directory
        if path == '/' or path == '/index.html':
            return os.path.join(os.getcwd(), 'public', 'index.html')

        # Static files from static directory
        if path.startswith('/static/'):
            return os.path.join(os.getcwd(), path[1:])  # Remove leading slash

        # Favicon
        if path == '/favicon.ico' or path == '/favicon.svg':
            return os.path.join(os.getcwd(), 'static', 'favicon.svg')

        # Default behavior for other paths
        return super().translate_path(path)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        PORT = find_free_port()
        with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
            print(f"Server running at http://localhost:{PORT}/")
            print("Opening browser...")
            webbrowser.open(f'http://localhost:{PORT}/')

            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down server...")
                httpd.shutdown()
    except OSError as e:
        print(f"Error starting server: {e}")
        print("Please check if another process is using the ports or try again.")