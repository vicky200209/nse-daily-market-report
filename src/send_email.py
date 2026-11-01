"""Step 4: email the PDF.

Environment variables (set them in the Claude Routine / cloud environment, never in this repo):
  REPORT_RECIPIENTS   comma-separated list, e.g. "me@gmail.com, friend@outlook.com"
  GMAIL_USER          the Gmail address that sends the mail
  GMAIL_APP_PASSWORD  16-character Gmail App Password (not your normal password)
If SMTP is blocked (e.g. in Claude cloud environments), use the Google Apps Script sender instead
(see tools/gmail_sender.gs) - it sends from your own Gmail over HTTPS:
  APPS_SCRIPT_URL     the web-app URL of your deployed script
  MAIL_TOKEN          the same secret you set in the script's properties
Other fallback:
  BREVO_API_KEY       Brevo (free tier) API key
"""
import base64
import glob
import json
import os
import smtplib
import ssl
import sys
import urllib.request
from email.message import EmailMessage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")


def recipients():
    raw = os.environ.get("REPORT_RECIPIENTS", "")
    return [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]


def _summary():
    try:
        with open(os.path.join(OUT, "data.json")) as f:
            d = json.load(f)
        n = {}
        if os.path.exists(os.path.join(OUT, "narrative.json")):
            with open(os.path.join(OUT, "narrative.json")) as f:
                n = json.load(f)
        nifty = next((i for i in d["market"]["indices"] if i["symbol"] == "^NSEI"), None)
        head = n.get("headline", "")
        lines = n.get("market_story", [])
        subj = f"NSE Daily Report - {d['session_date_human']}"
        if nifty:
            subj += f" | Nifty {nifty['pct']:+.2f}%"
        body = f"{head}\n\n" + "\n".join("- " + x for x in lines)
        body += f"\n\nLesson #{d['course_day']} and analysis of {len(d['stocks'])} stocks are in the attached PDF."
        body += "\n\nFor education only - not investment advice."
        return subj, body
    except Exception:
        return "NSE Daily Report", "Your daily report is attached."


def send(pdf_path=None, subject=None, body=None):
    to = recipients()
    if not to:
        sys.exit("ERROR: REPORT_RECIPIENTS is not set")
    if pdf_path is None:
        pdfs = sorted(glob.glob(os.path.join(OUT, "NSE_Daily_Report_*.pdf")))
        pdf_path = pdfs[-1] if pdfs else None
    s, b = _summary()
    subject, body = subject or s, body or b
    user, pwd = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    errors = []
    url, token = os.environ.get("APPS_SCRIPT_URL"), os.environ.get("MAIL_TOKEN")
    if url and token:
        payload = {"token": token, "to": to, "subject": subject, "body": body}
        if pdf_path:
            with open(pdf_path, "rb") as f:
                payload["pdf_b64"] = base64.b64encode(f.read()).decode()
            payload["filename"] = os.path.basename(pdf_path)
        req = urllib.request.Request(url.strip(), data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                txt = r.read().decode(errors="replace")
            if txt.strip().startswith("{"):
                res = json.loads(txt)
            else:  # Google returned an HTML page - show its title/text so the cause is visible
                import re
                title = re.search(r"<title>(.*?)</title>", txt, re.S)
                text = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", txt, flags=re.S)).strip()
                res = {"ok": False, "error": f"HTML page from Google (title: {title.group(1).strip() if title else '-'}): {text[:300]} "
                                             f"| URL used ends with ...{url.strip()[-12:]}"}
            if res.get("ok"):
                print(f"OK: emailed {len(to)} recipient(s) via Gmail (Apps Script)")
                return
            errors.append(f"Apps Script failed: {res.get('error')}")
        except Exception as e:
            errors.append(f"Apps Script failed: {e}")
        print(errors[-1], file=sys.stderr)
    if user and pwd:
        try:
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = subject, f"NSE Daily Report <{user}>", user
            msg["Bcc"] = ", ".join(to)  # recipients can't see each other
            msg.set_content(body)
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(pdf_path))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=20) as smtp:
                smtp.login(user, pwd.replace(" ", ""))
                smtp.send_message(msg)
            print(f"OK: emailed {len(to)} recipient(s) via Gmail")
            return
        except Exception as e:
            errors.append(f"Gmail SMTP failed: {e}")
            print(errors[-1], file=sys.stderr)
    key = os.environ.get("BREVO_API_KEY")
    if key:
        sender = os.environ.get("BREVO_SENDER", user or to[0])
        payload = {"sender": {"name": "NSE Daily Report", "email": sender}, "to": [{"email": sender}],
                   "bcc": [{"email": x} for x in to], "subject": subject, "textContent": body}
        if pdf_path:
            with open(pdf_path, "rb") as f:
                payload["attachment"] = [{"name": os.path.basename(pdf_path), "content": base64.b64encode(f.read()).decode()}]
        req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode(),
                                     headers={"api-key": key, "Content-Type": "application/json", "accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                print(f"OK: emailed {len(to)} recipient(s) via Brevo ({r.status})")
                return
        except Exception as e:
            errors.append(f"Brevo failed: {e}")
    sys.exit("ERROR: could not send email. " + " | ".join(errors or ["No APPS_SCRIPT_URL/MAIL_TOKEN, GMAIL_USER/GMAIL_APP_PASSWORD or BREVO_API_KEY set"]))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--error":
        send(pdf_path=False, subject="NSE Daily Report - FAILED today",
             body="The automatic report could not be created today.\n\nDetails:\n" + " ".join(sys.argv[2:]))
    else:
        send()
