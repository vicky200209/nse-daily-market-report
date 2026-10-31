/**
 * Gmail sender for NSE Daily Market Report.
 * Paste this into https://script.google.com (signed in with the SENDER Gmail),
 * then Deploy > New deployment > Web app (Execute as: Me, Who has access: Anyone).
 *
 * Security: set a secret token in Project Settings > Script properties:
 *   MAIL_TOKEN = <any long random text>
 * Put the same value in the Claude environment as MAIL_TOKEN.
 */

// SAFETY: only these addresses can ever receive mail from this script. Add yours (lowercase).
var ALLOWED = [];

function doPost(e) {
  var req = JSON.parse(e.postData.contents);
  var token = PropertiesService.getScriptProperties().getProperty('MAIL_TOKEN');
  if (!token || req.token !== token) {
    return ContentService.createTextOutput(JSON.stringify({ok: false, error: 'bad token'}));
  }
  var to = req.to.filter(function (x) { return ALLOWED.indexOf(x.trim().toLowerCase()) !== -1; });
  if (to.length === 0) {
    return ContentService.createTextOutput(JSON.stringify({ok: false, error: 'no allowed recipients'}));
  }
  var options = {name: 'NSE Daily Report', bcc: to.join(',')};
  if (req.pdf_b64) {
    options.attachments = [Utilities.newBlob(Utilities.base64Decode(req.pdf_b64), 'application/pdf', req.filename)];
  }
  // sent to yourself, recipients in BCC so they can't see each other
  GmailApp.sendEmail(Session.getActiveUser().getEmail(), req.subject, req.body, options);
  return ContentService.createTextOutput(JSON.stringify({ok: true, sent: to.length}));
}

// Run this once from the editor to grant Gmail permission.
function authorize() {
  GmailApp.getAliases();
}
