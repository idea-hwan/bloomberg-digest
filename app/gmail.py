from __future__ import annotations

import json
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module=r"google\.api_core\._python_version_support",
)

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.errors import ConfigError
from app.paths import configured_path

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailClient:
    def __init__(self, service):
        self._service = service

    def search(self, query: str) -> list[str]:
        ids: list[str] = []
        page_token = None
        while True:
            response = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token, maxResults=100)
                .execute()
            )
            ids.extend(item["id"] for item in response.get("messages", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return ids

    def fetch(self, message_id: str, fmt: str = "full") -> dict:
        kwargs = {"userId": "me", "id": message_id, "format": fmt}
        if fmt == "metadata":
            kwargs["metadataHeaders"] = ["Subject", "From", "Date"]
        return self._service.users().messages().get(**kwargs).execute()


def _credentials(
    credentials_path: Path,
    token_path: Path,
    launch_browser: bool,
    force: bool = False,
) -> Credentials:
    if not credentials_path.exists():
        raise ConfigError(
            "credentials.json이 없습니다. Google Cloud에서 데스크톱 앱 OAuth 클라이언트를 받아 "
            f"{credentials_path}에 두세요."
        )

    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ConfigError(
                "token.json을 읽지 못했습니다. 지운 뒤 python -m app auth 를 다시 실행하세요."
            ) from exc

    if creds and creds.valid and not force:
        return creds

    if creds and creds.expired and creds.refresh_token and not launch_browser and not force:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            raise ConfigError(
                "Gmail 토큰이 만료되었습니다. python -m app auth 를 다시 실행하세요."
            ) from exc
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not launch_browser:
        raise ConfigError("Gmail 로그인이 필요합니다. python -m app auth 를 먼저 실행하세요.")

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def connect(launch_browser: bool = False, force: bool = False) -> GmailClient:
    creds = _credentials(
        configured_path("GMAIL_CREDENTIALS_PATH", "credentials.json"),
        configured_path("GMAIL_TOKEN_PATH", "token.json"),
        launch_browser or force,
        force,
    )
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return GmailClient(service)


def authenticate(force: bool = False) -> None:
    connect(launch_browser=True, force=force)
