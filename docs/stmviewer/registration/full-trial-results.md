# REG-07 — rzeczywiste pełne próby i wierne odtwarzanie

Wykonano 2026-11-01, automatycznie w środowisku `netcat` na Linuksie.
**Wynik funkcjonalny:** lekkie dokumenty zachowują pełne wyniki, odmowy oraz
ręczne korekty; ponowny podgląd zgadza się z pikselami aktywnego aligned.
Ocena wizualna użytkownika i VLC pozostają niewykonane przez agenta.
REG-07 nie zmienia algorytmów ani nie rozstrzyga, które XY opisuje fizyczny dryf.
REG-06 pozostaje odłożony; niezależnej oceny jakości nie ma.

## Warunki i odtwarzalność

- Kod roboczy REG-07 względem `bb06220bdc8f132ebdcef0bc9ac8d045f39ef68e`;
  dokumenty zapisują `code_revision` i `code_dirty: true`. Finalny commit
  wdrożenia podaje przekazanie ticketu. Nie jest to deklaracja uruchomienia
  czystego starego commita.
- Python 3.12.12, Torch 2.9.1+cu128, Kornia 0.8.2, NVIDIA RTX 5090 32 GB.
  Każda metoda/film uruchomiona w świeżym procesie, bez pobierania danych lub wag.
- Ten sam lokalny checkpoint **LoFTR Outdoor**:
  `21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec` (SHA-256).
  Pełna ścieżka, ustawienia backendu i obu etapów hybrydy są w dokumentach.
- MOVIE_4: 362 klatki 256×256 po pominięciu źródłowych 1 i 2;
  SHA-256 pliku `9d066676a3f947ed53610438051537eb3b30288aadc11d774ec52e509f31f961`.
  MOVIE_8: 84 klatki 512×512;
  SHA-256 `a06ab5d34250ca564b11eb9da4e9ea65131b80d2a2e3ceaf09f0709569cdbde7`.
  Skróty źródeł po próbach pozostały niezmienione.
- Artefakty: `/tmp/stmviewer-reg07/movie{4,8}-{deep,ecc,local}/`;
  plik `trial.stmtrial.json` to zapisana próba, `report.json` zawiera pomiary.
  Katalogi `movie{4,8}-comparison/` zawierają osobne pomiary odczytu na CPU.
  Katalogi `*-initial-harness` są nieudanymi wczesnymi uruchomieniami samego
  skryptu (zły typ parametru białego tła AVI), nie końcowymi wynikami odbioru.
- Po doprecyzowaniu schematu źródeł dodano pole `origin_source`. Zachowane
  wyniki liczbowe zapisano ponownie przez publiczne API; porównano wszystkie
  dotychczasowe pola tożsamości, skróty i geometrię. Modelu nie przeliczano
  z tego powodu. Porównanie CPU i poniższe rozmiary dotyczą końcowych dokumentów.

## Pełne przebiegi

Czas obejmuje wczytanie modelu, estymację i renderowanie aligned; nie obejmuje
późniejszego zapisu dokumentu ani eksportów. RSS jest szczytem procesu do
końca rejestracji, obejmuje również oryginały i biblioteki.

| Film | Metoda | Wynik | Czas [s] | RSS [GiB] | Dokument [KiB] |
| --- | --- | --- | ---: | ---: | ---: |
| MOVIE_4 | Deep Matcher Outdoor | pełny: 362 klatek | 5.48 | 2.05 | 245.8 |
| MOVIE_4 | Deep Matcher + ECC | pełny: 362 klatek | 9.18 | 2.07 | 614.1 |
| MOVIE_4 | Deep + lokalny konsensus | odmowa 2→3 | 0.62 | 1.67 | 169.3 |
| MOVIE_8 | Deep Matcher Outdoor | pełny: 84 klatek | 7.87 | 1.99 | 58.2 |
| MOVIE_8 | Deep Matcher + ECC | pełny: 84 klatek | 9.40 | 2.03 | 143.2 |
| MOVIE_8 | Deep + lokalny konsensus | odmowa 1→2 | 0.65 | 1.66 | 44.0 |

