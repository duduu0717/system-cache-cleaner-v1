from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import subprocess
import sys
import time
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "screenshots"
TITLE = "系统缓存清理工具 V1.0"
STATES = ["home", "scan", "results", "clean", "complete"]

sys.path.insert(0, str(ROOT / "src"))
from cache_cleaner.app import CacheCleanerApp
from cache_cleaner.core import CacheCategory, CleanResult, ScanResult


def demo_results() -> list[ScanResult]:
    values = [
        ("user_temp", "用户临时文件", "当前用户和应用程序产生的临时文件", 1024, 856 * 1024**2),
        ("windows_temp", "Windows 临时文件", "Windows 系统临时目录中的可访问文件", 580, 620 * 1024**2),
        ("thumbnail_cache", "缩略图缓存", "Windows 资源管理器生成的缩略图数据库", 320, 412 * 1024**2),
    ]
    results = []
    for key, name, description, count, size in values:
        category = CacheCategory(key, name, description, (Path("Z:/demo-cache"),))
        files = [Path(f"Z:/demo-cache/{key}-{index}.tmp") for index in range(count)]
        results.append(ScanResult(category, files, size))
    return results


def show_state(state: str) -> None:
    app = CacheCleanerApp()
    app.results = demo_results()
    if state == "scan":
        app._show_working()
    elif state == "results":
        app._show_results()
    elif state == "clean":
        app._show_working(cleaning=True)
    elif state == "complete":
        result = CleanResult(3, 1462, 8, 1870 * 1024**2, 12.0)
        app._show_complete(result, Path("logs/clean-demo.log"))
    app.mainloop()


def find_window(timeout: float = 8.0) -> int:
    user32 = ctypes.windll.user32
    deadline = time.time() + timeout
    while time.time() < deadline:
        handle = user32.FindWindowW(None, TITLE)
        if handle:
            return handle
        time.sleep(0.1)
    raise RuntimeError(f"未找到窗口：{TITLE}")


def window_rect(handle: int) -> tuple[int, int, int, int]:
    rect = ctypes.wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(handle, ctypes.byref(rect)):
        raise OSError("无法读取窗口位置")
    return rect.left, rect.top, rect.right, rect.bottom


def capture(state: str, index: int) -> None:
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--show-state", state],
        cwd=ROOT,
    )
    try:
        handle = find_window()
        ctypes.windll.user32.ShowWindow(handle, 9)
        ctypes.windll.user32.SetForegroundWindow(handle)
        time.sleep(0.8)
        image = ImageGrab.grab(bbox=window_rect(handle), all_screens=True)
        image.save(OUTPUT / f"{index:02d}_{state}.png")
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--show-state", choices=STATES)
    args = parser.parse_args()
    if args.show_state:
        show_state(args.show_state)
        return

    OUTPUT.mkdir(exist_ok=True)
    for index, state in enumerate(STATES, start=1):
        capture(state, index)
    print(f"已生成 {len(STATES)} 张截图：{OUTPUT}")


if __name__ == "__main__":
    main()
