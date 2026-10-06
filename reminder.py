import customtkinter as ctk
import json
import os
import sys
import threading
import time
import csv
import uuid
import webbrowser
import urllib.parse
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkcalendar import DateEntry
from CTkMessagebox import CTkMessagebox

# Local services
import scheduler_service

# Optional pywhatkit
try:
    import pywhatkit as _pywhatkit
    _WHATSAPP_AVAILABLE = True
except Exception as _pwk_err:
    _pywhatkit = None
    _WHATSAPP_AVAILABLE = False
    print(f"[WARN] pywhatkit unavailable at startup: {_pwk_err}")

# Optional winotify
try:
    import winotify
    _WINOTIFY_AVAILABLE = True
except Exception:
    _WINOTIFY_AVAILABLE = False


# -------------------- Paths & Config -------------------- #
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_username = sys.argv[1] if len(sys.argv) > 1 else "default"
FILE = os.path.join(_BASE_DIR, f"events_{_username}.json") if _username != "default" \
       else os.path.join(_BASE_DIR, "events.json")
SETTINGS_FILE = os.path.join(_BASE_DIR, "settings.json")

editing_uuid = None
search_query = ""
filter_category = "All"
filter_priority = "All"
sort_key = "date"
_save_lock = threading.Lock()
_tts_lock  = threading.Lock()

CATEGORIES = [
    "👶 Baby Shower",
    "🎂 Birthday",
    "💍 Wedding",
    "💼 Meeting / Work",
    "🏥 Doctor / Health",
    "🎉 Party / Celebration",
    "🎓 Exam / Study",
    "✈️ Travel / Trip",
    "💳 Bill / Payment",
    "📌 General"
]

CATEGORY_COLORS = {
    "👶 Baby Shower": ("#FCE7F3", "#831843"),
    "🎂 Birthday":    ("#FEF3C7", "#92400E"),
    "💍 Wedding":     ("#F3E8FF", "#6B21A8"),
    "💼 Meeting / Work": ("#E0E7FF", "#3730A3"),
    "🏥 Doctor / Health": ("#FEE2E2", "#991B1B"),
    "🎉 Party / Celebration": ("#FFEDD5", "#9A3412"),
    "🎓 Exam / Study": ("#E0F2FE", "#075985"),
    "✈️ Travel / Trip": ("#CCFBF1", "#115E59"),
    "💳 Bill / Payment": ("#FEF9C3", "#854D0E"),
    "📌 General":     ("#F1F5F9", "#334155"),
}

REMIND_OPTIONS = [
    "At event time",
    "5 minutes before",
    "10 minutes before",
    "15 minutes before",
    "30 minutes before",
    "1 hour before",
    "2 hours before",
    "3 hours before",
    "1 day before",
    "2 days before"
]

PRIORITY_ORDER  = {"High": 0, "Medium": 1, "Low": 2}
PRIORITY_COLORS = {"High": "#EF4444", "Medium": "#F59E0B", "Low": "#10B981"}


# -------------------- Settings Handling -------------------- #
def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as exc:
        print(f"[SETTINGS] Save failed: {exc}")


