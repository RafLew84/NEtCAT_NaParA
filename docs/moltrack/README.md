# Dokumentacja MolTrack

Ten katalog jest kanonicznym punktem wejścia do dokumentacji wydanego workflow
Domain Analysis. Zestaw opisuje produkcyjny wariant C — Spatial Command Center —
i jest wersjonowany razem z kodem MolTrack 0.1.0.

## Dokumenty kanoniczne

| Dokument | Zakres | Stan |
| --- | --- | --- |
| [CONTEXT.md](CONTEXT.md) | Słownik domenowy i relacje między pojęciami | obowiązujący model domeny |
| [QUALITY_GATES.md](QUALITY_GATES.md) | Bramki jakości kodu i ratchet rozmiaru | wdrożone |
| [DOMAIN_ANALYSIS_USER_GUIDE.md](DOMAIN_ANALYSIS_USER_GUIDE.md) | Zadaniowa instrukcja wariantu C i zweryfikowany Quick start | wydane dla 0.1.0 |
| [DOMAIN_ANALYSIS_TECHNICAL_REFERENCE.md](DOMAIN_ANALYSIS_TECHNICAL_REFERENCE.md) | Seamy, właściciele stanu i inwarianty | wdrożone |
| [DOMAIN_ANALYSIS_FORMATS.md](DOMAIN_ANALYSIS_FORMATS.md) | Wersje sesji, eksportu, referencji, presetów i raportów | produkcyjne |
| [DOMAIN_ANALYSIS_MIGRATION_AND_TROUBLESHOOTING.md](DOMAIN_ANALYSIS_MIGRATION_AND_TROUBLESHOOTING.md) | Migracje, diagnostyka i bezpieczne odzyskiwanie | produkcyjne |

## Źródła prawdy

1. Stałe schematów, modele oraz testy w kodzie określają zachowanie wydania.
2. `CONTEXT.md` określa język domenowy i inwarianty.
3. Instrukcja użytkownika opisuje wyłącznie kontrolki produkcyjnego Qt wariantu C.
4. Prototyp HTML jest historycznym dowodem wyboru architektury informacji, nie
   alternatywną implementacją ani instrukcją operatora.

## Zgodność wydania

MolTrack 0.1.0 zapisuje MolTrack session v3 i Domain Analysis state v2. Produkcyjny
pakiet correction-aware ma export v10; legacy export v9 pozostaje jawnie
automatic-only. M6 i Orientation Reference Dataset używają target schema v2 i
collection envelope v2. Biblioteka/preset M6 używają odpowiednio
`m6-preset-library-v1` i `m6-preset-v1`, a raport kampanii
`m6-campaign-report-v2`.

## Dowód wydania dokumentacji

Clean-session walkthrough na rzeczywistych plikach TTMAPP przeszedł 2026-08-15.
Obejmuje oba stabilne backendy, korekty point/polygon, niezależne review, Save/Open
session v3, export v10, oba Reference Dataset v2 i jednorazowy Validation campaign
report v2. Cztery screenshoty w instrukcji zostały przechwycone bezpośrednio z
produkcyjnego `DomainAnalysisDialog` w tym samym przebiegu.

Menu `Help > Domain Analysis Guide` otwiera wersję instrukcji dołączoną do tej
wersji aplikacji. Automatyczna bramka sprawdza akcję Qt, lokalne linki, zgodność
wersji, alt text i podpisy screenshotów oraz ich SHA-256. Szczegółowy wynik jest w
[manifeście wydania dokumentacji](../domain_analysis_documentation_release.json),
który odwołuje się do [dowodu hard cutover TTMAPP](../domain_analysis_ttmapp_release_validation.json).
