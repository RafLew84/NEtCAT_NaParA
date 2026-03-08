from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QListWidgetItem,
)

from stmbrowser.services import (
    collect_supported_from_directory,
    collect_supported_from_files,
    load_supported_stm_image,
)
from stmbrowser.ui.widgets import FileListPanel, PairPreviewWidget


class STMBrowserMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: list[str] = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self.setWindowTitle("STM Browser")
        self.resize(1200, 800)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.file_panel = FileListPanel(self)
        self.preview = PairPreviewWidget(self)
        splitter.addWidget(self.file_panel)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 940])
        self.setCentralWidget(splitter)

        self.statusBar().showMessage("Ready")

    def _connect_signals(self) -> None:
        self.file_panel.btn_add_files.clicked.connect(self._on_add_files)
        self.file_panel.btn_add_folder.clicked.connect(self._on_add_folder)
        self.file_panel.btn_clear.clicked.connect(self._on_clear)
        self.file_panel.list.currentRowChanged.connect(self._on_row_selected)

    def _on_add_files(self) -> None:
        filt = "STM files (*.stp *.STP *.s94 *.S94);;All files (*.*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Add STM files", "", filt)
        if not paths:
            return
        supported = collect_supported_from_files(paths)
        self._append_paths(supported)

    def _on_add_folder(self) -> None:
        root = QFileDialog.getExistingDirectory(self, "Add folder with STM files")
        if not root:
            return
        found = collect_supported_from_directory(root, recursive=True)
        if not found:
            QMessageBox.information(self, "No STM files", "No .stp/.s94 files found in selected folder.")
            return
        self._append_paths(found)

    def _append_paths(self, paths: list[str]) -> None:
        if not paths:
            QMessageBox.information(self, "No supported files", "Selection contains no .stp/.s94 files.")
            return

        existing = set(self._paths)
        added = 0
        for p in paths:
            if p in existing:
                continue
            existing.add(p)
            self._paths.append(p)
            added += 1

            item = QListWidgetItem(os.path.basename(p))
            item.setToolTip(p)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.file_panel.list.addItem(item)

        self._refresh_pair_selection_state()

        if added == 0:
            self.statusBar().showMessage("No new files added (all already on the list).", 3000)
            return

        self.statusBar().showMessage(f"Added {added} file(s).", 3000)

    def _on_clear(self) -> None:
        self._paths.clear()
        self.file_panel.list.clear()
        self.preview.clear()
        self.statusBar().showMessage("List cleared.", 2000)

    def _refresh_pair_selection_state(self) -> None:
        count = self.file_panel.list.count()
        last_idx = count - 1
        for i in range(count):
            item = self.file_panel.list.item(i)
            if item is None:
                continue
            flags = item.flags() | Qt.ItemFlag.ItemIsEnabled
            if i == last_idx:
                flags &= ~Qt.ItemFlag.ItemIsSelectable
            else:
                flags |= Qt.ItemFlag.ItemIsSelectable
            item.setFlags(flags)

        if count < 2:
            self.file_panel.list.setCurrentRow(-1)
            self.preview.clear()
            return

        row = self.file_panel.list.currentRow()
        if row < 0 or row >= last_idx:
            self.file_panel.list.setCurrentRow(0)

    def _on_row_selected(self, row: int) -> None:
        if row < 0:
            self.preview.clear()
            return

        count = self.file_panel.list.count()
        if row >= count - 1:
            self.preview.clear()
            return

        item_a = self.file_panel.list.item(row)
        item_b = self.file_panel.list.item(row + 1)
        path_a = item_a.data(Qt.ItemDataRole.UserRole) if item_a else None
        path_b = item_b.data(Qt.ItemDataRole.UserRole) if item_b else None
        if not path_a or not path_b:
            self.preview.clear()
            return

        try:
            img_a = load_supported_stm_image(path_a)
            img_b = load_supported_stm_image(path_b)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Load error",
                f"Cannot load selected pair:\n{path_a}\n{path_b}\n\n{e}",
            )
            return

        self.preview.set_pair(img_a, img_b)
        self.statusBar().showMessage(f"Pair: {path_a}  |  {path_b}", 3000)