# -------------------- Data Handling & Migration -------------------- #
def load_data():
    migrated = False
    data = []
    if os.path.exists(FILE):
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            data = []

    # Ensure every event has all new fields & unique UUID
    for e in data:
        if "uuid" not in e:
            e["uuid"] = uuid.uuid4().hex[:12]
            migrated = True
        if "category" not in e:
            # Detect baby shower, birthday, doctor from name if possible
            name_lower = e.get("name", "").lower()
            if "baby" in name_lower or "shower" in name_lower:
                e["category"] = "👶 Baby Shower"
            elif "birth" in name_lower or "bday" in name_lower:
                e["category"] = "🎂 Birthday"
            elif "doctor" in name_lower or "appoint" in name_lower or "hospital" in name_lower:
                e["category"] = "🏥 Doctor / Health"
            elif "meet" in name_lower:
                e["category"] = "💼 Meeting / Work"
            else:
                e["category"] = "📌 General"
            migrated = True

        if "location" not in e:
            e["location"] = ""
            migrated = True
        if "remind_before" not in e:
            e["remind_before"] = "At event time"
            migrated = True
        if "email" not in e:
            e["email"] = ""
            migrated = True
        if "note" not in e:
            e["note"] = e.get("description", "")
            migrated = True
        e.setdefault("phone", "")
        e.setdefault("time", "")
        e.setdefault("priority", "Medium")
        e.setdefault("done", False)
        e.setdefault("notified", False)

    if migrated:
        try:
            with open(FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as exc:
            print(f"[MIGRATION] Save failed: {exc}")

    return data


def save_data():
    try:
        with _save_lock:
            with open(FILE, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=4)
    except Exception as exc:
        print(f"[SAVE] Error saving events: {exc}")


# -------------------- Text-To-Speech -------------------- #
def speak(text):
    def _run():
        with _tts_lock:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", 165)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as exc:
                print(f"[TTS] {exc}")
    threading.Thread(target=_run, daemon=True).start()


# -------------------- Notifications & Messaging -------------------- #
def show_toast(title: str, message: str, maps_url: str = ""):
    """Shows native Windows toast with sound and Maps link."""
    if _WINOTIFY_AVAILABLE:
        try:
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
            return
        except Exception:
            pass

    # Fallback to in-app dialog
    root.after(0, lambda: show_notification(message, title=title))


def send_whatsapp_message(phone: str, message: str):
    """
    Sends WhatsApp message:
    1. Twilio API if credentials are configured in Settings (100% background silent)
    2. pywhatkit fallback if available
    """
    def _send():
        settings = load_settings()
        sid = settings.get("twilio_account_sid")
        token = settings.get("twilio_auth_token")
        from_num = settings.get("twilio_whatsapp_from", "whatsapp:+14155238886")

        clean_phone = phone.strip()
        if not clean_phone.startswith("+"):
            clean_phone = "+" + clean_phone

        # Method 1: Twilio REST API
        if sid and token:
            try:
                from twilio.rest import Client
                client = Client(sid, token)
                dest = f"whatsapp:{clean_phone}" if not clean_phone.startswith("whatsapp:") else clean_phone
                sender = from_num if from_num.startswith("whatsapp:") else f"whatsapp:{from_num}"
                client.messages.create(body=message, from_=sender, to=dest)
                print(f"[WHATSAPP] Sent via Twilio to {clean_phone}")
                return
            except Exception as exc:
                print(f"[WHATSAPP] Twilio error: {exc}. Trying fallback...")

        # Method 2: pywhatkit
        if _WHATSAPP_AVAILABLE and _pywhatkit is not None:
            try:
                _pywhatkit.sendwhatmsg_instantly(
                    phone_no=clean_phone,
                    message=message,
                    wait_time=18,
                    tab_close=True,
                    close_time=4
                )
                return
            except Exception as exc:
                print(f"[WHATSAPP] pywhatkit error: {exc}")

        # If both fail:
        root.after(0, lambda: show_notification(
            f"Could not automatically send WhatsApp to {phone}.\n\nMessage:\n{message}",
            title="⚠️ WhatsApp Send Notice"
        ))

    threading.Thread(target=_send, daemon=True).start()


def trigger_event_reminder(e: dict):
    """Fires all notifications (voice, toast, WhatsApp, in-app modal) for an event."""
    name     = e.get("name", "Event")
    cat      = e.get("category", "General")
    loc      = e.get("location", "").strip()
    remind_b = e.get("remind_before", "At event time")
    phone    = e.get("phone", "").strip()
    note     = e.get("note", "").strip()

    is_advance = remind_b != "At event time"
    timing_desc = f"in {remind_b.replace(' before', '')}" if is_advance else "NOW!"

    maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(loc)}" if loc else ""

    # 1. Voice
    speak(f"Reminder: {name} is {timing_desc}!")

    # 2. Windows Toast
    toast_body = f"{cat}\nDate: {e['date']} at {e['time']}\n"
    if loc:
        toast_body += f"📍 {loc}\n"
    toast_body += f"Alert: {timing_desc}"
    show_toast(f"🗓️ Reminder: {name}", toast_body, maps_url)

    # 3. WhatsApp
    if phone:
        wa_text = f"🔔 *Event Reminder: {name}*\n"
        wa_text += f"⏰ *Happening {timing_desc}*\n"
        wa_text += f"📂 Category: {cat}\n"
        wa_text += f"📅 Date & Time: {e['date']} {e['time']}\n"
        if loc:
            wa_text += f"📍 Location: {loc}\n"
            wa_text += f"🗺️ Maps: {maps_url}\n"
        if note:
            wa_text += f"📝 Note: {note}\n"
        wa_text += "\n_Sent automatically by Event Reminder_"
        send_whatsapp_message(phone, wa_text)

    # 4. In-App Notification Modal
    root.after(0, lambda: show_notification(
        f"Event: {name}\n"
        f"Category: {cat}\n"
        f"Scheduled: {e['date']} {e['time']}\n"
        + (f"Location: 📍 {loc}\n" if loc else "")
        + f"Timing: {timing_desc}\n"
        + (f"Note: {note}" if note else ""),
        title=f"🔔 Event Alert: {name}"
    ))


# -------------------- Background Sync & Checker -------------------- #
def sync_background_scheduler():
    """Syncs all upcoming events to Windows Task Scheduler so they fire even when app is closed."""
    def _run():
        scheduler_service.sync_all_tasks(events, FILE)
    threading.Thread(target=_run, daemon=True).start()


def live_reminder_checker():
    """Live in-app reminder loop running every 20 seconds while app is open."""
    while True:
        now = datetime.now()
        for e in list(events):
            if not e.get("done") and not e.get("notified"):
                try:
                    trigger_dt = scheduler_service.calculate_trigger_datetime(e)
                    if trigger_dt and now >= trigger_dt >= (now - timedelta(minutes=2)):
                        e["notified"] = True
                        save_data()
                        trigger_event_reminder(e)
                        root.after(0, refresh_event_table)
                except Exception as exc:
                    print(f"[CHECKER] Error checking event: {exc}")
        time.sleep(20)


# -------------------- Event CRUD -------------------- #
def add_or_update_event():
    global editing_uuid
    name     = name_var.get().strip()
    category = category_var.get().strip()
    date_str = date_entry.get().strip()
    time_str = time_var.get().strip()
    location = location_var.get().strip()
    remind_b = remind_before_var.get().strip()
    phone    = phone_var.get().strip()
    email_addr = email_var.get().strip()
    note     = note_var.get().strip()
    priority = priority_var.get().strip()

    if not name or not date_str or not time_str:
        popup_message("Please enter Event Name, Date, and Time.")
        return

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        popup_message("Date must be YYYY-MM-DD and Time must be HH:MM (24-hour format).")
        return

    target_uuid = editing_uuid or uuid.uuid4().hex[:12]

    event_data = {
        "uuid": target_uuid,
        "name": name,
        "category": category,
        "date": date_str,
        "time": time_str,
        "location": location,
        "remind_before": remind_b,
        "phone": phone,
        "email": email_addr,
        "note": note,
        "priority": priority,
        "done": False,
        "notified": False
    }

    if editing_uuid:
        for idx, ev in enumerate(events):
            if ev.get("uuid") == editing_uuid:
                events[idx].update(event_data)
                break
        editing_uuid = None
        add_update_btn.configure(text="Add Event ➕", fg_color="#2563EB")
    else:
        events.append(event_data)

    save_data()

    # Register in Windows Task Scheduler for offline background firing!
    scheduler_service.schedule_event_task(event_data, FILE)

    clear_inputs()
    refresh_event_table()
    show_toast("Event Saved & Scheduled 🗓️", f"'{name}' scheduled with Windows Background Alert ({remind_b})")


