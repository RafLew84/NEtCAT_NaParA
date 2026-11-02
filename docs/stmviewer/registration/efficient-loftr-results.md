# REG-10: wyniki prób EfficientLoFTR

Data: 2026-11-02. Implementacja `6644d8c`, baza `03ad8d9`.
Próby automatyczne; ręczna ocena użytkownika pozostaje otwarta.
**Na obu trudnych filmach nowy estymator nie uzyskał kompletnego wyniku.**
Stary Deep outdoor daje kompletne łańcuchy i LS. To porównanie całych
estymatorów, łącznie z różnymi regułami agregacji, nie izolacja jakości modeli.

## Stałe ustawienia i dane

- `netcat`, torch 2.9.1+cu128; NVIDIA GeForce RTX 5090, około 32 GB VRAM.
  Faktyczne urządzenie pełnych prób: CUDA:0. Wzorce dodatkowe: CPU, 4 wątki.
- Model `eloftr_outdoor.ckpt`, pełny FP32, przypięty kod i wagi według
  [instrukcji przygotowania](efficient-loftr-setup.md). W raporcie i sesji
  zachowane SHA, kod, biblioteki, urządzenie oraz parametry agregacji.
- MOVIE_4: 362 klatki 256 × 256 po pominięciu źródłowych 1–2.
  MOVIE_8: 84 klatki 512 × 512. SHA plików i obrazów są w raportach lokalnych.
  Pliki źródłowe nie zostały zmienione.
- Te same listy sąsiednich par i grafów z oknem 3 dla obu metod. LS ma równe
  wagi, Huber używa tych samych pomiarów. Żaden score modelu nie jest wagą.
- Niezależny min/max każdego oryginału, bez gamma i skalowania; padding
  zerami tylko z prawej i dołu do wielokrotności 32. Punkty poza oryginałem
  nie tworzą poparcia. XY przesuwa obraz ruchomy na bazowy; finalne piksele
  powstają z oryginałów w istniejącym rendererze.

Reguły `translation-consensus-v1`: promień 1,5 px, maksymalnie 128 hipotez
z ustalonym ziarnem, co najmniej 8 zgodnych punktów i 25% poprawnych punktów;
konkurencyjna grupa z poparciem ≥80% największej i odległością >3 px daje
odmowę. Poparcie musi zajmować co najmniej 4 pola oraz ≥3 wiersze i ≥3
kolumny siatki 4 × 4 w obu obrazach; zasięg obu osi ≥25%, ortogonalny
rozrzut ≥0,05 znormalizowanego pola. Wynik pozostaje `manual_review`.

Regułę trzech wierszy/kolumn doprecyzowano podczas rozwoju na wzorcach:
pierwszy wariant przyjmował pas oraz ruch tylko górnej połowy. Model może
lokalizować punkty poza faktycznie teksturowanym pasem przez kontekst cech.
Nowa reguła odrzuca te konkretne przypadki, ale **nie stanowi niezależnej
oceny obrazu** ani ogólnego rozwiązania tearingu. Wzorce użyte do tej decyzji
są danymi rozwojowymi. Wcześniejsze wyniki zachowano osobno; nie dopasowywano
progów do MOVIE_4/MOVIE_8. Inne położenie zakłóceń może nadal przejść reguły.

## Pełne filmy

| Film / estymator | Odmowy par grafu | Łańcuch | LS | Huber |
| --- | ---: | --- | --- | --- |
| MOVIE_4 / Efficient | 430 / 1080 | odmowa 1→2 | 103 rozłączne komponenty | rozłączny |
| MOVIE_8 / Efficient | 229 / 246 | odmowa 1→2 | 67 rozłącznych komponentów | rozłączny |
| MOVIE_4 / Deep outdoor | 3 / 1080 | kompletny | kompletny | limit 200 iteracji |
| MOVIE_8 / Deep outdoor | 0 / 246 | kompletny | kompletny | zbieżny, 46 iteracji |

Numery w tej tabeli dotyczą bieżącej serii: odmowa 1→2 MOVIE_4 to źródłowe
3→4. Największa komponenta Efficient w MOVIE_4 obejmuje 229 klatek.
Nie zastosowano rozłącznego grafu ani nie uzupełniono braków inną metodą.
Zapisane kandydaty obu filmów odtworzono z sesji bez promocji do aligned.
Pełne relacje, w tym wskazane wcześniej problematyczne pary, są w sesjach.
Brak całego wyniku ogranicza wizualne porównanie pełnych aligned.

Instrumentowane czasy grafu (sekundy) i szczyty zasobów procesu:

