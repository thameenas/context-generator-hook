# context-generator-hook

A git post-commit hook that automatically maintains a living project context file (`.context/CONTEXT.md`) using **Gemini AI**. Designed for solo developers and hobby projects.

## Why?

LLMs waste tokens re-scanning your codebase every session. This tool keeps a lightweight, structured summary updated on every commit — so future LLM interactions have instant context.

## How it works

```
You commit → post-commit hook fires → ctxgen reads the diff
→ Gemini decides if the context needs updating → CONTEXT.md is updated
→ You review and commit the changes (if any)
```

- **Trivial commits** (typos, formatting) are detected and skipped
- **Large diffs** are chunked per-file and summarized individually before merging
- The hook runs in the background — **your commits are never blocked**
- Failures are logged, never raised

## Setup

### 1. Install

```bash
# Clone the repo
git clone <repo-url>
cd context-generator-hook

# Install with uv
uv sync
```

### 2. Set your API key

Get a free Gemini API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

```bash
export GEMINI_API_KEY="your-key-here"
```

Add it to your shell profile (`~/.zshrc`, `~/.bashrc`) to persist it.

### 3. Initialize context in your project

```bash
cd /path/to/your/project
ctxgen init
```

This scans your codebase and generates `.context/CONTEXT.md`.

### 4. Install the git hook

```bash
ctxgen install-hook
```

Done! Every future commit will automatically update your context file.

## Commands

| Command | Description |
|---|---|
| `ctxgen init` | Scan codebase and generate initial `.context/CONTEXT.md` |
| `ctxgen update` | Update context from latest commit diff (called by hook) |
| `ctxgen regenerate` | Rebuild context from scratch |
| `ctxgen install-hook` | Install post-commit hook into `.git/hooks/` |

## Configuration (optional)

Create `.context/config.json` in your project to override defaults:

```json
{
    "model": "gemini-2.5-flash",
    "max_diff_lines": 1500,
    "max_log_entries": 100
}
```

| Setting | Default | Description |
|---|---|---|
| `model` | `gemini-2.5-flash` | Gemini model to use |
| `max_diff_lines` | `1500` | Diffs above this are chunked per-file |
| `max_log_entries` | `100` | Max entries in `.context/hook.log` |

## Generated files

All files live in `.context/` at your project root:

```
.context/
├── CONTEXT.md      # The living context file
├── config.json     # Optional configuration
├── hook.log        # Update log (timestamps, statuses)
└── .lock           # Lockfile (auto-managed)
```

## Running tests

```bash
uv run pytest tests/ -v
```

## Design principles

- **Context is assistive, not authoritative** — the codebase is the source of truth
- **Git hooks never block commits** — everything runs in the background
- **Failures are graceful** — errors are logged, not raised
- **All AI content is reviewable** — the human commits the context file manually
