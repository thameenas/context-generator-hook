# Project Context

## Overview
This project, `context-generator-hook` (or `ctxgen`), is a Python CLI tool that automates the maintenance of a living project context file (`.context/CONTEXT.md`) using Google's Gemini AI. It operates primarily as a `git post-commit` hook, automatically detecting changes in a repository, generating or updating the context file based on these changes, and logging its activities. The core purpose is to provide an always-current, AI-generated technical overview of a codebase for LLM-assisted development, without requiring manual updates. It is built with Python, `click` for CLI, `gitpython` for Git interaction, and `google-genai` for LLM communication.

## Architecture
The system follows a modular, event-driven architecture triggered by Git commit events.
1.  **CLI-driven**: All interactions are via a `ctxgen` command-line interface.
2.  **Git Hook Integration**: A `post-commit` Git hook is installed, which asynchronously executes the `ctxgen update` command in the background (`nohup ... &`) to avoid blocking user commits.
3.  **LLM-Centric Logic**: Gemini AI models are central to generating and incrementally updating the context, utilizing specialized prompts for full generation and incremental updates. 
4.  **Graceful Failure**: The `update` command is designed to never crash, logging errors instead, adhering to the principle that Git hooks should not interfere with the user's workflow.
5.  **State Management**: Project-specific state (context file, logs, configuration, lock file) is managed within a `.context/` directory at the repository root. Changes within this directory are ignored when determining if a context update is needed.
6.  **Concurrency Control**: A PID-based lockfile prevents multiple `ctxgen update` processes from running simultaneously within the same repository.

## Core Workflows
### 1. Project Initialization (`ctxgen init`)
-   User executes `ctxgen init`.
-   The system loads project-specific configuration from `.context/config.json` or uses defaults.
-   It discovers the Git repository root and identifies all tracked files, excluding `.git/`, `.context/`, and common build/dependency directories.
-   Files are prioritized (e.g., `README.md`, `pyproject.toml`, main entry points).
-   Contents of prioritized files are read within a `max_total_chars` budget.
-   A "full generation" prompt (`full_generation.txt`) is constructed, including the file tree and contents.
-   The prompt is sent to the configured Gemini model via `GeminiClient`.
-   The generated markdown content is validated (minimum length, header/section presence).
-   The `.context/CONTEXT.md` file is created or overwritten with the AI-generated content.

### 2. Context Update on Commit (`ctxgen update`)
-   A `git post-commit` hook (created by `ctxgen install-hook`) triggers `ctxgen update` asynchronously in the background.
-   A process-level lock is attempted via `.context/.lock`. If another `ctxgen update` is active or a stale lock is found, the update is skipped or the lock is acquired after cleanup.
-   The current `CONTEXT.md` is read. If missing or empty, a full generation (Workflow 1) is performed as a fallback.
-   The `git diff` for the latest commit and the `commit message` are retrieved. Changes within directories defined in `EXCLUDE_DIRS` (including `.context/`) are explicitly excluded from this diff to prevent cyclical updates.
-   If the diff is empty, the update is skipped.
-   **Diff Processing Strategy**:
    -   **Small Diffs** (lines <= `max_diff_lines`): An "incremental update" prompt (`incremental_update.txt`) is constructed, including the current `CONTEXT.md`, the full diff, and the commit message. The prompt is sent to Gemini.
    -   **Large Diffs** (lines > `max_diff_lines`): For large diffs, an incremental update is skipped, and a full context regeneration (Workflow 1) is performed as a fallback to ensure context accuracy and avoid API rate limits from multi-stage processing.
-   If the LLM's response is `NO_UPDATE` (a sentinel value), the update is skipped.
-   The LLM's generated content is validated.
-   A log entry (`action: UPDATE`, `status: updated/skipped/generated/error`, `message`) is appended to `.context/hook.log`, which is then trimmed to `max_log_entries`.

### 3. Context Regeneration (`ctxgen regenerate`)
-   User executes `ctxgen regenerate`.
-   Similar to `init`, but explicitly confirms overwrite if `CONTEXT.md` exists. It forces a full context scan and generation, ignoring any existing context.

### 4. Hook Installation (`ctxgen install-hook`)
-   User executes `ctxgen install-hook`.
-   A shell script is written (or appended to) `.git/hooks/post-commit` to execute `nohup ctxgen update >> .context/hook.log 2>&1 &`.
-   The hook file is made executable (`chmod 0o755`).

