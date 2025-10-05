import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from main import notify_line

def test_notify_line():
    # テスト用メッセージ
    status = notify_line("テストメッセージ from pytest")
    assert status == 200  # LINE APIが正常なら200
