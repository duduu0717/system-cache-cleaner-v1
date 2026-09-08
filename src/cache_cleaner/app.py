from __future__ import annotations

import ctypes
import queue
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .core import (
    CleanResult,
    ScanResult,
    clean_selected,
    disk_info,
    format_bytes,
    scan_all,
)

BG = "#f3f6fa"
PANEL = "#ffffff"
PRIMARY = "#1769e0"
PRIMARY_DARK = "#0f56bd"
TEXT = "#1e293b"
MUTED = "#64748b"
BORDER = "#dce3ec"
SUCCESS = "#138a5b"
WARNING = "#b8660b"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def runtime_log_path() -> Path:
    base = Path.home() / "AppData" / "Local" / "SystemCacheCleaner" / "logs"
    return base / f"clean-{datetime.now():%Y%m%d-%H%M%S}.log"


class CacheCleanerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("系统缓存清理工具 V1.0")
        self.geometry("920x620")
        self.minsize(840, 560)
        self.configure(bg=BG)
        self.results: list[ScanResult] = []
        self.selected: dict[str, tk.BooleanVar] = {}
        self.events: queue.Queue[tuple] = queue.Queue()
        self.busy = False
        self._configure_styles()
        self._build_shell()
        self.after(80, self._process_events)
        self._show_home()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Primary.TButton",
            font=("Microsoft YaHei UI", 11, "bold"),
            foreground="white",
            background=PRIMARY,
            borderwidth=0,
            padding=(24, 12),
        )
        style.map(
            "Primary.TButton",
            background=[("active", PRIMARY_DARK), ("disabled", "#94a3b8")],
        )
        style.configure(
            "Secondary.TButton",
            font=("Microsoft YaHei UI", 10),
            foreground=TEXT,
            background="#e8eef6",
            borderwidth=0,
            padding=(18, 10),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#dbe5f1")],
        )
        style.configure(
            "Clean.Horizontal.TProgressbar",
            troughcolor="#dce6f3",
            background=PRIMARY,
            borderwidth=0,
            thickness=16,
        )
        style.configure(
            "TCheckbutton",
            background=PANEL,
            foreground=TEXT,
            font=("Microsoft YaHei UI", 10),
        )

    def _build_shell(self) -> None:
        header = tk.Frame(self, bg="#164f9e", height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="系统缓存清理工具",
            bg="#164f9e",
            fg="white",
            font=("Microsoft YaHei UI", 17, "bold"),
        ).pack(side="left", padx=30)
        tk.Label(
            header,
            text="V1.0",
            bg="#164f9e",
            fg="#dbeafe",
            font=("Segoe UI", 10),
        ).pack(side="left")
        role = "管理员模式" if is_admin() else "普通用户模式"
        tk.Label(
            header,
            text=role,
            bg="#164f9e",
            fg="#e2e8f0",
            font=("Microsoft YaHei UI", 9),
        ).pack(side="right", padx=30)
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True, padx=34, pady=26)

    def _clear(self) -> None:
        for widget in self.content.winfo_children():
            widget.destroy()

    def _title(self, title: str, subtitle: str) -> None:
        tk.Label(
            self.content,
            text=title,
            bg=BG,
            fg=TEXT,
            font=("Microsoft YaHei UI", 21, "bold"),
        ).pack(anchor="w")
        tk.Label(
            self.content,
            text=subtitle,
            bg=BG,
            fg=MUTED,
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", pady=(5, 20))

    def _panel(self) -> tk.Frame:
        panel = tk.Frame(self.content, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)
        return panel

    def _show_home(self) -> None:
        self._clear()
        self._title("释放磁盘空间", "扫描常见系统缓存，确认后再执行清理")
        panel = self._panel()
        try:
            info = disk_info()
        except OSError:
            info = None
        tk.Label(
            panel,
            text="系统盘空间",
            bg=PANEL,
            fg=TEXT,
            font=("Microsoft YaHei UI", 13, "bold"),
        ).pack(anchor="w", padx=30, pady=(27, 18))
        stats = tk.Frame(panel, bg=PANEL)
        stats.pack(fill="x", padx=30)
        values = [
            ("总容量", format_bytes(info.total) if info else "无法读取"),
            ("已使用", format_bytes(info.used) if info else "--"),
            ("可用空间", format_bytes(info.free) if info else "--"),
        ]
        for i, (label, value) in enumerate(values):
            box = tk.Frame(
                stats,
                bg="#f7f9fc",
                highlightbackground=BORDER,
                highlightthickness=1,
            )
            box.grid(
                row=0,
                column=i,
                sticky="nsew",
                padx=(0 if i == 0 else 8, 0),
            )
            stats.columnconfigure(i, weight=1)
            tk.Label(
                box,
                text=label,
                bg="#f7f9fc",
                fg=MUTED,
                font=("Microsoft YaHei UI", 9),
            ).pack(pady=(15, 3))
            tk.Label(
                box,
                text=value,
                bg="#f7f9fc",
                fg=TEXT,
                font=("Segoe UI", 17, "bold"),
            ).pack(pady=(0, 15))
        tk.Label(
            panel,
            text="将检查用户临时文件、Windows 临时文件和缩略图缓存",
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 10),
        ).pack(pady=(38, 15))
        ttk.Button(
            panel,
            text="开始扫描",
            style="Primary.TButton",
            command=self._start_scan,
        ).pack()
        tk.Label(
            panel,
            text="扫描阶段不会删除任何文件",
            bg=PANEL,
            fg="#8492a6",
            font=("Microsoft YaHei UI", 9),
        ).pack(pady=13)

    def _show_working(self, cleaning: bool = False) -> None:
        self._clear()
        title = "正在清理" if cleaning else "正在扫描"
        subtitle = "正在删除已确认的缓存文件" if cleaning else "正在统计缓存文件，请稍候"
        self._title(title, subtitle)
        panel = self._panel()
        icon = "清" if cleaning else "扫"
        tk.Label(
            panel,
            text=icon,
            bg="#e8f1fd",
            fg=PRIMARY,
            width=3,
            height=1,
            font=("Microsoft YaHei UI", 25, "bold"),
        ).pack(pady=(48, 18))
        self.status_label = tk.Label(
            panel,
            text="正在准备...",
            bg=PANEL,
            fg=TEXT,
            font=("Microsoft YaHei UI", 12),
        )
        self.status_label.pack(pady=8)
        self.progress = ttk.Progressbar(
            panel,
            style="Clean.Horizontal.TProgressbar",
            mode="indeterminate",
            length=520,
        )
        self.progress.pack(pady=20)
        self.progress.start(12)
        self.detail_label = tk.Label(
            panel,
            text="请保持程序运行",
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        )
        self.detail_label.pack()

    def _start_scan(self) -> None:
        if self.busy:
            return
        self.busy = True
        self._show_working()

        def worker() -> None:
            try:
                results = scan_all(
                    progress=lambda key, count, size: self.events.put(
                        ("scan_progress", key, count, size)
                    )
                )
                self.events.put(("scan_done", results))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _show_results(self) -> None:
        self._clear()
        total = sum(result.total_bytes for result in self.results)
        self._title(
            "扫描结果",
            f"共发现 {format_bytes(total)} 可清理空间，请确认需要清理的项目",
        )
        panel = self._panel()
        self.selected = {}
        header = tk.Frame(panel, bg="#f7f9fc")
        header.pack(fill="x", padx=1, pady=(1, 0))
        columns = [
            ("清理项目", "left", 28),
            ("占用空间", "right", 14),
            ("文件数量", "right", 12),
        ]
        for text, side, width in columns:
            tk.Label(
                header,
                text=text,
                bg="#f7f9fc",
                fg=MUTED,
                width=width,
                anchor="w" if side == "left" else "e",
                font=("Microsoft YaHei UI", 9),
            ).pack(side=side, padx=18, pady=12)
        for result in self.results:
            row = tk.Frame(panel, bg=PANEL)
            row.pack(fill="x", padx=20, pady=8)
            var = tk.BooleanVar(value=True)
            self.selected[result.category.key] = var
            ttk.Checkbutton(row, variable=var).pack(side="left")
            names = tk.Frame(row, bg=PANEL)
            names.pack(side="left", padx=8)
            tk.Label(
                names,
                text=result.category.name,
                bg=PANEL,
                fg=TEXT,
                font=("Microsoft YaHei UI", 10, "bold"),
            ).pack(anchor="w")
            tk.Label(
                names,
                text=result.category.description,
                bg=PANEL,
                fg=MUTED,
                font=("Microsoft YaHei UI", 8),
            ).pack(anchor="w")
            tk.Label(
                row,
                text=format_bytes(result.total_bytes),
                bg=PANEL,
                fg=TEXT,
                width=14,
                anchor="e",
                font=("Segoe UI", 10, "bold"),
            ).pack(side="right", padx=18)
            tk.Label(
                row,
                text=f"{result.file_count:,}",
                bg=PANEL,
                fg=TEXT,
                width=12,
                anchor="e",
                font=("Segoe UI", 10),
            ).pack(side="right", padx=18)
        actions = tk.Frame(panel, bg=PANEL)
        actions.pack(side="bottom", fill="x", padx=24, pady=20)
        ttk.Button(
            actions,
            text="返回首页",
            style="Secondary.TButton",
            command=self._show_home,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="清理选中项目",
            style="Primary.TButton",
            command=self._confirm_clean,
        ).pack(side="right")

    def _confirm_clean(self) -> None:
        selected = {key for key, var in self.selected.items() if var.get()}
        chosen = [result for result in self.results if result.category.key in selected]
        if not chosen:
            messagebox.showinfo(
                "未选择项目",
                "请至少选择一个需要清理的项目。",
                parent=self,
            )
            return
        names = "、".join(result.category.name for result in chosen)
        size = format_bytes(sum(result.total_bytes for result in chosen))
        confirmed = messagebox.askyesno(
            "确认清理",
            f"将清理：{names}\n预计释放空间：{size}\n\n文件删除后无法恢复，是否继续？",
            icon="warning",
            parent=self,
        )
        if not confirmed:
            return
        self._start_clean(selected)

    def _start_clean(self, selected: set[str]) -> None:
        self.busy = True
        self._show_working(cleaning=True)
        log_path = runtime_log_path()

        def worker() -> None:
            try:
                summary = clean_selected(
                    self.results,
                    selected,
                    log_path,
                    lambda key, index, total, released: self.events.put(
                        ("clean_progress", key, index, total, released)
                    ),
                )
                self.events.put(("clean_done", summary, log_path))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _show_complete(self, result: CleanResult, log_path: Path) -> None:
        self._clear()
        self._title("清理完成", "本次缓存清理任务已结束")
        panel = self._panel()
        tk.Label(
            panel,
            text="✓",
            bg=PANEL,
            fg=SUCCESS,
            font=("Segoe UI Symbol", 42, "bold"),
        ).pack(pady=(30, 4))
        tk.Label(
            panel,
            text=f"已释放 {format_bytes(result.released_bytes)}",
            bg=PANEL,
            fg=TEXT,
            font=("Microsoft YaHei UI", 20, "bold"),
        ).pack()
        stats = tk.Frame(panel, bg=PANEL)
        stats.pack(pady=25)
        values = [
            ("清理成功", f"{result.success_count:,} 个", SUCCESS),
            ("清理失败", f"{result.failed_count:,} 个", WARNING),
            ("清理耗时", f"{result.elapsed_seconds:.2f} 秒", TEXT),
        ]
        for i, (label, value, color) in enumerate(values):
            box = tk.Frame(stats, bg="#f7f9fc", width=170, height=70)
            box.grid(row=0, column=i, padx=6)
            box.pack_propagate(False)
            tk.Label(
                box,
                text=label,
                bg="#f7f9fc",
                fg=MUTED,
                font=("Microsoft YaHei UI", 8),
            ).pack(pady=(10, 1))
            tk.Label(
                box,
                text=value,
                bg="#f7f9fc",
                fg=color,
                font=("Microsoft YaHei UI", 12, "bold"),
            ).pack()
        tk.Label(
            panel,
            text=f"日志：{log_path}",
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 8),
            wraplength=700,
        ).pack(pady=(0, 18))
        ttk.Button(
            panel,
            text="返回首页",
            style="Primary.TButton",
            command=self._show_home,
        ).pack()

    def _process_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "scan_progress":
                    _, key, count, size = event
                    self.status_label.config(text=f"正在检查 {key}")
                    self.detail_label.config(
                        text=f"已发现 {count:,} 个文件，共 {format_bytes(size)}"
                    )
                elif kind == "scan_done":
                    self.busy = False
                    self.results = event[1]
                    self._show_results()
                elif kind == "clean_progress":
                    _, key, index, total, released = event
                    self.status_label.config(text=f"正在清理 {key}")
                    self.detail_label.config(
                        text=(
                            f"已处理 {index:,} / {total:,}，"
                            f"释放 {format_bytes(released)}"
                        )
                    )
                elif kind == "clean_done":
                    self.busy = False
                    self._show_complete(event[1], event[2])
                elif kind == "error":
                    self.busy = False
                    messagebox.showerror("操作失败", event[1], parent=self)
                    self._show_home()
        except queue.Empty:
            pass
        self.after(80, self._process_events)


def main() -> None:
    app = CacheCleanerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