## Data Models & State
1.  **`Config` (`src/context_hook/config.py`)**:
    *   `model: str` (default: `gemini-2.5-flash`): The Gemini model to use.
    *   `max_diff_lines: int` (default: `1500`): Threshold for diff size to trigger chunked processing.
    *   `max_log_entries: int` (default: `100`): Maximum entries to retain in `hook.log`.
    *   `project_root: Path`: Absolute path to the Git repository root.
    *   `context_dir: Path` (`.context/`): Directory for generated files.
    *   `context_file: Path` (`.context/CONTEXT.md`): The main context output.
    *   `config_file: Path` (`.context/config.json`): User-overridable configuration.
    *   `lock_file: Path` (`.context/.lock`): PID-based concurrency lock.
    *   `log_file: Path` (`.context/hook.log`): Operational log.
    *   **Loading**: Static method `Config.load()` finds `project_root` via `gitpython`, then loads overrides from `config_file`.
    *   **API Key**: `get_api_key()` retrieves `GEMINI_API_KEY` from environment variables, raising `RuntimeError` if not set.
2.  **`UpdateResult` (`src/context_hook/updater.py`)**:
    *   `status: str`: "updated", "skipped", "generated", "error".
    *   `message: str`: Human-readable description of the update outcome.
3.  **Git Objects (from `gitpython`)**: Internally used `Repo`, `Commit`, `Diff` objects to interact with the Git repository.
4.  **LLM Prompt Templates (`src/context_hook/prompts/*.txt`)**: Define the structure and rules for LLM interactions.
5.  **`.context/CONTEXT.md`**: Markdown file, adheres to a strict section-based format (e.g., `# Project Context`, `## Overview`) and always ends with a newline character.
6.  **`.context/.lock`**: Text file containing the PID of the process currently holding the lock.
7.  **`.context/hook.log`**: Plain text file, line-delimited log entries. Timestamps are recorded in the system's local timezone with an ISO-8601 offset, following the format `[ISO-8601 timestamp with local timezone offset] [ACTION] [STATUS] message`. 

## API & Interfaces
### CLI Commands (via `ctxgen` entry point):
*   `ctxgen init`: Scans codebase and generates initial `.context/CONTEXT.md`.
*   `ctxgen update`: Updates context from latest commit diff (designed for background hook execution).
*   `ctxgen regenerate`: Rebuilds context from scratch, overwriting existing `CONTEXT.md`.
*   `ctxgen install-hook`: Installs the `post-commit` Git hook into `.git/hooks/`.

### External API:
*   **Google Gemini API**: Accessed via `google-genai` SDK.
    *   `GeminiClient.generate(prompt: str, max_retries: int = 3) -> str`: Sends a text prompt to the configured Gemini model, returns generated text. Includes retry logic with exponential backoff for `429 RESOURCE_EXHAUSTED` (rate limit) errors. Handles `GeminiError` for API failures. Strips common markdown code block wrappers (e.g., ````markdown````, ```` ``` `) from the beginning and end of the generated text before returning it.

### Internal Module Interfaces:
*   **`context_hook.config`**:
    *   `Config.load() -> Config`: Factory method to load configuration.
    *   `Config.get_api_key() -> str`: Retrieves API key from `GEMINI_API_KEY` env var.
    *   `Config.ensure_context_dir() -> None`: Creates the `.context/` directory.
*   **`context_hook.gemini`**:
    *   `GeminiClient(api_key: str, model: str)`: Initializes the client.
*   **`context_hook.generator`**:
    *   `generate_full_context(config: Config, client: GeminiClient) -> str`: Orchestrates full context generation.
*   **`context_hook.git`**:
    *   `get_diff() -> str`: Returns the unified diff of the latest commit, explicitly excluding changes within directories defined in `EXCLUDE_DIRS`.
    *   `get_commit_message() -> str`: Returns the commit message of HEAD.
    *   `get_file_tree() -> list[str]`: Returns a sorted list of tracked file paths.
    *   `get_file_contents(paths: list[str], max_total_chars: int) -> dict[str, str]`: Reads file contents up to a total character limit.
    *   `get_prioritized_file_list(file_tree: list[str]) -> list[str]`: Sorts file paths by priority (e.g., `README.md` first, then by depth).
*   **`context_hook.lockfile`**:
    *   `acquire_lock(lock_file: Path)`: A context manager that creates and manages a PID-based lock file. Raises `LockError` if lock cannot be acquired (e.g., process with PID is alive).
*   **`context_hook.logger`**:
    *   `log_entry(log_file: Path, action: str, status: str, message: str) -> None`: Appends an entry to the log file.
    *   `trim_log(log_file: Path, max_entries: int) -> None`: Trims the log file to a specified number of entries.
