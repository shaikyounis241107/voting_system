"""
SecureVote - Online Voting System  (v3)
Tkinter + SQLite + matplotlib + Pillow
  Voter login: V001..V005 / 1234          Admin login: admin / admin123
"""
import tkinter as tk
from tkinter import ttk, filedialog
import sqlite3
import csv
import random
import time
import uuid

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageTk
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

DB = "voting.db"
OTP_LIFE = 120            # OTP valid for 120 seconds

# ---------- NEON AURORA THEME ----------
FONT = "Avenir Next"      # falls back automatically if missing
BG0 = "#060818"
CARD = "#0c1030"
FIELD = "#141a45"
BORDER = "#2a3170"
TEXT = "#f5f7ff"
MUTED = "#9aa3d4"
VIOLET = "#8b5cf6"
PINK = "#ec4899"
CYAN = "#22d3ee"
AMBER = "#fbbf24"
MINT = "#34d399"
DANGER = "#fb7185"
CAND_COLORS = ["#8b5cf6", "#22d3ee", "#ec4899", "#fbbf24", "#34d399", "#f97316"]
STEPS = ["Voter Login", "OTP Verification", "Cast Your Vote"]

# typography scale (keeps every screen consistent)
H1 = (FONT, 30, "bold")
H2 = (FONT, 16, "bold")
BODY = (FONT, 13)
SMALL = (FONT, 11)
CAPTION = (FONT, 10, "bold")

CARD_W, CARD_H = 940, 600
HERO_W = 340


# ---------- COLOUR / IMAGE HELPERS ----------
def hex2rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def blend(c1, c2, t):
    a, b = hex2rgb(c1), hex2rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lighten(c, t=0.18):
    return blend(c, "#ffffff", t)


def gradient_img(w, h, stops, diag=0.5):
    """Linear gradient. diag: 0 = left-to-right, 1 = top-to-bottom."""
    x = np.linspace(0, 1, w)[None, :]
    y = np.linspace(0, 1, h)[:, None]
    t = np.clip(x * (1 - diag) + y * diag, 0, 1)
    pos = np.linspace(0, 1, len(stops))
    cols = np.array([hex2rgb(c) for c in stops], float)
    arr = np.stack([np.interp(t, pos, cols[:, k]) for k in range(3)], axis=-1)
    return Image.fromarray(arr.astype("uint8"), "RGB")


def make_background(w, h):
    """Dark aurora glow with tiny stars."""
    s = 4
    sw, sh = max(w // s, 1), max(h // s, 1)
    img = Image.new("RGB", (sw, sh), hex2rgb(BG0))
    d = ImageDraw.Draw(img)
    blobs = [(0.04, 0.06, 0.20, "#4c1d95"), (0.97, 0.12, 0.17, "#0e7490"),
             (0.88, 1.00, 0.22, "#9d174d"), (0.00, 0.98, 0.18, "#1e40af"),
             (0.50, 0.50, 0.12, "#1e1b4b")]
    for fx, fy, fr, c in blobs:
        r = fr * max(sw, sh)
        d.ellipse([fx * sw - r, fy * sh - r, fx * sw + r, fy * sh + r],
                  fill=hex2rgb(c))
    img = img.filter(ImageFilter.GaussianBlur(max(sw * 0.09, 1)))
    img = img.resize((w, h), Image.BICUBIC)
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)
    for _ in range(110):
        x, y = rnd.randrange(w), rnd.randrange(h)
        b = rnd.randint(130, 235)
        size = rnd.choice([1, 1, 2])
        d.ellipse([x, y, x + size, y + size], fill=(b, b, 255))
    return img


def make_hero(w, h):
    """Left hero panel: gradient with soft glowing circles."""
    base = gradient_img(w, h, ["#4c1d95", "#be185d", "#1e1b4b"], diag=0.85)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for cx, cy, r, col in [(w * 0.95, h * 0.05, 130, (236, 72, 153, 70)),
                           (w * 0.0, h * 0.70, 170, (34, 211, 238, 55)),
                           (w * 0.9, h * 1.0, 150, (251, 191, 36, 50))]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    overlay = overlay.filter(ImageFilter.GaussianBlur(18))
    base = base.convert("RGBA")
    base.alpha_composite(overlay)
    return base.convert("RGB")


def button_image(w, h, stops, bg):
    grad = gradient_img(w, h, list(stops), diag=0.0)
    mask = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * 3 - 1, h * 3 - 1],
                                           radius=16 * 3, fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    base = Image.new("RGB", (w, h), hex2rgb(bg))
    base.paste(grad, (0, 0), mask)
    return base


def paint_gradient_bar(canvas, w, h, stops):
    steps = 64
    n = len(stops) - 1
    for i in range(steps):
        t = i / (steps - 1)
        seg = min(int(t * n), n - 1)
        col = blend(stops[seg], stops[seg + 1], t * n - seg)
        x0, x1 = int(w * i / steps), int(w * (i + 1) / steps) + 1
        canvas.create_rectangle(x0, 0, x1, h, fill=col, outline=col, tags="deco")


# ---------- DATABASE ----------
def get_db():
    return sqlite3.connect(DB)


def q(sql, args=()):
    con = get_db()
    rows = con.execute(sql, args).fetchall()
    con.close()
    return rows


def ex(sql, args=()):
    con = get_db()
    con.execute(sql, args)
    con.commit()
    con.close()


def get_setting(key, default=""):
    rows = q("SELECT value FROM settings WHERE key=?", (key,))
    return rows[0][0] if rows else default


