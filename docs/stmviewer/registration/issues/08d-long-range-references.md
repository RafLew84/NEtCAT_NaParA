# REG-08d: Dalsze klatki odniesienia — etap warunkowy

**What to build:** Użytkownik uzupełnia graf z lokalnego okna o wskazane dalsze
klatki odniesienia i porównuje wpływ dodatkowych relacji na cały film.
**Blocked by:** [REG-08c](08c-graph-movie-application.md) oraz osobna decyzja
użytkownika po odbiorze, poparta przykładami problemów na dłuższym odcinku.
**Status:** planned
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.
**Dodano do planu:** 2026-10-31 jako warunkowe rozwinięcie rekomendacji.

Obowiązują [plan](../README.md), [protokół](../manual-protocol.md)
i [przegląd strategii połączeń](../../registration-multiframe-research.md#jak-wybierać-połączenia).
Nie blokuje REG-10–12 ani REG-09. Nie zaczynamy go automatycznie po REG-08c.

## Zakres i kryteria odbioru

- [ ] Start wymaga sesji z bazowym wynikiem okna oraz wskazanych problemów,
  których lokalne odniesienia nie rozstrzygnęły. Wariant ma dokładnie te same
  istniejące pomiary, model, solver, próg i kotwicę. Dodajemy tylko nowe pary.
- [ ] W GUI wybieramy skończoną listę klatek odniesienia i zakres klatek,
  które mają być z nimi porównane. Przed uruchomieniem widać numery źródłowe,
  listę/liczbę nowych par; duplikaty istniejących relacji są pomijane.
  Konfiguracja jest jawna, bez automatycznego wyboru „najlepszych” referencji.
- [ ] Dalsze pary używają tego samego modelu na oryginałach. Wspólne struktury
  mogą zniknąć, więc brak dopasowania ma przyczynę i nie tworzy zerowego XY.
  Tożsamość klatki pierwszej nie daje jej szczególnej jakości. Nie wymuszamy
  dopasowania wszystkich klatek do jednego obrazu mimo braku wspólnej części.
- [ ] Powstaje osobny wynik okno+dalsze odniesienia z porównaniem do samego
  okna, listą nowych relacji, ich rozbieżnościami i wpływem na globalne XY.
  Zgodne cykle i mniejszy dryf trajektorii nie wystarczają do oceny jakości.
- [ ] Rozszerzenie sesji w tym tickecie zachowuje zbiór bazowy i dodane relacje.
  Odczyt odróżnia aktywny aligned od niezastosowanego kandydata. Zastosowanie,
  korekty manualne, ochrona aktywnego filmu i eksport działają jak REG-08c.
  Błędy/anulowanie nie zmieniają poprzednich prób ani filmu.

Poza zakresem: wszystkie pary pełnego filmu, automatyczny wybór klatek
kluczowych, dopasowanie do uśrednionego szablonu, zmiana modelu i wygładzanie.
Jeśli próby wykazują brak wspólnych struktur, zapisujemy ograniczenie zamiast
zwiększać bez końca liczbę odniesień.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Okno + jawne odniesienia → nowy zbiór relacji:** zachowanie starych pomiarów,
  deduplikacja, prawidłowe źródła/kierunki, brak wyniku dalszej pary i odtwarzalność.
- **Znana seria + dalsza relacja → XY:** poprawne dalekie połączenie i mylący
  okresowy odpowiednik; diagnozy bez automatycznej deklaracji poprawy.
- **GUI/sesja/film:** porównanie dwóch prób, wersja ustawień, anulowanie,
  świadome zastosowanie, ręczne korekty i zgodność małego MPP/AVI z podglądem.

## Próba manualna

1. Otwórz sesję z odebranym wynikiem okna i przygotowany wzorzec dłuższej serii z błędami
   lokalnymi. Dodaj dalszą referencję; sprawdź nowe pary, znane XY i kontury.
2. Na wskazanym fragmencie MOVIE_4/MOVIE_8 wybierz referencję ze wspólnymi
   strukturami. Porównaj cały odcinek przed i po dodaniu relacji, bez zmiany progu
   ani modelu. Zapisz również pogorszenie i rzeczywiste zmiany próbki.
3. Sprawdź parę bez rozpoznawalnej wspólnej struktury: jawna odmowa albo
   niepewność, bez uznawania zgodnego wzoru okresowego za dowód jakości.
4. Zapisz/otwórz sesję, anuluj nowe obliczenie, zastosuj kompletny wynik i wykonaj
   mały eksport. Obrazy i korekty mają odpowiadać wybranemu wynikowi.

**Oczekiwany wynik:** osobny pomiar korzyści dalszych odniesień. Brak poprawy
może zakończyć ten kierunek bez dodawania kolejnych rodzajów grafu.
