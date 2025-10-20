import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
LOCK_FILE = BASE_DIR / "watcher.lock"
WATCHER_LOG = BASE_DIR / "watcher.log"
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
ARCHIVE_DIR = BASE_DIR / "archive"
STYLES_DIR = BASE_DIR / "styles"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def save_config(cfg: dict):
    """Safely persist config.json on Windows with retries to avoid transient locks."""
    content = json.dumps(cfg, indent=2)
    # Create a unique temp file in the same directory for atomic-ish replace
    tmp = CONFIG_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
    except Exception as e:
        # Fall back to direct write if temp write fails
        CONFIG_FILE.write_text(content, encoding="utf-8")
        return

    # Try replacing with small retries to handle AV/indexer locks
    for attempt in range(5):
        try:
            tmp.replace(CONFIG_FILE)
            return
        except PermissionError:
            # Wait briefly and retry
            from time import sleep
            sleep(0.2)
            continue
        except Exception:
            break
    # Final fallback: write directly
    CONFIG_FILE.write_text(content, encoding="utf-8")


def list_styles(category: str) -> list[Path]:
    folder = STYLES_DIR / category
    if not folder.exists():
        return []
    return sorted([p for p in folder.glob("*.txt") if p.is_file()])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Booth – Watcher GUI")
        self.process: subprocess.Popen | None = None

        self.category_combo = QComboBox()
        self.category_combo.addItems(["background", "retheme"])  # future: add more categories

        self.style_combo = QComboBox()

        self.editor_model_edit = QLineEdit("gemini-2.5-flash-image")

        self.input_label = QLabel(str(INPUT_DIR))
        self.output_label = QLabel(str(OUTPUT_DIR))
        self.archive_label = QLabel(str(ARCHIVE_DIR))

        self.start_btn = QPushButton("Start Watching")
        self.stop_btn = QPushButton("Stop Watching")
        self.stop_btn.setEnabled(False)
        self.manual_btn = QPushButton("Process Image (copy to input)")

        self.open_input_btn = QPushButton("Open Input Folder")
        self.open_output_btn = QPushButton("Open Output Folder")
        self.open_archive_btn = QPushButton("Open Archive Folder")

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.status_label = QLabel("Idle")

        self._build_ui()
        self._wire_events()
        self._load_from_config()
        self._refresh_styles()

        # Log refresher
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._refresh_logs)
        self.timer.start()

        # Menu
        self._build_menu()

    def _build_menu(self):
        bar = self.menuBar()
        file_menu = bar.addMenu("File")
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)

        # Config group
        cfg_group = QGroupBox("Configuration")
        grid = QGridLayout(cfg_group)
        grid.addWidget(QLabel("Style category"), 0, 0)
        grid.addWidget(self.category_combo, 0, 1)
        grid.addWidget(QLabel("Style file"), 1, 0)
        grid.addWidget(self.style_combo, 1, 1)
        grid.addWidget(QLabel("Editor model"), 2, 0)
        grid.addWidget(self.editor_model_edit, 2, 1)

        # Paths
        path_group = QGroupBox("Paths")
        pgrid = QGridLayout(path_group)
        pgrid.addWidget(QLabel("Input"), 0, 0)
        pgrid.addWidget(self.input_label, 0, 1)
        pgrid.addWidget(self.open_input_btn, 0, 2)
        pgrid.addWidget(QLabel("Output"), 1, 0)
        pgrid.addWidget(self.output_label, 1, 1)
        pgrid.addWidget(self.open_output_btn, 1, 2)
        pgrid.addWidget(QLabel("Archive"), 2, 0)
        pgrid.addWidget(self.archive_label, 2, 1)
        pgrid.addWidget(self.open_archive_btn, 2, 2)

        # Controls
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(self.start_btn)
        ctrl_row.addWidget(self.stop_btn)
        ctrl_row.addWidget(self.manual_btn)

        # Log
        log_group = QGroupBox("Watcher Log")
        v = QVBoxLayout(log_group)
        v.addWidget(self.log_view)
        v.addWidget(self.status_label)

        layout.addWidget(cfg_group)
        layout.addWidget(path_group)
        layout.addLayout(ctrl_row)
        layout.addWidget(log_group)

        self.setCentralWidget(root)

    def _wire_events(self):
        self.category_combo.currentTextChanged.connect(self._refresh_styles)
        self.start_btn.clicked.connect(self.start_watch)
        self.stop_btn.clicked.connect(self.stop_watch)
        self.manual_btn.clicked.connect(self.manual_process)

        self.style_combo.currentTextChanged.connect(self._save_config)
        self.editor_model_edit.editingFinished.connect(self._save_config)

        self.open_input_btn.clicked.connect(lambda: self._open_folder(INPUT_DIR))
        self.open_output_btn.clicked.connect(lambda: self._open_folder(OUTPUT_DIR))
        self.open_archive_btn.clicked.connect(lambda: self._open_folder(ARCHIVE_DIR))

    def _open_folder(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _load_from_config(self):
        cfg = load_config()
        # Determine category from style_file path
        style_file = Path(cfg.get("style_file", "styles/background/80s.txt"))
        category = style_file.parts[-3] if len(style_file.parts) >= 3 else "background"
        if category in ["background", "retheme"]:
            self.category_combo.setCurrentText(category)
        else:
            self.category_combo.setCurrentText("background")
        self.editor_model_edit.setText(cfg.get("editor_model", "gemini-2.5-flash-image"))

    def _refresh_styles(self):
        category = self.category_combo.currentText() or "background"
        styles = list_styles(category)
        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        for p in styles:
            # Show relative path from BASE_DIR
            rel = p.relative_to(BASE_DIR)
            self.style_combo.addItem(str(rel), userData=str(rel))
        self.style_combo.blockSignals(False)

        # Try to keep current selection; else pick first
        cfg = load_config()
        current = cfg.get("style_file")
        idx = self.style_combo.findData(current)
        if idx < 0 and self.style_combo.count() > 0:
            idx = 0
        if idx >= 0:
            self.style_combo.setCurrentIndex(idx)
        self._save_config()

    def _save_config(self):
        # Persist UI selections to config.json
        cfg = load_config()
        style_rel = self.style_combo.currentData() or cfg.get("style_file", "styles/background/80s.txt")
        cfg["style_file"] = str(style_rel)
        # Infer mode from the style path category for compatibility with watcher
        try:
            cat = Path(str(style_rel)).parts[-3]
        except Exception:
            cat = "background"
        cfg["mode"] = "retheme" if cat == "retheme" else "background"
        cfg["editor_model"] = self.editor_model_edit.text().strip() or "gemini-2.5-flash-image"
        save_config(cfg)

    def start_watch(self):
        # Ensure single instance (lock)
        if LOCK_FILE.exists():
            QMessageBox.warning(self, "Watcher Running", f"A watcher is already running (lock: {LOCK_FILE}).")
            return
        # Save config before starting
        self._save_config()
        # Start watcher
        try:
            self.process = subprocess.Popen([sys.executable, str(BASE_DIR / "watcher.py")], cwd=str(BASE_DIR))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start watcher: {e}")
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Watcher started")

    def stop_watch(self):
        # Stop subprocess and remove lock
        try:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
        except Exception:
            pass
        finally:
            self.process = None
            if LOCK_FILE.exists():
                try:
                    LOCK_FILE.unlink()
                except Exception:
                    pass
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Watcher stopped")

    def manual_process(self):
        # Pick an image and copy it to input/ (watcher will pick it up)
        dlg = QFileDialog(self)
        dlg.setFileMode(QFileDialog.ExistingFile)
        dlg.setNameFilter("Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if dlg.exec():
            files = dlg.selectedFiles()
            if files:
                src = Path(files[0])
                INPUT_DIR.mkdir(parents=True, exist_ok=True)
                dst = INPUT_DIR / src.name
                try:
                    shutil.copy2(src, dst)
                    self.status_label.setText(f"Copied to input: {dst}")
                except Exception as e:
                    QMessageBox.critical(self, "Copy Failed", str(e))

    def _refresh_logs(self):
        if WATCHER_LOG.exists():
            try:
                text = WATCHER_LOG.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            self.log_view.setPlainText(text)
            self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(900, 700)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
