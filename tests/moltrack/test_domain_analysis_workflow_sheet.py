from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from moltrack.ui.domain_analysis_workflow_sheet import (
    DomainAnalysisWorkflowActions,
    M6CalibrationWorkflowSheet,
)


def test_calibration_status_does_not_expose_the_output_parent_path() -> None:
    app = QApplication.instance() or QApplication([])
    output = Path("C:/Users/operator/private-run/report-v2-123")
    sheet = M6CalibrationWorkflowSheet(
        DomainAnalysisWorkflowActions(run_calibration=lambda: output)
    )
    try:
        sheet.run_campaign_button.click()
        app.processEvents()

        assert sheet.status_label.text() == (
            "Calibration report published. report-v2-123"
        )
    finally:
        sheet.close()
        sheet.deleteLater()
        app.processEvents()