def delete_event(ev_uuid: str):
    ev = next((e for e in events if e.get("uuid") == ev_uuid), None)
    if not ev:
        return
    msg = CTkMessagebox(
        title="Delete Event",
        message=f"Are you sure you want to delete '{ev['name']}'?",
        icon="warning", option_1="Yes", option_2="No"
    )
    if msg.get() == "Yes":
        events[:] = [e for e in events if e.get("uuid") != ev_uuid]
        save_data()
        scheduler_service.remove_event_task(ev_uuid)
        refresh_event_table()


def mark_done(ev_uuid: str):
    for ev in events:
        if ev.get("uuid") == ev_uuid:
            ev["done"] = True
            ev["notified"] = True
            break
    save_data()
    scheduler_service.remove_event_task(ev_uuid)
    refresh_event_table()


def edit_event(ev_uuid: str):
    global editing_uuid
    ev = next((e for e in events if e.get("uuid") == ev_uuid), None)
    if not ev:
        return

    editing_uuid = ev_uuid
    name_var.set(ev["name"])
    category_var.set(ev.get("category", "📌 General"))
    try:
        date_entry.set_date(datetime.strptime(ev["date"], "%Y-%m-%d"))
    except Exception:
        pass
    time_var.set(ev["time"])
    location_var.set(ev.get("location", ""))
    remind_before_var.set(ev.get("remind_before", "At event time"))
    phone_var.set(ev.get("phone", ""))
    email_var.set(ev.get("email", ""))
    note_var.set(ev.get("note", ""))
    priority_var.set(ev.get("priority", "Medium"))

    add_update_btn.configure(text="Save Changes ✏️", fg_color="#D97706")


def test_event_now(ev_uuid: str):
    """Allows user to immediately trigger an alert test for an event."""
    ev = next((e for e in events if e.get("uuid") == ev_uuid), None)
    if ev:
        trigger_event_reminder(ev)


def open_location_map(location: str):
    if location:
        url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(location)}"
        webbrowser.open(url)


def clear_inputs():
    global editing_uuid
    name_var.set("")
    category_var.set(CATEGORIES[0])
    date_entry.set_date(datetime.now().date())
    time_var.set("")
    location_var.set("")
    remind_before_var.set("At event time")
    phone_var.set("")
    email_var.set("")
    note_var.set("")
    priority_var.set("Medium")
    editing_uuid = None
    add_update_btn.configure(text="Add Event ➕", fg_color="#2563EB")


# -------------------- Filter & Sort -------------------- #
def get_sorted_filtered():
    filtered = []
    q = search_query.lower()
    for e in events:
        # Search match across name, location, date, note
        matches_search = (
            q in e.get("name", "").lower()
            or q in e.get("location", "").lower()
            or q in e.get("note", "").lower()
            or q in e.get("date", "")
        )
        if not matches_search:
            continue

        # Category filter
        if filter_category != "All" and e.get("category") != filter_category:
            continue

        # Priority filter
        if filter_priority != "All" and e.get("priority") != filter_priority:
            continue

        filtered.append(e)

    # Sort
    if sort_key == "date":
        filtered.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
    elif sort_key == "name":
        filtered.sort(key=lambda x: x.get("name", "").lower())
    elif sort_key == "category":
        filtered.sort(key=lambda x: x.get("category", ""))
    elif sort_key == "priority":
        filtered.sort(key=lambda x: PRIORITY_ORDER.get(x.get("priority", "Medium"), 1))
    elif sort_key == "status":
        filtered.sort(key=lambda x: int(x.get("done", False)))

    return filtered


