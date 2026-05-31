import unittest

import numpy as np


class MolTrackDomainModelTests(unittest.TestCase):
    def test_analysis_region_can_describe_rectangular_terrace_in_native_coordinates(self) -> None:
        from moltrack.core import AnalysisRegion, AnalysisRegionKind

        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.5, 2.0, 11.5, 8.0),
        )

        self.assertEqual(region.kind, AnalysisRegionKind.TERRACE)
        self.assertEqual(region.name, "Terrace A")
        self.assertEqual(region.color_rgb, (20, 120, 240))
        self.assertEqual(region.geometry_type, "rect")
        self.assertEqual(region.coordinate_system, "native")
        self.assertEqual(region.bounds_xyxy, (1.5, 2.0, 11.5, 8.0))
        self.assertEqual(region.rect_xyxy, (1.5, 2.0, 11.5, 8.0))

    def test_analysis_region_can_describe_polygonal_ignore_region(self) -> None:
        from moltrack.core import AnalysisRegion, AnalysisRegionKind

        vertices = [(3.0, 1.0), (9.0, 2.0), (7.0, 8.0), (2.0, 6.0)]

        region = AnalysisRegion.polygon(
            kind=AnalysisRegionKind.IGNORE,
            name="Ignore drift artifact",
            color_rgb=(220, 30, 30),
            vertices_xy=vertices,
        )

        self.assertEqual(region.kind, AnalysisRegionKind.IGNORE)
        self.assertEqual(region.geometry_type, "polygon")
        self.assertIsNone(region.rect_xyxy)
        np.testing.assert_allclose(region.polygon_xy, np.asarray(vertices, dtype=np.float64))
        self.assertEqual(region.bounds_xyxy, (2.0, 1.0, 9.0, 8.0))

    def test_analysis_region_rejects_invalid_contract_values(self) -> None:
        from moltrack.core import AnalysisRegion

        with self.assertRaises(ValueError):
            AnalysisRegion.rectangle(
                kind="unknown",
                name="Bad kind",
                color_rgb=(1, 2, 3),
                rect_xyxy=(0.0, 0.0, 1.0, 1.0),
            )
        with self.assertRaises(ValueError):
            AnalysisRegion.rectangle(
                kind="custom",
                name=" ",
                color_rgb=(1, 2, 3),
                rect_xyxy=(0.0, 0.0, 1.0, 1.0),
            )
        with self.assertRaises(ValueError):
            AnalysisRegion.rectangle(
                kind="custom",
                name="Bad color",
                color_rgb=(1, 2, 300),
                rect_xyxy=(0.0, 0.0, 1.0, 1.0),
            )
        with self.assertRaises(ValueError):
            AnalysisRegion(
                kind="custom",
                name="Ambiguous geometry",
                color_rgb=(1, 2, 3),
                rect_xyxy=(0.0, 0.0, 1.0, 1.0),
                polygon_xy=np.asarray([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]),
            )

    def test_analysis_region_can_be_copied_to_all_working_frames_without_registration(self) -> None:
        from moltrack.core import AnalysisRegion, CopiedAnalysisRegion, SourceImageSeries

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=4)
        working_series = source.create_working_series(reverse_frame_order=True).remove_working_frame(1)
        region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(2.0, 3.0, 12.0, 18.0),
        )

        copied = CopiedAnalysisRegion.from_working_series(region, working_series)

        self.assertEqual(copied.working_frame_indices, (0, 1, 2))
        for working_frame_index in copied.working_frame_indices:
            self.assertTrue(copied.applies_to_working_frame(working_frame_index))
            self.assertIs(copied.region_for_working_frame(working_frame_index), region)
            self.assertEqual(copied.region_for_working_frame(working_frame_index).rect_xyxy, region.rect_xyxy)
        self.assertFalse(copied.applies_to_working_frame(3))
        with self.assertRaises(IndexError):
            copied.region_for_working_frame(3)

    def test_project_can_resolve_frame_scoped_versions_of_one_logical_region(self) -> None:
        from moltrack.core import AnalysisRegion, FrameScopedAnalysisRegion, MolTrackProject, SourceImageSeries

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=5)
        project = MolTrackProject.from_source_series(source)
        terrace_early = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace 1",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 10.0, 10.0),
        )
        terrace_late = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace 1",
            color_rgb=(20, 120, 240),
            rect_xyxy=(20.0, 0.0, 30.0, 10.0),
        )

        project = project.with_frame_scoped_analysis_regions(
            (
                FrameScopedAnalysisRegion(region=terrace_early, working_frame_indices=(0, 1)),
                FrameScopedAnalysisRegion(region=terrace_late, working_frame_indices=(2, 3, 4)),
            )
        )

        self.assertEqual(project.analysis_regions_for_working_frame(0)[0].rect_xyxy, terrace_early.rect_xyxy)
        self.assertEqual(project.analysis_regions_for_working_frame(4)[0].rect_xyxy, terrace_late.rect_xyxy)
        self.assertIs(project.region_for_working_frame("Terrace 1", 1), project.analysis_regions_for_working_frame(1)[0])
        self.assertEqual(project.region_for_working_frame("Terrace 1", 4).rect_xyxy, terrace_late.rect_xyxy)

    def test_project_rejects_overlapping_frame_scopes_for_the_same_logical_region(self) -> None:
        from moltrack.core import AnalysisRegion, FrameScopedAnalysisRegion, MolTrackProject, SourceImageSeries

        project = MolTrackProject.from_source_series(SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=3))
        region_a = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace 1",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 10.0, 10.0),
        )
        region_b = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace 1",
            color_rgb=(20, 120, 240),
            rect_xyxy=(20.0, 0.0, 30.0, 10.0),
        )

        with self.assertRaises(ValueError):
            project.with_frame_scoped_analysis_regions(
                (
                    FrameScopedAnalysisRegion(region=region_a, working_frame_indices=(0, 1)),
                    FrameScopedAnalysisRegion(region=region_b, working_frame_indices=(1, 2)),
                )
            )

    def test_registration_shift_describes_global_xy_shift_for_one_working_frame(self) -> None:
        from moltrack.core import RegistrationShift

        shift = RegistrationShift(
            working_frame_index=2,
            dx=1.25,
            dy=-0.5,
            method="phase_correlation",
        )

        self.assertEqual(shift.working_frame_index, 2)
        self.assertEqual(shift.shift_xy, (1.25, -0.5))
        self.assertEqual(shift.method, "phase_correlation")

    def test_molecular_detection_describes_one_bbox_in_native_coordinates(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        detection = MolecularDetection(
            detection_id=" mol-001 ",
            working_frame_index=2,
            source_frame_index=7,
            bbox_xyxy=(10.0, 20.0, 18.0, 28.0),
            confidence=0.875,
            model_name="yolo-molecules-v1",
            review_status="candidate",
            backend_name="yolo",
            run_mode="roi_replace",
            region_name="Terrace 1",
        )

        self.assertEqual(detection.detection_id, "mol-001")
        self.assertEqual(detection.working_frame_index, 2)
        self.assertEqual(detection.source_frame_index, 7)
        self.assertEqual(detection.coordinate_system, "native")
        self.assertEqual(detection.bbox_xyxy, (10.0, 20.0, 18.0, 28.0))
        self.assertEqual(detection.centroid_xy, (14.0, 24.0))
        self.assertEqual(detection.confidence, 0.875)
        self.assertEqual(detection.model_name, "yolo-molecules-v1")
        self.assertEqual(detection.review_status, DetectionReviewStatus.CANDIDATE)
        self.assertEqual(detection.backend_name, "yolo")
        self.assertEqual(detection.run_mode, "roi_replace")
        self.assertEqual(detection.region_name, "Terrace 1")

    def test_molecular_detection_rejects_invalid_contract_values(self) -> None:
        from moltrack.core import MolecularDetection

        valid_payload = dict(
            detection_id="mol-001",
            working_frame_index=2,
            source_frame_index=7,
            bbox_xyxy=(10.0, 20.0, 18.0, 28.0),
            confidence=0.875,
            model_name="yolo-molecules-v1",
            review_status="candidate",
            backend_name="yolo",
            run_mode="full_frame",
        )

        invalid_overrides = (
            {"detection_id": " "},
            {"working_frame_index": -1},
            {"source_frame_index": -1},
            {"bbox_xyxy": (10.0, 20.0, 10.0, 28.0)},
            {"confidence": 1.01},
            {"confidence": float("nan")},
            {"model_name": " "},
            {"review_status": " "},
            {"review_status": "unknown"},
            {"backend_name": " "},
            {"run_mode": "unknown"},
            {"coordinate_system": "registered"},
        )

        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides):
                payload = {**valid_payload, **overrides}
                with self.assertRaises(ValueError):
                    MolecularDetection(**payload)

    def test_detection_review_status_controls_default_analysis_membership(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection

        self.assertEqual(
            [status.value for status in DetectionReviewStatus],
            ["candidate", "accepted", "edited", "rejected", "manual", "uncertain"],
        )

        candidate = MolecularDetection(
            detection_id="mol-001",
            working_frame_index=2,
            source_frame_index=7,
            bbox_xyxy=(10.0, 20.0, 18.0, 28.0),
            confidence=0.875,
            model_name="yolo-molecules-v1",
            review_status="candidate",
            backend_name="yolo",
            run_mode="full_frame",
        )
        accepted = MolecularDetection(
            detection_id="mol-002",
            working_frame_index=2,
            source_frame_index=7,
            bbox_xyxy=(20.0, 30.0, 28.0, 38.0),
            confidence=0.75,
            model_name="yolo-molecules-v1",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
        )

        self.assertEqual(candidate.review_status, DetectionReviewStatus.CANDIDATE)
        self.assertFalse(candidate.included_in_default_analysis)
        self.assertTrue(accepted.included_in_default_analysis)
        self.assertTrue(DetectionReviewStatus.EDITED.included_in_default_analysis)
        self.assertTrue(DetectionReviewStatus.MANUAL.included_in_default_analysis)
        self.assertFalse(DetectionReviewStatus.REJECTED.included_in_default_analysis)
        self.assertFalse(DetectionReviewStatus.UNCERTAIN.included_in_default_analysis)
        self.assertEqual(DetectionReviewStatus.default_for_yolo(), DetectionReviewStatus.CANDIDATE)

    def test_project_can_store_optional_registration_shifts_by_working_frame(self) -> None:
        from moltrack.core import MolTrackProject, RegistrationShift, SourceImageSeries

        project = MolTrackProject.from_source_series(SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=3))

        self.assertEqual(project.registration_shifts, ())
        self.assertIsNone(project.registration_shift_for_working_frame(1))

        updated = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=2, dx=-0.5, dy=0.25, method="ecc_translation"),
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="reference"),
            )
        )

        self.assertEqual([shift.working_frame_index for shift in updated.registration_shifts], [0, 2])
        self.assertEqual(updated.registration_shift_for_working_frame(2).shift_xy, (-0.5, 0.25))
        self.assertIsNone(updated.registration_shift_for_working_frame(1))

    def test_project_rejects_invalid_registration_shift_contracts(self) -> None:
        from moltrack.core import MolTrackProject, RegistrationShift, SourceImageSeries

        project = MolTrackProject.from_source_series(SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=2))

        with self.assertRaises(ValueError):
            RegistrationShift(working_frame_index=0, dx=float("nan"), dy=0.0)

        with self.assertRaises(ValueError):
            project.with_registration_shifts(
                (
                    RegistrationShift(working_frame_index=1, dx=0.0, dy=0.0),
                    RegistrationShift(working_frame_index=1, dx=0.5, dy=0.0),
                )
            )

        with self.assertRaises(IndexError):
            project.with_registration_shifts(
                (RegistrationShift(working_frame_index=2, dx=0.0, dy=0.0),)
            )

    def test_project_remaps_registration_shifts_when_working_frame_is_removed(self) -> None:
        from moltrack.core import MolTrackProject, RegistrationShift, SourceImageSeries

        project = MolTrackProject.from_source_series(SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=4))
        project = project.with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="reference"),
                RegistrationShift(working_frame_index=1, dx=1.0, dy=0.0, method="phase_correlation"),
                RegistrationShift(working_frame_index=3, dx=3.0, dy=-1.0, method="phase_correlation"),
            )
        )

        updated = project.remove_working_frame(1)

        self.assertEqual([shift.working_frame_index for shift in updated.registration_shifts], [0, 2])
        self.assertEqual(updated.registration_shift_for_working_frame(0).shift_xy, (0.0, 0.0))
        self.assertEqual(updated.registration_shift_for_working_frame(2).shift_xy, (3.0, -1.0))
        self.assertIsNone(updated.registration_shift_for_working_frame(1))

    def test_project_from_source_series_preserves_working_to_source_frame_mapping(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries

        source = SourceImageSeries(
            source_uri="C:/data/movie.mpp",
            frame_count=3,
            display_name="movie.mpp",
        )

        project = MolTrackProject.from_source_series(source, project_name="test project")

        self.assertEqual(project.project_name, "test project")
        self.assertEqual(project.source_series, source)
        self.assertEqual(project.working_series.frame_count, 3)
        self.assertEqual(project.working_series.source_frame_indices(), [0, 1, 2])
        self.assertEqual(project.working_series.get_source_frame_index(2), 2)
        self.assertEqual(project.working_series.get_working_frame(1).source_frame_index, 1)

    def test_working_series_requires_contiguous_working_frame_indexes(self) -> None:
        from moltrack.core import SourceImageSeries, WorkingFrame, WorkingImageSeries

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=3)

        with self.assertRaises(ValueError):
            WorkingImageSeries(
                source_series=source,
                frames=(
                    WorkingFrame(working_frame_index=0, source_frame_index=0),
                    WorkingFrame(working_frame_index=2, source_frame_index=1),
                ),
            )

    def test_working_series_rejects_source_frame_index_outside_source_series(self) -> None:
        from moltrack.core import SourceImageSeries, WorkingFrame, WorkingImageSeries

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=2)

        with self.assertRaises(IndexError):
            WorkingImageSeries(
                source_series=source,
                frames=(
                    WorkingFrame(working_frame_index=0, source_frame_index=0),
                    WorkingFrame(working_frame_index=1, source_frame_index=2),
                ),
            )

    def test_project_rejects_working_series_from_different_source(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries

        source_a = SourceImageSeries(source_uri="C:/data/a.mpp", frame_count=2)
        source_b = SourceImageSeries(source_uri="C:/data/b.mpp", frame_count=2)

        with self.assertRaises(ValueError):
            MolTrackProject(
                source_series=source_a,
                working_series=source_b.create_working_series(),
            )

    def test_project_from_source_series_can_create_reversed_working_series(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=4)

        project = MolTrackProject.from_source_series(source, reverse_frame_order=True)

        self.assertEqual(project.working_series.source_frame_indices(), [3, 2, 1, 0])
        self.assertEqual(project.working_series.get_working_frame(0).working_frame_index, 0)
        self.assertEqual(project.working_series.get_working_frame(0).source_frame_index, 3)
        self.assertEqual(project.working_series.get_working_frame(3).working_frame_index, 3)
        self.assertEqual(project.working_series.get_working_frame(3).source_frame_index, 0)

    def test_project_can_remove_working_frame_and_reindex_remaining_frames(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=4)
        project = MolTrackProject.from_source_series(source)

        updated = project.remove_working_frame(1)

        self.assertIs(updated.source_series, source)
        self.assertEqual(project.working_series.source_frame_indices(), [0, 1, 2, 3])
        self.assertEqual(updated.working_series.source_frame_indices(), [0, 2, 3])
        self.assertEqual(
            [frame.working_frame_index for frame in updated.working_series.frames],
            [0, 1, 2],
        )
        self.assertEqual(updated.working_series.removed_source_frame_indices(), [1])

    def test_removed_frame_from_reversed_working_series_preserves_source_provenance(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=4)
        project = MolTrackProject.from_source_series(source, reverse_frame_order=True)

        updated = project.remove_working_frame(1)

        self.assertEqual(project.working_series.source_frame_indices(), [3, 2, 1, 0])
        self.assertEqual(updated.working_series.source_frame_indices(), [3, 1, 0])
        self.assertEqual(
            [(frame.working_frame_index, frame.source_frame_index) for frame in updated.working_series.frames],
            [(0, 3), (1, 1), (2, 0)],
        )
        self.assertEqual(updated.working_series.removed_source_frame_indices(), [2])

    def test_cannot_remove_last_working_frame(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries

        source = SourceImageSeries(source_uri="C:/data/single.s94", frame_count=1)
        project = MolTrackProject.from_source_series(source)

        with self.assertRaises(ValueError):
            project.remove_working_frame(0)


if __name__ == "__main__":
    unittest.main()
