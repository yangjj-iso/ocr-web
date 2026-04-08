import os
from pathlib import Path

from config import LOCAL_PATH_ROOTS, UPLOAD_DIR


class PathSecurityError(ValueError):
    pass


def _normalize(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def is_within_roots(path: Path, roots: tuple[Path, ...] | list[Path] = LOCAL_PATH_ROOTS) -> bool:
    candidate = _normalize(path)
    for root in roots:
        normalized_root = _normalize(root)
        if candidate == normalized_root or candidate.startswith(f"{normalized_root}{os.sep}"):
            return True
    return False


def ensure_allowed_path(
    raw_path: str | Path,
    *,
    expect_file: bool = False,
    expect_dir: bool = False,
    roots: tuple[Path, ...] | list[Path] = LOCAL_PATH_ROOTS,
) -> Path:
    if not raw_path:
        raise PathSecurityError("Path is required.")

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        raise PathSecurityError("Only absolute paths are allowed.")

    resolved = candidate.resolve(strict=False)
    if not is_within_roots(resolved, roots):
        allowed = ", ".join(str(root) for root in roots)
        raise PathSecurityError(f"Path is outside allowed roots: {allowed}")

    if expect_file:
        if not resolved.exists() or not resolved.is_file():
            raise PathSecurityError(f"File does not exist: {resolved}")
    if expect_dir:
        if not resolved.exists() or not resolved.is_dir():
            raise PathSecurityError(f"Directory does not exist: {resolved}")
    return resolved


def is_managed_upload_path(path: str | Path) -> bool:
    return is_within_roots(Path(path), [UPLOAD_DIR])
