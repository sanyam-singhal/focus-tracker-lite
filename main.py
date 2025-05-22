from __future__ import annotations
import sqlite3, time
from datetime import datetime, timedelta
from playsound3 import playsound
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static, Input, Button, DataTable, ListView, ListItem

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
    #inputs Input#minutes { width: 15; }
    #inputs Input#tag     { width: 20; }
    #inputs Button#start  { width: 10; }
    #inputs Button#quit   { width: 8; }  
    #timer { height: 1; content-align: center middle; }
    """
    remaining: reactive[int | None] = reactive(None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.break_default = 5  # minutes
        self.break_remaining = None
        self.break_timer = None
        # Pomodoro defaults
        self.pomodoro_mode = False
        self.pomo_focus = 25
        self.pomo_short_break = 5
        self.pomo_long_break = 15
        self.pomo_cycles = 4
        self.pomo_current_cycle = 0
        self.pomo_in_break = False

    def compose(self) -> ComposeResult:
        yield Static("⏱  Focus Tracker – Ctrl-Q quits", id="title")
        # --- Goals and Progress Bars ---
        self.daily_goal = 120  # minutes, default
        self.weekly_goal = 600 # minutes, default
        self._goal_bar = Static("", id="goal_bar", markup=False)
        self._goal_settings = Button("Set Goals", id="set_goals", variant="primary")
        yield self._goal_bar
        yield self._goal_settings
        # --- Pomodoro ---
        self._pomo_status = Static("", id="pomo_status")
        self._pomo_toggle = Button("Pomodoro: Off", id="pomo_toggle", variant="primary")
        self._pomo_settings = Button("Pomodoro Settings", id="pomo_settings", variant="default")
        yield self._pomo_status
        yield self._pomo_toggle
        yield self._pomo_settings
        # --- Heatmap ---
        self._heatmap = Static("", id="heatmap")
        yield self._heatmap
        with Horizontal(id="inputs"):
            self._minutes_input = Input(placeholder="Minutes", id="minutes", type="integer")
            yield self._minutes_input
            yield Input(placeholder="Tag", id="tag")
            yield Button("Start", id="start", variant="success")
            yield Button("Pause", id="pause", variant="primary")
            yield Button("Quit", id="quit", variant="error") 

        yield Static("", id="stats")
        yield Static("", id="timer")
        with VerticalScroll():
            self.table = DataTable(zebra_stripes=True)
            self.table.add_columns("Start", "Dur", "Tag", "Note")
            yield self.table

    def on_mount(self) -> None:
        self.query_one("#minutes", Input).focus()
        self._refresh_table()
        self._load_tags()
        self.table.cursor_type = "row"
        self.table.focus()
        self._update_pomo_status()

    def _refresh_table(self) -> None:
        self.table.clear()
        with get_db() as con:
            for ts, dur, tag, note, session_id in con.execute(
                "SELECT start_ts,duration_min,tag,note,id FROM sessions ORDER BY id DESC LIMIT 100"
            ):
                self.table.add_row(
                    datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
                    f"{dur} m",
                    tag or "",
                    note,
                    key=session_id
                )
            # --- Statistics ---
            now = datetime.now()
            today_start = datetime(now.year, now.month, now.day).timestamp()
            week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            today = con.execute(
                "SELECT COUNT(*), COALESCE(SUM(duration_min),0) FROM sessions WHERE start_ts >= ?",
                (today_start,)
            ).fetchone()
            week = con.execute(
                "SELECT COUNT(*), COALESCE(SUM(duration_min),0) FROM sessions WHERE start_ts >= ?",
                (week_start,)
            ).fetchone()
            stats = (
                f"[b]Today:[/b] {today[0]} sessions, {today[1]} min   "
                f"[b]This week:[/b] {week[0]} sessions, {week[1]} min"
            )
            self.query_one("#stats", Static).update(stats)
            # --- Progress Bars ---
            daily_pct = min(today[1] / self.daily_goal, 1.0) if self.daily_goal else 0
            weekly_pct = min(week[1] / self.weekly_goal, 1.0) if self.weekly_goal else 0
            bar = (
                f"[b]Daily Goal:[/b] {today[1]}/{self.daily_goal} min  "
                f"[[{'#'*int(daily_pct*20):20}]] {int(daily_pct*100)}%\n"
                f"[b]Weekly Goal:[/b] {week[1]}/{self.weekly_goal} min  "
                f"[[{'#'*int(weekly_pct*20):20}]] {int(weekly_pct*100)}%"
            )
            self.query_one("#goal_bar", Static).update(bar)
            # --- Heatmap ---
            days = 30
            start = (now - timedelta(days=days-1)).replace(hour=0, minute=0, second=0, microsecond=0)
            data = {row[0]: row[1] for row in con.execute(
                "SELECT date(datetime(start_ts, 'unixepoch')), SUM(duration_min) FROM sessions "
                "WHERE start_ts >= ? GROUP BY date(datetime(start_ts, 'unixepoch'))",
                (start.timestamp(),)
            )}
            blocks = [' ', '░', '▒', '▓', '█']
            max_min = max(data.values()) if data else 1
            # Build 7x5 grid (weeks x days)
            grid = [[' ' for _ in range(7)] for _ in range(5)]
            for i in range(days):
                d = start + timedelta(days=i)
                w, wd = divmod(i, 7)
                mins = data.get(d.strftime('%Y-%m-%d'), 0)
                level = int((mins / max_min) * 4) if max_min else 0
                grid[w][wd] = blocks[level]
            heatmap = '[b]Mon Tue Wed Thu Fri Sat Sun[/b]\n'
            for row in grid:
                heatmap += ' '.join(row) + '\n'
            self.query_one("#heatmap", Static).update(heatmap)

    def _load_tags(self) -> None:
        pass  # Tag suggestions feature removed

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            await self._start_session()
        elif event.button.id == "pause":
            self._pause_resume()
        elif event.button.id == "quit":
            self.exit()
        elif event.button.id == "set_goals":
            self._show_goal_settings()
        elif event.button.id == "edit_save":
            await self._save_edit_session()
        elif event.button.id == "edit_cancel":
            self._edit_popup.remove()
        elif event.button.id == "edit_delete":
            await self._delete_session()
        elif event.button.id == "goal_save":
            await self._save_goal_settings()
        elif event.button.id == "goal_cancel":
            self._goal_popup.remove()
        elif event.button.id == "break_start":
            await self._start_break()
        elif event.button.id == "break_skip":
            # Skip the break: stop timer, remove popup, reset state
            if hasattr(self, 'break_timer') and self.break_timer:
                self.break_timer.stop()
                self.break_timer = None
            if hasattr(self, '_break_popup') and self._break_popup:
                self._break_popup.remove()
                self._break_popup = None
        elif event.button.id == "pomo_toggle":
            self.pomodoro_mode = not self.pomodoro_mode
            self._update_pomo_status()
        elif event.button.id == "pomo_settings":
            self._show_pomo_settings()
        elif event.button.id == "pomo_save":
            await self._save_pomo_settings()
        elif event.button.id == "pomo_cancel":
            self._pomo_popup.remove()

    async def on_input_changed(self, event: Input.Changed) -> None:
        pass  # Tag suggestions feature removed

    def _show_tag_suggestions(self) -> None:
        pass  # Tag suggestions feature removed

    async def on_list_view_selected(self, event):
        pass  # Tag suggestions feature removed

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "note_prompt":
            await self._save_note(event.value)
        elif event.input.id == "goal_daily" or event.input.id == "goal_weekly":
            await self._save_goal_settings()

    async def _start_session(self) -> None:
        if self.remaining is not None:
            self.bell(); return
        if self.pomodoro_mode:
            self.duration = self.pomo_focus * 60
            self.remaining = self.duration
            self.tag = self.query_one("#tag", Input).value.strip() or None
            self.start_ts = time.time()
            self.tick_timer = self.set_interval(1.0, self._tick)
            self.pomo_in_break = False
        else:
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
            if self.pomodoro_mode:
                self.call_after_refresh(self._pomo_next)
            else:
                self.call_after_refresh(self._prompt_note)
                self.call_after_refresh(self._prompt_break)

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
        # Optimize for responsiveness: remove unnecessary blocking, refresh immediately
        with get_db() as con:
            con.execute(
                "INSERT INTO sessions(start_ts,duration_min,tag,note) "
                "VALUES (?,?,?,?)",
                (self.start_ts, self.duration // 60, self.tag, note.strip()),
            )
        self.query_one("#note_prompt", Input).remove()
        self.call_after_refresh(self._refresh_table)  # Use call_after_refresh for snappier UI

    def _pause_resume(self) -> None:
        if not hasattr(self, "tick_timer") or self.remaining is None:
            self.bell(); return
        if getattr(self, "_paused", False):
            self.tick_timer = self.set_interval(1.0, self._tick)
            self._paused = False
            self.query_one("#pause", Button).label = "Pause"
        else:
            self.tick_timer.stop()
            self._paused = True
            self.query_one("#pause", Button).label = "Resume"

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        session_id = event.row_key.value
        with get_db() as con:
            tag, note = con.execute(
                "SELECT tag, note FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        # Show popup for editing
        self._edit_session_id = session_id
        self._edit_popup = Static(id="edit_popup")
        self._edit_tag = Input(value=tag or "", placeholder="Edit tag", id="edit_tag")
        self._edit_note = Input(value=note or "", placeholder="Edit note", id="edit_note")
        self._edit_save = Button("Save", id="edit_save", variant="success")
        self._edit_cancel = Button("Cancel", id="edit_cancel", variant="error")
        self._edit_delete = Button("Delete", id="edit_delete", variant="warning")
        self.mount(self._edit_popup)
        self._edit_popup.mount(self._edit_tag)
        self._edit_popup.mount(self._edit_note)
        self._edit_popup.mount(self._edit_save)
        self._edit_popup.mount(self._edit_cancel)
        self._edit_popup.mount(self._edit_delete)
        self._edit_tag.focus()

    async def _save_edit_session(self) -> None:
        tag = self._edit_tag.value.strip()
        note = self._edit_note.value.strip()
        with get_db() as con:
            con.execute(
                "UPDATE sessions SET tag=?, note=? WHERE id=?",
                (tag, note, self._edit_session_id)
            )
        self._edit_popup.remove()
        self._refresh_table()

    def _show_goal_settings(self):
        self._goal_popup = Static(id="goal_popup")
        self._goal_daily = Input(value=str(self.daily_goal), placeholder="Daily goal (min)", id="goal_daily")
        self._goal_weekly = Input(value=str(self.weekly_goal), placeholder="Weekly goal (min)", id="goal_weekly")
        self._goal_save = Button("Save", id="goal_save", variant="success")
        self._goal_cancel = Button("Cancel", id="goal_cancel", variant="error")
        self.mount(self._goal_popup)
        self._goal_popup.mount(self._goal_daily)
        self._goal_popup.mount(self._goal_weekly)
        self._goal_popup.mount(self._goal_save)
        self._goal_popup.mount(self._goal_cancel)
        self._goal_daily.focus()

    async def _save_goal_settings(self):
        try:
            daily = int(self._goal_daily.value)
            weekly = int(self._goal_weekly.value)
            if daily > 0 and weekly > 0:
                self.daily_goal = daily
                self.weekly_goal = weekly
        except Exception:
            pass
        self._goal_popup.remove()
        self._refresh_table()

    def _prompt_break(self) -> None:
        if hasattr(self, '_break_popup') and self._break_popup:
            return
        self.break_remaining = self.break_default * 60
        self._break_popup = Static(id="break_popup")
        self._break_time = Static(self._format_break_time(), id="break_time")
        self._break_input = Input(value=str(self.break_default), placeholder="Break min", id="break_input")
        self._break_start = Button("Start Break", id="break_start", variant="success")
        self._break_skip = Button("Skip Break", id="break_skip", variant="warning")
        self.mount(self._break_popup)
        self._break_popup.mount(self._break_time)
        self._break_popup.mount(self._break_input)
        self._break_popup.mount(self._break_start)
        self._break_popup.mount(self._break_skip)
        self._break_input.focus()

    def _format_break_time(self):
        m, s = divmod(self.break_remaining or 0, 60)
        return f"Break: [b]{m:02d}:{s:02d}[/b]"

    async def _start_break(self):
        try:
            mins = int(self._break_input.value)
            if mins > 0:
                self.break_remaining = mins * 60
                self.break_default = mins
        except Exception:
            self.break_remaining = self.break_default * 60
        # Instead of removing the popup, keep it visible and update timer inside it
        self._break_input.disabled = True
        self._break_start.disabled = True
        self._break_timer_running = True
        self.break_timer = self.set_interval(1.0, self._break_tick)
        self._update_break_popup_time()

    def _update_break_popup_time(self):
        if hasattr(self, '_break_popup') and self._break_popup:
            self._break_time.update(self._format_break_time())

    def _break_tick(self):
        self.break_remaining -= 1
        self._update_break_popup_time()
        if self.break_remaining <= 0:
            self.break_timer.stop()
            self.break_timer = None
            if hasattr(self, '_break_popup') and self._break_popup:
                self._break_popup.remove()
                self._break_popup = None
            self.query_one("#timer", Static).update("Break over! Ready to focus again.")
            playsound(SOUND)

    def _update_pomo_status(self):
        if self.pomodoro_mode:
            self._pomo_toggle.label = "Pomodoro: On"
            status = f"[b]Pomodoro:[/b] {self.pomo_focus}m focus / {self.pomo_short_break}m break, {self.pomo_cycles} cycles, long break {self.pomo_long_break}m"
            self._minutes_input.disabled = True
        else:
            self._pomo_toggle.label = "Pomodoro: Off"
            status = ""
            self._minutes_input.disabled = False
        self._pomo_status.update(status)

    def _show_pomo_settings(self):
        self._pomo_popup = Static(id="pomo_popup")
        self._pomo_focus_in = Input(value=str(self.pomo_focus), placeholder="Focus min", id="pomo_focus_in")
        self._pomo_short_in = Input(value=str(self.pomo_short_break), placeholder="Short break min", id="pomo_short_in")
        self._pomo_long_in = Input(value=str(self.pomo_long_break), placeholder="Long break min", id="pomo_long_in")
        self._pomo_cycles_in = Input(value=str(self.pomo_cycles), placeholder="Cycles", id="pomo_cycles_in")
        self._pomo_save = Button("Save", id="pomo_save", variant="success")
        self._pomo_cancel = Button("Cancel", id="pomo_cancel", variant="error")
        self.mount(self._pomo_popup)
        self._pomo_popup.mount(self._pomo_focus_in)
        self._pomo_popup.mount(self._pomo_short_in)
        self._pomo_popup.mount(self._pomo_long_in)
        self._pomo_popup.mount(self._pomo_cycles_in)
        self._pomo_popup.mount(self._pomo_save)
        self._pomo_popup.mount(self._pomo_cancel)
        self._pomo_focus_in.focus()

    async def _save_pomo_settings(self):
        try:
            focus = int(self._pomo_focus_in.value)
            short = int(self._pomo_short_in.value)
            longb = int(self._pomo_long_in.value)
            cycles = int(self._pomo_cycles_in.value)
            if focus > 0 and short > 0 and longb > 0 and cycles > 0:
                self.pomo_focus = focus
                self.pomo_short_break = short
                self.pomo_long_break = longb
                self.pomo_cycles = cycles
        except Exception:
            pass
        self._pomo_popup.remove()
        self._update_pomo_status()

    def _pomo_next(self):
        if not self.pomo_in_break:
            # Just finished a focus session
            self.pomo_current_cycle += 1
            if self.pomo_current_cycle % self.pomo_cycles == 0:
                # Long break
                self.remaining = self.pomo_long_break * 60
                self.query_one("#timer", Static).update(f"Long Break: [b]{self.pomo_long_break:02d}:00[/b]")
            else:
                # Short break
                self.remaining = self.pomo_short_break * 60
                self.query_one("#timer", Static).update(f"Break: [b]{self.pomo_short_break:02d}:00[/b]")
            self.pomo_in_break = True
            self.tick_timer = self.set_interval(1.0, self._tick)
        else:
            # Just finished a break
            if self.pomo_current_cycle % self.pomo_cycles == 0:
                self.pomo_current_cycle = 0  # Reset cycle
            self.remaining = self.pomo_focus * 60
            self.query_one("#timer", Static).update(f"[b]{self.pomo_focus:02d}:00[/b]")
            self.pomo_in_break = False
            self.tick_timer = self.set_interval(1.0, self._tick)

    async def _delete_session(self) -> None:
        with get_db() as con:
            con.execute(
                "DELETE FROM sessions WHERE id=?",
                (self._edit_session_id,)
            )
        self._edit_popup.remove()
        self._refresh_table()

    BINDINGS = [("q", "quit", "Quit")]

if __name__ == "__main__":
    FocusApp().run()