*   **`context_hook.updater`**:
    *   `update_context(config: Config, client: GeminiClient) -> UpdateResult`: Orchestrates incremental context updates. For large diffs, it now falls back to full context generation rather than chunking and merging.
    *   `_validate_context(content: str) -> bool`: Performs basic structural validation on LLM output (minimum length, header count).

## Key Components
*   `src/context_hook/cli.py`: Defines the command-line interface, parsing arguments and coordinating calls to core logic.
*   `src/context_hook/config.py`: Manages project configuration (defaults, user overrides, API key retrieval, path resolution).
*   `src/context_hook/gemini.py`: Provides a standardized interface for interacting with the Google Gemini API. It includes error handling, retry logic, and post-processes LLM responses to strip markdown code block wrappers.
*   `src/context_hook/generator.py`: Implements the logic for generating a complete context file from a full codebase scan.
*   `src/context_hook/git.py`: Encapsulates all interactions with the local Git repository, such as reading diffs (now explicitly excluding changes within `EXCLUDE_DIRS`), file trees, and file contents.
*   `src/context_hook/lockfile.py`: Implements a robust PID-based file locking mechanism to prevent race conditions during concurrent updates.
*   `src/context_hook/logger.py`: Provides simple, file-based logging utilities for tracking hook execution and outcomes.
*   `src/context_hook/prompts/`: A directory containing various `.txt` files that serve as templates for LLM prompts, guiding the AI's behavior for different tasks (full generation, incremental updates). The chunk summary and merge summaries prompts have been removed.
*   `src/context_hook/updater.py`: Contains the core intelligence for determining update strategy (small vs. large diff). It now orchestrates LLM calls for incremental updates on small diffs and triggers a full regeneration for large diffs, and ensures the final `CONTEXT.md` is written ending with a newline character.

## Dependencies & Environment
### Python Dependencies (from `pyproject.toml`):
*   `google-genai>=1.0.0`: Primary dependency for interacting with the Gemini API.
*   `click>=8.0`: Used for building the command-line interface.
*   `gitpython>=3.1`: Provides Pythonic access to Git repositories for diffing, file tree traversal, etc.
*   `hatchling`: Build backend for packaging the project.
*   `pytest>=8.0` (dev dependency): Testing framework.

### Environment Variables:
*   `GEMINI_API_KEY`: Required environment variable containing the Google Gemini API key. The `Config.get_api_key()` method checks for this.

### Configuration Files:
*   `.context/config.json`: An optional JSON file within the project's `.context/` directory for overriding default settings (e.g., `model`, `max_diff_lines`, `max_log_entries`).

## Development Notes
*   **Python Version**: Requires Python 3.11 or higher.
*   **Design Principles**: Adheres to principles like "context is assistive, not authoritative," "Git hooks never block commits," "failures are graceful," and "all AI content is reviewable."
*   **Concurrency Handling**: Employs a file-based PID lock to ensure only one `ctxgen update` process runs at a time for a given repository. Stale or malformed lock files are automatically cleaned up.
*   **LLM Input Management**:
    *   File contents for full generation are read within a `max_total_chars` budget (default 50,000 characters).
    *   Files are prioritized (`README.md`, `pyproject.toml`, etc.) and shallow files are preferred when reading contents to fit within the token budget.
    *   Large Git diffs now trigger a full context regeneration instead of incremental updates, ensuring comprehensive updates while avoiding token and rate limit issues. Changes to files within directories defined in `EXCLUDE_DIRS` are ignored when generating diffs for updates.
*   **Error Handling**: The `ctxgen update` command is designed to catch all exceptions and log them to `.context/hook.log` rather than raising them, ensuring the `post-commit` hook never fails the Git operation. It also now normalizes LLM output by stripping markdown wrappers and ensures the context file ends with a newline. Log entries now capture timestamps in the system's local timezone for easier debugging.
*   **Prompt Engineering**: Relies heavily on distinct prompt templates (`full_generation.txt`, `incremental_update.txt`) to guide the LLM's output for specific tasks and to enforce the desired output format (e.g., "Respond with ONLY the markdown content. No explanations..."). The `GeminiClient` now automatically strips common markdown wrappers from LLM responses to ensure clean output.
*   **Context Validation**: Basic structural validation (`_validate_context`) is performed on LLM output to ensure it's not empty, too short, or missing fundamental sections before writing to `CONTEXT.md`. Output is pre-processed by `GeminiClient` to strip markdown wrappers and ensure a trailing newline.
*   **Ignored Files**: `git.py` explicitly excludes common directories (`.git`, `node_modules`, `venv`, etc.) and binary file extensions from file tree scanning and content reading.
