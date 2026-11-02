"""Create small v0.4 exports paired with genuine MPP/MolTrack inputs for review."""

import csv
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from stmdomains.tools.demo_inputs import write_mpp, write_session


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def refresh_package(paths):
    root = paths["manifest"].parent
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path != paths["manifest"]:
            data = path.read_bytes()
            files.append({"path": str(path.relative_to(root)), "size_bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()})
    write_json(paths["manifest"], {"prototype_version": "0.4",
               "package_kind": "data_results_and_source", "files": files})
    with ZipFile(paths["zip"], "w") as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, "stm_domains_prototype/" + str(path.relative_to(root)))


def create_result_demo(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    root = directory / "package"
    paths = {"source": directory / "input.mpp", "session": directory / "input.moltrack.json",
             "manifest": root / "MANIFEST_v04.json", "zip": directory / "result.zip"}
    images = np.arange(3 * 16 * 24, dtype=float).reshape(3, 16, 24)
    write_mpp(paths["source"], images[:, ::-1, ::-1])
    write_session(paths["session"], paths["source"], [0, 1, 2])
    points = [(0, "a", 4, 4), (0, "b", 8, 4), (0, "c", 14, 4),
              (0, "d", 18, 4), (0, "duplicate", 14.1, 4),
              (1, "no-analysis", 8, 8), (2, "f", 4, 8), (2, "g", 14, 8)]
    payload = json.loads(paths["session"].read_text())
    payload["molecular_detections"] = {"frame_count": 3, "detections": [
        {"frame_index": f, "detection_id": name, "bbox_xyxy": [x-1, y-1, x+1, y+1],
         "source_view": "raw"} for f, name, x, y in points
    ]}
    write_json(paths["session"], payload)
    selected = [p for p in points if p[0] != 1]
    mapping = {0: 0, 2: 1}
    rows = []
    for frame, name, x, y in selected:
        domain = 1 if name in ("a", "b") else 2 if name == "c" else 0
        duplicate = name == "duplicate"
        reason = "" if domain else ("suppressed_duplicate" if duplicate else
                 "insufficient_local_support" if name == "f" else
                 "periodicity_not_confirmed" if name == "g" else "class_ambiguous")
        rows.append({"frame_number": frame+1, "frame_index": frame,
                     "local_frame_index": mapping[frame], "detection_id": name,
                     "x_px": x, "y_px": y, "provisional_class_id": "" if duplicate else "q" if domain else "w",
                     "class_id": "q" if domain else "", "domain_local_id": domain,
                     "order_score": "" if duplicate else .9, "order_threshold": "" if duplicate else .5,
                     "order_supported": bool(domain or name == "d"), "order_support_sufficient": not duplicate and name != "f",
                     "local_point_count": "" if duplicate else 10, "effective_point_count": "" if duplicate else 8,
                     "class_confidence": "" if duplicate else .8, "class_reliable": bool(domain or name in ("f", "g")),
                     "unassigned_reason": reason,
                     "status": "domain" if domain else "suppressed_duplicate" if duplicate else "uncertain_or_small"})
    frames = [
        {"frame_number": 1, "frame_index": 0, "local_frame_index": 0, "detections_original": 5,
         "molecules_used": 4, "assigned_to_domains": 3, "uncertain_or_small": 1,
         "total_domains": 2, "class_counts": {"q": 2, "w": 0},
         "class_gate_accepted": 3, "order_supported": 4, "assigned_fraction": .75},
        {"frame_number": 3, "frame_index": 2, "local_frame_index": 1, "detections_original": 2,
         "molecules_used": 2, "assigned_to_domains": 0, "uncertain_or_small": 2,
         "total_domains": 0, "class_counts": {"q": 0, "w": 0},
         "class_gate_accepted": 0, "order_supported": 0, "assigned_fraction": 0.},
    ]
    domains = [
        {"frame_number": 1, "frame_index": 0, "local_frame_index": 0, "domain_local_id": 1,
         "class_index": 0, "class_id": "q", "display_id": "q1", "n_molecules": 2},
        {"frame_number": 1, "frame_index": 0, "local_frame_index": 0, "domain_local_id": 2,
         "class_index": 0, "class_id": "q", "display_id": "q2", "n_molecules": 1},
    ]
    summary = {"prototype_version": "0.4-discovery", "source_frame_numbers": [1, 3],
               "classes": [{"id": "q", "color": "#10b9bd"}, {"id": "w", "color": "#f5b343"}],
               "selected_k": 2, "class_model_directory": "work/discovery/order_filtered",
               "parameters": {"min_molecules_per_domain": 1}, "frame_summary": frames,
               "domains": domains, "n_original_detections": 7, "n_unique_used": 6,
               "n_assigned": 3, "assigned_fraction": .5}
    write_json(root / "results_discovery/analysis_summary.json", summary)
    write_csv(root / "results_discovery/detections_with_domains.csv", rows)
    write_csv(root / "results_discovery/domains.csv", domains)
    write_csv(root / "results_discovery/frame_summary.csv", [dict(f, class_counts=json.dumps(f["class_counts"])) for f in frames])
    write_json(root / "analysis_config.json", {"schema": "stm-domain-prototype-run-v1",
               "prototype_version": "0.4", "selected_classes": 2})
    sources = {key: {"path": str(paths[path]), "size_bytes": paths[path].stat().st_size,
                    "sha256": hashlib.sha256(paths[path].read_bytes()).hexdigest()}
               for key, path in (("mpp", "source"), ("session", "session"))}
    write_json(root / "work/expanded/metadata.json", {
        "schema": "stm-domain-prototype-selected-input-v1", "sources": sources,
        "source_movie_frame_count": 3, "source_frame_indices": [0, 2], "source_frame_numbers": [1, 3],
        "n_frames": 2, "n_detections": 7,
        "frame_details": [{"local_frame_index": f, "source_frame_index": source,
                           "frame_number": source+1, "detection_count": count}
                          for f, source, count in ((0, 0, 5), (1, 2, 2))],
    })
    np.savez_compressed(root / "work/expanded/input_selected.npz", images=images[[0, 2]],
                        source_frame_indices=np.array([0, 2], dtype=np.int32))
    refresh_package(paths)
    (directory / "README.txt").write_text(
        "Syntetyczny przykład interfejsu, bez obliczania ani oceny detektora.\n"
        "1. Uruchom: python -m stmdomains.main (środowisko netcat).\n"
        "2. Otwórz input.moltrack.json, następnie dołącz result.zip jako wynik v0.4.\n"
        "3. Klatka 1: 5 oznaczeń, 4 aktywne, 3 przypisane, 2 domeny.\n"
        "   a/b należą do domeny 1; c do domeny 2. Wszystkie mają końcową klasę q.\n"
        "   Widok Domeny rozróżnia te domeny; Klasy pokazują wspólny kolor q.\n"
        "   d: szary, niejednoznaczna klasa (wstępna w). duplicate: pominięty duplikat.\n"
        "4. Klatka 2: jedno oznaczenie, brak analizy; nie jest wynikiem z zerem domen.\n"
        "5. Klatka 3: analiza wykonana, 2 nieprzypisane molekuły, 0 domen.\n"
        "   f: niewystarczające otoczenie; g: niepotwierdzona okresowość.\n"
        "6. Kliknij oznaczenie; w opisie pod obrazem lub danych oznaczenia sprawdź ID,\n"
        "   domenę, klasę końcową/wstępną i przyczynę.\n"
        "7. Zamiast ZIP można otworzyć package/MANIFEST_v04.json.\n",
        encoding="utf-8",
    )
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?",
                        default=Path(".scratch/stmdomains-ui-04/demo"))
    for name, path in create_result_demo(parser.parse_args().directory).items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
