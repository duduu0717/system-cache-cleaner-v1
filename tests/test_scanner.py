from pathlib import Path

from cache_cleaner.core import CacheCategory, format_bytes, scan_category


def test_scan_category_counts_matching_files(tmp_path: Path) -> None:
    (tmp_path / "one.tmp").write_bytes(b"123")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "two.tmp").write_bytes(b"4567")
    (nested / "ignore.log").write_bytes(b"ignored")

    category = CacheCategory("test", "测试", "", (tmp_path,), ("*.tmp",))
    result = scan_category(category)

    assert result.file_count == 2
    assert result.total_bytes == 7


def test_scan_does_not_follow_directory_symlink(tmp_path: Path) -> None:
    external = tmp_path.parent / f"{tmp_path.name}-external"
    external.mkdir()
    (external / "outside.tmp").write_bytes(b"outside")
    link = tmp_path / "linked"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError:
        return

    category = CacheCategory("test", "测试", "", (tmp_path,), ("*.tmp",))
    assert scan_category(category).file_count == 0


def test_format_bytes() -> None:
    assert format_bytes(0) == "0 B"
    assert format_bytes(1536) == "1.50 KB"