def refresh_event_table():
    for w in table_frame.winfo_children():
        w.destroy()

    COL_W = [30, 140, 140, 85, 55, 110, 120, 105, 75, 75, 175]
    HEADS = [
        "#", "Category", "Event Name", "Date", "Time",
        "Alert Timing", "Location", "Phone", "Priority", "Status", "Actions"
    ]

    for col, (h, w) in enumerate(zip(HEADS, COL_W)):
        ctk.CTkLabel(
            table_frame, text=h, font=("Helvetica", 11, "bold"),
            width=w, height=32, corner_radius=6,
            fg_color=("#1E3A8A", "#0F172A"), text_color="white"
        ).grid(row=0, column=col, padx=1, pady=2, sticky="nsew")

    filtered = get_sorted_filtered()

    if not filtered:
        empty_frame = ctk.CTkFrame(table_frame, fg_color="transparent")
        empty_frame.grid(row=1, column=0, columnspan=11, pady=50)
        ctk.CTkLabel(
            empty_frame, text="✨ No events match the current filter.",
            font=("Helvetica", 15, "bold"), text_color="gray"
        ).pack()
        ctk.CTkLabel(
            empty_frame, text="Add a new event with the form above, or clear your filters.",
            font=("Helvetica", 12), text_color="gray"
        ).pack(pady=4)
        return

    for row_pos, e in enumerate(filtered):
        is_even = row_pos % 2 == 0
        row_bg  = ("#F8FAFC", "#1E293B") if is_even else ("#FFFFFF", "#0F172A")
        done    = e.get("done", False)
        priority = e.get("priority", "Medium")
        p_color  = PRIORITY_COLORS.get(priority, "#F59E0B")
        txt_clr  = "gray" if done else ("black", "white")

        ev_uuid  = e.get("uuid")
        cat      = e.get("category", "📌 General")
        loc      = e.get("location", "").strip()

        # Row index
        ctk.CTkLabel(table_frame, text=str(row_pos + 1), width=COL_W[0], fg_color=row_bg, font=("Helvetica", 10), text_color="gray").grid(row=row_pos+1, column=0, padx=1, pady=1, sticky="nsew")

        # Category Badge
        cat_frame = ctk.CTkFrame(table_frame, fg_color=row_bg, width=COL_W[1])
        cat_badge_bg, cat_badge_fg = CATEGORY_COLORS.get(cat, ("#F1F5F9", "#334155"))
        ctk.CTkLabel(
            cat_frame, text=cat, font=("Helvetica", 10, "bold"),
            fg_color=cat_badge_bg, text_color=cat_badge_fg,
            corner_radius=6, height=22, padx=6
        ).pack(pady=4)
        cat_frame.grid(row=row_pos+1, column=1, padx=1, pady=1, sticky="nsew")

        # Event Name
        ctk.CTkLabel(table_frame, text=e["name"], width=COL_W[2], wraplength=COL_W[2]-8, fg_color=row_bg, font=("Helvetica", 11, "bold" if not done else "normal"), text_color=txt_clr).grid(row=row_pos+1, column=2, padx=1, pady=1, sticky="nsew")

        # Date & Time
        ctk.CTkLabel(table_frame, text=e["date"], width=COL_W[3], fg_color=row_bg, font=("Helvetica", 11), text_color=txt_clr).grid(row=row_pos+1, column=3, padx=1, pady=1, sticky="nsew")
        ctk.CTkLabel(table_frame, text=e["time"], width=COL_W[4], fg_color=row_bg, font=("Helvetica", 11), text_color=txt_clr).grid(row=row_pos+1, column=4, padx=1, pady=1, sticky="nsew")

        # Remind Before offset
        remind_txt = e.get("remind_before", "At time")
        ctk.CTkLabel(table_frame, text=f"⏰ {remind_txt}", width=COL_W[5], wraplength=COL_W[5]-6, fg_color=row_bg, font=("Helvetica", 10), text_color=("#1D4ED8", "#93C5FD")).grid(row=row_pos+1, column=5, padx=1, pady=1, sticky="nsew")

        # Location with Google Maps button
        loc_frame = ctk.CTkFrame(table_frame, fg_color=row_bg, width=COL_W[6])
        if loc:
            loc_btn = ctk.CTkButton(
                loc_frame, text=f"📍 {loc[:12]}…", width=COL_W[6]-10, height=24,
                font=("Helvetica", 10), fg_color="transparent", border_width=1,
                border_color="#94A3B8", text_color=("#0284C7", "#38BDF8"),
                command=lambda l=loc: open_location_map(l)
            )
            loc_btn.pack(pady=4)
        else:
            ctk.CTkLabel(loc_frame, text="—", font=("Helvetica", 10), text_color="gray").pack(pady=4)
        loc_frame.grid(row=row_pos+1, column=6, padx=1, pady=1, sticky="nsew")

        # Phone
        ctk.CTkLabel(table_frame, text=e.get("phone", "—") or "—", width=COL_W[7], fg_color=row_bg, font=("Helvetica", 10), text_color=txt_clr).grid(row=row_pos+1, column=7, padx=1, pady=1, sticky="nsew")

        # Priority
        ctk.CTkLabel(table_frame, text=priority, width=COL_W[8], fg_color=row_bg, font=("Helvetica", 10, "bold"), text_color=p_color).grid(row=row_pos+1, column=8, padx=1, pady=1, sticky="nsew")

        # Status
        status_txt = "✔ Done" if done else "⏳ Pending"
        status_clr = "#10B981" if done else "#F59E0B"
        ctk.CTkLabel(table_frame, text=status_txt, width=COL_W[9], fg_color=row_bg, font=("Helvetica", 10, "bold"), text_color=status_clr).grid(row=row_pos+1, column=9, padx=1, pady=1, sticky="nsew")

        # Actions
        af = ctk.CTkFrame(table_frame, fg_color=row_bg, width=COL_W[10])
        if not done:
            ctk.CTkButton(
                af, text="✔", width=32, height=24, corner_radius=6,
                fg_color="#10B981", hover_color="#059669",
                command=lambda u=ev_uuid: mark_done(u)
            ).pack(side="left", padx=1)
        ctk.CTkButton(
            af, text="✏", width=32, height=24, corner_radius=6,
            fg_color="#3B82F6", hover_color="#1D4ED8",
            command=lambda u=ev_uuid: edit_event(u)
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            af, text="🚀", width=32, height=24, corner_radius=6,
            fg_color="#8B5CF6", hover_color="#6D28D9",
            command=lambda u=ev_uuid: test_event_now(u)
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            af, text="🗑", width=32, height=24, corner_radius=6,
            fg_color="#EF4444", hover_color="#B91C1C",
            command=lambda u=ev_uuid: delete_event(u)
        ).pack(side="left", padx=1)
        af.grid(row=row_pos+1, column=10, padx=1, pady=1, sticky="nsew")


