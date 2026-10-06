import json
import os
import sys
import hashlib
import re
import customtkinter as ctk
from tkinter import messagebox
import subprocess


# -------------------- Paths -------------------- #
# Always resolve relative to this file so it works from any working directory
_BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(_BASE_DIR, "users.json")


# -------------------- Password Utils -------------------- #
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def migrate_plaintext_passwords():
    """
    BUG FIX: Some entries in users.json were stored as plain-text.
    Anything that is NOT a 64-character hex SHA-256 digest gets re-hashed
    automatically on first launch.
    """
    users = load_users()
    changed = False
    sha256_re = re.compile(r'^[a-f0-9]{64}$')
    for user, stored in users.items():
        if not sha256_re.match(stored):          # plain-text detected
            users[user] = hash_password(stored)
            changed = True
    if changed:
        save_users(users)


# -------------------- Multilingual Strings -------------------- #
LANG = {
    "English": {
        "title":            "Event Reminder — Login",
        "subtitle":         "Your Personal Event Manager",
        "username":         "Username",
        "password":         "Password",
        "password_confirm": "Confirm Password",
        "login":            "Login",
        "register":         "Register",
        "login_success":    "Welcome back, {username}! 👋",
        "login_fail":       "Invalid username or password.",
        "login_warn":       "Please fill in all fields.",
        "register_success": "Account created! You can now log in.",
        "register_fail":    "Username already exists.",
        "password_mismatch":"Passwords do not match!",
        "pw_short":         "Password must be at least 4 characters.",
        "user_short":       "Username must be at least 3 characters.",
        "language":         "Language",
        "pw_strength":      ["", "Weak", "Fair", "Good", "Strong ✔"],
    },
    "Hindi": {
        "title":            "इवेंट रिमाइंडर — लॉगिन",
        "subtitle":         "आपका व्यक्तिगत इवेंट मैनेजर",
        "username":         "उपयोगकर्ता नाम",
        "password":         "पासवर्ड",
        "password_confirm": "पासवर्ड पुष्टि करें",
        "login":            "लॉगिन करें",
        "register":         "रजिस्टर करें",
        "login_success":    "स्वागत है, {username}! 👋",
        "login_fail":       "गलत उपयोगकर्ता नाम या पासवर्ड।",
        "login_warn":       "सभी फ़ील्ड भरें।",
        "register_success": "रजिस्ट्रेशन सफल!",
        "register_fail":    "यह नाम पहले से मौजूद है।",
        "password_mismatch":"पासवर्ड मेल नहीं खाते!",
        "pw_short":         "पासवर्ड कम से कम 4 अक्षर होना चाहिए।",
        "user_short":       "नाम कम से कम 3 अक्षर होना चाहिए।",
        "language":         "भाषा",
        "pw_strength":      ["", "कमज़ोर", "ठीक", "अच्छा", "मज़बूत ✔"],
    },
    "Marathi": {
        "title":            "इव्हेंट रिमाइंडर — लॉगिन",
        "subtitle":         "तुमचा वैयक्तिक इव्हेंट व्यवस्थापक",
        "username":         "वापरकर्ता नाव",
        "password":         "पासवर्ड",
        "password_confirm": "पासवर्ड पडताळा",
        "login":            "लॉगिन करा",
        "register":         "नोंदणी करा",
        "login_success":    "{username}, आपले स्वागत आहे! 👋",
        "login_fail":       "अवैध वापरकर्ता नाव किंवा पासवर्ड।",
        "login_warn":       "सर्व फील्ड भरा।",
        "register_success": "नोंदणी यशस्वी!",
        "register_fail":    "हे नाव आधीपासूनच अस्तित्वात आहे।",
        "password_mismatch":"पासवर्ड जुळत नाही!",
        "pw_short":         "पासवर्ड किमान 4 अक्षरे असणे आवश्यक आहे।",
        "user_short":       "नाव किमान 3 अक्षरे असणे आवश्यक आहे।",
        "language":         "भाषा",
        "pw_strength":      ["", "कमकुवत", "बरे", "चांगले", "मजबूत ✔"],
    },
}

