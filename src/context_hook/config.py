"""Configuration management for context-hook."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from git import Repo, InvalidGitRepositoryError


# Relative paths (resolved against project root)
CONTEXT_DIR = ".context"
CONTEXT_FILE = ".context/CONTEXT.md"
CONFIG_FILE = ".context/config.json"
LOCK_FILE = ".context/.lock"
LOG_FILE = ".context/hook.log"


def find_project_root() -> Path:
    """Find the git repository root from the current working directory."""
    try:
        repo = Repo(Path.cwd(), search_parent_directories=True)
        return Path(repo.working_dir)
    except InvalidGitRepositoryError:
        raise RuntimeError(
            "Not inside a git repository. "
            "Run this command from within a git project."
        )


@dataclass
class Config:
    """Configuration with sensible defaults. Only GEMINI_API_KEY is required."""

    model: str = "gemini-2.0-flash"
    max_diff_lines: int = 1500
    max_log_entries: int = 100
    project_root: Path = field(default_factory=find_project_root)

    @property
    def context_dir(self) -> Path:
        return self.project_root / CONTEXT_DIR

    @property
    def context_file(self) -> Path:
        return self.project_root / CONTEXT_FILE

    @property
    def config_file(self) -> Path:
        return self.project_root / CONFIG_FILE

    @property
    def lock_file(self) -> Path:
        return self.project_root / LOCK_FILE

    @property
    def log_file(self) -> Path:
        return self.project_root / LOG_FILE

    @classmethod
    def load(cls) -> "Config":
        """Load config from .context/config.json, falling back to defaults."""
        config = cls()

        if config.config_file.exists():
            try:
                with open(config.config_file) as f:
                    data = json.load(f)
                if "model" in data:
                    config.model = data["model"]
                if "max_diff_lines" in data:
                    config.max_diff_lines = data["max_diff_lines"]
                if "max_log_entries" in data:
                    config.max_log_entries = data["max_log_entries"]
            except (json.JSONDecodeError, OSError):
                pass  # Ignore malformed config, use defaults

        return config

    def get_api_key(self) -> str:
        """Get Gemini API key from GEMINI_API_KEY environment variable."""
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable not set.\n"
                "Get a free API key at: https://aistudio.google.com/apikey"
            )
        return key

    def ensure_context_dir(self) -> None:
        """Create .context/ directory if it doesn't exist."""
        self.context_dir.mkdir(exist_ok=True)
