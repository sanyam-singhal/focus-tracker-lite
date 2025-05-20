from __future__ import annotations
import sqlite3, time
from datetime import datetime
from playsound3 import playsound
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static, Input, Button, DataTable

DB, SOUND = "focus.db", "alarm.wav"

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
    CSS = """
    #inputs Input#minutes { width: 10; }
    #inputs Input#tag     { width: 25; }
    #inputs Button#start  { width: 10; }
    #inputs Button#quit   { width: 8; }  
    #timer { height: 1; content-align: center middle; }
    """
    remaining: reactive[int | None] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Static("⏱  Focus Tracker – Ctrl-Q quits", id="title")
        with Horizontal(id="inputs"):
            yield Input(placeholder="Minutes", id="minutes", type="integer")
            yield Input(placeholder="Tag (optional)", id="tag")
            yield Button("Start", id="start", variant="success")
            yield Button("Quit", id="quit", variant="error") 

        yield Static("", id="timer")
        with VerticalScroll():
            self.table = DataTable(zebra_stripes=True)
            self.table.add_columns("Start", "Dur", "Tag", "Note")
            yield self.table

    def on_mount(self) -> None:
        self.query_one("#minutes", Input).focus()
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.clear()
        with get_db() as con:
            for ts, dur, tag, note in con.execute(
                "SELECT start_ts,duration_min,tag,note "
                "FROM sessions ORDER BY id DESC LIMIT 100"
            ):
                self.table.add_row(
                    datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
                    f"{dur} m",
                    tag or "",
                    note,
                )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            await self._start_session()
        elif event.button.id == "quit":
            self.exit()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "note_prompt":
            await self._save_note(event.value)

    async def _start_session(self) -> None:
        if self.remaining is not None:
            self.bell(); return

        minutes = self.query_one("#minutes", Input).value
        if not minutes.isdigit() or int(minutes) <= 0:
            self.bell(); return

        self.duration   = int(minutes) * 60
        self.remaining  = self.duration
        self.tag        = self.query_one("#tag", Input).value.strip() or None
        self.start_ts   = time.time()

        self.tick_timer = self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        self.remaining -= 1
        m, s = divmod(max(self.remaining, 0), 60)
        self.query_one("#timer", Static).update(f"[b]{m:02d}:{s:02d}[/b]")

        if self.remaining <= 0:
            self.tick_timer.stop()
            self.remaining = None
            playsound(SOUND)
            self.call_after_refresh(self._prompt_note)

    def _prompt_note(self) -> None:
        if self.query("#note_prompt"):
            return
        prompt = Input(
            placeholder="What did you get done?  (Enter to save)",
            id="note_prompt",
        )
        self.mount(prompt)
        prompt.focus()

    async def _save_note(self, note: str) -> None:
        with get_db() as con:
            con.execute(
                "INSERT INTO sessions(start_ts,duration_min,tag,note) "
                "VALUES (?,?,?,?)",
                (self.start_ts, self.duration // 60, self.tag, note.strip()),
            )
        self.query_one("#note_prompt", Input).remove()
        self._refresh_table()

    BINDINGS = [("q", "quit", "Quit")]

if __name__ == "__main__":
    FocusApp().run()
