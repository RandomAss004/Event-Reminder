# 🗓️ Event Reminder App — Enhanced Edition (v2.5)

A full-featured personal & team Event Reminder application featuring **offline background alerts**, **advance reminder warnings**, **event categories**, **venue location with Google Maps**, **automatic WhatsApp & Email delivery**, and a modern CustomTkinter interface.

---

## 🌟 What's New & Fixed

### 1. 🛡️ Closed-App / Offline Reminders (Windows Task Scheduler)
- **Problem Solved:** Previously, when the software was closed, background threads died and no reminders or messages were sent.
- **Solution:** Every created/updated event is automatically registered into **Windows Task Scheduler** via `scheduler_service.py`.
- When the event or reminder time arrives, Windows natively triggers `notifier.py` using `pythonw.exe` completely silently in the background — **even when the Event Reminder app is completely closed or turned off**!

### 2. ⏰ Advance Reminders ("Remind Before")
- Choose when you want to receive alerts before an event begins:
  - `At event time`
  - `5 minutes before`, `10 minutes before`, `15 minutes before`, `30 minutes before`
  - `1 hour before` *(e.g. event is at 10 PM → alert sends at 9 PM)*
  - `2 hours before`, `3 hours before`, `1 day before`, `2 days before`
- The advance notice is clearly stated in the WhatsApp message, Windows Toast, voice announcement, and Email!

### 3. 👶 Event Categories & Visual Badges
- Choose from specialized event types with distinct color badges & icons:
  - 👶 **Baby Shower**
  - 🎂 **Birthday**
  - 💍 **Wedding / Engagement**
  - 💼 **Meeting / Work**
  - 🏥 **Doctor / Health**
  - 🎉 **Party / Celebration**
  - 🎓 **Exam / Study**
  - ✈️ **Travel / Trip**
  - 💳 **Bill / Payment**
  - 📌 **General**
- Instant filter dropdown to show events by category.

### 4. 📍 Event Location & Google Maps Integration
- Enter venue, clinic, office, or hall names (e.g. `"Grand Celebration Banquet, Mumbai"`).
- In the table: Click the **📍 View Map** button to open the location directly in **Google Maps**.
- Windows Toasts include an action button to navigate directly on Maps.
- WhatsApp messages include a direct Google Maps link.

### 5. 📱 Background WhatsApp & ✉️ Email (via Settings)
- **Twilio Cloud WhatsApp API**: Configured directly in the app's `⚙️ Settings` modal. Sends WhatsApp messages completely silently via cloud HTTP requests without needing a browser window open.
- **pywhatkit Fallback**: Automatically used if Twilio is not configured.
- **SMTP Email Alerts**: Supports Gmail (App Passwords), Outlook, or custom SMTP servers.
- **🚀 Test Alert Button**: Click the rocket icon on any event to immediately test your WhatsApp, Toast, and Voice alert without waiting!

---

## 🚀 Getting Started

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Run the Desktop App
```powershell
cd C:\Users\DELL\Desktop\python\Event_Reminder-main
python login.py
```

### 3. Login or Register
- Multi-language support: **English**, **Hindi**, **Marathi**
- Real-time password strength meter & secure SHA-256 storage
- Opens the main dashboard with your personalized user profile.

---

## 📁 Key Project Files

| File | Description |
|---|---|
| [`login.py`](file:///C:/Users/DELL/Desktop/python/Event_Reminder-main/login.py) | Modern login & registration screen with language switcher |
| [`reminder.py`](file:///C:/Users/DELL/Desktop/python/Event_Reminder-main/reminder.py) | Main dashboard: categories, advance timing, location, table, search & sort |
| [`scheduler_service.py`](file:///C:/Users/DELL/Desktop/python/Event_Reminder-main/scheduler_service.py) | Manages Windows Task Scheduler entries so alerts fire when app is closed |
| [`notifier.py`](file:///C:/Users/DELL/Desktop/python/Event_Reminder-main/notifier.py) | Standalone background executor: sends Toasts, WhatsApp, Email, & Voice |
| [`settings.json`](file:///C:/Users/DELL/Desktop/python/Event_Reminder-main/settings.json) | Local configuration for Twilio WhatsApp & SMTP Email |
| [`requirements.txt`](file:///C:/Users/DELL/Desktop/python/Event_Reminder-main/requirements.txt) | Python dependencies |

---

## 👥 Authors & Team
- **Team Lead:** Om A. Singh
- **Team Members:** Aryan Gharat, Rohan Sarkate, Umar Patel, Shriven Muley, Atul Bawaskar
