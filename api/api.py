from pathlib import Path
import os

import requests
from dotenv import load_dotenv

# Load .env from project root.
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

STRAVA_REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN")
STRAVA_CLUB_ID = os.environ.get("STRAVA_CLUB_ID")
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")

if not STRAVA_REFRESH_TOKEN:
    raise SystemExit("環境変数 STRAVA_REFRESH_TOKEN を .env に設定してください")

if not STRAVA_CLUB_ID:
    raise SystemExit("環境変数 STRAVA_CLUB_ID を .env に設定してください")

if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
    raise SystemExit("環境変数 STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET を .env に設定してください")


def refresh_access_token(refresh_token: str) -> str:
    token_url = "https://www.strava.com/oauth/token"
    response = requests.post(
        token_url,
        data={
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    response.raise_for_status()
    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError("Stravaのaccess_token取得に失敗しました")
    return access_token


def get_club_activities(
    access_token: str,
    page: int = 1,
    per_page: int = 30,
    after: int | None = None,
    before: int | None = None,
) -> requests.Response:
    url = f"https://www.strava.com/api/v3/clubs/{STRAVA_CLUB_ID}/activities"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "page": page,
        "per_page": per_page
    }
    if after is not None:
        params["after"] = after
    if before is not None:
        params["before"] = before
    response = requests.get(url, headers=headers, params=params)
    return response


if __name__ == "__main__":
    token = refresh_access_token(STRAVA_REFRESH_TOKEN)
    response = get_club_activities(token)
    print(response.json())