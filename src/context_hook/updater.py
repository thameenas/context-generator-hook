"""Incremental context updater. Called on every commit."""

from dataclasses import dataclass
from pathlib import Path

from context_hook.config import Config
from context_hook.gemini import GeminiClient, GeminiError
from context_hook.generator import generate_full_context
from context_hook.git import (
    get_diff,
    get_commit_message,
)

# Paths to prompt templates (relative to this file)
PROMPTS_DIR = Path(__file__).parent / "prompts"
INCREMENTAL_PROMPT = PROMPTS_DIR / "incremental_update.txt"

# Sentinel value the LLM returns when the diff is trivial
NO_UPDATE = "NO_UPDATE"


@dataclass
class UpdateResult:
    """Result of an update operation."""
    status: str    # "updated", "skipped", "generated", "error"
    message: str   # Human-readable description


def update_context(config: Config, client: GeminiClient) -> UpdateResult:
    """Main update orchestration — called on every commit.

    Flow:
    1. Read current CONTEXT.md (if missing, do full generation instead)
    2. Get diff + commit message
    3. Choose strategy based on diff size
    4. Call LLM
    5. If NO_UPDATE → skip
    6. Validate and write

    Returns:
        UpdateResult with status and message.
    """
    # 1. Read current context (or generate if missing)
    if not config.context_file.exists():
        return _do_full_generation(config, client)

    current_context = config.context_file.read_text()
    if not current_context.strip():
        return _do_full_generation(config, client)

    # 2. Get diff and commit message
    diff = get_diff()
    commit_message = get_commit_message()

    if not diff.strip():
        return UpdateResult("skipped", "Empty diff, nothing to update.")

    # 3. Choose strategy based on diff size
    diff_lines = diff.count("\n")

    if diff_lines <= config.max_diff_lines:
        result = _update_small_diff(client, current_context, diff, commit_message)
    else:
        # For large diffs, doing multiple LLM calls hits API rate limits.
        # Since Gemini has a massive context window, it's safer, faster, and
        # more accurate to just do a full regeneration.
        return _do_full_generation(config, client)

    # 4. Check for NO_UPDATE
    if result.strip() == NO_UPDATE:
        return UpdateResult("skipped", "LLM determined no context update needed.")

    # 5. Validate
    if not _validate_context(result):
        return UpdateResult(
            "error",
            "LLM response failed validation — context file not updated.",
        )

    # 6. Write
    config.ensure_context_dir()
    config.context_file.write_text(result)

    return UpdateResult("updated", f"Context updated ({diff_lines} diff lines).")


def _do_full_generation(config: Config, client: GeminiClient) -> UpdateResult:
    """Fallback: generate context from scratch when CONTEXT.md is missing."""
    result = generate_full_context(config, client)
    config.ensure_context_dir()
    config.context_file.write_text(result)
    return UpdateResult("generated", "No existing context — generated from full scan.")


def _update_small_diff(
    client: GeminiClient,
    current_context: str,
    diff: str,
    commit_message: str,
) -> str:
    """Handle normal-sized diffs with a single LLM call."""
    template = INCREMENTAL_PROMPT.read_text()
    prompt = template.format(
        current_context=current_context,
        diff=diff,
        commit_message=commit_message,
    )
    return client.generate(prompt)





def _validate_context(content: str) -> bool:
    """Basic structural validation of LLM output.

    Checks:
    - Not empty
    - Contains the main header
    - Contains at least 2 expected sections
    - Not suspiciously short
    """
    if not content or not content.strip():
        return False

    if len(content.strip()) < 50:
        return False

    # Check for expected structure
    expected_sections = [
        "## Overview",
        "## Architecture",
        "## Core Workflows",
        "## Data Models",
        "## API",
        "## Key Components",
        "## Dependencies",
        "## Development Notes",
    ]
    found = sum(1 for s in expected_sections if s in content)

    return found >= 2
