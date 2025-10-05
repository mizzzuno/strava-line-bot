from dotenv import load_dotenv
from pathlib import Path

# プロジェクトルートの .env を読み込む
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

import os
import threading
import urllib.parse
import http.server
import webbrowser
import requests
import json

PORT = 8000
REDIRECT_PATH = "/exchange_token"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit("環境変数 STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET を設定してください")

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != REDIRECT_PATH:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return
        qs = urllib.parse.parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code")
            return

        # exchange code -> token
        try:
            resp = requests.post(STRAVA_TOKEN_URL, data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code"
            })
            resp.raise_for_status()
            j = resp.json()
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Token exchange failed: {e}".encode())
            print("Token exchange failed:", e)
            return

        # 表示 & コンソール出力
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        out = ("<html><body><h3>Token obtained — check console.</h3>"
               "<pre>{}</pre></body></html>").format(json.dumps(j, indent=2))
        self.wfile.write(out.encode("utf-8"))

        print("---- Strava token response ----")
        print(json.dumps(j, indent=2))
        # 簡易保存（カレントディレクトリ）
        with open("strava_tokens.json", "w") as f:
            json.dump(j, f, indent=2)
        print("Saved tokens to ./strava_tokens.json")
        # サーバ停止（1回で終了する）
        threading.Thread(target=self.server.shutdown).start()

def run():
    addr = ("", PORT)
    server = http.server.HTTPServer(addr, Handler)
    auth_url = (
        "https://www.strava.com/oauth/authorize?"
        f"client_id={CLIENT_ID}&response_type=code"
        f"&redirect_uri=http://localhost:{PORT}{REDIRECT_PATH}"
        f"&scope=activity:read_all,read&approval_prompt=force"
    )
    print("Open this URL in your browser (or will open automatically):")
    print(auth_url)
    webbrowser.open(auth_url)
    server.serve_forever()

if __name__ == "__main__":
    run()
# ...existing code...