Lokalny konsensus odmówił MOVIE_4 na **bieżącej parze 2→3**, czyli źródłowej
4→5: dwa fragmenty, jeden rząd, dwie kolumny. Dokument zachował odniesienie,
pierwszą udaną parę, dokładny start Deep oraz diagnozę odmowy następnej pary.
MOVIE_8 zatrzymał się na 1→2: jeden fragment, jeden rząd i jedna kolumna.
Oba niekompletne dokumenty zapisały się i odczytały poprawnie. Nie pominięto
żadnej trudnej pary i nie włączono innej metody, aby uzyskać pełny film.

W pełnych Deep/Deep+ECC **każdą** klatkę odtworzono z zapisanych XY i oryginału.
Próbki float64, NaN i prostokąt oryginalnego pola są dokładnie zgodne z
materializowanym aligned. Zapis i odczyt pojedynczego dokumentu zajmowały
około 0,15–0,26 s. Statusy odziedziczone po niepewnej parze nie są niezależnym
orzeczeniem o jakości wszystkich późniejszych klatek.

## Odczyt bez modelu i pamięć porównania

Świeże procesy miały zablokowany import `torch` i `kornia`. Wczytano A=Deep
oraz B=Deep+ECC, odtworzono wszystkie klatki obu wyników we wspólnym płótnie,
a następnie dziesięć razy ponownie odczytano dokumenty i przełączono wybrane
klatki. Bez dostępu do wag, inferencji i pełnych stosów aligned w porównaniu.

| Film | Odtworzone obrazy | Odczyt + pełny przebieg A/B | Szczyt RSS (`resource`) | Zmiana RSS po 10 odczytach (`psutil`) |
| --- | ---: | ---: | ---: | ---: |
| MOVIE_4 | 724 | 1.69 s | 254.9 MiB | 3.4 MiB |
| MOVIE_8 | 168 | 1.38 s | 241.3 MiB | 1.3 MiB |

Są to pomiary funkcji porównania, nie całej sesji GUI z wcześniej utworzonym
aligned. Osobny test 200-klatkowej serii ogranicza dodatkową pamięć renderera
do poniżej 8 MiB szczytu i 2 MiB po zwolnieniu obrazów. Renderer odtwarza
jedną klatkę na żądanie; wspólne odniesienie stanowi pierwszy zachowany oryginał.
To nie skaluje ani ponownie nie estymuje przesunięć.

Największy zmierzony RSS całego procesu z modelem, dwiema korektami i eksportem
wyniósł **2,90 GiB**. Porównanie mieści się w zakładanych 16 GB wolnego RAM.
Nie jest to certyfikat odbioru na fizycznym komputerze 16 GB ani karcie 8 GB;
Torch raportował maksymalnie około 0,92 GiB przydzielonych i 1,60 GiB
zarezerwowanych danych CUDA, co nie obejmuje całkowitego zajęcia VRAM.

## Korekty ręczne i eksporty

Dla obu pełnych Deep+ECC wykonano kontrolne korekty **+1 X** na pierwszej
wskazanej parze i **−1 Y** na drugiej. MOVIE_4: 29→30 i 35→36;
MOVIE_8: 15→16 i 55→56. Są to celowe zmiany do testu funkcji, nie postulowana
poprawa fizycznego dopasowania. Wynik bazowy i oryginały pozostały bez zmian.

- Zapis/odczyt zatwierdzonej próby pary zachował start, sumę ruchów, końcowe XY,
  opis punktu startu i brak automatycznej oceny jakości.
- Zapis/odczyt pełnego wyniku z dwiema korektami zachował bazę, oba nadpisania
  i poprawne przesunięcie wszystkich dalszych klatek. Renderowane wartości
  odpowiadają poprawionemu aligned. Pliki: `manual-pair.stmtrial.json`
  i `manual-series.stmtrial.json` w obu katalogach `*-ecc`.
- Pełne **niekorygowane Deep+ECC** zapisano do MPP+JSON i ponownie odczytano:
  wszystkie wartości, maski ważności, skumulowane XY, geometria i pochodzenie
  odpowiadają wynikowi. MOVIE_4: 362 klatki; MOVIE_8: 84 klatki.
- Pełne AVI FFV1 z obu wyników odczytano OpenCV/FFmpeg: dokładna zgodność
  wszystkich rastrów uint8, liczby klatek i 7 FPS. MOVIE_4: 412×330,
  MOVIE_8: 786×754; białe tło braków, proporcje pikselowe, gamma 1.
  To automatyczna weryfikacja dekodera; **VLC i oględziny GUI są do odbioru**.

