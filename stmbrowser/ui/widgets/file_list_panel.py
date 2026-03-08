from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QAbstractItemView,
)


class FileListPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self.btn_add_files = QPushButton("Add Files…", self)
        self.btn_add_folder = QPushButton("Add Folder…", self)
        self.btn_clear = QPushButton("Clear", self)
        row.addWidget(self.btn_add_files)
        row.addWidget(self.btn_add_folder)
        row.addWidget(self.btn_clear)
        layout.addLayout(row)

        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.list, 1)
