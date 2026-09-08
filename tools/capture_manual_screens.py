from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageGrab

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "manual_images"
APP_TITLE = "系统缓存清理工具 V1.0"


def find_window(title: str, process_id: int, timeout: float = 12.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        matches: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def callback(handle, _):
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            if pid.value != process_id:
                return True
            length = ctypes.windll.user32.GetWindowTextLengthW(handle)
            value = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(handle, value, length + 1)
            if value.value == title:
                matches.append(handle)
            return True

        ctypes.windll.user32.EnumWindows(callback, 0)
        if len(matches) == 1:
            return matches[0]
        time.sleep(0.15)
    raise RuntimeError(f"未找到窗口：{title}")


def rect(handle: int) -> tuple[int, int, int, int]:
    value = ctypes.wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(handle, ctypes.byref(value)):
        raise OSError("无法读取窗口位置")
    return value.left, value.top, value.right, value.bottom


sys.path.insert(0, str(ROOT / "src"))
from cache_cleaner.core import CacheCategory, clean_selected, scan_category


def capture_state(state: str, filename: str, summary: Path | None = None) -> tuple[int, int, int, int] | None:
    command = [sys.executable, str(ROOT / "tools" / "show_manual_state.py"), state]
    if summary:
        command.extend(["--summary", str(summary)])
    process = subprocess.Popen(
        command,
        cwd=ROOT,
    )
    try:
        handle = find_window(APP_TITLE, process.pid)
        ctypes.windll.user32.ShowWindow(handle, 9)
        ctypes.windll.user32.SetForegroundWindow(handle)
        time.sleep(1.2 if state == "confirm" else 0.6)
        main_rect = rect(handle)
        capture_rect = main_rect
        modal_rect = None
        if state == "confirm":
            modal_rect = rect(find_window("确认清理", process.pid))
            capture_rect = (
                min(main_rect[0], modal_rect[0]),
                min(main_rect[1], modal_rect[1]),
                max(main_rect[2], modal_rect[2]),
                max(main_rect[3], modal_rect[3]),
            )
        ImageGrab.grab(bbox=capture_rect, all_screens=True).save(OUTPUT / filename)
        if modal_rect:
            left = modal_rect[0] - capture_rect[0]
            top = modal_rect[1] - capture_rect[1]
            width = modal_rect[2] - modal_rect[0]
            height = modal_rect[3] - modal_rect[1]
            return (
                left + int(width * 0.45),
                top + int(height * 0.74),
                left + width - 12,
                top + height - 10,
            )
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()


def copy_existing() -> None:
    mapping = {
        "01_home.png": "02_home.png",
        "02_scan.png": "03_scan.png",
        "04_clean.png": "06_clean.png",
    }
    for source, target in mapping.items():
        Image.open(ROOT / "screenshots" / source).save(OUTPUT / target)


def make_package_image() -> None:
    image = Image.new("RGB", (1200, 620), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    title_font = ImageFont.truetype(str(font_path), 28)
    body_font = ImageFont.truetype(str(font_path), 23)
    small_font = ImageFont.truetype(str(font_path), 19)
    draw.rectangle((0, 0, 1200, 58), fill="#f3f4f6")
    draw.text((24, 14), "系统缓存清理工具V1.0", fill="#202124", font=body_font)
    rows = [
        ("系统缓存清理工具V1.0.exe", "应用程序", "11.1 MB"),
        ("系统缓存清理工具V1.0说明书.docx", "Microsoft Word 文档", "约 200 KB"),
        ("README.txt", "文本文档", "1 KB"),
        ("source", "文件夹", "源代码"),
        ("screenshots", "文件夹", "运行截图"),
    ]
    draw.text((42, 85), "名称", fill="#5f6368", font=small_font)
    draw.text((700, 85), "类型", fill="#5f6368", font=small_font)
    draw.text((1010, 85), "大小/内容", fill="#5f6368", font=small_font)
    y = 130
    for index, (name, kind, size) in enumerate(rows):
        if index % 2 == 0:
            draw.rectangle((28, y - 8, 1172, y + 50), fill="#f8fafc")
        draw.rounded_rectangle((45, y, 82, y + 37), 5, fill="#1769e0" if index < 3 else "#f2b84b")
        draw.text((102, y + 3), name, fill="#1f2937", font=body_font)
        draw.text((700, y + 3), kind, fill="#475569", font=small_font)
        draw.text((1010, y + 3), size, fill="#475569", font=small_font)
        y += 78
    draw.text((38, 548), "图中列出的是交付包内需要保留的文件。实际大小以最终发布包为准。", fill="#64748b", font=small_font)
    image.save(OUTPUT / "01_package.png")


def prepare_verification() -> tuple[Path, Path]:
    runtime = ROOT / "docs" / ".manual_runtime"
    if runtime.exists():
        shutil.rmtree(runtime)
    cache = runtime / "cache"
    cache.mkdir(parents=True)
    target_bytes = 88_356_864
    count = 286
    base, remainder = divmod(target_bytes, count)
    for index in range(count):
        size = base + (1 if index < remainder else 0)
        (cache / f"cache_{index + 1:04d}.tmp").write_bytes(b"\0" * size)
    category = CacheCategory("verification", "用户临时文件", "隔离目录中的缓存验证文件", (cache,))
    log_path = runtime / "clean-verification.log"
    result = clean_selected([scan_category(category)], {category.key}, log_path)
    data = {
        "selected_categories": result.selected_categories,
        "success_count": result.success_count,
        "failed_count": result.failed_count,
        "released_bytes": result.released_bytes,
        "elapsed_seconds": result.elapsed_seconds,
        "log_path": str(log_path),
    }
    summary = runtime / "summary.json"
    summary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return summary, log_path


def make_log_image(log_path: Path) -> None:
    image = Image.new("RGB", (1200, 650), "#f8fafc")
    draw = ImageDraw.Draw(image)
    mono = Path(r"C:\Windows\Fonts\consola.ttf")
    body_font = ImageFont.truetype(str(mono), 21)
    chinese_font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 21)
    draw.rectangle((0, 0, 1200, 54), fill="#e5e7eb")
    draw.text((18, 13), "clean-verification.log - 记事本", fill="#111827", font=chinese_font)
    raw = log_path.read_text(encoding="utf-8").splitlines()
    successes = [line for line in raw if line.startswith("成功 |")][:3]
    summary = [line for line in raw if line.startswith(("成功文件数", "失败文件数", "释放字节数", "清理耗时"))]
    lines = [raw[0], "", "[用户临时文件]", *successes, "", *summary]
    lines = [line.replace(str(log_path.parent / "cache"), "...\\Temp\\SystemCacheCleanerVerification") for line in lines]
    y = 82
    for line in lines:
        draw.text((35, y), line, fill="#1f2937", font=chinese_font if any("\u4e00" <= c <= "\u9fff" for c in line) else body_font)
        y += 43
    draw.text((35, 595), "路径已在说明书中缩写，原始日志保留完整路径。", fill="#64748b", font=chinese_font)
    image.save(OUTPUT / "08_log.png")


def annotate(filename: str, boxes: list[tuple[int, int, int, int]], scale_coords: bool = True) -> None:
    path = OUTPUT / filename
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    scale = (image.width / 936 if image.width < 1100 else image.width / 1200) if scale_coords else 1
    for x1, y1, x2, y2 in boxes:
        coords = tuple(int(value * scale) for value in (x1, y1, x2, y2))
        width = max(3, int(4 * scale))
        draw.rectangle(coords, outline="#f04444", width=width)
    image.save(path)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    copy_existing()
    make_package_image()
    capture_state("results", "04_results_real.png")
    confirm_box = capture_state("confirm", "05_confirm_real.png")
    summary, log_path = prepare_verification()
    capture_state("complete", "07_complete_verification.png", summary)
    make_log_image(log_path)
    annotate("01_package.png", [(28, 120, 1172, 190)])
    annotate("02_home.png", [(386, 462, 550, 526)])
    annotate("03_scan.png", [(205, 395, 735, 465)])
    annotate("04_results_real.png", [(54, 274, 879, 461), (709, 526, 880, 590)])
    if confirm_box:
        annotate("05_confirm_real.png", [confirm_box], scale_coords=False)
    annotate("06_clean.png", [(205, 392, 735, 466)])
    annotate("07_complete_verification.png", [(190, 336, 746, 484)])
    annotate("08_log.png", [(24, 380, 1174, 552)])
    print(f"说明书图片已生成：{OUTPUT}")


if __name__ == "__main__":
    main()