def set_setting(key, value):
    ex("INSERT INTO settings (key, value) VALUES (?, ?) "
       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def setup_database():
    con = get_db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS voters (
                    voter_id TEXT PRIMARY KEY,
                    name TEXT,
                    password TEXT,
                    has_voted INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    party TEXT,
                    votes INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT)""")
    cur.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", [
        ("election_open", "1"), ("results_public", "1"), ("admin_password", "admin123")])
    if cur.execute("SELECT COUNT(*) FROM voters").fetchone()[0] == 0:
        cur.executemany("INSERT INTO voters VALUES (?, ?, ?, 0)", [
            ("V001", "Younis", "1234"),
            ("V002", "Arjun", "1234"),
            ("V003", "Fatima", "1234"),
            ("V004", "Ravi", "1234"),
            ("V005", "Sneha", "1234"),
        ])
    if cur.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 0:
        cur.executemany("INSERT INTO candidates (name, party) VALUES (?, ?)", [
            ("Alice Rao", "Unity Party"),
            ("Bilal Khan", "Progress Party"),
            ("Chitra Devi", "Green Party"),
        ])
    con.commit()
    con.close()


def election_open():
    return get_setting("election_open", "1") == "1"


def election_stats():
    total = q("SELECT COUNT(*) FROM voters")[0][0]
    voted = q("SELECT COUNT(*) FROM voters WHERE has_voted=1")[0][0]
    cands = q("SELECT id, name, party, votes FROM candidates ORDER BY id")
    return dict(total=total, voted=voted, remaining=total - voted,
                turnout=(100.0 * voted / total if total else 0.0),
                votes=sum(c[3] for c in cands), cands=cands)


# ---------- CUSTOM WIDGETS ----------
class GradButton(tk.Canvas):
    """Rounded gradient button (drawn as an image so it looks the same on macOS)."""

    def __init__(self, master, text, command, width=500, height=50,
                 stops=(VIOLET, PINK), bg=CARD, size=14):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, cursor="hand2")
        self._cmd = command
        self._normal = ImageTk.PhotoImage(button_image(width, height, stops, bg))
        self._hover = ImageTk.PhotoImage(
            button_image(width, height, [lighten(c) for c in stops], bg))
        self._img = self.create_image(0, 0, image=self._normal, anchor="nw")
        self.create_text(width // 2, height // 2, text=text, fill="white",
                         font=(FONT, size, "bold"))
        self.bind("<Enter>", lambda e: self.itemconfig(self._img, image=self._hover))
        self.bind("<Leave>", lambda e: self.itemconfig(self._img, image=self._normal))
        self.bind("<Button-1>", lambda e: self._cmd())


class ScrollFrame(tk.Frame):
    """A vertically scrollable frame (mouse-wheel aware)."""

    def __init__(self, master, bg=CARD):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, event):
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")


class Dialog(tk.Toplevel):
    """Styled modal dialog used instead of the plain system message boxes."""

    def __init__(self, app, title, heading, message, confirm_text="OK",
                 cancel_text=None, color=VIOLET, icon="!", candidate=None,
                 require_text=None):
        super().__init__(app, bg=color)
        self.result = False
        self.require_text = require_text
        self.title(title)
        self.resizable(False, False)
        self.transient(app)

        outer = tk.Frame(self, bg=CARD)
        outer.pack(padx=2, pady=2)
        body = tk.Frame(outer, bg=CARD)
        body.pack(padx=40, pady=30)

        if candidate:
            name, party, ccolor = candidate
            av = tk.Canvas(body, width=92, height=92, bg=CARD, highlightthickness=0)
            av.create_oval(2, 2, 90, 90, outline=ccolor, width=3)
            av.create_oval(10, 10, 82, 82, fill=ccolor, outline="")
            av.create_text(46, 46, text=name[0], fill="white", font=(FONT, 34, "bold"))
            av.pack()
        else:
            av = tk.Canvas(body, width=76, height=76, bg=CARD, highlightthickness=0)
            av.create_oval(2, 2, 74, 74, outline=color, width=3)
            av.create_text(38, 38, text=icon, fill=color, font=(FONT, 32, "bold"))
            av.pack()

        tk.Label(body, text=heading, fg=TEXT, bg=CARD,
                 font=(FONT, 20, "bold")).pack(pady=(14, 2))
        if candidate:
            tk.Label(body, text=candidate[0], fg=candidate[2], bg=CARD,
                     font=(FONT, 18, "bold")).pack()
            tk.Label(body, text=candidate[1], fg=MUTED, bg=CARD, font=BODY).pack()
        tk.Label(body, text=message, fg=MUTED, bg=CARD, font=BODY, wraplength=380,
                 justify="center").pack(pady=(10, 8))

        self.entry = None
        self.err = tk.Label(body, text="", fg=DANGER, bg=CARD, font=SMALL)
        if require_text:
            wrap = tk.Frame(body, bg=FIELD, highlightthickness=2, highlightbackground=BORDER)
            self.entry = tk.Entry(wrap, bg=FIELD, fg=TEXT, insertbackground=CYAN,
                                  relief="flat", bd=0, highlightthickness=0,
                                  font=(FONT, 16), justify="center", width=14)
            self.entry.pack(padx=12, pady=8)
            wrap.pack(pady=(4, 2))
            self.err.pack()

        row = tk.Frame(body, bg=CARD)
        row.pack(pady=(14, 0))
        if cancel_text:
            GradButton(row, cancel_text, self.cancel, width=150, height=44,
                       stops=(FIELD, "#1f2866")).pack(side="left", padx=(0, 12))
        GradButton(row, confirm_text, self.confirm, width=170, height=44,
                   stops=(color, PINK if color == VIOLET else lighten(color, 0.25))
                   ).pack(side="left")

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())
        self.bind("<Return>", lambda e: self.confirm())

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = app.winfo_rootx() + (app.winfo_width() - w) // 2
        y = app.winfo_rooty() + (app.winfo_height() - h) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        (self.entry or self).focus_force()

    def confirm(self):
        if self.require_text and self.entry.get().strip().upper() != self.require_text:
            self.err.config(text=f"Type {self.require_text} to continue.")
            return
        self.result = True
        self.destroy()

    def cancel(self):
        self.result = False
        self.destroy()


def make_entry(parent, show="", size=14, var=None):
    wrap = tk.Frame(parent, bg=FIELD, highlightthickness=2, highlightbackground=BORDER)
    entry = tk.Entry(wrap, bg=FIELD, fg=TEXT, insertbackground=CYAN, relief="flat",
                     bd=0, highlightthickness=0, font=(FONT, size), show=show,
                     textvariable=var)
    entry.pack(fill="x", padx=14, pady=10)
    entry.bind("<FocusIn>", lambda e: wrap.config(highlightbackground=VIOLET))
    entry.bind("<FocusOut>", lambda e: wrap.config(highlightbackground=BORDER))
    return wrap, entry


def caption(parent, text, pady=(10, 4)):
    tk.Label(parent, text=text, fg=CYAN, bg=CARD, font=CAPTION).pack(anchor="w", pady=pady)


def chip(parent, text, color, bg=FIELD):
    return tk.Label(parent, text=text, fg=color, bg=bg, font=(FONT, 10, "bold"),
                    padx=12, pady=5)


def make_tree(parent, columns, headings, widths):
    frame = tk.Frame(parent, bg=CARD)
    tree = ttk.Treeview(frame, columns=columns, show="headings", style="Neon.Treeview",
                        selectmode="browse")
    for col, head, wd in zip(columns, headings, widths):
        tree.heading(col, text=head)
        tree.column(col, width=wd, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview,
                        style="Neon.Vertical.TScrollbar")
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return frame, tree


def draw_hbars(c, items, w, h, maximum):
    c.delete("all")
    if not items:
        c.create_text(w / 2, h / 2, text="No data yet", fill=MUTED, font=BODY)
        return
    maximum = max(maximum, 1)
    row = (h - 10) / len(items)
    label_w = 120
    for i, (label, val, color) in enumerate(items):
        y = 8 + row * i + row / 2
        c.create_text(6, y, text=label[:15], fill=TEXT, anchor="w", font=SMALL)
        c.create_rectangle(label_w, y - 9, w - 46, y + 9, fill=FIELD, outline="")
        end = label_w + (w - 46 - label_w) * val / maximum
        if val > 0:
            c.create_rectangle(label_w, y - 9, end, y + 9, fill=color, outline="")
        c.create_text(w - 6, y, text=str(val), fill=TEXT, anchor="e", font=(FONT, 11, "bold"))


# ---------- APP ----------
class VotingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SecureVote - Online Voting System")
        self.geometry("1100x720")
        self.minsize(1000, 680)
        self.configure(bg=BG0)

        self.current_voter = None
        self.otp = None
        self.otp_time = 0
        self.attempts = 0
        self.after_id = None
        self.fx_id = None
        self.flash_job = None
        self.res_win = None
        self.is_admin = False
        self.login_mode = "voter"
        self.admin_msg = None
        self._resize_job = None
        self._bg_photo = None

        self.setup_styles()
        self.bg = tk.Canvas(self, highlightthickness=0, bg=BG0)
        self.bg.pack(fill="both", expand=True)

        # glowing gradient border behind the card
        self._border_photo = ImageTk.PhotoImage(
            gradient_img(CARD_W + 6, CARD_H + 6, [VIOLET, PINK, CYAN], diag=0.5))
        self.border_id = self.bg.create_image(550, 360, image=self._border_photo)

        self.card = tk.Frame(self.bg, bg=CARD)
        self.card.pack_propagate(False)
        self.card_id = self.bg.create_window(550, 360, window=self.card,
                                             width=CARD_W, height=CARD_H)

        self.hero_photo = ImageTk.PhotoImage(make_hero(HERO_W, CARD_H))
        self.bg.bind("<Configure>", self.on_resize)
        self.show_login()

    def setup_styles(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("Neon.Treeview", background=FIELD, fieldbackground=FIELD,
                     foreground=TEXT, rowheight=32, borderwidth=0, font=(FONT, 11))
        st.configure("Neon.Treeview.Heading", background="#241a5e", foreground="white",
                     relief="flat", font=(FONT, 11, "bold"), padding=8)
        st.map("Neon.Treeview", background=[("selected", VIOLET)],
               foreground=[("selected", "white")])
        st.map("Neon.Treeview.Heading", background=[("active", "#33257f")])
        st.configure("Neon.Vertical.TScrollbar", background=BORDER, troughcolor=CARD,
                     bordercolor=CARD, arrowcolor=TEXT, relief="flat")

    # ----- Background -----
    def on_resize(self, event=None):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, self.draw_background)

    def draw_background(self):
        self._resize_job = None
        w, h = self.bg.winfo_width(), self.bg.winfo_height()
        if w < 50 or h < 50:
            return
        self.bg.delete("deco")
        self._bg_photo = ImageTk.PhotoImage(make_background(w, h))
        self.bg.create_image(0, 0, image=self._bg_photo, anchor="nw", tags="deco")
        self.bg.tag_lower("deco")
        self.bg.coords(self.card_id, w / 2, h / 2)
        self.bg.coords(self.border_id, w / 2, h / 2)

    # ----- Dialog helpers -----
    def ask(self, title, heading, message, confirm="Confirm", cancel="Cancel",
            color=VIOLET, icon="!", candidate=None, require_text=None):
        dlg = Dialog(self, title, heading, message, confirm, cancel, color, icon,
                     candidate, require_text)
        self.wait_window(dlg)
        return dlg.result

    def notify(self, heading, message, color=AMBER, icon="!"):
        self.ask(heading, heading, message, "OK", None, color, icon)

    # ----- Layout helpers -----
    def clear(self):
        for attr in ("after_id", "fx_id", "flash_job"):
            job = getattr(self, attr)
            if job:
                self.after_cancel(job)
                setattr(self, attr, None)
        self.unbind("<Return>")
        self.unbind_all("<MouseWheel>")
        self.admin_msg = None
        for widget in self.card.winfo_children():
            widget.destroy()

    def build_shell(self, step):
        self.clear()
        hero = tk.Canvas(self.card, width=HERO_W, height=CARD_H,
                         highlightthickness=0, bg="#4c1d95")
        hero.pack(side="left")
        hero.create_image(0, 0, image=self.hero_photo, anchor="nw")

        cx, y = 60, 52
        hero.create_polygon(cx - 28, y, cx + 28, y, cx + 28, y + 32, cx, y + 60,
                            cx - 28, y + 32, fill="white", outline="")
        hero.create_text(cx, y + 26, text="✓", fill=VIOLET, font=(FONT, 26, "bold"))
        hero.create_text(32, 142, text="SecureVote", fill="white", anchor="w",
                         font=(FONT, 30, "bold"))
        hero.create_text(32, 182, text="Your voice. Verified. Counted.", fill="#f5d0fe",
                         anchor="w", font=BODY)

        top, gap = 262, 66
        for i, label in enumerate(STEPS):
            cy = top + i * gap
            if i < len(STEPS) - 1:
                hero.create_line(48, cy + 17, 48, cy + gap - 17,
                                 fill=("#a7f3d0" if i < step else "#c084fc"), width=2)
            if i < step:
                hero.create_oval(32, cy - 16, 64, cy + 16, fill=MINT, outline="")
                hero.create_text(48, cy, text="✓", fill="white", font=(FONT, 14, "bold"))
                color, fnt = "white", (FONT, 14)
            elif i == step:
                hero.create_oval(28, cy - 20, 68, cy + 20, outline="white", width=2)
                hero.create_oval(34, cy - 14, 62, cy + 14, fill="white", outline="")
                hero.create_text(48, cy, text=str(i + 1), fill=VIOLET, font=(FONT, 14, "bold"))
                color, fnt = "white", (FONT, 15, "bold")
            else:
                hero.create_oval(32, cy - 16, 64, cy + 16, outline="#c084fc", width=2)
                hero.create_text(48, cy, text=str(i + 1), fill="#e9d5ff", font=(FONT, 13))
                color, fnt = "#e9d5ff", (FONT, 14)
            hero.create_text(82, cy, text=label, fill=color, anchor="w", font=fnt)

        hero.create_text(32, CARD_H - 34, text="OTP verified   •   One person, one vote",
                         fill="#e9d5ff", anchor="w", font=SMALL)

        right = tk.Frame(self.card, bg=CARD)
        right.pack(side="left", fill="both", expand=True, padx=48, pady=34)
        return right

    def make_msg(self, parent, side="top"):
        self.msg = tk.Label(parent, text="", bg=CARD, fg=DANGER, font=(FONT, 12), anchor="w")
        self.msg.pack(fill="x", side=side)

    def set_msg(self, text, color=DANGER):
        self.msg.config(text=text, fg=color)

    def can_view_results(self):
        return self.is_admin or get_setting("results_public", "1") == "1" or not election_open()

    # =============== LOGIN (voter + admin) ===============
    def show_login(self, mode=None):
        if mode:
            self.login_mode = mode
        self.current_voter = None
        self.otp = None
        self.is_admin = False
        admin = self.login_mode == "admin"
        right = self.build_shell(0)

        is_open = election_open()
        chip(right, "●  ELECTION OPEN" if is_open else "●  ELECTION CLOSED",
             MINT if is_open else DANGER).pack(anchor="w")

        seg = tk.Frame(right, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        seg.pack(fill="x", pady=(14, 16))
        for key, label in (("voter", "Voter"), ("admin", "Admin")):
            active = key == self.login_mode
            lbl = tk.Label(seg, text=label, cursor="hand2", pady=8,
                           font=(FONT, 12, "bold"), bg=VIOLET if active else FIELD,
                           fg="white" if active else MUTED)
            lbl.pack(side="left", expand=True, fill="x")
            lbl.bind("<Button-1>", lambda e, k=key: self.show_login(k))

        tk.Label(right, text="Admin sign in" if admin else "Welcome back", font=H1,
                 fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(right, text="Manage candidates, voters and the election" if admin
                 else "Log in with your Voter ID to cast your vote",
                 fg=MUTED, bg=CARD, font=BODY).pack(anchor="w", pady=(2, 16))

        tk.Label(right, text="USERNAME" if admin else "VOTER ID", fg=CYAN, bg=CARD,
                 font=CAPTION).pack(anchor="w")
        wrap, self.id_entry = make_entry(right)
        wrap.pack(fill="x", pady=(4, 12))

        hdr = tk.Frame(right, bg=CARD)
        hdr.pack(fill="x")
        tk.Label(hdr, text="PASSWORD", fg=CYAN, bg=CARD, font=CAPTION).pack(side="left")
        show_lbl = tk.Label(hdr, text="Show", fg=MUTED, bg=CARD, cursor="hand2", font=SMALL)
        show_lbl.pack(side="right")
        wrap, self.pw_entry = make_entry(right, show="*")
        wrap.pack(fill="x", pady=(4, 4))

        def toggle_pw(event=None):
            hidden = self.pw_entry.cget("show") == "*"
            self.pw_entry.config(show="" if hidden else "*")
            show_lbl.config(text="Hide" if hidden else "Show")
        show_lbl.bind("<Button-1>", toggle_pw)

        self.make_msg(right)
        GradButton(right, "Sign in  →", self.check_login,
                   stops=(CYAN, VIOLET) if admin else (VIOLET, PINK)).pack(pady=(6, 12))

        if not admin and self.can_view_results():
            link = tk.Label(right, text="View election results", fg=PINK, bg=CARD,
                            cursor="hand2", font=(FONT, 12, "underline"))
            link.pack(anchor="w")
            link.bind("<Button-1>", lambda e: self.show_results())

        tk.Label(right, text="Demo admin:  admin / admin123" if admin
                 else "Demo voters: V001 to V005   |   Password: 1234",
                 fg=MUTED, bg=CARD, font=SMALL).pack(side="bottom", anchor="w")

        self.bind("<Return>", lambda e: self.check_login())
        self.id_entry.focus_set()

    def check_login(self):
        ident = self.id_entry.get().strip()
        password = self.pw_entry.get().strip()

        if self.login_mode == "admin":
            if ident.lower() == "admin" and password == get_setting("admin_password"):
                self.is_admin = True
                self.show_admin()
            else:
                self.set_msg("Wrong admin username or password.")
            return

        rows = q("SELECT voter_id, name, password, has_voted FROM voters WHERE voter_id=?",
                 (ident,))
        row = rows[0] if rows else None
        if row is None or row[2] != password:
            self.set_msg("Wrong Voter ID or password.")
            return
        if not election_open():
            self.set_msg("The election is closed. Voting is not available.")
            return
        if row[3] == 1:
            self.set_msg("You have already cast your vote.")
            return

        self.current_voter = (row[0], row[1])
        self.new_otp()
        self.show_otp()

    def new_otp(self):
        self.otp = str(random.randint(100000, 999999))
        self.otp_time = time.time()
        self.attempts = 0

    # =============== OTP ===============
    def show_otp(self):
        right = self.build_shell(1)

        tk.Label(right, text="Verify it's you", font=H1, fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(right, text=f"Hello {self.current_voter[1]}, enter the 6-digit code",
                 fg=MUTED, bg=CARD, font=BODY).pack(anchor="w", pady=(2, 16))

        banner = tk.Frame(right, bg="#0b2a2e", highlightthickness=1, highlightbackground=MINT)
        banner.pack(fill="x", pady=(0, 20))
        tk.Label(banner, text="DEMO SMS", bg="#0b2a2e", fg=MINT,
                 font=(FONT, 9, "bold")).pack(anchor="w", padx=14, pady=(9, 0))
        self.otp_banner = tk.Label(banner, text="", bg="#0b2a2e", fg=TEXT, font=BODY,
                                   justify="left")
        self.otp_banner.pack(anchor="w", padx=14, pady=(0, 9))
        self.refresh_banner()

        row = tk.Frame(right, bg=CARD)
        row.pack(anchor="w", pady=(0, 8))
        self.otp_boxes = []
        for i in range(6):
            w = tk.Frame(row, bg=FIELD, highlightthickness=2, highlightbackground=BORDER)
            e = tk.Entry(w, width=2, justify="center", font=(FONT, 26, "bold"),
                         bg=FIELD, fg=TEXT, insertbackground=CYAN, relief="flat",
                         bd=0, highlightthickness=0)
            e.pack(padx=7, pady=9)
            w.pack(side="left", padx=(0, 10))
            e.bind("<KeyRelease>", lambda ev, i=i: self.otp_key(ev, i))
            e.bind("<BackSpace>", lambda ev, i=i: self.otp_back(i))
            e.bind("<FocusIn>", lambda ev, w=w: w.config(highlightbackground=VIOLET))
            e.bind("<FocusOut>", lambda ev, w=w: w.config(highlightbackground=BORDER))
            self.otp_boxes.append(e)

        self.countdown = tk.Label(right, text="", bg=CARD, fg=MUTED, font=(FONT, 12), anchor="w")
        self.countdown.pack(fill="x")
        self.make_msg(right)

        GradButton(right, "Verify  →", self.verify_otp,
                   stops=(CYAN, VIOLET)).pack(pady=(8, 12))

        links = tk.Frame(right, bg=CARD)
        links.pack(fill="x")
        resend = tk.Label(links, text="Resend OTP", fg=PINK, bg=CARD, cursor="hand2",
                          font=(FONT, 13, "underline"))
        resend.pack(side="left")
        resend.bind("<Button-1>", lambda e: self.resend_otp())
        back = tk.Label(links, text="Back to login", fg=MUTED, bg=CARD, cursor="hand2",
                        font=(FONT, 13, "underline"))
        back.pack(side="right")
        back.bind("<Button-1>", lambda e: self.show_login())

        self.bind("<Return>", lambda e: self.verify_otp())
        self.otp_boxes[0].focus_set()
        self.tick()

    def otp_key(self, event, i):
        if event.keysym in ("BackSpace", "Return", "Tab", "Shift_L", "Shift_R"):
            return
        digits = "".join(ch for ch in self.otp_boxes[i].get() if ch.isdigit())
        self.otp_boxes[i].delete(0, tk.END)
        if not digits:
            return
        for k, ch in enumerate(digits):
            if i + k < 6:
                self.otp_boxes[i + k].delete(0, tk.END)
                self.otp_boxes[i + k].insert(0, ch)
        self.otp_boxes[min(i + len(digits), 5)].focus_set()

    def otp_back(self, i):
        if self.otp_boxes[i].get() == "" and i > 0:
            self.otp_boxes[i - 1].delete(0, tk.END)
            self.otp_boxes[i - 1].focus_set()

    def otp_value(self):
        return "".join(e.get() for e in self.otp_boxes)

    def refresh_banner(self):
        self.otp_banner.config(
            text=f"Your verification code is  {self.otp}\n"
                 "(A real system would send this by SMS or email.)")

    def resend_otp(self):
        self.new_otp()
        self.refresh_banner()
        for e in self.otp_boxes:
            e.delete(0, tk.END)
        self.otp_boxes[0].focus_set()
        self.set_msg("A new OTP has been sent.", MINT)

    def tick(self):
        left = OTP_LIFE - int(time.time() - self.otp_time)
        if left <= 0:
            self.countdown.config(text="OTP expired. Click Resend OTP.", fg=DANGER)
        else:
            self.countdown.config(text=f"Code expires in {left // 60}:{left % 60:02d}", fg=MUTED)
        self.after_id = self.after(1000, self.tick)

    def verify_otp(self):
        if time.time() - self.otp_time > OTP_LIFE:
            self.set_msg("OTP expired. Please resend.")
            return
        if self.otp_value() == self.otp:
            self.show_candidates()
            return
        self.attempts += 1
        if self.attempts >= 3:
            self.notify("Too many attempts", "You entered a wrong OTP three times.\n"
                        "Please log in again to get a new code.", DANGER, "✕")
            self.show_login()
        else:
            self.set_msg(f"Wrong OTP. {3 - self.attempts} attempts left.")

    # =============== VOTING SCREEN ===============
    def show_candidates(self):
        right = self.build_shell(2)

        tk.Label(right, text="Choose your candidate", font=(FONT, 28, "bold"),
                 fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(right, text="Tap a card to select, then review and submit. Your vote is final.",
                 fg=MUTED, bg=CARD, font=BODY).pack(anchor="w", pady=(2, 10))

        cands = q("SELECT id, name, party FROM candidates ORDER BY id")
        self.choice = None
        self.cards = {}
        if not cands:
            tk.Label(right, text="No candidates have been added yet.\nPlease contact the "
                     "administrator.", fg=AMBER, bg=CARD, font=BODY, justify="left"
                     ).pack(anchor="w", pady=20)
            GradButton(right, "Back to login", self.show_login, stops=(FIELD, "#1f2866")).pack()
            return

        GradButton(right, "Review & Submit Vote  →", self.cast_vote,
                   stops=(PINK, VIOLET)).pack(side="bottom", pady=(6, 0))
        self.make_msg(right, side="bottom")

        sf = ScrollFrame(right)
        sf.pack(fill="both", expand=True)
        for idx, (cid, name, party) in enumerate(cands):
            color = CAND_COLORS[idx % len(CAND_COLORS)]
            card = tk.Frame(sf.inner, bg=FIELD, highlightthickness=2,
                            highlightbackground=BORDER, cursor="hand2")
            card.pack(fill="x", pady=6, padx=(0, 6))
            stripe = tk.Frame(card, bg=color, width=6)
            stripe.pack(side="left", fill="y")
            av = tk.Canvas(card, width=52, height=52, bg=FIELD, highlightthickness=0)
            av.create_oval(2, 2, 50, 50, fill=color, outline="")
            av.create_text(26, 26, text=name[0], fill="white", font=(FONT, 19, "bold"))
            av.pack(side="left", padx=14, pady=11)
            info = tk.Frame(card, bg=FIELD)
            info.pack(side="left")
            n_lbl = tk.Label(info, text=name, bg=FIELD, fg=TEXT, font=(FONT, 15, "bold"))
            n_lbl.pack(anchor="w")
            p_lbl = tk.Label(info, text=party, bg=FIELD, fg=color, font=(FONT, 12))
            p_lbl.pack(anchor="w")
            ind = tk.Canvas(card, width=28, height=28, bg=FIELD, highlightthickness=0)
            ind.pack(side="right", padx=(6, 18))
            badge = tk.Label(card, text="", bg=FIELD, fg=color, font=(FONT, 10, "bold"))
            badge.pack(side="right")

            self.cards[cid] = dict(card=card, ind=ind, badge=badge, color=color,
                                   widgets=[card, av, info, n_lbl, p_lbl, badge, ind])
            self.draw_indicator(ind, MUTED, False)
            for w in (card, stripe, av, info, n_lbl, p_lbl, badge, ind):
                w.bind("<Button-1>", lambda e, c=cid: self.select_candidate(c))

    @staticmethod
    def draw_indicator(canvas, color, selected):
        canvas.delete("all")
        canvas.create_oval(3, 3, 25, 25, outline=color, width=2)
        if selected:
            canvas.create_oval(9, 9, 19, 19, fill=color, outline=color)

    def select_candidate(self, cid):
        self.choice = cid
        for c, d in self.cards.items():
            on = c == cid
            bg = blend(FIELD, d["color"], 0.16) if on else FIELD
            for w in d["widgets"]:
                w.config(bg=bg)
            d["card"].config(highlightbackground=d["color"] if on else BORDER)
            d["badge"].config(text="SELECTED" if on else "")
            self.draw_indicator(d["ind"], d["color"] if on else MUTED, on)
        self.set_msg("")

    def cast_vote(self):
        if self.choice is None:
            self.set_msg("Please select a candidate first.")
            return
        rows = q("SELECT name, party FROM candidates WHERE id=?", (self.choice,))
        if not rows:
            self.set_msg("That candidate no longer exists. Please pick again.")
            return
        color = self.cards[self.choice]["color"]
        ok = self.ask("Confirm your vote", "Confirm your vote",
                      "You are about to cast your vote for the candidate shown above.\n"
                      "This action is final and cannot be changed.",
                      "Confirm Vote", "Go Back", color, candidate=(rows[0][0], rows[0][1], color))
        if not ok:
            return
        if not election_open():
            self.notify("Election closed", "The administrator closed the election "
                        "before your vote was submitted.", DANGER, "✕")
            self.show_login()
            return

        con = get_db()
        cur = con.cursor()
        # Only succeeds while has_voted is still 0 -> one vote per voter
        cur.execute("UPDATE voters SET has_voted=1 WHERE voter_id=? AND has_voted=0",
                    (self.current_voter[0],))
        if cur.rowcount == 0:
            con.close()
            self.notify("Already voted", "Our records show you have already voted.",
                        DANGER, "✕")
            self.show_login()
            return
        cur.execute("UPDATE candidates SET votes = votes + 1 WHERE id=?", (self.choice,))
        con.commit()
        con.close()
        self.show_done()

    # =============== THANK YOU + CONFETTI ===============
    def show_done(self):
        right = self.build_shell(3)
        name = self.current_voter[1]
        self.current_voter = None

        self.confetti = tk.Canvas(right, width=500, height=120, bg=CARD, highlightthickness=0)
        self.confetti.pack(anchor="w")
        self.confetti.create_oval(4, 14, 92, 102, fill=MINT, outline="")
        self.confetti.create_text(48, 58, text="✓", fill="white", font=(FONT, 46, "bold"))
        self.particles = []
        for _ in range(60):
            x, y = random.randint(110, 495), random.randint(-120, 0)
            size = random.randint(5, 10)
            pid = self.confetti.create_rectangle(x, y, x + size, y + size,
                                                 fill=random.choice(CAND_COLORS), outline="")
            self.particles.append([pid, random.uniform(1.5, 4), random.uniform(-1, 1)])
        self.frames = 0
        self.animate_confetti()

        tk.Label(right, text="Vote recorded!", font=H1, fg=TEXT, bg=CARD).pack(anchor="w", pady=(6, 0))
        tk.Label(right, text=f"Thank you, {name}. Your vote has been securely saved.",
                 fg=MUTED, bg=CARD, font=BODY).pack(anchor="w", pady=(2, 12))
        tk.Label(right, text=f"Confirmation code:  {uuid.uuid4().hex[:10].upper()}",
                 fg=CYAN, bg=CARD, font=(FONT, 14, "bold")).pack(anchor="w", pady=(0, 22))

        if self.can_view_results():
            GradButton(right, "View Results", self.show_results).pack(pady=(0, 10))
        GradButton(right, "Log out", self.show_login, stops=(FIELD, "#1f2866")).pack()

    def animate_confetti(self):
        if self.frames > 110:
            self.fx_id = None
            return
        for p in self.particles:
            self.confetti.move(p[0], p[2], p[1])
        self.frames += 1
        self.fx_id = self.after(30, self.animate_confetti)

    # =============== RESULTS DASHBOARD ===============
    def show_results(self):
        if not self.can_view_results():
            self.notify("Results are hidden", "The administrator has not published "
                        "the results yet.")
            return
        if self.res_win is not None and self.res_win.winfo_exists():
            self.res_win.lift()
        else:
            self.res_win = tk.Toplevel(self, bg=CARD)
            self.res_win.title("Election Results")
            self.res_win.geometry("980x730")
        self.draw_results()

    def draw_results(self):
        win = self.res_win
        for w in win.winfo_children():
            w.destroy()
        st = election_stats()
        data = st["cands"]
        names = [d[1] for d in data]
        votes = [d[3] for d in data]
        colors = [CAND_COLORS[i % len(CAND_COLORS)] for i in range(len(data))]
        total = st["votes"]
        top = max(votes) if votes else 0
        closed = not election_open()

        head = tk.Frame(win, bg=CARD)
        head.pack(fill="x", padx=30, pady=(22, 0))
        left = tk.Frame(head, bg=CARD)
        left.pack(side="left")
        tk.Label(left, text="Election Results", fg=TEXT, bg=CARD, font=(FONT, 26, "bold")
                 ).pack(anchor="w")
        chip(left, "●  FINAL RESULTS" if closed else "●  LIVE",
             AMBER if closed else MINT).pack(anchor="w", pady=(4, 0))
        GradButton(head, "Export CSV", self.export_results, width=130, height=38,
                   stops=(FIELD, "#1f2866"), bg=CARD, size=12).pack(side="right")
        GradButton(head, "Refresh", self.draw_results, width=110, height=38,
                   stops=(CYAN, VIOLET), bg=CARD, size=12).pack(side="right", padx=10)

        # winner / leader banner
        leaders = [names[i] for i in range(len(data)) if votes[i] == top] if total else []
        if not total:
            btxt, bsub, bcol = "No votes cast yet", "Results will appear as votes come in.", MUTED
        elif len(leaders) > 1:
            btxt, bsub, bcol = "It's a tie", " and ".join(leaders) + f" have {top} votes each.", AMBER
        else:
            pct = top * 100 / total
            btxt = leaders[0]
            bsub = f"{top} votes  •  {pct:.0f}% of all votes"
            bcol = AMBER
        banner = tk.Frame(win, bg=FIELD, highlightthickness=2, highlightbackground=bcol)
        banner.pack(fill="x", padx=30, pady=(14, 10))
        tk.Label(banner, text=("WINNER" if closed and len(leaders) == 1 else
                               "LEADING" if len(leaders) == 1 else "STATUS"),
                 fg=bcol, bg=FIELD, font=CAPTION).pack(anchor="w", padx=20, pady=(12, 0))
        tk.Label(banner, text=btxt, fg=TEXT, bg=FIELD, font=(FONT, 22, "bold")
                 ).pack(anchor="w", padx=20)
        tk.Label(banner, text=bsub, fg=MUTED, bg=FIELD, font=BODY
                 ).pack(anchor="w", padx=20, pady=(0, 12))

        # stat tiles
        second = sorted(votes, reverse=True)[1] if len(votes) > 1 else 0
        tiles = [("TOTAL VOTES", str(total), CYAN),
                 ("TURNOUT", f"{st['turnout']:.0f}%  ({st['voted']}/{st['total']})", MINT),
                 ("YET TO VOTE", str(st["remaining"]), AMBER),
                 ("LEAD MARGIN", str(top - second) if total else "-", PINK)]
        row = tk.Frame(win, bg=CARD)
        row.pack(fill="x", padx=24)
        for i, (cap, val, col) in enumerate(tiles):
            box = tk.Frame(row, bg=FIELD, highlightthickness=2, highlightbackground=col)
            box.grid(row=0, column=i, sticky="nsew", padx=6)
            row.grid_columnconfigure(i, weight=1, uniform="t")
            tk.Label(box, text=cap, bg=FIELD, fg=MUTED, font=CAPTION).pack(pady=(10, 0))
            tk.Label(box, text=val, bg=FIELD, fg=col, font=(FONT, 17, "bold")).pack(pady=(0, 10))

        # turnout bar
        bar = tk.Canvas(win, height=10, bg=CARD, highlightthickness=0)
        bar.pack(fill="x", padx=30, pady=(12, 0))

        def draw_bar(e, pct=st["turnout"]):
            bar.delete("all")
            bar.create_rectangle(0, 0, e.width, 10, fill=FIELD, outline="")
            if pct > 0:
                bar.create_rectangle(0, 0, e.width * pct / 100, 10, fill=CYAN, outline="")
        bar.bind("<Configure>", draw_bar)

        # charts
        fig = Figure(figsize=(9.2, 3.3), dpi=100, facecolor=CARD)
        ax1 = fig.add_subplot(121, facecolor=CARD)
        if total:
            ax1.pie(votes, colors=colors, startangle=90, counterclock=False,
                    wedgeprops=dict(width=0.34, edgecolor=CARD, linewidth=3))
        else:
            ax1.pie([1], colors=[BORDER], wedgeprops=dict(width=0.34, edgecolor=CARD))
        ax1.text(0, 0.07, str(total), ha="center", va="center", color=TEXT,
                 fontsize=28, fontweight="bold")
        ax1.text(0, -0.2, "TOTAL VOTES", ha="center", va="center", color=MUTED, fontsize=9)

        order = sorted(range(len(data)), key=lambda i: votes[i])
        ax2 = fig.add_subplot(122, facecolor=CARD)
        ax2.barh([names[i] for i in order], [votes[i] for i in order],
                 color=[colors[i] for i in order], height=0.5)
        peak = max(top, 1)
        for y, i in enumerate(order):
            pct = votes[i] * 100 / total if total else 0
            ax2.text(votes[i] + peak * 0.04, y, f"{votes[i]}  ({pct:.0f}%)",
                     va="center", color=TEXT, fontsize=10)
        ax2.set_xlim(0, peak * 1.6)
        ax2.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax2.tick_params(colors=MUTED, labelsize=10, length=0)
        for spine in ax2.spines.values():
            spine.set_visible(False)
        ax2.xaxis.grid(True, color=BORDER, linewidth=0.6)
        ax2.set_axisbelow(True)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(4, 12))

    def export_results(self):
        path = filedialog.asksaveasfilename(
            parent=self.res_win, defaultextension=".csv", initialfile="election_results.csv",
            filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        st = election_stats()
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Candidate", "Party", "Votes", "Percent"])
            for _, name, party, votes in st["cands"]:
                w.writerow([name, party, votes,
                            round(votes * 100 / st["votes"], 1) if st["votes"] else 0])
            w.writerow([])
            w.writerow(["Registered voters", st["total"]])
            w.writerow(["Votes cast", st["voted"]])
            w.writerow(["Turnout %", round(st["turnout"], 1)])

    # =============== ADMIN PANEL ===============
    TABS = [("Overview", "overview"), ("Candidates", "candidates"),
            ("Voters", "voters"), ("Election", "election")]

    def show_admin(self, tab="overview"):
        self.clear()
        self.is_admin = True
        self.admin_tab = tab

        head = tk.Frame(self.card, bg=CARD)
        head.pack(fill="x", padx=32, pady=(22, 0))
        left = tk.Frame(head, bg=CARD)
        left.pack(side="left")
        tk.Label(left, text="Admin Panel", fg=TEXT, bg=CARD, font=(FONT, 26, "bold")).pack(anchor="w")
        tk.Label(left, text="Manage candidates, voters and the election", fg=MUTED,
                 bg=CARD, font=(FONT, 12)).pack(anchor="w")
        right = tk.Frame(head, bg=CARD)
        right.pack(side="right")
        GradButton(right, "Log out", self.show_login, width=110, height=38,
                   stops=(PINK, VIOLET), size=12).pack(anchor="e")
        self.admin_msg = tk.Label(right, text="", bg=CARD, fg=MINT, font=SMALL)
        self.admin_msg.pack(anchor="e", pady=(4, 0))

        bar = tk.Canvas(self.card, height=3, bg=CARD, highlightthickness=0)
        bar.pack(fill="x", padx=32, pady=(10, 0))
        bar.bind("<Configure>", lambda e: (bar.delete("deco"),
                                           paint_gradient_bar(bar, e.width, 3, [VIOLET, PINK, CYAN])))

        tabs = tk.Frame(self.card, bg=CARD)
        tabs.pack(fill="x", padx=32, pady=(8, 0))
        for title, key in self.TABS:
            active = key == tab
            cell = tk.Frame(tabs, bg=CARD)
            cell.pack(side="left", padx=(0, 22))
            lbl = tk.Label(cell, text=title, bg=CARD, cursor="hand2",
                           fg=TEXT if active else MUTED, font=(FONT, 14, "bold" if active else "normal"))
            lbl.pack()
            tk.Frame(cell, bg=PINK if active else CARD, height=3).pack(fill="x", pady=(4, 0))
            lbl.bind("<Button-1>", lambda e, k=key: self.show_admin(k))

        self.admin_body = tk.Frame(self.card, bg=CARD)
        self.admin_body.pack(fill="both", expand=True, padx=32, pady=(12, 22))
        getattr(self, "admin_" + tab)()

    def admin_flash(self, text, color=MINT):
        if self.admin_msg is None or not self.admin_msg.winfo_exists():
            return
        self.admin_msg.config(text=text, fg=color)
        if self.flash_job:
            self.after_cancel(self.flash_job)
        self.flash_job = self.after(3500, self._admin_unflash)

    def _admin_unflash(self):
        self.flash_job = None
        if self.admin_msg is not None and self.admin_msg.winfo_exists():
            self.admin_msg.config(text="")

    def stat_tile(self, parent, col, cap, value, color):
        box = tk.Frame(parent, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        box.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
        parent.grid_columnconfigure(col, weight=1, uniform="tile")
        tk.Frame(box, bg=color, height=4).pack(fill="x")
        tk.Label(box, text=cap, fg=MUTED, bg=FIELD, font=CAPTION).pack(anchor="w", padx=16, pady=(12, 0))
        tk.Label(box, text=value, fg=color, bg=FIELD, font=(FONT, 24, "bold")
                 ).pack(anchor="w", padx=16, pady=(0, 14))

    # ----- Overview -----
    def admin_overview(self):
        st = election_stats()
        body = self.admin_body
        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x")
        self.stat_tile(row, 0, "REGISTERED VOTERS", str(st["total"]), VIOLET)
        self.stat_tile(row, 1, "VOTES CAST", str(st["voted"]), MINT)
        self.stat_tile(row, 2, "YET TO VOTE", str(st["remaining"]), AMBER)
        self.stat_tile(row, 3, "TURNOUT", f"{st['turnout']:.0f}%", CYAN)

        lower = tk.Frame(body, bg=CARD)
        lower.pack(fill="both", expand=True, pady=(14, 0))
        lower.grid_columnconfigure(0, weight=3, uniform="o")
        lower.grid_columnconfigure(1, weight=2, uniform="o")
        lower.grid_rowconfigure(0, weight=1)

        left = tk.Frame(lower, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(left, text="Votes by candidate", fg=TEXT, bg=FIELD, font=H2
                 ).pack(anchor="w", padx=18, pady=(14, 0))
        c = tk.Canvas(left, bg=FIELD, highlightthickness=0)
        c.pack(fill="both", expand=True, padx=12, pady=10)
        items = [(n, v, CAND_COLORS[i % len(CAND_COLORS)]) for i, (_, n, _, v) in enumerate(st["cands"])]
        top = max([v for _, v, _ in items], default=0)
        c.bind("<Configure>", lambda e: draw_hbars(c, items, e.width, e.height, top))

        right = tk.Frame(lower, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(right, text="Election status", fg=TEXT, bg=FIELD, font=H2
                 ).pack(anchor="w", padx=18, pady=(14, 8))
        is_open = election_open()
        chip(right, "●  OPEN" if is_open else "●  CLOSED",
             MINT if is_open else DANGER, bg=CARD).pack(anchor="w", padx=18)
        public = get_setting("results_public", "1") == "1"
        tk.Label(right, text=f"Candidates: {len(st['cands'])}\nResults public: "
                 f"{'Yes' if public else 'No'}", fg=MUTED, bg=FIELD, font=BODY, justify="left"
                 ).pack(anchor="w", padx=18, pady=12)
        GradButton(right, "Open Results Dashboard", self.show_results, width=240, height=42,
                   stops=(CYAN, VIOLET), bg=FIELD, size=12).pack(anchor="w", padx=18, pady=(0, 6))
        GradButton(right, "Manage Election", lambda: self.show_admin("election"), width=240,
                   height=42, stops=(VIOLET, PINK), bg=FIELD, size=12).pack(anchor="w", padx=18)

    # ----- Candidates -----
    def admin_candidates(self):
        body = self.admin_body
        locked = election_stats()["votes"] > 0
        form = tk.Frame(body, bg=FIELD, highlightthickness=1, highlightbackground=BORDER, width=280)
        form.pack(side="left", fill="y", padx=(0, 14))
        form.pack_propagate(False)
        inner = tk.Frame(form, bg=CARD)
        inner.pack(fill="both", expand=True, padx=18, pady=14)
        tk.Label(inner, text="Candidate details", fg=TEXT, bg=CARD, font=H2).pack(anchor="w")
        caption(inner, "FULL NAME")
        wrap, self.c_name = make_entry(inner, size=13)
        wrap.pack(fill="x")
        caption(inner, "PARTY")
        wrap, self.c_party = make_entry(inner, size=13)
        wrap.pack(fill="x")
        self.c_sel = None

        grid = tk.Frame(inner, bg=CARD)
        grid.pack(pady=(18, 0))
        for i, (txt, cmd, stops) in enumerate([
                ("Add", self.cand_add, (VIOLET, PINK)), ("Update", self.cand_update, (CYAN, VIOLET)),
                ("Delete", self.cand_delete, (PINK, "#be123c")), ("Clear", self.cand_clear, (FIELD, "#1f2866"))]):
            GradButton(grid, txt, cmd, width=100, height=38, stops=stops, size=12
                       ).grid(row=i // 2, column=i % 2, padx=4, pady=4)
        if locked:
            tk.Label(inner, text="Votes already cast: adding or\ndeleting candidates is locked.\n"
                     "Reset the election to change\nthe candidate list.", fg=AMBER, bg=CARD,
                     font=SMALL, justify="left").pack(anchor="w", pady=(12, 0))

        frame, self.c_tree = make_tree(body, ("id", "name", "party", "votes"),
                                       ["ID", "Name", "Party", "Votes"], [50, 200, 170, 70])
        frame.pack(side="left", fill="both", expand=True)
        self.c_tree.bind("<<TreeviewSelect>>", self.cand_select)
        self.cand_refresh()

    def cand_refresh(self):
        self.c_tree.delete(*self.c_tree.get_children())
        for cid, name, party, votes in q("SELECT id, name, party, votes FROM candidates ORDER BY id"):
            self.c_tree.insert("", "end", iid=str(cid), values=(cid, name, party, votes))

    def cand_select(self, event=None):
        sel = self.c_tree.selection()
        if not sel:
            return
        self.c_sel = int(sel[0])
        v = self.c_tree.item(sel[0], "values")
        self.c_name.delete(0, tk.END)
        self.c_name.insert(0, v[1])
        self.c_party.delete(0, tk.END)
        self.c_party.insert(0, v[2])

    def cand_clear(self):
        self.c_sel = None
        self.c_name.delete(0, tk.END)
        self.c_party.delete(0, tk.END)
        if self.c_tree.selection():
            self.c_tree.selection_remove(self.c_tree.selection())

    def cand_values(self):
        name, party = self.c_name.get().strip(), self.c_party.get().strip()
        if not name or not party:
            self.notify("Missing details", "Please enter both a name and a party.")
            return None
        return name, party

    def cand_add(self):
        if election_stats()["votes"] > 0:
            self.notify("Election in progress", "Votes have been cast, so candidates "
                        "can't be added. Reset the election first.", DANGER, "✕")
            return
        vals = self.cand_values()
        if vals:
            if len(q("SELECT id FROM candidates")) >= len(CAND_COLORS):
                self.notify("Limit reached", f"You can have up to {len(CAND_COLORS)} candidates.")
                return
            ex("INSERT INTO candidates (name, party) VALUES (?, ?)", vals)
            self.cand_clear()
            self.cand_refresh()
            self.admin_flash("Candidate added")

    def cand_update(self):
        if self.c_sel is None:
            self.notify("Select a candidate", "Click a candidate in the table first.")
            return
        vals = self.cand_values()
        if vals:
            ex("UPDATE candidates SET name=?, party=? WHERE id=?", vals + (self.c_sel,))
            self.cand_refresh()
            self.admin_flash("Candidate updated")

    def cand_delete(self):
        if self.c_sel is None:
            self.notify("Select a candidate", "Click a candidate in the table first.")
            return
        if election_stats()["votes"] > 0:
            self.notify("Election in progress", "Votes have been cast, so candidates "
                        "can't be deleted. Reset the election first.", DANGER, "✕")
            return
        if self.ask("Delete candidate", "Delete this candidate?", "This cannot be undone.",
                    "Delete", "Cancel", DANGER, "!"):
            ex("DELETE FROM candidates WHERE id=?", (self.c_sel,))
            self.cand_clear()
            self.cand_refresh()
            self.admin_flash("Candidate deleted", DANGER)

    # ----- Voters -----
    def admin_voters(self):
        body = self.admin_body
        form = tk.Frame(body, bg=FIELD, highlightthickness=1, highlightbackground=BORDER, width=280)
        form.pack(side="left", fill="y", padx=(0, 14))
        form.pack_propagate(False)
        inner = tk.Frame(form, bg=CARD)
        inner.pack(fill="both", expand=True, padx=18, pady=14)
        tk.Label(inner, text="Voter details", fg=TEXT, bg=CARD, font=H2).pack(anchor="w")
        self.v_sel = None
        self.v_fields = {}
        for key, label in (("id", "VOTER ID"), ("name", "FULL NAME"), ("pw", "PASSWORD")):
            caption(inner, label, pady=(8, 3))
            wrap, ent = make_entry(inner, size=13)
            wrap.pack(fill="x")
            self.v_fields[key] = ent
        grid = tk.Frame(inner, bg=CARD)
        grid.pack(pady=(14, 0))
        for i, (txt, cmd, stops) in enumerate([
                ("Add", self.voter_add, (VIOLET, PINK)), ("Update", self.voter_update, (CYAN, VIOLET)),
                ("Delete", self.voter_delete, (PINK, "#be123c")), ("Clear", self.voter_clear, (FIELD, "#1f2866"))]):
            GradButton(grid, txt, cmd, width=100, height=38, stops=stops, size=12
                       ).grid(row=i // 2, column=i % 2, padx=4, pady=4)

        right = tk.Frame(body, bg=CARD)
        right.pack(side="left", fill="both", expand=True)
        top = tk.Frame(right, bg=CARD)
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="Search", fg=CYAN, bg=CARD, font=CAPTION).pack(side="left", padx=(0, 10))
        self.v_search = tk.StringVar()
        wrap, _ = make_entry(top, size=12, var=self.v_search)
        wrap.pack(side="left", fill="x", expand=True)
        frame, self.v_tree = make_tree(right, ("id", "name", "status"),
                                       ["Voter ID", "Name", "Status"], [100, 240, 120])
        frame.pack(fill="both", expand=True)
        self.v_tree.tag_configure("voted", foreground=MINT)
        self.v_tree.tag_configure("pending", foreground=AMBER)
        self.v_tree.bind("<<TreeviewSelect>>", self.voter_select)
        self.v_search.trace_add("write", lambda *a: self.voter_refresh())
        self.voter_refresh()

    def voter_refresh(self):
        if not self.v_tree.winfo_exists():
            return
        term = self.v_search.get().strip().lower()
        self.v_tree.delete(*self.v_tree.get_children())
        for vid, name, voted in q("SELECT voter_id, name, has_voted FROM voters ORDER BY voter_id"):
            if term and term not in f"{vid} {name}".lower():
                continue
            self.v_tree.insert("", "end", iid=vid, tags=("voted" if voted else "pending",),
                               values=(vid, name, "Voted" if voted else "Pending"))

    def voter_select(self, event=None):
        sel = self.v_tree.selection()
        if not sel:
            return
        self.v_sel = sel[0]
        rows = q("SELECT voter_id, name, password FROM voters WHERE voter_id=?", (self.v_sel,))
        if not rows:
            return
        for key, val in zip(("id", "name", "pw"), rows[0]):
            self.v_fields[key].delete(0, tk.END)
            self.v_fields[key].insert(0, val)

    def voter_clear(self):
        self.v_sel = None
        for ent in self.v_fields.values():
            ent.delete(0, tk.END)
        if self.v_tree.selection():
            self.v_tree.selection_remove(self.v_tree.selection())

    def voter_values(self):
        vid = self.v_fields["id"].get().strip().upper()
        name = self.v_fields["name"].get().strip()
        pw = self.v_fields["pw"].get().strip()
        if not vid or not name or not pw:
            self.notify("Missing details", "Voter ID, name and password are all required.")
            return None
        return vid, name, pw

    def voter_add(self):
        vals = self.voter_values()
        if not vals:
            return
        try:
            ex("INSERT INTO voters (voter_id, name, password, has_voted) VALUES (?,?,?,0)", vals)
        except sqlite3.IntegrityError:
            self.notify("Duplicate ID", f"Voter ID {vals[0]} already exists.", DANGER, "✕")
            return
        self.voter_clear()
        self.voter_refresh()
        self.admin_flash("Voter added")

    def voter_update(self):
        if self.v_sel is None:
            self.notify("Select a voter", "Click a voter in the table first.")
            return
        vals = self.voter_values()
        if vals:
            ex("UPDATE voters SET name=?, password=? WHERE voter_id=?", (vals[1], vals[2], self.v_sel))
            self.voter_refresh()
            self.admin_flash("Voter updated (ID can't be changed)")

    def voter_delete(self):
        if self.v_sel is None:
            self.notify("Select a voter", "Click a voter in the table first.")
            return
        rows = q("SELECT has_voted FROM voters WHERE voter_id=?", (self.v_sel,))
        if rows and rows[0][0]:
            self.notify("Voter has voted", "A voter who has already voted can't be "
                        "deleted, as it would break the vote count.", DANGER, "✕")
            return
        if self.ask("Delete voter", "Delete this voter?", "This cannot be undone.",
                    "Delete", "Cancel", DANGER, "!"):
            ex("DELETE FROM voters WHERE voter_id=?", (self.v_sel,))
            self.voter_clear()
            self.voter_refresh()
            self.admin_flash("Voter deleted", DANGER)

    # ----- Election controls -----
    def admin_election(self):
        body = self.admin_body
        body.grid_columnconfigure(0, weight=1, uniform="e")
        body.grid_columnconfigure(1, weight=1, uniform="e")
        body.grid_rowconfigure(0, weight=1, uniform="e")
        body.grid_rowconfigure(1, weight=1, uniform="e")

        def panel(r, c, title, text, color=BORDER):
            box = tk.Frame(body, bg=FIELD, highlightthickness=2, highlightbackground=color)
            box.grid(row=r, column=c, sticky="nsew", padx=(0 if c == 0 else 8, 0 if c == 1 else 8),
                     pady=(0 if r == 0 else 8, 0 if r == 1 else 8))
            tk.Label(box, text=title, fg=TEXT, bg=FIELD, font=H2).pack(anchor="w", padx=20, pady=(16, 2))
            tk.Label(box, text=text, fg=MUTED, bg=FIELD, font=SMALL, justify="left", wraplength=330
                     ).pack(anchor="w", padx=20)
            return box

        is_open = election_open()
        box = panel(0, 0, "Voting status",
                    "Open: voters can log in and vote.\nClosed: voting stops and results become public.")
        chip(box, "●  OPEN" if is_open else "●  CLOSED", MINT if is_open else DANGER,
             bg=CARD).pack(anchor="w", padx=20, pady=10)
        GradButton(box, "Close Election" if is_open else "Reopen Election", self.toggle_election,
                   width=220, height=42, stops=(PINK, "#be123c") if is_open else (MINT, CYAN),
                   bg=FIELD, size=12).pack(anchor="w", padx=20)

        public = get_setting("results_public", "1") == "1"
        box = panel(0, 1, "Results visibility",
                    "Public: voters can see live results.\nHidden: only you can see them until the election closes.")
        chip(box, "●  PUBLIC" if public else "●  HIDDEN", MINT if public else AMBER,
             bg=CARD).pack(anchor="w", padx=20, pady=10)
        GradButton(box, "Hide Results" if public else "Publish Results", self.toggle_public,
                   width=220, height=42, stops=(CYAN, VIOLET), bg=FIELD, size=12
                   ).pack(anchor="w", padx=20)

        box = panel(1, 0, "Export", "Open the results dashboard and download the final "
                    "tally as a CSV file.")
        GradButton(box, "Open Results Dashboard", self.show_results, width=240, height=42,
                   stops=(VIOLET, PINK), bg=FIELD, size=12).pack(anchor="w", padx=20, pady=(14, 0))

        box = panel(1, 1, "Danger zone", "Reset sets every vote to zero and lets all voters "
                    "vote again. Use it before a new election.", DANGER)
        GradButton(box, "Reset Election", self.reset_election, width=220, height=42,
                   stops=(DANGER, "#be123c"), bg=FIELD, size=12).pack(anchor="w", padx=20, pady=(14, 0))

    def toggle_election(self):
        if election_open():
            if not self.ask("Close election", "Close the election?",
                            "Voters will no longer be able to vote and the results "
                            "will become public.", "Close Election", "Cancel", PINK, "!"):
                return
            set_setting("election_open", "0")
        else:
            set_setting("election_open", "1")
        self.show_admin("election")
        self.admin_flash("Election status updated")

    def toggle_public(self):
        set_setting("results_public", "0" if get_setting("results_public", "1") == "1" else "1")
        self.show_admin("election")
        self.admin_flash("Results visibility updated")

    def reset_election(self):
        if not self.ask("Reset election", "Reset the whole election?",
                        "All votes will be erased and every voter can vote again. "
                        "This cannot be undone.", "Reset", "Cancel", DANGER, "!",
                        require_text="RESET"):
            return
        con = get_db()
        con.execute("UPDATE candidates SET votes = 0")
        con.execute("UPDATE voters SET has_voted = 0")
        con.commit()
        con.close()
        set_setting("election_open", "1")
        self.show_admin("election")
        self.admin_flash("Election has been reset", AMBER)


if __name__ == "__main__":
    setup_database()
    app = VotingApp()
    app.mainloop()
