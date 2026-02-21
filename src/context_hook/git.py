"""Git operations for context-hook."""

from pathlib import Path
from git import Repo, InvalidGitRepositoryError

# Empty tree hash — used to diff against when there's no parent commit
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf899d15363d7d95f"

# Directories and patterns to exclude from file tree scans
EXCLUDE_DIRS = {
    ".git", ".context", "node_modules", "__pycache__", ".venv",
    "venv", ".env", ".tox", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".eggs", "*.egg-info",
    # Java / Gradle / Maven
    "target", ".gradle", ".idea", "out", "bin",
}

# Binary file extensions to skip when reading contents
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".tar", ".gz", ".bz2",
    ".pyc", ".pyo", ".so", ".dylib", ".dll",
    ".exe", ".bin", ".dat", ".db", ".sqlite",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
}

# Files to prioritize when reading contents (in order)
PRIORITY_FILES = [
    "README.md", "README", "README.rst", "README.txt",
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
    "setup.py", "setup.cfg",
    "main.py", "app.py", "index.ts", "index.js", "main.go", "main.rs",
    "Makefile", "Dockerfile", "docker-compose.yml",
]


def get_repo() -> Repo:
    """Get the git repo from current working directory."""
    return Repo(Path.cwd(), search_parent_directories=True)


def get_diff() -> str:
    """Get the full unified diff of the latest commit (HEAD~1..HEAD).

    If this is the first commit (no parent), diffs against the empty tree.
    Returns the diff as a string.
    """
    repo = get_repo()
    head = repo.head.commit

    if head.parents:
        parent = head.parents[0]
        return repo.git.diff(parent.hexsha, head.hexsha)
    else:
        # First commit — diff against empty tree
        return repo.git.diff(EMPTY_TREE_SHA, head.hexsha)


def get_diff_file_chunks() -> list[dict]:
    """Get the diff split by file for large diff chunking.

    Returns a list of dicts:
        {'file': str, 'diff': str, 'status': str}
    where status is 'added', 'modified', 'deleted', or 'renamed'.
    """
    repo = get_repo()
    head = repo.head.commit

    if head.parents:
        parent = head.parents[0]
        diffs = parent.diff(head, create_patch=True)
    else:
        diffs = head.diff(EMPTY_TREE_SHA, create_patch=True, R=True)

    chunks = []
    for diff_item in diffs:
        # Determine file path
        file_path = diff_item.b_path or diff_item.a_path

        # Determine status
        if diff_item.new_file:
            status = "added"
        elif diff_item.deleted_file:
            status = "deleted"
        elif diff_item.renamed_file:
            status = "renamed"
        else:
            status = "modified"

        # Get the patch (diff text)
        try:
            patch = diff_item.diff.decode("utf-8", errors="replace")
        except (AttributeError, UnicodeDecodeError):
            patch = str(diff_item.diff)

        if patch:  # Skip empty diffs (binary files, etc.)
            chunks.append({
                "file": file_path,
                "diff": patch,
                "status": status,
            })

    return chunks


def get_commit_message() -> str:
    """Get the commit message of HEAD."""
    repo = get_repo()
    return repo.head.commit.message.strip()


def get_file_tree() -> list[str]:
    """Get list of all tracked file paths, excluding irrelevant directories.

    Returns sorted list of relative file paths.
    """
    repo = get_repo()
    root = Path(repo.working_dir)
    tracked_files = []

    for item in repo.tree().traverse():
        if item.type != "blob":
            continue

        path = item.path
        # Skip excluded directories
        parts = Path(path).parts
        if any(part in EXCLUDE_DIRS for part in parts):
            continue

        # Skip binary files
        if Path(path).suffix.lower() in BINARY_EXTENSIONS:
            continue

        tracked_files.append(path)

    return sorted(tracked_files)


def get_file_contents(
    paths: list[str],
    max_total_chars: int = 50_000,
) -> dict[str, str]:
    """Read contents of specified files, respecting a total character budget.

    Files are read in the order given. Reading stops when the budget
    is exhausted. Binary files and unreadable files are skipped.

    Returns dict of {path: content}.
    """
    repo = get_repo()
    root = Path(repo.working_dir)
    contents = {}
    chars_used = 0

    for path in paths:
        if chars_used >= max_total_chars:
            break

        full_path = root / path
        if not full_path.is_file():
            continue

        if full_path.suffix.lower() in BINARY_EXTENSIONS:
            continue

        try:
            text = full_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue

        # Respect budget — include file only if it fits (or partially)
        remaining = max_total_chars - chars_used
        if len(text) > remaining:
            text = text[:remaining] + "\n... (truncated)"

        contents[path] = text
        chars_used += len(text)

    return contents


def get_prioritized_file_list(file_tree: list[str]) -> list[str]:
    """Sort file tree with priority files first, then by path depth (shallower first).

    This determines the order in which files are read during full generation.
    """
    priority_set = {f.lower() for f in PRIORITY_FILES}

    def sort_key(path: str):
        name = Path(path).name.lower()
        # Priority files get index 0, others get index 1
        is_priority = 0 if name in priority_set else 1
        # Then sort by depth (shallower first), then alphabetically
        depth = len(Path(path).parts)
        return (is_priority, depth, path)

    return sorted(file_tree, key=sort_key)
