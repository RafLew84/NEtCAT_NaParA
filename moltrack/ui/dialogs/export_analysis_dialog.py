from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import (
    MolecularFrameRangeSelection,
    MolecularM6OrientationAnalysisSettings,
)
from moltrack.persistence import AnalysisExportSettings


class ExportAnalysisDialog(QDialog):
    """Collect one validated, immutable analysis export request."""

    _SCOPE_OPTIONS = (
        ("Current frame", "current_frame"),
        ("Selected ranges", "selected_ranges"),
        ("Full working series", "full_working_series"),
    )
    _FORMAT_OPTIONS = (("Directory", "directory"), ("ZIP", "zip"))

    def __init__(
        self,
        *,
        frame_count: int,
        active_frame_index: int,
        source_view: str,
        use_segmentation_centroids: bool,
        intensity_metric: str,
        intensity_unit: str,
        background_inner_radius_px: int,
        background_outer_radius_px: int,
        density_grid_shape: tuple[int, int],
        selected_ranges: MolecularFrameRangeSelection | None,
        m6_orientation_settings: MolecularM6OrientationAnalysisSettings | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._frame_count = int(frame_count)
        self._active_frame_index = int(active_frame_index)
        self._source_view = str(source_view)
        self._use_segmentation_centroids = bool(use_segmentation_centroids)
        self._intensity_metric = str(intensity_metric)
        self._intensity_unit = str(intensity_unit)
        self._background_inner_radius_px = int(background_inner_radius_px)
        self._background_outer_radius_px = int(background_outer_radius_px)
        self._density_grid_shape = tuple(int(value) for value in density_grid_shape)
        self._selected_ranges = selected_ranges
        self._m6_orientation_settings = m6_orientation_settings

        self.setWindowTitle("Export Analysis")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_scope = QComboBox(self)
        for label, value in self._SCOPE_OPTIONS:
            self.cmb_scope.addItem(label, value)
        selected_index = self.cmb_scope.findData("selected_ranges")
        selected_item = self.cmb_scope.model().item(selected_index)
        if selected_item is not None:
            selected_item.setEnabled(selected_ranges is not None)
        form.addRow("Scope", self.cmb_scope)

        content_widget = QWidget(self)
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.chk_tables = QCheckBox("Tables", content_widget)
        self.chk_tables.setChecked(True)
        self.chk_spatial_grids = QCheckBox("Spatial grids", content_widget)
        self.chk_plots = QCheckBox("SVG/PNG plots", content_widget)
        content_layout.addWidget(self.chk_tables)
        content_layout.addWidget(self.chk_spatial_grids)
        content_layout.addWidget(self.chk_plots)
        content_layout.addStretch(1)
        form.addRow("Include", content_widget)

        self.cmb_package_format = QComboBox(self)
        for label, value in self._FORMAT_OPTIONS:
            self.cmb_package_format.addItem(label, value)
        form.addRow("Package", self.cmb_package_format)

        destination_widget = QWidget(self)
        destination_layout = QHBoxLayout(destination_widget)
        destination_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_destination = QLineEdit(destination_widget)
        self.btn_browse = QPushButton("Browse...", destination_widget)
        destination_layout.addWidget(self.edit_destination, 1)
        destination_layout.addWidget(self.btn_browse)
        form.addRow("Destination", destination_widget)

        self.chk_overwrite = QCheckBox("Replace existing package", self)
        form.addRow("", self.chk_overwrite)

        centroid_mode = (
            "Segmentation centroids"
            if self._use_segmentation_centroids
            else "BBox centers"
        )
        self.lbl_source_view = QLabel(self._source_view, self)
        self.lbl_centroid_mode = QLabel(centroid_mode, self)
        self.lbl_intensity_metric = QLabel(self._intensity_metric, self)
        form.addRow("Source view", self.lbl_source_view)
        form.addRow("Position source", self.lbl_centroid_mode)
        form.addRow("Intensity metric", self.lbl_intensity_metric)
        layout.addLayout(form)

        self.lbl_comparison_requirement = QLabel("", self)
        self.lbl_comparison_requirement.setWordWrap(True)
        if selected_ranges is None:
            self.lbl_comparison_requirement.setText(
                "Run Compare ranges in Position Analysis to export selected ranges or "
                "spatial grids."
            )
        layout.addWidget(self.lbl_comparison_requirement)

        self.lbl_validation = QLabel("", self)
        self.lbl_validation.setWordWrap(True)
        self.lbl_validation.setStyleSheet("color: #b42318;")
        layout.addWidget(self.lbl_validation)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.btn_export = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_export.setText("Export")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.cmb_scope.currentIndexChanged.connect(self._refresh_options_and_validation)
        self.cmb_package_format.currentIndexChanged.connect(
            self._refresh_options_and_validation
        )
        self.chk_tables.toggled.connect(self._refresh_options_and_validation)
        self.chk_spatial_grids.toggled.connect(self._refresh_options_and_validation)
        self.chk_plots.toggled.connect(self._refresh_options_and_validation)
        self.edit_destination.textChanged.connect(self._refresh_options_and_validation)
        self.btn_browse.clicked.connect(self._browse_destination)
        self._refresh_options_and_validation()

    def scope_options(self) -> tuple[tuple[str, bool], ...]:
        return tuple(
            (
                value,
                bool(self.cmb_scope.model().item(index).isEnabled()),
            )
            for index, (_label, value) in enumerate(self._SCOPE_OPTIONS)
        )

    def selected_scope(self) -> str:
        return str(self.cmb_scope.currentData())

    def set_scope(self, scope: str) -> None:
        index = self.cmb_scope.findData(str(scope))
        if index < 0:
            raise ValueError(f"Unsupported analysis export scope: {scope!r}.")
        item = self.cmb_scope.model().item(index)
        if item is None or not item.isEnabled():
            raise ValueError(f"Analysis export scope is unavailable: {scope!r}.")
        self.cmb_scope.setCurrentIndex(index)

    def analysis_context(self) -> dict[str, str]:
        return {
            "source_view": self._source_view,
            "centroid_mode": (
                "segmentation_centroids"
                if self._use_segmentation_centroids
                else "bbox_centers"
            ),
            "intensity_metric": self._intensity_metric,
        }

    def content_option_states(self) -> dict[str, tuple[bool, bool]]:
        return {
            "tables": (self.chk_tables.isChecked(), self.chk_tables.isEnabled()),
            "spatial_grids": (
                self.chk_spatial_grids.isChecked(),
                self.chk_spatial_grids.isEnabled(),
            ),
            "plots": (self.chk_plots.isChecked(), self.chk_plots.isEnabled()),
        }

    def set_include_tables(self, enabled: bool) -> None:
        self.chk_tables.setChecked(bool(enabled))

    def set_include_spatial_grids(self, enabled: bool) -> None:
        if enabled and not self.chk_spatial_grids.isEnabled():
            raise ValueError("Spatial grids require a completed range comparison.")
        self.chk_spatial_grids.setChecked(bool(enabled))

    def set_include_plots(self, enabled: bool) -> None:
        self.chk_plots.setChecked(bool(enabled))

    def set_package_format(self, package_format: str) -> None:
        index = self.cmb_package_format.findData(str(package_format))
        if index < 0:
            raise ValueError(f"Unsupported package format: {package_format!r}.")
        self.cmb_package_format.setCurrentIndex(index)

    def set_destination_path(self, path: str | Path) -> None:
        self.edit_destination.setText(str(path))

    def validation_message(self) -> str:
        return self.lbl_validation.text()

    def comparison_requirement_message(self) -> str:
        return self.lbl_comparison_requirement.text()

    def is_export_enabled(self) -> bool:
        return self.btn_export.isEnabled()

    def export_settings(self) -> AnalysisExportSettings:
        if not self.is_export_enabled():
            raise ValueError(self.validation_message() or "Export settings are invalid.")
        return AnalysisExportSettings(
            scope=self.selected_scope(),
            destination=Path(self.edit_destination.text().strip()),
            package_format=str(self.cmb_package_format.currentData()),
            include_tables=self.chk_tables.isChecked(),
            include_spatial_grids=self.chk_spatial_grids.isChecked(),
            include_plots=self.chk_plots.isChecked(),
            frame_count=self._frame_count,
            active_frame_index=self._active_frame_index,
            source_view=self._source_view,
            use_segmentation_centroids=self._use_segmentation_centroids,
            intensity_metric=self._intensity_metric,
            intensity_unit=self._intensity_unit,
            background_inner_radius_px=self._background_inner_radius_px,
            background_outer_radius_px=self._background_outer_radius_px,
            density_grid_shape=self._density_grid_shape,
            selected_ranges=(
                self._selected_ranges
                if self.selected_scope() == "selected_ranges"
                else None
            ),
            overwrite=self.chk_overwrite.isChecked(),
            m6_orientation_settings=self._m6_orientation_settings,
        )

    def _refresh_options_and_validation(self) -> None:
        spatial_available = (
            self.selected_scope() == "selected_ranges"
            and self._selected_ranges is not None
        )
        self.chk_spatial_grids.setEnabled(spatial_available)
        if not spatial_available:
            self.chk_spatial_grids.setChecked(False)

        message = ""
        if not self.edit_destination.text().strip():
            message = "Choose a destination path."
        elif not any(
            checkbox.isChecked()
            for checkbox in (self.chk_tables, self.chk_spatial_grids, self.chk_plots)
        ):
            message = "Select at least one content type."
        self.lbl_validation.setText(message)
        self.btn_export.setEnabled(not message)

    def _browse_destination(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Analysis",
            self.edit_destination.text(),
            "ZIP archive (*.zip);;Analysis package (*)"
            if self.cmb_package_format.currentData() == "zip"
            else "Analysis package (*)",
        )
        if path:
            if self.cmb_package_format.currentData() == "zip" and not path.lower().endswith(
                ".zip"
            ):
                path += ".zip"
            self.set_destination_path(path)
