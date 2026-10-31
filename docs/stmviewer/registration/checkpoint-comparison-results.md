# Porównanie checkpointów Deep Matcher — 2026-10-31

Na pytanie użytkownika sprawdzono dodatkowe wagi klasycznego LoFTR, bez zmiany
kodowania obrazów, wyznaczania jednego XY ani ustawień aplikacji. Baza programu:
`6e50e57`. To osobny eksperyment z wagami, nie odbiór REG-05 ani rozpoczęcie REG-06.

**Outdoor i Indoor policzyły wszystkie 14 wskazanych par i oba pełne filmy.
Indoor New policzył 12/14 par, ukończył MOVIE_8 i odmówił w MOVIE_4.**
Wyniki checkpointów znacznie się różnią. Kompletność, score, rozmiar aligned
ani gładkość trajektorii nie rozstrzygają, które XY jest fizycznie poprawne.
Ręczna ocena struktur próbki pozostaje do wykonania.

## Checkpointy i zgodność

Kornia udostępnia trzy warianty: Outdoor z treningiem na MegaDepth oraz
Indoor i Indoor New z treningiem na ScanNet. Nie są to checkpointy trenowane
specjalnie na STM. [Dokumentacja Kornia](https://kornia.readthedocs.io/en/latest/feature.matching.html)
i [oficjalne pliki Kornia](https://huggingface.co/kornia/loftr).
Oryginalny LoFTR ma także warianty DS/OT; OT wymaga innego dopasowania i nie
został objęty tą zamianą plików. [Repozytorium autorów](https://github.com/zju3dv/LoFTR).

| Wariant | Plik | `coarse.temp_bug_fix` | Użycie w obecnym GUI |
| --- | --- | --- | --- |
| Outdoor | `loftr_outdoor.ckpt` | `False` | Obecne wagi |
| Indoor | `loftr_indoor.ckpt` | `False` | Można wskazać plik w polu wag |
| Indoor New | `loftr_indoor_ds_new.ckpt` | `True` | Sama zamiana pliku jest niewystarczająca; porównano osobnym skryptem |

W zainstalowanej Kornia 0.8.2 `LoFTR(pretrained=None)` używa starego kodowania
pozycji; tylko wybór `pretrained="indoor_new"` automatycznie zmienia flagę.
Obecna aplikacja ładuje lokalny `state_dict` z `strict=True`, ale bufor
kodowania pozycji nie należy do tego zapisu. Zatem plik może się wczytać mimo
niewłaściwego wariantu. W eksperymencie każdy model dostaje świeże
`deepcopy(default_cfg)` i jawną flagę, bez pobierania przez konstruktor.
Nie mutujemy wspólnej konfiguracji; kontrola po przebiegu to potwierdza.

Historyczne `pretrained=outdoor` w konfiguracji wstrzykniętego backendu
translacji nie wybiera wag i może pozostać w tekstowych szczegółach próby.
Rzeczywiste wagi identyfikują tutaj ścieżka, SHA-256, `checkpoint_variant`
i pełna `loftr_configuration` w raporcie, a nie to historyczne pole.
Obsługa jawnego wyboru wariantu Indoor New w aplikacji wymaga osobnej zmiany.
EfficientLoFTR i MatchAnything-ELoFTR są innymi modelami z dalszych ticketów,
nie plikami zamiennymi dla obecnego klasycznego LoFTR.

Nowe pliki pobrano z repozytorium `kornia/loftr` na Hugging Face. Zweryfikowano
sumy SHA-256 względem metadanych LFS; istniejący Outdoor ma tę samą sumę co
oficjalny plik. Wagi pozostają poza Git w `data/weights/loftr/`:

| Wariant | Bajty | SHA-256 |
| --- | --- | --- |
| outdoor | 46341978 | `21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec` |
| indoor | 46336731 | `d73c54720370ba0690cd477e38404a626e881292cc0be09a6801da0cc6f53198` |
| indoor_new | 46355053 | `be9ff88b323ec27889114719f668ae41aff7034b56a4c4acbd46b8b180b87ed3` |

Outdoor pozostaje w istniejącym katalogu:
`/home/rlew/projekty/tracker-import-20261008/trackers-windows-20261008/model_cache/torch/hub/checkpoints/loftr_outdoor.ckpt`.
Indoor i Indoor New są zapisane w
`/home/rlew/projekty/NEtCAT-viewer/data/weights/loftr/`.

## Warunki i stałe pary

Linux, `netcat`: Python 3.12.12, Torch 2.9.1+cu128, Kornia 0.8.2;
Deep na NVIDIA RTX 5090 32 GB, 4 wątki Torch/OMP i 1 OpenBLAS.
Wszystkie warianty mają identyczną normalizację wejścia, progi liczby dopasowań,
odporną agregację XY i pojedyncze końcowe renderowanie oryginałów.
Nie użyto ECC ani lokalnego konsensusu z REG-05. MOVIE_4 pomija źródłowe
klatki 1 i 2, pozostawiając 362 klatki; MOVIE_8 ma wszystkie 84 klatki.
Rozmiary original: odpowiednio 256×256 i 512×512 px. Sumy danych i pełne
ustawienia znajdują się w każdym `report.json`.

Pary są niezależnymi próbami, nawet gdy dany wariant odmawia pełnemu łańcuchowi.
XY oznacza ruch klatki przesuwanej na bazową: +X w prawo, +Y w dół.

| Film | Para bieżąca | Para źródłowa | Outdoor XY [px] | Indoor XY [px] | Indoor New XY [px] |
| --- | --- | --- | --- | --- | --- |
| MOVIE_4 | 1→2 | 3→4 | (22.372; 13.478) | (-103.637; -15.739) | (16.236; 8.146) |
| MOVIE_4 | 31→32 | 33→34 | (-22.941; -31.578) | (24.681; 0.135) | odmowa |
| MOVIE_4 | 118→119 | 120→121 | (31.435; 22.284) | (31.317; 23.728) | (32.335; 22.451) |
| MOVIE_4 | 29→30 | 31→32 | (0.679; 7.235) | (24.023; 0.294) | odmowa |
| MOVIE_4 | 35→36 | 37→38 | (0.094; -5.303) | (-7.634; 0.215) | (-23.425; 0.308) |
| MOVIE_4 | 44→45 | 46→47 | (23.387; 8.111) | (-40.011; 8.113) | (15.570; -0.073) |
| MOVIE_4 | 45→46 | 47→48 | (0.364; 17.277) | (-23.985; -8.078) | (0.175; 16.522) |
| MOVIE_4 | 61→62 | 63→64 | (-0.341; -0.798) | (-0.112; 0.190) | (7.994; 7.413) |
| MOVIE_4 | 94→95 | 96→97 | (38.222; 9.234) | (32.885; 8.729) | (32.209; 8.844) |
| MOVIE_4 | 95→96 | 97→98 | (-15.461; -6.952) | (-23.342; -8.288) | (-23.381; -8.971) |
| MOVIE_4 | 96→97 | 98→99 | (-15.651; -6.577) | (-16.024; -0.889) | (-15.841; -7.384) |
| MOVIE_8 | 1→2 | 1→2 | (15.108; 0.428) | (15.471; 0.485) | (15.599; 0.287) |
| MOVIE_8 | 16→17 | 16→17 | (-24.514; -32.170) | (-31.770; -31.934) | (-24.151; -32.126) |
| MOVIE_8 | 56→57 | 56→57 | (-39.609; 7.039) | (-39.895; 7.945) | (-40.009; 7.873) |

Przykład rozbieżności: MOVIE_4 bieżąca 1→2 (źródłowa 3→4) daje Outdoor
(+22,372; +13,478), a Indoor (−103,637; −15,739) px. To powód do kontroli
obrazów, nie podstawa do automatycznego uznania którejś trajektorii za lepszą.
Indoor New odmówił bieżącej 31→32 (6 dopasowań zamiast wymaganych 8)
i 29→30 (2 wektory zgodne zamiast wymaganych 4). Nie podstawiano innej metody.

## Pełne filmy

| Wariant | Film | Wynik | Aligned H × W | Estymacja i render [s] | Eksport MPP [s] |
| --- | --- | --- | --- | --- | --- |
| outdoor | MOVIE_4 | kompletny | 346 × 400 | 5.508 | 3.153 |
| outdoor | MOVIE_8 | kompletny | 743 × 763 | 7.883 | 4.278 |
| indoor | MOVIE_4 | kompletny | 478 × 1391 | 7.666 | 19.771 |
| indoor | MOVIE_8 | kompletny | 737 × 1258 | 10.431 | 7.424 |
| indoor_new | MOVIE_4 | odmowa bieżącej 2→3 | — | 0.475 | — |
| indoor_new | MOVIE_8 | kompletny | 734 × 1074 | 5.390 | 3.440 |

Odmowa Indoor New w pełnym MOVIE_4 dotyczy źródłowej pary 4→5: tylko
2 dopasowania zamiast wymaganych 8. Nie zapisano niepełnego aligned.
Czasy obejmują ładowanie modelu; nie są izolowanym benchmarkiem. Czas do odmowy
nie oznacza przetworzenia całego filmu. Próby na GPU 32 GB nie są odbiorem 8 GB.

## Oglądanie wyników

Pięć kompletnych MPP z dodatkami metadanych znajduje się w katalogu:

`/home/rlew/projekty/NEtCAT-viewer/data/loftr-checkpoint-comparison-20261031/`

Wybierz podkatalog `outdoor`, `indoor` albo `indoor_new`, potem
`movie_4-full` lub `movie_8-full`, a w nim
`deep_matcher_translation-aligned.mpp`. Indoor New nie ma pełnego MOVIE_4.
Przenosząc wynik, zachowaj towarzyszący `.mpp.stmviewer.json` oraz informację,
z którego katalogu wariantu pochodzi film; sama nazwa metody MPP to Deep Matcher.

Otwórz Outdoor i Indoor w dwóch oknach STM Viewera. Ustaw tę samą klatkę,
gamma 1, proporcje pikselowe i porównywalne powiększenie struktur próbki.
Inny rozmiar płótna nie oznacza innej skali próbek; samo „dopasuj do okna”
może dać różne powiększenie. Porównaj stałe problematyczne pary MOVIE_4 oraz
początek i dalszą część obu filmów. Zapisz lepiej/podobnie/gorzej/niejednoznacznie
w co najmniej trzech rozpoznawalnych obszarach, osobno od tearingu.

Do własnej próby zwykłego Indoor można wskazać
`data/weights/loftr/loftr_indoor.ckpt` w istniejącym polu wag Deep Matcher.
Nie wybieraj tam `loftr_indoor_ds_new.ckpt` jako sposobu odtworzenia tego
porównania — obecne GUI nie ustawia wymaganej konfiguracji. Wynik Indoor New
można już oglądać przez przygotowany MPP albo odtworzyć poniższym skryptem.

## Odtwarzanie i sprawdzenia

Skrypt [checkpoint_trial.py](../../../tests/stmviewer/diagnostics/checkpoint_trial.py)
wykorzystuje publiczne API Viewera i istniejący runner prób. Zmienia tylko
konfigurację konstruktora w procesie eksperymentu; aplikacja i jej domyślne
wagi pozostają bez zmian. Wczytuje checkpoint przez `weights_only=True`,
kontroluje brak mutacji konfiguracji i blokuje pobieranie modeli w trakcie próby.
Katalog wynikowy musi być nowy.

Przykład w katalogu Viewer, po aktywowaniu `netcat`:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4 PYTHONPATH=. \
python tests/stmviewer/diagnostics/checkpoint_trial.py \
  data/MOVIE_4.mpp /tmp/nowa-proba-indoor \
  --variant indoor --weights data/weights/loftr/loftr_indoor.ckpt \
  --device cuda --drop-first 2 --export
```

Dla Indoor New wybierz `--variant indoor_new` i plik `loftr_indoor_ds_new.ckpt`.
Dla MOVIE_8 pomiń `--drop-first 2`. Zamiast `--export` można podać np.
`--pair 30 --pair 36`, aby zbadać bieżące 29→30 i 35→36 niezależnie od całej serii.
Kod wyjścia 1 przy odmowie jest wynikiem próby, a nie ukrytym sukcesem.

Wykonano 42 próby par i 6 prób pełnych serii na rzeczywistych wagach;
sprawdzono uruchamianie CLI oraz Ruff. Read-only przegląd harnessu potwierdził
rozdzielenie konfiguracji modeli i zachowanie dotychczasowego przetwarzania.
Nie zmieniano kodu aplikacji, dlatego nie powtarzano pełnego zestawu jej testów.
Ponowny odczyt pięciu MPP+metadanych: **5/5 PASS**. Sprawdzono metadane
wszystkich 976 klatek, w tym geometrię, XY, pochodzenie, odniesienie i status.
Dla pierwszej, środkowej i ostatniej klatki każdego filmu (15 klatek) wszystkie
wartości i maska NaN są dokładnie zgodne z ponownym przesunięciem oryginału
przez SciPy z interpolacją liniową. Raport: `/tmp/checkpoint-roundtrip.json`.
To potwierdzenie zapisu, a nie poprawności fizycznego dopasowania.

Raporty, XY, statusy i pliki są w powyższym katalogu danych, poza Git.
Nie wykonano ręcznego odbioru jakości, Windows ani VLC.
