# Czy opis otoczenia usuwa sztuczne granice przy brzegu pola?

ID: 24a
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
Assignee: Codex — domains/start
Parent: [STM Domains — etap 2](../map-methods-and-save.md)
Blocked by: 24

## Wynik — 2026-11-01

Wykonano [próbę](../graph-context-boundary-trial.md) i
[manifest](../graph-context-boundary-manifest.json): 3534 wyniki, 93 znane
kontrole, 8350 niezmienionych centrów, 0 fitów/kroków optymalizacji.
**A zaliczone:** półotwarte otoczenie daje jedną domenę i 121/121 centrów
przed/po odmowach dla wszystkich ziaren, wag i solverów. **B niezaliczone:**
prawdziwe granice pozostają błędne. C również niezaliczone dla zmienionych
wyuczonych modeli. Potwierdzono artefakt brzegu, bez naprawy detektora.

Galeria: `.scratch/graph-context-24a/index.html`. Źródła:
`stmdomains/experiments/training/graph_context/`; [odtworzenie](../../../stmdomains/experiments/training/graph_context/README.md).
Prototyp zachowano na `prototype/stmdomains-graph-context-boundaries`;
podjęcie `959fde3`, implementacja i protokół `ee73c83`.
Audyt 3534 predykcji i niezależny audyt metryk przeszły, 1302 bazowe wyniki
są identyczne z 24. Galeria: 40 sprawdzeń, zero błędów JS, trzy obejrzane zrzuty.

Status oznacza zakończenie zleconego eksperymentu, bez odbioru metody w 13.
25/26, dalszy trening i nowe dane nie zostały wybrane.

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
