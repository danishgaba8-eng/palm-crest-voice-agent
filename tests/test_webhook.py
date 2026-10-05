import json

import pytest
from fastapi.testclient import TestClient

from voice_agent.main import confirmation_sms, create_app
from voice_agent.records import SHEET_HEADER, CallRecord


class FakeCallLog:
    def __init__(self, fail: bool = False):
        self.rows: dict[str, CallRecord] = {}
        self.fail = fail

    def append_if_new(self, record: CallRecord) -> bool:
        if self.fail:
            raise RuntimeError("sheets down")
        if record.call_id in self.rows:
            return False
        self.rows[record.call_id] = record
        return True


class FakeSms:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send(self, to: str, body: str) -> None:
        self.sent.append((to, body))


def analyzed_call(**overrides):
    call = {
        "call_id": "call_123",
        "direction": "inbound",
        "from_number": "+971501234567",
        "to_number": "+12025550100",
        "start_timestamp": 1_760_000_000_000,
        "end_timestamp": 1_760_000_154_400,
        "transcript": "Agent: Hello...\nUser: Hi...",
        "recording_url": "https://example.com/rec.wav",
        "disconnection_reason": "agent_hangup",
        "call_analysis": {
            "call_summary": "Caller wants a 2-bed rental in JVC.",
            "user_sentiment": "Positive",
            "call_successful": True,
            "custom_analysis_data": {
                "lead_name": "Sara",
                "intent": "rent",
                "property_type": "apartment",
                "area": "JVC",
                "budget_aed": 95000,
                "timeline": "within 1 month",
                "appointment_booked": True,
                "appointment_time": "Thu 9 Oct, 4:00 PM",
            },
        },
    }
    call.update(overrides)
    return {"event": "call_analyzed", "call": call}


@pytest.fixture
def deps():
    return FakeCallLog(), FakeSms()


def client_for(call_log, sms, valid_signature=True):
    app = create_app(
        call_log=call_log,
        sms=sms,
        verify_signature=lambda body, sig: valid_signature,
        agency_name="Palm Crest Realty",
        agency_phone="+97140000000",
    )
    return TestClient(app)


def post(client, payload):
    return client.post(
        "/retell/webhook",
        content=json.dumps(payload),
        headers={"x-retell-signature": "sig", "content-type": "application/json"},
    )


def test_rejects_bad_signature(deps):
    call_log, sms = deps
    resp = post(client_for(call_log, sms, valid_signature=False), analyzed_call())
    assert resp.status_code == 401
    assert not call_log.rows and not sms.sent


def test_booked_call_is_logged_and_confirmed(deps):
    call_log, sms = deps
    resp = post(client_for(call_log, sms), analyzed_call())
    assert resp.status_code == 204

    record = call_log.rows["call_123"]
    assert record.lead_phone == "+971501234567"
    assert record.duration_s == 154
    assert record.budget_aed == "95000"
    assert sms.sent == [
        (
            "+971501234567",
            "Hi Sara, your property consultation with Palm Crest Realty is confirmed "
            "for Thu 9 Oct, 4:00 PM. To change it, call +97140000000.",
        )
    ]


def test_ignores_events_other_than_call_analyzed(deps):
    call_log, sms = deps
    payload = analyzed_call()
    payload["event"] = "call_ended"
    assert post(client_for(call_log, sms), payload).status_code == 204
    assert not call_log.rows and not sms.sent


def test_retried_webhook_does_not_double_sms(deps):
    call_log, sms = deps
    client = client_for(call_log, sms)
    post(client, analyzed_call())
    post(client, analyzed_call())
    assert len(sms.sent) == 1


def test_no_sms_without_booking(deps):
    call_log, sms = deps
    payload = analyzed_call()
    payload["call"]["call_analysis"]["custom_analysis_data"]["appointment_booked"] = False
    post(client_for(call_log, sms), payload)
    assert "call_123" in call_log.rows
    assert not sms.sent


def test_outbound_call_texts_the_dialled_number(deps):
    call_log, sms = deps
    post(client_for(call_log, sms), analyzed_call(direction="outbound", from_number="+12025550100", to_number="+971559876543"))
    assert sms.sent[0][0] == "+971559876543"


def test_sms_still_sent_when_sheet_fails():
    sms = FakeSms()
    post(client_for(FakeCallLog(fail=True), sms), analyzed_call())
    assert len(sms.sent) == 1


def test_transfer_and_missing_analysis_fields():
    record = CallRecord.from_retell(
        {"call_id": "c1", "direction": "inbound", "from_number": "+1", "disconnection_reason": "call_transfer"}
    )
    assert record.transferred is True
    assert record.appointment_booked is False
    row = record.to_row()
    assert len(row) == len(SHEET_HEADER)
    assert row[SHEET_HEADER.index("successful")] == ""


def test_sms_without_name_or_time():
    record = CallRecord.from_retell({"call_id": "c1", "from_number": "+1"})
    assert confirmation_sms(record, "Palm Crest Realty", "") == (
        "Hi, your property consultation with Palm Crest Realty is confirmed."
    )


def test_settings_accept_service_account_json_instead_of_file(monkeypatch):
    from voice_agent.config import Settings

    monkeypatch.setattr("voice_agent.config.load_dotenv", lambda: None)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.setenv("RETELL_API_KEY", "key_test")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet123")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}')

    settings = Settings.from_env()
    assert settings.google_service_account_json == '{"type": "service_account"}'
    assert settings.google_service_account_file == ""
    assert settings.sms_enabled is False
