"""
scheduler_service.py
====================
Manages Windows Task Scheduler entries so reminders, Windows Toasts,
and WhatsApp/Email notifications trigger automatically even when the
Event Reminder software is completely closed/turned off.
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

REMIND_OFFSETS = {
    "At event time": 0,
    "5 minutes before": 5,
    "10 minutes before": 10,
    "15 minutes before": 15,
    "30 minutes before": 30,
    "1 hour before": 60,
    "2 hours before": 120,
    "3 hours before": 180,
    "6 hours before": 360,
    "12 hours before": 720,
    "1 day before": 1440,
    "2 days before": 2880,
    "1 week before": 10080,
}


def get_pythonw_path() -> str:
    """Find pythonw.exe to run background scripts without showing a cmd window."""
    candidate = sys.executable.replace("python.exe", "pythonw.exe")
    if os.path.exists(candidate):
        return candidate
    return sys.executable


def calculate_trigger_datetime(event: dict) -> datetime | None:
    """
    Computes the exact datetime when the notification should fire,
    taking into account the 'remind_before' offset.
    """
    date_str = event.get("date", "").strip()
    time_str = event.get("time", "").strip()
    if not date_str or not time_str:
        return None

    try:
        event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None

    offset_label = event.get("remind_before", "At event time")
    offset_mins = REMIND_OFFSETS.get(offset_label, 0)
    trigger_dt = event_dt - timedelta(minutes=offset_mins)

    now = datetime.now()
    # If the advance reminder time has passed, but the event itself is still in the future:
    # Fall back to event time so the user still gets a reminder!
    if trigger_dt <= now < event_dt:
        return event_dt

    return trigger_dt


def get_task_name(event_uuid: str) -> str:
    """Standardized task name in Windows Task Scheduler."""
    clean_id = event_uuid.replace("-", "")[:24]
    return f"EventReminder_{clean_id}"


def schedule_event_task(event: dict, events_file_path: str) -> bool:
    """
    Registers a scheduled task in Windows Task Scheduler for this event.
    Returns True if scheduled successfully.
    """
    event_uuid = event.get("uuid")
    if not event_uuid or event.get("done"):
        return False

    trigger_dt = calculate_trigger_datetime(event)
    if not trigger_dt or trigger_dt <= datetime.now():
        return False

    task_name = get_task_name(event_uuid)
    pythonw = get_pythonw_path()
    notifier_script = os.path.join(BASE_DIR, "notifier.py")

    # Command line: "pythonw.exe" "notifier.py" "events.json" "<uuid>"
    tr_command = f'\\"{pythonw}\\" \\"{notifier_script}\\" \\"{events_file_path}\\" {event_uuid}'

    st_time = trigger_dt.strftime("%H:%M")
    sd_date = trigger_dt.strftime("%m/%d/%Y")

    cmd = [
        "schtasks", "/Create",
        "/SC", "ONCE",
        "/TN", task_name,
        "/TR", tr_command,
        "/ST", st_time,
        "/SD", sd_date,
        "/F"
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if res.returncode == 0:
            print(f"[SCHEDULER] Successfully scheduled task '{task_name}' for {sd_date} {st_time}")
            return True
        else:
            print(f"[SCHEDULER] Error scheduling task '{task_name}': {res.stderr}")
            return False
    except Exception as exc:
        print(f"[SCHEDULER] Exception during task creation: {exc}")
        return False


def remove_event_task(event_uuid: str) -> bool:
    """
    Deletes the scheduled task from Windows Task Scheduler when an event
    is deleted or marked completed.
    """
    if not event_uuid:
        return False

    task_name = get_task_name(event_uuid)
    cmd = ["schtasks", "/Delete", "/TN", task_name, "/F"]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return res.returncode == 0
    except Exception:
        return False


def sync_all_tasks(events: list, events_file_path: str):
    """
    Synchronizes all events with Windows Task Scheduler:
    - Schedules tasks for upcoming events
    - Removes tasks for completed / old events
    """
    for event in events:
        event_uuid = event.get("uuid")
        if not event_uuid:
            continue

        if event.get("done"):
            remove_event_task(event_uuid)
        else:
            trigger_dt = calculate_trigger_datetime(event)
            if trigger_dt and trigger_dt > datetime.now():
                schedule_event_task(event, events_file_path)
            else:
                remove_event_task(event_uuid)


if __name__ == "__main__":
    print("Testing scheduler_service...")
    test_event = {
        "uuid": "test-sync-123",
        "name": "Baby Shower Celebration",
        "date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "time": "18:00",
        "remind_before": "1 hour before",
        "done": False
    }
    test_file = os.path.join(BASE_DIR, "events.json")
    success = schedule_event_task(test_event, test_file)
    print("Schedule success:", success)
    removed = remove_event_task(test_event["uuid"])
    print("Remove success:", removed)
