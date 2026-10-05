"""Settings loaded from environment variables (see .env.example)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    retell_api_key: str
    google_service_account_file: str
    google_service_account_json: str
    google_sheet_id: str
    google_sheet_tab: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    agency_name: str
    agency_phone: str

    @property
    def sms_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        # Locally a key file is simplest; on hosts like Render, paste the JSON into an env var instead.
        account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        return cls(
            retell_api_key=_required("RETELL_API_KEY"),
            google_service_account_file="" if account_json else _required("GOOGLE_SERVICE_ACCOUNT_FILE"),
            google_service_account_json=account_json,
            google_sheet_id=_required("GOOGLE_SHEET_ID"),
            google_sheet_tab=os.getenv("GOOGLE_SHEET_TAB", "Calls"),
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
            agency_name=os.getenv("AGENCY_NAME", "Palm Crest Realty"),
            agency_phone=os.getenv("AGENCY_PHONE", ""),
        )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
