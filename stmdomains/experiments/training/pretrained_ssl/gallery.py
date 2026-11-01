"""Saved issue26 grid comparison and adaptation diagnostics in one local HTML."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re

from ...bundle import file_hash, write_json
from .. import gallery as original
from .common import read_json, reporting_stage

LABELS = {'dino_adapted': 'DINOv2 · po adaptacji · nauczyciel EMA',
          'dino_frozen': 'DINOv2 · oryginalne wagi', 'fft': 'FFT · klasyczny punkt odniesienia'}
CASES = {'single': 'single', 'boundary': 'two_orientations', 'phase': 'phase_boundary',
         'missing': 'missing_band', 'artifact': 'stripes', 'orientation8': 'orientation_8deg'}


def document_template():
    html = original._HTML.replace('STM Domains — próba AE / rVAE', 'STM Domains — adaptacja DINOv2')
    html = html.replace('STM Domains · eksperyment 21', 'STM Domains · eksperyment 26 · prototyp')
    html = html.replace('Czy AE i rVAE uczą się cech, które pomagają znaleźć domeny lepiej niż klasyczna tekstura?',
        'Czy adaptacja DINOv2 pomaga rozdzielać domeny? Porównaj te same cechy przed i po uczeniu oraz klasyczne FFT.')
    labels = json.dumps(LABELS, ensure_ascii=False)
    line = 'function runLabel(run){const labels=' + labels + ';return `${labels[run.family]||run.family}${run.seed?` · ziarno ${run.seed}`:""}`;}'
    html, count = re.subn(r'function runLabel\(run\)\{[^\n]+', lambda _: line, html)
    if count != 1:
        raise ValueError('Source gallery run-label contract changed')
    html = html.replace('const f={fft:0,ae:1,rvae:2};', 'const f={dino_adapted:0,dino_frozen:1,fft:2};')
    extra = '<button id="scenario-phase">Przesunięcie</button><button id="scenario-orientation8">Obrót 8°</button><button id="scenario-missing">Brak centrów</button><button id="scenario-artifact">Paski</button>'
    html = html.replace('<button id="scenario-ttmapp">TTMAPP</button>', extra+'<button id="scenario-ttmapp">TTMAPP</button>')
    html = html.replace("['single','boundary','ttmapp']", "['single','boundary','phase','orientation8','missing','artifact','ttmapp']")
    html = html.replace('<div class="controls" id="scenarios">', '<p class="meta">Punkty oznaczają środki okien regularnej siatki 48 px. Nie są wykrytymi molekułami. Kolory pokazują zapisany podział; cechy pochodzą z oryginalnego pomiaru.</p><div class="controls" id="scenarios">')
    html = html.replace('Kontrola syntetyczna: zamrożony model i reguły z części uczącej.', 'Nowa realizacja znanej rodziny syntetycznej: zamrożony model i reguły z części uczącej.')
    html = html.replace('<footer>', '<footer><p>26: adaptacja ostatniego bloku DINOv2; nauczyciel EMA po ustalonym treningu. Lewy panel pozwala ocenić reprezentację przed odmowami, prawy obejmuje zachowaną bramkę porządku. To badanie jednej akwizycji, bez automatycznego odbioru detektora.</p>')
    return html


def build(output):
    from .evaluate import verify_freeze
    output = Path(output).resolve()
    if (output/'index.html').exists():
        raise FileExistsError('Preserve previous gallery')
    with reporting_stage(output, 'gallery') as budget:
        verify_freeze(output, check_budget=budget.check)
        control_path = output/'controls/evaluation/manifest.json'
        if file_hash(control_path) != read_json(output/'plan.json')['controls_evaluation_manifest_sha256']:
            raise ValueError('Control scenario metadata changed after the frozen plan')
        manifest = read_json(control_path)
        seed = min(row['seed'] for row in manifest['controls'])
        scenarios = {'ttmapp': 'ttmapp-250'}
        for name, case in CASES.items():
            matches = [row['sample_id'] for row in manifest['controls'] if row['case']==case and row['seed']==seed]
            if len(matches) != 1:
                raise ValueError('Fixed scenario missing: '+case)
            scenarios[name] = matches[0]
        write_json(output/'gallery/scenario-map.json', scenarios)
        write_json(output/'gallery/scenario-source.json', dict(control_manifest_sha256=file_hash(control_path),
            selection='Fixed first control seed and declared cases; no quality selection', control_seed=seed))
        old_template, old_read = original._HTML, original._read_json
        def checked_read(path):
            budget.check()
            return old_read(path)
        try:
            original._HTML, original._read_json = document_template(), checked_read
            result = original.build_gallery(output, scenario_samples={k:v for k,v in scenarios.items() if k in {'ttmapp','single','boundary'}})
        finally:
            original._HTML, original._read_json = old_template, old_read
        path = output/'index.html'
        prefix, tail = path.read_text().split('<script id="data" type="application/json">', 1)
        encoded, suffix = tail.split('</script>', 1)
        payload = json.loads(encoded)
        payload.update(schema='stmdomains-pretrained-ssl26-gallery-v1', scenarios=scenarios)
        for row in manifest['controls']:
            if row['sample_id'] in payload['samples']:
                payload['samples'][row['sample_id']]['control_case'] = row['case']
                payload['samples'][row['sample_id']]['control_seed'] = row['seed']
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        html = prefix+'<script id="data" type="application/json">'+encoded+'</script>'+suffix
        html = html.replace('`Kontrola · ${sample.id}`', '`Kontrola · ${sample.control_case||sample.id} · ${sample.control_seed||""}`')
        figures = []
        for filename, title in [('training-curves.png', 'Przebieg adaptacji i diagnostyka zadania'), ('descriptor-diagnostics.png', 'Zmiana opisu obrazu po adaptacji')]:
            fig = output/'figures'/filename
            if fig.exists():
                image = base64.b64encode(fig.read_bytes()).decode('ascii')
                figures.append(f'<details style="margin:16px 0"><summary>{title}</summary><img alt="{title}" style="width:100%;height:auto" src="data:image/png;base64,{image}"></details>')
        if len(figures)<2:
            raise ValueError('Training and descriptor figures required')
        html = html.replace('</main>', '<section><h2>Adaptacja i cechy</h2><p>Stałe próby diagnostyczne; strata samodestylacji ani zmienność cech nie określają jakości domen.</p>'+''.join(figures)+'</section></main>')
        path.write_text(html)
        result.update(schema=payload['schema'], html_bytes=path.stat().st_size, html_sha256=file_hash(path),
            source_sha256=file_hash(Path(__file__)), embedded_scientific_figures=len(figures), scenarios=scenarios,
            no_inference_in_gallery=True, controls='New seeds of known families', point_meaning='Grid crop centers, not molecule detections')
        write_json(output/'gallery/manifest.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    result = build(parser.parse_args().output)
    print(json.dumps({k:result[k] for k in ('html','html_bytes','samples','runs','predictions')}))


if __name__ == '__main__':
    main()
