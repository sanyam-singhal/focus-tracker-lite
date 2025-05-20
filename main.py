#!/usr/bin/env python3
"""
focus.py – minimal “Pomodoro + journal” tracker with tags and sound.
Usage examples:
  python focus.py start 50 --tag deep-work --sound-path alarm.wav
  python focus.py log --last 5
Requires: playsound3  (pip install playsound3)
"""
from __future__ import annotations
import argparse
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from playsound3 import playsound  # third-party, tiny and cross-platform

DB = "focus.db"
TABLE_SQL = """CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_ts REAL,
    duration_min INTEGER,
    note TEXT,
    tag TEXT
)"""

def get_db() -> sqlite3.Connection:
    """Return sqlite connection and run one-time migrations if needed."""
    con = sqlite3.connect(DB)
    con.execute(TABLE_SQL)

    # Add tag column if an older DB exists without it (SQLite ≥3.35 has IF NOT EXISTS)
    try:
        con.execute("ALTER TABLE sessions ADD COLUMN tag TEXT")
    except sqlite3.OperationalError:  # column already present
        pass
    return con

def play_alarm(path: str | Path) -> None:
    """Play `path` (blocking) and fall back to terminal bell if it fails."""
    try:
        playsound(str(path))  # synchronous; returns after sound ends
    except Exception as exc:  # noqa: BLE001
        print(f"[sound-error] {exc}  – Falling back to beep.")
        print("\a")

def alert_and_record(start_ts: float, dur: int, sound_path: Path) -> None:
    """Notify user, ask for note, persist to SQLite."""
    play_alarm(sound_path)
    print(f"\n⏰  {dur}-minute block finished! What did you get done?")
    note = input("> ").strip()

    with get_db() as con:
        con.execute(
            "INSERT INTO sessions(start_ts, duration_min, note, tag) VALUES (?,?,?,?)",
            (start_ts, dur, note, CURRENT_TAG.get()),
        )
    print("✅  Saved. Keep it up!")

# Simple holder for current tag (avoids global var mutation inside Timer thread)
class _TagHolder:
    _value: Optional[str] = None
    def set(self, val: Optional[str]) -> None: self._value = val
    def get(self) -> Optional[str]: return self._value
CURRENT_TAG = _TagHolder()

def start_session(minutes: int, tag: Optional[str], sound_path: Path) -> None:
    CURRENT_TAG.set(tag)
    start_ts = time.time()
    ends = datetime.fromtimestamp(start_ts + minutes * 60).strftime("%H:%M:%S")
    tag_info = f"[tag: {tag}]" if tag else ""
    print(f"🚀  {minutes}-min focus started {tag_info} – ends ≈ {ends}")

    timer = threading.Timer(
        minutes * 60, alert_and_record, args=(start_ts, minutes, sound_path)
    )
    timer.start()

    try:
        timer.join()                 # ← keeps interpreter alive, prevents traceback
    except KeyboardInterrupt:
        print("\n⏹️  Session cancelled.")
        timer.cancel()

def show_log(last: int | None) -> None:
    with get_db() as con:
        cur = con.cursor()
        sql = "SELECT start_ts, duration_min, tag, note FROM sessions ORDER BY id DESC"
        if last:
            sql += f" LIMIT {last}"
        rows = cur.execute(sql)
        for ts, dur, tag, note in rows:
            dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            tag_txt = f"[{tag}]" if tag else ""
            print(f"{dt} | {dur:>3} min [{tag_txt:10}] | {note}")

def cli() -> None:
    p = argparse.ArgumentParser(prog="focus")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("start", help="begin a focus session")
    ps.add_argument("minutes", type=int, help="duration in minutes")
    ps.add_argument("--tag", help="optional tag (e.g., deep-work, break)")
    ps.add_argument(
        "--sound-path",
        default="alarm.wav",
        help="audio file to play on finish (wav/mp3/flac…)",
    )

    plog = sub.add_parser("log", help="show past sessions")
    plog.add_argument("--last", type=int, metavar="N", help="only last N rows")

    args = p.parse_args()
    if args.cmd == "start":
        path = Path(args.sound_path).expanduser()
        if not path.exists():
            print(f"[warn] sound file {path} not found – will use terminal bell.")
        start_session(args.minutes, args.tag, path)
    elif args.cmd == "log":
        show_log(args.last)

if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        sys.exit("\n⏹️  Interrupted.")
