import tkinter as tk
from tkinter import messagebox
import sqlite3
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

CARD_W, CARD_H = 940, 600
HERO_W = 340


# ---------- COLOUR / IMAGE HELPERS ----------
def hex2rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def lighten(c, t=0.18):
    r, g, b = hex2rgb(c)
    return "#%02x%02x%02x" % (int(r + (255 - r) * t), int(g + (255 - g) * t),
                              int(b + (255 - b) * t))


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


# ---------- DATABASE ----------
def get_db():
    return sqlite3.connect(DB)


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


# ---------- CUSTOM WIDGETS ----------
class GradButton(tk.Canvas):
    """Rounded gradient button (drawn as an image so it looks the same on macOS)."""

    def __init__(self, master, text, command, width=500, height=50,
                 stops=(VIOLET, PINK), bg=CARD):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, cursor="hand2")
        self._cmd = command
        self._normal = ImageTk.PhotoImage(button_image(width, height, stops, bg))
        self._hover = ImageTk.PhotoImage(
            button_image(width, height, [lighten(c) for c in stops], bg))
        self._img = self.create_image(0, 0, image=self._normal, anchor="nw")
        self.create_text(width // 2, height // 2, text=text, fill="white",
                         font=(FONT, 14, "bold"))
        self.bind("<Enter>", lambda e: self.itemconfig(self._img, image=self._hover))
        self.bind("<Leave>", lambda e: self.itemconfig(self._img, image=self._normal))
        self.bind("<Button-1>", lambda e: self._cmd())


