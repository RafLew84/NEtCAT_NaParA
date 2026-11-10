"""Render a fixed illustrative subset of prepared E2 summaries, without fitting.

The full numerical record remains in edge-summary.jsonl.gz. Plots use actual
features, common support, seed20261101 for trained models and all three baselines.
No plot selection depends on an observed score. Matplotlib writes standalone
PNG/SVG files; a small local HTML chooser needs no server or network.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

_CONFIG = tempfile.TemporaryDirectory(prefix="e2-matplotlib-")
os.environ.setdefault("MPLCONFIGDIR", _CONFIG.name)
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SEED = 20261101
CASES = ("measurement", "two_orientations", "phase_boundary", "orientation_8deg",
         "different_spacing", "empty_gap", "independent_rows")
REGIMES = ("transfer", "transductive")
SAMPLERS = ("centers", "grid")
SPACES = ("native", "l2", "adapted")
FAMILIES = ("ae", "rvae_full", "rvae_content", "rvae_angle", "fft", "photometry", "geometry")
TITLES = {"ae": "AE", "rvae_full": "rVAE treść+kąt", "rvae_content": "rVAE treść",
          "rvae_angle": "rVAE kąt", "fft": "FFT", "photometry": "Jasność/kontrast",
          "geometry": "Geometria ACF", "transfer": "transfer historyczny",
          "transductive": "transdukcja", "centers": "centra molekuł", "grid": "siatka",
          "native": "Natywna", "l2": "Po L2, przed PCA", "adapted": "Po adapterze",
          "measurement": "STM — znane wnętrza", "two_orientations": "Dwie orientacje",
          "phase_boundary": "Granica przesunięcia", "orientation_8deg": "Orientacje Δ8°",
          "different_spacing": "Różne rozstawy", "empty_gap": "Pusta przerwa",
          "independent_rows": "Niezależne rzędy"}
REASONS = {"no_eligible_pairs": "brak ocenialnych par", "no_finite_distances": "brak skończonych odległości",
           "no_different_pairs": "brak par różnych domen", "no_same_pairs": "brak par tej samej domeny",
           "missing_reference": "brak referencji", "no_positive_reference_pairs": "brak par dodatnich domen"}
COLORS = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#666666")
STYLES = ("-", "--", "-.", ":", "-", "--", "-.")


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def selected_records(path):
    """Keep only the predeclared588 records, streaming past all other results."""
    result, total = {}, 0
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            total += 1
            family = record["family"]
            if (record["condition"] != "actual" or record["support"] != "common"
                    or record["case"] not in CASES or family not in FAMILIES
                    or (family in FAMILIES[:4] and record.get("seed") != SEED)):
                continue
            key = tuple(record[name] for name in ("regime", "sampler", "case", "space", "family"))
            if key in result:
                raise ValueError(f"Duplicate selected plot summary: {key}")
            result[key] = record
    expected = set(itertools.product(REGIMES, SAMPLERS, CASES, SPACES, FAMILIES))
    if set(result) != expected:
        raise ValueError(f"Plot matrix incomplete: missing={len(expected-set(result))}, extra={len(set(result)-expected)}")
    return result, total


def number(value, digits=3):
    return "n/d" if value is None else f"{value:.{digits}f}"


def reason(summary):
    value = summary.get("unavailable_reason")
    return REASONS.get(value, value or "krzywa nie została zapisana")


def counts(summary):
    return tuple(int(summary["counts"][name]) for name in ("same_pairs", "different_pairs"))


def figure_title(regime, sampler, case):
    return f"{TITLES[case]} · {TITLES[regime]} · {TITLES[sampler]}"


def context_note(case):
    return ("Jedna znana akwizycja rozwojowa; krawędzie/klatki nie są niezależnymi replikacjami."
            if case == "measurement" else
            "Relacje połączono w obrębie przypadku; jednostka kontroli: obraz/ziarno generatora.")


def comparison_figure(records, regime, sampler, case, space):
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 7.7))
    fig.subplots_adjust(left=.065, right=.985, bottom=.34, top=.84, wspace=.22)
    selected = [records[(regime, sampler, case, space, family)]["summary"] for family in FAMILIES]
    denominators = {counts(summary) for summary in selected}
    if len(denominators) != 1:
        raise ValueError(f"Common-support plot has different class counts: {(regime,sampler,case,space)}")
    n_same, n_different = denominators.pop()
    prevalence = n_different / (n_same + n_different) if n_same + n_different else None
    fig.suptitle(figure_title(regime, sampler, case), fontsize=15, fontweight="bold", y=.975)
    fig.text(.5, .925, f"{TITLES[space]} · common / actual · model seed {SEED}; bazy bez ziarna", ha="center", fontsize=10)
    fig.text(.5, .885, f"Pary: wewnątrz domeny {n_same}; między domenami {n_different}. Baza AP = częstość granic: {number(prevalence)}.", ha="center", fontsize=10)
    for axis, title in zip(axes, ("ROC", "Precision–recall")):
        axis.set(title=title, xlim=(0, 1), ylim=(0, 1.02))
        axis.grid(alpha=.18)
    axes[0].set(xlabel="False positive rate", ylabel="True positive rate")
    axes[1].set(xlabel="Recall", ylabel="Precision")
    plotted = 0
    for family, summary, color, style in zip(FAMILIES, selected, COLORS, STYLES):
        roc, pr = summary.get("roc"), summary.get("pr")
        if roc is None or pr is None:
            continue
        for values, xname, yname, axis in ((roc, "fpr", "tpr", axes[0]),
                                         (pr, "recall", "precision", axes[1])):
            x, y = np.asarray(values[xname]), np.asarray(values[yname])
            if x.shape != y.shape or x.ndim != 1 or not len(x) or not np.isfinite(x).all() or not np.isfinite(y).all() or (np.diff(x) < 0).any():
                raise ValueError("Invalid or unordered stored curve")
            axis.plot(x, y, color=color, linestyle=style, linewidth=1.7, label=TITLES[family])
        plotted += 1
    if plotted:
        axes[0].plot([0, 1], [0, 1], color="#999999", linestyle=":", linewidth=1)
        if prevalence is not None:
            axes[1].axhline(prevalence, color="#555555", linestyle=":", linewidth=1)
        axes[0].legend(loc="lower right", fontsize=8, framealpha=.9)
    else:
        explanations = sorted({reason(summary) for summary in selected})
        for axis in axes:
            axis.text(.5, .5, "Brak ocenialnej krzywej\n" + "\n".join(explanations),
                      transform=axis.transAxes, ha="center", va="center", fontsize=11, color="#555555")
    cell_text = [[TITLES[family], number(summary.get("roc_auc")), number(summary.get("average_precision")),
                  reason(summary) if summary.get("roc") is None else "zapisana krzywa"]
                 for family, summary in zip(FAMILIES, selected)]
    table = axes[0].table(cellText=cell_text, colLabels=["Odczyt", "ROC AUC", "AP", "Dostępność"],
                         colWidths=[.27, .16, .16, .41], cellLoc="left", bbox=[0, -.51, 2.2, .39])
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    for row, color in enumerate(COLORS, 1):
        table[(row, 0)].get_text().set_color(color)
    fig.text(.065, .018, "Dodatnia klasa: różne dodatnie domeny; większy dystans wskazuje granicę. Brak klasy ≠ wynik zerowy.\n"
             "Krzywe mogą być przerzedzone do512 punktów; AUC/AP pochodzą z pełnych progów, AP nie jest polem trapezowym pod PR.\n"
             + context_note(case), fontsize=8, va="bottom")
    return fig


def distance_figure(records, regime, sampler, case):
    fig, axes = plt.subplots(len(FAMILIES), len(SPACES), figsize=(13.5, 15.5), squeeze=False)
    fig.subplots_adjust(left=.13, right=.98, top=.90, bottom=.10, hspace=.80, wspace=.35)
    fig.suptitle(figure_title(regime, sampler, case), fontsize=15, fontweight="bold", y=.975)
    fig.text(.5, .947, "Mediana i kwartyle q25–q75 · common / actual · każda mini-oś ma własną skalę", ha="center", fontsize=11)
    fig.text(.5, .925, f"Model seed {SEED}; bazy bez ziarna. Surowych wielkości native różnych rodzin nie porównujemy jako wspólnego progu.", ha="center", fontsize=9)
    for i, family in enumerate(FAMILIES):
        for j, space in enumerate(SPACES):
            axis = axes[i, j]
            summary = records[(regime, sampler, case, space, family)]["summary"]
            ns, nd = counts(summary)
            quantiles = summary["quantiles"]
            drawn = 0
            for y, key, color, marker in ((1, "same", "#0072B2", "o"), (0, "different", "#D55E00", "s")):
                q = quantiles.get(key)
                if q is None:
                    continue
                low, median, high = (float(q[name]) for name in ("q25", "median", "q75"))
                if not np.isfinite([low, median, high]).all() or not 0 <= low <= median <= high:
                    raise ValueError("Invalid distance quartiles")
                axis.errorbar(median, y, xerr=[[median-low], [high-median]], fmt=marker,
                              color=color, capsize=4, markersize=4, linewidth=2)
                drawn += 1
            axis.set_yticks([0, 1], [f"różne (n={nd})", f"te same (n={ns})"], fontsize=7)
            axis.set_ylim(-.6, 1.6)
            axis.set_xlabel(TITLES[space] + " · dystans", fontsize=8)
            axis.tick_params(axis="x", labelsize=8)
            axis.grid(axis="x", alpha=.20)
            if drawn:
                left, right = axis.get_xlim()
                axis.set_xlim(max(0., left), right)
                axis.ticklabel_format(axis="x", style="sci", scilimits=(-3, 4), useOffset=False)
            else:
                axis.text(.5, .5, reason(summary), transform=axis.transAxes, ha="center", va="center", fontsize=8)
                axis.set_xticks([])
            if j == 0:
                axis.set_title(TITLES[family], loc="left", fontsize=10, fontweight="bold")
    fig.text(.065, .025, "Kreska = rozstęp kwartylowy odległości par; znacznik = mediana. To nie przedział ufności ani niepewność między ziarnami.\n"
             "Brak jednej klasy pozostaje jawny. Dane bez progu dobranego do referencji; brak indywidualnego przeskalowania na potrzeby wyglądu.\n"
             + context_note(case), fontsize=9, va="bottom")
    return fig


def write_chooser(root, figures):
    payload = json.dumps(dict(figures=figures, titles=TITLES), ensure_ascii=False).replace("<", "\\u003c")
    (root / "plots.html").write_text(_HTML.replace("__DATA__", payload), encoding="utf-8")


def write_plots(output):
    """Render exactly84 ROC/PR and28 quantile figures into an existing E2 artifact."""
    root = Path(output).resolve()
    source, manifest = root / "edge-summary.jsonl.gz", root / "plots-manifest.json"
    target = root / "plots"
    if manifest.exists() or target.exists() or (root / "plots.html").exists():
        raise FileExistsError("Preserve existing E2 plots; use a fresh plot artifact")
    records, scanned = selected_records(source)
    source_hash = file_hash(source)
    target.mkdir()
    figures, files = [], {}
    style = {"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
             "axes.spines.right": False, "svg.fonttype": "none", "svg.hashsalt": "stmdomains-e2",
             "savefig.facecolor": "white", "path.simplify": False}
    with plt.rc_context(style):
        for regime, sampler, case in itertools.product(REGIMES, SAMPLERS, CASES):
            for space in (*SPACES, "all"):
                kind = "distances" if space == "all" else "curves"
                stem = f"{kind}-{regime}-{sampler}-{case}-{space}"
                fig = (distance_figure(records, regime, sampler, case) if space == "all" else
                       comparison_figure(records, regime, sampler, case, space))
                try:
                    for extension in ("png", "svg"):
                        path = target / f"{stem}.{extension}"
                        fig.savefig(path, dpi=180, metadata={"Creator": "stmdomains E2 plots", "Date": None} if extension == "svg" else None)
                        files[str(path.relative_to(root))] = file_hash(path)
                finally:
                    plt.close(fig)
                figures.append(dict(id=stem, kind=kind, regime=regime, sampler=sampler,
                                    case=case, space=space, png=f"plots/{stem}.png", svg=f"plots/{stem}.svg"))
            print(f"E2 plots {len(figures)}/112", flush=True)
    if len(figures) != 112 or file_hash(source) != source_hash:
        raise ValueError("Incomplete figures or changed summary source")
    write_chooser(root, figures)
    files["plots.html"] = file_hash(root / "plots.html")
    result = dict(schema="stmdomains-e2-plots-v1", created_utc=datetime.now(timezone.utc).isoformat(),
                  source=str(source), source_sha256=source_hash, source_records=scanned,
                  selected_records=len(records), figure_count=len(figures), file_count=len(files),
                  selection=dict(cases=list(CASES), model_seed=SEED, baseline_seed=None,
                                 families=list(FAMILIES), condition="actual", support="common",
                                 regimes=list(REGIMES), samplers=list(SAMPLERS), spaces=list(SPACES)),
                  note="Fixed illustrative subset, not all seeds; no best-score selection, fitting or new evaluation. Native scales remain separate. Pair IQR is not a confidence interval.",
                  python=sys.executable, python_version=platform.python_version(),
                  matplotlib_version=matplotlib.__version__, numpy_version=np.__version__,
                  code_sha256=file_hash(Path(__file__)), files=files)
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = write_plots(args.output)
    print(json.dumps({key: result[key] for key in ("figure_count", "selected_records", "file_count")}))


_HTML = r'''<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>E2 — odległości i krzywe relacji</title><style>
body{margin:0;background:#101721;color:#eff4fa;font:15px/1.5 system-ui,sans-serif}main{max-width:1400px;padding:22px;margin:auto}
h1{font-size:25px}a{color:#92dfca}.note{padding:12px;border-left:3px solid #efc47e;background:#302b23}
.controls{display:flex;flex-wrap:wrap;gap:14px;margin:18px 0}label{flex:1;min-width:160px}select{display:block;width:100%;margin-top:4px;padding:8px;background:#233346;color:inherit;border:1px solid #6d819a;font:inherit}
#figure{display:block;width:100%;height:auto;background:white;margin:12px 0}#status{color:#92dfca}.downloads{display:flex;gap:20px}
</style><main><h1>E2 — odległości i krzywe relacji</h1><p><a href="index.html">← Obrazy, molekuły i domeny</a></p>
<p class="note">Stały zestaw ilustracyjny: siedem zapowiedzianych przypadków, model seed20261101 i wszystkie trzy bazy.
Cechy rzeczywiste (<b>actual</b>), wspólna dostępność (<b>common</b>). Pozostałe ziarna, tasowania i własna dostępność są w pełnych zapisanych wynikach; nie wybrano najlepszego modelu.
ROC/PR oceniają relacje końców krawędzi, nie dokładne położenie konturu. Klatki jednej akwizycji nie są niezależnymi testami.</p>
<div class="controls"><label>Wykres<select id="kind"><option value="curves">ROC i precision–recall</option><option value="distances">Mediany i kwartyle odległości</option></select></label>
<label>Przypadek<select id="case"></select></label><label>Reżim<select id="regime"></select></label><label>Miejsca<select id="sampler"></select></label><label>Przestrzeń<select id="space"></select></label></div>
<div id="status" role="status"></div><div class="downloads"><a id="png" download>PNG</a><a id="svg" download>SVG</a></div>
<img id="figure" alt="Zapisany wykres E2"><p>Odległości native różnych rodzin mają osobne skale. Kwartyle opisują rozrzut par, nie przedziały ufności.
Brak odpowiednich par pozostaje brakiem miary. Liczebności i częstość klasy dodatniej są zapisane na figurach.</p></main>
<script>'use strict';const DATA=__DATA__, $=id=>document.getElementById(id);
function fill(id,values,preferred){const element=$(id),previous=preferred??element.value;element.replaceChildren();for(const value of values){const option=document.createElement('option');option.value=value;option.textContent=DATA.titles[value]||value;element.appendChild(option)}if(values.includes(previous))element.value=previous}
for(const [id,preferred] of [['case','measurement'],['regime','transductive'],['sampler','centers']])fill(id,[...new Set(DATA.figures.map(x=>x[id]))],preferred);
function update(){fill('space',$('kind').value==='distances'?['all']:['native','l2','adapted'],$('space').value||'adapted');$('space').disabled=$('kind').value==='distances';
const selected=DATA.figures.filter(x=>['kind','case','regime','sampler','space'].every(key=>x[key]===$(key).value));
if(selected.length!==1)throw Error('Wybór nie wskazuje jednej figury');const item=selected[0];
window.e2PlotsState={ready:false,id:item.id,kind:item.kind,case:item.case,regime:item.regime,sampler:item.sampler,space:item.space,count:DATA.figures.length};
$('figure').src=item.png;$('png').href=item.png;$('svg').href=item.svg;$('status').textContent=item.id;
$('figure').onload=()=>{window.e2PlotsState.ready=true};$('figure').onerror=()=>{window.e2PlotsState.error='Nie można odczytać PNG';$('status').textContent=window.e2PlotsState.error};}
for(const id of ['kind','case','regime','sampler','space'])$(id).onchange=update;update();</script></html>'''


if __name__ == "__main__":
    main()
