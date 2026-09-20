"""Safe ZIP extraction + project-root detection for uploaded projects."""
import io
import os
import zipfile


class ZipError(ValueError):
    """Raised for invalid / unsafe / empty ZIP uploads."""


def safe_extract_zip(zip_bytes: bytes, dest_dir: str) -> list[str]:
    """Extract *zip_bytes* into *dest_dir* safely, return relative paths.

    Guards:
    - rejects invalid/corrupted archives (BadZipFile -> ZipError)
    - rejects empty archives
    - blocks absolute paths, drive letters, and '..' traversal members
    - skips directory entries themselves (creates parents as needed)
    Does not touch the original uploaded bytes.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise ZipError(f"Invalid or corrupted ZIP file: {e}")
    with zf:
        members = zf.infolist()
        if not members:
            raise ZipError("The ZIP archive is empty.")
        # Filter out pure directory entries when checking emptiness:
        # a ZIP with only empty dirs is still "empty" for our purposes.
        file_members = [m for m in members if not m.is_dir()]
        if not file_members:
            raise ZipError("The ZIP archive contains no files.")
        dest_abs = os.path.abspath(dest_dir)
        extracted: list[str] = []
        for member in file_members:
            name = member.filename
            # Zip spec uses forward slashes; normalise for checks.
            norm = name.replace("\\", "/")
            # Block absolute paths, drive letters, leading slashes.
            if norm.startswith("/") or norm.startswith("~"):
                raise ZipError(f"Blocked unsafe path in ZIP: {name!r}")
            if len(norm) > 1 and norm[1] == ":":
                raise ZipError(f"Blocked unsafe path in ZIP: {name!r}")
            parts = norm.split("/")
            if ".." in parts:
                raise ZipError(f"Blocked path traversal in ZIP: {name!r}")
            # Resolve final target and confirm it stays inside dest_dir.
            target_abs = os.path.abspath(os.path.join(dest_abs, *parts))
            try:
                inside = os.path.commonpath([dest_abs, target_abs]) == dest_abs
            except ValueError:
                inside = False
            if not inside:
                raise ZipError(f"Blocked path traversal in ZIP: {name!r}")
            parent = os.path.dirname(target_abs)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with zf.open(member, "r") as src, open(target_abs, "wb") as dst:
                dst.write(src.read())
            extracted.append(os.path.relpath(target_abs, dest_abs))
        return extracted


def create_project_zip(project_root: str) -> bytes:
    """Zip the (possibly agent-modified) project at *project_root*.

    Returns the ZIP file bytes, with paths relative to *project_root* so
    re-uploading the download works with detect_project_root().
    Raises ZipError when there is nothing to zip or the tree is too large.
    """
    if not os.path.isdir(project_root):
        raise ZipError("Project directory is missing; cannot build download.")
    buf = io.BytesIO()
    total_bytes = 0
    file_count = 0
    # Cap the in-memory ZIP so a runaway agent output can't exhaust RAM.
    MAX_TOTAL_BYTES = 200 * 1024 * 1024
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _dirnames, filenames in os.walk(project_root):
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                total_bytes += size
                if total_bytes > MAX_TOTAL_BYTES:
                    raise ZipError("Project is too large to download (over 200 MB).")
                arcname = os.path.relpath(full, project_root).replace(os.sep, "/")
                zf.write(full, arcname)
                file_count += 1
    if file_count == 0:
        raise ZipError("Project contains no files to download.")
    return buf.getvalue()


def detect_project_root(extract_dir: str) -> str:
    """Return the real project root inside *extract_dir*.

    - If the archive held a single top-level folder, return that folder.
    - Otherwise return *extract_dir* itself.
    Raises ZipError when nothing was extracted.
    """
    entries = [e for e in os.listdir(extract_dir)]
    if not entries:
        raise ZipError("Extraction produced no files; cannot determine project root.")
    if len(entries) == 1:
        single = os.path.join(extract_dir, entries[0])
        if os.path.isdir(single):
            children = os.listdir(single)
            if not children:
                return extract_dir
            markers = {
                "package.json", "pyproject.toml", "setup.py", "setup.cfg",
                "requirements.txt", "readme.md", "readme", "src", "lib",
                "app", "pkg", "main.py", "index.js",
            }
            lowered = {c.lower() for c in children}
            # A lone folder holding a single file (e.g. just src/a.py)
            # is more likely a real source dir than a ZIP wrapper,
            # so don't strip that level.
            if len(children) == 1 and not (lowered & markers):
                return extract_dir
            return single
    return extract_dir
