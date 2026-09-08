from __future__ import annotations

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
    process = subprocess.Popen([sys.executable, str(ROOT / "run_app.py"), "--demo-state", state], cwd=ROOT)
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
    OUTPUT.mkdir(exist_ok=True)
    for index, state in enumerate(STATES, start=1):
        capture(state, index)
    print(f"已生成 {len(STATES)} 张截图：{OUTPUT}")


if __name__ == "__main__":
    main()
