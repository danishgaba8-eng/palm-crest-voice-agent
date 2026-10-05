"""Retell post-call webhook: log every call to the CRM sheet, SMS-confirm bookings.

Run locally:  uvicorn voice_agent.main:app --port 8000
"""

import json
import logging
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from .records import CallRecord
from .sinks import CallLog, SmsSender

log = logging.getLogger(__name__)

Verifier = Callable[[str, str], bool]


def create_app(
    call_log: CallLog,
    sms: SmsSender,
    verify_signature: Verifier,
    agency_name: str,
    agency_phone: str = "",
) -> FastAPI:
    app = FastAPI(title="Voice agent webhook")

    def process_call(record: CallRecord) -> None:
        try:
            is_new = call_log.append_if_new(record)
        except Exception:
            log.exception("Failed to log call %s to sheet", record.call_id)
            is_new = True  # Still confirm the booking; a missing SMS is worse than a missing row.
        if not is_new:
            log.info("Call %s already logged; skipping", record.call_id)
            return

        if record.appointment_booked and record.lead_phone:
            try:
                sms.send(record.lead_phone, confirmation_sms(record, agency_name, agency_phone))
            except Exception:
                log.exception("Failed to send confirmation SMS for call %s", record.call_id)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/retell/webhook", status_code=204)
    async def retell_webhook(request: Request, background: BackgroundTasks) -> Response:
        raw = (await request.body()).decode("utf-8")
        if not verify_signature(raw, request.headers.get("x-retell-signature", "")):
            raise HTTPException(status_code=401, detail="Invalid signature")

        payload = json.loads(raw)
        # Retell also sends call_started and call_ended; only call_analyzed has the summary.
        if payload.get("event") == "call_analyzed":
            # Reply right away and do the slow work after; Retell retries slow webhooks.
            background.add_task(process_call, CallRecord.from_retell(payload["call"]))
        return Response(status_code=204)

    return app


def confirmation_sms(record: CallRecord, agency_name: str, agency_phone: str) -> str:
    greeting = f"Hi {record.lead_name}," if record.lead_name else "Hi,"
    when = f" for {record.appointment_time}" if record.appointment_time else ""
    contact = f" To change it, call {agency_phone}." if agency_phone else ""
    return f"{greeting} your property consultation with {agency_name} is confirmed{when}.{contact}"


def build_default_app() -> FastAPI:
    from retell import Retell

    from .config import Settings
    from .sinks import AppsScriptCallLog, DisabledSms, GoogleSheetCallLog, TwilioSms

    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    retell = Retell(api_key=settings.retell_api_key)

    def verify(body: str, signature: str) -> bool:
        return bool(signature) and retell.verify(body, api_key=settings.retell_api_key, signature=signature)

    sms = (
        TwilioSms(settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number)
        if settings.sms_enabled
        else DisabledSms()
    )
    if settings.sheets_webhook_url:
        call_log = AppsScriptCallLog(settings.sheets_webhook_url, settings.sheets_webhook_token)
    else:
        call_log = GoogleSheetCallLog(
            settings.google_sheet_id,
            settings.google_sheet_tab,
            service_account_file=settings.google_service_account_file,
            service_account_json=settings.google_service_account_json,
        )
    return create_app(
        call_log=call_log,
        sms=sms,
        verify_signature=verify,
        agency_name=settings.agency_name,
        agency_phone=settings.agency_phone,
    )


def __getattr__(name: str):
    # Lets `uvicorn voice_agent.main:app` build the real app, while tests import
    # create_app without needing credentials.
    if name == "app":
        return build_default_app()
    raise AttributeError(name)
