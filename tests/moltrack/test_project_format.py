import unittest
import json
import tempfile
import zipfile
from pathlib import Path

import numpy as np


class MolTrackProjectFormatTests(unittest.TestCase):
    def test_manifest_defines_zip_bundle_schema_sources_and_frame_mapping(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries
        from moltrack.persistence import MANIFEST_PATH, MOLTRACK_PROJECT_SCHEMA, build_project_manifest

        source = SourceImageSeries(
            source_uri="frame_a_series_4_frames",
            source_uris=("frame_a.stp", "frame_b.s94", "frame_c.stp", "frame_d.s94"),
            frame_count=4,
            display_name="field series",
        )
        project = MolTrackProject.from_source_series(
            source,
            project_name="molecule field",
            reverse_frame_order=True,
        ).remove_working_frame(1)

        manifest = build_project_manifest(project)

        self.assertEqual(MANIFEST_PATH, "manifest.json")
        self.assertEqual(manifest["schema"], MOLTRACK_PROJECT_SCHEMA)
        self.assertEqual(manifest["bundle"], {"container": "zip", "manifest_path": "manifest.json"})
        self.assertEqual(manifest["project"]["name"], "molecule field")
        self.assertEqual(
            manifest["source_series"],
            {
                "source_uri": "frame_a_series_4_frames",
                "source_uris": ["frame_a.stp", "frame_b.s94", "frame_c.stp", "frame_d.s94"],
                "display_name": "field series",
                "frame_count": 4,
            },
        )
        self.assertEqual(
            manifest["working_series"]["frame_mapping"],
            [
                {"working_frame_index": 0, "source_frame_index": 3},
                {"working_frame_index": 1, "source_frame_index": 1},
                {"working_frame_index": 2, "source_frame_index": 0},
            ],
        )
        self.assertEqual(manifest["working_series"]["removed_source_frame_indices"], [2])
        self.assertNotIn("masks", manifest)

    def test_manifest_is_json_serializable(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries
        from moltrack.persistence import build_project_manifest

        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="movie.mpp", frame_count=2),
            project_name="json check",
        )

        encoded = json.dumps(build_project_manifest(project), ensure_ascii=False, sort_keys=True)
        decoded = json.loads(encoded)

        self.assertEqual(decoded["schema"], "moltrack.project.v1")
        self.assertEqual(decoded["working_series"]["frame_mapping"][1]["source_frame_index"], 1)

    def test_save_and_load_empty_project_round_trips_manifest_state(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries
        from moltrack.persistence import MANIFEST_PATH, load_project, save_project

        source = SourceImageSeries(
            source_uri="frame_a_series_4_frames",
            source_uris=("frame_a.stp", "frame_b.s94", "frame_c.stp", "frame_d.s94"),
            frame_count=4,
            display_name="field series",
        )
        project = MolTrackProject.from_source_series(
            source,
            project_name="round trip",
            reverse_frame_order=True,
        ).remove_working_frame(2)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "round_trip.moltrack"

            save_project(path, project)

            self.assertTrue(zipfile.is_zipfile(path))
            with zipfile.ZipFile(path, mode="r") as zf:
                self.assertEqual(zf.namelist(), [MANIFEST_PATH])

            loaded = load_project(path)

        self.assertEqual(loaded.project_name, "round trip")
        self.assertEqual(loaded.source_series.source_uri, "frame_a_series_4_frames")
        self.assertEqual(loaded.source_series.source_uris, ("frame_a.stp", "frame_b.s94", "frame_c.stp", "frame_d.s94"))
        self.assertEqual(loaded.source_series.display_name, "field series")
        self.assertEqual(loaded.source_series.frame_count, 4)
        self.assertIsNone(loaded.source_series.raw_frames)
        self.assertEqual(loaded.working_series.source_frame_indices(), [3, 2, 0])
        self.assertEqual(loaded.working_series.removed_source_frame_indices(), [1])

    def test_save_and_load_project_round_trips_analysis_regions(self) -> None:
        from moltrack.core import AnalysisRegion, CopiedAnalysisRegion, MolTrackProject, SourceImageSeries
        from moltrack.persistence import load_project, save_project

        source = SourceImageSeries(source_uri="movie.mpp", frame_count=3)
        project = MolTrackProject.from_source_series(source, project_name="regions")
        terrace = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(1.5, 2.0, 11.5, 8.0),
        )
        ignore = AnalysisRegion.polygon(
            kind="ignore",
            name="Ignore artifact",
            color_rgb=(240, 40, 40),
            vertices_xy=[(1.0, 1.0), (4.0, 1.5), (3.0, 5.0)],
        )
        project = project.with_analysis_regions(
            (terrace, ignore),
            copied_analysis_regions=(CopiedAnalysisRegion.from_working_series(terrace, project.working_series),),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "regions.moltrack"

            save_project(path, project)
            loaded = load_project(path)

        self.assertEqual([region.name for region in loaded.analysis_regions], ["Terrace A", "Ignore artifact"])
        self.assertEqual(loaded.analysis_regions[0].kind.value, "terrace")
        self.assertEqual(loaded.analysis_regions[0].rect_xyxy, (1.5, 2.0, 11.5, 8.0))
        self.assertEqual(loaded.analysis_regions[1].kind.value, "ignore")
        np.testing.assert_allclose(
            loaded.analysis_regions[1].polygon_xy,
            np.asarray([(1.0, 1.0), (4.0, 1.5), (3.0, 5.0)], dtype=np.float64),
        )
        self.assertEqual(len(loaded.copied_analysis_regions), 1)
        self.assertEqual(loaded.copied_analysis_regions[0].region.name, "Terrace A")
        self.assertEqual(loaded.copied_analysis_regions[0].working_frame_indices, (0, 1, 2))

    def test_save_and_load_project_round_trips_frame_scoped_analysis_regions(self) -> None:
        from moltrack.core import AnalysisRegion, FrameScopedAnalysisRegion, MolTrackProject, SourceImageSeries
        from moltrack.persistence import load_project, save_project

        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="movie.mpp", frame_count=5),
            project_name="scoped regions",
        )
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

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scoped_regions.moltrack"

            save_project(path, project)
            loaded = load_project(path)

        self.assertEqual(len(loaded.frame_scoped_analysis_regions), 2)
        self.assertEqual(loaded.frame_scoped_analysis_regions[0].region.name, "Terrace 1")
        self.assertEqual(loaded.frame_scoped_analysis_regions[0].working_frame_indices, (0, 1))
        self.assertEqual(loaded.region_for_working_frame("Terrace 1", 0).rect_xyxy, (0.0, 0.0, 10.0, 10.0))
        self.assertEqual(loaded.region_for_working_frame("Terrace 1", 4).rect_xyxy, (20.0, 0.0, 30.0, 10.0))

    def test_save_and_load_project_round_trips_registration_shifts(self) -> None:
        from moltrack.core import MolTrackProject, RegistrationShift, SourceImageSeries
        from moltrack.persistence import load_project, save_project

        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="movie.mpp", frame_count=3),
            project_name="registered",
        ).with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=2, dx=1.25, dy=-0.5, method="phase_correlation_adjacent"),
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "registered.moltrack"

            save_project(path, project)
            loaded = load_project(path)

        self.assertEqual(len(loaded.registration_shifts), 2)
        self.assertEqual(loaded.registration_shift_for_working_frame(0).shift_xy, (0.0, 0.0))
        self.assertEqual(loaded.registration_shift_for_working_frame(2).shift_xy, (1.25, -0.5))
        self.assertEqual(loaded.registration_shift_for_working_frame(2).method, "phase_correlation_adjacent")

    def test_save_and_load_project_round_trips_molecular_detections(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolTrackProject, MolecularDetection, SourceImageSeries
        from moltrack.persistence import load_project, save_project

        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="movie.mpp", frame_count=3),
            project_name="detections",
        ).with_molecular_detections(
            (
                MolecularDetection(
                    detection_id="accepted-full-frame",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(1.0, 2.0, 4.0, 6.0),
                    confidence=0.93,
                    model_name="yolo11s_v4.0_pro.pt",
                    review_status=DetectionReviewStatus.ACCEPTED,
                    backend_name="yolo",
                    run_mode="full_frame",
                ),
                MolecularDetection(
                    detection_id="roi-edited",
                    working_frame_index=1,
                    source_frame_index=1,
                    bbox_xyxy=(10.5, 20.25, 12.75, 23.5),
                    confidence=0.81,
                    model_name="yolo11s_v4.0_pro.pt",
                    review_status=DetectionReviewStatus.EDITED,
                    backend_name="yolo",
                    run_mode="roi_replace",
                    region_name="Terrace A",
                ),
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "detections.moltrack"

            save_project(path, project)
            loaded = load_project(path)

        self.assertEqual(loaded.molecular_detections, project.molecular_detections)
        self.assertEqual(loaded.molecular_detections[0].review_status, DetectionReviewStatus.ACCEPTED)
        self.assertEqual(loaded.molecular_detections[0].bbox_xyxy, (1.0, 2.0, 4.0, 6.0))
        self.assertEqual(loaded.molecular_detections[0].backend_name, "yolo")
        self.assertEqual(loaded.molecular_detections[0].run_mode, "full_frame")
        self.assertIsNone(loaded.molecular_detections[0].region_name)
        self.assertEqual(loaded.molecular_detections[1].review_status, DetectionReviewStatus.EDITED)
        self.assertEqual(loaded.molecular_detections[1].bbox_xyxy, (10.5, 20.25, 12.75, 23.5))
        self.assertEqual(loaded.molecular_detections[1].run_mode, "roi_replace")
        self.assertEqual(loaded.molecular_detections[1].region_name, "Terrace A")

    def test_manifest_records_molecular_detection_provenance(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolTrackProject, MolecularDetection, SourceImageSeries
        from moltrack.persistence import build_project_manifest

        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="movie.mpp", frame_count=2),
            project_name="detection manifest",
        ).with_molecular_detections(
            (
                MolecularDetection(
                    detection_id="roi-candidate",
                    working_frame_index=1,
                    source_frame_index=1,
                    bbox_xyxy=(2.0, 3.0, 5.0, 7.0),
                    confidence=0.66,
                    model_name="yolo11s_v4.0_pro.pt",
                    review_status=DetectionReviewStatus.CANDIDATE,
                    backend_name="yolo",
                    run_mode="roi_replace",
                    region_name="Terrace A",
                ),
            )
        )

        manifest = build_project_manifest(project)

        self.assertEqual(
            manifest["molecular_detections"],
            [
                {
                    "detection_id": "roi-candidate",
                    "working_frame_index": 1,
                    "source_frame_index": 1,
                    "bbox_xyxy": [2.0, 3.0, 5.0, 7.0],
                    "confidence": 0.66,
                    "model_name": "yolo11s_v4.0_pro.pt",
                    "review_status": "candidate",
                    "backend_name": "yolo",
                    "run_mode": "roi_replace",
                    "region_name": "Terrace A",
                    "coordinate_system": "native",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