def search_events(*_):
    global search_query
    search_query = search_var.get().strip()
    refresh_event_table()


def on_category_filter_change(choice):
    global filter_category
    filter_category = "All" if choice == "All Categories" else choice
    refresh_event_table()


def on_priority_filter_change(choice):
    global filter_priority
    filter_priority = "All" if choice == "All Priorities" else choice
    refresh_event_table()


def sort_events(key):
    global sort_key
    sort_key = key
    refresh_event_table()


def popup_message(msg):
    CTkMessagebox(title="Event Reminder", message=msg).get()


def show_notification(msg, title="🔔 Event Reminder"):
    notif = ctk.CTkToplevel(root)
    notif.title(title)
    notif.geometry("440x260")
    notif.attributes("-topmost", True)
    ctk.CTkLabel(notif, text=title, font=("Helvetica", 15, "bold")).pack(pady=(16, 4))
    ctk.CTkLabel(notif, text=msg, font=("Helvetica", 12), wraplength=400, justify="left").pack(pady=10, padx=16)
    ctk.CTkButton(notif, text="Got It", width=120, height=34, command=notif.destroy).pack(pady=8)


# -------------------- Modals (Settings, Overview, Graph) -------------------- #
def show_settings_modal():
    settings = load_settings()
    modal = ctk.CTkToplevel(root)
    modal.title("⚙️ Notification Settings")
    modal.geometry("520x540")
    modal.attributes("-topmost", True)

    ctk.CTkLabel(modal, text="⚙️ Notification & Messaging Settings", font=("Helvetica", 16, "bold")).pack(pady=(16, 8))

    sf = ctk.CTkScrollableFrame(modal, width=480, height=400)
    sf.pack(padx=16, pady=8, fill="both", expand=True)

    # Twilio Section
    ctk.CTkLabel(sf, text="📱 WhatsApp via Twilio API (Runs 100% in Background)", font=("Helvetica", 13, "bold"), text_color="#2563EB").pack(anchor="w", pady=(8, 4))
    ctk.CTkLabel(sf, text="Allows silent background sending without needing WhatsApp Web open.", font=("Helvetica", 11), text_color="gray").pack(anchor="w", pady=(0, 6))

    sid_var = ctk.StringVar(value=settings.get("twilio_account_sid", ""))
    token_var = ctk.StringVar(value=settings.get("twilio_auth_token", ""))
    from_var = ctk.StringVar(value=settings.get("twilio_whatsapp_from", "whatsapp:+14155238886"))

    ctk.CTkLabel(sf, text="Account SID:").pack(anchor="w")
    ctk.CTkEntry(sf, textvariable=sid_var, placeholder_text="ACxxxxxxxxxxxxxxxxxxxxxxx").pack(fill="x", pady=2)

    ctk.CTkLabel(sf, text="Auth Token:").pack(anchor="w")
    ctk.CTkEntry(sf, textvariable=token_var, show="*", placeholder_text="Twilio Auth Token").pack(fill="x", pady=2)

    ctk.CTkLabel(sf, text="Twilio WhatsApp Sender:").pack(anchor="w")
    ctk.CTkEntry(sf, textvariable=from_var, placeholder_text="whatsapp:+14155238886").pack(fill="x", pady=2)

    # Email Section
    ctk.CTkLabel(sf, text="✉️ Email Alerts (SMTP)", font=("Helvetica", 13, "bold"), text_color="#0D9488").pack(anchor="w", pady=(16, 4))

    email_from_var = ctk.StringVar(value=settings.get("email_from", ""))
    email_pw_var   = ctk.StringVar(value=settings.get("email_password", ""))
    smtp_srv_var   = ctk.StringVar(value=settings.get("smtp_server", "smtp.gmail.com"))
    smtp_prt_var   = ctk.StringVar(value=str(settings.get("smtp_port", 587)))

    ctk.CTkLabel(sf, text="Sender Email:").pack(anchor="w")
    ctk.CTkEntry(sf, textvariable=email_from_var, placeholder_text="your_email@gmail.com").pack(fill="x", pady=2)

    ctk.CTkLabel(sf, text="App Password:").pack(anchor="w")
    ctk.CTkEntry(sf, textvariable=email_pw_var, show="*", placeholder_text="Google App Password").pack(fill="x", pady=2)

    ctk.CTkLabel(sf, text="SMTP Server & Port:").pack(anchor="w")
    row_smtp = ctk.CTkFrame(sf, fg_color="transparent")
    row_smtp.pack(fill="x", pady=2)
    ctk.CTkEntry(row_smtp, textvariable=smtp_srv_var, width=320).pack(side="left")
    ctk.CTkEntry(row_smtp, textvariable=smtp_prt_var, width=100).pack(side="right")

    def save_and_close():
        new_settings = {
            "twilio_account_sid": sid_var.get().strip(),
            "twilio_auth_token": token_var.get().strip(),
            "twilio_whatsapp_from": from_var.get().strip(),
            "email_from": email_from_var.get().strip(),
            "email_password": email_pw_var.get().strip(),
            "smtp_server": smtp_srv_var.get().strip(),
            "smtp_port": int(smtp_prt_var.get().strip() or "587"),
            "enable_voice": True,
            "enable_toasts": True
        }
        save_settings(new_settings)
        modal.destroy()
        popup_message("Settings saved successfully! ✅")

    ctk.CTkButton(modal, text="Save Settings 💾", fg_color="#2563EB", height=38, command=save_and_close).pack(pady=10)


