"""Full context generation from codebase scan. Used by init and regenerate."""

from pathlib import Path

from context_hook.config import Config
from context_hook.gemini import GeminiClient, GeminiError
from context_hook.git import (
    get_file_tree,
    get_file_contents,
    get_prioritized_file_list,
)


# Path to prompt template (relative to this file)
PROMPT_FILE = Path(__file__).parent / "prompts" / "full_generation.txt"


def generate_full_context(config: Config, client: GeminiClient) -> str:
    """Generate complete CONTEXT.md by scanning the codebase.

    Flow:
    1. Get tracked file tree from git
    2. Prioritize files (README, configs, entry points first)
    3. Read file contents within character budget
    4. Format the full generation prompt
    5. Call Gemini to generate context
    6. Validate and return

    Args:
        config: Project configuration.
        client: Initialized Gemini client.

    Returns:
        Generated context markdown string.

    Raises:
        GeminiError: If the LLM call fails.
    """
    # 1. Get file tree
    file_tree = get_file_tree()
    if not file_tree:
        raise RuntimeError("No tracked files found in repository.")

    # 2. Prioritize files
    prioritized = get_prioritized_file_list(file_tree)

    # 3. Read file contents (within budget)
    contents = get_file_contents(prioritized, max_total_chars=50_000)

    # 4. Format prompt
    prompt_template = PROMPT_FILE.read_text()

    file_tree_str = "\n".join(f"  {f}" for f in file_tree)
    file_contents_str = _format_file_contents(contents)

    prompt = prompt_template.format(
        file_tree=file_tree_str,
        file_contents=file_contents_str,
    )

    # 5. Call LLM
    result = client.generate(prompt)

    # 6. Basic validation
    if not result or len(result.strip()) < 50:
        raise GeminiError("Generated context is too short — likely an error.")

    return result


def _format_file_contents(contents: dict[str, str]) -> str:
    """Format file contents for inclusion in the prompt.

    Each file is wrapped with a clear header and separator.
    """
    parts = []
    for path, text in contents.items():
        parts.append(f"--- {path} ---")
        parts.append(text)
        parts.append("")  # blank line between files

    return "\n".join(parts)
