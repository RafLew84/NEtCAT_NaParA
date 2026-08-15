# Dokumentacja MolTrack

Ten katalog jest punktem wejścia do dokumentacji produktu i kontraktów domenowych
MolTrack. Dokumenty opisujące planowany workflow korekt domen są wersjonowane razem
z kodem, ale do czasu spełnienia bramki wydania pozostają oznaczone jako **draft**.

## Dokumenty kanoniczne

| Dokument | Zakres | Stan |
| --- | --- | --- |
| [CONTEXT.md](CONTEXT.md) | Słownik domenowy i relacje między pojęciami | bieżący i docelowy model domeny |
| [QUALITY_GATES.md](QUALITY_GATES.md) | Obowiązujące bramki jakości kodu | wdrożone |
| [DOMAIN_ANALYSIS_USER_GUIDE_DRAFT.md](DOMAIN_ANALYSIS_USER_GUIDE_DRAFT.md) | Zadaniowa instrukcja wariantu C i Quick start | draft implementacyjny |
| [DOMAIN_ANALYSIS_TECHNICAL_REFERENCE_DRAFT.md](DOMAIN_ANALYSIS_TECHNICAL_REFERENCE_DRAFT.md) | Seamy, właściciele stanu i inwarianty | draft implementacyjny |
| [DOMAIN_ANALYSIS_FORMATS_DRAFT.md](DOMAIN_ANALYSIS_FORMATS_DRAFT.md) | Wersje sesji, eksportu, referencji, presetów i raportów | stan obecny + kontrakt docelowy |
| [DOMAIN_ANALYSIS_MIGRATION_AND_TROUBLESHOOTING_DRAFT.md](DOMAIN_ANALYSIS_MIGRATION_AND_TROUBLESHOOTING_DRAFT.md) | Migracje, diagnostyka i bezpieczne odzyskiwanie | draft implementacyjny |

## Co jest źródłem prawdy

1. Dla zachowania dostępnego w wydaniu źródłem prawdy są stałe schematów, modele
   oraz testy w kodzie.
2. Dla planowanego workflow źródłem prawdy są `CONTEXT.md` i zatwierdzone decyzje
   mapy `manual-domain-orientation-calibration`.
3. Prototyp HTML pokazuje wyłącznie architekturę informacji wariantu
   **C — Spatial command center**. Nie jest implementacją ani dowodem akceptacji.
4. Instrukcja użytkownika może utracić dopisek `_DRAFT` dopiero po przejściu
   pełnej bramki dokumentacyjnej poniżej.

## Bieżący stan zgodności

Kod produkcyjny zapisuje obecnie MolTrack session v2, Domain Analysis state v1 i
Domain Analysis export v9. Docelowe session v3, correction workspace, export v10,
Reference Dataset v2, preset library i campaign report v2 nie są jeszcze
wdrożone. Z tego powodu instrukcja nie może być traktowana jako opis aktualnego UI.

## Bramka dokumentacyjna wydania

Wydanie workflow korekt domen jest zablokowane, dopóki wszystkie poniższe punkty
nie są spełnione:

- produkcyjne Qt realizuje zatwierdzony wariant C nad jednym workspace Controllerem;
- finalne nazwy kontrolek zostały przeniesione do instrukcji;
- screenshoty pochodzą z produkcyjnego UI, mają alt text i podpisy;
- Quick start przeszedł krok po kroku na czystej sesji i rzeczywistym przykładzie
  TTMAPP;
- test UI potwierdza, że menu `Help` otwiera właściwą wersję instrukcji;
- lokalne linki, nazwy plików i deklarowane wersje schematów są sprawdzane
  automatycznie;
- zachowanie walkthrough odpowiada testom akceptacyjnym, a dokumenty nie opisują
  funkcji spoza wydania.

Wynik i data walkthrough, identyfikator danych TTMAPP oraz wersja aplikacji muszą
zostać zapisane w instrukcji przed usunięciem oznaczenia draft.
