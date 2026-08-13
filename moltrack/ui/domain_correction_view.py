from __future__ import annotations

from moltrack.analysis.domain_analysis import (
    ApplyPreparedDomainCorrection,
    DomainAnalysisWorkspaceController,
    DiscardPreparedDomainCorrection,
    PreviewManualOrientation,
    PreviewManualOrientationReset,
    PreviewCreateManualDomain,
    PreviewMoveToManualDomain,
    PreviewDeleteManualDomain,
    PreviewRestoreManualDomain,
    SelectDomainMolecules,
)


class DomainCorrectionActionBinding:
    """Translate Qt correction signals into workspace actions."""

    def __init__(self, controller: DomainAnalysisWorkspaceController) -> None:
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        self._controller = controller

    def select_molecule(self, source_id: str) -> None:
        self._controller.dispatch(SelectDomainMolecules((source_id,)))

    def preview_manual_orientation(
        self,
        orientation_label: str,
        reason_code: object,
    ) -> None:
        if reason_code is not None and not isinstance(reason_code, str):
            raise TypeError("reason_code must be text or None.")
        self._controller.dispatch(PreviewManualOrientation(
            orientation_label,
            reason_code,
        ))

    def preview_orientation_reset(self) -> None:
        self._controller.dispatch(PreviewManualOrientationReset())

    def apply_prepared_correction(self) -> None:
        prepared = self._controller.snapshot.domain_corrections.prepared
        if prepared is not None:
            self._controller.dispatch(ApplyPreparedDomainCorrection(prepared))

    def discard_prepared_correction(self) -> None:
        self._controller.dispatch(DiscardPreparedDomainCorrection())

    def preview_create_manual_domain(self) -> None:
        self._controller.dispatch(PreviewCreateManualDomain())

    def preview_move_to_manual_domain(self, manual_domain_id: str) -> None:
        self._controller.dispatch(PreviewMoveToManualDomain(manual_domain_id))

    def preview_delete_manual_domain(self, manual_domain_id: str) -> None:
        self._controller.dispatch(PreviewDeleteManualDomain(manual_domain_id))

    def preview_restore_manual_domain(self, manual_domain_id: str) -> None:
        self._controller.dispatch(PreviewRestoreManualDomain(manual_domain_id))


__all__ = ["DomainCorrectionActionBinding"]
