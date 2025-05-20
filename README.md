# Focus Tracker Lite

A minimalist focus timer TUI (Text User Interface) app with local SQLite storage for tracking your productive sessions.

## Overview

Focus Tracker Lite helps you implement time-boxing and focus sessions by providing a simple timer with session tracking. The application stores your focus sessions in a local SQLite database, allowing you to keep a record of your productivity over time.

## Features

- Simple and intuitive text-based user interface
- Set custom focus session durations
- Add tags to categorize your focus sessions
- Record notes about what you accomplished during each session
- Audible alarm notification when a session ends
- View history of your recent focus sessions
- Local SQLite storage - no internet connection required

## Requirements

- Python 3.12 or higher
- Dependencies:
  - textual >= 3.2.0
  - playsound3 >= 3.2.3

## Installation

1. Clone this repository:

```bash
git clone https://github.com/sanyam-singhal/focus-tracker-lite.git
```

Change the directory to the cloned repository.
```bash
cd focus-tracker-lite
```

2. Install uv package manager (if you don't have it installed already):

   **Windows (PowerShell):**
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   **macOS/Linux:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Create a virtual environment using uv:

   ```bash
   uv venv
   ```

4. Install dependencies from pyproject.toml using uv sync:

```bash
uv sync
```

This will install all the required dependencies defined in the project's pyproject.toml file into the virtual environment.

5. Ensure you have an audio file named `alarm.wav` in the same directory as the script for the timer sound notification.

## Usage

Run the application with uv:

```bash
uv run main.py
```

The `uv run` command ensures the script runs in the virtual environment with all the required dependencies. It also verifies that your environment is in sync with the project's dependencies before executing the script.

### Using the Timer

1. Enter the number of minutes for your focus session in the "Minutes" field. The field only supports integer values.
2. Add a tag in the "Tag" field to categorize your session
3. Click the "Start" button to begin the focus session
4. When the timer ends, an alarm will sound and you'll be prompted to enter notes about what you accomplished. You can change the alarm sound by changing the alarm.wav. For convenience, it is shipped together with the git repo (small 1 MB file).

5. Your session will be saved to the local SQLite database file named `focus.db` in the same directory as the application.


## Data Storage

All focus sessions are stored in a local SQLite database file named `focus.db` in the same directory as the application. The database includes:

- Start timestamp
- Duration in minutes
- Optional tag (for categorization like deep work, studying, work, entertainment, etc.)
- Notes about what was accomplished

## License

MIT License

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.