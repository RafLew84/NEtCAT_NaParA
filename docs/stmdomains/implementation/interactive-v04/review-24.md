# SD-V4-24 — przegląd implementacji

2026-11-09. Dwie niezależne osie `code-review`. Baza `6b5820c`,
pierwszy przegląd `git diff 6b5820c...1c1b798`, poprawki `9b7a19b`.
Specyfikacja: [ticket 24](24-save-manual-corrections.md). Standardy:
root i aplikacyjne AGENTS.md, GLOSSARY i [wspólne kryteria planu](README.md).

## Standards

**P1 — znacznik zapisu przeżywał nadpisanie jedynego pliku.** Zapis korekt
do A, a potem nadpisanie A samym automatem nie unieważniało zapisanych
stanów korekt. Zamknięcie mogło pominąć ostrzeżenie, co naruszało zasadę
„Zamknięcie programu nie może bez ostrzeżenia utracić edycji”.

Poprawka: stan zapisu jest przypisany do konkretnej ścieżki. Nadpisanie
zastępuje cały jej punkt zapisu; Zapisz jako zachowuje punkt innego pliku.
Test rodzica odtworzył błąd przed poprawką. Recenzent potwierdził zamknięcie
uwagi i wykonał 3 testy netcat/offscreen: nadpisanie bez korekt, Zapisz jako
oraz zapis jednego źródła przy pozostałych niezapisanych.

**Standards: 1 P1 poprawiona, 0 otwartych.** Innych naruszeń standardów ani
istotnych problemów z listy heurystycznej nie stwierdzono.

## Spec

**P2 — drugi wariant podczas ponownego wejścia w edycję.** Po otwarciu
projektu wynik bazowy korekt i automat były osobnymi obiektami. Wybranie
automatu i rozpoczęcie edycji tworzyło nowy wariant zamiast wznowienia
poprzedniego. Naruszało to wznowienie własnych przypisań i historii.

Poprawka: zgodne oryginały są wiązane ze wspólnym wynikiem, którego tożsamość
pozostaje stabilna również po wymianie zawartości ograniczonego cache rastrów.
Sprawdzana jest zgodność wybranego oryginału z zapisanym automatem.
Regresje obejmują zwykły katalog oraz lokalny wynik geometrii bez katalogu.

**P2 — rozdzielenie atomowej transakcji przez uszkodzenie historii.** Przy
scaleniu A+B→istniejące A można było rozbić jeden krok na dwa, przeliczyć
sumę kontrolną i otworzyć plik. Jedno Cofnij zmieniało wtedy tylko jedną
klatkę. Naruszało to atomowość i wymóg odrzucania niespójnej historii.

Poprawka: jedna tożsamość transakcji występuje tylko w jednym globalnym
kroku. Zakres może obejmować niezmienione zgodne klatki, lecz musi odnosić
się do wariantów tej samej listy klas. Test odtworzył rozdzieloną transakcję
przed poprawką i potwierdził odmowę po poprawce.

Recenzent potwierdził obie poprawki, wykonując 6 testów netcat/offscreen
oraz ponawiając próbę uszkodzonego zakresu. Nie znalazł dalszych problemów
w sprawdzonym zakresie ani rozszerzenia zadania.

**Spec: 2 P2 poprawione, 0 otwartych.**

Podsumowanie osi: Standards — 1 P1 zamknięta; Spec — 2 P2 zamknięte.

Dodatkowa poprawka `94803e8` po próbie natywnego GUI: automatyczne
dopasowanie obrazu do zmienionego układu okna nie oznacza edycji użytkownika.
Porównanie stanu ignoruje pochodną skalę/środek tylko w trybie Dopasuj;
sam zapis widoku jest bez zmian. Ręczny zoom nadal oznacza zmianę.
Test RED/GREEN oraz ponowny przegląd Standards i Spec: bez uwag.
Recenzent Spec wykonał dodatkowo test regresji (1 PASS).

Końcowa regresja: **645 testów PASS / 292,67 s**, mypy **124 moduły PASS**.
Wyniki odbioru i instrukcja użytkownika: [raport 24](acceptance-24.md).
