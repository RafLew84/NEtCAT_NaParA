# REG-07 — sprawdzenia zapisu i odczytu sesji

Data: 2026-11-01. Gałąź `viewer/registration-difficult-movies`, baza `750c474`.
Raport dotyczy sesji, które zastąpiły wycofaną bibliotekę pełnych prób A/B.

## Rzeczywiste filmy

Sprawdzono pełne MOVIE_4 po usunięciu dwóch pierwszych źródłowych klatek oraz
MOVIE_8. Rejestracja Phase służyła przygotowaniu danych do próby zapisu,
nie ocenie jakości dopasowania. Do każdego filmu zastosowano dwie ręczne
korekty, po czym zapisano i ponownie odczytano samodzielną sesję.

| Dane | Klatki original | Rozmiar aligned: wiersze × kolumny | Plik sesji | Zapis | Odczyt |
| --- | --- | --- | --- | --- | --- |
| MOVIE_4, bez pierwszych 2 | 362 × 256 × 256 | 1367 × 489 | 214 445 150 B | 7,08 s | 1,58 s |
| MOVIE_8 | 84 × 512 × 512 | 1019 × 1773 | 216 429 734 B | 6,32 s | 1,13 s |

Dla **wszystkich** klatek porównano próbki original i aligned bajt po bajcie,
ważność, XY, geometrię, metadane, pochodzenie i historię zastosowanych korekt.
Dalsza ręczna poprawka po odczycie zmieniła oczekiwane klatki.
Wyeksportowano cały odtworzony aligned do MPP+JSON i sprawdzono zgodność próbek
po ponownym odczycie. Wyeksportowano również zakres pierwszych trzech klatek
każdego filmu jako FFV1; zapis obejmuje automatyczny odczyt kontrolny AVI.

Szczytowy RSS procesu diagnostycznego: **6712 MiB**, przy jednoczesnym utrzymaniu
źródeł, aligned, odtworzonej sesji i ponownie odczytanego pełnego MPP.
Nie jest to minimalna wymagana pamięć ani wynik pomiaru samego odczytu.
Limit formatu sesji wynosi 8 GiB nieskompresowanych próbek original+aligned;
limit metadanych to 64 MiB. ZIP kompresuje bezstratnie; NPY zachowuje float64,
NaN/Inf i znaki zera. Żadne wagi modeli nie trafiają do sesji.

Lokalne artefakty: `/tmp/stmviewer-session-real/`, raport `report.json`,
`MOVIE_4-moved.stmsession`, `MOVIE_8-moved.stmsession`, pełne MPP+JSON oraz
`*-restored-first3.avi`. Dane pozostają poza Git.

## Automatyczne sprawdzenia aplikacji

- Publiczny zapis/odczyt: oryginały, aktywny aligned, dwie korekty i dalsza
  edycja/cofnięcie, usunięte odniesienie, zagnieżdżona historia importowanego MPP,
  diagnostyka Deep+ECC/lokalnych fragmentów, geometria i metadane.
- Walidacja wersji ZIP/JSON/NPY, powtórzonych pól/plików, rozmiaru, typu,
  brakujących/uciętych danych i uszkodzonej kompresji. Kontrola przed alokacją.
- Anulowanie i błąd I/O: zachowany wcześniejszy plik i stan aplikacji,
  usunięte pliki tymczasowe, możliwość ponowienia.
- Qt offscreen: odczyt bez źródła i wag, gamma, zoom/przesunięcie osobno
  dla obu widoków, klatka/FPS/pętla, zatrzymanie Play, ostrzeżenia klatek,
  edycja/cofnięcie i eksport po odczycie, stan po usunięciu odniesienia,
  blokady w trakcie I/O i bezpieczne zamykanie okna.
- Kontrola obrazu okna po odczycie MOVIE_8: `/tmp/stmviewer-session-ui.png`.
  To automatyczne uruchomienie offscreen, nie ręczna ocena jakości dopasowania.

Końcowe liczby testów i przegląd: [karta sprawdzeń](reviews/REG-07-session.md).

Odbiór GUI/VLC przez użytkownika: **niewykonany**. Nie deklarujemy fizycznego
odbioru Windows 11 ani komputera z 8 GB VRAM. Instrukcja: [próba manualna](session-manual.md).
