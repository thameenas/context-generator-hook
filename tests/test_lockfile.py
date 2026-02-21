"""Tests for the lockfile module."""

import os
from pathlib import Path

import pytest

from context_hook.lockfile import acquire_lock, LockError


class TestAcquireLock:
    def test_acquires_and_releases(self, tmp_path):
        lock_file = tmp_path / ".lock"
        with acquire_lock(lock_file):
            assert lock_file.exists()
            pid = int(lock_file.read_text().strip())
            assert pid == os.getpid()
        assert not lock_file.exists()

    def test_raises_if_already_locked(self, tmp_path):
        lock_file = tmp_path / ".lock"
        # Write current PID (simulates another running process)
        lock_file.write_text(str(os.getpid()))

        with pytest.raises(LockError, match="Another context-hook update"):
            with acquire_lock(lock_file):
                pass

    def test_removes_stale_lock(self, tmp_path):
        lock_file = tmp_path / ".lock"
        # Write a PID that definitely doesn't exist
        lock_file.write_text("99999999")

        # Should succeed — stale lock is cleaned up
        with acquire_lock(lock_file):
            assert lock_file.exists()
            pid = int(lock_file.read_text().strip())
            assert pid == os.getpid()
        assert not lock_file.exists()

    def test_handles_malformed_lock(self, tmp_path):
        lock_file = tmp_path / ".lock"
        lock_file.write_text("not-a-number")

        # Should succeed — malformed lock is cleaned up
        with acquire_lock(lock_file):
            assert lock_file.exists()
        assert not lock_file.exists()

    def test_releases_on_exception(self, tmp_path):
        lock_file = tmp_path / ".lock"
        with pytest.raises(ValueError):
            with acquire_lock(lock_file):
                raise ValueError("test error")
        # Lock should be released even on exception
        assert not lock_file.exists()

    def test_creates_parent_directory(self, tmp_path):
        lock_file = tmp_path / "subdir" / ".lock"
        with acquire_lock(lock_file):
            assert lock_file.exists()
        assert not lock_file.exists()