PW_STRENGTH_COLORS = ["", "#FF5A5A", "#FFA500", "#2196F3", "#4CAF50"]


def t() -> dict:
    """Shorthand for current language dict."""
    return LANG[lang_var.get()]


# -------------------- UI Callbacks -------------------- #
def update_labels(*_):
    root.title(t()["title"])
    subtitle_label.configure(text=t()["subtitle"])
    username_label.configure(text=t()["username"])
    password_label.configure(text=t()["password"])
    confirm_label.configure(text=t()["password_confirm"])
    login_btn.configure(text=f"🔐  {t()['login']}")
    register_btn.configure(text=f"📝  {t()['register']}")
    lang_label.configure(text=t()["language"] + " :")


def toggle_password_visibility():
    show = password_entry.cget("show") == "*"
    password_entry.configure(show="" if show else "*")
    confirm_entry.configure(show="" if show else "*")
    eye_btn.configure(text="🙈" if show else "👁")


def check_strength(event=None):
    pw = password_var.get()
    n  = len(pw)
    if n == 0:
        level = 0
    elif n < 4:
        level = 1
    elif n < 7:
        level = 2
    elif n < 10 or not re.search(r'[A-Z]', pw) or not re.search(r'\d', pw):
        level = 3
    else:
        level = 4
    strength_bar.set(level / 4)
    labels = t()["pw_strength"]
    strength_lbl.configure(
        text=labels[level],
        text_color=PW_STRENGTH_COLORS[level] if level else "gray"
    )


# -------------------- Login / Register -------------------- #
def login():
    username = username_var.get().strip()
    password = password_var.get().strip()
    if not username or not password:
        messagebox.showwarning(t()["title"], t()["login_warn"])
        return
    users = load_users()
    if username in users and users[username] == hash_password(password):
        messagebox.showinfo(t()["title"], t()["login_success"].format(username=username))
        root.destroy()
        subprocess.Popen([sys.executable,
                          os.path.join(_BASE_DIR, "reminder.py"),
                          username])
    else:
        messagebox.showerror(t()["title"], t()["login_fail"])


def register():
    username = username_var.get().strip()
    password = password_var.get().strip()
    confirm  = confirm_var.get().strip()

    if not username or not password or not confirm:
        messagebox.showwarning(t()["title"], t()["login_warn"])
        return
    if len(username) < 3:
        messagebox.showwarning(t()["title"], t()["user_short"])
        return
    if password != confirm:
        messagebox.showerror(t()["title"], t()["password_mismatch"])
        return
    if len(password) < 4:
        messagebox.showwarning(t()["title"], t()["pw_short"])
        return

    users = load_users()
    if username in users:
        messagebox.showerror(t()["title"], t()["register_fail"])
        return

    users[username] = hash_password(password)   # always hash before saving
    save_users(users)
    messagebox.showinfo(t()["title"], t()["register_success"])
    username_var.set("")
    password_var.set("")
    confirm_var.set("")
    strength_bar.set(0)
    strength_lbl.configure(text="")


# -------------------- Fix data before UI launches -------------------- #
migrate_plaintext_passwords()


# ==================== UI ==================== #
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.geometry("430x620")
root.resizable(False, False)
root.title("Event Reminder — Login")

lang_var     = ctk.StringVar(value="English")
username_var = ctk.StringVar()
password_var = ctk.StringVar()
confirm_var  = ctk.StringVar()


# ---------- Header ----------
header = ctk.CTkFrame(root, height=128, corner_radius=0,
                       fg_color=("#1E3A8A", "#0d1f4a"))
header.pack(fill="x")
header.pack_propagate(False)

ctk.CTkLabel(header, text="🗓️", font=("Helvetica", 42)).pack(pady=(10, 0))
ctk.CTkLabel(header, text="Event Reminder",
              font=("Helvetica", 22, "bold"), text_color="white").pack()