def show_overview_page():
    win = ctk.CTkToplevel(root)
    win.title("📊 Event Overview & Analytics")
    win.geometry("480x520")
    win.attributes("-topmost", True)

    total     = len(events)
    completed = sum(1 for e in events if e.get("done"))
    pending   = total - completed

    ctk.CTkLabel(win, text="📊  Event Statistics & Analytics", font=("Helvetica", 17, "bold")).pack(pady=(16, 10))

    # Overall stats
    stats_frame = ctk.CTkFrame(win)
    stats_frame.pack(fill="x", padx=20, pady=6)
    for label, val, color in [
        ("Total Events", total, None),
        ("Completed Events", completed, "#10B981"),
        ("Pending Reminders", pending, "#F59E0B")
    ]:
        row = ctk.CTkFrame(stats_frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text=label, font=("Helvetica", 12)).pack(side="left")
        ctk.CTkLabel(row, text=str(val), font=("Helvetica", 13, "bold"), text_color=color).pack(side="right")

    # Progress bar
    if total > 0:
        pct = int((completed / total) * 100)
        ctk.CTkLabel(win, text=f"Overall Completion: {pct}%", font=("Helvetica", 11)).pack(pady=(10, 2))
        pb = ctk.CTkProgressBar(win, width=420, height=12)
        pb.pack(pady=(0, 10))
        pb.set(completed / total)

    # Category breakdown
    ctk.CTkLabel(win, text="Events by Category", font=("Helvetica", 13, "bold")).pack(anchor="w", padx=20, pady=(10, 4))
    cat_frame = ctk.CTkScrollableFrame(win, height=180)
    cat_frame.pack(fill="both", expand=True, padx=20, pady=4)

    counts_by_cat = {}
    for e in events:
        c = e.get("category", "📌 General")
        counts_by_cat[c] = counts_by_cat.get(c, 0) + 1

    for cat_name, cnt in sorted(counts_by_cat.items(), key=lambda x: -x[1]):
        r = ctk.CTkFrame(cat_frame)
        r.pack(fill="x", pady=2)
        ctk.CTkLabel(r, text=cat_name, font=("Helvetica", 11)).pack(side="left", padx=8, pady=4)
        ctk.CTkLabel(r, text=f"{cnt} event(s)", font=("Helvetica", 11, "bold")).pack(side="right", padx=8)


def show_weekly_graph():
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    stats = {d: 0 for d in days}
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())

    for e in events:
        try:
            ed = datetime.strptime(e["date"], "%Y-%m-%d").date()
            if e.get("done") and week_start <= ed < week_start + timedelta(days=7):
                day = ed.strftime("%a")
                if day in stats:
                    stats[day] += 1
        except Exception:
            continue

    win = ctk.CTkToplevel(root)
    win.title("📊 Weekly Event Activity")
    win.geometry("700x460")
    win.attributes("-topmost", True)

    counts = list(stats.values())
    fig, ax = plt.subplots(figsize=(6.8, 3.8), dpi=100)
    colors = ["#2563EB" if c > 0 else "#CBD5E1" for c in counts]
    bars = ax.bar(days, counts, color=colors, edgecolor="white", linewidth=1.2, width=0.55)
    ax.set_title("Events Completed This Week", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Day of Week")
    ax.set_ylabel("Completed Events")
    ax.set_ylim(0, max(counts, default=0) + 1.5)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    for bar, cnt in zip(bars, counts):
        if cnt > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                    str(cnt), ha="center", va="bottom", fontweight="bold")

    fig.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
    canvas.draw()


def show_about():
    info = (
        "🗓️  Event Reminder App — Enhanced Edition\n\n"
        "✨ Key Features:\n"
        "• Offline / Closed-App Alerts via Windows Task Scheduler\n"
        "• Advance Reminder Offset (e.g. 1 hour before, 30 min before)\n"
        "• Categories: Baby Shower, Birthday, Wedding, Medical & more\n"
        "• Location integration with instant Google Maps navigation\n"
        "• Silent background WhatsApp via Twilio + pywhatkit fallback\n"
        "• Native Windows 10/11 Toast notifications with sound\n\n"
        "Team Lead : Om A. Singh\n"
        "Version 2.5 • Full Offline Architecture"
    )
    win = ctk.CTkToplevel(root)
    win.title("About Event Reminder")
    win.geometry("430x380")
    win.attributes("-topmost", True)
    ctk.CTkLabel(win, text=info, justify="left", font=("Helvetica", 11)).pack(pady=20, padx=20)
    ctk.CTkButton(win, text="OK", command=win.destroy, width=120).pack(pady=8)


def export_to_csv():
    import tkinter.filedialog as fd
    path = fd.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile=f"events_{_username}.csv",
        title="Export Events to CSV"
    )
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            fields = ["uuid", "name", "category", "date", "time", "location", "remind_before", "phone", "email", "priority", "note", "done"]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for e in events:
                writer.writerow({k: e.get(k, "") for k in fields})
        popup_message(f"✅ Successfully exported {len(events)} events to:\n{path}")
    except Exception as exc:
        popup_message(f"Export failed:\n{exc}")


