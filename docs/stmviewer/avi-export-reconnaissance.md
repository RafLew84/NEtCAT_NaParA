# AVI — podgląd i lokalna próba kodeków

Sprawdzenie: 2026-10-19, baza `08c9ca6`, worktree `NEtCAT-viewer`.
To rozpoznanie dla [Opcji filmu AVI](issues/05-avi-export.md), nie eksporter.

## Obecny sposób wyświetlania

- [ViewerWidget](../../napara/gui/widgets/viewer_widget.py) stosuje 256-elementową
  szarą LUT z funkcją `x ** (1 / gamma)`. Gamma nie zmienia danych źródłowych.
  Histogram udostępnia też poziomy czerni i bieli.
- `set_image` domyślnie włącza `auto_levels=True` i automatyczne zmniejszenie
  obrazu na potrzeby ekranu. [SequenceViewerWidget](../../nanotrack/ui/widgets/sequence_viewer_widget.py)
  jawnie włącza automatyczne poziomy przy każdej klatce. Wspólna gamma nie
  oznacza zatem wspólnego zakresu kontrastu.
- Odczyt zainstalowanego kodu pyqtgraph `ImageItem.py` potwierdził użycie
  min/max z próbkowanej tablicy, z docelową liczbą próbek `2**16`.
  To obecny szczegół widgetu, nie samodzielna specyfikacja eksportu.
- Helper `_image_for_pyqtgraph_display` zastępuje brakujące wartości medianą
  w kopii do wyświetlania. Nie odtwarza maski ani szachownicy wymaganej przez
  nowy STM Viewer. Eksporter nie może traktować tej kopii jako oryginalnych
  danych ani automatycznie przejmować tego sposobu wypełniania braków.
- Osobne skale X/Y w transformacji widgetu wpływają na proporcje widocznego
  obrazu. Przy anizotropii natywne wymiary tablicy i proporcje fizyczne nie
  są tym samym. NaPara i NanoTrack ustawiają `imageAxisOrder='row-major'`.
- Osie, histogram, opisy i kontrolki są osobnymi elementami GUI.
  Zrzut okna nie jest stabilnym sposobem zapisu obrazu niezależnego od okna.

## Próba zapisu i odczytu AVI

[Skrypt próby](experiments/avi_codec_probe.py) generuje wyłącznie małe tablice
uint8 BGR, zapisuje wyniki w `/tmp/stmviewer-avi-probe/` i odczytuje je pętlą
OpenCV. Kolorowe prawe/dolne krawędzie pozwalają wykryć utratę pikseli.
Nie wymaga danych pomiarowych ani GUI.

Uruchomienie z worktree:

```bash
/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python docs/stmviewer/experiments/avi_codec_probe.py
```

Środowisko: Python 3.12.12, NumPy 2.2.5, OpenCV 4.11.0. Build deklaruje
FFmpeg (avcodec 59.37.100, avformat 59.27.100) i brak GStreamer.
Sama lista potencjalnych backendów zawiera także GStreamer, więc nie jest
dowodem jego działania. Faktycznie użyty writer i reader raportowały FFMPEG.

| Kodek | Rozmiar źródła W×H | Rozmiar podany do writer | Rozmiar odczytany | Klatki / FPS | Piksele po odczycie |
| --- | --- | --- | --- | --- | --- |
| MJPG | 64×48 | 64×48 | 64×48 | 7 / 7,5 | Zmienione przez kompresję stratną. |
| MJPG | 65×49 | 65×49 | 64×48 | 7 / 7,5 | Utracona ostatnia kolumna i wiersz. |
| MJPG | 65×49 | 66×50 po dopełnieniu | 66×50 | 7 / 7,5 | Geometria zachowana; kompresja stratna. |
| FFV1 | 64×48 | 64×48 | 64×48 | 7 / 7,5 | Dokładnie zgodne z wejściem uint8 BGR. |
| FFV1 | 65×49 | 65×49 | 64×48 | 7 / 7,5 | Zwrócony fragment dokładny, ale krawędzie utracone. |
| FFV1 | 65×49 | 66×50 po dopełnieniu | 66×50 | 7 / 7,5 | Dokładnie zgodne z wejściem uint8 BGR. |

Wszystkie writery zgłosiły poprawne otwarcie, również przy cichym obcięciu.
Liczbę klatek potwierdzono metadanymi oraz faktyczną pętlą odczytu.
Raport maszynowy po wykonaniu skryptu jest w
`/tmp/stmviewer-avi-probe/results.json`; plików AVI nie dodano do Git.
FFV1 zachowuje wyrenderowany raster, nie oryginalne wartości float pomiaru.

## Ograniczenia potwierdzenia

Próba obejmuje sześć małych filmów w jednym lokalnym środowisku.
Nie jest testem odtwarzaczy systemowych, VLC ani programów prezentacyjnych
na komputerach użytkowników. Nie sprawdzano dużych AVI, przerwania zapisu,
NaN w rendererze aplikacji, tekstu/podziałki, kompletnego GUI ani prawdziwego
eksportera. Nie instalowano pakietów i nie zmieniono wspólnych modułów.

Do odbioru implementacji potrzebne są: wybrany odtwarzacz, kontrola orientacji,
pełnych krawędzi, liczby klatek i FPS oraz osobne sprawdzenie renderowania
kontrastu, maski, opisów i proporcji. `writer.isOpened()` nie wystarcza.
