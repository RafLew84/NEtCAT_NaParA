# Code review — ticket 14

Baza: `60785df41de0d5f20517e53cdf4abb0878df6e3c`.
Implementacja: `959c5c6`; poprawka po przeglądzie: `a9cf6b4`.
Data: 2026-10-26. Dwie niezależne osie skilla `code-review`, agenci read-only.

Zakres: `git diff 60785df...HEAD`, następnie osobno `git diff 959c5c6..a9cf6b4`.
Specyfikacja: [ticket 14](issues/14-original-avi-basic.md), decyzje
[AVI](../issues/05-avi-export.md) i [odbioru](../issues/06-acceptance.md).
Standardy: główny AGENTS.md, stmviewer/AGENTS.md, PARALLEL_DEVELOPMENT.md,
zasady implementacji, GLOSSARY.md oraz heurystyki skilla.

## Standards

Pierwszy przegląd: 0 naruszeń zapisanych reguł; 1 uwaga projektowa P3,
**możliwy Duplicated Code**. Warunek zajętości importu/rejestracji/MPP/AVI
powtarzał się w akcjach głównego okna. Zalecono dwa nazwane predykaty,
z zachowaniem świadomej różnicy dotyczącej importu.

Poprawka `a9cf6b4` wydziela `_processing_series` oraz `_operation_in_progress`.
Recenzent potwierdził usunięcie uwagi i brak nowych ustaleń w całym diffie poprawki.
Kod pozostaje w zakresie aplikacji; największy zmieniony plik ma 802 linie.
Zatwierdzone granice testów i rozróżnienie dowodów Qt/VLC/manual są zachowane.
**Końcowo 0 otwartych ustaleń Standards.**

## Spec

Pierwszy i uzupełniający przegląd: **0 ustaleń**. Zaimplementowano zakres
włącznie, FPS niezależne od Play, gamma podglądu, czarne tło, pełny obraz,
proporcje i dopełnienie, sprawdzenie kodeka, postęp/anulowanie oraz ochronę
wcześniejszego filmu. FFV1 porównuje się do rastra uint8.

Brak wyborów prezentacji, aligned i opisów odpowiada podziałowi ticketów.
Opcja Proporcje pikselowe realizuje wcześniejszy wybór pomijania zastępczej skali.
Dokumentacja oddziela wykonane próby Qt/VLC od oczekującego odbioru użytkownika.
Poprawka blokad, `r+b` przy synchronizacji i dokumentacja nie rozszerzają zakresu.

Łącznie: Standards — 1 uwaga P3 rozwiązana, 0 otwartych; Spec — 0 ustaleń.
