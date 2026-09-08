from pathlib import Path

from cache_cleaner.core import CacheCategory, ScanResult, clean_selected, scan_category


def test_clean_selected_deletes_only_selected_category(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    selected_file = first_root / "selected.tmp"
    retained_file = second_root / "retained.tmp"
    selected_file.write_bytes(b"12345")
    retained_file.write_bytes(b"keep")
    first = CacheCategory("first", "第一类", "", (first_root,))
    second = CacheCategory("second", "第二类", "", (second_root,))

    result = clean_selected(
        [scan_category(first), scan_category(second)],
        {"first"},
        tmp_path / "logs" / "clean.log",
    )

    assert not selected_file.exists()
    assert retained_file.exists()
    assert result.success_count == 1
    assert result.failed_count == 0
    assert result.released_bytes == 5


def test_clean_selected_rejects_file_outside_allowed_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "personal-document.txt"
    outside.write_text("must stay", encoding="utf-8")
    category = CacheCategory("cache", "缓存", "", (allowed,))
    tampered = ScanResult(category, files=[outside], total_bytes=outside.stat().st_size)

    result = clean_selected([tampered], {"cache"}, tmp_path / "clean.log")

    assert outside.exists()
    assert result.success_count == 0
    assert result.failed_count == 1
    assert "拒绝不安全" in result.failures[0]


def test_clean_selected_writes_utf8_log(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "file.tmp").write_bytes(b"data")
    category = CacheCategory("cache", "用户临时文件", "", (cache,))
    log_path = tmp_path / "clean.log"

    clean_selected([scan_category(category)], {"cache"}, log_path)

    content = log_path.read_text(encoding="utf-8")
    assert "用户临时文件" in content
    assert "成功文件数: 1" in content
