"""Tests for the generator module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from context_hook.config import Config
from context_hook.gemini import GeminiClient, GeminiError
from context_hook.generator import generate_full_context


VALID_CONTEXT = """# Project Context

## Overview
A test project.

## Architecture
Simple.

## Key Components
- Main module

## Dependencies
- None

## Development Notes
Standard patterns.
"""


@pytest.fixture
def config(tmp_path):
    return Config(project_root=tmp_path)


@pytest.fixture
def mock_client():
    client = MagicMock(spec=GeminiClient)
    client.generate.return_value = VALID_CONTEXT
    return client


class TestGenerateFullContext:
    def test_generates_context(self, config, mock_client):
        with patch("context_hook.generator.get_file_tree", return_value=["main.py", "utils.py"]):
            with patch("context_hook.generator.get_file_contents", return_value={"main.py": "print('hi')"}):
                result = generate_full_context(config, mock_client)

        assert "# Project Context" in result
        mock_client.generate.assert_called_once()

    def test_raises_on_empty_repo(self, config, mock_client):
        with patch("context_hook.generator.get_file_tree", return_value=[]):
            with pytest.raises(RuntimeError, match="No tracked files"):
                generate_full_context(config, mock_client)

    def test_raises_on_empty_response(self, config, mock_client):
        mock_client.generate.return_value = ""

        with patch("context_hook.generator.get_file_tree", return_value=["main.py"]):
            with patch("context_hook.generator.get_file_contents", return_value={"main.py": "code"}):
                with pytest.raises(GeminiError, match="too short"):
                    generate_full_context(config, mock_client)

    def test_prompt_includes_file_tree(self, config, mock_client):
        with patch("context_hook.generator.get_file_tree", return_value=["main.py", "lib/utils.py"]):
            with patch("context_hook.generator.get_file_contents", return_value={}):
                generate_full_context(config, mock_client)

        prompt = mock_client.generate.call_args[0][0]
        assert "main.py" in prompt
        assert "lib/utils.py" in prompt

    def test_prompt_includes_file_contents(self, config, mock_client):
        contents = {"main.py": "def hello(): pass"}

        with patch("context_hook.generator.get_file_tree", return_value=["main.py"]):
            with patch("context_hook.generator.get_file_contents", return_value=contents):
                generate_full_context(config, mock_client)

        prompt = mock_client.generate.call_args[0][0]
        assert "def hello(): pass" in prompt
