# Próba ręczna — Play, Pause i tempo (ticket 06)

W katalogu `NEtCAT-viewer`, w środowisku `netcat`, uruchom:

```bash
python -m stmviewer.main
```

Pod obrazem, nad nawigacją i miniaturami, znajdują się **Play/Pause**,
wybór **kl./s** i **Pętla**. Nowe okno ma 5 kl./s i wyłączoną pętlę.
Tempo podglądu nie zmienia czasu pomiaru ani wartości danych.

## Dane i oczekiwany wynik

Gotowe wzorce są wersjonowane w repozytorium; nie trzeba przygotowywać
plików binarnych ręcznie:

- `tests/stmviewer/fixtures/mpp/timed.MPP`: trzy rozpoznawalne klatki
  (L po lewej, gradient, L po prawej), źródłowe czasy 1,5 s / brak / 4,25 s.
  Odtwarzanie nie zmienia tych czasów. Generator: `python tests/stmviewer/make_mpp_fixtures.py`.
- `tests/stmviewer/fixtures/asymmetric.stp`: jedna klatka, Play nieaktywne.
- `tests/stmviewer/fixtures/mpp/truncated.mpp`: uszkodzony film do próby błędu.
- Seria STP: wybierz razem `tests/stmviewer/fixtures/series/klatka1.stp`,
  `klatka2.stp`, `klatka10.stp`. Kolejność pozostaje 1–2–10.
- Dłuższa próba: lokalny pomiar MPP, np. `data/MOVIE_3.MPP` lub
  `data/nanotrack_registration/trudne/MOVIE_8.mpp` z katalogu pomiarów.
  Duże dane pozostają lokalne, poza Git.

1. W pustym oknie Play jest nieaktywne. Otwórz pojedynczy STP: podgląd działa,
   Play nadal jest nieaktywne.
2. Otwórz `timed.MPP`. Naciśnij Play przy 5 kl./s bez pętli. Oczekuj klatek
   1–2–3 i zatrzymania na trzeciej. Przycisk wraca do napisu Play; numer,
   obraz i zaznaczenie miniatury wskazują tę samą klatkę.
3. Naciśnij Play na trzeciej: od razu pojawia się pierwsza. Przy 1 kl./s
   zatrzymaj film na drugiej, zaczekaj, a potem wznów go. Pause zachowuje
   bieżący obraz; wznowienie kontynuuje od bieżącej klatki.
4. Zaznacz Pętla i uruchom film. Po 3 następuje 1, odtwarzanie trwa.
   Wyłącz pętlę w trakcie Play: film kończy się przy najbliższym końcu serii.
   Sprawdź wszystkie tempa: 1/2/5/10/20/30. Zmiana tempa działa podczas Play.
5. W trakcie Play wybierz klatkę miniaturą, suwakiem, numerem i przyciskami
   poprzednia/następna. Każda z tych czynności zatrzymuje odtwarzanie.
   Kliknięcie bieżącej miniatury lub uchwytu suwaka również zatrzymuje film.
   Rozpoczęcie wpisywania numeru zatrzymuje Play; Enter zatwierdza wybór.
6. Podczas Play ustaw gamma 2, użyj kółka lub +/− i przeciągnij obraz.
   Odtwarzanie trwa; kolejne klatki zachowują gamma, powiększenie i położenie.
   Miniatury pozostają przy gamma 1. Dopasuj oraz Reset gamma również działają.
7. Podczas Play otwórz dialog i anuluj wybór. Następnie spróbuj wczytać
   `truncated.mpp` i zamknij komunikat. Stara seria pozostaje i Play może
   trwać dalej. Podczas importu w tle można oglądać starą serię; Anuluj import
   zachowuje jej bieżący stan. Jeśli film bez pętli dojdzie w tym czasie do
   końca, pozostaje na końcu — błąd importu nie cofa czasu odtwarzania.
8. Otwórz nowy poprawny film podczas Play: pierwsza klatka, pauza, gamma 1
   i dopasowany obraz. Wybrane tempo i pętla pozostają ustawieniami okna;
   nowa seria nie uruchamia się samoczynnie. Zamknięcie okna zatrzymuje Play.
9. Na dłuższym filmie sprawdź 5 kl./s przez co najmniej 30 s oraz reakcję
   Pause i ręcznego wyboru. Przy wyższym FPS na wolnym komputerze program
   może zwalniać, lecz ma pokazywać klatki po kolei. Kontrolowane przeciążenie
   malowania jest dodatkowo objęte testem automatycznym.

## Odtwarzalny pomiar na ekranie Linuksa

Pomiar jest osobny od testów pytest. Potrzebuje filmu z różnymi obrazami
klatek. W trybie Qt xcb okno musi pozostawać widoczne i niezasłonięte:

```bash
PYTHONPATH=. QT_QPA_PLATFORM=xcb python tests/stmviewer/measure_playback.py \
  /ścieżka/do/filmu.MPP --output /tmp/stmviewer-playback.json
```

Skrypt wybiera plik w rzeczywistym dialogu, buduje referencje przez ręczną
nawigację i odczytuje piksele z ekranu przez `QScreen.grabWindow`.
Przy `QT_QPA_PLATFORM=offscreen` ta sama komenda odczytuje już pomalowany
bufor okna Qt przez `QScreen.grabWindow`, bez wymuszania malowania przez
`QWidget.grab`. Ten wariant mierzy pracę aplikacji, bez kompozytora i monitora;
wynik JSON jawnie rozróżnia tryb pomiaru.

Sprawdza kolejność zmian przez 30 s, rozkład odstępów między obrazami
oraz 50 prób Pause i 50 prób wyboru numerem. Wynik JSON i zrzut okna PNG
zapisuje pod podaną ścieżką. Czas otwarcia obejmuje obsługę dialogu;
płynność mierzy dopiero po przygotowaniu obrazów. Nie zmienia źródła.

To automatyczna próba GUI, odrębna od ręcznego odbioru użytkownika.
Pomiar typowego original nie zastępuje odbioru dużej serii, aligned ani
Windows. Warunki końcowe są w [decyzji 06](issues/06-acceptance.md#answer).

## Status sprawdzeń

93 testy Viewera przechodzą w Qt offscreen. Obejmują Pause/wznowienie,
koniec/pętlę, wszystkie metody ręcznego wyboru, gamma/zoom/tempo, brak
pomijania przy wolnym malowaniu, błędy/anulowanie importu i zamknięcie.
Mypy strict: 15 plików bez błędów. Pełne repo: 1832 passed, 63 wcześniejsze
failed, 12 skipped; identyczny zestaw niepowodzeń jak przed zmianą.

Pomiar Qt offscreen na 84 klatkach 512 × 512 trwał 30 s: 4,956 kl./s,
mediana odstępu 201,61 ms, p95 204,34 ms, bez pominiętych obrazów.
Po 50 prób: Pause p95 5,40 ms, wybór p95 10,70 ms; wszystkie poniżej 250 ms.
To wyniki pomalowanego bufora Qt, bez kompozytora/monitora. Próbę xcb
przerwało zasłonięcie okna, więc nie została zaliczona jako pomiar płynności.
Dane, komenda i ograniczenia są w [przekazaniu](handoff.md).
Użytkownik potwierdził ręczny odbiór 2026-10-21: „testy manualne ok”,
zamykając próbę tego etapu, w tym płynność i reakcję. Nie podał systemu ani
dodatkowych wyników liczbowych; odrębne odbiory platform pozostają do wykonania.
