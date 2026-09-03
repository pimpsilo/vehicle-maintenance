#!/usr/bin/env bash
# ==============================================================================
# auth_google.py - 1-Click Google Calendar Authenticator
# ==============================================================================
# Run this script on your Mac to authenticate your Google Account:
#   .venv/bin/python scripts/auth_google.py
# ==============================================================================
import os
import sys
import json
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Run with: .venv/bin/python scripts/auth_google.py")
    sys.exit(1)

# Ensure app directory is on path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.services.gcal_service import GoogleCalendarService

PORT = 8088
REDIRECT_URI = f"http://localhost:{PORT}"

auth_code = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #10b981;">&#10004; Google Calendar Authorized!</h1>
                <p>You can close this browser tab and return to your terminal.</p>
            </body>
            </html>
            """)
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization failed or cancelled.</h1>")

    def log_message(self, format, *args):
        return  # Silence server logs


def main():
    print("=" * 70)
    print("🚗 Vehicle Maintenance - Google Calendar Authorization")
    print("=" * 70)

    client_id = settings.google_client_id
    client_secret = settings.google_client_secret

    if not client_id or not client_secret:
        print("❌ Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env")
        sys.exit(1)

    print(f"Client ID: {client_id[:20]}...{client_id[-15:]}")
    print(f"Target Calendar: {settings.google_calendar_id}")
    print(f"Token Storage: {settings.google_token_file}\n")

    auth_url = GoogleCalendarService.get_auth_url(redirect_uri=REDIRECT_URI)

    print("🌐 Opening your web browser to authorize with Google...")
    print(f"If your browser doesn't open automatically, visit this URL:\n\n{auth_url}\n")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", PORT), OAuthCallbackHandler)
    print(f"Waiting for authorization on {REDIRECT_URI}...")
    
    while auth_code is None:
        server.handle_request()

    server.server_close()

    print("\n📦 Exchanging authorization code for tokens...")
    try:
        token_data = GoogleCalendarService.exchange_code_for_token(auth_code, redirect_uri=REDIRECT_URI)
        print("✅ Tokens obtained successfully!")
        print(f"   Saved to: {settings.google_token_file}")
        print("\n🎉 Google Calendar integration is now ACTIVE!")
        print("   Run ./scripts/update_qnap.sh to push the credentials and token to your QNAP NAS.\n")
    except Exception as e:
        print(f"❌ Error exchanging code: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