# -------------------- Status Bar -------------------- #
def update_status_bar():
    now = datetime.now()
    clock = now.strftime("%A, %d %b %Y | %H:%M:%S")

    upcoming = []
    for e in events:
        if not e.get("done"):
            try:
                dt = datetime.strptime(f"{e['date']} {e['time']}", "%Y-%m-%d %H:%M")
                if dt > now:
                    upcoming.append((dt, e["name"], e.get("remind_before", "At event time")))
            except Exception:
                pass
    upcoming.sort()

    if upcoming:
        ndt, nname, nremind = upcoming[0]
        diff = ndt - now
        h, rem = divmod(int(diff.total_seconds()), 3600)
        m = rem // 60
        countdown = f" | ⏰ Next: '{nname}' in {h}h {m}m" if h else f" | ⏰ Next: '{nname}' in {m}m"
    else:
        countdown = " | No upcoming events"

    bg_indicator = " | 🛡️ Windows Background Sync: Active"
    status_label.configure(text=f"👤 {_username.title()} | {clock}{countdown}{bg_indicator}")
    root.after(1000, update_status_bar)


# ==================== MAIN UI SETUP ==================== #
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title(f"🗓️ Event Reminder — {_username.title()} (Background Sync Active)")
root.geometry("1200x860")
root.minsize(1000, 700)

# Form Variables
name_var          = ctk.StringVar()
category_var      = ctk.StringVar(value=CATEGORIES[0])
time_var          = ctk.StringVar()
location_var      = ctk.StringVar()
remind_before_var = ctk.StringVar(value="1 hour before")
phone_var         = ctk.StringVar()
email_var         = ctk.StringVar()
note_var          = ctk.StringVar()
search_var        = ctk.StringVar()
priority_var      = ctk.StringVar(value="Medium")

events = load_data()


# ---------- Top Header Bar ----------
top_bar = ctk.CTkFrame(root, height=54, corner_radius=0, fg_color=("#1E3A8A", "#0B1329"))
top_bar.pack(fill="x")
top_bar.pack_propagate(False)

ctk.CTkLabel(top_bar, text="🗓️ EVENT REMINDER", font=("Helvetica", 20, "bold"), text_color="white").pack(side="left", padx=16, pady=10)
ctk.CTkLabel(top_bar, text=f"• User: {_username.title()}", font=("Helvetica", 12), text_color="#93C5FD").pack(side="left", padx=4)

# Top Right Controls
def toggle_theme():
    mode = ctk.get_appearance_mode()
    new = "light" if mode == "Dark" else "dark"
    ctk.set_appearance_mode(new)
    theme_btn.configure(text="☀️ Light" if new == "light" else "🌙 Dark")

theme_btn = ctk.CTkButton(
    top_bar, text="🌙 Dark", width=85, height=30, corner_radius=15,
    fg_color="transparent", border_width=1, border_color="#93C5FD",
    text_color="white", command=toggle_theme
)
theme_btn.pack(side="right", padx=12, pady=10)

ctk.CTkButton(
    top_bar, text="⚙️ Settings", width=95, height=30, corner_radius=15,
    fg_color="#2563EB", text_color="white", command=show_settings_modal
).pack(side="right", padx=4, pady=10)

ctk.CTkButton(
    top_bar, text="🔄 Sync Tasks", width=105, height=30, corner_radius=15,
    fg_color="transparent", border_width=1, border_color="#10B981",
    text_color="#10B981", command=lambda: (sync_background_scheduler(), popup_message("Windows Task Scheduler synchronized! ✅"))
).pack(side="right", padx=4, pady=10)


# ---------- Event Input Form ----------
form_card = ctk.CTkFrame(root, corner_radius=12)
form_card.pack(pady=8, padx=14, fill="x")

ctk.CTkLabel(form_card, text="➕ Add / Edit Event Details", font=("Helvetica", 14, "bold")).grid(
    row=0, column=0, columnspan=8, padx=14, pady=(10, 4), sticky="w")

# Row 1: Category, Event Name, Date, Time
ctk.CTkLabel(form_card, text="Category *:", font=("Helvetica", 11)).grid(row=1, column=0, padx=(12, 4), pady=4, sticky="w")
cat_menu = ctk.CTkOptionMenu(form_card, values=CATEGORIES, variable=category_var, width=170)
cat_menu.grid(row=1, column=1, padx=4, pady=4, sticky="ew")

ctk.CTkLabel(form_card, text="Event Name *:", font=("Helvetica", 11)).grid(row=1, column=2, padx=(12, 4), pady=4, sticky="w")
ctk.CTkEntry(form_card, textvariable=name_var, placeholder_text="e.g. Baby Shower, Rohan Birthday", width=220).grid(row=1, column=3, padx=4, pady=4, sticky="ew")

ctk.CTkLabel(form_card, text="Date *:", font=("Helvetica", 11)).grid(row=1, column=4, padx=(12, 4), pady=4, sticky="w")
date_entry = DateEntry(form_card, date_pattern="yyyy-mm-dd", width=12, background="darkblue", foreground="white", borderwidth=2)
date_entry.grid(row=1, column=5, padx=4, pady=4, sticky="ew")

ctk.CTkLabel(form_card, text="Time * (HH:MM):", font=("Helvetica", 11)).grid(row=1, column=6, padx=(12, 4), pady=4, sticky="w")
ctk.CTkEntry(form_card, textvariable=time_var, placeholder_text="19:30 (24h)", width=90).grid(row=1, column=7, padx=(4, 12), pady=4, sticky="ew")

# Row 2: Location, Remind Before, Phone, Priority
ctk.CTkLabel(form_card, text="📍 Location:", font=("Helvetica", 11)).grid(row=2, column=0, padx=(12, 4), pady=4, sticky="w")
ctk.CTkEntry(form_card, textvariable=location_var, placeholder_text="e.g. Royal Palace Hall, Mumbai", width=170).grid(row=2, column=1, padx=4, pady=4, sticky="ew")

