"""Estimator identity across the known window-only provenance schema migration."""
from stmviewer.graph_types import GraphConfig

# REG-08a–08c hashed the solver/orchestrator together with these unchanged matcher
# files. Only this audited legacy digest maps to the estimator-only identity.
_LEGACY_ESTIMATORS = {
    'sha256:df02b29bb7e6c42ed6687999a5da783f55a1f9c40d4ce03402919c5cee959982':
    'sha256:820f7c85c41a25571e8514d58cef4666b4e90203989c936809cf52bb6c5fdf35',
}


def estimator_identity(config: GraphConfig) -> str | None:
    return config.pair_code_version or _LEGACY_ESTIMATORS.get(config.code_version)


def validate_extension_config(base: GraphConfig, added: GraphConfig) -> None:
    """Allow weight relocation/device selection spelling, never a different estimator."""
    for name in ('window', 'weights_sha256', 'device', 'backend_settings', 'libraries', 'settings_version'):
        if getattr(base, name) != getattr(added, name):
            raise ValueError(f'Dalsze odniesienia: ustawienia modelu nie odpowiadają bazie ({name}).')
    identity, current = estimator_identity(base), estimator_identity(added)
    if identity is None or current is None:
        if base.code_version == added.code_version and base.pair_code_version == added.pair_code_version:
            return
        raise ValueError('Dalsze odniesienia: nieznana wersja estymatora bazowego; wykonaj nowy graf okna.')
    if identity != current:
        raise ValueError('Dalsze odniesienia: kod estymatora różni się od bazowego grafu.')