def make_entry(parent, show="", size=14):
    wrap = tk.Frame(parent, bg=FIELD, highlightthickness=2,
                    highlightbackground=BORDER)
    entry = tk.Entry(wrap, bg=FIELD, fg=TEXT, insertbackground=CYAN,
                     relief="flat", bd=0, highlightthickness=0,
                     font=(FONT, size), show=show)
    entry.pack(fill="x", padx=14, pady=11)
    entry.bind("<FocusIn>", lambda e: wrap.config(highlightbackground=VIOLET))
    entry.bind("<FocusOut>", lambda e: wrap.config(highlightbackground=BORDER))
    return wrap, entry


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
        self.res_win = None
        self._resize_job = None
        self._bg_photo = None

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

    # ----- Layout helpers -----
    def clear(self):
        for attr in ("after_id", "fx_id"):
            job = getattr(self, attr)
            if job:
                self.after_cancel(job)
                setattr(self, attr, None)
        self.unbind("<Return>")
        for widget in self.card.winfo_children():
            widget.destroy()

    def build_shell(self, step):
        self.clear()
        hero = tk.Canvas(self.card, width=HERO_W, height=CARD_H,
                         highlightthickness=0, bg="#4c1d95")
        hero.pack(side="left")
        hero.create_image(0, 0, image=self.hero_photo, anchor="nw")

        # shield logo
        cx, y = 60, 52
        hero.create_polygon(cx - 28, y, cx + 28, y, cx + 28, y + 32, cx, y + 60,
                            cx - 28, y + 32, fill="white", outline="")
        hero.create_text(cx, y + 26, text="✓", fill=VIOLET, font=(FONT, 26, "bold"))
        hero.create_text(32, 142, text="SecureVote", fill="white", anchor="w",
                         font=(FONT, 30, "bold"))
        hero.create_text(32, 182, text="Your voice. Verified. Counted.", fill="#f5d0fe",
                         anchor="w", font=(FONT, 13))

        # progress tracker
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
                         fill="#e9d5ff", anchor="w", font=(FONT, 11))

        right = tk.Frame(self.card, bg=CARD)
        right.pack(side="left", fill="both", expand=True, padx=48, pady=38)
        return right

    def make_msg(self, parent):
        self.msg = tk.Label(parent, text="", bg=CARD, fg=DANGER,
                            font=(FONT, 12), anchor="w")
        self.msg.pack(fill="x")

    def set_msg(self, text, color=DANGER):
        self.msg.config(text=text, fg=color)

    # ----- Screen 1: Login -----
    def show_login(self):
        self.current_voter = None
        self.otp = None
        right = self.build_shell(0)

        tk.Label(right, text="Welcome back", font=(FONT, 32, "bold"),
                 fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(right, text="Log in with your Voter ID to cast your vote",
                 fg=MUTED, bg=CARD, font=(FONT, 13)).pack(anchor="w", pady=(2, 26))

        tk.Label(right, text="VOTER ID", fg=CYAN, bg=CARD,
                 font=(FONT, 10, "bold")).pack(anchor="w")
        wrap, self.id_entry = make_entry(right)
        wrap.pack(fill="x", pady=(5, 16))

        tk.Label(right, text="PASSWORD", fg=CYAN, bg=CARD,
                 font=(FONT, 10, "bold")).pack(anchor="w")
        wrap, self.pw_entry = make_entry(right, show="*")
        wrap.pack(fill="x", pady=(5, 8))

        self.make_msg(right)
        GradButton(right, "Login  →", self.check_login).pack(pady=(8, 16))

        link = tk.Label(right, text="View live results", fg=PINK, bg=CARD,
                        cursor="hand2", font=(FONT, 13, "underline"))
        link.pack(anchor="w")
        link.bind("<Button-1>", lambda e: self.show_results())

        tk.Label(right, text="Demo voters: V001 to V005     Password: 1234",
                 fg=MUTED, bg=CARD, font=(FONT, 11)).pack(side="bottom", anchor="w")

        self.bind("<Return>", lambda e: self.check_login())
        self.id_entry.focus_set()

    def check_login(self):
        voter_id = self.id_entry.get().strip()
        password = self.pw_entry.get().strip()

        con = get_db()
        row = con.execute(
            "SELECT voter_id, name, password, has_voted FROM voters WHERE voter_id=?",
            (voter_id,)).fetchone()
        con.close()

        if row is None or row[2] != password:
            self.set_msg("Wrong Voter ID or password.")
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

    # ----- Screen 2: OTP -----
    def show_otp(self):
        right = self.build_shell(1)

        tk.Label(right, text="Verify it's you", font=(FONT, 32, "bold"),
                 fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(right, text=f"Hello {self.current_voter[1]}, enter the 6-digit code",
                 fg=MUTED, bg=CARD, font=(FONT, 13)).pack(anchor="w", pady=(2, 16))

        banner = tk.Frame(right, bg="#0b2a2e", highlightthickness=1,
                          highlightbackground=MINT)
        banner.pack(fill="x", pady=(0, 20))
        tk.Label(banner, text="DEMO SMS", bg="#0b2a2e", fg=MINT,
                 font=(FONT, 9, "bold")).pack(anchor="w", padx=14, pady=(9, 0))
        self.otp_banner = tk.Label(banner, text="", bg="#0b2a2e", fg=TEXT,
                                   font=(FONT, 13), justify="left")
        self.otp_banner.pack(anchor="w", padx=14, pady=(0, 9))
        self.refresh_banner()

        row = tk.Frame(right, bg=CARD)
        row.pack(anchor="w", pady=(0, 8))
        self.otp_boxes = []
        self.otp_wraps = []
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
            self.otp_wraps.append(w)

        self.countdown = tk.Label(right, text="", bg=CARD, fg=MUTED,
                                  font=(FONT, 12), anchor="w")
        self.countdown.pack(fill="x")
        self.make_msg(right)

        GradButton(right, "Verify  →", self.verify_otp,
                   stops=(CYAN, VIOLET)).pack(pady=(8, 12))

        links = tk.Frame(right, bg=CARD)
        links.pack(fill="x")
        resend = tk.Label(links, text="Resend OTP", fg=PINK, bg=CARD,
                          cursor="hand2", font=(FONT, 13, "underline"))
        resend.pack(side="left")
        resend.bind("<Button-1>", lambda e: self.resend_otp())
        back = tk.Label(links, text="Back to login", fg=MUTED, bg=CARD,
                        cursor="hand2", font=(FONT, 13, "underline"))
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
        # a single digit stays here; extra digits (paste) flow into next boxes
        for k, ch in enumerate(digits):
            if i + k < 6:
                self.otp_boxes[i + k].delete(0, tk.END)
                self.otp_boxes[i + k].insert(0, ch)
        nxt = min(i + len(digits), 5)
        self.otp_boxes[nxt].focus_set()

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
            self.countdown.config(text=f"Code expires in {left // 60}:{left % 60:02d}",
                                  fg=MUTED)
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
            messagebox.showerror("Blocked", "Too many wrong attempts.")
            self.show_login()
        else:
            self.set_msg(f"Wrong OTP. {3 - self.attempts} attempts left.")

    # ----- Screen 3: Candidates -----
    def show_candidates(self):
        right = self.build_shell(2)

        tk.Label(right, text="Choose your candidate", font=(FONT, 28, "bold"),
                 fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(right, text="Tap a card to select. Your vote is final.",
                 fg=MUTED, bg=CARD, font=(FONT, 13)).pack(anchor="w", pady=(2, 14))

        con = get_db()
        candidates = con.execute(
            "SELECT id, name, party FROM candidates ORDER BY id").fetchall()
        con.close()

        self.choice = None
        self.cards = {}
        for idx, (cid, name, party) in enumerate(candidates):
            color = CAND_COLORS[idx % len(CAND_COLORS)]
            card = tk.Frame(right, bg=FIELD, highlightthickness=2,
                            highlightbackground=BORDER, cursor="hand2")
            card.pack(fill="x", pady=6)

            stripe = tk.Frame(card, bg=color, width=6)
            stripe.pack(side="left", fill="y")

            av = tk.Canvas(card, width=52, height=52, bg=FIELD, highlightthickness=0)
            av.create_oval(2, 2, 50, 50, fill=color, outline="")
            av.create_text(26, 26, text=name[0], fill="white", font=(FONT, 19, "bold"))
            av.pack(side="left", padx=14, pady=11)

            info = tk.Frame(card, bg=FIELD)
            info.pack(side="left")
            tk.Label(info, text=name, bg=FIELD, fg=TEXT,
                     font=(FONT, 15, "bold")).pack(anchor="w")
            tk.Label(info, text=party, bg=FIELD, fg=color,
                     font=(FONT, 12)).pack(anchor="w")

            ind = tk.Canvas(card, width=28, height=28, bg=FIELD, highlightthickness=0)
            ind.pack(side="right", padx=20)
            self.draw_indicator(ind, MUTED, False)

            self.cards[cid] = (card, ind, color)
            for w in (card, stripe, av, info, ind) + tuple(info.winfo_children()):
                w.bind("<Button-1>", lambda e, c=cid: self.select_candidate(c))

        self.make_msg(right)
        GradButton(right, "Submit Vote", self.cast_vote,
                   stops=(PINK, VIOLET)).pack(pady=(6, 0))

    @staticmethod
    def draw_indicator(canvas, color, selected):
        canvas.delete("all")
        canvas.create_oval(3, 3, 25, 25, outline=color, width=2)
        if selected:
            canvas.create_oval(9, 9, 19, 19, fill=color, outline=color)

    def select_candidate(self, cid):
        self.choice = cid
        for c, (card, ind, color) in self.cards.items():
            if c == cid:
                card.config(highlightbackground=color)
                self.draw_indicator(ind, color, True)
            else:
                card.config(highlightbackground=BORDER)
                self.draw_indicator(ind, MUTED, False)
        self.set_msg("")

    def cast_vote(self):
        if self.choice is None:
            self.set_msg("Please select a candidate first.")
            return
        if not messagebox.askyesno("Confirm", "Submit your vote? You cannot change it."):
            return

        con = get_db()
        cur = con.cursor()
        # Only succeeds while has_voted is still 0 -> one vote per voter
        cur.execute("UPDATE voters SET has_voted=1 WHERE voter_id=? AND has_voted=0",
                    (self.current_voter[0],))
        if cur.rowcount == 0:
            con.close()
            messagebox.showerror("Error", "You have already voted.")
            self.show_login()
            return
        cur.execute("UPDATE candidates SET votes = votes + 1 WHERE id=?", (self.choice,))
        con.commit()
        con.close()
        self.show_done()

    # ----- Screen 4: Thank you + confetti -----
    def show_done(self):
        right = self.build_shell(3)
        name = self.current_voter[1]
        self.current_voter = None

        self.confetti = tk.Canvas(right, width=500, height=120, bg=CARD,
                                  highlightthickness=0)
        self.confetti.pack(anchor="w")
        self.confetti.create_oval(4, 14, 92, 102, fill=MINT, outline="")
        self.confetti.create_text(48, 58, text="✓", fill="white",
                                  font=(FONT, 46, "bold"))
        self.particles = []
        for _ in range(60):
            x, y = random.randint(110, 495), random.randint(-120, 0)
            size = random.randint(5, 10)
            col = random.choice(CAND_COLORS)
            pid = self.confetti.create_rectangle(x, y, x + size, y + size,
                                                 fill=col, outline="")
            self.particles.append([pid, random.uniform(1.5, 4), random.uniform(-1, 1)])
        self.frames = 0
        self.animate_confetti()

        tk.Label(right, text="Vote recorded!", font=(FONT, 32, "bold"),
                 fg=TEXT, bg=CARD).pack(anchor="w", pady=(6, 0))
        tk.Label(right, text=f"Thank you, {name}. Your vote has been securely saved.",
                 fg=MUTED, bg=CARD, font=(FONT, 13)).pack(anchor="w", pady=(2, 12))
        tk.Label(right, text=f"Confirmation code:  {uuid.uuid4().hex[:10].upper()}",
                 fg=CYAN, bg=CARD, font=(FONT, 14, "bold")).pack(anchor="w", pady=(0, 22))

        GradButton(right, "View Results", self.show_results).pack(pady=(0, 10))
        GradButton(right, "Log out", self.show_login,
                   stops=(FIELD, "#1f2866")).pack()

    def animate_confetti(self):
        if self.frames > 110:
            self.fx_id = None
            return
        for p in self.particles:
            self.confetti.move(p[0], p[2], p[1])
        self.frames += 1
        self.fx_id = self.after(30, self.animate_confetti)

    # ----- Results dashboard -----
    def show_results(self):
        con = get_db()
        data = con.execute(
            "SELECT name, party, votes FROM candidates ORDER BY id").fetchall()
        total_voters = con.execute("SELECT COUNT(*) FROM voters").fetchone()[0]
        voted = con.execute("SELECT COUNT(*) FROM voters WHERE has_voted=1").fetchone()[0]
        con.close()

        if self.res_win is not None and self.res_win.winfo_exists():
            self.res_win.destroy()
        win = tk.Toplevel(self, bg=CARD)
        self.res_win = win
        win.title("Live Election Results")
        win.geometry("900x640")

        tk.Label(win, text="Live Election Results", bg=CARD, fg=TEXT,
                 font=(FONT, 26, "bold")).pack(anchor="w", padx=32, pady=(24, 0))
        tk.Label(win, text="Updated with every vote", bg=CARD, fg=MUTED,
                 font=(FONT, 13)).pack(anchor="w", padx=32, pady=(0, 6))

        names = [d[0] for d in data]
        votes = [d[2] for d in data]
        colors = [CAND_COLORS[i % len(CAND_COLORS)] for i in range(len(data))]
        total = sum(votes)
        top = max(max(votes), 1)
        order = sorted(range(len(data)), key=lambda i: votes[i])

        fig = Figure(figsize=(8.6, 3.7), dpi=100, facecolor=CARD)
        ax1 = fig.add_subplot(121, facecolor=CARD)
        if total:
            ax1.pie(votes, colors=colors, startangle=90, counterclock=False,
                    wedgeprops=dict(width=0.34, edgecolor=CARD, linewidth=3))
        else:
            ax1.pie([1], colors=[BORDER], wedgeprops=dict(width=0.34, edgecolor=CARD))
        ax1.text(0, 0.07, str(total), ha="center", va="center", color=TEXT,
                 fontsize=28, fontweight="bold")
        ax1.text(0, -0.2, "TOTAL VOTES", ha="center", va="center", color=MUTED,
                 fontsize=9)

        ax2 = fig.add_subplot(122, facecolor=CARD)
        ax2.barh([names[i] for i in order], [votes[i] for i in order],
                 color=[colors[i] for i in order], height=0.5)
        for y, i in enumerate(order):
            pct = votes[i] * 100 / total if total else 0
            ax2.text(votes[i] + top * 0.04, y, f"{votes[i]}  ({pct:.0f}%)",
                     va="center", color=TEXT, fontsize=10)
        ax2.set_xlim(0, top * 1.6)
        ax2.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax2.tick_params(colors=MUTED, labelsize=10, length=0)
        for spine in ax2.spines.values():
            spine.set_visible(False)
        ax2.xaxis.grid(True, color=BORDER, linewidth=0.6)
        ax2.set_axisbelow(True)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20)

        if total == 0:
            leader = "No votes yet"
        else:
            winners = [names[i] for i in range(len(data)) if votes[i] == top]
            leader = winners[0] if len(winners) == 1 else "Tie"

        stats = tk.Frame(win, bg=CARD)
        stats.pack(fill="x", padx=26, pady=(0, 26))
        for title, value, col in [("TOTAL VOTES", str(total), CYAN),
                                  ("TURNOUT", f"{voted} / {total_voters}", MINT),
                                  ("LEADING", leader, AMBER)]:
            box = tk.Frame(stats, bg=FIELD, highlightthickness=2,
                           highlightbackground=col)
            box.pack(side="left", expand=True, fill="x", padx=6)
            tk.Label(box, text=title, bg=FIELD, fg=MUTED,
                     font=(FONT, 10, "bold")).pack(pady=(12, 0))
            tk.Label(box, text=value, bg=FIELD, fg=col,
                     font=(FONT, 18, "bold")).pack(pady=(0, 12))


if __name__ == "__main__":
    setup_database()
    app = VotingApp()
    app.mainloop()
