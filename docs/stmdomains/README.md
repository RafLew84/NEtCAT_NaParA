# STM Domains

Program do wykrywania i analizy domen pól molekularnych na obrazach STM.
Katalog aplikacji: `stmdomains/`.

## Stan początkowy

Gotowe są osobny punkt uruchomienia, podstawowe okno PyQt6 i akcja zakończenia.
Zakres planowania obejmuje otwarcie zapisu z gotowymi oznaczeniami i powiązanymi
obrazami, przeglądanie klatek oraz analizę typów uporządkowania w serii.
Szkielet nie implementuje tych funkcji i nie wybiera modelu ani algorytmu.

## Mapa

[STM Domains — specyfikacja analizy typów uporządkowania w serii](map.md)
jest mapą decyzji `wayfinder`. [Rejestr pytań i zależności](issues/README.md)
prowadzi do kolejnych rozmów i prototypów; [słownik](GLOSSARY.md) ustala nazwy.
Na tym etapie tickety rozstrzygają decyzje, a nie zlecają implementację.
Pliki wersjonujemy na gałęzi `domains/*`; [przekazanie](handoff.md) opisuje stan
gotowy do odbioru w sesji integracyjnej.

## Uruchomienie

Z katalogu głównego worktree, w jego środowisku:

```bash
python -m stmdomains.main
```

[Przygotowanie środowiska](../../README.md) i
[praca równoległa](../PARALLEL_DEVELOPMENT.md).

## Kod do oceny i testy

- Istniejąca analiza molekularna: `moltrack/analysis/` oraz `tests/moltrack/`.
- Czytniki i model obrazu: `napara/io/`, `napara/core/data_models.py`.
- Viewer: `napara/gui/widgets/viewer_widget.py`.
- Testy nowych funkcji: `tests/stmdomains/` (na razie katalog startowy).

Współdzielony kod i modele mogą wymagać dodatkowych zależności poza PyQt6 szkieletu.
Nowe metody będą oceniane na danych i kryteriach rozstrzygniętych przez pytania mapy.

## Materiały do decyzji

- [Ogólne wykrywanie domen molekularnych](research-general-domain-detection.md)
  — przegląd metod wykrywania regularności rozmieszczenia i uporządkowania
  orientacji molekuł, założeń MolTrack oraz propozycja porównania metod na danych.
  Notatka badawcza z 2026-10-14, rozszerzona o rozwiązania z lat 2024–2026,
  w tym SBC/MatID, odkrywanie lokalnych środowisk i analizę obrazów STM.
  Wybór rozwiązania pozostaje otwarty.
- [Pomiar orientacji pojedynczej molekuły](research-molecular-orientation.md)
  — wymagane dane wejściowe, znaczenie kąta, porównanie metod oraz inspekcja
  przykładowego zapisu TTMAPP i wycinków obrazu. Parametry fizyczne eksportu
  są nieznane; definicja orientacji pozostaje do ustalenia na przykładach.
