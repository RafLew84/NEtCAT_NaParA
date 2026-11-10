# Przygotowanie wspólnego wejścia i kontroli — issue 14

Data: 2026-10-23. Przygotowano odtwarzalny zestaw dla prób 15–22.
Nie uruchomiono algorytmu domenowego ani treningu i nie wybrano metody.
Kod: [stmdomains/experiments](../../stmdomains/experiments/prepare.py).
[Protokół](experiment-input-protocol.md) określa wejście, format wyników,
miary i podglądy kolejnych porównań.

## Wynik

Lokalny pakiet, poza Git:
`/home/rlew/projekty/NEtCAT-domains/.scratch/unsupervised-input/`.
Otworzyć `index.html`: pełne pole, centra i osobno włączana referencja/prawda
kontrolna. Galeria nie pokazuje predykcji domen. Dla kolejnej metody przekazać
wyłącznie podkatalog `analysis/`; `evaluation/` pozostaje do późniejszej oceny.

| Sprawdzenie | Wynik |
| --- | --- |
| MPP i zapis MolTrack | SHA-256 identyczne z audytem; 268 klatek 256×256, kolejność 0–267 |
| Zakres pilotażu | 24 pełne pola: 1, 50, 100, 150, 200 oraz 250–268 |
| Oznaczenia w pilocie | 6730, w tym 298 na klatce 255 bez ręcznej referencji |
| Oznaczenia częściowo poza kadrem | Zachowano 1 bbox z poprawnym środkiem; nie przycinano go |
| Powrót bboxów raw → expanded | Maksymalny błąd 0 px dla wszystkich 6730 oznaczeń pilotażu |
| Geometria rejestracji | Płótno 480×408, padding LTRB 224/139/0/13; wejście raw bez paddingu |
| Kontrole | 22 przypadki × 6 ziaren = 132 pary obraz/punkty z osobną prawdą |
| Referencje | 18 klatek, 54 konserwatywne wnętrza, numer 255 nadal bez anotacji |
| Powiązanie PNG z pomiarem | Wszystkie 18 czystych PNG odtworzone piksel w piksel z MPP/rejestracji |
| Zgodność z poprzednim audytem | Wszystkie 18 map kolorów i instancji identyczne z poprzednimi NPZ |
| Powtarzalność i brak wpływu referencji | Wszystkie 157 plików `analysis/` identyczne bajt w bajt po ponownym przygotowaniu bez referencji |
| Odczyt gotowego zestawu | Wszystkie 156 próbek przechodzą walidację i kontrolę hashy |

Źródła:

- `MOVIE_23raw_TTMAPP_I_AU111.MPP`:
  `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`;
- `detection_full.moltrack.json`:
  `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.

W całym źródle jest 52 494 oznaczeń, bez wykluczeń przez położenie środka.
Numery klatek 64–68 nie mają detekcji; nie uznano ich za podłoże lub nieporządek.
Różnica daty pliku MPP względem sesji nie zmienia identyfikacji: adapter
badawczy wymaga dokładnie audytowanych sum kontrolnych. Nie zmienia reguł
interaktywnego importera. Zachowano informację o niskiej pewności zapisanej
rejestracji; niczego nie liczono ponownie.

## Odtworzenie

W worktree zawierającym ten commit, z lokalnego środowiska `netcat`:

```bash
/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python \
  -m stmdomains.experiments.prepare \
  --mpp /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  --session /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/detection_full.moltrack.json \
  --review /home/rlew/projekty/NEtCAT-domains/data/ttmapp_frames_250_268_domain_review \
  --out .scratch/unsupervised-input-repeat
```

Katalog docelowy musi być nowy. Pominięcie `--review` odtwarza identyczne
wejście analizy bez referencji; to sprawdzenie wykonano. `--full-series`
eksportuje wszystkie 268 klatek do późniejszego pomiaru zakwalifikowanych
kandydatów. W tym zadaniu nie wykonano pełnego eksportu ani analizy całej serii;
czytnik i walidacja źródła obejmowały wszystkie klatki.

Przygotowanie końcowego pilotażu wraz z referencjami zajęło **5,89 s**, ze
szczytowym RSS **445 916 KiB** (około 435,5 MiB), zmierzonym przez
`/usr/bin/time`. Powtórzenie bez referencji: 3,82 s, 445 808 KiB. To pomiary
lokalnego przygotowania, nie koszt detektora ani gwarancja wydajności.
Pakiet z podglądami i zapisem kontroli weryfikacyjnych ma około 61,5 MB.
Środowisko: NumPy 2.2.5, SciPy 1.15.2, Pillow 11.2.1; dokładne wersje
i hashe plików generatora są w `audit.json`.

## Wykonane sprawdzenia

```bash
/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python \
  -m pytest -q tests/stmdomains/test_experiment_inputs.py
```

**35 testów przeszło.** Obejmują wszystkie kontrole, rozdzielenie domeny,
typu i orientacji, ubytki detekcji bez zmiany obrazu, przeskalowanie i crop,
bboxy przy brzegu, odrzucanie błędnej geometrii/etykiet na wejściu, kontrolę
hashy i format wyniku. Miary par rozróżniają scalenie, podział oraz odmowę;
odrzucenie wszystkiego daje zerowe pokrycie i nieokreślone błędy par.

Na realnych danych wykonano dodatkowo sprawdzenia z tabeli, porównanie
artefaktów obu przygotowań oraz zgodności wszystkich map z wcześniejszym
audytem. Obejrzano statyczny arkusz rzeczywistych klatek i kontroli z
nakładkami referencji. Sprawdzono pliki podglądów oraz składnię JavaScript
w Qt QJSEngine. Interakcji DOM w przeglądarce i natywnego GUI aplikacji
nie testowano; nie były przedmiotem tego przygotowania.

## Ograniczenia i następny krok

- Adapter celowo obsługuje tylko dokładnie audytowany zestaw TTMAPP.
  Inne źródło wymaga osobnego audytu i jawnej zmiany protokołu.
- Jedna akwizycja i już używane referencje nie potwierdzają generalizacji.
  Nie znamy prawdy poza wnętrzami ani dokładnych granic, kątów i pokrycia.
- Syntetyka sprawdza zachowanie na jawnych przypadkach, nie odwzorowuje
  całej fizyki STM. Ziarna oceny nie zastępują niezależnej akwizycji.
- Wzorzec wyników i podstawowy walidator nie implementują metody domenowej,
  produkcyjnych statystyk ani zapisu `.stmdomains`. Predykcje i ich
  niezmienność po usunięciu referencji sprawdzą właściwe próby metod.
- Nie korzystano z GPU, nie pobierano modeli i nie zmieniano wspólnych modułów.

Issue 14 kończy przygotowanie i odblokowuje 15, 16, 17, 18 oraz 20.
Zalecany następny eksperyment: [15 — lokalne otoczenie molekuł](issues/15-local-neighborhood-domains.md).
Protokół jakości 04 i odbiór metod 13 nadal są otwarte.
