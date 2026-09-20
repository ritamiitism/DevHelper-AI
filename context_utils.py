"""Project inspection helpers shared by the CLI tools and Streamlit UI."""
import os

# Extensions we show inline; everything else is listed but not previewed.
TEXT_EXTENSIONS = {
    ".py", ".txt", ".md", ".json", ".toml", ".cfg", ".ini", ".yml", ".yaml",
    ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".csv", ".env.example",
}
MAX_PREVIEW_CHARS = 5000
MAX_TREE_ENTRIES = 500
# Never execute or even preview these; listed only.
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".idea", ".vscode"}


def build_project_tree(root: str, max_entries: int = MAX_TREE_ENTRIES) -> list[str]:
    """Return a sorted, indented file listing capped at *max_entries*."""
    lines: list[str] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        filenames = sorted(filenames)
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        indent = "  " * depth
        if rel != ".":
            lines.append(f"{'  ' * (depth - 1)}{os.path.basename(dirpath)}/")
        for name in filenames:
            if len(lines) >= max_entries:
                truncated = True
                break
            lines.append(f"{indent}{name}")
        if truncated or len(lines) >= max_entries:
            truncated = True
            break
    if truncated:
        lines.append(f"... (truncated at {max_entries} entries)")
    return lines


def collect_file_inventory(root: str) -> dict:
    """Walk *root* and return counts + code files for context selection."""
    total_files = 0
    total_bytes = 0
    code_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in filenames:
            total_files += 1
            full = os.path.join(dirpath, name)
            try:
                total_bytes += os.path.getsize(full)
            except OSError:
                continue
            rel = os.path.relpath(full, root)
            _, ext = os.path.splitext(name)
            if ext.lower() in TEXT_EXTENSIONS or ext == "":
                code_files.append(rel)
    code_files.sort()
    return {"total_files": total_files, "total_bytes": total_bytes, "text_files": code_files}


def build_context_summary(root: str) -> str:
    """Small human-readable summary passed around the UI and (later) retrieval.

    EXTENSION POINT: future token-efficient retrieval should replace/augment
    this — e.g. pick top-K relevant files via keyword/embedding search and
    pass only those to the agent — instead of sending the whole project.
    Currently the CLI agent pulls files itself via tools, so the full project
    simply needs to be on disk at *root*; this summary is informational only.
    """
    inv = collect_file_inventory(root)
    lines = [
        f"Project root: {root}",
        f"Files: {inv['total_files']} ({inv['total_bytes']} bytes)",
        f"Text files ({len(inv['text_files'])}):",
    ]
    lines.extend(f" - {p}" for p in inv["text_files"][:100])
    if len(inv["text_files"]) > 100:
        lines.append(f" ... and {len(inv['text_files']) - 100} more")
    return "\n".join(lines)
