from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


@dataclass(frozen=True)
class CacheCategory:
    key: str
    name: str
    description: str
    roots: tuple[Path, ...]
    patterns: tuple[str, ...] = ("*",)


@dataclass
class ScanResult:
    category: CacheCategory
    files: list[Path] = field(default_factory=list)
    total_bytes: int = 0
    skipped: int = 0

    @property
    def file_count(self) -> int:
        return len(self.files)


@dataclass(frozen=True)
class DiskInfo:
    total: int
    used: int
    free: int


def default_categories() -> list[CacheCategory]:
    """Return the small, fixed set of cache locations supported by V1.0."""
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    user_temp = Path(os.environ.get("TEMP", ""))
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))

    return [
        CacheCategory(
            "user_temp",
            "用户临时文件",
            "当前用户和应用程序产生的临时文件",
            (user_temp,),
        ),
        CacheCategory(
            "windows_temp",
            "Windows 临时文件",
            "Windows 系统临时目录中的可访问文件",
            (windows_dir / "Temp",),
        ),
        CacheCategory(
            "thumbnail_cache",
            "缩略图缓存",
            "Windows 资源管理器生成的缩略图数据库",
            (local_app_data / "Microsoft" / "Windows" / "Explorer",),
            ("thumbcache_*.db",),
        ),
    ]


def disk_info(path: Path | None = None) -> DiskInfo:
    target = path or Path(os.environ.get("SystemDrive", "C:")) / "\\"
    usage = shutil.disk_usage(target)
    return DiskInfo(usage.total, usage.used, usage.free)


def _matches(path: Path, patterns: Iterable[str]) -> bool:
    return any(path.match(pattern) for pattern in patterns)


def _walk_files(root: Path) -> Iterable[Path]:
    """Walk without following links and continue past inaccessible entries."""
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            yield Path(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue


def scan_category(
    category: CacheCategory,
    progress: Callable[[int, int], None] | None = None,
) -> ScanResult:
    result = ScanResult(category)
    for root in category.roots:
        if not root or not root.is_dir():
            continue
        for path in _walk_files(root):
            if not _matches(path, category.patterns):
                continue
            try:
                size = path.stat(follow_symlinks=False).st_size
            except OSError:
                result.skipped += 1
                continue
            result.files.append(path)
            result.total_bytes += size
            if progress:
                progress(result.file_count, result.total_bytes)
    return result


def scan_all(
    categories: Iterable[CacheCategory] | None = None,
    progress: Callable[[str, int, int], None] | None = None,
) -> list[ScanResult]:
    results: list[ScanResult] = []
    for category in categories or default_categories():
        callback = None
        if progress:
            callback = lambda count, size, key=category.key: progress(key, count, size)
        results.append(scan_category(category, callback))
    return results


def format_bytes(value: int) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return "0 B"