## Stałe i dodatkowe pary do oględzin

Różnica to **XY Deep+ECC minus XY Deep** dla pary, w pikselach oryginału.
Nie jest błędem względem prawdy pomiarowej. Pary dodatkowe nie służyły tu
strojeniu ustawień; pozostają nowymi punktami do ręcznego obejrzenia na tych
samych filmach, a nie nowym niezależnym zbiorem danych.

| Film | Para bieżąca | ΔX [px] | ΔY [px] | Długość różnicy [px] | Lista |
| --- | --- | ---: | ---: | ---: | --- |
| MOVIE_4 | 1→2 | -2.828 | -1.813 | 3.359 | stała |
| MOVIE_4 | 29→30 | -0.265 | -1.948 | 1.966 | stała |
| MOVIE_4 | 31→32 | +0.117 | -0.880 | 0.888 | stała |
| MOVIE_4 | 35→36 | -0.882 | +0.867 | 1.237 | stała |
| MOVIE_4 | 44→45 | -9.236 | +4.394 | 10.228 | stała |
| MOVIE_4 | 45→46 | +3.097 | -0.061 | 3.098 | stała |
| MOVIE_4 | 61→62 | -1.209 | -0.005 | 1.209 | stała |
| MOVIE_4 | 94→95 | -4.289 | -0.846 | 4.372 | stała |
| MOVIE_4 | 95→96 | -3.468 | -0.642 | 3.527 | stała |
| MOVIE_4 | 96→97 | +0.513 | +0.415 | 0.660 | stała |
| MOVIE_4 | 118→119 | +0.321 | +0.803 | 0.865 | stała |
| MOVIE_4 | 151→152 | -1.106 | +0.102 | 1.111 | dodatkowa |
| MOVIE_4 | 250→251 | -0.592 | -0.368 | 0.697 | dodatkowa |
| MOVIE_4 | 350→351 | -0.112 | +0.197 | 0.226 | dodatkowa |
| MOVIE_8 | 1→2 | -0.827 | +0.162 | 0.842 | stała |
| MOVIE_8 | 16→17 | -2.252 | -0.138 | 2.256 | stała |
| MOVIE_8 | 56→57 | +0.094 | -1.621 | 1.623 | stała |
| MOVIE_8 | 40→41 | +2.490 | -0.926 | 2.656 | dodatkowa |
| MOVIE_8 | 80→81 | -0.645 | +1.871 | 1.979 | dodatkowa |

Każda para pozostaje **niejednoznaczna bez oceny struktur przez użytkownika**.
W szczególności mała różnica dwóch metod nie potwierdza poprawności obu;
duża różnica nie wskazuje automatycznie lepszej metody. Resztkowy tearing
należy ocenić oddzielnie. Obowiązuje dotychczasowy wybór użytkownika:
Outdoor pozostaje bazą, lokalny konsensus wariantem eksperymentalnym.

## Powtórzenie

W aktywnym `netcat`, z katalogu repozytorium (nowy katalog wyników):

```bash
python tests/stmviewer/diagnostics/full_trial_validation.py run data/MOVIE_4.mpp /tmp/reg07-repeat-movie4-ecc --drop-first 2 --method deep_matcher_ecc --weights /ścieżka/do/loftr_outdoor.ckpt --export --manual
python tests/stmviewer/diagnostics/full_trial_validation.py compare data/MOVIE_4.mpp /tmp/stmviewer-reg07/movie4-deep/trial.stmtrial.json /tmp/stmviewer-reg07/movie4-ecc/trial.stmtrial.json /tmp/reg07-repeat-comparison --drop-first 2
```

Skrypt uruchamiaj z `PYTHONPATH=.:tests/stmviewer` i `OPENBLAS_NUM_THREADS=1`.
Dla MOVIE_8 pomiń `--drop-first 2`. Metody: `deep_matcher_translation`,
`deep_matcher_ecc`, `deep_local_consensus`. Każdy przebieg modelu uruchom osobno.
Skrypt pomiarowy używa linuksowego `resource` i opcjonalnego `psutil`;
nie dodaje tych wymagań do pracy samego porównania w GUI.
