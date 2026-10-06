#!/usr/bin/env python3
"""
notifier.py
===========
Standalone background notification runner invoked by Windows Task Scheduler.
Runs completely independently in the background even when the main Event Reminder
application is closed or turned off.

Capabilities:
1. Native Windows 10/11 Toast Notification (with sound and action click)
2. WhatsApp Notification via Twilio Cloud API (silent, no browser needed) or pywhatkit fallback
3. Email Notification via SMTP (Gmail, Outlook, custom SMTP)
4. Text-To-Speech spoken voice reminder (pyttsx3)
5. Google Maps navigation link included if location is specified
"""

import sys
import json
import os
import urllib.parse
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


# ==================== 1. Text to Speech ==================== #
def speak_alert(text: str):
    """Spoken voice alert."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as exc:
        print(f"[TTS] Voice error: {exc}")


# ==================== 2. Windows Native Toast ==================== #
def show_windows_toast(title: str, message: str, maps_url: str = ""):
    """Shows a native Windows 10/11 banner toast with sound and optional Maps button."""
    try:
        import winotify
        toast = winotify.Notification(
            app_id="Event Reminder",
            title=title[:60],
            msg=message[:200],
            duration="long"
        )
        toast.set_audio(winotify.audio.Default, loop=False)
        if maps_url:
            toast.add_actions(label="📍 Open Location in Maps", launch=maps_url)
        toast.show()
        return True
    except Exception as exc:
        print(f"[TOAST] winotify fallback error: {exc}")

    # Fallback to PowerShell balloon tip
    try:
        import subprocess
        safe_title = title.replace("'", "").replace('"', "")[:50]
        safe_msg = message.replace("'", "").replace('"', "").replace("\n", " ")[:180]
        ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.BalloonTipTitle = '{safe_title}'
$n.BalloonTipText  = '{safe_msg}'
$n.ShowBalloonTip(10000)
Start-Sleep -Milliseconds 12000
$n.Dispose()
"""
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps_cmd],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return True
    except Exception as exc:
        print(f"[TOAST] Fallback error: {exc}")
        return False


# ==================== 3. WhatsApp Messaging ==================== #
def send_whatsapp(phone: str, message: str, settings: dict):
    """
    Sends WhatsApp message:
    Method A: Twilio WhatsApp API (Silent, HTTP request, works 24/7 without browser)
    Method B: pywhatkit (opens WhatsApp Web)
    """
    if not phone:
        return

    # Normalize phone: ensure + prefix
    clean_phone = phone.strip()
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    account_sid = settings.get("twilio_account_sid") or os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token  = settings.get("twilio_auth_token") or os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = settings.get("twilio_whatsapp_from") or os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    # Priority 1: Direct Twilio API (Recommended for 100% background reliability)
    if account_sid and auth_token:
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            dest = f"whatsapp:{clean_phone}" if not clean_phone.startswith("whatsapp:") else clean_phone
            sender = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"
            resp = client.messages.create(body=message, from_=sender, to=dest)
            print(f"[WHATSAPP] Twilio sent successfully, SID: {resp.sid}")
            return
        except Exception as exc:
            print(f"[WHATSAPP] Twilio API error: {exc}. Trying fallback...")

    # Priority 2: pywhatkit instant send
    try:
        import pywhatkit
        pywhatkit.sendwhatmsg_instantly(
            phone_no=clean_phone,
            message=message,
            wait_time=18,
            tab_close=True,
            close_time=4
        )
        print(f"[WHATSAPP] pywhatkit triggered for {clean_phone}")
    except Exception as exc:
        print(f"[WHATSAPP] pywhatkit error: {exc}")