| Film / estymator | Całe obliczenie grafu | Model z transferami | Konsensus Efficient | LS | RAM [MiB] | CUDA [MiB] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MOVIE_4 / Efficient | 9,90 | 6,99 | 2,03 | 0,006 | 2676 | 450 |
| MOVIE_8 / Efficient | 4,67 | 3,38 | 0,58 | 0,001 | 2636 | 996 |
| MOVIE_4 / Deep | 17,51 | 9,61 | osobno niemierzony | 0,011 | 2754 | 331 |
| MOVIE_8 / Deep | 15,51 | 5,52 | osobno niemierzony | 0,003 | 2644 | 936 |

Graf Efficient nie ma kompletnego renderowania. Dla Deep sam renderer
łańcucha: 0,61 s / 0,56 s; zastosowanie LS: 0,59 s / 0,58 s (MOVIE_4/8).
Miernik modelu obejmuje wykonanie i transfery; pozostałe sekcje profilowano
osobno. Czasy nie są gwarancją na innym sprzęcie. RAM to szczyt procesu,
CUDA to szczyt alokacji Torch, nie całkowite użycie karty. Łącznie z zapisami
i eksportami największy szczyt RAM wyniósł 3983 MiB (MOVIE_8/Deep). Po zadaniu
pozostaje około 8 MiB alokacji runtime; prywatne moduły upstream są usunięte,
a model nie pozostaje w pamięci aplikacji. Nie zaliczono stanowiska 8 GB VRAM.

## Wzorce i pełny cykl pracy

Końcowe porównanie CPU: `/tmp/reg10-patterns-v2/report.json`.

| Wzorzec | EfficientLoFTR | Dotychczasowy Deep outdoor |
| --- | --- | --- |
| cpu.mpp, dwie pary | maks. błąd osi 0,017 px | 0,299 px |
| przesunięcia subpikselowe, dwie pary | maks. błąd osi 0,336 px | 0,056 px |
| nieruchomy pas na ruchomej scenie | odmowa: konkurencyjne grupy | ≈(0,0), podąża za pasem |
| tekstura w jednym pasie | odmowa przestrzenna | ≈(7,0), tylko lokalne poparcie |
| różny ruch góry i dołu | odmowa przestrzenna | wybiera ruch górnej połowy |
| wzorzec okresowy | odmowa | za mało dopasowań |

Osobny wzorzec 193 × 259 na CPU: zadane (−7,+5), wynik
(−7,00565,+5,00211); padding do 224 × 288 i poprawne odrzucenie punktów
paddingu. Dodatkowe testy rzeczywistych wag obejmują parę CPU/CUDA,
łańcuch, graf/Hubera i zastosowanie. Na małym kompletnym wyniku sprawdzono
ręczną korektę, sesję, MPP z odtworzeniem wartości i pochodzenia oraz AVI
FFV1 z liczbą klatek, FPS i rozmiarem. Kompletne filmy Deep dodatkowo
przeszły zapis sesji/korekt, pięcioklatkowy MPP i AVI MJPG/FFV1.

Automatyczny Qt offscreen, z obejrzeniem zrzutów:

- `cpu.mpp` 1→2: (1,998878, −1,005877), 64/64 punkty;
  `/tmp/reg10-efficient-success-gui.png`.
- MOVIE_4 źródłowe 31→32: odmowa, 4/89 zgodnych wektorów;
  `/tmp/reg10-efficient-pair-gui.png`. Poprzedni wynik zachowany;
  odrzucona próba pokazuje oryginały bez nowego XY.

To testy automatyczne, nie ręczny odbiór użytkownika lub VLC.
Windows 11, sprzęt docelowy i niezależna jakość STM pozostają niesprawdzone.

## Artefakty i odtwarzanie

- `/tmp/reg10-movie4-efficient-v3/graph-candidate.stmsession`
- `/tmp/reg10-movie8-efficient-v3/graph-candidate.stmsession`
- `/tmp/reg10-movie4-deep-v1/` i `/tmp/reg10-movie8-deep-v1/` — kandydaci,
  pełne łańcuchy, zastosowane wyniki, korekty, MPP i AVI.
- Każdy katalog zawiera `report.json`; skrypt
  `tests/stmviewer/diagnostics/efficient_trial.py` odtwarza pełne próby.
- `tests/stmviewer/diagnostics/efficient_patterns.py` odtwarza porównanie
  wzorców przygotowanych przez generator REG-05.
- `/tmp/reg10-patterns/report.json` i wcześniejsze katalogi Efficient v1/v2
  dokumentują etap rozwoju. Końcowe wyniki to **Efficient v3 i wzorce v2**.

Przykład, do nowego pustego katalogu wyników:

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/efficient_trial.py \
  /tmp/reg10-recheck-movie4 --source data/MOVIE_4.mpp --drop-first 2 \
  --method efficient_loftr --device cuda
```

**Decyzja użytkownika o przydatności nowej metody i ręczny odbiór oczekują.**
[Instrukcja manualna](efficient-loftr-manual.md), [karta wykonania](reviews/REG-10.md).
