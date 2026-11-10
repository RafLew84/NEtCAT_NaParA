"""E0: audit existing evidence and build a local reference viewer; no inference.

Run with netcat: python -m stmdomains.experiments.e0_audit --out NEW_DIRECTORY.
Inputs are the previously audited local pilot; original files are never changed.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import io
import json
from pathlib import Path
import platform

import numpy as np
from PIL import Image

from .bundle import arrays_hash, file_hash, load_sample, write_json
from .references import extract, render_expected
from .training.data import support_available, transfer_membership

ROOT = Path(__file__).resolve().parents[2]
COLORS = ["#52baf5", "#ee7b93", "#f3d35c", "#ae8ce8", "#6ed6a0"]
NAMES = {1: "BLACK", 2: "RED", 3: "YELLOW"}
ACQUISITION = "ttmapp-8fbbfa5d515a"


def read(path):
    return json.loads(Path(path).read_text())


def png_url(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()


def visual(arrays, instances, labels, *, uncertain=False):
    image = arrays["image"]
    lo, hi = np.percentile(image[arrays["measured"]], [2, 98])
    gray = (255 * np.clip((image - lo) / max(hi - lo, 1e-12), 0, 1)).astype("uint8")
    rgba = np.zeros((*image.shape, 4), dtype="uint8")
    colors = {label: COLORS[(ident - 1) % len(COLORS)] for ident, label in labels.items()}
    for label in colors:
        for historical, color in (("BLACK", "#52baf5"), ("RED", "#ee7b93"), ("YELLOW", "#f3d35c")):
            if label.endswith(historical):
                colors[label] = color
    for ident, label in labels.items():
        color = colors[label]
        rgba[instances == ident] = [int(color[i:i + 2], 16) for i in (1, 3, 5)] + [70]
    ij = np.floor(arrays["centers_xy"]).astype(int)
    point_labels = [labels.get(int(instances[y, x])) if not uncertain else None for x, y in ij]
    return dict(image=png_url(gray), overlay=None if uncertain else png_url(rgba),
                width=image.shape[1], height=image.shape[0],
                xy=arrays["centers_xy"].tolist(), point_labels=point_labels, colors=colors,
                display_percentiles=[2, 98], display_limits=[float(lo), float(hi)])


def crop_arrays(arrays, box):
    x0, y0, x1, y1 = box
    keep = np.all((arrays["centers_xy"] >= [x0, y0]) &
                  (arrays["centers_xy"] < [x1, y1]), axis=1)
    return dict(image=arrays["image"][y0:y1, x0:x1],
                measured=arrays["measured"][y0:y1, x0:x1],
                centers_xy=arrays["centers_xy"][keep] - [x0, y0],
                boxes_xyxy=arrays["boxes_xyxy"][keep] - [x0, y0, x0, y0],
                object_ids=arrays["object_ids"][keep])


def synthetic_examples(root):
    base = root / ".scratch/training-20/controls"
    manifest = read(base / "evaluation/manifest.json")
    specifications = [
        ("single", "Jedna sieć", "Jedna domena według generatora."),
        ("two_orientations", "Dwie orientacje", "Dwie domeny tego samego typu; kąty 0° i 27°."),
        ("phase_boundary", "Granica przesunięcia", "Dwie domeny: prawa połowa przesunięta o 4 px, bez zmiany kąta."),
        ("crop", "Przesunięcie początku wycinka", "Nadal jedna domena; krawędź kadru nie jest granicą wewnętrzną."),
        ("empty_gap", "Rzeczywista przerwa", "Dwie domeny, brak sygnału molekuł w pasie x=78–114."),
        ("missing_band", "Brak samych oznaczeń", "Jedna domena. Te same oznaczone centra co przy przerwie, ale obraz zawiera sieć."),
        ("independent_rows", "Niezależne rzędy", "Zachowany negatyw wspólnej sieci 2D; losowa faza każdego rzędu."),
        ("insufficient_field", "Zbyt małe pole", "Generator zna jedną sieć, lecz pole 20×20 nie wystarcza do oceny. Brak danych ≠ nieporządek."),
    ]
    samples, inventory, cached = [], [], {}
    for case, title, note in specifications:
        record = next(r for r in manifest["controls"] if r["case"] == case and r["seed"] == 920001)
        source, arrays = load_sample(base / "analysis", record["sample_id"])
        truth_path = base / "evaluation" / record["file"]
        assert file_hash(truth_path) == record["sha256"]
        with np.load(truth_path, allow_pickle=False) as z:
            truth = {k: z[k] for k in z.files}
        assert arrays_hash(truth) == record["content_sha256"]
        cached[case] = (arrays, truth, source)
        uncertain = case == "insufficient_field"
        labels = {int(i): f"D{i}" for i in np.unique(truth["domain_labels"]) if i > 0}
        # Excluded boundary bands have no displayed claim; points there stay gray.
        display_ids = np.where(truth["evaluation_valid"], truth["domain_labels"], 0)
        samples.append(dict(id=case, title=title, kind="synthetic", note=note +
                            " Kolory: prawda generatora poza pasem niepewności, nie wynik modelu.",
                            rois=[], source=str(base.relative_to(root)),
                            **visual(arrays, display_ids, labels, uncertain=uncertain)))
        inventory.append(dict(case=case, source_sample_id=record["sample_id"], seed=920001,
                              analysis_file=str((base / "analysis" / source["file"]).relative_to(root)),
                              analysis_sha256=source["sha256"], truth_sha256=record["sha256"],
                              truth_file=str(truth_path.relative_to(root)),
                              expected_domain_count=record["expected_domain_count"],
                              expected_state=record.get("expected_state", "known_generator_domains"),
                              role="development_illustration", prediction_computed=False))
    for case, parent, box, title, note in [
        ("narrow_known", "single", [6, 78, 186, 102], "Dwa rzędy — znane pochodzenie",
         "Wycięty fragment jednej znanej sieci. Wysokość 24 px nie zapewnia okna 32 px; nie jest to fizyczny płat na podłożu."),
        ("two_rows_uncertain", "independent_rows", [6, 72, 186, 96], "Dwa rzędy — nierozstrzygnięte",
         "Nierozstrzygnięte: lokalny wycinek nie rozstrzyga powtarzalności 2D. Nie dziedziczy automatycznie oceny całego pola; brak lokalnej etykiety domeny."),
    ]:
        arrays, _, source = cached[parent]
        cropped = crop_arrays(arrays, box)
        samples.append(dict(id=case, title=title, kind="synthetic", note=note,
                            rois=[], source=f"Diagnostyczny crop {parent}; raw bbox {box}",
                            **visual(cropped, np.zeros(cropped["image"].shape, int), {}, uncertain=True)))
        inventory.append(dict(case=case, parent=parent, bbox_parent_raw_xyxy=box,
                              expected_domain_count=None, latent_domain_count=1 if parent == "single" else None,
                              expected_state="insufficient_local_evidence", role="development_illustration",
                              source_analysis_sha256=source["sha256"], prediction_computed=False))
    return samples, inventory


def candidate_rois(record, arrays):
    number = record["frame_number"]
    origin = np.asarray(record["origin_in_expanded_xy"])
    candidates = []
    if number in (1, 50, 100, 150, 200):
        fit = number in (1, 50, 100)
        band = [328., 480.] if fit else [168., 312.]
        box = [max(0., band[0] - origin[0]), 0., min(256., band[1] - origin[0]), 256.]
        candidates.append(("fit-east" if fit else "validation-middle", box,
                           "Przejrzeć wnętrza i styki; potwierdzić oba rodzaje relacji.",
                           "development_fit_candidate" if fit else "development_validation_candidate"))
    diagnostic = {
        251: [("narrow", [215, 77, 255, 137], "Wąska czerwona referencja: wystarczalność danych i niepewność brzegu.")],
        258: [("multiple", [120, 0, 256, 145], "Sprawdzić styki kilku przybliżonych regionów i pasy niepewności.")],
        259: [("boundary", [140, 0, 256, 145], "Zweryfikować sąsiedztwa po obu stronach przybliżonych granic."),
              ("unknown", [30, 135, 225, 245], "Nieoznaczony obszar: wnętrza, defekty i możliwe przerwy; bez etykiety negatywnej.")],
        268: [("unknown", [25, 130, 245, 250], "Nieoznaczony dół obrazu; ustalić lokalne domeny i niepewne obszary.")],
    }
    candidates.extend((key, box, purpose, "development_diagnostic")
                      for key, box, purpose in diagnostic.get(number, []))
    result = []
    for key, box, purpose, role in candidates:
        counts = Counter()
        for xy in arrays["centers_xy"]:
            support = np.r_[xy - 35, xy + 35]
            if not (np.all(support[:2] >= box[:2]) and np.all(support[2:] <= box[2:])):
                continue
            if support_available(support, arrays["measured"]):
                legacy, _ = transfer_membership(record, support)
                counts[legacy or "excluded"] += 1
        result.append(dict(id=f"e0-{record['sample_id']}-{key}", sample_id=record["sample_id"],
                           frame_number=number, frame_index=record["frame_index"],
                           source_frame_index=record["source_frame_index"],
                           bbox_raw_xyxy=box, bbox_expanded_xyxy=(np.array(box) + np.tile(origin, 2)).tolist(),
                           coordinate_system="raw_edge_xy", purpose=purpose, role=role,
                           status="pending_user_review", certainty="unreviewed", supervised_role=None,
                           acquisition_group_id=ACQUISITION,
                           dependence_group_id=ACQUISITION + "/" + (key if number < 250 else "late-review"),
                           independent_test_eligible=False, seen_by_transductive_encoders=True,
                           full_support_70px_center_counts=dict(counts),
                           registration_independence_validated=False))
    return result


def real_examples(root):
    base = root / ".scratch/training-20/data/analysis"
    ref_base = root / ".scratch/partial-domain-reference"
    review = root / "data/ttmapp_frames_250_268_domain_review"
    reference = read(ref_base / "manifest.json")
    ref_records = {r["frame_number"]: r for r in reference["frames"]}
    samples, inventory, regions_all, rois_all = [], [], [], []
    checked = 0
    for record in read(base / "manifest.json")["samples"]:
        _, arrays = load_sample(base, record["sample_id"])
        number = record["frame_number"]
        instances = np.zeros(arrays["image"].shape, int)
        labels, regions = {}, []
        item = dict(sample_id=record["sample_id"], frame_number=number,
                    frame_index=record["frame_index"], source_frame_index=record["source_frame_index"],
                    analysis_file=str((base / record["file"]).relative_to(root)),
                    analysis_sha256=record["sha256"], object_count=len(arrays["object_ids"]),
                    origin_in_expanded_xy=record["origin_in_expanded_xy"],
                    registration_status=record["registration_status"],
                    registration_quality=record["registration_quality"],
                    physical_scale_trusted=record["calibration_trusted"],
                    acquisition_group_id=ACQUISITION, role="development_diagnostic",
                    independent_test_eligible=False, seen_by_transductive_encoders=True,
                    precise_boundary_reference=False)
        if number in ref_records:
            ref = ref_records[number]
            clean_path, manual_path = (review / ref[k] for k in ("clean_file", "manual_file"))
            assert file_hash(clean_path) == ref["clean_sha256"]
            assert file_hash(manual_path) == ref["manual_sha256"]
            clean = np.asarray(Image.open(clean_path).convert("RGB"))
            manual = np.asarray(Image.open(manual_path).convert("RGB"))
            expected = render_expected(arrays["image"], np.asarray(ref["origin_xy"]), (408, 480))
            assert np.array_equal(clean, np.repeat(expected[:, :, None], 3, axis=2)), number
            assert np.allclose(ref["origin_xy"], record["origin_in_expanded_xy"], atol=1e-9)
            extracted, _ = extract(clean, manual, 3.)
            yy, xx = np.indices(arrays["image"].shape)
            px = np.floor(2 * (xx + .5 + ref["origin_xy"][0])).astype(int)
            py = np.floor(2 * (yy + .5 + ref["origin_xy"][1])).astype(int)
            for i, region in enumerate(extracted, 1):
                instances[region["core"][py, px]] = i
                labels[i] = f"R{i} {NAMES[region['class_id']]}"
            mask_path = ref_base / f"frame_{number}_partial_reference.npz"
            with np.load(mask_path, allow_pickle=False) as z:
                assert np.array_equal(instances, z["raw_core_instances"]), number
            checked += 1
            for source_region in ref["region_candidates"]:
                i = source_region["instance"]
                ij = np.floor(arrays["centers_xy"]).astype(int)
                regions.append(dict(id=f"{record['sample_id']}-R{i}", sample_id=record["sample_id"],
                                    frame_number=number, frame_index=record["frame_index"],
                                    bbox_raw_xyxy=source_region["raw_core_bbox_xyxy"],
                                    reference_color=source_region["class_name"],
                                    core_pixels=int((instances == i).sum()),
                                    associated_center_count=int((instances[ij[:, 1], ij[:, 0]] == i).sum()),
                                    status="accepted_partial_reference_2026-10-21",
                                    certainty="conservative_derived_core_not_precise_boundary",
                                    approval_source="docs/stmdomains/partial-domain-reference-audit.md",
                                    center_membership="computed_by_core_containment_not_manually_validated",
                                    role="development_diagnostic", supervised_role=None,
                                    acquisition_group_id=ACQUISITION, dependence_group_id=ACQUISITION + "/late-review"))
            item.update(reference_mask_file=str(mask_path.relative_to(root)), reference_mask_sha256=file_hash(mask_path),
                        clean_file=str(clean_path.relative_to(root)), manual_file=str(manual_path.relative_to(root)),
                        clean_sha256=ref["clean_sha256"], manual_sha256=ref["manual_sha256"],
                        png_reconstruction_max_error=0, reextracted_cores_identical=True)
        rois = candidate_rois(record, arrays)
        rois_all.extend(rois)
        regions_all.extend(regions)
        item["reference_region_count"] = len(regions)
        inventory.append(item)
        note = ("Kolory R1/R2… oznaczają konserwatywne wnętrza przybliżonych ręcznych regionów. "
                "Historyczny BLACK pokazano na niebiesko dla czytelności; RED i YELLOW zachowują swoje kolory. "
                "Przypisanie centrum wynika z położenia w masce, nie jest osobną ręczną etykietą molekuły. "
                "Szare punkty pozostają nieoznaczone; nie są negatywami. " if labels else
                "Brak zatwierdzonej referencji domen tej klatki. Szare punkty są centrami z MolTrack, nie predykcją domen. ")
        note += "Pomarańczowe prostokąty: obszary do przeglądu, bez nowych etykiet. Całość to jedna akwizycja rozwojowa."
        samples.append(dict(id=record["sample_id"], title=f"TTMAPP · klatka {number}", kind="measurement",
                            note=note, rois=rois, source=item["analysis_file"],
                            **visual(arrays, instances, labels)))
    assert checked == 18 and len(regions_all) == 54
    return samples, inventory, regions_all, rois_all


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("Use a fresh output directory")
    root = ROOT
    ref_path = root / ".scratch/partial-domain-reference/manifest.json"
    ref = read(ref_path)
    source_paths = [root / "data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP",
                    root / "data/TTMAPP/detection_full.moltrack.json", ref_path,
                    root / ".scratch/training-20/data/split.json",
                    root / ".scratch/training-20/data/analysis/manifest.json"]
    hashes = {str(p.relative_to(root)): file_hash(p) for p in source_paths}
    assert hashes[str(source_paths[0].relative_to(root))] == ref["source_mpp_sha256"]
    assert hashes[str(source_paths[1].relative_to(root))] == ref["session_sha256"]
    samples, frames, regions, rois = real_examples(root)
    controls, cases = synthetic_examples(root)
    assert hashes == {str(p.relative_to(root)): file_hash(p) for p in source_paths}
    out.mkdir(parents=True)
    manifest = dict(schema="stmdomains-e0-reference-audit-v1", base_commit="308b455",
                    acquisition_group_id=ACQUISITION, independent_acquisition_count=1,
                    independent_test=[], supervised_split_ready=False,
                    supervised_split_blockers=["candidate ROI relations not reviewed",
                        "both relation classes not confirmed per role", "registration uncertainty not calibrated"],
                    source_hashes=hashes, frame_count=len(frames), partial_reference_frames=18,
                    partial_reference_regions=len(regions), missing_manual_frame_numbers=[255],
                    all_pilot_frames_seen_by_transductive_encoders=True,
                    support_policy=dict(scales_raw_px=[32, 48, 64], shift_px=2, interpolation_px=1,
                                        max_full_support_px=70, registration_guard_px=8,
                                        registration_guard_calibrated=False),
                    historical_split=read(source_paths[3]), frames=frames, regions=regions,
                    candidate_rois=rois, cases=cases, predictions_computed=False,
                    new_human_labels_created=False,
                    checks=dict(verified_analysis_npz=24, reconstructed_clean_png=18,
                                reextracted_identical_reference_masks=18, verified_synthetic_truth=8,
                                source_hashes_unchanged=True),
                    environment=dict(python=platform.python_version(), numpy=np.__version__),
                    code_sha256={str(p.relative_to(root)): file_hash(p) for p in
                                 [Path(__file__), Path(__file__).with_name("e0_gallery.py"),
                                  Path(__file__).with_name("references.py"),
                                  Path(__file__).with_name("bundle.py"),
                                  Path(__file__).parent / "training/data.py"]})
    census_path = root / ".scratch/ml-e0-project-census.json"
    if census_path.exists():
        census = read(census_path)
        manifest["separate_project_census"] = dict(file=str(census_path.relative_to(root)),
            sha256=file_hash(census_path), project_count=census["project_count"], scope=census["scope"],
            method=census["method"], limitations=census["limitations"])
    write_json(out / "reference-manifest.json", manifest)
    write_json(out / "gallery-data.json", samples + controls)
    from .e0_gallery import write_gallery
    write_gallery(out / "index.html", samples + controls)
    print(json.dumps(dict(output=str(out), frames=len(frames), regions=len(regions),
                          candidate_rois=len(rois), illustrations=len(cases), checks=manifest["checks"]), indent=2))


if __name__ == "__main__":
    main()
