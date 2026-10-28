# Ticket 18 — duża seria: podgląd i rejestracja

Uruchomienie z katalogu repozytorium:

```bash
conda activate netcat
python -m stmviewer.main
```

## Dane do ręcznej próby

Lokalna seria: `data/large-ticket18-v2/large.mpp`, manifest obok pliku.
Zawiera 1000 obrazów 512 × 512, skale 1 nm/px, czasy co 1,5 s i kontrolowane
przesunięcia do 128 px w obu osiach. Mały znacznik binarny rozróżnia klatki
również po wyrównaniu. Plik MPP ma około 2,10 GB; pełny wynik aligned zajmuje
więcej pamięci niż oryginały. Przygotuj co najmniej 16 GB wolnego RAM.

Odtworzenie danych w **nowym** katalogu:

```bash
python tests/stmviewer/make_large_series.py data/large-ticket18-new
```

Generator zapisuje plik kolejno klatkami oraz manifest z SHA-256, wymiarami,
przesunięciami i czasem; nie tworzy stosu 1000 klatek w pamięci. Odmawia
nadpisania istniejącego `large.mpp`. Wzorzec nie ustanawia limitu importu.

## Ręczny scenariusz

1. Otwórz duży MPP. Sprawdź postęp odczytu i tworzenia miniatur. Po sukcesie
   licznik ma pokazać 1000 klatek, a metadane 512 × 512 px.
2. Włącz pętlę i Play przy 5 kl./s na co najmniej 30 s. Obserwuj ciągłość
   zmian obrazu. Sprawdź Pause, skok do odległej klatki, miniatury, zoom,
   przesuwanie i gamma. Przy 30 kl./s ewentualne spowolnienie nie może powodować
   przeskakiwania klatek.
3. Uruchom Phase. Podczas obliczeń wybieraj klatki i zmieniaj zoom/gamma.
   Postęp powinien się zmieniać; usuwanie/import są zablokowane. Po sukcesie
   program pokazuje pełny aligned. Zapisz faktyczny rozmiar podany w panelu;
   dla tego wzorca oczekiwany obszar to 640 × 640.
4. Powtórz co najmniej 30 s Play i próby wyboru/Pause w aligned. Przełączaj
   original/aligned; każde zachowuje własny zoom.
5. Usuń klatkę środkową, ostatnią i pierwszą. Pozostałe aligned zachowują
   swój obszar i położenie. Pierwotne czasy/pochodzenie pozostają, a bieżąca
   numeracja skraca się do 997. Ponów Phase: odniesieniem jest nowa pierwsza
   klatka, wynik pojawia się dopiero po pełnym zakończeniu.
6. Ponów Phase i anuluj raz podczas liczenia par, drugi raz podczas
   przygotowania aligned. Stary kompletny wynik ma pozostać dostępny.
7. Otwórz ponownie duży MPP i anuluj podczas odczytu, następnie podczas
   tworzenia miniatur. Bieżąca seria i jej aligned mają pozostać. Powtórz
   import z sukcesem, wykonaj Phase, a następnie jeszcze raz oba kroki.
8. Otwórz mały `tests/stmviewer/fixtures/mpp/known-times.mpp`. Program pokazuje
   trzy klatki i zwalnia poprzednie dane. RSS procesu nie musi od razu wrócić
   do wartości startowej: alokator może zachować wolne bloki do ponownego użycia.
   Dlatego oceniamy także powtarzane operacje i brak zatrzymanych starych tablic.

## Powtarzalny pomiar automatyczny

Osobny skrypt, niewłączany do szybkiego `pytest`. Wymaga środowiska aplikacji
oraz `psutil` (w użytym `netcat` jest 7.1.3), X11 i Qt xcb. Dla innego środowiska
pomiarowego można doinstalować `psutil` przez `python -m pip install psutil`.
Raport zapisuje ścieżkę wejścia, rozmiar i SHA-256 (obliczane przed pomiarem).
Okno musi być w całości widoczne i niezasłonięte; nie zmieniaj go ręcznie
podczas pomiaru. Raport i dwa zrzuty zapisują się we wskazanym katalogu.

```bash
QT_QPA_PLATFORM=xcb PYTHONPATH=. python tests/stmviewer/measure_large_series.py \
  data/large-ticket18-v2/large.mpp --output /tmp/stmviewer18-large.json

QT_QPA_PLATFORM=xcb PYTHONPATH=. python tests/stmviewer/measure_large_series.py \
  data/nanotrack_registration/dobre/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  --typical --output /tmp/stmviewer18-typical.json
```

Skrypt używa przycisków, edytora numeru klatki i rzeczywistego okna wyboru
pliku. Referencje obrazów zbiera przez ręczny wybór każdej klatki, a Play
sprawdza przez zrzuty pikseli X11, nie przez liczenie wywołań timera.
Każdy widok ma 30 s pomiaru przy 5 kl./s i 50 prób dla każdej czynności:
wybór oraz Pause. Daje to 100 prób na widok, 400 dla serii dużej i typowej.
Pause mierzy zmianę wyglądu przycisku i sprawdza zatrzymanie obrazu.
Próba przy 30 kl./s trwa dodatkowo 3 s. Zrzuty nie mierzą fizycznego odświeżania
monitora. Tryb `--smoke` skraca próbę i nigdy nie stanowi odbioru wydajności.

RSS jest próbkowany co 50 ms dla procesu i jego dzieci; krótszy szczyt może
zostać niedoszacowany. Raport rozdziela start, szczyt i koniec operacji oraz
sprawdza budżet 16 000 000 000 bajtów. Synchroniczny sterownik dostarcza
zdarzenia odroczonego usuwania Qt między etapami, tak jak powrót do zwykłej
pętli programu; nie wymusza GC ani oddawania pamięci przez alokator.
Czasy otwarcia obejmują dialog, dekodowanie i miniatury. To nie jest kontrolowany
pomiar zimnego dysku: cache plików systemu operacyjnego nie jest czyszczony.

Osobne sprawdzenie żywych buforów NumPy (wolniejsze; nie służy pomiarowi tempa):

```bash
QT_QPA_PLATFORM=xcb PYTHONPATH=. python tests/stmviewer/check_series_memory.py \
  data/large-ticket18-v2/large.mpp --output /tmp/stmviewer18-live-memory.json
```

[Wyniki i ograniczenia pomiaru](large-series-results.md).
Ręczna akceptacja użytkownika pozostaje otwarta. Odbiory platform Ubuntu
oraz Windows są osobnymi ticketami 20 i 21.
