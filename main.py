#!/usr/bin/env python3
"""
focus_tui.py – Textual UI for your focus timer (playsound3 alarm).
"""

from __future__ import annotations
import sqlite3, time
from datetime import datetime
from pathlib import Path

from playsound3 import playsound            # <= plays alarm (maintained fork) :contentReference[oaicite:8]{index=8}
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static, Input, Button, DataTable

DB = "focus.db"
SOUND = "alarm.wav"


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.execute(
        """CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY,
            start_ts REAL,
            duration_min INTEGER,
            tag TEXT,
            note TEXT
        )"""
    )
    return con


class FocusApp(App):
    remaining: reactive[int | None] = reactive(None)

    # ───────────────────────── compose UI ──────────────────────────
    def compose(self) -> ComposeResult:
        yield Static("⏱  Focus Tracker  –  Ctrl-Q to quit", id="title")

        with Horizontal(id="inputs"):
            yield Input(placeholder="Minutes", id="minutes", type="integer")
            yield Input(placeholder="Tag optional…", id="tag")
            yield Button("Start", id="start", variant="success")

        yield Static("", id="timer")

        with VerticalScroll():
            self.table = DataTable(zebra_stripes=True)
            self.table.add_columns("Start", "Dur", "Tag", "Note")
            yield self.table

    # ───────────────────────── helpers ────────────────────────────
    def on_mount(self) -> None:
        self.query_one("#minutes", Input).focus()
        self.refresh_table()

    def refresh_table(self) -> None:
        self.table.clear()
        with get_db() as con:
            for ts, dur, tag, note in con.execute(
                "SELECT start_ts,duration_min,tag,note FROM sessions "
                "ORDER BY id DESC LIMIT 100"
            ):
                start = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                self.table.add_row(start, f"{dur} m", tag or "", note)

    # ───────────────────────── launch / tick ──────────────────────
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            await self.launch_timer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "minutes":
            await self.launch_timer()
        elif event.input.id == "note_prompt":
            await self.save_note(event)

    async def launch_timer(self) -> None:
        minutes_str = self.query_one("#minutes", Input).value
        if not minutes_str.isdigit() or int(minutes_str) <= 0:
            self.bell(); return

        self.duration = int(minutes_str) * 60
        self.remaining = self.duration
        self.tag = self.query_one("#tag", Input).value.strip() or None
        self.start_ts = time.time()

        # modern timer handle
        self.tick_timer = self.set_interval(1, self._tick, name="countdown")  # returns Timer object :contentReference[oaicite:9]{index=9}

    def _tick(self) -> None:
        if self.remaining is None:
            return
        self.remaining -= 1
        mins, secs = divmod(max(self.remaining, 0), 60)
        self.query_one("#timer", Static).update(f"[b]{mins:02d}:{secs:02d}[/b]")

        if self.remaining <= 0:
            self.tick_timer.stop()                            # stop via handle, per Timer API :contentReference[oaicite:10]{index=10}
            playsound(SOUND)
            self.call_after_refresh(self.collect_note)

    # ───────────────────────── note collection ────────────────────
    def collect_note(self) -> None:
        prompt = Input(
            placeholder="What did you get done? (Enter to save)",
            id="note_prompt",
        )
        self.mount(prompt)
        prompt.focus()

    async def save_note(self, event: Input.Submitted) -> None:
        note = event.value.strip()
        with get_db() as con:
            con.execute(
                "INSERT INTO sessions(start_ts,duration_min,tag,note) "
                "VALUES (?,?,?,?)",
                (self.start_ts, self.duration // 60, self.tag, note),
            )
        event.input.remove()
        self.refresh_table()
        self.remaining = None

    BINDINGS = [("q", "quit", "Quit")]


if __name__ == "__main__":
    FocusApp().run()
