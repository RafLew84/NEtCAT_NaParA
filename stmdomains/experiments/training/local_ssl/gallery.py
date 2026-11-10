"""Single-file Polish comparison viewer for the issue22 research prototype."""
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


SCENARIO_CASES = {
    "single": "single", "boundary": "two_orientations", "phase": "phase_boundary",
    "missing": "missing_band", "artifact": "stripes",
}


def document_template():
    html = original._HTML.replace("STM Domains — próba AE / rVAE", "STM Domains — lokalne SSL")
    html = html.replace("STM Domains · eksperyment 21", "STM Domains · eksperyment 22 · prototyp")
    html = html.replace("Czy AE i rVAE uczą się cech, które pomagają znaleźć domeny lepiej niż klasyczna tekstura?",
                        "Czy lokalna zgodność wycinków daje lepsze domeny niż FFT i ten sam encoder bez treningu?")
    labels = json.dumps(FAMILY_LABELS, ensure_ascii=False)
    replacement = "function runLabel(run){const labels=" + labels + ";if(run.family==='fft')return labels.fft;return `${labels[run.family]||run.family} · z${run.latent} · ziarno ${run.seed}`;}"
    html, count = re.subn(r"function runLabel\(run\)\{[^\n]+", lambda _: replacement, html)
    if count != 1:
        raise ValueError("The source gallery run-label interface changed")
    html = html.replace("const f={fft:0,ae:1,rvae:2};", "const f={fft:0,local_ssl_untrained:1,local_ssl:2};")
    html = html.replace('<button id="scenario-ttmapp">TTMAPP</button>',
                        '<button id="scenario-phase">Granica przesunięcia</button><button id="scenario-missing">Brak centrów</button>'
                        '<button id="scenario-artifact">Paski</button><button id="scenario-ttmapp">TTMAPP</button>')
    html = html.replace("['single','boundary','ttmapp']", "['single','boundary','phase','missing','artifact','ttmapp']")
    html = html.replace("<footer>", "<footer><p>22: macierz FFT / lokalne SSL × FH / MWS oraz encoder bez treningu. "
                        "TTMAPP i kontrole są znaną oceną rozwojową. Jasność, kanał cech i kolor składowej nie oznaczają typu struktury lub kąta.</p>")
    html = html.replace("Kontrola syntetyczna: zamrożony model i reguły z części uczącej.",
                        "Znana kontrola syntetyczna: zamrożony model i reguły z części uczącej.")
    return html


def scenario_samples(output: Path, control_manifest: Path):
    manifest = read_json(control_manifest)
    first_seed = min(record["seed"] for record in manifest["controls"])
    samples = {"ttmapp": "ttmapp-250"}
    for scenario, case in SCENARIO_CASES.items():
        matches = [record["sample_id"] for record in manifest["controls"] if record["case"] == case and record["seed"] == first_seed]
        if len(matches) != 1:
            raise ValueError("Expected one fixed first-seed control for " + case)
        samples[scenario] = matches[0]
    write_json(output / "gallery/scenario-map.json", samples)
    write_json(output / "gallery/scenario-source.json", dict(
        manifest_sha256=file_hash(control_manifest), control_seed=first_seed, cases=SCENARIO_CASES,
        rule="First original control seed, fixed cases and real frame250; no quality selection"))
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
            result = original.build_gallery(output, scenario_samples={key: value for key, value in scenarios.items()
                                                                      if key in {"single", "boundary", "ttmapp"}})
        finally:
            original._HTML, original._read_json = original_html, original_read
        target = output / "index.html"
        document = target.read_text()
        prefix, tail = document.split('<script id="data" type="application/json">', 1)
        encoded, suffix = tail.split("</script>", 1)
        payload = json.loads(encoded)
        payload["schema"] = "stmdomains-issue22-gallery-v1"
        payload["scenarios"] = scenarios
        if any(sample not in payload["samples"] for sample in scenarios.values()):
            raise ValueError("Scenario not present in frozen predictions")
        document = prefix + '<script id="data" type="application/json">' + json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>" + suffix
        predictions = {(row["run_id"], row["partition"], row["sample_id"]): row for row in payload["predictions"]}
        previews = {}
        for name in ("ttmapp", "boundary", "phase"):
            sample = scenarios[name]
            for family in ("fft", "local_ssl_untrained", "local_ssl"):
                budget.check()
                run = "transfer/fft" if family == "fft" else f"transfer/{family}/z32/seed-20261101"
                prediction = predictions.get((run, "fh4", sample))
                if prediction is None:
                    continue
                path = output / "gallery/previews" / f"{name}-{family}.png"
                original._preview_png(payload["samples"][sample], prediction, path, label=f"{name} · {FAMILY_LABELS[family]}")
                previews[str(path.relative_to(output))] = file_hash(path)
        figures = []
        for filename, title in (("local-correspondence.png", "Dwa widoki i odpowiadające pozycje"),
                                ("validation-curves.png", "Składniki funkcji celu podczas treningu"),
                                ("representation-diagnostics.png", "Zróżnicowanie cech i jasność")):
            path = output / "figures" / filename
            if path.exists():
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                figures.append(f'<details style="margin:16px 0"><summary>{title}</summary><img alt="{title}" style="width:100%;height:auto" src="data:image/png;base64,{encoded}"></details>')
        if figures:
            document = document.replace("</main>", '<section><h2>Lokalne cechy i trening</h2><p>Stałe przykłady i diagnostyka; nie służą do wyboru modelu po ocenie domen.</p>' + "".join(figures) + "</section></main>")
        target.write_text(document)
        result.update(schema="stmdomains-issue22-gallery-v1", html_bytes=target.stat().st_size,
                      html_sha256=file_hash(target), source_sha256=file_hash(Path(__file__)),
                      renderer_sha256=file_hash(Path(original.__file__)), previews=previews,
                      embedded_scientific_figures=len(figures), transductive_models=True,
                      known_development_controls=True, scenarios=scenarios)
        write_json(output / "gallery/manifest.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--control-manifest", type=Path, default=Path(".scratch/training-20/controls/evaluation/manifest.json"))
    args = parser.parse_args()
    result = build(args.output, args.control_manifest)
    print(json.dumps({key: result[key] for key in ("html", "html_bytes", "samples", "runs", "predictions")}))


if __name__ == "__main__":
    main()
