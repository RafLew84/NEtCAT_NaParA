# REG-04 — rzeczywiste próby modelu i filmów

Data: 2026-10-31. Implementacja REG-04 po bazie `29d7fc9`.
Są to automatyczne próby publicznych funkcji aplikacji. Nie obejmują odbioru
wizualnego użytkownika, odtworzenia AVI w VLC ani stanowiska Windows.
Wyniki score i wymiary aligned nie są miarą fizycznej poprawności dryfu.

## Stanowisko i odtwarzalność

- Linux, środowisko `netcat`, Python 3.12; Torch 2.9.1+cu128, Kornia 0.8.2, OpenCV 4.11.0.
- NVIDIA GeForce RTX 5090, 32 GiB VRAM. Dostęp CUDA wymagał uruchomienia poza sandboxem.
- Lokalne wagi LoFTR outdoor: SHA-256 `21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec`.
- W narzędziu zablokowano pobieranie przez Torch i `urlopen`; każde wykonanie korzystało z lokalnych wag.
- Ustawienia Deep identyczne w bazie i hybrydzie. ECC v1: 100 iteracji, epsilon 1e-6, filtr 5, translacja.
- ECC otrzymywał start dokładnie z tej próby Deep; pełna lekka diagnostyka jest w raportach JSON.
- Dane i duże wyniki są w `/tmp/stmviewer-reg04-trials/`, poza Git; są odtwarzalne poniższym narzędziem.

```bash
PYTHONPATH=. python tests/stmviewer/diagnostics/deep_ecc_trial.py \
  data/MOVIE_4.mpp /tmp/nowa-proba-reg04 \
  --weights /sciezka/do/loftr_outdoor.ckpt --device cuda --drop-first 2 --export
```

Bez `--pair` narzędzie rejestruje całą serię; błąd kończy próbę tej metody,
bez zastępowania inną metodą lub pomijania pary. Powtarzane `--pair` wybiera
niezależne próby par według numeru klatki przesuwanej po usunięciu początku.
`--method` może ograniczyć wariant, a `--device cpu` uruchamia CPU.

## Znane wzorce

Generator i kroki GUI: [instrukcja](deep-ecc-manual.md).
Wygenerowane MPP odczytano ponownie i potwierdzono dokładną zgodność wartości
oraz orientacji ze źródłowymi tablicami. Wzorzec translacji ma niekwadratowe
wymiary i prawdziwe granice pola widzenia, bez zawijania.

| Urządzenie | Para | Znane XY sceny | Start Deep | Koniec ECC |
| --- | --- | --- | --- | --- |
| CPU | 1→2 | (22.4, −13.25) | (22.285, -13.359) | (22.392, -13.278) |
| CPU | 2→3 | (−41, 24.6) | (-41.025, 24.517) | (-41.004, 24.615) |
| CUDA | 1→2 | (22.4, −13.25) | (22.285, -13.359) | (22.392, -13.276) |
| CUDA | 2→3 | (−41, 24.6) | (-41.025, 24.517) | (-41.004, 24.615) |

Obie pary przeszły na CPU i CUDA. Różnice są mniejsze niż 0,03 px na współrzędną
na końcu ECC. To sprawdzenie wzorca, nie dokładności rzeczywistego STM.

Wzorzec **okresowy**: rzeczywisty Deep odmówił obu parom (odpowiednio 3 i 1
dopasowania przy wymaganych 8). Hybryda zgłosiła etap Deep, bez uruchomienia
zastępczego dopasowania. Nie uzyskano gotowego wyniku ECC tego wzorca.

Wzorzec **nieruchomych pasów**: oba przebiegi zakończyły się, lecz ECC pogorszył
zgodność ze znanym przesunięciem sceny. Dla pary 1→2 start Deep wynosił
(22.265, −13.426), a ECC (21.581, −27.479); dla 2→3 odpowiednio
(−41.027, 24.506) i (−38.906, 32.497). Score ECC wyniósł 0.090 i 0.128.
Wynik hybrydy ma status wymagający oceny. Ten przykład uzasadnia porównywanie
startu i końca oraz pozostawienie samego Deep jako osobnego wariantu.

## Pełne filmy

| Seria | Metoda | Wynik | Aligned H × W | Czas [s] | Szczyt alokacji Torch CUDA [MiB] |
| --- | --- | --- | --- | --- | --- |
| MOVIE_4, źródłowe 3–364 (362 klatki) | Deep | kompletny | 346 × 400 | 10.05 | 330.5 |
| MOVIE_4, źródłowe 3–364 (362 klatki) | Deep→ECC | kompletny | 329 × 412 | 14.42 | 331.0 |
| MOVIE_8 (84 klatki) | Deep | kompletny | 743 × 763 | 12.35 | 936.5 |
| MOVIE_8 (84 klatki) | Deep→ECC | kompletny | 754 × 785 | 13.89 | 936.4 |

