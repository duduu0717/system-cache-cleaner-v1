from pathlib import Path

from cache_cleaner.core import CacheCategory, default_categories, format_bytes, scan_category


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


def test_missing_temp_environment_does_not_fall_back_to_working_directory(monkeypatch) -> None:
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    categories = default_categories()

    assert categories[0].roots == ()
    assert categories[2].roots == ()


def test_scan_excludes_packaged_runtime_directory(tmp_path: Path, monkeypatch) -> None:
    runtime = tmp_path / "_MEI-runtime"
    runtime.mkdir()
    (runtime / "python-runtime.dll").write_bytes(b"runtime")
    (tmp_path / "normal.tmp").write_bytes(b"cache")
    monkeypatch.setattr("sys._MEIPASS", str(runtime), raising=False)
    category = CacheCategory("test", "测试", "", (tmp_path,))

    result = scan_category(category)

    assert result.files == [tmp_path / "normal.tmp"]
