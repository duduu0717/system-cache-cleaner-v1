from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cache_cleaner.app import CacheCleanerApp
from cache_cleaner.core import CleanResult, scan_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", choices=["results", "confirm", "complete"])
    parser.add_argument("--summary")
    args = parser.parse_args()

    app = CacheCleanerApp()
    app.geometry("920x620+180+80")
    app.update_idletasks()
    if args.state == "complete":
        data = json.loads(Path(args.summary).read_text(encoding="utf-8"))
        result = CleanResult(
            selected_categories=data["selected_categories"],
            success_count=data["success_count"],
            failed_count=data["failed_count"],
            released_bytes=data["released_bytes"],
            elapsed_seconds=data["elapsed_seconds"],
        )
        app._show_complete(result, Path(data["log_path"]))
    else:
        app.results = scan_all()
        app._show_results()
        if args.state == "confirm":
            app.after(500, app._confirm_clean)
    app.mainloop()


if __name__ == "__main__":
    main()
