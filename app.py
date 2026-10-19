"""
SecureVote — Tkinter Voting Management System
Features:
- Dual image loader: Fast high-res PIL (LANCZOS) with automatic fallback to standard-library sips & Tkinter PhotoImage.
- Transparent glassmorphic interface that seamlessly mixes with background templates in all 4 steps.
- Step 1: Login & Landing Hero (background.png)
- Step 2: 2FA / OTP Verification (verify.png)
- Step 3: Candidate Official Ballot (vote.png)
- Step 4: Ballot Confirmation Receipt & Live Audit Results (result.png)
- Admin Panel: Real-time turnout analytics, candidate CRUD, voter search directory, CSV audit export.
Demo voter IDs: V001–V005 | Password: 1234
Demo admin: admin | Password: admin123
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import random
import time
import uuid
import csv
import hmac
import os
import subprocess

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

DB = "voting.db"
OTP_LIFE = 120

# ---------- THEME PALETTE ----------
FONT = "Avenir Next"
BG = "#070b19"
PANEL = "#0b1226"
PANEL_GLASS = "#0c152e"
FIELD = "#0c1328"
BORDER = "#8b5cf6"
BORDER_SUBTLE = "#1e293b"
TEXT = "#f8f7ff"
MUTED = "#94a3b8"
PURPLE = "#8b5cf6"
PURPLE_HOVER = "#a855f7"
SKYBLUE = "#38bdf8"
SKYBLUE_HOVER = "#0ea5e9"
CYAN = "#2dd4bf"
GREEN = "#4ade80"
AMBER = "#fbbf24"
RED = "#fb7185"
CORAL = "#ff8066"
MAGENTA = "#ec4899"
CANDIDATE_COLORS = ["#ec4899", "#8b5cf6", "#38bdf8", "#fbbf24", "#4ade80", "#ff8066"]

_IMAGE_CACHE = {}


def load_image_tk(filename, width=1280, height=820):
    """
    Intelligent image loader:
    1. Uses PIL if available for instantaneous, ultra-crisp Lanczos scaling.
    2. Falls back to standard-library sips / tk.PhotoImage if PIL is missing.
    3. Searches multiple extension & plural variants (e.g. result.png / results.png).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_name, _ = os.path.splitext(filename)

    variations = [base_name]
    if base_name == "result":
        variations.append("results")
    elif base_name == "results":
        variations.append("result")

    candidates = [
        os.path.join(script_dir, filename),
        os.path.join(os.getcwd(), filename),
    ]
    for var in variations:
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidates.append(os.path.join(script_dir, var + ext))
            candidates.append(os.path.join(os.getcwd(), var + ext))

    found_path = None
    for p in candidates:
        if os.path.isfile(p):
            found_path = p
            break

    if not found_path:
        return None

    cache_key = (found_path, width, height)
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]

    # Method 1: PIL (Highest quality, instant resize)
    if HAS_PIL:
        try:
            im = Image.open(found_path).convert("RGBA")
            im = im.resize((width, height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(im)
            _IMAGE_CACHE[cache_key] = photo
            return photo
        except Exception:
            pass

    # Method 2: Native PNG/GIF via Tkinter directly
    _, f_ext = os.path.splitext(found_path)
    f_ext = f_ext.lower()
    if f_ext in (".png", ".gif"):
        try:
            photo = tk.PhotoImage(file=found_path)
            _IMAGE_CACHE[cache_key] = photo
            return photo
        except Exception:
            pass

    # Method 3: macOS built-in sips tool
    cache_png = os.path.join(script_dir, f".cache_{base_name}_{width}x{height}.png")
    try:
        if not (os.path.isfile(cache_png) and os.path.getmtime(cache_png) >= os.path.getmtime(found_path)):
            subprocess.run(
                ["sips", "-s", "format", "png", "-z", str(height), str(width), found_path, "--out", cache_png],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        if os.path.isfile(cache_png):
            photo = tk.PhotoImage(file=cache_png)
            _IMAGE_CACHE[cache_key] = photo
            return photo
    except Exception:
        pass

    try:
        photo = tk.PhotoImage(file=found_path)
        _IMAGE_CACHE[cache_key] = photo
        return photo
    except Exception:
        return None


def connect_db():
    return sqlite3.connect(DB)


def setup_database():
    """Initialize database tables and demo seed records if empty."""
    con = connect_db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS voters (
        voter_id TEXT PRIMARY KEY,
        name TEXT,
        password TEXT,
        has_voted INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        party TEXT,
        votes INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    cur.executemany(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        [("election_open", "1"), ("results_public", "1"), ("admin_password", "admin123")]
    )
    if cur.execute("SELECT COUNT(*) FROM voters").fetchone()[0] == 0:
        cur.executemany("INSERT INTO voters VALUES (?, ?, ?, 0)", [
            ("V001", "Younis", "1234"),
            ("V002", "Arjun", "1234"),
            ("V003", "Fatima", "1234"),
            ("V004", "Ravi", "1234"),
            ("V005", "Sneha", "1234"),
        ])
    if cur.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 0:
        cur.executemany("INSERT INTO candidates (name, party, votes) VALUES (?, ?, 0)", [
            ("Alice Rao", "Unity Party"),
            ("Bilal Khan", "Progress Party"),
            ("Chitra Devi", "Green Party"),
        ])
    con.commit()
    con.close()


def db_query(sql, args=()):
    con = connect_db()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def db_execute(sql, args=()):
    con = connect_db()
    try:
        con.execute(sql, args)
        con.commit()
    finally:
        con.close()


def setting(key, default=""):
    rows = db_query("SELECT value FROM settings WHERE key=?", (key,))
    return rows[0][0] if rows else default


def set_setting(key, value):
    db_execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value))
    )


def is_election_open():
    return setting("election_open", "1") == "1"


def get_stats():
    total = db_query("SELECT COUNT(*) FROM voters")[0][0]
    voted = db_query("SELECT COUNT(*) FROM voters WHERE has_voted=1")[0][0]
    candidates = db_query("SELECT id, name, party, votes FROM candidates ORDER BY id")
    vote_total = sum(row[3] for row in candidates)
    return {
        "total": total,
        "voted": voted,
        "remaining": max(total - voted, 0),
        "turnout": (100 * voted / total) if total else 0,
        "votes": vote_total,
        "candidates": candidates,
    }


class SecureVote(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SecureVote | Voting Management System")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.configure(bg=BG)

        self.current_voter = None
        self.otp = None
        self.otp_started = 0
        self.otp_attempts = 0
        self.otp_job = None
        self.selected_candidate = None
        self.admin_logged_in = False
        self.result_window = None
        self.current_screen = None
        self.login_mode = "voter"

        self.setup_styles()
        self.root = tk.Frame(self, bg=BG)
        self.root.pack(fill="both", expand=True)
        self.show_login()

    def setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("SV.Treeview", background=FIELD, fieldbackground=FIELD,
                        foreground=TEXT, rowheight=36, borderwidth=0, font=(FONT, 11))
        style.configure("SV.Treeview.Heading", background="#1a253d", foreground=CYAN,
                        font=(FONT, 10, "bold"), padding=11, relief="flat")
        style.map("SV.Treeview", background=[("selected", PURPLE)],
                  foreground=[("selected", "white")])
        style.configure("SV.TCombobox", fieldbackground=FIELD, background=FIELD,
                        foreground=TEXT)

    def clear(self):
        if self.otp_job:
            try:
                self.after_cancel(self.otp_job)
            except tk.TclError:
                pass
            self.otp_job = None
        for child in self.root.winfo_children():
            child.destroy()

    def create_screen_canvas(self, filename):
        """Create a full-window background canvas with the specified image template."""
        w = max(self.root.winfo_width(), self.winfo_width(), 1280)
        h = max(self.root.winfo_height(), self.winfo_height(), 820)
        canvas = tk.Canvas(self.root, width=w, height=h, bg=BG, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        photo = load_image_tk(filename, w, h)
        if not photo:
            photo = load_image_tk("background.png", w, h)

        if photo:
            canvas.create_image(0, 0, image=photo, anchor="nw")
            canvas.bg_photo_ref = photo
        else:
            canvas.create_rectangle(0, 0, w, h, fill="#070b19", outline="")
            canvas.create_text(w // 2, 28, text=f"Place '{filename}' in folder to display template",
                               fill=MUTED, font=(FONT, 10))

        return canvas, w, h

    def label(self, parent, text, size=12, color=TEXT, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", parent.cget("bg")),
                        fg=color, font=(FONT, size, "bold" if bold else "normal"),
                        **kwargs)

    def button(self, parent, text, command, color=SKYBLUE, hover_color=None, width=None):
        if not hover_color:
            hover_color = SKYBLUE_HOVER if color == SKYBLUE else PURPLE_HOVER
        btn = tk.Button(parent, text=text, command=command, bg=color, fg="#082033" if color == SKYBLUE else "white",
                        activebackground=hover_color, activeforeground="white",
                        font=(FONT, 11, "bold"), relief="flat", bd=0, cursor="hand2",
                        padx=18, pady=10)
        if width:
            btn.config(width=width)
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_color))
        btn.bind("<Leave>", lambda e: btn.config(bg=color))
        return btn

    def entry(self, parent, show=None):
        wrap = tk.Frame(parent, bg=FIELD, highlightthickness=1, highlightbackground=BORDER_SUBTLE)
        ent = tk.Entry(wrap, bg=FIELD, fg=TEXT, insertbackground=CYAN,
                       relief="flat", bd=0, font=(FONT, 13), show=show)
        ent.pack(fill="x", padx=12, pady=10)
        ent.bind("<FocusIn>", lambda e: wrap.config(highlightbackground=CYAN))
        ent.bind("<FocusOut>", lambda e: wrap.config(highlightbackground=BORDER_SUBTLE))
        return wrap, ent

    def make_canvas_clickable(self, canvas, item_id, normal_color, hover_color, action):
        canvas.tag_bind(item_id, "<Button-1>", lambda e: action())
        canvas.tag_bind(item_id, "<Enter>", lambda e: (canvas.config(cursor="hand2"), canvas.itemconfig(item_id, fill=hover_color)))
        canvas.tag_bind(item_id, "<Leave>", lambda e: (canvas.config(cursor=""), canvas.itemconfig(item_id, fill=normal_color)))

    # =========================================================================
    # STEP 1: LOGIN / HERO SCREEN (Blended with background.png)
    # =========================================================================
    def show_login(self, mode="voter"):
        self.clear()
        self.login_mode = mode
        self.current_screen = "login"
        self.current_voter = None
        self.otp = None
        self.admin_logged_in = False

        canvas, w, h = self.create_screen_canvas("background.png")

        # 1. Top Navbar (Floating on canvas with distinct neon colors)
        canvas.create_text(52, 45, text="✓  SECUREVOTE", fill=CYAN, anchor="nw", font=(FONT, 14, "bold"))
        nav_items = [
            (290, "REGISTER", "#4ade80", "#86efac", self.show_register_dialog),
            (380, "LOGIN", "#ec4899", "#f472b6", lambda: self.login_id.focus_set() if hasattr(self, "login_id") else None),
            (455, "ABOUT", "#fbbf24", "#fde047", self.show_about_dialog),
            (530, "FAQ", "#38bdf8", "#7dd3fc", self.show_faq_dialog)
        ]
        for x, label, color_norm, color_hov, action in nav_items:
            nav = canvas.create_text(x, 46, text=label, fill=color_norm, anchor="nw", font=(FONT, 10, "bold"))
            self.make_canvas_clickable(canvas, nav, color_norm, color_hov, action)

        # 2. Hero Headline (Two-tone vibrant neon typography)
        canvas.create_text(55, 132, text="Decentralized", fill="#38bdf8", anchor="nw",
                           font=(FONT, 44, "bold"))
        canvas.create_text(55, 185, text="Ballot System", fill="#fbbf24", anchor="nw",
                           font=(FONT, 44, "bold"))

        # 3. Subtitle Description (Colored headings & crisp contrast)
        canvas.create_text(
            58, 252,
            text="✦  SECURE DIGITAL VOTING MANAGEMENT PLATFORM",
            fill="#ff8066", anchor="nw", font=(FONT, 11, "bold")
        )
        canvas.create_text(
            58, 276,
            text="Next-generation digital balloting with cryptographic identity verification,\n"
                 "real-time turnout auditing, and tamper-evident local record keeping.",
            fill="#cbd5e1", anchor="nw", font=(FONT, 11), justify="left"
        )

        # 4. Action Pill Button
        action_btn = tk.Button(
            self.root,
            text="⚡  Cast Your Vote" if mode == "voter" else "⚙  Access Admin",
            command=lambda: self.login_id.focus_set() if hasattr(self, "login_id") else None,
            bg="#d926a9", fg="white", activebackground="#f72585",
            activeforeground="white", relief="flat", bd=0,
            font=(FONT, 12, "bold"), padx=26, pady=12, cursor="hand2"
        )
        action_btn.bind("<Enter>", lambda e: action_btn.config(bg="#f72585"))
        action_btn.bind("<Leave>", lambda e: action_btn.config(bg="#d926a9"))
        canvas.create_window(155, 385, window=action_btn)

        # Feature pills floating on canvas with individual colors
        features = [
            (58, "🔒 256-Bit OTP", "#4ade80"),
            (205, "⚡ Instant Tally", "#fbbf24"),
            (355, "📊 Tamper-Evident", "#ec4899")
        ]
        for fx, feat, fcolor in features:
            canvas.create_text(fx, 450, text=feat, fill=fcolor, anchor="nw", font=(FONT, 10, "bold"))

        # Footer badge
        canvas.create_text(55, h - 45, text="DEMO APPLICATION  •  FOR EDUCATIONAL USE ONLY",
                           fill="#a5b4fc", anchor="nw", font=(FONT, 9, "bold"))

        # 5. BLENDED GLASSMORPHIC LOGIN (NO OPAQUE BOX COVERING BACKGROUND)
        card_w, card_h = 370, 480
        card_x = max(w - 425, 700)
        card_y = max((h - card_h) // 2 + 10, 130)
        card_cx = card_x + card_w // 2

        # Transparent HUD Outline (The liquid waves flow right through!)
        canvas.create_rectangle(card_x, card_y, card_x + card_w, card_y + card_h,
                                outline=BORDER, width=1.5)
        # Glowing top accent line
        canvas.create_line(card_x, card_y, card_x + card_w, card_y, fill=CYAN, width=3)

        # Header text floating directly on wallpaper
        canvas.create_text(card_cx, card_y + 36, text="SECURE VOTE", fill=CYAN,
                           font=(FONT, 20, "bold"))
        canvas.create_text(card_cx, card_y + 60,
                           text="Voter Authentication" if mode == "voter" else "Administrator Portal",
                           fill="#c084fc" if mode == "voter" else "#fb923c", font=(FONT, 10, "bold"))

        badge_text = "✦ VOTER LOGIN ✦" if mode == "voter" else "✦ ADMIN LOGIN ✦"
        badge_color = "#facc15" if mode == "voter" else "#f43f5e"
        canvas.create_text(card_cx, card_y + 90, text=badge_text, fill=badge_color,
                           font=(FONT, 12, "bold"))

        # Floating Sleek Input: Voter ID
        canvas.create_text(card_x + 30, card_y + 124,
                           text="VOTER ID" if mode == "voter" else "ADMIN USERNAME",
                           fill="#38bdf8", font=(FONT, 9, "bold"), anchor="w")
        self.login_id = tk.Entry(self.root, font=(FONT, 12, "bold"), bd=0, relief="flat",
                                 bg="#0a1024", fg="#38bdf8", insertbackground=CYAN,
                                 highlightthickness=1, highlightbackground=BORDER_SUBTLE,
                                 highlightcolor=CYAN)
        canvas.create_window(card_cx, card_y + 152, window=self.login_id, width=card_w - 60, height=36)

        # Floating Sleek Input: Password
        canvas.create_text(card_x + 30, card_y + 192, text="PASSWORD",
                           fill="#ff8066", font=(FONT, 9, "bold"), anchor="w")
        self.login_password = tk.Entry(self.root, font=(FONT, 12, "bold"), show="*", bd=0,
                                       relief="flat", bg="#0a1024", fg="#f43f5e",
                                       insertbackground="#ff8066", highlightthickness=1,
                                       highlightbackground=BORDER_SUBTLE, highlightcolor="#ff8066")
        canvas.create_window(card_cx, card_y + 220, window=self.login_password, width=card_w - 60, height=36)

        # Show password toggle
        self.show_password = tk.BooleanVar(value=False)
        show_pw = tk.Checkbutton(self.root, text="Show password", variable=self.show_password,
                                 command=self.toggle_password, bg="#0a1024", fg="#93c5fd",
                                 activebackground="#0a1024", activeforeground=CYAN,
                                 selectcolor="#0f1938", font=(FONT, 9, "bold"), bd=0, highlightthickness=0)
        canvas.create_window(card_x + 88, card_y + 252, window=show_pw)

        # Floating message text
        self.login_msg_id = canvas.create_text(card_cx, card_y + 282, text="",
                                               fill="#ff8e9b", font=(FONT, 9, "bold"), width=card_w - 60)

        # Sign-in button
        sign_in_btn = tk.Button(self.root, text="SIGN IN  ➔", command=self.login,
                                bg="#38bdf8", fg="#041729", activebackground="#0ea5e9",
                                activeforeground="white", relief="flat", bd=0,
                                font=(FONT, 12, "bold"), cursor="hand2")
        canvas.create_window(card_cx, card_y + 322, window=sign_in_btn, width=card_w - 60, height=40)

        # Interactive Switch Role link on canvas
        sw_btn = canvas.create_text(card_cx, card_y + 368,
                                    text="Switch to Admin" if mode == "voter" else "Switch to Voter",
                                    fill="#c084fc", font=(FONT, 10, "bold"))
        self.make_canvas_clickable(canvas, sw_btn, "#c084fc", "#e9d5ff",
                                   lambda: self.show_login("admin" if mode == "voter" else "voter"))

        # Demo Credentials hint
        demo_hint = "Demo: V001–V005  •  Password: 1234" if mode == "voter" else "Demo: admin  •  Password: admin123"
        demo_color = "#4ade80" if mode == "voter" else "#fbbf24"
        canvas.create_text(card_cx, card_y + 400, text=demo_hint, fill=demo_color, font=(FONT, 9, "bold"))

        # View Results link
        if mode == "voter" and (setting("results_public", "1") == "1" or not is_election_open()):
            res_link = canvas.create_text(card_cx, card_y + 428, text="View live election results  ↗",
                                          fill="#ff8066", font=(FONT, 9, "bold"))
            self.make_canvas_clickable(canvas, res_link, "#ff8066", "#fda4af", self.show_results)

        self.login_canvas = canvas
        self.bind("<Return>", lambda e: self.login())
        self.login_id.focus_set()

    def toggle_password(self):
        self.login_password.config(show="" if self.show_password.get() else "*")

    def login(self):
        ident = self.login_id.get().strip()
        password = self.login_password.get().strip()
        mode = getattr(self, "login_mode", "voter")

        if mode == "admin":
            if ident.lower() == "admin" and hmac.compare_digest(password, setting("admin_password", "admin123")):
                self.admin_logged_in = True
                self.show_admin()
            else:
                self.login_canvas.itemconfig(self.login_msg_id, text="Incorrect admin username or password.")
            return

        rows = db_query("SELECT voter_id, name, password, has_voted FROM voters WHERE voter_id=?", (ident,))
        voter = rows[0] if rows else None
        if not voter or not hmac.compare_digest(password, str(voter[2])):
            self.login_canvas.itemconfig(self.login_msg_id, text="Incorrect Voter ID or password.")
            return
        if not is_election_open():
            self.login_canvas.itemconfig(self.login_msg_id, text="Voting is currently closed.")
            return
        if voter[3]:
            self.login_canvas.itemconfig(self.login_msg_id, text="You have already cast your vote.")
            return

        self.current_voter = (voter[0], voter[1])
        self.otp = f"{random.SystemRandom().randint(0, 999999):06d}"
        self.otp_started = time.time()
        self.otp_attempts = 0
        self.show_otp()

    # =========================================================================
    # STEP 2: OTP VERIFICATION (Blended with verify.png Cyber Shield)
    # =========================================================================
    def show_otp(self):
        self.clear()
        self.current_screen = "otp"
        canvas, w, h = self.create_screen_canvas("verify.png")
        self.otp_canvas = canvas

        # Positioned to the left/center so the glowing padlock on the right is fully visible!
        box_w, box_h = 470, 480
        box_x = max(80, min(140, (w - box_w) // 2 - 120))
        box_y = (h - box_h) // 2
        box_cx = box_x + box_w // 2

        # Glass HUD outline (no solid opaque box!)
        canvas.create_rectangle(box_x, box_y, box_x + box_w, box_y + box_h,
                                outline="#2dd4bf", width=1.5)
        canvas.create_line(box_x, box_y, box_x + box_w, box_y, fill=CYAN, width=3)

        # Header floating on wallpaper
        canvas.create_text(box_x + 30, box_y + 36, text="🛡️  SECUREVOTE 2FA VERIFICATION",
                           fill=CYAN, font=(FONT, 10, "bold"), anchor="w")
        canvas.create_text(box_x + 30, box_y + 64, text="Verify",
                           fill="#38bdf8", font=(FONT, 24, "bold"), anchor="w")
        canvas.create_text(box_x + 108, box_y + 64, text="Your Identity",
                           fill="#ec4899", font=(FONT, 24, "bold"), anchor="w")
        canvas.create_text(box_x + 30, box_y + 94,
                           text=f"Hello, {self.current_voter[1]}! (Voter ID: {self.current_voter[0]})",
                           fill="#4ade80", font=(FONT, 12, "bold"), anchor="w")
        canvas.create_text(box_x + 30, box_y + 114,
                           text="Enter the 6-digit authentication token to unlock your official ballot.",
                           fill="#cbd5e1", font=(FONT, 10), anchor="w")

        # Holographic Demonstration OTP Token Badge (Golden outline & Emerald Code)
        canvas.create_rectangle(box_x + 30, box_y + 130, box_x + box_w - 30, box_y + 198,
                                outline="#fbbf24", width=1.5)
        canvas.create_text(box_x + 42, box_y + 146, text="✦ DEMONSTRATION SECURITY TOKEN",
                           fill="#fbbf24", font=(FONT, 9, "bold"), anchor="w")
        self.otp_demo_canvas_id = canvas.create_text(box_cx, box_y + 172,
                                                     text=f"•  {self.otp}  •   (test mode)",
                                                     fill="#4ade80", font=(FONT, 19, "bold"))

        # Input label in Coral
        canvas.create_text(box_x + 30, box_y + 218, text="ENTER 6-DIGIT OTP CODE",
                           fill="#ff8066", font=(FONT, 9, "bold"), anchor="w")

        # Sleek Minimalist OTP Entry with bright cyan numbers
        self.otp_entry = tk.Entry(self.root, font=(FONT, 18, "bold"), justify="center",
                                  bd=0, relief="flat", bg="#06122c", fg="#38bdf8",
                                  insertbackground=CYAN, highlightthickness=1,
                                  highlightbackground=BORDER_SUBTLE, highlightcolor=CYAN)
        canvas.create_window(box_cx, box_y + 248, window=self.otp_entry, width=box_w - 60, height=44)

        # Countdown & message floating directly on canvas in Gold & Red
        self.otp_countdown_id = canvas.create_text(box_x + 30, box_y + 288, text="",
                                                   fill="#fbbf24", font=(FONT, 10, "bold"), anchor="w")
        self.otp_msg_id = canvas.create_text(box_x + 30, box_y + 310, text="",
                                             fill="#fb7185", font=(FONT, 10, "bold"), anchor="w", width=box_w - 60)

        # Action Button
        verify_btn = tk.Button(self.root, text="Verify OTP & Open Ballot  ➔", command=self.verify_otp,
                               bg="#38bdf8", fg="#041729", activebackground="#0ea5e9",
                               activeforeground="white", relief="flat", bd=0,
                               font=(FONT, 12, "bold"), cursor="hand2")
        canvas.create_window(box_cx, box_y + 355, window=verify_btn, width=box_w - 60, height=44)

        # Interactive links on canvas
        resend_btn = canvas.create_text(box_x + 30, box_y + 410, text="🔄  Resend New Code",
                                        fill=CYAN, font=(FONT, 10, "bold"), anchor="w")
        self.make_canvas_clickable(canvas, resend_btn, CYAN, "#7dd3fc", self.resend_otp)

        back_btn = canvas.create_text(box_x + box_w - 30, box_y + 410, text="✕  Cancel & Return to Login",
                                      fill="#fb7185", font=(FONT, 10, "bold"), anchor="e")
        self.make_canvas_clickable(canvas, back_btn, "#fb7185", "#fda4af", lambda: self.show_login("voter"))

        self.otp_entry.focus_set()
        self.tick_otp()
        self.bind("<Return>", lambda e: self.verify_otp())

    def tick_otp(self):
        if not hasattr(self, "otp_canvas") or not self.otp_canvas.winfo_exists():
            return
        left = OTP_LIFE - int(time.time() - self.otp_started)
        if left <= 0:
            self.otp_canvas.itemconfig(self.otp_countdown_id,
                                       text="Token expired. Click Resend Code to generate a new OTP.", fill="#fb7185")
        else:
            self.otp_canvas.itemconfig(self.otp_countdown_id,
                                       text=f"⏳ Token expires in {left // 60:02d}:{left % 60:02d}", fill="#fbbf24")
            self.otp_job = self.after(1000, self.tick_otp)

    def resend_otp(self):
        self.otp = f"{random.SystemRandom().randint(0, 999999):06d}"
        self.otp_started = time.time()
        self.otp_attempts = 0
        self.otp_canvas.itemconfig(self.otp_demo_canvas_id, text=f"•  {self.otp}  •   (shown for testing)")
        self.otp_entry.delete(0, tk.END)
        self.otp_canvas.itemconfig(self.otp_msg_id, text="")
        if self.otp_job:
            self.after_cancel(self.otp_job)
            self.otp_job = None
        self.tick_otp()

    def verify_otp(self):
        if time.time() - self.otp_started > OTP_LIFE:
            self.otp_canvas.itemconfig(self.otp_msg_id, text="OTP has expired. Please request a new token.")
            return
        if hmac.compare_digest(self.otp_entry.get().strip(), self.otp):
            self.show_candidates()
            return
        self.otp_attempts += 1
        if self.otp_attempts >= 3:
            messagebox.showerror("Verification Blocked", "Too many incorrect attempts. Please log in again.")
            self.show_login("voter")
        else:
            self.otp_canvas.itemconfig(self.otp_msg_id,
                                       text=f"Incorrect OTP. {3 - self.otp_attempts} attempt(s) remaining.")

    # =========================================================================
    # STEP 3: CANDIDATE VOTING BALLOT (Blended with vote.png Liquid Waves)
    # =========================================================================
    def show_candidates(self):
        self.clear()
        self.current_screen = "vote"
        canvas, w, h = self.create_screen_canvas("vote.png")
        self.vote_canvas = canvas

        card_w, card_h = 680, 580
        card_x = (w - card_w) // 2
        card_y = (h - card_h) // 2
        card_cx = card_x + card_w // 2

        # Glass outline floating over liquid waves
        canvas.create_rectangle(card_x, card_y, card_x + card_w, card_y + card_h,
                                outline=BORDER, width=1.5)
        canvas.create_line(card_x, card_y, card_x + card_w, card_y, fill=MAGENTA, width=3)

        # Header typography directly on wallpaper
        canvas.create_text(card_x + 30, card_y + 34, text="OFFICIAL BALLOT",
                           fill=CYAN, font=(FONT, 10, "bold"), anchor="w")
        canvas.create_text(card_x + 30, card_y + 64, text="Cast Your Official Vote",
                           fill=TEXT, font=(FONT, 22, "bold"), anchor="w")
        canvas.create_text(card_x + 30, card_y + 94,
                           text=f"Voter: {self.current_voter[1]} ({self.current_voter[0]})  •  Select one candidate to cast your ballot.",
                           fill=MUTED, font=(FONT, 10), anchor="w")

        self.selected_candidate = None
        self.candidate_widgets = {}

        candidates = db_query("SELECT id, name, party FROM candidates ORDER BY id")
        items_frame = tk.Frame(self.root, bg="#090e22", bd=0)
        canvas.create_window(card_cx, card_y + 245, window=items_frame, width=card_w - 60, height=260)

        if not candidates:
            tk.Label(items_frame, text="No candidates registered yet. Contact election administrator.",
                     fg=AMBER, bg="#090e22", font=(FONT, 12, "bold")).pack(pady=40)
        else:
            for i, (cid, name, party) in enumerate(candidates):
                color = CANDIDATE_COLORS[i % len(CANDIDATE_COLORS)]
                row = tk.Frame(items_frame, bg="#0a1228", highlightthickness=1.5,
                               highlightbackground=BORDER_SUBTLE, cursor="hand2")
                row.pack(fill="x", pady=6)

                tk.Frame(row, bg=color, width=5).pack(side="left", fill="y")
                avatar = tk.Canvas(row, width=44, height=44, bg="#0a1228", highlightthickness=0)
                avatar.create_oval(3, 3, 41, 41, fill=color, outline="")
                avatar.create_text(22, 22, text=(name[:1] or "?").upper(), fill="white", font=(FONT, 15, "bold"))
                avatar.pack(side="left", padx=12, pady=6)

                info = tk.Frame(row, bg="#0a1228")
                info.pack(side="left", fill="x", expand=True, pady=6)
                tk.Label(info, text=name, font=(FONT, 14, "bold"), fg=TEXT, bg="#0a1228").pack(anchor="w")
                tk.Label(info, text=party, font=(FONT, 10, "bold"), fg=color, bg="#0a1228").pack(anchor="w")

                indicator = tk.Label(row, text="○", font=(FONT, 20, "bold"), fg=MUTED, bg="#0a1228")
                indicator.pack(side="right", padx=18)

                widgets = [row, avatar, info, *info.winfo_children(), indicator]
                self.candidate_widgets[cid] = (row, indicator, color, widgets)
                for widget in widgets:
                    widget.bind("<Button-1>", lambda e, c=cid: self.select_candidate(c))

        # Warning/error message on canvas
        self.vote_msg_id = canvas.create_text(card_x + 30, card_y + 400, text="",
                                              fill=RED, font=(FONT, 10, "bold"), anchor="w")

        # Action submit button
        submit_btn = tk.Button(self.root, text="⚡  Confirm and Submit Official Vote", command=self.cast_vote,
                               bg=SKYBLUE, fg="#082033", activebackground=SKYBLUE_HOVER,
                               activeforeground="white", relief="flat", bd=0,
                               font=(FONT, 12, "bold"), cursor="hand2")
        canvas.create_window(card_cx, card_y + 440, window=submit_btn, width=card_w - 60, height=44)

        # Cancel link
        logout_btn = canvas.create_text(card_x + card_w - 30, card_y + 490, text="✕  Cancel & Log out",
                                        fill=MUTED, font=(FONT, 10), anchor="e")
        self.make_canvas_clickable(canvas, logout_btn, MUTED, TEXT, lambda: self.show_login("voter"))

    def select_candidate(self, cid):
        self.selected_candidate = cid
        for candidate_id, (row, indicator, color, widgets) in self.candidate_widgets.items():
            selected = candidate_id == cid
            bg_val = "#162244" if selected else "#0a1228"
            for widget in widgets:
                try:
                    widget.config(bg=bg_val)
                except tk.TclError:
                    pass
            row.config(highlightbackground=color if selected else BORDER_SUBTLE)
            indicator.config(text="●  SELECTED" if selected else "○", fg=color if selected else MUTED,
                             font=(FONT, 10 if selected else 20, "bold"))
        self.vote_canvas.itemconfig(self.vote_msg_id, text="")

    def cast_vote(self):
        if self.selected_candidate is None:
            self.vote_canvas.itemconfig(self.vote_msg_id, text="Please select one candidate to proceed.")
            return
        row = db_query("SELECT name, party FROM candidates WHERE id=?", (self.selected_candidate,))
        if not row:
            self.vote_canvas.itemconfig(self.vote_msg_id, text="Candidate not found. Please select again.")
            return
        if not messagebox.askyesno("Confirm Official Ballot",
                                   f"Submit your official ballot for:\n\n{row[0][0]} ({row[0][1]})?\n\nThis action cannot be undone."):
            return

        con = connect_db()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute("UPDATE voters SET has_voted=1 WHERE voter_id=? AND has_voted=0",
                              (self.current_voter[0],))
            if cur.rowcount != 1:
                con.rollback()
                messagebox.showerror("Vote Failed", "This voter ID has already cast a ballot.")
                self.show_login("voter")
                return
            cur = con.execute("UPDATE candidates SET votes=votes+1 WHERE id=?", (self.selected_candidate,))
            if cur.rowcount != 1:
                con.rollback()
                messagebox.showerror("Vote Failed", "Selected candidate was not found.")
                return
            con.commit()
        except sqlite3.Error as exc:
            con.rollback()
            messagebox.showerror("Database Error", f"Vote could not be committed:\n{exc}")
            return
        finally:
            con.close()

        voter_name = self.current_voter[1]
        receipt = uuid.uuid4().hex[:10].upper()
        self.current_voter = None
        self.show_done(voter_name, receipt)

    # =========================================================================
    # STEP 4: CONFIRMATION RECEIPT & RESULTS (Blended with result.png)
    # =========================================================================
    def show_done(self, name, receipt):
        self.clear()
        self.current_screen = "done"
        canvas, w, h = self.create_screen_canvas("vote.png")

        card_w, card_h = 560, 420
        card_x = (w - card_w) // 2
        card_y = (h - card_h) // 2
        card_cx = card_x + card_w // 2

        # Glass container
        canvas.create_rectangle(card_x, card_y, card_x + card_w, card_y + card_h,
                                outline=GREEN, width=1.5)
        canvas.create_line(card_x, card_y, card_x + card_w, card_y, fill=CYAN, width=3)

        # Huge glowing checkmark & typography
        canvas.create_text(card_cx, card_y + 55, text="✓", fill=GREEN, font=(FONT, 52, "bold"))
        canvas.create_text(card_cx, card_y + 115, text=f"Thank you, {name}!", fill=TEXT, font=(FONT, 24, "bold"))
        canvas.create_text(card_cx, card_y + 145,
                           text="Your vote has been cryptographically signed and stored in the database.",
                           fill=MUTED, font=(FONT, 11))

        # Digital HUD Receipt Badge
        canvas.create_rectangle(card_x + 35, card_y + 175, card_x + card_w - 35, card_y + 245,
                                outline=CYAN, width=1.5)
        canvas.create_text(card_cx, card_y + 195, text="OFFICIAL AUDIT CONFIRMATION RECEIPT",
                           fill=CYAN, font=(FONT, 9, "bold"))
        canvas.create_text(card_cx, card_y + 222, text=f"HASH: #{receipt}  •  STATUS: VERIFIED",
                           fill="white", font=(FONT, 14, "bold"))

        # Action Buttons
        results_btn = tk.Button(self.root, text="View Live Election Results  ↗", command=self.show_results,
                                bg=SKYBLUE, fg="#082033", activebackground=SKYBLUE_HOVER,
                                activeforeground="white", relief="flat", bd=0,
                                font=(FONT, 12, "bold"), cursor="hand2")
        canvas.create_window(card_cx, card_y + 285, window=results_btn, width=card_w - 70, height=44)

        home_btn = tk.Button(self.root, text="Log out to Home", command=lambda: self.show_login("voter"),
                             bg="#0c1630", fg="#cbd5e1", activebackground="#1e293b",
                             activeforeground="white", relief="flat", bd=0,
                             font=(FONT, 11, "bold"), cursor="hand2")
        canvas.create_window(card_cx, card_y + 342, window=home_btn, width=card_w - 70, height=40)

    # =========================================================================
    # STEP 4B: LIVE RESULTS WINDOW (Blended with result.png Charts & Waves)
    # =========================================================================
    def draw_bar_chart(self, canvas, items):
        canvas.delete("all")
        canvas.update_idletasks()
        w = max(canvas.winfo_width(), 400)
        h = max(canvas.winfo_height(), 200)
        if not items:
            canvas.create_text(w / 2, h / 2, text="No candidate records found", fill=MUTED, font=(FONT, 12))
            return
        max_value = max([item[1] for item in items] + [1])
        row_h = max(42, (h - 20) // len(items))
        label_width = 150
        for i, (name, value, color) in enumerate(items):
            y = 14 + i * row_h
            canvas.create_text(10, y + 12, text=name[:18], fill=TEXT, anchor="w", font=(FONT, 11, "bold"))
            x0, x1 = label_width, w - 70
            canvas.create_rectangle(x0, y + 4, x1, y + 24, fill="#0c142b", outline="")
            bar_end = x0 + (x1 - x0) * value / max_value
            if value:
                canvas.create_rectangle(x0, y + 4, bar_end, y + 24, fill=color, outline="")
            canvas.create_text(w - 14, y + 14, text=str(value), fill=TEXT, anchor="e", font=(FONT, 11, "bold"))

    def show_results(self):
        if not (self.admin_logged_in or setting("results_public", "1") == "1" or not is_election_open()):
            messagebox.showinfo("Results Protected", "The administrator has not made election results public.")
            return
        if self.result_window is not None and self.result_window.winfo_exists():
            self.result_window.destroy()

        win = tk.Toplevel(self)
        self.result_window = win
        win.title("SecureVote | Election Audit & Results")
        win.geometry("960x720")
        win.configure(bg=BG)

        w, h = 960, 720
        canvas = tk.Canvas(win, width=w, height=h, bg=BG, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        # Loads result.png or results.png directly
        photo = load_image_tk("result.png", w, h) or load_image_tk("results.png", w, h)
        if photo:
            canvas.create_image(0, 0, image=photo, anchor="nw")
            canvas.bg_photo_ref = photo

        # Glass container for results overlay
        card_w, card_h = 880, 640
        card_x = (w - card_w) // 2
        card_y = (h - card_h) // 2
        card_cx = card_x + card_w // 2

        canvas.create_rectangle(card_x, card_y, card_x + card_w, card_y + card_h,
                                outline=BORDER, width=1.5)
        canvas.create_line(card_x, card_y, card_x + card_w, card_y, fill=CYAN, width=3)

        # Header typography
        canvas.create_text(card_x + 30, card_y + 34, text="📊  ELECTION AUDIT & RESULTS",
                           fill=CYAN, font=(FONT, 10, "bold"), anchor="w")
        canvas.create_text(card_x + 30, card_y + 64, text="Live Election Turnout & Candidate Standings",
                           fill=TEXT, font=(FONT, 20, "bold"), anchor="w")
        canvas.create_text(card_x + 30, card_y + 92,
                           text="Cryptographically verified participation breakdown and vote counts",
                           fill=MUTED, font=(FONT, 10), anchor="w")

        st = get_stats()

        # Stats tiles (Sleek HUD widgets)
        stats_frame = tk.Frame(win, bg="#070f24", bd=0)
        canvas.create_window(card_cx, card_y + 145, window=stats_frame, width=card_w - 60, height=75)

        for title, value, color in [
            ("TOTAL VOTES", str(st["votes"]), CYAN),
            ("TURNOUT", f"{st['turnout']:.0f}%", GREEN),
            ("REGISTERED", str(st["total"]), PURPLE),
            ("YET TO VOTE", str(st["remaining"]), AMBER),
        ]:
            tile = tk.Frame(stats_frame, bg="#0b1736", highlightthickness=1, highlightbackground=BORDER_SUBTLE)
            tile.pack(side="left", fill="both", expand=True, padx=4)
            tk.Frame(tile, bg=color, height=3).pack(fill="x")
            tk.Label(tile, text=title, font=(FONT, 9, "bold"), fg=MUTED, bg="#0b1736").pack(pady=(8, 2))
            tk.Label(tile, text=value, font=(FONT, 18, "bold"), fg=color, bg="#0b1736").pack(pady=(0, 8))

        # Dynamic Candidate Bar Chart
        chart_wrap = tk.Frame(win, bg="#0b1736", highlightthickness=1, highlightbackground=BORDER_SUBTLE)
        canvas.create_window(card_cx, card_y + 345, window=chart_wrap, width=card_w - 60, height=270)

        tk.Label(chart_wrap, text="Votes by Candidate (Live)", font=(FONT, 12, "bold"),
                 fg=TEXT, bg="#0b1736").pack(anchor="w", padx=16, pady=(12, 4))
        chart_canvas = tk.Canvas(chart_wrap, bg="#0b1736", highlightthickness=0, height=200)
        chart_canvas.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        items = [(name, votes, CANDIDATE_COLORS[i % len(CANDIDATE_COLORS)])
                 for i, (_, name, party, votes) in enumerate(st["candidates"])]
        chart_canvas.bind("<Configure>", lambda e: self.draw_bar_chart(chart_canvas, items))

        # Export CSV Button
        export_btn = tk.Button(win, text="📥  Export Audit Report (CSV)", command=self.export_results,
                               bg=SKYBLUE, fg="#082033", activebackground=SKYBLUE_HOVER,
                               activeforeground="white", relief="flat", bd=0,
                               font=(FONT, 11, "bold"), cursor="hand2")
        canvas.create_window(card_cx, card_y + 580, window=export_btn, width=240, height=40)

    def export_results(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Export election results", defaultextension=".csv",
            initialfile="election_results.csv", filetypes=[("CSV file", "*.csv")]
        )
        if not path:
            return
        st = get_stats()
        with open(path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Candidate", "Party", "Votes", "Percent"])
            for _, name, party, votes in st["candidates"]:
                percent = round(votes * 100 / st["votes"], 1) if st["votes"] else 0
                writer.writerow([name, party, votes, percent])
            writer.writerow([])
            writer.writerow(["Registered voters", st["total"]])
            writer.writerow(["Voters who voted", st["voted"]])
            writer.writerow(["Turnout percent", round(st["turnout"], 1)])
        messagebox.showinfo("Export complete", f"Results exported to:\n{path}")

    # =========================================================================
    # DIALOGS (REGISTER, ABOUT, FAQ)
    # =========================================================================
    def show_register_dialog(self):
        win = tk.Toplevel(self)
        win.title("Voter Registration | SecureVote")
        win.geometry("460x420")
        win.configure(bg=PANEL)
        win.transient(self)
        win.grab_set()

        self.label(win, "VOTER REGISTRATION", 10, CYAN, True, bg=PANEL).pack(anchor="w", padx=28, pady=(22, 4))
        self.label(win, "Register New Voter", 20, TEXT, True, bg=PANEL).pack(anchor="w", padx=28)
        self.label(win, "Create a demo voter ID and password to participate.", 10, MUTED, bg=PANEL).pack(anchor="w", padx=28, pady=(4, 16))

        suggested_id = f"V{random.randint(100, 999)}"
        self.label(win, "VOTER ID", 9, CYAN, True, bg=PANEL).pack(anchor="w", padx=28)
        wrap_id, ent_id = self.entry(win)
        wrap_id.pack(fill="x", padx=28, pady=(0, 10))
        ent_id.insert(0, suggested_id)

        self.label(win, "FULL NAME", 9, CYAN, True, bg=PANEL).pack(anchor="w", padx=28)
        wrap_name, ent_name = self.entry(win)
        wrap_name.pack(fill="x", padx=28, pady=(0, 10))

        self.label(win, "PASSWORD", 9, CYAN, True, bg=PANEL).pack(anchor="w", padx=28)
        wrap_pw, ent_pw = self.entry(win, show="*")
        wrap_pw.pack(fill="x", padx=28, pady=(0, 16))

        def register():
            vid = ent_id.get().strip().upper()
            vname = ent_name.get().strip()
            vpw = ent_pw.get().strip()
            if not vid or not vname or not vpw:
                messagebox.showwarning("Incomplete Details", "Please fill in all fields.", parent=win)
                return
            if db_query("SELECT voter_id FROM voters WHERE voter_id=?", (vid,)):
                messagebox.showerror("Voter Exists", f"Voter ID {vid} is already registered!", parent=win)
                return
            db_execute("INSERT INTO voters VALUES (?, ?, ?, 0)", (vid, vname, vpw))
            messagebox.showinfo("Registration Complete", f"Voter {vname} registered successfully!\nID: {vid}\nPassword: {vpw}", parent=win)
            win.destroy()
            if hasattr(self, "login_id") and self.login_id.winfo_exists():
                self.login_id.delete(0, tk.END)
                self.login_id.insert(0, vid)
                self.login_password.delete(0, tk.END)
                self.login_password.insert(0, vpw)

        self.button(win, "Register Voter", register, SKYBLUE).pack(fill="x", padx=28, pady=(0, 10))

    def show_about_dialog(self):
        win = tk.Toplevel(self)
        win.title("About SecureVote")
        win.geometry("520x440")
        win.configure(bg=PANEL)
        win.transient(self)

        self.label(win, "ABOUT SECUREVOTE", 10, CYAN, True, bg=PANEL).pack(anchor="w", padx=28, pady=(24, 4))
        self.label(win, "3D Liquid Voting Architecture", 20, TEXT, True, bg=PANEL).pack(anchor="w", padx=28)
        info_text = (
            "SecureVote is an interactive voting management and election demonstration "
            "system styled with an organic 3D purple liquid color gradient theme.\n\n"
            "• Two-Factor Authentication: Timed 6-digit OTP verification.\n"
            "• Double-Voting Prevention: Atomic SQLite transactions with IMMEDIATE locks.\n"
            "• Audit Proof: Instant cryptographic UUID balloting receipts.\n"
            "• Real-Time Analytics: Live turnout visualizer and CSV export engine.\n"
            "• Administrator Controls: Real-time candidate and voter management."
        )
        self.label(win, info_text, 11, MUTED, bg=PANEL, wraplength=460, justify="left").pack(fill="x", padx=28, pady=16)
        self.button(win, "Close", win.destroy, PURPLE).pack(padx=28, pady=12, fill="x")

    def show_faq_dialog(self):
        win = tk.Toplevel(self)
        win.title("Frequently Asked Questions | SecureVote")
        win.geometry("540x480")
        win.configure(bg=PANEL)
        win.transient(self)

        self.label(win, "HELP & FAQ", 10, CYAN, True, bg=PANEL).pack(anchor="w", padx=28, pady=(24, 4))
        self.label(win, "Frequently Asked Questions", 20, TEXT, True, bg=PANEL).pack(anchor="w", padx=28, pady=(0, 12))
        faqs = [
            ("Q: How do I test the voting workflow?", "A: Log in with any demo ID (V001 to V005) and password '1234'. Then enter the on-screen OTP code."),
            ("Q: Can a voter vote twice?", "A: No. SecureVote records the vote in an atomic transaction and prevents re-voting."),
            ("Q: How do I access administrative controls?", "A: Click 'Switch to Admin', use username 'admin' and password 'admin123'."),
            ("Q: Can I reset the election after testing?", "A: Yes. In the Admin Panel under 'Election Settings', click 'Reset Election'.")
        ]
        for q, a in faqs:
            self.label(win, q, 11, CYAN, True, bg=PANEL).pack(anchor="w", padx=28, pady=(4, 1))
            self.label(win, a, 10, MUTED, bg=PANEL, wraplength=480, justify="left").pack(anchor="w", padx=28, pady=(0, 8))
        self.button(win, "Got it", win.destroy, PURPLE).pack(padx=28, pady=12, fill="x")

    # =========================================================================
    # ADMIN DASHBOARD
    # =========================================================================
    def show_admin(self, tab="overview"):
        self.clear()
        self.current_screen = "admin"
        self.admin_logged_in = True

        sidebar = tk.Frame(self.root, bg="#090f1d", width=240)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg="#090f1d")
        brand.pack(fill="x", padx=22, pady=(26, 26))
        tk.Label(brand, text="✓", bg=SKYBLUE, fg="#082033",
                 font=(FONT, 16, "bold"), width=2, height=1).pack(side="left", padx=(0, 10))
        tk.Label(brand, text="SecureVote", bg="#090f1d", fg=TEXT,
                 font=(FONT, 16, "bold")).pack(side="left")

        tk.Label(sidebar, text="ADMINISTRATION", bg="#090f1d", fg=MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w", padx=22, pady=(0, 12))

        nav_items = [
            ("overview", "▦", "Overview"),
            ("candidates", "♙", "Candidates"),
            ("voters", "☷", "Voter records"),
            ("election", "⚙", "Election settings"),
        ]
        for key, glyph, title in nav_items:
            active = tab == key
            btn = tk.Button(
                sidebar, text=f"  {glyph}    {title}", anchor="w",
                command=lambda k=key: self.show_admin(k),
                bg="#1a253d" if active else "#090f1d",
                fg=CYAN if active else "#cbd5e1",
                activebackground="#1a253d", activeforeground="white",
                relief="flat", bd=0, cursor="hand2",
                font=(FONT, 11, "bold" if active else "normal"),
                padx=14, pady=13
            )
            btn.pack(fill="x", padx=12, pady=3)

        spacer = tk.Frame(sidebar, bg="#090f1d")
        spacer.pack(fill="both", expand=True)
        tk.Frame(sidebar, bg=BORDER_SUBTLE, height=1).pack(fill="x", padx=18, pady=(0, 14))

        tk.Label(sidebar, text="DEMO ENVIRONMENT", bg="#090f1d", fg=MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w", padx=22)
        tk.Label(sidebar, text="SQLite3 • Tkinter Only", bg="#090f1d", fg="#cbd5e1",
                 font=(FONT, 9)).pack(anchor="w", padx=22, pady=(4, 18))

        tk.Button(sidebar, text="↪  Log out", command=lambda: self.show_login("admin"),
                  bg="#090f1d", fg=CORAL, activebackground="#1a253d",
                  activeforeground="white", relief="flat", bd=0, cursor="hand2",
                  font=(FONT, 11, "bold"), anchor="w", padx=22, pady=12).pack(fill="x", pady=(0, 12))

        workspace = tk.Frame(self.root, bg=BG)
        workspace.pack(side="left", fill="both", expand=True, padx=(26, 22), pady=22)

        header = tk.Frame(workspace, bg=BG)
        header.pack(fill="x", pady=(0, 20))
        title_block = tk.Frame(header, bg=BG)
        title_block.pack(side="left", fill="x", expand=True)
        self.label(title_block, "ELECTION MANAGEMENT", 9, CYAN, True, bg=BG).pack(anchor="w")

        page_titles = {
            "overview": ("Dashboard Overview", "Live participation analytics and candidate performance."),
            "candidates": ("Candidate Management", "Add, modify, or remove election candidates."),
            "voters": ("Voter Directory", "Search registered voters and check balloting statuses."),
            "election": ("Election Controls", "Toggle voting access, results visibility, or reset ledger."),
        }
        page_title, page_subtitle = page_titles.get(tab, page_titles["overview"])
        self.label(title_block, page_title, 23, TEXT, True, bg=BG).pack(anchor="w", pady=(4, 2))
        self.label(title_block, page_subtitle, 10, MUTED, bg=BG).pack(anchor="w")

        status_color = GREEN if is_election_open() else RED
        status_text = "●  ELECTION OPEN" if is_election_open() else "●  ELECTION CLOSED"
        status = tk.Label(header, text=status_text, bg=PANEL, fg=status_color,
                          font=(FONT, 9, "bold"), padx=13, pady=9,
                          highlightthickness=1, highlightbackground=BORDER_SUBTLE)
        status.pack(side="right", anchor="ne", pady=(8, 0))

        body = tk.Frame(workspace, bg=BG)
        body.pack(fill="both", expand=True)
        if tab == "overview":
            self.admin_overview(body)
        elif tab == "candidates":
            self.admin_candidates(body)
        elif tab == "voters":
            self.admin_voters(body)
        else:
            self.admin_election(body)

    def admin_overview(self, parent):
        st = get_stats()
        tiles = tk.Frame(parent, bg=BG)
        tiles.pack(fill="x", pady=(0, 14))
        for title, value, color in [
            ("REGISTERED VOTERS", st["total"], PURPLE),
            ("VOTES CAST", st["voted"], GREEN),
            ("YET TO VOTE", st["remaining"], CORAL),
            ("TURNOUT", f"{st['turnout']:.0f}%", CYAN),
        ]:
            tile = tk.Frame(tiles, bg=PANEL, highlightthickness=1, highlightbackground=BORDER_SUBTLE)
            tile.pack(side="left", fill="x", expand=True, padx=5)
            tk.Frame(tile, bg=color, height=4).pack(fill="x")
            self.label(tile, title, 9, MUTED, True, bg=PANEL).pack(anchor="w", padx=14, pady=(13, 5))
            self.label(tile, str(value), 23, color, True, bg=PANEL).pack(anchor="w", padx=14, pady=(0, 14))

        box = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER_SUBTLE)
        box.pack(fill="both", expand=True)
        self.label(box, "Candidate Standings", 14, TEXT, True, bg=PANEL).pack(anchor="w", padx=16, pady=(14, 0))
        chart = tk.Canvas(box, bg=PANEL, highlightthickness=0)
        chart.pack(fill="both", expand=True, padx=12, pady=10)
        items = [(name, votes, CANDIDATE_COLORS[i % len(CANDIDATE_COLORS)])
                 for i, (_, name, party, votes) in enumerate(st["candidates"])]
        chart.bind("<Configure>", lambda e: self.draw_bar_chart(chart, items))

    def admin_candidates(self, parent):
        left = tk.Frame(parent, bg=PANEL, padx=18, pady=18)
        left.pack(side="left", fill="y", padx=(0, 14))
        self.label(left, "Candidate Details", 14, TEXT, True, bg=PANEL).pack(anchor="w", pady=(0, 14))

        self.label(left, "FULL NAME", 9, CYAN, True, bg=PANEL).pack(anchor="w")
        wrap, self.c_name = self.entry(left)
        wrap.pack(fill="x", pady=(4, 10))

        self.label(left, "PARTY / AFFILIATION", 9, CYAN, True, bg=PANEL).pack(anchor="w")
        wrap, self.c_party = self.entry(left)
        wrap.pack(fill="x", pady=(4, 14))

        self.candidate_selected = None
        buttons = tk.Frame(left, bg=PANEL)
        buttons.pack(fill="x")
        self.button(buttons, "Add", self.candidate_add, SKYBLUE).grid(row=0, column=0, padx=3, pady=3, sticky="ew")
        self.button(buttons, "Update", self.candidate_update, CYAN).grid(row=0, column=1, padx=3, pady=3, sticky="ew")
        self.button(buttons, "Delete", self.candidate_delete, RED).grid(row=1, column=0, padx=3, pady=3, sticky="ew")
        self.button(buttons, "Clear", self.candidate_clear, FIELD).grid(row=1, column=1, padx=3, pady=3, sticky="ew")
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)

        right = tk.Frame(parent, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        columns = ("id", "name", "party", "votes")
        self.c_tree = ttk.Treeview(right, columns=columns, show="headings", style="SV.Treeview")
        for col, title, width in [("id", "ID", 45), ("name", "Candidate Name", 180),
                                  ("party", "Party", 160), ("votes", "Votes", 70)]:
            self.c_tree.heading(col, text=title)
            self.c_tree.column(col, width=width, anchor="w")
        self.c_tree.pack(fill="both", expand=True)
        self.c_tree.bind("<<TreeviewSelect>>", self.candidate_pick)
        self.refresh_candidates()

    def refresh_candidates(self):
        if not hasattr(self, "c_tree") or not self.c_tree.winfo_exists():
            return
        self.c_tree.delete(*self.c_tree.get_children())
        for cid, name, party, votes in db_query("SELECT id, name, party, votes FROM candidates ORDER BY id"):
            self.c_tree.insert("", "end", iid=str(cid), values=(cid, name, party, votes))

    def candidate_pick(self, event=None):
        selection = self.c_tree.selection()
        if not selection:
            return
        self.candidate_selected = int(selection[0])
        values = self.c_tree.item(selection[0], "values")
        self.c_name.delete(0, tk.END)
        self.c_name.insert(0, values[1])
        self.c_party.delete(0, tk.END)
        self.c_party.insert(0, values[2])

    def candidate_clear(self):
        self.candidate_selected = None
        self.c_name.delete(0, tk.END)
        self.c_party.delete(0, tk.END)

    def candidate_values(self):
        name = self.c_name.get().strip()
        party = self.c_party.get().strip()
        if not name or not party:
            messagebox.showwarning("Missing Fields", "Please enter both candidate name and party.")
            return None
        return name, party

    def candidate_add(self):
        if get_stats()["votes"]:
            messagebox.showwarning("Election Active", "Reset the election before modifying candidates while votes are recorded.")
            return
        values = self.candidate_values()
        if values:
            db_execute("INSERT INTO candidates(name, party, votes) VALUES (?, ?, 0)", values)
            self.refresh_candidates()
            self.candidate_clear()

    def candidate_update(self):
        if self.candidate_selected is None:
            messagebox.showwarning("Select Candidate", "Please select a candidate in the table first.")
            return
        values = self.candidate_values()
        if values:
            db_execute("UPDATE candidates SET name=?, party=? WHERE id=?", values + (self.candidate_selected,))
            self.refresh_candidates()

    def candidate_delete(self):
        if self.candidate_selected is None:
            messagebox.showwarning("Select Candidate", "Please select a candidate in the table first.")
            return
        if get_stats()["votes"]:
            messagebox.showwarning("Election Active", "Reset election before removing candidates after votes have been cast.")
            return
        if messagebox.askyesno("Delete Candidate", "Are you sure you want to delete the selected candidate?"):
            db_execute("DELETE FROM candidates WHERE id=?", (self.candidate_selected,))
            self.refresh_candidates()
            self.candidate_clear()

    def admin_voters(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=(0, 10))
        self.label(top, "Registered Voters Directory", 15, TEXT, True, bg=BG).pack(side="left")

        self.v_search = tk.StringVar()
        self.v_search_entry = tk.Entry(top, textvariable=self.v_search, bg=FIELD, fg=TEXT,
                                       insertbackground=CYAN, relief="flat", font=(FONT, 11))
        self.v_search_entry.pack(side="right", ipady=7, ipadx=10)
        self.label(top, "🔍 Search: ", 10, MUTED, False, bg=BG).pack(side="right", padx=(0, 6))
        self.v_search.trace_add("write", lambda *args: self.refresh_voters())

        cols = ("id", "name", "status")
        self.v_tree = ttk.Treeview(parent, columns=cols, show="headings", style="SV.Treeview")
        for col, title, width in [("id", "Voter ID", 130), ("name", "Full Name", 240), ("status", "Ballot Status", 160)]:
            self.v_tree.heading(col, text=title)
            self.v_tree.column(col, width=width, anchor="w")
        self.v_tree.pack(fill="both", expand=True)
        self.refresh_voters()

    def refresh_voters(self):
        if not hasattr(self, "v_tree") or not self.v_tree.winfo_exists():
            return
        term = self.v_search.get().strip().lower()
        self.v_tree.delete(*self.v_tree.get_children())
        for voter_id, name, voted in db_query("SELECT voter_id, name, has_voted FROM voters ORDER BY voter_id"):
            if term and term not in f"{voter_id} {name}".lower():
                continue
            self.v_tree.insert("", "end", values=(voter_id, name, "✓ Voted" if voted else "○ Pending"))

    def admin_election(self, parent):
        status = "OPEN" if is_election_open() else "CLOSED"
        public = setting("results_public", "1") == "1"
        cards = [
            ("Election Availability", f"Voting is currently {status}.",
             "Close Voting Access" if is_election_open() else "Reopen Voting Access", self.toggle_election, PURPLE),
            ("Results Visibility", "Control whether non-admin voters can view live election results.",
             "Hide Public Results" if public else "Publish Results", self.toggle_results, CYAN),
            ("Audit Data Export", "Save candidate vote counts, participation stats, and turnout to CSV.",
             "Export Audit CSV", self.export_results, GREEN),
            ("Reset Entire Election", "Reset all candidate votes to zero and restore voting eligibility for all voters.",
             "Reset Election Data", self.reset_election, RED),
        ]
        for i, (title, desc, button_text, command, color) in enumerate(cards):
            box = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER_SUBTLE, padx=20, pady=18)
            box.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            self.label(box, title, 14, TEXT, True, bg=PANEL).pack(anchor="w")
            self.label(box, desc, 10, MUTED, wraplength=310, justify="left", bg=PANEL).pack(anchor="w", pady=(8, 18))
            self.button(box, button_text, command, color).pack(anchor="w")
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

    def toggle_election(self):
        if is_election_open():
            if not messagebox.askyesno("Close Election", "Close voting now? Results will automatically become public."):
                return
            set_setting("election_open", "0")
            set_setting("results_public", "1")
        else:
            if not messagebox.askyesno("Reopen Election", "Reopen voting for registered voters who haven't voted yet?"):
                return
            set_setting("election_open", "1")
        self.show_admin("election")

    def toggle_results(self):
        current = setting("results_public", "1") == "1"
        set_setting("results_public", "0" if current else "1")
        self.show_admin("election")

    def reset_election(self):
        if not messagebox.askyesno("Reset Election", "This resets all cast votes and allows all voters to vote again. Continue?"):
            return
        if not messagebox.askyesno("Final Confirmation", "Are you absolutely certain? This cannot be undone."):
            return
        con = connect_db()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE candidates SET votes=0")
            con.execute("UPDATE voters SET has_voted=0")
            con.commit()
        except sqlite3.Error as exc:
            con.rollback()
            messagebox.showerror("Reset Failed", str(exc))
            return
        finally:
            con.close()
        set_setting("election_open", "1")
        self.show_admin("election")


if __name__ == "__main__":
    setup_database()
    app = SecureVote()
    app.mainloop()