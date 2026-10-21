# Ręczna próba 01 — pojedynczy STP

Uruchomienie i zależności: [README](README.md#uruchomienie).
Wszystkie poniższe funkcje są już dostępne; kolejne etapy nie są wymagane.

## Małe dane

W repozytorium są trzy syntetyczne pliki w `tests/stmviewer/fixtures/`:

- `asymmetric.stp`: 4 × 3 próbki double, biała litera L po lewej i na dole,
  szare znaczniki po prawej. Pole 8 × 9 nm, więc wyświetlany obraz jest nieco
  wyższy niż szerszy, mimo większej liczby kolumn niż wierszy.
- `unknown.stp`: 4 × 3 próbki, jasny pasek u góry poza lewym pikselem oraz
  jasny piksel poniżej. Brak kalibracji: obraz ma proporcje pikselowe 4:3,
  a metadane są opisane jako nieznane.
- `truncated.stp`: niepełny binarny obraz, przeznaczony do sprawdzenia błędu.

Można je odtworzyć bez danych pomiarowych i dodatkowych pakietów:

```bash
python tests/stmviewer/make_fixtures.py
```

Macierz wartości `asymmetric.stp` po odczycie (wiersze od góry, kolumny od lewej):

```text
12   0   0   3
12   0   6   0
12  12  12   1.5
```

`Z Amplitude: 99 nm` jest celowo różne od zakresu danych. Nie powinno mnożyć
ani normalizować tych wartości. UI normalizuje jedynie jasność podglądu.
Dokładne wartości sprawdzają testy importu; panel pokazuje jednostkę `nm`.

## Kroki i oczekiwany wynik

1. Z katalogu repo uruchom `python -m stmviewer.main`. Oczekuj pustego okna,
   komunikatu „Brak otwartego obrazu” i dostępnego przycisku „Otwórz STP…”.
2. Przyciskiem wybierz `asymmetric.stp`. Sprawdź białe L po lewej i na dole,
   brak obciętych krawędzi, źródło oraz „Klatka 1 z 1 · original”.
   Panel: rozmiar 4 × 3 px, kanał Topo, sygnał nm, pole X 8 nm / Y 9 nm,
   offset X 2 nm / Y −1 nm, napięcie 0 V, prąd 0.25 nA, kąt 0°.
3. Zmniejsz i powiększ okno. Cały obraz nadal jest dopasowany i zachowuje
   proporcje 8:9. Zmiana okna nie zmienia danych.
4. Użyj menu Plik → Otwórz STP albo Ctrl+O i otwórz `unknown.stp`.
   Nowy obraz zastępuje poprzedni, pole ma proporcje 4:3; parametry są
   nieznane. Nie pojawiają się wymyślone wartości 0 ani skala w nanometrach.
5. Otwórz wybór pliku i naciśnij Anuluj. Obraz i parametry zostają.
6. Otwórz `truncated.stp`. Komunikat wskazuje ten plik i przyczynę błędu.
   Zamknij komunikat. Nadal widzisz `unknown.stp`; można otworzyć następny STP.
7. Zamknij program, uruchom ponownie: stan jest pusty. Otwórz rzeczywisty
   pomiar, np. dostępny w repo
   `tests/moltrack/fixtures/ttmapp_domain_analysis_sources/movie2/34855.STP`.
   Oczekuj 256 × 256 px, kanału Topo, jednostki nm, pola około
   68.1811 × 68.1811 nm. Prąd, napięcie i kąt pozostają nieznane.

Przy zgłaszaniu wyniku podaj system, interpreter, commit i numery kroków.
Automatyczny Qt offscreen oraz sterowana skryptem próba okna xcb nie są
ręcznym odbiorem przez użytkownika. Windows jest osobnym wymaganym odbiorem
całej aplikacji w tickecie 21.
