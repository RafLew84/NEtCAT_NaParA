"""Saved annotations retain their identity and coordinate meaning."""

import numpy as np
import pytest

from stmdomains.core.registration import parse_registration
from stmdomains.io.annotations import AnnotationStore


def store(payload, count=2, shape=(6, 10), **kwargs):
    registration = parse_registration(payload.get("registration"), count, shape)
    return AnnotationStore(payload, count, registration, shape, **kwargs)


def detection(identifier="molecule", frame=0, **changes):
    record = {"detection_id": identifier, "frame_index": frame,
              "bbox_xyxy": [1, 2, 5, 4], "selected": False, "origin": "manual"}
    record.update(changes)
    return record


@pytest.mark.parametrize("schema", [1, 2, 3])
def test_current_and_historical_boxes_keep_the_saved_frame_identity(schema):
    payload = {"schema_version": schema, "working_series": {"source_frame_indices": [4, 2]},
               "molecular_detections": {"frame_count": 2, "detections": [
                   detection(original_bbox_xyxy=[0, 1, 4, 3]), detection("second", 1)]}}
    annotations = store(payload)
    first = annotations.frame(0)
    item = first.detections[0]
    assert item.detection_id == "molecule"
    assert item.bbox_xyxy == (1, 2, 5, 4)
    assert item.center_xy == (3, 3)
    assert item.original_bbox_xyxy == (0, 1, 4, 3)
    assert item.metadata["selected"] is False
    assert item.source_view == "raw"
    assert annotations.frame(1).detections[0].detection_id == "second"
    assert first.detection_state == "available"


@pytest.mark.parametrize(("section", "state"), [
    (None, "missing"),
    ({"frame_count": 2, "detections": []}, "empty"),
    ({"frame_count": 2, "detections": None}, "invalid"),
    ({"frame_count": 1, "detections": [detection()]}, "invalid"),
])
def test_absent_empty_and_damaged_sections_are_distinct(section, state):
    result = store({"molecular_detections": section}).frame(0)
    assert result.detection_state == state
    assert result.detections == ()
    assert "0 molekuł" not in result.detection_message


def test_one_bad_record_and_duplicate_ids_do_not_hide_valid_bbox():
    records = [detection("valid"), detection("duplicate"), detection("duplicate", 1),
               detection("wrong-view", source_view="mystery"),
               detection("nan", bbox_xyxy=[1, 2, float("nan"), 4]),
               detection("bad-frame", frame=True)]
    result = store({"molecular_detections": {"frame_count": 2, "detections": records}}).frame(0)
    assert [item.detection_id for item in result.detections] == ["valid"]
    assert result.detection_state == "partial"
    assert any("duplicate" in message for message in result.diagnostics)


def test_no_records_in_an_available_flat_list_is_not_a_confirmed_empty_list():
    result = store({"molecular_detections": {"frame_count": 2, "detections": [detection()]}}).frame(1)
    assert result.detection_state == "available"
    assert result.detection_message == "Brak zapisanych oznaczeń na tej klatce."


def registration():
    return {"reference_frame_index": 0, "results_by_frame": [
        {"frame_index": 0, "shift_xy": [0, 0], "status": "ok"},
        {"frame_index": 1, "shift_xy": [-1.25, .5], "status": "low_confidence"},
    ]}


def test_fractional_registration_translates_only_once_and_retains_partial_boxes():
    records = [detection("shifted", 1, source_view="expanded_aligned",
                         bbox_xyxy=[2.75, 1.5, 6.75, 3.5],
                         metadata={"registered_frame_origin_xy": [.75, .5]}),
               detection("edge", 1, bbox_xyxy=[-1, 0, 1, 2]),
               detection("outside", 1, bbox_xyxy=[12, 0, 14, 2]),
               detection("conflict", 1, source_view="expanded_aligned",
                         metadata={"registered_frame_origin_xy": [9, 9]})]
    annotations = store({"registration": registration(),
                         "molecular_detections": {"frame_count": 2, "detections": records}})
    raw = annotations.frame(1)
    assert [item.detection_id for item in raw.detections] == ["shifted", "edge", "outside"]
    assert raw.detections[0].bbox_xyxy == (2, 1, 6, 3)
    assert raw.detections[1].bbox_xyxy == (-1, 0, 1, 2)
    assert raw.detections[2].outside_field
    assert "poza polem pomiarowym: 1" in raw.detection_message
    assert any("conflict" in item for item in raw.diagnostics)
    for _ in range(3):
        aligned = annotations.frame(1, "expanded_aligned")
        assert aligned.detections[0].bbox_xyxy == (2.75, 1.5, 6.75, 3.5)
        assert annotations.frame(1).detections[0].bbox_xyxy == (2, 1, 6, 3)


