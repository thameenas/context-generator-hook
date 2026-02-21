"""CLI entry point for ctxgen."""

import click


@click.group()
def main():
    """Maintain a living project context file, updated on every git commit."""
    pass
