from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
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


@dataclass
class CleanResult:
    selected_categories: int = 0
    success_count: int = 0
    failed_count: int = 0
    released_bytes: int = 0
    elapsed_seconds: float = 0.0
    failures: list[str] = field(default_factory=list)


def default_categories() -> list[CacheCategory]:
    """Return the small, fixed set of cache locations supported by V1.0."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    user_temp = os.environ.get("TEMP")
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))

    return [
        CacheCategory(
            "user_temp",
            "用户临时文件",
            "当前用户和应用程序产生的临时文件",
            (Path(user_temp),) if user_temp else (),
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
            (Path(local_app_data) / "Microsoft" / "Windows" / "Explorer",) if local_app_data else (),
            ("thumbcache_*.db",),
        ),
    ]


def disk_info(path: Path | None = None) -> DiskInfo:
    target = path or Path(os.environ.get("SystemDrive", "C:")) / "\\"
    usage = shutil.disk_usage(target)
    return DiskInfo(usage.total, usage.used, usage.free)


def _matches(path: Path, patterns: Iterable[str]) -> bool:
    return any(path.match(pattern) for pattern in patterns)


def _is_within(path: Path, roots: Iterable[Path]) -> bool:
    try:
        resolved = path.resolve(strict=False)
        return any(resolved == root.resolve(strict=False) or root.resolve(strict=False) in resolved.parents for root in roots)
    except OSError:
        return False


def runtime_exclusions() -> tuple[Path, ...]:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    return (Path(bundle_dir),) if bundle_dir else ()


def _walk_files(root: Path, excluded_roots: tuple[Path, ...] = ()) -> Iterable[Path]:
    """Walk without following links and continue past inaccessible entries."""
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        entry_path = Path(entry.path)
                        if _is_within(entry_path, excluded_roots):
                            continue
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(entry_path)
                        elif entry.is_file(follow_symlinks=False):
                            yield entry_path
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
        for path in _walk_files(root, runtime_exclusions()):
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


def _is_safe_file(path: Path, allowed_roots: tuple[Path, ...]) -> bool:
    """Only accept normal files located below an explicitly allowed root."""
    try:
        if path.is_symlink() or not path.is_file():
            return False
        resolved = path.resolve(strict=True)
        for root in allowed_roots:
            if not root or not root.is_dir():
                continue
            try:
                resolved.relative_to(root.resolve(strict=True))
                return True
            except ValueError:
                continue
    except OSError:
        return False
    return False


def clean_selected(
    results: Iterable[ScanResult],
    selected_keys: set[str],
    log_path: Path,
    progress: Callable[[str, int, int, int], None] | None = None,
) -> CleanResult:
    """Delete selected scanned files after revalidating every individual path."""
    started = time.monotonic()
    summary = CleanResult()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_lines = [f"清理开始时间: {datetime.now():%Y-%m-%d %H:%M:%S}"]

    for result in results:
        if result.category.key not in selected_keys:
            continue
        summary.selected_categories += 1
        log_lines.append(f"\n[{result.category.name}]")
        total = result.file_count
        for index, path in enumerate(result.files, start=1):
            if not _is_safe_file(path, result.category.roots):
                summary.failed_count += 1
                message = f"拒绝不安全或已失效的路径: {path}"
                summary.failures.append(message)
                log_lines.append(f"失败 | {message}")
            else:
                try:
                    size = path.stat(follow_symlinks=False).st_size
                    path.unlink()
                    summary.success_count += 1
                    summary.released_bytes += size
                    log_lines.append(f"成功 | {size} B | {path}")
                except OSError as exc:
                    summary.failed_count += 1
                    message = f"{path} | {exc}"
                    summary.failures.append(message)
                    log_lines.append(f"失败 | {message}")
            if progress:
                progress(result.category.key, index, total, summary.released_bytes)

    summary.elapsed_seconds = time.monotonic() - started
    log_lines.extend(
        [
            "",
            f"成功文件数: {summary.success_count}",
            f"失败文件数: {summary.failed_count}",
            f"释放字节数: {summary.released_bytes}",
            f"清理耗时: {summary.elapsed_seconds:.2f} 秒",
        ]
    )
    log_path.write_text("\n".join(log_lines), encoding="utf-8")
    return summary


def format_bytes(value: int) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return "0 B"
