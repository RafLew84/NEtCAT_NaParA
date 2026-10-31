"""Standalone issue21a viewer using the saved issue21 comparison renderer."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re

from ...bundle import file_hash, write_json
from .. import gallery as original
from ..predict import read_json
from .diagnostics import FAMILY_LABELS, reporting_stage


def document_template():
    html = original._HTML.replace("STM Domains — próba AE / rVAE", "STM Domains — próba21a rVAE")
    html = html.replace("STM Domains · eksperyment 21", "STM Domains · eksperyment 21a")
    html = html.replace("Czy AE i rVAE uczą się cech, które pomagają znaleźć domeny lepiej niż klasyczna tekstura?",
                        "Czy kodowanie współrzędnych Fouriera i słabsza regularyzacja pomagają rVAE odtworzyć strukturę oraz rozdzielać domeny?")
    html = html.replace('<option value="transductive">Transdukcja · cała obecna seria</option>', "")
    labels = json.dumps(FAMILY_LABELS, ensure_ascii=False)
    replacement = "function runLabel(run){const labels=" + labels + ";if(run.family==='fft')return labels.fft;return `${labels[run.family]||run.family} · z${run.latent} · ziarno ${run.seed}`;}"
    html, count = re.subn(r"function runLabel\(run\)\{[^\n]+", lambda _: replacement, html)
    if count != 1:
        raise ValueError("The source gallery run-label interface changed")
    html = html.replace("const f={fft:0,ae:1,rvae:2};", "const f={fft:0,ae:1,rvae:2,rvae_lowkl:3,rvae_fourier:4,rvae_fourier_lowkl:5};")
    html = html.replace("<footer>", "<footer><p>21a: cztery warianty rVAE oraz zachowane AE i FFT. TTMAPP jest już oglądaną oceną rozwojową. Wynik przed odmowami opisuje reprezentację i podział; nie jest przyjętym detektorem.</p>")
    return html


def scenario_samples(output: Path, control_manifest: Path):
    manifest = read_json(control_manifest)
    first_seed = min(record["seed"] for record in manifest["controls"])
    samples = {"ttmapp": "ttmapp-250"}
    for scenario, case in (("single", "single"), ("boundary", "two_orientations")):
        matching = [record["sample_id"] for record in manifest["controls"] if record["case"] == case and record["seed"] == first_seed]
        if len(matching) != 1:
            raise ValueError("Expected one fixed first-seed control for " + case)
        samples[scenario] = matching[0]
    write_json(output / "gallery/scenario-map.json", samples)
    write_json(output / "gallery/scenario-source.json", dict(
        manifest_sha256=file_hash(control_manifest), control_seed=first_seed,
        rule="First reserved control seed, cases single/two_orientations; fixed real frame250; no quality selection"))
    return samples


def build(output: Path, control_manifest: Path):
    from .evaluate import verify_freeze
    with reporting_stage(output, "gallery") as budget:
        verify_freeze(output, check_budget=budget.check)
        scenarios = scenario_samples(output, control_manifest)
        original_html, original_read = original._HTML, original._read_json
        def read_checked(path):
            budget.check()
            return original_read(path)
        try:
            original._HTML = document_template()
            original._read_json = read_checked
            result = original.build_gallery(output, scenario_samples=scenarios)
        finally:
            original._HTML, original._read_json = original_html, original_read
        target = output / "index.html"
        document = target.read_text()
        payload = json.loads(document.split('<script id="data" type="application/json">', 1)[1].split("</script>", 1)[0])
        predictions = {(row["run_id"], row["partition"], row["sample_id"]): row for row in payload["predictions"]}
        previews = {}
        for name, sample in scenarios.items():
            for family in ("fft", "ae", "rvae", "rvae_lowkl", "rvae_fourier", "rvae_fourier_lowkl"):
                budget.check()
                run = "transfer/fft" if family == "fft" else f"transfer/{family}/z32/seed-20261101"
                prediction = predictions.get((run, "fh4", sample))
                if prediction is None:
                    continue
                path = output / "gallery/previews" / f"{name}-{family}.png"
                original._preview_png(payload["samples"][sample], prediction, path, label=f"{name} · {FAMILY_LABELS[family]}")
                previews[str(path.relative_to(output))] = file_hash(path)
        # Optional scientific figures remain embedded, so the resulting HTML
        # continues to work as a single movable file without a server.
        figures = []
        for filename, title in (("reconstruction-examples.png", "Ustalony wycinek TTMAPP250"),
                                ("diagnostic-reconstruction.png", "Próba odtwarzania16 wycinków treningowych"),
                                ("validation-curves.png", "Walidacja rekonstrukcji i regularyzacji")):
            path = output / "figures" / filename
            if path.exists():
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                figures.append(f'<details style="margin:16px 0"><summary>{title}</summary><img alt="{title}" style="width:100%;height:auto" src="data:image/png;base64,{encoded}"></details>')
        if figures:
            document = document.replace("</main>", '<section><h2>Rekonstrukcje i trening</h2><p>Ustalone przykłady; nie służą do wyboru modelu po ocenie domen.</p>' + "".join(figures) + "</section></main>")
            target.write_text(document)
        result.update(schema="stmdomains-issue21a-gallery-v1", html_bytes=target.stat().st_size,
                      html_sha256=file_hash(target), source_sha256=file_hash(Path(__file__)),
                      renderer_sha256=file_hash(Path(original.__file__)), previews=previews,
                      embedded_scientific_figures=len(figures), transductive_models=False)
        write_json(output / "gallery/manifest.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--control-manifest", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output, args.control_manifest)
    print(json.dumps({key: result[key] for key in ("html", "html_bytes", "samples", "runs", "predictions")}))


if __name__ == "__main__":
    main()
