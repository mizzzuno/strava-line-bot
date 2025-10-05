from http.server import BaseHTTPRequestHandler
import sys
import os

# プロジェクトのルートディレクトリをPythonのパスに追加します
# これにより、'main'モジュールを正しくインポートできます
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from main import main

class handler(BaseHTTPRequestHandler):
    """
    Vercel Serverless Functionのハンドラクラス。
    GETリクエストを受け取ると、main.main()関数を実行します。
    """
    def do_GET(self):
        try:
            # mainモジュールのmain関数を実行
            main()
            
            # 成功した場合、ステータスコード200とメッセージを返す
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write("Stravaアクティビティの通知を送信しました。".encode('utf-8'))
        except Exception as e:
            # エラーが発生した場合、ステータスコード500とエラーメッセージを返す
            self.send_response(500)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"エラーが発生しました: {e}".encode('utf-8'))

        return
