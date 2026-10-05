"""Where call records go: a Google Sheet acting as the CRM, and Twilio SMS."""

import json
import logging
from typing import Protocol

from .records import SHEET_HEADER, CallRecord

log = logging.getLogger(__name__)


class CallLog(Protocol):
    def append_if_new(self, record: CallRecord) -> bool:
        """Store the record. Returns False if this call_id was already stored."""


class SmsSender(Protocol):
    def send(self, to: str, body: str) -> None: ...


class GoogleSheetCallLog:
    def __init__(self, sheet_id: str, tab: str, service_account_file: str = "", service_account_json: str = ""):
        import gspread

        if service_account_json:
            client = gspread.service_account_from_dict(json.loads(service_account_json))
        else:
            client = gspread.service_account(filename=service_account_file)
        spreadsheet = client.open_by_key(sheet_id)
        try:
            self._ws = spreadsheet.worksheet(tab)
        except gspread.WorksheetNotFound:
            self._ws = spreadsheet.add_worksheet(tab, rows=1000, cols=len(SHEET_HEADER))
        if self._ws.row_values(1) != SHEET_HEADER:
            self._ws.update([SHEET_HEADER], "A1")

    def append_if_new(self, record: CallRecord) -> bool:
        # Retell retries webhooks that fail or time out, so dedupe on call_id.
        if self._ws.find(record.call_id, in_column=1):
            return False
        self._ws.append_row(record.to_row(), value_input_option="RAW")
        return True


class AppsScriptCallLog:
    """Posts rows to the Sheet's Apps Script web app (apps_script/Code.gs)."""

    def __init__(self, url: str, token: str, client=None):
        import httpx

        self._url = url
        self._token = token
        # Apps Script answers POSTs with a redirect to the actual response.
        self._client = client or httpx.Client(timeout=20, follow_redirects=True)

    def append_if_new(self, record: CallRecord) -> bool:
        response = self._client.post(
            self._url, json={"token": self._token, "header": SHEET_HEADER, "row": record.to_row()}
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise RuntimeError(f"Apps Script rejected the row: {result.get('error')}")
        return bool(result.get("is_new"))


class TwilioSms:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        from twilio.rest import Client

        self._client = Client(account_sid, auth_token)
        self._from = from_number

    def send(self, to: str, body: str) -> None:
        self._client.messages.create(to=to, from_=self._from, body=body)


class DisabledSms:
    def send(self, to: str, body: str) -> None:
        log.info("SMS disabled; would have sent to %s: %s", to, body)
