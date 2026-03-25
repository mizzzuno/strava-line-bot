## 仮想環境を使った実行手順（macOS）

1. プロジェクトへ移動

```bash
cd /Users/miz/dev/strava-line-bot
```

2. 仮想環境を作成（未作成の場合のみ）

```bash
python3 -m venv .venv
```

3. 仮想環境を有効化

```bash
source .venv/bin/activate
```

4. 依存関係をインストール

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. 実行

```bash
python main.py
```

6. 仮想環境を抜ける

```bash
deactivate
```

## 有効化せずに 1 回だけ実行する方法

```bash
/Users/miz/dev/strava-line-bot/.venv/bin/python main.py
```
