# REG-08b — porównanie LS i Hubera

Status: **done**; użytkownik potwierdził „testy manualne ok” 2026-11-01.
Poniższe kroki zachowano jako instrukcję ponowienia próby. Potwierdzenie nie
określa systemu, sprzętu ani porównawczej jakości na poszczególnych filmach.

## Uruchomienie i dane

W katalogu `NEtCAT-viewer`, środowisko `netcat`:

```bash
python -m stmviewer.main
```

Otwórz sesję z grafem REG-08a, następnie **Dopasowanie wieloklatkowe…**.
Huber korzysta wyłącznie z zapisanych relacji. Nie potrzebuje wag LoFTR, Torch,
Kornia ani GPU; nowe dopasowanie Deep nadal wymaga swojego modelu.

Istniejące sesje na stanowisku:

- `/tmp/reg08a-movie4-final/window-3.stmsession` i `window-5.stmsession`:
  MOVIE_4 z już usuniętymi dwiema pierwszymi klatkami.
- `/tmp/reg08a-movie8-final/window-3.stmsession` i `window-5.stmsession`:
  pełny MOVIE_8.

Wyniki w `/tmp` są tymczasowe. Aby je zachować, zapisz sesję w wybranym katalogu.

## Obliczenie i porównanie

1. Ustaw **Próg Hubera** (domyślnie 2 px), kliknij **Oblicz nowy wariant Hubera**.
   Limit iteracji wynosi domyślnie 200; można jawnie go zwiększyć.
   Program używa dokładnie tych samych pomiarów, braków, źródeł i pierwszej
   klatki odniesienia co LS. Nie wykonuje ponownie Deep.
2. W zakładce **Film** przełącz **Kandydat grafu — wspólne XY (LS)** oraz
   nowy wariant **Huber 1 — próg 2 px**. Obejrzyj film, Play/Pause, kolejne
   klatki i te same szczegóły w zoomie. Kadr i kontrast są wspólne.
3. Sprawdź XY Hubera i ich różnicę względem LS. W tabeli relacji sprawdź
   pomiar, resztę LS, resztę Hubera i końcową wagę. Waga mniejsza od 1 oznacza
   ograniczony wpływ konfliktowej relacji w tym rozwiązaniu; nie dowodzi,
   że pomiar jest fizycznie błędny.
4. Zmień próg na 1 px i oblicz następny wariant. Samo wpisanie progu nie
   zmienia wcześniejszego wyniku. Oba warianty pozostają na liście; można je
   przełączać bez ponownej rejestracji.
5. Obejrzyj informację o zakończeniu, iteracjach, koszcie i uwarunkowaniu.
   Odmowa lub limit iteracji nie tworzą filmu Hubera; wcześniejsze poprawnie
   obliczone warianty i LS pozostają. Dane ostatniej iteracji są diagnostyką.
   Przy limicie można zwiększyć **Limit iteracji** i utworzyć nowy wariant;
   wcześniejsza nieukończona próba również pozostaje w sesji.

Próg dotyczy **długości całego wektora błędu XY** w pikselach. Jedna waga
obejmuje obie osie. Mniejszy próg szybciej osłabia konfliktowe relacje;
nie oznacza automatycznie lepszego dopasowania struktur.

## Wzorce do ręcznego odbioru

Generator przygotowuje nowe sceny, oddzielne od danych doboru ustawień:

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/robust_graph_fixtures.py acceptance /tmp/stmviewer-reg08b-fixtures
```

Każdy przypadek ma wejściową sesję LS oraz sesję `*-with-huber.stmsession`.
Pomiary są **zadane**, nie są wynikiem modelu Deep. Oczekiwane położenia
struktur dziewięciu klatek: `(0,0), (5,-3), (11,-7), (8,2), (-6,5),
(-3,-8), (7,-1), (2,9), (-8,4)`; pełne wyniki liczbowe są w `manifest.json`.

- `one-outlier`: jeden celowo błędny pomiar 3→6, błąd `(18,-14)` px.
  Porównaj odchylenia LS i Hubera od znanych położeń. Huber ogranicza wpływ
  odstającej relacji; nie oczekuj idealnego odzyskania wszystkich XY.
- `bridge`: jedyne połączenie obu części grafu ma błędne XY. Brak obejścia
  uniemożliwia rozpoznanie tego błędu z samych relacji; Huber go nie naprawi.
- `tree`: brak relacji nadmiarowych. LS i Huber mogą dać ten sam wynik.
- `disconnected`: dwie odłączone części; brak pełnego rozwiązania.
- `periodic-alias`: obraz okresowy co 24 px i spójne błędne przesunięcia.
  Zerowa reszta oraz wagi 1 nie rozwiązują niejednoznaczności.
- `majority-wrong`: dominują spójne błędne pomiary. Huber nie gwarantuje
  odzyskania prawdziwego ruchu; może wzmocnić błędną większość.

## MOVIE_4 i MOVIE_8

Gotowe sesje i wyniki liczbowe podaje [raport](robust-graph-results.md).
MOVIE_4/3 nie osiągnął zbieżności nawet przy limicie 5000; w tej sesji oceń
wyraźną odmowę i zachowanie LS. Dla MOVIE_4/5 i MOVIE_8 dostępne są kompletne
warianty obu progów, w niektórych przypadkach z jawnym limitem 5000.

Dla każdego zapisanego okna 3/5 porównaj LS i progi 2 oraz 1 px na tym samym
zestawie relacji. Dla MOVIE_4 sprawdź 29→30, 35→36, 44–46, 61→62, 94–97,
pierwsze 150 klatek i cały film; numeracja po usunięciu dwóch pierwszych.
Obejrzyj też pełny MOVIE_8. Zanotuj poprawę, pogorszenie lub niejednoznaczność
na rozpoznawalnych strukturach. Spadek kosztu Hubera nie jest oceną jakości STM.

## Sesja, anulowanie i aktywny aligned

1. Zamknij okno grafu i zapisz sesję. Otwórz ją ponownie, również bez wag
   lub bibliotek modelu. Oba warianty, ich progi, XY, wagi i zakończenia zostają.
2. Rozpocznij kolejne obliczenie i anuluj. Poprzednie warianty i aktywny film
   pozostają. Krótka próba może zakończyć się przed kliknięciem Anuluj.
3. Podczas obliczeń zmiana serii i zapis są zablokowane, podgląd główny działa.
4. Obejrzenie lub obliczenie Hubera nie zmienia aktywnego aligned, ręcznych
   korekt ani eksportu MPP/AVI. **Zastosowanie wyniku do filmu należy do REG-08c.**
5. Nowe pomiary Deep lub inna seria tworzą nowy zestaw relacji; warianty Hubera
   poprzedniego grafu nie są do niego przenoszone. Zapisz sesję przed taką zmianą,
   jeśli chcesz zachować poprzednie porównanie.

Ręczny odbiór pozostaje oddzielny od testów Qt offscreen i pomiarów liczbowych.
