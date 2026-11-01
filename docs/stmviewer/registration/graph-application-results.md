# REG-08c — wyniki zastosowania grafu

Data: 2026-11-01. Status: **ready-for-review**; odbiór manualny oczekuje.
Kod `140136e`, poprawka czytelności `73bbc44`; baza `5f45b36`.

## Sprawdzony workflow

Publiczne API zastosowano do wcześniej zapisanych relacji, bez nowych wag,
obliczeń Deep ani optymalizacji. Proces blokował import Torch/Kornia.
Dla każdej serii i obu kompletnych wariantów LS/Huber wykonano:

1. Odtworzenie łańcucha z tych samych pomiarów i przykładową korektę X+1.
2. Jawne zastosowanie grafu, następnie przykładową korektę Y+1.
3. Zapis/odczyt samodzielnej sesji i dokładne porównanie próbek, masek,
   XY, korekt, tożsamości pomiarów i aktywnej bazy.
4. Przywrócenie poprzednika oraz powrót do grafu: identyczne próbki, maski,
   baza i nadpisania. Nowa rewizja chroni przed zastosowaniem starej próby pary.
5. Mały MPP+metadane po usunięciu końcowych klatek, dokładny odczyt próbek
   i pochodzenia; AVI FFV1/MJPG z aktywnymi poprawkami.

Korekty +1 służą próbie funkcji; nie są rekomendacją poprawy dryfu.
REG-08c nie zmienia wyznaczonych przez REG-08a/08b pozycji ani solverów.

| Dane | Klatki / okno | Zastosowanie LS / Huber | Obszar poprawionego LS / Hubera (H×W) | MPP |
| --- | --- | --- | --- | --- |
| Wzorzec z jedną błędną relacją | 9 / 3 | 0,015 / 0,014 s | 275×272 / 274×275 | 7 klatek |
| MOVIE_4 bez źródłowych 1/2 | 362 / 5 | 0,641 / 0,691 s | 320×341 / 307×349 | 31 klatek |
| MOVIE_8 | 84 / 3 | 0,679 / 0,684 s | 747×710 / 746×781 | 18 klatek |

Czas obejmuje walidację, zachowanie lekkiego poprzednika i render zastosowania,
nie wcześniejsze liczenie Deep ani zapis sesji. Huber: zachowany kompletny
wariant z progiem 2 px. Parametry modelu i solvera pozostają w każdej sesji.
Maksymalny RSS całego skryptu, który celowo trzyma kilka wyników do porównań:
176 MiB, 3879 MiB i 4079 MiB. To pomiar lokalny, nie odbiór sprzętu docelowego.
Poprzednik w stanie aplikacji nie zawiera dodatkowych tablic obrazów.

## Artefakty i ponowienie

Raporty i sesje:

- `/tmp/reg08c-known-v1/report.json`
- `/tmp/reg08c-movie4-v1/report.json`
- `/tmp/reg08c-movie8-v1/report.json`

Każdy katalog zawiera `ready-to-apply.stmsession`, `ls-corrected.stmsession`,
`huber-corrected.stmsession`, MPP z towarzyszącymi metadanymi i oba kodeki AVI.
[Instrukcja ręczna](graph-application-manual.md) opisuje użycie.

Skrypt wersjonowany w repo, przykład ponowienia do nowego katalogu:

```bash
PYTHONPATH=. python tests/stmviewer/diagnostics/graph_application_trial.py \
  /tmp/reg08b-movie4-window5-long/comparison.stmsession \
  /tmp/reg08c-movie4-repeat --moving-frame 30
```

Pozostałe wejścia: `/tmp/reg08b-movie8-window3-long/comparison.stmsession`
(z `--moving-frame 17`) i
`/tmp/stmviewer-reg08b-fixtures/one-outlier-with-huber.stmsession`
(z `--moving-frame 6`). Skrypt wymaga kompletnego zapisanego łańcucha;
nie uzupełnia pomiarów modelem. Mierzy zastosowanie i odtwarzalność, nie jakość STM.

## GUI i VLC

Automatyczny Qt offscreen: okna przy 1260×740, mała seria i MOVIE_4.
Obejrzano panel zastosowania, rozwijane 362 źródła, aktywny film, poprzednika
oraz opis ręcznej korekty G/surowy pomiar. Przyciski zastosowania i przywrócenia
są widoczne; ustawienia nowych obliczeń są niżej w przewijanym panelu.
Zrzuty i pomiary: `/tmp/reg08c-gui-audit/`.

VLC **3.0.24** na Linuksie odczytał wzorcowe AVI FFV1 i MJPG do EOF,
z aktywnym dekoderem i kodem wyjścia 0, bez błędów. Użyto wyjścia dummy:
to automatyczny test dekodowania, nie ręczna ocena odtwarzania.
Logi: `/tmp/reg08c-vlc-{FFV1,MJPG}-final.log`,
raport `/tmp/reg08c-vlc-report.json`. Niezależne testy eksportu dekodują AVI
przez OpenCV i porównują klatki z analitycznym wzorcem (FFV1 dokładnie,
MJPG z tolerancją kompresji), liczbę klatek i FPS.

Ręczna ocena obu filmów, Windows 11 i stanowisko docelowe pozostają do wykonania.
[Karta testów i przeglądu](reviews/REG-08c.md).
