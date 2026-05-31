import unittest


class MolTrackDomainModelTests(unittest.TestCase):
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
