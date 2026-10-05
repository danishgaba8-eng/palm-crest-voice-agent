"""Turns Retell's `call_analyzed` payload into a flat record for the CRM sheet."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Google Sheets rejects cells over 50,000 characters.
MAX_CELL_CHARS = 45_000

SHEET_HEADER = [
    "call_id",
    "started_at_utc",
    "direction",
    "lead_phone",
    "duration_s",
    "lead_name",
    "intent",
    "property_type",
    "area",
    "budget_aed",
    "timeline",
    "appointment_booked",
    "appointment_time",
    "transferred",
    "sentiment",
    "successful",
    "summary",
    "recording_url",
    "transcript",
]


@dataclass
class CallRecord:
    call_id: str
    direction: str
    lead_phone: str
    started_at_utc: str
    duration_s: int
    summary: str
    sentiment: str
    successful: bool | None
    transferred: bool
    recording_url: str
    transcript: str
    # Fields extracted by Retell's post-call analysis (see agent/post_call_analysis.md)
    lead_name: str
    intent: str
    property_type: str
    area: str
    budget_aed: str
    timeline: str
    appointment_booked: bool
    appointment_time: str

    @classmethod
    def from_retell(cls, call: dict[str, Any]) -> "CallRecord":
        analysis = call.get("call_analysis") or {}
        custom = analysis.get("custom_analysis_data") or {}
        direction = call.get("direction", "inbound")
        # The lead is whoever is on the other end from our agent's number.
        lead_phone = call.get("from_number") if direction == "inbound" else call.get("to_number")

        start_ms = call.get("start_timestamp")
        end_ms = call.get("end_timestamp")

        return cls(
            call_id=call["call_id"],
            direction=direction,
            lead_phone=lead_phone or "",
            started_at_utc=_iso(start_ms),
            duration_s=round((end_ms - start_ms) / 1000) if start_ms and end_ms else 0,
            summary=analysis.get("call_summary", ""),
            sentiment=analysis.get("user_sentiment", ""),
            successful=analysis.get("call_successful"),
            transferred=call.get("disconnection_reason") == "call_transfer",
            recording_url=call.get("recording_url", ""),
            transcript=call.get("transcript", ""),
            lead_name=_text(custom.get("lead_name")),
            intent=_text(custom.get("intent")),
            property_type=_text(custom.get("property_type")),
            area=_text(custom.get("area")),
            budget_aed=_text(custom.get("budget_aed")),
            timeline=_text(custom.get("timeline")),
            appointment_booked=custom.get("appointment_booked") is True,
            appointment_time=_text(custom.get("appointment_time")),
        )

    def to_row(self) -> list[Any]:
        values = {
            **self.__dict__,
            "successful": "" if self.successful is None else self.successful,
            "transcript": self.transcript[:MAX_CELL_CHARS],
        }
        return [values[column] for column in SHEET_HEADER]


def _iso(ms: int | None) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()
