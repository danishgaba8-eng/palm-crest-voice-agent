# Post-call analysis fields

In the Retell agent, open **Post-Call Analysis** and add these fields. Names must match exactly,
because the webhook reads them from `call_analysis.custom_analysis_data`.

| Name | Type | Description (paste into Retell) |
|---|---|---|
| `lead_name` | Text | The caller's name, if given. Empty if unknown. |
| `intent` | Selector: `buy`, `rent`, `sell`, `other` | What the caller wants to do. |
| `property_type` | Text | Property type and bedrooms, e.g. "2-bed apartment". |
| `area` | Text | Preferred areas mentioned, comma-separated. |
| `budget_aed` | Number | Budget in AED: annual rent for renters, price for buyers. Empty if not given. |
| `timeline` | Text | When they want to move or buy, e.g. "within 1 month". |
| `appointment_booked` | Boolean | True only if `book_appointment_cal` succeeded during the call. |
| `appointment_time` | Text | The booked slot as said to the caller, e.g. "Thu 9 Oct, 4:00 PM". Empty if none. |

Retell's built-in fields (`call_summary`, `user_sentiment`, `call_successful`) are also written to the sheet.
