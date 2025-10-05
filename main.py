# sample_strava_club_weekly.py
from dotenv import load_dotenv
from pathlib import Path

# プロジェクトルートの .env を読み込む
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

import os, time, requests, math, datetime

STRAVA_CLIENT_ID = os.environ['STRAVA_CLIENT_ID']
STRAVA_CLIENT_SECRET = os.environ['STRAVA_CLIENT_SECRET']
STRAVA_REFRESH_TOKEN = os.environ['STRAVA_REFRESH_TOKEN']
CLUB_ID = os.environ['STRAVA_CLUB_ID']
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
LINE_USER_ID = os.environ['LINE_USER_ID']  # 送信先ユーザーIDを .env に追加してください

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_CLUB_ACTIVITIES = f"https://www.strava.com/api/v3/clubs/{CLUB_ID}/activities"

def refresh_access_token(refresh_token):
    resp = requests.post(STRAVA_TOKEN_URL, data={
        'client_id': STRAVA_CLIENT_ID,
        'client_secret': STRAVA_CLIENT_SECRET,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    })
    resp.raise_for_status()
    j = resp.json()
    return j['access_token'], j.get('refresh_token', refresh_token), j.get('expires_at')

def week_start_unix(now=None):
    # 週の始まりを月曜日 00:00 (UTC) とする例
    if now is None:
        now = datetime.datetime.utcnow()
    # shift to monday
    start = now - datetime.timedelta(days=(now.weekday()))
    start = datetime.datetime(start.year, start.month, start.day, 0, 0, 0)
    return int(start.replace(tzinfo=datetime.timezone.utc).timestamp())

def get_club_activities(access_token, after_ts):
    headers = {'Authorization': f'Bearer {access_token}'}
    page = 1
    per_page = 200
    activities = []
    while True:
        params = {'after': after_ts, 'page': page, 'per_page': per_page}
        retry_count = 0
        while True:
            try:
                r = requests.get(STRAVA_CLUB_ACTIVITIES, headers=headers, params=params)
                r.raise_for_status()
                break
            except requests.exceptions.HTTPError as e:
                if r.status_code == 429:
                    print(f"429 Too Many Requests: {r.url}  API制限中。LINE通知します。")
                    from sys import exc_info
                    notify_line(f"Strava API制限中: 429 Too Many Requests\n{r.url}")
                    raise
                else:
                    raise
        page_items = r.json()
        if not page_items:
            break
        activities.extend(page_items)
        page += 1
    return activities

def aggregate_weekly_rides(activities):
    totals = {}  # athlete_id -> {'name': 'A B', 'meters': n}
    for a in activities:
        # activity object: has 'type' and 'distance' and 'athlete' fields
        if a.get('type') != 'Ride' and a.get('sport_type') != 'Ride':
            continue
        athlete = a.get('athlete', {})
        name = (athlete.get('firstname') or '') + ' ' + (athlete.get('lastname') or '')
        aid = athlete.get('id')
        if not aid:
            continue
        totals.setdefault(aid, {'name': name.strip(), 'meters': 0})
        totals[aid]['meters'] += a.get('distance', 0) or 0
    # km に変換
    for v in totals.values():
        v['km'] = round(v['meters'] / 1000.0, 2)
    return totals

def notify_line(message):
    headers = {
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    resp = requests.post('https://api.line.me/v2/bot/message/push', headers=headers, json=payload)
    resp.raise_for_status()
    return resp.status_code

def main():
    # refresh token -> access token
    access_token, new_refresh, expires_at = refresh_access_token(STRAVA_REFRESH_TOKEN)
    # 週開始
    after_ts = week_start_unix()
    activities = get_club_activities(access_token, after_ts)
    print(f"取得したactivities件数: {len(activities)}")
    if activities:
        print("最初の3件のactivityデータ:")
        for a in activities[:3]:
            print(a)
    else:
        print("activitiesデータが空です")
    totals = aggregate_weekly_rides(activities)
    # 200 km 未満抽出
    under = [(t['name'] or f"id:{aid}", t['km']) for aid, t in totals.items() if t['km'] < 200]
    under.sort(key=lambda x: x[1])
    if not under:
        msg = "今週: 全員200km以上達成または活動が見えない可能性があります。"
    else:
        lines = ["今週200km未満のメンバー："]
        for name, km in under:
            lines.append(f"・{name}: {km} km")
        msg = "\n".join(lines)
    print("LINE通知を送信します: \n" + msg)
    try:
        status = notify_line(msg)
        print(f"LINE通知送信完了: status_code={status}")
    except Exception as e:
        print(f"LINE通知送信失敗: {e}")

if __name__ == '__main__':
    main()