# Próba ręczna — filmy MPP (ticket 04)

W katalogu `NEtCAT-viewer`, po aktywowaniu środowiska `netcat`, uruchom:

```bash
python -m stmviewer.main
```

„Otwórz STP/S94/MPP…” (menu Plik lub Ctrl+O) przyjmuje **jeden MPP** albo
serię STP/S94. Wybranie kilku MPP lub połączenie MPP z obrazami daje komunikat;
poprzednia seria pozostaje otwarta. Nowy film zastępuje ją dopiero po pełnym
odczycie i przygotowaniu miniatur.

## Małe wzorce

Pliki w `tests/stmviewer/fixtures/mpp/` można odtworzyć poleceniem:

```bash
python tests/stmviewer/make_mpp_fixtures.py
```

| Plik | Oczekiwany wynik |
| --- | --- |
| `timed.MPP` | 3 klatki 4 × 3 px, Current, nA, pole 8 × 9 nm; czasy 1,5 s, brak, 4,25 s |
| `no-times.mpp` | 1 klatka, brak czasu; nawigacja wyłączona |
| `long.mpp` | 1000 klatek po 1 × 1 px i ponad 1000 linii nagłówka; ostatni czas 999 s |
| `truncated.mpp` | Ucięta trzecia klatka; komunikat wskazuje plik i klatkę 3/3 |

1. Otwórz `timed.MPP`. Pierwszy obraz to białe L po lewej i na dole,
   szary znacznik u góry po prawej i jaśniejszy wewnątrz. Panel pokazuje
   `Klatka źródłowa MPP: 1`, czas `1.5 s` i źródłowy zapis `1500 ms`.
   Offsety wynoszą 2 i −1 nm, napięcie −0,2 V, prąd 0,4 nA, kąt 37°.
2. Użyj Następna: druga klatka ma gradient od jasnego lewego górnego rogu
   do ciemnego prawego dolnego. Czas jest nieznany, numer źródłowy to 2.
   Trzecia klatka ma L po prawej i na górze, czas `4.25 s`, numer źródłowy 3.
   Wybieraj też suwakiem, numerem i miniaturami; podświetlona jest jedna miniatura.
3. Przybliż obraz kółkiem i przesuń lewym przyciskiem. Przejdź między klatkami:
   zoom i przesunięcie pozostają. „Dopasuj” przywraca całą klatkę.
4. Otwórz `long.mpp`, wpisz numer 1000. Oczekuj `Klatka 1000 z 1000`,
   numeru źródłowego 1000 i czasu 999 s. Pasek przewija się do ostatniej
   miniatury. Te jednopikselowe klatki mają jednolite szare podglądy.
5. Wróć do `timed.MPP`, wybierz trzecią klatkę i powiększ ją. Spróbuj
   otworzyć `truncated.mpp`. Po zamknięciu błędu film, numer, czas i widok
   mają pozostać. Powtórz z wyborem dwóch MPP oraz MPP wraz z STP/S94.
6. Anuluj okno wyboru plików — stan pozostaje. Aby sprawdzić „Anuluj import”
   w trakcie odczytu, użyj większego lokalnego filmu. Import ma postęp odczytu
   klatek i miniatur; anulowanie pozostawia wcześniejszy film i jego wybór.
   Małe wzorce mogą wczytać się zbyt szybko, by kliknąć anulowanie. Test
   automatyczny sprawdza ten przypadek z opóźnionym odczytem drugiej klatki.
7. Otwórz `no-times.mpp`, a następnie dowolny STP/S94. Oczekuj jednej klatki
   z nieznanym czasem; po STP/S94 opis numeru źródłowego MPP znika.

## Rzeczywiste pomiary lokalne

Dane są poza Git, w `/home/rlew/projekty/NEtCAT-domains/data/`:

- `MOVIE_3.MPP`: 17 klatek 256 × 256, Current, nA, pole 45,5181 × 45,5181 nm.
  Wybierz klatki 1, 9 i 17; numer w źródle i podgląd muszą się zmieniać razem.
- `MOVIE_1.MPP`: 36 klatek 301 × 268, Topo, nm, pole 150,848 × 134,31 nm.
  Służy także sprawdzeniu prostokątnego obrazu.
- `nanotrack_registration/trudne/MOVIE_4.mpp`: 364 klatki 256 × 256.
- `nanotrack_registration/trudne/MOVIE_8.mpp`: 84 klatki 512 × 512.
- `TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`: 268 klatek 256 × 256.

Lokalne filmy deklarują zerowe czasy; Viewer pokazuje źródłowe zero, nie
potwierdza jego prawdziwości jako czasu pomiaru. Zastępcze 1000 nm i zera
TTMAPP nie są wzorcem kalibracji. Na innym stanowisku użyj własnych danych.

## Kontrakt odczytu

MPP double little-endian zachowuje wartości float64 bez mnożenia przez
amplitudę Z. Obrót 180° jest wykonywany raz na wejściu, zgodnie z istniejącym
loaderem NanoTrack oraz STP; osie X/Y i wymiary nie są zamieniane.
Numer źródłowy jest przechowywany jako indeks od 0, a w GUI prezentowany od 1,
niezależnie od pozycji w bieżącej serii.

Czasy `Frames Synchronization / Frame 0000…` odnoszą się do indeksów źródła.
Obsługiwane jednostki: s, sec, ms, us/µs/μs, min i h. Brak, nieznana jednostka,
liczba bez jednostki i wartość niefinitywna dają nieznany czas wyłącznie tej
klatki. Oryginalny tekst pozostaje zachowany. FPS i Total Time nie wytwarzają
czasów klatek; nie zerujemy początku ani nie zamykamy przerw.

Nagłówek jest czytany do `[Header end]` bez limitu liczby linii/klatek;
pojedyncza linia ma ochronny limit 64 KiB. Liczbę i długość danych sprawdzamy
przed alokacją klatek. Metadane zachowują sekcje źródłowe. Nieznane jednostki
kalibracji pozostają nieznane, rzeczywiste zero z jednostką pozostaje zerem.
NaN pozostaje w danych; jego docelowa prezentacja należy do ticketu 05.
Odczyt dodatku metadanych i eksport należą do kolejnych ticketów.

## Wykonane sprawdzenia

68 testów Viewera i mypy strict (15 plików) przechodzą. Porównano wszystkie
klatki 12 lokalnych MPP z dotychczasowym czytnikiem po obrocie: wartości,
wymiary i NaN zgodne. Automatyczna próba rzeczywistego okna Qt xcb przeszła
na wzorcach oraz `MOVIE_3.MPP`; zrzuty oceniono wizualnie. To próby automatyczne.

Użytkownik potwierdził pozytywny wynik testów manualnych 2026-10-21:
„testy manualne ok”. Ticket 04 ma status `done`. Nie wskazano systemu;
odrębny odbiór platform, w tym Windows, pozostaje do wykonania.
