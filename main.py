# sample_strava_club_weekly.py
from dotenv import load_dotenv
from pathlib import Path

# プロジェクトルートの .env を読み込む
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

import os, time, requests, math, datetime
from api.api import get_club_activities as fetch_club_activities_page

STRAVA_CLIENT_ID = os.environ['STRAVA_CLIENT_ID']
STRAVA_CLIENT_SECRET = os.environ['STRAVA_CLIENT_SECRET']
STRAVA_REFRESH_TOKEN = os.environ['STRAVA_REFRESH_TOKEN']
CLUB_ID = os.environ['STRAVA_CLUB_ID']
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
LINE_USER_ID = os.environ['LINE_USER_ID']  # 送信先ユーザーIDを .env に追加してください

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


def parse_strava_datetime_to_unix(created_at):
    if not created_at:
        return None
    try:
        return int(datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp())
    except (TypeError, ValueError):
        return None

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
        now = datetime.datetime.now(datetime.timezone.utc)
    # shift to monday
    start = now - datetime.timedelta(days=(now.weekday()))
    start = datetime.datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=datetime.timezone.utc)
    return int(start.replace(tzinfo=datetime.timezone.utc).timestamp())


def last_7_days_unix(now=None):
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    return int((now - datetime.timedelta(days=7)).timestamp())


def extract_activity_timestamp(item):
    # club activities のレスポンス差異に備えて候補キーを順に試す
    for key in ('start_date', 'start_date_local', 'created_at'):
        ts = parse_strava_datetime_to_unix(item.get(key))
        if ts is not None:
            return ts
    return None

def get_club_activities(access_token, after_ts):
    page = 1
    per_page = 200
    activities = []
    rate_limit_usage = 0
    rate_limit_limit = 600  # Default 15-min limit

    while True:
        # レート制限のチェック
        if rate_limit_usage >= rate_limit_limit * 0.95:
            now = datetime.datetime.now(datetime.timezone.utc)
            # 次の15分ウィンドウの開始まで待機
            wait_seconds = 900 - (now.minute * 60 + now.second) % 900 + 5
            print(f"Rate limit approaching. Waiting for {wait_seconds} seconds.")
            time.sleep(wait_seconds)

        params = {'page': page, 'per_page': per_page}
        try:
            r = fetch_club_activities_page(
                access_token,
                page=params['page'],
                per_page=params['per_page'],
                after=after_ts,
            )
            r.raise_for_status()

            # レート制限ヘッダーの更新
            if 'X-RateLimit-Limit' in r.headers:
                rate_limit_limit = int(r.headers['X-RateLimit-Limit'].split(',')[0])
            if 'X-RateLimit-Usage' in r.headers:
                rate_limit_usage = int(r.headers['X-RateLimit-Usage'].split(',')[0])

        except requests.exceptions.HTTPError as e:
            response = e.response
            if response is not None and response.status_code == 429:
                print(f"429 Too Many Requests: {response.url}  API制限中。LINE通知します。")
                notify_line(f"Strava API制限中: 429 Too Many Requests\n{response.url}")
                # 429エラーの場合、次の15分ウィンドウまで待機
                now = datetime.datetime.now(datetime.timezone.utc)
                wait_seconds = 900 - (now.minute * 60 + now.second) % 900 + 5
                print(f"Rate limit hit. Waiting for {wait_seconds} seconds before retrying.")
                time.sleep(wait_seconds)
                continue  # 同じページでリトライ
            else:
                raise
        page_items = r.json()
        if not page_items:
            break

        # club activities APIは after が効かない場合があるため、日時で絞って古いページで打ち切る
        stop_paging = False
        has_any_timestamp = False
        for item in page_items:
            created_ts = extract_activity_timestamp(item)
            if created_ts is None:
                continue
            has_any_timestamp = True
            if created_ts >= after_ts:
                activities.append(item)
            else:
                stop_paging = True

        if not has_any_timestamp:
            # タイムスタンプが全く無いレスポンスでは週次フィルタ不能なので、
            # API呼び出し回数を増やさないため最新ページのみ集計対象にする
            print("警告: activityに日時フィールドが無いため週次フィルタ不可。最新ページのみで集計します。")
            activities.extend(page_items)
            break

        if stop_paging:
            break

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
        if aid:
            athlete_key = f"id:{aid}"
        else:
            # club activities では athlete.id が返らないことがある
            fallback_name = name.strip()
            if not fallback_name:
                fallback_name = (a.get('name') or '').strip()
            if not fallback_name:
                continue
            athlete_key = f"name:{fallback_name}"

        if athlete_key not in totals:
            totals[athlete_key] = {'name': name.strip(), 'meters': 0}
        if not totals[athlete_key]['name']:
            totals[athlete_key]['name'] = (a.get('name') or '').strip()
        if not totals[athlete_key]['name']:
            totals[athlete_key]['name'] = athlete_key.replace('name:', '')

        if not totals[athlete_key]['name']:
            continue
        totals[athlete_key]['meters'] += a.get('distance', 0) or 0
    # km に変換
    for v in totals.values():
        v['km'] = round(v['meters'] / 1000.0, 2)
    return totals


def get_recent_week_ride_distance_by_member():
    access_token, _, _ = refresh_access_token(STRAVA_REFRESH_TOKEN)
    after_ts = last_7_days_unix()
    activities = get_club_activities(access_token, after_ts)
    totals = aggregate_weekly_rides(activities)

    rows = []
    for aid, item in totals.items():
        member_name = item['name'] or f"id:{aid}"
        rows.append({
            'athlete_id': aid,
            'name': member_name,
            'distance_m': round(item['meters'], 1),
            'distance_km': item['km'],
        })
    rows.sort(key=lambda x: x['distance_m'], reverse=True)
    return rows

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