ctk.CTkLabel(form_card, text="⏰ Remind Before:", font=("Helvetica", 11)).grid(row=2, column=2, padx=(12, 4), pady=4, sticky="w")
remind_menu = ctk.CTkOptionMenu(form_card, values=REMIND_OPTIONS, variable=remind_before_var, width=170)
remind_menu.grid(row=2, column=3, padx=4, pady=4, sticky="ew")

ctk.CTkLabel(form_card, text="📱 WhatsApp Phone:", font=("Helvetica", 11)).grid(row=2, column=4, padx=(12, 4), pady=4, sticky="w")
ctk.CTkEntry(form_card, textvariable=phone_var, placeholder_text="+919876543210", width=130).grid(row=2, column=5, padx=4, pady=4, sticky="ew")

ctk.CTkLabel(form_card, text="Priority:", font=("Helvetica", 11)).grid(row=2, column=6, padx=(12, 4), pady=4, sticky="w")
ctk.CTkOptionMenu(form_card, values=["High", "Medium", "Low"], variable=priority_var, width=90).grid(row=2, column=7, padx=(4, 12), pady=4, sticky="ew")

# Row 3: Note / Description & Buttons
ctk.CTkLabel(form_card, text="📝 Note / Info:", font=("Helvetica", 11)).grid(row=3, column=0, padx=(12, 4), pady=4, sticky="w")
ctk.CTkEntry(form_card, textvariable=note_var, placeholder_text="Special instructions, dress code, gift details...").grid(row=3, column=1, columnspan=3, padx=4, pady=4, sticky="ew")

# Form Buttons in row 3
action_subframe = ctk.CTkFrame(form_card, fg_color="transparent")
action_subframe.grid(row=3, column=4, columnspan=4, padx=(10, 12), pady=4, sticky="ew")

add_update_btn = ctk.CTkButton(
    action_subframe, text="Add Event ➕", command=add_or_update_event,
    width=140, height=34, font=("Helvetica", 12, "bold"),
    fg_color="#2563EB", hover_color="#1D4ED8", corner_radius=8
)
add_update_btn.pack(side="left", padx=4)

ctk.CTkButton(
    action_subframe, text="Clear 🔄", command=clear_inputs,
    width=80, height=34, corner_radius=8,
    fg_color="transparent", border_width=1
).pack(side="left", padx=4)

ctk.CTkButton(
    action_subframe, text="📤 Export CSV", command=export_to_csv,
    width=110, height=34, corner_radius=8,
    fg_color="#059669", hover_color="#047857"
).pack(side="right", padx=4)


# ---------- Search, Category Filter, and Sort Bar ----------
filter_bar = ctk.CTkFrame(root, corner_radius=10)
filter_bar.pack(pady=(0, 6), padx=14, fill="x")

# Search
ctk.CTkEntry(
    filter_bar, textvariable=search_var,
    placeholder_text="🔍 Search events by name, location, date, or note...", height=34
).pack(side="left", padx=8, pady=6, fill="x", expand=True)
search_var.trace_add("write", search_events)

# Category Filter Dropdown
cat_filter_values = ["All Categories"] + CATEGORIES
cat_filter_menu = ctk.CTkOptionMenu(
    filter_bar, values=cat_filter_values, width=160, height=34,
    command=on_category_filter_change
)
cat_filter_menu.pack(side="left", padx=4, pady=6)

# Priority Filter Dropdown
prio_filter_menu = ctk.CTkOptionMenu(
    filter_bar, values=["All Priorities", "High", "Medium", "Low"], width=130, height=34,
    command=on_priority_filter_change
)
prio_filter_menu.pack(side="left", padx=4, pady=6)

# Sort Buttons
ctk.CTkLabel(filter_bar, text="Sort:", font=("Helvetica", 11)).pack(side="left", padx=(10, 2))
for lbl, key in [("📅 Date", "date"), ("🔤 Name", "name"), ("🎯 Priority", "priority")]:
    ctk.CTkButton(
        filter_bar, text=lbl, width=80, height=34, corner_radius=8,
        fg_color="transparent", border_width=1, command=lambda k=key: sort_events(k)
    ).pack(side="left", padx=2, pady=6)


# ---------- Events Table Container ----------
table_frame = ctk.CTkScrollableFrame(root, corner_radius=10)
table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 6))


# ---------- Bottom Action Controls ----------
bottom_bar = ctk.CTkFrame(root, corner_radius=10)
bottom_bar.pack(pady=(0, 4), padx=14, fill="x")

for text, cmd, col in [
    ("📊 Weekly Activity", show_weekly_graph, "#7C3AED"),
    ("📋 Overview & Stats", show_overview_page, "#0284C7"),
    ("ℹ️ About App", show_about, "#475569"),
]:
    ctk.CTkButton(
        bottom_bar, text=text, command=cmd, height=32, corner_radius=8,
        fg_color=col, hover_color=col
    ).pack(side="left", padx=6, pady=5)

ctk.CTkLabel(
    bottom_bar, text="💡 Tip: Click 🚀 on any event to immediately test WhatsApp and Toast alert!",
    font=("Helvetica", 11), text_color="gray"
).pack(side="right", padx=12)


# ---------- Live Status Bar ----------
status_label = ctk.CTkLabel(
    root, text="Initialising background sync...", font=("Helvetica", 11),
    height=22, anchor="w", text_color="gray"
)
status_label.pack(fill="x", padx=16, pady=(0, 4))


# ---------- App Boot & Sync ----------
sync_background_scheduler()
threading.Thread(target=live_reminder_checker, daemon=True).start()
refresh_event_table()
update_status_bar()

root.mainloop()
