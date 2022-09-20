from __future__ import print_function

import datetime
import json
import os.path

from flask import Flask, jsonify, redirect, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
app = Flask(__name__)


class CalendarClient:
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    API_SERVICE = "calendar"
    API_VERSION = "v3"
    TOKEN_FILE = "token.json"
    API_CLIENT_ID = os.environ.get("API_CLIENT_ID")
    API_CLIENT_SECRET = os.environ.get("API_CLIENT_SECRET")
    CLIENT_CONFIG = {
        "web": {
            "client_id": API_CLIENT_ID,
            "client_secret": API_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    @classmethod
    def get_flow(cls, callback_url):
        return Flow.from_client_config(
            cls.CLIENT_CONFIG, cls.SCOPES, redirect_uri=callback_url
        )

    @classmethod
    def get_auth_url(cls, callback_url):
        flow = cls.get_flow(callback_url)
        auth_url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true"
        )

        return auth_url

    @classmethod
    def get_credentials(cls, code, callback_url):
        flow = cls.get_flow(callback_url)
        flow.fetch_token(
            code=code,
        )
        return flow.credentials

    @classmethod
    def get_upcoming_events(cls, n: int = 10) -> list[dict]:
        try:
            service = cls._build_service()
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

    @classmethod
    def _build_service(cls):
        return build(
            cls.API_SERVICE, cls.API_VERSION, credentials=cls._get_credentials()
        )


def main():
    events = CalendarClient.get_upcoming_events(20)
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        print(start, event)


if __name__ == "__main__":
    main()


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/callback")
def callback():
    creds = CalendarClient.get_credentials(
        code=request.args.get("code"),
        callback_url="https://a74a-2a02-a31a-c23d-df80-d36f-b656-373-66f8.eu.ngrok.io/callback",
    )
    # store it ine a session
    return creds.to_json()


@app.route("/auth")
def auth():
    return redirect(
        CalendarClient.get_auth_url(
            "https://a74a-2a02-a31a-c23d-df80-d36f-b656-373-66f8.eu.ngrok.io/callback"
        )
    )


@app.route("/events")
def events():
    events = CalendarClient.get_upcoming_events(20)
    serialized_events = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        serialized_events.append({"start": start, "summary": event["summary"]})
    return jsonify(serialized_events)
