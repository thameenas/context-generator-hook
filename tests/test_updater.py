"""Tests for the updater module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from context_hook.config import Config
from context_hook.gemini import GeminiClient
from context_hook.updater import (
    update_context,
    _validate_context,
    NO_UPDATE,
)


@pytest.fixture
def config(tmp_path):
    """Create a config pointing to a temp directory."""
    return Config(project_root=tmp_path)


@pytest.fixture
def mock_client():
    """Create a mock Gemini client."""
    return MagicMock(spec=GeminiClient)


VALID_CONTEXT = """# Project Context

## Overview
A test project for testing.

## Architecture
Simple module-based architecture.

## Key Components
- Module A: handles things
- Module B: handles other things

## Dependencies
- pytest: testing framework

## Development Notes
Follow standard patterns.
"""


class TestUpdateContext:
    def test_generates_when_no_context_file(self, config, mock_client):
        """If CONTEXT.md doesn't exist, should do full generation."""
        mock_client.generate.return_value = VALID_CONTEXT

        with patch("context_hook.updater.generate_full_context") as mock_gen:
            mock_gen.return_value = VALID_CONTEXT
            result = update_context(config, mock_client)

        assert result.status == "generated"
        assert config.context_file.exists()
        assert config.context_file.read_text() == VALID_CONTEXT

    def test_skips_on_no_update(self, config, mock_client):
        """If LLM returns NO_UPDATE, context file should not change."""
        config.ensure_context_dir()
        config.context_file.write_text(VALID_CONTEXT)
        original = config.context_file.read_text()

        mock_client.generate.return_value = NO_UPDATE

        with patch("context_hook.updater.get_diff", return_value="- old\n+ new"):
            with patch("context_hook.updater.get_commit_message", return_value="fix typo"):
                result = update_context(config, mock_client)

        assert result.status == "skipped"
        assert config.context_file.read_text() == original

    def test_updates_on_valid_response(self, config, mock_client):
        """If LLM returns valid updated context, should write it."""
        config.ensure_context_dir()
        config.context_file.write_text(VALID_CONTEXT)

        updated = VALID_CONTEXT.replace("A test project", "An updated project")
        mock_client.generate.return_value = updated

        with patch("context_hook.updater.get_diff", return_value="- old\n+ new"):
            with patch("context_hook.updater.get_commit_message", return_value="update stuff"):
                result = update_context(config, mock_client)

        assert result.status == "updated"
        assert "updated project" in config.context_file.read_text()

    def test_skips_empty_diff(self, config, mock_client):
        """Empty diff should skip without calling LLM."""
        config.ensure_context_dir()
        config.context_file.write_text(VALID_CONTEXT)

        with patch("context_hook.updater.get_diff", return_value=""):
            with patch("context_hook.updater.get_commit_message", return_value="empty"):
                result = update_context(config, mock_client)

        assert result.status == "skipped"
        mock_client.generate.assert_not_called()

    def test_large_diff_uses_full_generation(self, config, mock_client):
        """Diffs exceeding max_diff_lines should fallback to full generation."""
        config.ensure_context_dir()
        config.context_file.write_text(VALID_CONTEXT)
        config.max_diff_lines = 5  # Very low threshold

        # Large diff
        large_diff = "\n".join([f"+ line {i}" for i in range(100)])
        mock_client.generate.return_value = VALID_CONTEXT

        with patch("context_hook.updater.get_diff", return_value=large_diff):
            with patch("context_hook.updater.get_commit_message", return_value="big change"):
                with patch("context_hook.updater.generate_full_context", return_value=VALID_CONTEXT) as mock_gen:
                    result = update_context(config, mock_client)

        # Should have fallen back to full generation
        assert result.status == "generated"
        mock_gen.assert_called_once()


class TestValidateContext:
    def test_empty_is_invalid(self):
        assert _validate_context("") is False

    def test_too_short_is_invalid(self):
        assert _validate_context("hello") is False

    def test_missing_sections_is_invalid(self):
        assert _validate_context("# Project Context\nSome text here.") is False

    def test_valid_context(self):
        assert _validate_context(VALID_CONTEXT) is True

    def test_partial_sections_valid(self):
        """At least 2 sections should be enough."""
        context = """# Project Context

## Overview
A test.

## Architecture  
Simple design.
Something else to make it long enough to validate.
"""
        assert _validate_context(context) is True
