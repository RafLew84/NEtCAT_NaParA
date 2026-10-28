# Przegląd ticketu 19 — 2026-10-28

Skill: `/home/rlew/.codex/skills/code-review/SKILL.md`.
Dwie niezależne osie w równoległych agentach; przegląd tylko do odczytu.
Baza: `6b43765f71f28f77d1b8bf74cf2643f67e0dba15`.
Commit: `6888cff fix(stmviewer): support full-series metadata exports`.
Polecenie: `git diff 6b43765f71f28f77d1b8bf74cf2643f67e0dba15...6888cff`.
Spec: [ticket 19](issues/19-large-exports.md),
[zasady odbioru](README.md), [specyfikacja odbioru](../issues/06-acceptance.md).
Standardy: główny i aplikacyjny AGENTS.md, PARALLEL_DEVELOPMENT.md,
implementation/README.md, GLOSSARY.md oraz heurystyki skillu. Nie znaleziono
osobnych CODING_STANDARDS.md ani CONTRIBUTING.md.

## Standards

Nie stwierdzono naruszeń udokumentowanych standardów. Zmiany pozostają w zakresie
STM Viewer; potrzebną zmianę wspólnego czytnika przekazano integracji.
Dokumentacja rozróżnia pomiary automatyczne, VLC i oczekujący odbiór ręczny.
Test regresji korzysta z publicznego zapisu/odczytu.

Jedna drobna uwaga heurystyczna — **possible Duplicated Code**:

- `tests/stmviewer/measure_large_exports.py`: scenariusze anulowania i awarii
  powtarzały wybór zapisanego wyniku, identyfikację pliku i dodatku oraz
  sprawdzenie ich niezmienności:
  ```python
  target = Path(old["file"])
  before = source_identity(target)
  sidecar = (...)
  ...
  assert source_identity(target) == before
  ```
  Można wydzielić wspólne przygotowanie i sprawdzenie publikacji. Oba bloki
  nieznacznie się różniły: tylko wybór wyniku dla awarii jawnie wymagał
  `status == "saved"`. To uwaga dotycząca utrzymania skryptu, nie błąd
  obecnego przebiegu ani naruszenie reguły repo.

**Wynik: 0 naruszeń standardów, 1 nieblokująca uwaga heurystyczna.**

## Spec

Nie znaleziono nowych błędów implementacji ani rozszerzenia zakresu. Pełne
raporty potwierdzają 1000 klatek original/aligned, późniejsze serie 998 klatek,
zgodność MPP/FFV1, oba kodeki VLC, kontrolowane awarie i pomiary pamięci.
Refaktor `repeat_export` zachowuje zakres sprawdzeń.

Pozostaje **znana zależność odbiorowa**: wspólny czytnik NaPara/NanoTrack odrzuca
duży nagłówek. Specyfikacja wymaga „odczytu w Viewer i dotychczasowych czytnikach”,
a `implementation/README.md` stanowi, że potrzebny wkład integracji „jest częścią
odbioru odpowiedniego ticketu”. Przekazanie problemu jest poprawne i jawne,
lecz samo ręczne OK użytkownika nie powinno zamknąć ticketu jako `done`.
Warto zapisać ten warunek bezpośrednio przy statusie, obok oczekiwania na test manualny.

`ready-for-review` jest odpowiedni. Brak Windows i dodatkowej próby WSxM opisano
zgodnie z podziałem etapów; nie są przedstawione jako zaliczone.

**Spec: 0 nowych usterek; 1 jawna zależność integracyjna pozostaje do odbioru.**

## Działania po przeglądzie

Wydzielono `repeat_export` ze wspólnym wyborem wyniku `saved`, kontrolą SHA-256
obu plików MPP i sprawdzeniem usunięcia plików tymczasowych. Pełny smoke GUI
na 20/18 klatkach przeszedł: 13 eksportów, 3 anulowania, 2 kontrolowane awarie.
Kod produkcyjny nie zmienił się po pełnym zestawie testów.
Ponowny przegląd Standards tylko tej korekty potwierdził: 0 otwartych uwag,
bez nowych naruszeń; testów nie powtarzano w tym przeglądzie.

W tickecie, README i handoff dopisano dwa wymagane warunki `done`: ręczny odbiór
użytkownika oraz poprawkę/odbiór wspólnego czytnika w integracji. Ta zależność
pozostaje otwarta; nie została uznana za rozwiązaną przez samo przekazanie.

Standards: 1 drobna uwaga usunięta, 0 naruszeń. Spec: 1 znana zależność odbiorowa
pozostaje otwarta; 0 nowych usterek implementacji.