Czas obejmuje wczytanie modelu, estymację, renderowanie oraz zapis MPP+JSON;
nie jest izolowanym benchmarkiem algorytmu. Pamięć oznacza tylko alokacje
Torch na CUDA, nie całkowite zużycie VRAM procesu ani RAM komputera.
Nie wykonywano cichego fallbacku ani pomijania par. Wszystkie cztery MPP
odczytano ponownie: poprawna liczba klatek, nazwa/wersja metody, status, XY,
geometria i obecność brakujących próbek. Zgodność wartości małych wyników
obejmuje osobny zestaw testów REG-04; powyższy odczyt dużych filmów sprawdzał
metadane i próbki brakujące, nie porównywał każdej wartości z tablicą w RAM.

Filmy do lokalnej oceny:

- `/tmp/stmviewer-reg04-trials/movie4-full/deep_matcher_translation-aligned.mpp`
- `/tmp/stmviewer-reg04-trials/movie4-full/deep_matcher_ecc-aligned.mpp`
- `/tmp/stmviewer-reg04-trials/movie8-full/deep_matcher_translation-aligned.mpp`
- `/tmp/stmviewer-reg04-trials/movie8-full/deep_matcher_ecc-aligned.mpp`

Obok każdego pozostaje wymagany plik `.stmviewer.json`.

## Wskazane pary pomiarów

Wszystkie wskazane pary policzono samym Deep i hybrydą. Tabela pokazuje
dokładny start i koniec jednej próby hybrydy, w pikselach original.
Są to wyniki do obejrzenia, bez automatycznego werdyktu poprawy.

| Film | Para źródłowa | Para bieżąca | Start Deep XY | Koniec ECC XY | Poprawka XY |
| --- | --- | --- | --- | --- | --- |
| MOVIE_4 | 3→4 | 1→2 | (22.372, 13.478) | (19.544, 11.665) | (-2.828, -1.813) |
| MOVIE_4 | 33→34 | 31→32 | (-22.941, -31.578) | (-22.824, -32.458) | (0.117, -0.880) |
| MOVIE_4 | 120→121 | 118→119 | (31.435, 22.284) | (31.756, 23.087) | (0.321, 0.803) |
| MOVIE_4 | 31→32 | 29→30 | (0.679, 7.235) | (0.414, 5.287) | (-0.265, -1.948) |
| MOVIE_4 | 37→38 | 35→36 | (0.094, -5.303) | (-0.788, -4.436) | (-0.882, 0.867) |
| MOVIE_4 | 46→47 | 44→45 | (23.387, 8.111) | (14.151, 12.505) | (-9.236, 4.394) |
| MOVIE_4 | 47→48 | 45→46 | (0.364, 17.277) | (3.462, 17.217) | (3.097, -0.061) |
| MOVIE_4 | 63→64 | 61→62 | (-0.341, -0.798) | (-1.551, -0.803) | (-1.209, -0.005) |
| MOVIE_4 | 96→97 | 94→95 | (38.222, 9.234) | (33.933, 8.387) | (-4.289, -0.846) |
| MOVIE_4 | 97→98 | 95→96 | (-15.461, -6.952) | (-18.929, -7.594) | (-3.468, -0.642) |
| MOVIE_4 | 98→99 | 96→97 | (-15.651, -6.577) | (-15.138, -6.163) | (0.513, 0.415) |
| MOVIE_8 | 1→2 | 1→2 | (15.108, 0.428) | (14.281, 0.590) | (-0.827, 0.162) |
| MOVIE_8 | 16→17 | 16→17 | (-24.514, -32.170) | (-26.766, -32.308) | (-2.252, -0.138) |
| MOVIE_8 | 56→57 | 56→57 | (-39.609, 7.039) | (-39.515, 5.419) | (0.094, -1.621) |

Źródłowe 46→47 MOVIE_4 (bieżące 44→45) otrzymuje poprawkę około
(−9,24; +4,39) px. Warto obejrzeć ją szczególnie uważnie; wielkość zmiany
nie rozstrzyga, który wynik opisuje próbkę lepiej.

## Ograniczenie zbieżności ECC

OpenCV może zwrócić wynik po wyczerpaniu limitu 100 iteracji i nie przekazuje
osobnej flagi osiągnięcia tolerancji. Pomyślny powrót backendu oznacza otrzymanie
skończonego XY, nie dowód zbieżności ani poprawy dopasowania. Jawny wyjątek
ECC kończy próbę; wynik bez wyjątku nadal wymaga oceny wizualnej.

## Pozostały odbiór

- Ocena struktur i tearing w GUI, pełne odtworzenie oraz decyzja użytkownika: **niewykonane**.
- VLC dla AVI oraz Windows: **niewykonane w tej próbie**.
- Kontrolowana odmowa/anulowanie i eksport małego wzorca: instrukcja oraz wyniki testów w karcie REG-04.
- Status akceptacji należy do [karty REG-04](reviews/REG-04.md), nie wynika z powyższych score.
