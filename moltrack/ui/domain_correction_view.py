from __future__ import annotations

from typing import cast

from moltrack.analysis.domain_analysis import (
    ApplyPreparedDomainCorrection,
    BoundaryResolution,
    DomainAnalysisWorkspaceController,
    DomainSelectionView,
    DiscardPreparedDomainCorrection,
    ClearDomainMoleculeSelection,
    PreviewManualOrientation,
    PreviewManualOrientationReset,
    PreviewCreateManualDomain,
    PreviewMoveToManualDomain,
    PreviewDeleteManualDomain,
    PreviewRestoreManualDomain,
    RestoreMemberResolution,
    SelectDomainMoleculesByPolygons,
    ToggleDomainMoleculeSelection,
)


class DomainCorrectionActionBinding:
    """Translate Qt correction signals into workspace actions."""

    def __init__(self, controller: DomainAnalysisWorkspaceController) -> None:
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        self._controller = controller

    def select_molecule(self, source_id: str) -> None:
        self._controller.dispatch(ToggleDomainMoleculeSelection(source_id))

    def select_polygons(self, polygons: object, target_view: str) -> None:
        if not isinstance(polygons, tuple):
            raise TypeError("polygons must be a tuple.")
        if target_view not in {"raw", "expanded_aligned"}:
            raise ValueError(f"Unsupported target view: {target_view!r}.")
        self._controller.dispatch(SelectDomainMoleculesByPolygons(
            polygons=polygons,
            target_view=cast(DomainSelectionView, target_view),
        ))

    def clear_selection(self) -> None:
        self._controller.dispatch(ClearDomainMoleculeSelection())

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

    def apply_prepared_correction(self, confirmed: bool = False) -> None:
        prepared = self._controller.snapshot.domain_corrections.prepared
        if prepared is not None:
            action = (
                ApplyPreparedDomainCorrection.confirmed(prepared)
                if confirmed
                else ApplyPreparedDomainCorrection(prepared)
            )
            self._controller.dispatch(action)

    def discard_prepared_correction(self) -> None:
        self._controller.dispatch(DiscardPreparedDomainCorrection())

    def preview_create_manual_domain(self) -> None:
        self._controller.dispatch(PreviewCreateManualDomain())

    def preview_move_to_manual_domain(
        self,
        manual_domain_id: str,
        boundary_resolution: object = None,
    ) -> None:
        if boundary_resolution not in {None, "preserve", "clear"}:
            raise ValueError("Unsupported boundary resolution.")
        self._controller.dispatch(PreviewMoveToManualDomain(
            manual_domain_id,
            cast(BoundaryResolution | None, boundary_resolution),
        ))

    def preview_delete_manual_domain(self, manual_domain_id: str) -> None:
        self._controller.dispatch(PreviewDeleteManualDomain(manual_domain_id))

    def preview_restore_manual_domain(
        self,
        manual_domain_id: str,
        member_resolutions: object = (),
    ) -> None:
        if not isinstance(member_resolutions, tuple):
            raise TypeError("member_resolutions must be a tuple.")
        normalized = tuple(
            (
                source_id,
                cast(RestoreMemberResolution, resolution),
            )
            for source_id, resolution in member_resolutions
            if isinstance(source_id, str)
            and resolution in {"move_back", "keep_current"}
        )
        if len(normalized) != len(member_resolutions):
            raise ValueError("Unsupported restore member resolution.")
        self._controller.dispatch(PreviewRestoreManualDomain(
            manual_domain_id,
            normalized,
        ))


__all__ = ["DomainCorrectionActionBinding"]
