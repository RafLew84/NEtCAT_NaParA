# SD-V4-23a — przegląd implementacji

2026-11-09. Zastosowano `code-review`: niezależne osie Standards i Spec,
równolegle przez dwóch recenzentów. Baza przed zadaniem: `ee2071d`;
przegląd początkowy `git diff ee2071d...5ca2e6f`. Poprawka: `5de0d7f`.
Specyfikacja: [ticket 23a](23a-split-merge-classes.md). Standardy:
root AGENTS.md, stmdomains/AGENTS.md oraz wspólne kryteria i zasady
edycji ręcznej w [planie](README.md), wraz z heurystykami umiejętności.

## Standards

Nie stwierdzono naruszeń udokumentowanych standardów ani istotnych problemów
z listy heurystycznej. Zmiany pozostają w zakresie STM Domains. Rozdzielono
transakcję klas, obsługę pracy w tle, okno operacji i generator przykładu.
Wykorzystano istniejące reguły przypisania klas i podziału domen. Zachowano
historię, ochronę przed spóźnionym wynikiem oraz obsługę anulowania i zamykania.

Instrukcja odbioru podaje gotowy przykład, oczekiwane liczniki i komendę
uruchomienia w netcat. Rozróżnia sprawdzenie GUI agenta od otwartego odbioru
użytkownika oraz sprawność edycji od jakości detekcji.

**Standards: 0 uwag; brak stwierdzonego problemu wymagającego poprawki.**

## Spec

Pierwszy przegląd: **1 uwaga P2** — zakres pomijał dostępne wyniki wybranej
listy klas. Spec wymaga „wszystkie klatki wybranego wyniku korzystające z tej
listy klas”. W `ui/manual_class_operations.py` wcześniejszy wybór wariantu
innej klatki miał pierwszeństwo także przy obcym katalogu. Ponadto wersja
pochodziła z bieżącego widoku. Pomijano klatkę bez wyszukania zgodnego źródła.

Reprodukcja w netcat/offscreen: klatka 2 ma wynik wspólnego katalogu,
ale wcześniej wybrano na niej obcy wariant. Zakres 1–2 obejmował tylko
klatkę 1. Dwa nowe testy odtworzyły błąd (RED: `(0,)` zamiast `(0, 1)`).

**Poprawka `5de0d7f`:** resolver dobiera warianty zgodne z listą/katalogiem,
metodą i przebiegiem. Obcy wybrany wariant nie przesłania zgodnego wyniku;
wyszukiwanie obejmuje poprzednią analizę niezależnie od widocznej wersji.
Jawny anchor ma pierwszeństwo na własnej klatce. Przy wielu zgodnych
wariantach wybór jest deterministyczny, opisany w instrukcji, z ID w tabeli.

Ponowny niezależny przegląd poprawki potwierdził rozwiązanie P2, bez nowych
regresji i rozszerzenia zakresu. Testy controls/window: **13 PASS / 7,92 s**.

**Spec: 1 uwaga zamknięta, 0 otwartych.**

Podsumowanie osi: Standards — 0 uwag; Spec — 1 P2 poprawiona, 0 otwartych.
Końcowa regresja: **624 PASS / 280,46 s**, mypy **119 modułów PASS**.
Testy i otwarty ręczny odbiór: [raport](acceptance-23a.md).
