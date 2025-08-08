from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout

class ImageListPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        self.list = QListWidget(self)
        layout.addWidget(self.list)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Images…", self)
        self.btn_remove = QPushButton("Remove", self)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        layout.addLayout(btn_row)
