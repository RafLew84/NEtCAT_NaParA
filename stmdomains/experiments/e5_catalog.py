"""Predeclared E5 contrasts; no selection using evaluation references."""
from __future__ import annotations

CONDITIONS = (
    dict(id='map_base', label='AE z32 · 48 px', baseline_id='map_base', contrast='map', feature='exact48', scales=[48], centering='exact', readout='z32'),
    dict(id='map_full', label='Mapa AE 64×7×7 · 48 px', baseline_id='map_base', contrast='map', feature='map48', scales=[48], centering='exact', readout='spatial'),
    dict(id='scale_base', label='Jedna skala · 48 px', baseline_id='scale_base', contrast='scale', feature='exact48', scales=[48], centering='exact', readout='single'),
    dict(id='scale32', label='Jedna skala · 32 px', baseline_id='scale_base', contrast='scale', feature='exact32', scales=[32], centering='exact', readout='single'),
    dict(id='scale64', label='Jedna skala · 64 px', baseline_id='scale_base', contrast='scale', feature='exact64', scales=[64], centering='exact', readout='single'),
    dict(id='scale_multi', label='Połączenie 32 + 48 + 64 px', baseline_id='scale_base', contrast='scale', feature='multi', scales=[32, 48, 64], centering='exact', readout='multiscale'),
    dict(id='center_base', label='Centrum źródłowe · 48 px', baseline_id='center_base', contrast='center', feature='exact48', scales=[48], centering='exact', readout='single'),
    dict(id='center_snap', label='Najbliższa siatka 8 + 16k', baseline_id='center_base', contrast='center', feature='snap48', scales=[48], centering='grid', readout='single'),
    dict(id='center_shift', label='Najbliższa siatka 16 + 16k', baseline_id='center_base', contrast='center', feature='shifted48', scales=[48], centering='shifted_grid', readout='single'),
)
PATCHES = dict(exact32=(32, 'exact'), exact48=(48, 'exact'), exact64=(64, 'exact'),
               snap48=(48, 'snap'), shifted48=(48, 'shifted'))
CONTEXTS = ('common', 'own')
STAGES = ('H_M1', 'A_fixed_M1')


def conditions(family):
    return [c for c in CONDITIONS if family == 'ae' or c['contrast'] != 'map']


def runs():
    result = []
    for regime in ('transfer', 'transductive'):
        for family in ('ae', 'rvae_full', 'rvae_content', 'fft'):
            for seed in ((None,) if family == 'fft' else (20261101, 20261102, 20261103)):
                ident = f'{regime}/{family}' + (f'/z32/seed-{seed}' if seed else '')
                result.append(dict(run_id=ident, regime=regime, family=family, seed=seed))
    return result


def feature_key(run, name):
    return f"{run['family']}__{run['seed'] or 0}__{name}"


def patch_keys(condition):
    if condition['feature'] == 'multi': return ['exact32', 'exact48', 'exact64']
    if condition['feature'] == 'map48': return ['exact48']
    return [condition['feature']]
