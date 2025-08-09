# napara/gui/widgets/metadata_widget.py
from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel
from PyQt6.QtCore import Qt

class MetadataWidget(QWidget):
    """Simple metadata placeholder (filename, shape px, physical size nm, scale, channel)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.form = QFormLayout(self)
        self.lbl_filename = ElidedLabel("-") 
        # self.lbl_filename.setTextElideMode(Qt.TextElideMode.ElideLeft)
        self.lbl_shape = QLabel("-")
        self.lbl_size_nm = QLabel("-")   
        self.lbl_scale = QLabel("-")
        self.lbl_channel = QLabel("-")

        self.form.addRow("File:", self.lbl_filename)
        self.form.addRow("Shape (px):", self.lbl_shape)
        self.form.addRow("Size (nm):", self.lbl_size_nm)  
        self.form.addRow("Scale (nm/px):", self.lbl_scale)
        self.form.addRow("Channel:", self.lbl_channel)

    def set_metadata(
        self,
        *,
        filename: str = "",
        shape: tuple[int, int] | None = None,
        size_nm: tuple[float, float] | None = None,       
        scale_nm_per_px: float | None = None,
        channel: str | None = None,
    ):
        """Update metadata labels."""
        self.lbl_filename.setText(filename or "-")
        # self.lbl_filename.setToolTip(filename or "")
        self.lbl_shape.setText(f"{shape[1]} × {shape[0]}" if shape else "-")
        if size_nm:
            self.lbl_size_nm.setText(f"{size_nm[0]:.4g} × {size_nm[1]:.4g}")
        else:
            self.lbl_size_nm.setText("-")
        self.lbl_scale.setText(f"{scale_nm_per_px:.4g}" if scale_nm_per_px else "-")
        self.lbl_channel.setText(channel or "-")

# from PyQt6.QtWidgets import QLabel
# from PyQt6.QtCore import Qt, pyqtSignal

class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setMinimumWidth(50) 

    def setText(self, text: str):
        self._full_text = text
        self._update_elided_text()
        self.setToolTip(self._full_text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self):
        fm = self.fontMetrics()
        elided_text = fm.elidedText(
            self._full_text, 
            Qt.TextElideMode.ElideLeft, 
            self.width()
        )
        super().setText(elided_text)
