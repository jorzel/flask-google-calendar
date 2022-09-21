from __future__ import print_function

import datetime
import os.path
from typing import Optional, Sequence, TypedDict

from flask import Flask, jsonify, redirect, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
app.config["SESSION_TYPE"] = "filesystem"


CALLBACK_URL = os.environ.get("CALLBACK_URL")
API_CLIENT_ID = os.environ.get("API_CLIENT_ID")
API_CLIENT_SECRET = os.environ.get("API_CLIENT_SECRET")
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CredentialsPayload(TypedDict):
    token: str
    refresh_token: Optional[str]
    token_uri: str
    client_id: str
    client_secret: str
    scopes: str


class CalendarClient:
    API_SERVICE = "calendar"
    API_VERSION = "v3"

    def __init__(self, client_id: str, client_secret: str, scopes: Sequence[str]):
        self._client_id = client_id
        self._client_secret = client_secret
        self._scopes = scopes
        self._client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

    def get_auth_url(self, callback_url: str) -> str:
        flow = self._get_flow(callback_url)
        auth_url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true"
        )
        return auth_url

    def get_credentials(self, code: str, callback_url: str) -> Credentials:
        flow = self._get_flow(callback_url)
        flow.fetch_token(code=code)
        return flow.credentials

    def refresh_credentials(
        self, credentials_payload: CredentialsPayload
    ) -> Credentials:
        credentials = Credentials.from_authorized_user_info(credentials_payload)
        if not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
        return credentials

    def get_upcoming_events(
        self,
        credentials_payload: CredentialsPayload,
        n: int = 10,
    ) -> list[dict]:
        try:
            credentials = self.refresh_credentials(credentials_payload)
            service = self._build_service(credentials)
            now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
            print(f"Getting the upcoming {n} events")
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=now,
                    maxResults=n,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            if not events:
                print("No upcoming events found.")
                return []
            return events

        except HttpError as error:
            print("An error occurred: %s" % error)
            return []

    def _get_flow(self, callback_url: str) -> Flow:
        return Flow.from_client_config(
            self._client_config, self._scopes, redirect_uri=callback_url
        )

    def _build_service(self, credentials: Credentials):
        return build(self.API_SERVICE, self.API_VERSION, credentials=credentials)


client = CalendarClient(API_CLIENT_ID, API_CLIENT_SECRET, SCOPES)


def is_authenticated() -> Optional[CredentialsPayload]:
    if session.get("credentials"):
        return session["credentials"]


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/callback")
def callback():
    credentials = client.get_credentials(
        code=request.args.get("code"),
        callback_url=CALLBACK_URL,
    )
    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    return credentials.to_json()


@app.route("/auth")
def auth():
    return redirect(client.get_auth_url(CALLBACK_URL))


@app.route("/events")
def events():
    credentials_payload = is_authenticated()
    if not credentials_payload:
        return redirect(url_for("auth"))
    events = client.get_upcoming_events(credentials_payload, n=15)
    serialized_events = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        serialized_events.append({"start": start, "summary": event["summary"]})
    return jsonify(serialized_events)