def test_missing_registration_hides_only_annotations_requiring_it():
    records = [detection("raw"), detection("aligned", source_view="expanded_aligned")]
    result = store({"molecular_detections": {"frame_count": 2, "detections": records}}).frame(0)
    assert [item.detection_id for item in result.detections] == ["raw"]
    assert result.detection_state == "partial"


def segmentation(identifier="mask", frame=0, **changes):
    record = {"segmentation_id": identifier, "frame_index": frame,
              "bbox_xyxy": [1, 2, 5, 4], "prompt_detection_ids": ["molecule"],
              "mask": {"encoding": "rle", "shape": [6, 10], "counts": [21, 2, 37]},
              "original_mask": {"encoding": "same-as-mask"},
              "polygon_xy": [[1, 2], [5, 2], [5, 4]], "origin": "sam2"}
    record.update(changes)
    return record


def test_bad_optional_mask_preserves_its_polygon_and_the_linked_detection():
    payload = {
        "molecular_detections": {"frame_count": 2, "detections": [detection()]},
        "molecular_segmentations": {"frame_count": 2, "segmentations": [
            segmentation(mask={"encoding": "rle", "shape": [10, 6], "counts": [60]})]},
    }
    result = store(payload).frame(0)
    assert result.detections[0].detection_id == "molecule"
    item = result.segmentations[0]
    assert item.mask is None
    assert item.polygon_xy == ((1, 2), (5, 2), (5, 4))
    assert item.prompt_detection_ids == ("molecule",)
    assert item.bbox_xyxy == (1, 2, 5, 4)
    assert item.diagnostics
    assert result.segmentation_state == "partial"


def test_mask_decoding_is_lazy_and_cache_obeys_both_limits():
    payload = {
        "molecular_detections": {"frame_count": 2, "detections": [detection(), detection("other", 1)]},
        "molecular_segmentations": {"frame_count": 2, "segmentations": [
            segmentation(), segmentation("other-mask", 1, prompt_detection_ids=["other"])]},
    }
    annotations = store(payload, cache_frames=1, cache_bytes=60)
    assert annotations.cache_info == (0, 0)
    first = annotations.frame(0)
    assert annotations.cache_info == (1, 60)
    assert first.segmentations[0].mask[2, 1:3].all()
    assert first.segmentations[0].mask.sum() == 2
    assert not first.segmentations[0].mask.flags.writeable
    second = annotations.frame(1)
    assert second.segmentations[0].segmentation_id == "other-mask"
    assert annotations.cache_info == (1, 60)
    np.testing.assert_array_equal(annotations.frame(0).segmentations[0].mask,
                                  first.segmentations[0].mask)
    too_small = store(payload, cache_bytes=59)
    assert too_small.frame(0).segmentations[0].mask.sum() == 2
    assert too_small.cache_info == (0, 0)


def test_broken_history_does_not_hide_a_valid_current_box():
    result = store({"molecular_detections": {"frame_count": 2, "detections": [
        detection(original_bbox_xyxy=[1, 2])
    ]}}).frame(0)
    assert result.detections[0].bbox_xyxy == (1, 2, 5, 4)
    assert result.detections[0].metadata["original_bbox_xyxy"] == [1, 2]
    assert result.diagnostics


def test_segmentations_never_guess_missing_or_cross_frame_links():
    anonymous = detection()
    anonymous.pop("detection_id")
    payload = {
        "molecular_detections": {"frame_count": 2, "detections": [anonymous, detection("elsewhere", 1)]},
        "molecular_segmentations": {"frame_count": 2, "segmentations": [
            segmentation("guess", prompt_detection_ids=["local-detections-0"]),
            segmentation("wrong-frame", prompt_detection_ids=["elsewhere"]),
            segmentation("standalone", prompt_detection_ids=[])]},
    }
    result = store(payload).frame(0)
    assert len(result.detections) == 1
    assert [x.segmentation_id for x in result.segmentations] == ["standalone"]
    assert result.segmentation_state == "partial"
