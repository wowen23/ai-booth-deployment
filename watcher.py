import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent


CONFIG_FILE = "config.json"
PROCESSED_LEDGER = "processed.json"
LOG_FILE = "watcher.log"


@dataclass
class AppConfig:
    input_dir: Path
    output_dir: Path
    archive_dir: Path
    style_category: str
    style_file: Path
    model_priority: List[str]
    num_images: int
    debounce_ms: int


def load_config(base: Path) -> AppConfig:
    cfg_path = base / CONFIG_FILE
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return AppConfig(
        input_dir=(base / data.get("input_dir", "input")).resolve(),
        output_dir=(base / data.get("output_dir", "output")).resolve(),
        archive_dir=(base / data.get("archive_dir", "archive")).resolve(),
        style_category=data.get("style_category", "background"),
        style_file=(base / data.get("style_file", "styles/background/80s.txt")).resolve(),
        model_priority=list(data.get("model_priority", ["imagen-3.0-generate-002"])),
        num_images=int(data.get("num_images", 1)),
        debounce_ms=int(data.get("debounce_ms", 1000)),
    )


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def ensure_dirs(cfg: AppConfig):
    for p in [cfg.input_dir, cfg.output_dir, cfg.archive_dir]:
        p.mkdir(parents=True, exist_ok=True)


def load_ledger(base: Path) -> Dict[str, float]:
    path = base / PROCESSED_LEDGER
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_ledger(base: Path, ledger: Dict[str, float]):
    path = base / PROCESSED_LEDGER
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    tmp.replace(path)


def is_stable(path: Path, debounce_ms: int) -> bool:
    # File is considered stable if its size does not change over debounce window
    interval = max(0.2, debounce_ms / 1000.0)
    try:
        s1 = path.stat().st_size
        time.sleep(interval)
        s2 = path.stat().st_size
        return s1 == s2 and s1 > 0
    except FileNotFoundError:
        return False


def choose_model(model_priority: List[str]) -> str:
    # For Phase 1, just take the first. Later, we can probe availability.
    return model_priority[0]


def run_generation(base: Path, cfg: AppConfig, input_file: Path) -> Tuple[bool, Optional[str]]:
    model = choose_model(cfg.model_priority)
    prompt_file = cfg.style_file

    # Build command: python generate_image.py @prompt.txt --n N --model <model>
    cmd = [
        sys.executable,
        str(base / "generate_image.py"),
        f"@{prompt_file}",
        "--n",
        str(cfg.num_images),
        "--model",
        model,
        "--output",
        str(cfg.output_dir),
    ]

    env = os.environ.copy()

    log(f"Running: {' '.join(map(str, cmd))}")
    try:
        proc = subprocess.run(cmd, cwd=str(base), env=env, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            log(f"ERROR: generation failed (rc={proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
            return False, proc.stderr or proc.stdout
        else:
            log(f"SUCCESS: generation completed\nstdout:\n{proc.stdout}")
            return True, proc.stdout
    except subprocess.TimeoutExpired:
        log("ERROR: generation timed out")
        return False, "timeout"
    except Exception as e:
        log(f"ERROR: exception during generation: {e}")
        return False, str(e)


class Handler(FileSystemEventHandler):
    def __init__(self, base: Path, cfg: AppConfig, ledger: Dict[str, float]):
        super().__init__()
        self.base = base
        self.cfg = cfg
        self.ledger = ledger

    def on_created(self, event):
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            path = Path(event.src_path)
            # Simple dedupe: filename + mtime
            try:
                mtime = path.stat().st_mtime
            except FileNotFoundError:
                return

            key = f"{path.name}:{int(mtime)}"
            if key in self.ledger:
                log(f"Duplicate ignored: {path.name}")
                return

            # Wait until stable
            log(f"Detected new file: {path}")
            for _ in range(30):  # up to ~30 * interval seconds
                if is_stable(path, self.cfg.debounce_ms):
                    break
                time.sleep(max(0.2, self.cfg.debounce_ms / 1000.0))
            else:
                log(f"File not stable, skipping: {path}")
                return

            # Run generation
            ok, _ = run_generation(self.base, self.cfg, path)
            if ok:
                # Move to archive
                dest = self.cfg.archive_dir / path.name
                try:
                    shutil.move(str(path), str(dest))
                    self.ledger[key] = time.time()
                    save_ledger(self.base, self.ledger)
                    log(f"Archived: {dest}")
                except Exception as e:
                    log(f"ERROR archiving {path}: {e}")


def main():
    base = Path(__file__).resolve().parent
    cfg = load_config(base)
    ensure_dirs(cfg)
    ledger = load_ledger(base)

    parser = argparse.ArgumentParser(description="Watch a folder and trigger image generation on new files")
    parser.add_argument("--once", action="store_true", help="Run a single pass on current contents and exit")
    args = parser.parse_args()

    if args.once:
        # Process all files currently in input directory once
        for p in sorted(cfg.input_dir.glob("*")):
            if p.is_file():
                # mimic on_created logic
                try:
                    mtime = p.stat().st_mtime
                except FileNotFoundError:
                    continue
                key = f"{p.name}:{int(mtime)}"
                if key in ledger:
                    continue
                if not is_stable(p, cfg.debounce_ms):
                    continue
                ok, _ = run_generation(base, cfg, p)
                if ok:
                    dest = cfg.archive_dir / p.name
                    try:
                        shutil.move(str(p), str(dest))
                        ledger[key] = time.time()
                        save_ledger(base, ledger)
                        log(f"Archived: {dest}")
                    except Exception as e:
                        log(f"ERROR archiving {p}: {e}")
        return

    # Start watchdog observer
    event_handler = Handler(base, cfg, ledger)
    observer = Observer()
    observer.schedule(event_handler, str(cfg.input_dir), recursive=False)
    observer.start()
    log(f"Watching: {cfg.input_dir}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
