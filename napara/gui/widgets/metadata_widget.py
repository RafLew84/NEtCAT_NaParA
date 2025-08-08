# napara/gui/widgets/metadata_widget.py
from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel

class MetadataWidget(QWidget):
    """Simple metadata placeholder (filename, shape px, physical size nm, scale, channel)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.form = QFormLayout(self)
        self.lbl_filename = QLabel("-")
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
        self.lbl_shape.setText(f"{shape[1]} × {shape[0]}" if shape else "-")
        if size_nm:
            self.lbl_size_nm.setText(f"{size_nm[0]:.4g} × {size_nm[1]:.4g}")
        else:
            self.lbl_size_nm.setText("-")
        self.lbl_scale.setText(f"{scale_nm_per_px:.4g}" if scale_nm_per_px else "-")
        self.lbl_channel.setText(channel or "-")
