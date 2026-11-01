# Czy opis otoczenia usuwa sztuczne granice przy brzegu pola?

ID: 24a
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: claimed
Assignee: Codex — domains/start
Parent: [STM Domains — etap 2](../map-methods-and-save.md)
Blocked by: 24

## Podjęcie — 2026-11-01

Użytkownik polecił wykonać próbę zaproponowaną po omówieniu 24: usunąć
sztuczne podziały jednorodnej sieci, zachowując prawdziwe granice orientacji
i przesunięcia. [Protokół](../graph-context-boundary-protocol.md) ogranicza
próbę do istniejących kontroli i zamrożonych wag, bez nowych treningów.
Wynik 24 pozostaje zachowany. 25/26 i dodatkowe MPP/STP są nadal odłożone.

## Question

Czy spójna konwencja brzegu okna usuwa artefakt bez utraty prawdziwych granic?
Ablacja agregacji sąsiadów oddzieli wpływ samego opisu korzenia od grafu.
Nie uznajemy odrzucenia miejsc brzegowych za naprawę. Nie rozszerzamy tego
zadania do nowego uczenia, pomiaru materiału lub odbioru detektora.

## Dependencies

- [Uczenie grafu otoczeń molekuł — 24](24-graph-self-supervised-domains.md)