# ==================== 4. Email Notification ==================== #
def send_email(to_addr: str, subject: str, text_body: str, html_body: str, settings: dict):
    """Sends HTML email via SMTP."""
    from_addr = settings.get("email_from")
    password  = settings.get("email_password")
    server    = settings.get("smtp_server", "smtp.gmail.com")
    port      = int(settings.get("smtp_port", 587))

    if not from_addr or not password or not to_addr:
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = from_addr
        msg["To"]      = to_addr

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(server, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(from_addr, password)
            smtp.send_message(msg)
        print(f"[EMAIL] Sent successfully to {to_addr}")
    except Exception as exc:
        print(f"[EMAIL] Send error: {exc}")


# ==================== Main Runner ==================== #
def main():
    if len(sys.argv) < 3:
        print("Usage: notifier.py <events_json_path> <event_uuid>")
        sys.exit(1)

    events_file = sys.argv[1]
    event_uuid  = sys.argv[2]

    if not os.path.exists(events_file):
        print(f"[NOTIFIER] File not found: {events_file}")
        sys.exit(1)

    try:
        with open(events_file, "r", encoding="utf-8") as f:
            events = json.load(f)
    except Exception as exc:
        print(f"[NOTIFIER] Failed to read events: {exc}")
        sys.exit(1)

    event = next((e for e in events if e.get("uuid") == event_uuid), None)
    if not event:
        print(f"[NOTIFIER] Event UUID {event_uuid} not found (may have been deleted).")
        sys.exit(0)

    if event.get("done"):
        print(f"[NOTIFIER] Event '{event.get('name')}' is already marked as done.")
        sys.exit(0)

    # Extract event fields
    name          = event.get("name", "Upcoming Event")
    category      = event.get("category", "General")
    date_str      = event.get("date", "")
    time_str      = event.get("time", "")
    location      = event.get("location", "").strip()
    remind_before = event.get("remind_before", "At event time")
    phone         = event.get("phone", "").strip()
    email_addr    = event.get("email", "").strip()
    note          = event.get("note", "").strip()

    # Google Maps URL
    maps_url = ""
    if location:
        maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(location)}"

    # Check if this is an advance reminder or the final event time
    is_advance = remind_before != "At event time"
    timing_desc = f"in {remind_before.replace(' before', '')}" if is_advance else "NOW!"

    # Build plain message
    msg_lines = [
        f"🔔 Reminder: {name} is {timing_desc}",
        f"📂 Category: {category}",
        f"📅 Date & Time: {date_str} at {time_str}"
    ]
    if location:
        msg_lines.append(f"📍 Location: {location}")
    if is_advance:
        msg_lines.append(f"⏰ Notice: {remind_before}")
    if note:
        msg_lines.append(f"📝 Note: {note}")

    plain_text = "\n".join(msg_lines)

    # Build WhatsApp message
    wa_lines = [
        f"🔔 *Event Reminder: {name}*",
        f"⏰ *Happening {timing_desc}*",
        f"📂 Category: {category}",
        f"📅 Date & Time: {date_str} {time_str}",
    ]
    if location:
        wa_lines.append(f"📍 Location: {location}")
        wa_lines.append(f"🗺️ Maps: {maps_url}")
    if note:
        wa_lines.append(f"📝 Note: {note}")
    wa_lines.append("\n_Sent automatically by Event Reminder_")
    wa_message = "\n".join(wa_lines)

    # Build HTML Email body
    html_body = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px;">
      <div style="max-width: 540px; margin: auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #e2e8f0;">
        <div style="background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%); padding: 24px; color: white; text-align: center;">
          <h1 style="margin: 0; font-size: 24px; font-weight: bold;">🗓️ Event Reminder</h1>
          <p style="margin: 8px 0 0; opacity: 0.9; font-size: 14px;">Happening {timing_desc}</p>
        </div>
        <div style="padding: 24px;">
          <h2 style="color: #0f172a; margin-top: 0; font-size: 20px;">{name}</h2>
          <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 16px;">
            <tr><td style="padding: 8px 0; color: #64748b; width: 110px;"><b>Category:</b></td><td style="color: #1e293b;">{category}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;"><b>Date & Time:</b></td><td style="color: #1e293b;">{date_str} at {time_str}</td></tr>
            {"<tr><td style='padding: 8px 0; color: #64748b;'><b>Location:</b></td><td style='color: #1e293b;'>📍 " + location + "</td></tr>" if location else ""}
            {"<tr><td style='padding: 8px 0; color: #64748b;'><b>Note:</b></td><td style='color: #1e293b;'>" + note + "</td></tr>" if note else ""}
          </table>
          {f'<div style="margin-top: 24px; text-align: center;"><a href="{maps_url}" style="display: inline-block; background: #2563EB; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 14px;">📍 Open in Google Maps</a></div>' if maps_url else ''}
        </div>
        <div style="background: #f8fafc; padding: 14px; text-align: center; color: #94a3b8; font-size: 12px; border-top: 1px solid #e2e8f0;">
          Event Reminder App • Automated notification
        </div>
      </div>
    </body>
    </html>
    """

    settings = load_settings()

    print(f"[NOTIFIER] Triggered for '{name}' at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Spoken voice alert
    speak_alert(f"Reminder: {name} is {timing_desc}.")

    # 2. Windows Native Toast notification
    toast_title = f"🗓️ Reminder: {name}"
    toast_desc = f"{category} • {date_str} {time_str}\n" + (f"📍 {location}\n" if location else "") + f"Alert: {timing_desc}"
    show_windows_toast(toast_title, toast_desc, maps_url)

    # 3. WhatsApp notification
    if phone:
        send_whatsapp(phone, wa_message, settings)

    # 4. Email notification
    if email_addr:
        send_email(email_addr, f"🗓️ Reminder: {name} ({timing_desc})", plain_text, html_body, settings)

    print("[NOTIFIER] Finished successfully.")


if __name__ == "__main__":
    main()
