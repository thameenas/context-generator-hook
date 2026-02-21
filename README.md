# context-generator-hook

A git post-commit hook that automatically maintains a living project context file (`.context/CONTEXT.md`) using **Gemini**.

## Why?

Maintaining a project context file is great for LLM-assisted development - but keeping it up to date is easy to forget. This tool automates it by hooking into your git workflow, so your context file stays current without any extra effort.

## How it works

```
You commit → post-commit hook fires → ctxgen reads the diff
→ Gemini decides if the context needs updating → CONTEXT.md is updated
→ You review and commit the changes (if any)
```

- **Trivial commits** (typos, formatting) are detected and skipped
- **Large diffs** overflow the incremental update limits and trigger a full context regeneration, keeping your updates safely within API rate limits
- The hook runs in the background — **your commits are never blocked**
- Failures are logged, never raised

## Quick start

### 1. Install `ctxgen` globally

**With uv (recommended):**
```bash
uv tool install git+https://github.com/thameenas/context-generator-hook.git
```

**With pipx:**
```bash
pipx install git+https://github.com/thameenas/context-generator-hook.git
```

**From source:**
```bash
git clone https://github.com/thameenas/context-generator-hook.git
cd context-generator-hook
uv tool install .
```

After install, `ctxgen` is available globally - use it in any project.

### 2. Set your Gemini API key

Used gemini here assuming that the free version should be enough for this purpose. Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

```bash
# Add to your shell profile (~/.zshrc or ~/.bashrc)
export GEMINI_API_KEY="your-key-here"
```

### 3. Set up your project

```bash
cd /path/to/your/project

# Generate initial context from your codebase
ctxgen init

# Install the post-commit hook
ctxgen install-hook
```

That's it! Every future commit will automatically update `.context/CONTEXT.md`. Review the changes and commit them when you're happy.

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
