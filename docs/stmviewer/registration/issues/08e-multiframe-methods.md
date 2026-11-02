# REG-08e: Pozostałe metody w dopasowaniu wieloklatkowym

**What to build:** Użytkownik wybiera algorytm dopasowania par w istniejącym
oknie **Dopasowanie wieloklatkowe…**, oblicza wspólne położenia klatek przez
LS albo Huber i stosuje wybrany wynik do filmu.
**Blocked by:** [REG-08c](08c-graph-movie-application.md), odebrany.
**Status:** in-progress
**Manualny odbiór:** niewykonany; implementacja w toku.
**Start:** 2026-11-02, na jawne zlecenie użytkownika.
**Baza przeglądu:** `a631c79661dff5cb5d7b1bc387edcb22a4a490d6`.
**Dodano do planu:** 2026-11-02, na zlecenie użytkownika.

Obowiązują [plan](../README.md), [protokół prób](../manual-protocol.md)
i [zasady implementacji](../../implementation/README.md#praca-ze-skillem-implement).
To rozszerzenie istniejącego okna 3/5 klatek. REG-08d został wycofany;
nie jest zależnością ani częścią tego zadania. REG-10–12 zachowują osobne
zakresy nowych modeli. Po przygotowaniu ticketu użytkownik osobno zlecił implementację REG-08e.

## Efekt w aplikacji

Przykład: **Optical Flow → okno 5 → Oblicz kandydata grafu → Oblicz wariant
Hubera → obejrzyj film → Zastosuj wynik do filmu**. Analogiczna ścieżka działa
dla każdej dostępnej metody. Użytkownik rozróżnia **metodę dopasowania par**
od **sposobu wyznaczenia położeń filmu: LS/Huber**.

Nie dodajemy nowego okna, biblioteki prób A/B ani ręcznego planowania par.
Pozostają istniejące zakładki, porównanie z łańcuchem/aktywnym aligned,
przyciski obliczeń i zastosowania wyniku.

## Zakres metod

| Metoda w oknie wieloklatkowym | Obecny wariant w aplikacji |
| --- | --- |
| Phase | `phase_correlation` |
| Korelacja bez normalizacji (v1) | `phase_no_normalization` |
| Tile+RANSAC | `tile_correlation_ransac` |
| ECC | `ecc_translation` |
| Optical Flow | `optical_flow_median` — jedno globalne XY z mediany przepływu |
| Deep Matcher | `deep_matcher_translation` — zachowanie dotychczasowej metody |
| Deep Matcher + ECC (v1) | `deep_matcher_ecc` — istniejący wariant REG-04 |
| Deep Matcher + lokalne fragmenty (v1) | `deep_local_consensus` — istniejący wariant REG-05 |

Korzystamy z już istniejących estymatorów i ich ustawień. Nie zmieniamy
algorytmów ani kryteriów przyjmowania dopasowania, aby uzyskać pełny film.
Zestaw jest zamknięty do powyższych metod; nowe modele należą do REG-10–12.

## Kryteria odbioru

- [ ] W istniejącym panelu jest jedno pole **Metoda dopasowania par**.
  Domyślnie pozostaje Deep Matcher, a otwarcie zapisanej próby ustawia jej
  metodę i parametry. Wybór w tym oknie jest jawny i odrębny od metody
  rejestracji sąsiedniej w głównym oknie. Sama zmiana wyboru nie zmienia
  aktywnego aligned, istniejącego kandydata ani podpisów jego wyników.
- [ ] Kontrolki wag/urządzenia dotyczą tylko metod korzystających z Deep.
  Metody CPU działają bez wag i bez importowania Torch/Kornia. Niedostępność
  wybranej metody ma konkretną przyczynę; bez pobierania, cichej zmiany metody
  lub urządzenia. Model jest ładowany raz na zadanie, nie osobno dla każdej pary.
- [ ] Każda metoda mierzy te same pary wynikające z okna 3/5, na oryginalnych
  danych, niezależnie od gamma. Kierunek d_ij przesuwa klatkę j na i.
  Wynikiem pary jest jedno globalne XY. Nie dodajemy obrotów, zmiany skali,
  deformacji lokalnej ani przesunięć zależnych od linii skanowania.
- [ ] LS i Huber korzystają z dokładnie tego samego zapisanego zbioru pomiarów
  wybranej metody. Obliczenie Hubera nie uruchamia ponownie dopasowania par.
  Zachowujemy kotwicę, matematykę solverów i okno; zmiana metody tworzy nowego
  kandydata. Zmiana okna 3→5 może wykorzystać wspólne pomiary tylko przy
  identycznych źródłach, metodzie i ustawieniach. Pomiarów różnych metod nie mieszamy.
- [ ] Lokalna odmowa pary jest zapisana jako brak XY z przyczyną, a nie (0,0).
  Rozłączony graf pozostaje niekompletny. Awaria modelu/biblioteki, brak pamięci
  i anulowanie przerywają zadanie oraz zachowują poprzedniego kandydata i film.
  Metoda złożona nie wraca po cichu do samego Deep, jeśli ECC lub fragmenty odmówią.
- [ ] Poprawny wektor dwóch skończonych wartości XY dla właściwej pary,
  bez skalibrowanej pewności (`manual_review`, `quality_score=None`), może
  wejść do LS/Hubera z zachowaniem braku oceny. Nie jest przemianowany na
  pewne `ok` ani potraktowany jako brak dopasowania. Status `failed`, NaN/Inf,
  błędny wymiar wektora lub tożsamość pary nie stają się poprawnym pomiarem;
  niepoprawny wynik backendu zgłaszamy jako błąd z przyczyną.
  Wskaźniki metod mają własne znaczenie; nie stają się porównywalnymi
  prawdopodobieństwami ani wagami LS/Hubera. Zbieżność nie oznacza potwierdzonej jakości.
- [ ] Podgląd relacji, łańcucha i filmu oraz zastosowany aligned pokazują
  faktyczną metodę i solver. Dla niesąsiedniej pary nazwy obu klatek i numery
  źródłowe są poprawne także w postępie i błędach metod złożonych.
  Zachowujemy dostępne diagnozy pary Deep+ECC/fragmentów i przyczyny odmów;
  nie wymagamy nowej rozbudowanej wizualizacji diagnostyki.
- [ ] Sesja zachowuje metodę, jej parametry, wersję kodu/bibliotek i właściwe
  pochodzenie pomiarów, a w metodach modelowych również wagi/SHA i urządzenie.
  CPU nie dostaje fikcyjnych wag. Starsze sesje z grafem Deep otwierają się
  z dotychczasowym znaczeniem i bez przeliczania. Odczyt zachowanych wyników
  nie wymaga modelu ani bibliotek estymatora; weryfikujemy je dopiero przy nowym pomiarze.
- [ ] Kandydat pozostaje odrębny od aktywnego filmu. Zastosowanie kompletnego
  LS/Hubera, przywrócenie poprzednika, ręczne korekty, usuwanie klatek i MPP/AVI
  działają według REG-08c. W sesji i metadanych MPP zachowujemy prawdziwą
  metodę oraz solver; zgodność starszych zapisów pozostaje. Niekompletny Huber
  ma komunikat i nie jest automatycznie zastępowany przez LS.
- [ ] Postęp, Anuluj, blokady zmian serii i zachowanie gamma/wybranej klatki
  pozostają zgodne z obecnym programem. Dostarczone są gotowe małe dane,
  instrukcja odbioru, pomiary na MOVIE_4/MOVIE_8 i oddzielny opis jakości.
  Pliki kodu mają cel do 1000 linii i twardy limit 1500.

## Publiczne granice TDD

- **Metoda + seria + okno → pomiary:** wybór właściwego istniejącego estymatora,
  te same indeksy/kierunki par, znany ruch, odmowa, poprawne XY bez pewności
  oraz odrzucenie niepoprawnego wyniku backendu; brak
  zależności Deep dla CPU. Zamiana metody nie używa cudzych pomiarów z pamięci.
- **Zachowane pomiary → LS/Huber:** obie drogi na tym samym zbiorze, bez nowych
  wywołań estymatora; brakujące połączenia, odstający pomiar i niepełny Huber.
- **GUI → wynik → sesja/eksport:** wybór metody, poprawne etykiety i parametry,
  anulowanie/błąd bez podmiany filmu, zastosowanie, korekta, przywrócenie,
  odczyt starej sesji Deep oraz nowej sesji CPU i metody złożonej,
  mały MPP/AVI z geometrią i pochodzeniem zgodnymi z podglądem.

Testy publicznych granic, bez testowania prywatnych helperów i list kontrolek
jako osobnej implementacji. Atrapy ograniczamy do bibliotek/modeli i innych
zewnętrznych granic; rzeczywiste estymatory sprawdzamy osobno na małym wzorcu.

## Odbiór manualny

1. Uruchom `python -m stmviewer.main` w `netcat`. Wczytaj dostarczony wzorzec
   ze znanym ruchem i nawrotami. Otwórz **Dopasowanie wieloklatkowe…**.
2. Wybierz kolejno Phase, Optical Flow, ECC, Tile+RANSAC i korelację bez
   normalizacji. Dla każdej oblicz okno 3, potem Huber z tych samych relacji;
   sprawdź metodę w podpisach, liczbę par i film. Wybrane przypadki powtórz
   dla okna 5. CPU musi działać również bez wskazanych wag Deep.
3. Z lokalnymi wagami sprawdź Deep, Deep+ECC i Deep+lokalne fragmenty.
   Dla metody, która odmawia dopasowania, wymagaj czytelnej przyczyny i
   zachowania wcześniejszego filmu. Nie wymuszamy sukcesu na każdym wzorcu.
4. Na MOVIE_4 usuń źródłowe klatki 1 i 2 przed obliczeniami. Przy niezmienionej
   serii i oknie porównaj przynajmniej Optical Flow i Deep, osobno LS/Huber.
   Obejrzyj pierwsze 150 bieżących klatek i wcześniej wskazane trudne pary.
   Powtórz porównanie na MOVIE_8. Wyniki można przechować w osobnych sesjach;
   nie dodajemy biblioteki prób w programie. Zanotuj lepiej/podobnie/gorzej/
   niejednoznacznie oraz tearing osobno, bez oceniania jakości samym rozmiarem aligned.
5. Zastosuj wybrany kompletny wynik CPU, wykonaj korektę ręczną, zapisz i otwórz
   sesję, przywróć poprzedni wynik. Wykonaj mały eksport MPP/AVI i sprawdź
   ponowny odczyt, klatki, geometrię, metodę i solver. Analogiczny zapis sprawdź
   dla metody złożonej; starsza sesja Deep nadal ma się otwierać.
6. Anuluj pomiar oraz sprawdź niedostępną metodę i parę bez wyniku.
   Dotychczasowy aligned i wcześniejsze ręczne poprawki muszą pozostać.

**Oczekiwany wynik:** ta sama prosta obsługa wieloklatkowego LS/Hubera dla
wszystkich wymienionych metod, z jawnym wyborem algorytmu i bez przywracania REG-08d.
