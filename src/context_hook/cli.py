"""CLI entry point for ctxgen."""

import sys
import click

from context_hook.config import Config
from context_hook.gemini import GeminiClient, GeminiError
from context_hook.lockfile import acquire_lock, LockError
from context_hook.logger import log_entry, trim_log


@click.group()
def main():
    """Maintain a living project context file, updated on every git commit."""
    pass


@main.command()
def init():
    """Initialize context for this project. Scans codebase and generates .context/CONTEXT.md."""
    from context_hook.generator import generate_full_context

    try:
        config = Config.load()
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Check if context already exists
    if config.context_file.exists():
        if not click.confirm(
            f"{config.context_file} already exists. Overwrite?",
            default=False,
        ):
            click.echo("Aborted.")
            return

    # Get API key
    try:
        api_key = config.get_api_key()
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    client = GeminiClient(api_key=api_key, model=config.model)

    click.echo("Scanning codebase...")
    try:
        result = generate_full_context(config, client)
    except (GeminiError, RuntimeError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    config.ensure_context_dir()
    config.context_file.write_text(result)
    click.echo(f"Context generated at {config.context_file}")


@main.command()
def update():
    """Update context from latest commit diff. Called by post-commit hook.

    This command is designed to run in the background. It never exits
    with a non-zero code — errors are logged, not raised.
    """
    from context_hook.updater import update_context

    try:
        config = Config.load()
        api_key = config.get_api_key()
        client = GeminiClient(api_key=api_key, model=config.model)

        with acquire_lock(config.lock_file):
            result = update_context(config, client)

        log_entry(config.log_file, "UPDATE", result.status, result.message)
        trim_log(config.log_file, config.max_log_entries)

    except LockError as e:
        # Another update is running — skip silently
        try:
            config = Config.load()
            log_entry(config.log_file, "UPDATE", "SKIPPED", str(e))
        except Exception:
            pass

    except Exception as e:
        # Catch everything — this must never crash
        try:
            config = Config.load()
            log_entry(config.log_file, "UPDATE", "ERROR", str(e))
        except Exception:
            pass


@main.command()
def regenerate():
    """Rebuild context from scratch by scanning the full codebase."""
    from context_hook.generator import generate_full_context

    try:
        config = Config.load()
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if config.context_file.exists():
        if not click.confirm(
            "This will overwrite the existing CONTEXT.md. Continue?",
            default=False,
        ):
            click.echo("Aborted.")
            return

    try:
        api_key = config.get_api_key()
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    client = GeminiClient(api_key=api_key, model=config.model)

    click.echo("Scanning codebase...")
    try:
        result = generate_full_context(config, client)
    except (GeminiError, RuntimeError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    config.ensure_context_dir()
    config.context_file.write_text(result)
    click.echo(f"Context regenerated at {config.context_file}")


@main.command()
def install_hook():
    """Install the post-commit hook into .git/hooks/."""
    try:
        config = Config.load()
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    hooks_dir = config.project_root / ".git" / "hooks"
    hook_file = hooks_dir / "post-commit"

    # Read our hook template
    hook_template = (
        '#!/bin/sh\n'
        '# ctxgen: Post-commit hook to update project context\n'
        '# This runs in the background and never blocks your commit.\n'
        '\n'
        'if command -v ctxgen >/dev/null 2>&1; then\n'
        '    nohup ctxgen update >> .context/hook.log 2>&1 &\n'
        'fi\n'
    )

    ctxgen_marker = "ctxgen update"

    if hook_file.exists():
        existing = hook_file.read_text()
        if ctxgen_marker in existing:
            click.echo("Hook already installed.")
            return

        # Append our command to existing hook
        click.echo("Existing post-commit hook found — appending ctxgen.")
        with open(hook_file, "a") as f:
            f.write(
                '\n# ctxgen: Post-commit hook to update project context\n'
                'if command -v ctxgen >/dev/null 2>&1; then\n'
                '    nohup ctxgen update >> .context/hook.log 2>&1 &\n'
                'fi\n'
            )
    else:
        hooks_dir.mkdir(exist_ok=True)
        hook_file.write_text(hook_template)

    # Make executable
    hook_file.chmod(0o755)
    click.echo(f"Post-commit hook installed at {hook_file}")
