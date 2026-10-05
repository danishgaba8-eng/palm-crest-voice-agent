# Real estate AI voice agent (demo)

An inbound and outbound phone agent for a fictional Dubai agency, **Palm Crest Realty**. It answers FAQs,
qualifies buyers, renters and landlords, books consultations on Cal.com and transfers urgent calls to a
human. After each call, a webhook logs the lead to a Google Sheet (the CRM) and sends an SMS confirmation
for bookings.

```
Caller ⇄ Twilio/Retell number ⇄ Retell agent (Deepgram STT · GPT · ElevenLabs TTS)
                                     ├─ check_availability_cal / book_appointment_cal → Cal.com
                                     ├─ transfer_call → your mobile
                                     └─ call_analyzed webhook → this service
                                                                 ├─ Google Sheet row
                                                                 └─ Twilio SMS (if booked)
```

## 1. Cal.com
1. Create an event type "Property consultation", 30 min, timezone Asia/Dubai, hours Sun–Fri 9:00–19:00.
2. Settings → Developer → API keys: create a key. Note the **event type ID** (shown in the event's URL).

## 2. Google Sheet (CRM)
1. Create a blank sheet and copy its ID from the URL (`/d/<ID>/edit`).
2. In Google Cloud: create a project, enable the **Google Sheets API**, then create a service account and
   download its JSON key as `voice-agent/service-account.json`.
3. Share the sheet with the service account's `client_email` as Editor.
   The service writes the header row itself on first run.

## 3. Run the webhook
```bash
cd voice-agent
python -m venv .venv && .venv/Scripts/activate   # Windows Git Bash; use bin/activate on Mac/Linux
pip install -r requirements.txt
cp .env.example .env    # fill in values
uvicorn voice_agent.main:app --port 8000
```
For a quick local test, expose it to Retell with `ngrok http 8000`.

### Deploy to Render (always on)
1. In Render: **New → Blueprint**, pick this repo. [render.yaml](render.yaml) defines the web service.
2. Fill the secret env vars when prompted. For `GOOGLE_SERVICE_ACCOUNT_JSON`, paste the whole contents of
   the service-account key file (no file upload needed).
3. Once it's live, check `https://<service>.onrender.com/health` returns `{"status":"ok"}`.

The free plan sleeps after ~15 minutes idle and takes up to a minute to wake, so the first webhook after a
quiet spell can time out. Use a paid instance (or an uptime pinger on `/health`) before showing the demo to clients.

Tests: `python -m pytest`

## 4. Retell agent
1. Create a **Single Prompt** agent. Paste [agent/prompt.md](agent/prompt.md) as the prompt.
2. **Models:** LLM GPT-4.1 (or GPT-4o), voice from **ElevenLabs**, transcriber **Deepgram**. Language:
   multilingual, if you want to demo English and Arabic.
3. **Dynamic variable defaults:** `call_type` = `inbound`, `lead_name` = (empty), `call_reason` = (empty).
4. **Functions:**
   - `check_availability_cal`, `book_appointment_cal`, `list_bookings_cal` and `reschedule_booking_cal`:
     built-in Cal.com functions (Add → Cal.com). Connect your API key once, set the event type ID where asked,
     and set `timezone` to the fixed value `Asia/Dubai`. Leave `booking_uid` as "let AI decide", so the agent
     takes it from the `list_bookings_cal` result.
   - `transfer_call`: your mobile number.
   - `end_call`.
5. **Post-call analysis:** add the fields in [agent/post_call_analysis.md](agent/post_call_analysis.md).
6. **Webhook URL:** `https://<your-host>/retell/webhook`. Signatures are verified with your Retell API key.
7. Check that `{{current_time_Asia/Dubai}}` resolves in a web test call. If it doesn't, switch to
   `{{current_time}}` and set the agent's timezone.

## 5. Phone number
- **Simplest:** buy a number in Retell (Phone Numbers → Buy) and assign the agent to it for inbound and outbound.
- **Via Twilio:** buy a Twilio number, set up Elastic SIP Trunking pointing at Retell's SIP URI, then
  import the number in Retell. This is what lets the portfolio say "Twilio".
- Put the same number (or another Twilio number) in `TWILIO_FROM_NUMBER` for SMS. Texting UAE numbers
  needs a registered alphanumeric sender ID; for the demo, text your own number on a trial account.

## 6. Outbound call
```bash
python -m voice_agent.outbound --to +971501234567 --name "Sara" --reason "enquired about 2-bed rentals in JVC"
```
Only call numbers that consented, such as your own, for the demo.

## 7. Portfolio proof
Record three calls (FAQ plus qualification, booking, urgent transfer), and screenshot the Sheet row,
the Cal.com booking and the SMS. Cut them into a 60–90 second video for the Upwork entry.
