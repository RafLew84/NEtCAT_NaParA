# 12: Wybierz liczbę klas automatycznie

**ID:** SD-V4-12

**What to build:** Użytkownik wybiera Auto zamiast K, analizuje zakres lub jedną klatkę i widzi wybraną liczbę klas wraz z wynikiem oraz informacją o nierozstrzygnięciu.

**Blocked by:** [07: Wybierz liczbę klas i zakres ich odkrywania](07-fit-shared-classes.md),
[11: Ustaw i uruchom pełną analizę w jednym oknie](11-unified-analysis-window.md).

**Status:** ready-for-agent — niewykonany; następny po zaimplementowanym 11
(`d18048b`, odbiór ręczny użytkownika 11 oczekuje).

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Auto jest dostępne w zakładce Klasy wspólnego okna z 11, dla bieżącej klatki, zakresu i całej serii. Zachowuje jeden zestaw parametrów akceptacji, porządku i domen; nie tworzy odrębnego formularza ani ścieżki resetującej ustawienia.
- [ ] Tryb Auto jest przekazywany przez dopasowanie, wybór modelu i segmentację; bazowe K5 ani wcześniejsze ręczne K nie nadpisują go po drodze. Klasy są wyznaczane z wybranego wejścia, bez modelu/paczki v0.4.
- [ ] Program porównuje dopuszczalnych kandydatów do wskazanego maksimum, z kontrolą liczby próbek. Pokazuje wybrane K i krótkie uzasadnienie.
- [ ] Jawna reguła odróżnia jedną klasę, K>=2 i brak podstaw do oceny. Reguła jest zapisana przed oceną TTMAPP; samo silhouette nie jest stosowane do K1.
- [ ] Kontrole obejmują pojedynczą sieć, dwa odróżnialne otoczenia, szum oraz brak/słabe dane. Program nie wymusza co najmniej dwóch klas.
- [ ] Użytkownik może przełączyć na ręczne K i porównać wynik. Wynik Auto nie jest potajemnie zastępowany ręcznym K5 ani historycznym rankingiem paczki; ranking powstaje dla aktualnie wybranych danych.
- [ ] Testy obejmują obie skale zakresu, powtarzalność, K1, nierozstrzygnięcie i pełne przejście trybu Auto przez obliczenia.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. We wspólnym oknie Analiza z 11 wybierz Auto w zakładce Klasy dla zakresu odkrywania 259–268 oraz dla pojedynczej klatki; sprawdź wybrane K i wynik bieżącej klatki. Wyniki pozostałych klatek nie udają przeliczonych. Sprawdź także analizę całego zakresu z Auto przy tym samym komplecie ustawień.
2. Na dostarczonych kontrolach jednej sieci i dwóch otoczeń sprawdź zachowanie Auto, następnie otwórz przykład z niewystarczającymi danymi.
3. Przełącz z Auto na K5 i z powrotem; widok oraz metadane muszą pokazywać faktycznie użyty model, bez nadpisania wcześniejszego wyniku.

## Granice zadania

Auto jest wyborem w ograniczonym zakresie, nie gwarancją liczby fizycznych faz.
Nowy klasteryzator bez K nie jest wymagany do realizacji tego ticketu.
W aktualnym planie 12 rozszerza wspólne okno z nowego 11, obejmujące już
analizę klatki i serii z 08. Historyczny zakres 11 wchłonięty przez 05/07
nie wraca; zależność dotyczy zadania o nowym zakresie z 2026-11-03.

Punkt integracji po 11: **Analiza → Analiza… → Klasy**.
Wspólny szkic jest w `stmdomains/ui/analysis_dialog.py`, pola klas
w `analysis_scope_fields.py`, a niemutowalne żądanie obliczeń to
`SeriesAnalysisPlan` w `stmdomains/analysis/series_settings.py`.
Rozszerzenie powinno zachować publiczne testy klatka/seria i pełny komplet
akceptacji, porządku oraz domen. [Odbiór obecnego przebiegu](acceptance-11.md).
