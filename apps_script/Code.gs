// Receives call records from the voice-agent webhook and appends them to this Sheet.
// Setup: Extensions → Apps Script, paste this file, set the TOKEN script property
// (Project Settings → Script properties), then Deploy → New deployment → Web app,
// "Execute as: Me", "Who has access: Anyone". Put the /exec URL in SHEETS_WEBHOOK_URL.

const TAB = 'Calls';

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  const token = PropertiesService.getScriptProperties().getProperty('TOKEN');
  if (!token || body.token !== token) {
    return json({ ok: false, error: 'unauthorized' });
  }

  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(TAB) || spreadsheet.insertSheet(TAB);

  // Two webhook deliveries for the same call can arrive together; serialise them.
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(body.header);
    }
    const lastRow = sheet.getLastRow();
    const callIds = lastRow > 1 ? sheet.getRange(2, 1, lastRow - 1, 1).getValues().flat() : [];
    if (callIds.includes(body.row[0])) {
      return json({ ok: true, is_new: false });
    }
    sheet.appendRow(body.row);
    return json({ ok: true, is_new: true });
  } finally {
    lock.releaseLock();
  }
}

function json(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(ContentService.MimeType.JSON);
}
