"""File-based logging for context-hook."""

from datetime import datetime
from pathlib import Path


def log_entry(log_file: Path, action: str, status: str, message: str = "") -> None:
    """Append a log entry to the hook log file.

    Format: [ISO-8601 timestamp] [ACTION] [STATUS] message

    Example:
        [2026-02-21T12:30:00+05:30] [UPDATE] [SKIPPED] Trivial diff, no update needed
    """
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    entry = f"[{timestamp}] [{action.upper()}] [{status.upper()}]"
    if message:
        entry += f" {message}"
    entry += "\n"

    try:
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, "a") as f:
            f.write(entry)
    except OSError:
        pass  # Logging should never crash the tool


def trim_log(log_file: Path, max_entries: int = 100) -> None:
    """Trim the log file to keep only the last max_entries lines."""
    try:
        if not log_file.exists():
            return
        lines = log_file.read_text().splitlines(keepends=True)
        if len(lines) > max_entries:
            log_file.write_text("".join(lines[-max_entries:]))
    except OSError:
        pass


def read_log(log_file: Path, n: int = 20) -> list[str]:
    """Read the last n log entries. Useful for debugging."""
    try:
        if not log_file.exists():
            return []
        lines = log_file.read_text().splitlines()
        return lines[-n:]
    except OSError:
        return []