subtitle_label = ctk.CTkLabel(header, text=LANG["English"]["subtitle"],
                               font=("Helvetica", 12), text_color="#90b8ff")
subtitle_label.pack()


# ---------- Card ----------
card = ctk.CTkFrame(root, corner_radius=18)
card.pack(pady=14, padx=22, fill="both", expand=True)


# Language row
lang_row = ctk.CTkFrame(card, fg_color="transparent")
lang_row.pack(fill="x", padx=20, pady=(14, 4))
lang_label = ctk.CTkLabel(lang_row, text="Language :", font=("Helvetica", 12))
lang_label.pack(side="left")
ctk.CTkOptionMenu(lang_row, values=list(LANG.keys()),
                   variable=lang_var, width=160).pack(side="right")

ctk.CTkFrame(card, height=1, fg_color="gray30").pack(fill="x", padx=20, pady=8)

# Username
username_label = ctk.CTkLabel(card, text="Username", font=("Helvetica", 12, "bold"),
                               anchor="w")
username_label.pack(padx=22, pady=(4, 2), fill="x")
ctk.CTkEntry(card, textvariable=username_var,
              placeholder_text="Enter your username",
              width=370, height=40, corner_radius=9).pack(padx=22, pady=(0, 10))

# Password
password_label = ctk.CTkLabel(card, text="Password", font=("Helvetica", 12, "bold"),
                               anchor="w")
password_label.pack(padx=22, pady=(4, 2), fill="x")

pw_row = ctk.CTkFrame(card, fg_color="transparent")
pw_row.pack(padx=22, pady=(0, 4), fill="x")
password_entry = ctk.CTkEntry(pw_row, textvariable=password_var, show="*",
                               placeholder_text="Enter your password",
                               width=320, height=40, corner_radius=9)
password_entry.pack(side="left")
password_entry.bind("<KeyRelease>", check_strength)
eye_btn = ctk.CTkButton(pw_row, text="👁", width=42, height=40, corner_radius=9,
                          fg_color="transparent", border_width=1,
                          command=toggle_password_visibility)
eye_btn.pack(side="left", padx=(6, 0))

# Strength bar
str_row = ctk.CTkFrame(card, fg_color="transparent")
str_row.pack(padx=22, pady=(0, 10), fill="x")
strength_bar = ctk.CTkProgressBar(str_row, width=280, height=7, corner_radius=4)
strength_bar.pack(side="left", pady=2)
strength_bar.set(0)
strength_lbl = ctk.CTkLabel(str_row, text="", font=("Helvetica", 11), width=70)
strength_lbl.pack(side="left", padx=8)

# Confirm password
confirm_label = ctk.CTkLabel(card, text="Confirm Password",
                               font=("Helvetica", 12, "bold"), anchor="w")
confirm_label.pack(padx=22, pady=(4, 2), fill="x")
confirm_entry = ctk.CTkEntry(card, textvariable=confirm_var, show="*",
                              placeholder_text="Confirm your password",
                              width=370, height=40, corner_radius=9)
confirm_entry.pack(padx=22, pady=(0, 18))

# Buttons
login_btn = ctk.CTkButton(
    card, text="🔐  Login", command=login,
    width=370, height=44, font=("Helvetica", 14, "bold"),
    corner_radius=11, fg_color="#2563EB", hover_color="#1d4ed8"
)
login_btn.pack(padx=22, pady=(0, 8))

register_btn = ctk.CTkButton(
    card, text="📝  Register", command=register,
    width=370, height=44, font=("Helvetica", 14, "bold"),
    corner_radius=11, fg_color="transparent", border_width=2,
    text_color=("black", "white"), hover_color=("gray85", "gray20")
)
register_btn.pack(padx=22, pady=(0, 16))

# Footer hint
ctk.CTkLabel(card, text="Press  Enter  to login",
              font=("Helvetica", 10), text_color="gray").pack()


# ---------- Bindings ----------
lang_var.trace_add("write", update_labels)
root.bind("<Return>", lambda _: login())

root.mainloop()
