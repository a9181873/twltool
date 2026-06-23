#!/usr/bin/env python3
"""Upload twltool screenshots to Google Drive, skip duplicates by filename.

ponytail: google-api-python-client + google-auth-oauthlib already installed,
           no new deps needed. Uses existing OAuth token.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

TOKEN_PATH = Path("/opt/data/google_token.json")
CLIENT_SECRET_PATH = Path("/opt/data/google_client_secret.json")
SCREENSHOT_DIR = Path("/opt/data/twltool/reports/screenshots")
DRIVE_FOLDER_NAME = "台壽巡檢截圖"
CREDS_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _load_client_config() -> dict:
    """Read OAuth client_id/secret from google_client_secret.json."""
    cs = json.loads(CLIENT_SECRET_PATH.read_text())
    key = "installed" if "installed" in cs else "web"
    return cs[key]


def _load_creds() -> Credentials:
    """Load OAuth token, auto-refresh if expired, persist updated token."""
    data = json.loads(TOKEN_PATH.read_text())
    client = _load_client_config()
    creds = Credentials(
        token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client["client_id"],
        client_secret=client["client_secret"],
        scopes=CREDS_SCOPES,
    )
    if creds.expired or not creds.valid:
        creds.refresh(Request())
        data["access_token"] = creds.token
        if creds.expiry:
            data["expiry"] = creds.expiry.timestamp()
        TOKEN_PATH.write_text(json.dumps(data, indent=2))
    return creds


def _find_or_create_folder(service, name: str) -> str:
    """Return folder ID, creating it if needed."""
    resp = service.files().list(
        q=f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces="drive",
        fields="files(id)",
        pageSize=1,
    ).execute()
    if resp.get("files"):
        return resp["files"][0]["id"]

    folder = service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id",
    ).execute()
    folder_id = folder["id"]
    print(f"[drive] created folder '{name}' ({folder_id})")
    return folder_id


def _list_existing(service, folder_id: str) -> set[str]:
    """Return set of filenames already in the Drive folder."""
    names = set()
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces="drive",
            fields="nextPageToken,files(name)",
            pageSize=100,
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            names.add(f["name"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return names


def upload_new() -> dict[str, int]:
    """Upload all new screenshots not already in Drive. Returns stats."""
    if not TOKEN_PATH.exists():
        print("[drive] no token, skipping")
        return {"uploaded": 0, "skipped": 0, "errors": 0}

    creds = _load_creds()
    service = build("drive", "v3", credentials=creds)
    folder_id = _find_or_create_folder(service, DRIVE_FOLDER_NAME)
    existing = _list_existing(service, folder_id)

    stats = {"uploaded": 0, "skipped": 0, "errors": 0}
    pngs = sorted(SCREENSHOT_DIR.glob("*.png"))

    for png in pngs:
        if png.name in existing:
            stats["skipped"] += 1
            continue
        try:
            media = MediaFileUpload(str(png), mimetype="image/png", resumable=True)
            service.files().create(
                body={"name": png.name, "parents": [folder_id]},
                media_body=media,
                fields="id",
            ).execute()
            stats["uploaded"] += 1
            print(f"[drive] uploaded {png.name}")
        except Exception as e:
            stats["errors"] += 1
            print(f"[drive] ERROR {png.name}: {e}", file=sys.stderr)

    return stats


if __name__ == "__main__":
    result = upload_new()
    print(json.dumps(result, ensure_ascii=False))
