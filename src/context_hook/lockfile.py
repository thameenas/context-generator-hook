"""Lockfile mechanism to prevent concurrent updates."""

import contextlib
import os
import signal
from pathlib import Path


class LockError(Exception):
    """Raised when the lock cannot be acquired."""
    pass


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


@contextlib.contextmanager
def acquire_lock(lock_file: Path):
    """Context manager for a PID-based lockfile.

    - If lockfile exists and PID is alive: raise LockError
    - If lockfile exists and PID is dead: remove stale lock, acquire
    - If lockfile doesn't exist: acquire

    Usage:
        with acquire_lock(Path(".context/.lock")):
            # do work
    """
    lock_file.parent.mkdir(exist_ok=True)

    if lock_file.exists():
        try:
            stale_pid = int(lock_file.read_text().strip())
            if _is_pid_alive(stale_pid):
                raise LockError(
                    f"Another context-hook update is running (PID {stale_pid}). "
                    "Skipping this update."
                )
            # PID is dead — stale lock, remove it
            lock_file.unlink(missing_ok=True)
        except (ValueError, OSError):
            # Malformed lock file, remove it
            lock_file.unlink(missing_ok=True)

    # Write current PID
    try:
        lock_file.write_text(str(os.getpid()))
    except OSError as e:
        raise LockError(f"Failed to create lockfile: {e}")

    try:
        yield
    finally:
        lock_file.unlink(missing_ok=True)
