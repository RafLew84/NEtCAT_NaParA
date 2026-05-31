import unittest
import json
import tempfile
import zipfile
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
