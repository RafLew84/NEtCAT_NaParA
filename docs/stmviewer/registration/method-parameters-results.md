# REG-15 — wyniki ograniczonej próby parametrów

Data: 2026-11-03. [Ticket](issues/15-method-parameters.md),
[instrukcja ręczna](method-parameters-manual.md), [testy](reviews/REG-15.md).

Celem było sprawdzenie wpływu jawnych ustawień i odtwarzalności wyniku.
Nie dobierano automatycznie najlepszego zestawu ani nie potwierdzono
dokładności fizycznego dryfu STM. Wykonano 24 próby: sześć konfiguracji
na czterech parach. Wszystkie zachowały bajty wejściowych obrazów.

## Dane i odtworzenie

MOVIE_4 po usunięciu pierwszych dwóch klatek: bieżące 1→2, 29→30,
160→161, czyli źródłowe 3→4, 31→32, 162→163. MOVIE_8: 1→2.
AKAZE pracował na CPU, LightGlue na CUDA, z istniejącymi lokalnymi wagami.

```bash
conda activate netcat
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/method_parameters_trial.py --device cuda
```

Lokalny wynik: data/registration-reg15/attempts.json oraz 24 obrazy PNG.
JSON zawiera pełne profile, identyfikatory modeli, przygotowanie, skróty
obrazów, numery źródłowe, XY albo odmowę, diagnostykę i czas.
W PNG od lewej: klatka bazowa, przesuwana, nakładka bez dopasowania
oraz — tylko przy uzyskanym wyniku — nakładka po dopasowaniu.
Dane są lokalne i nie trafiają do Git.

## Wyniki

Każdy zmieniony wariant różni się jednym ustawieniem od domyślnego.
Percentyle oznaczają 1/99 przy pozostałych ustawieniach domyślnych.
Tolerancja konsensusu wynosi 2 px original we wszystkich 24 próbach.

| Konfiguracja | Wyniki / 4 pary | MOVIE_4 160→161: XY [px] | MOVIE_8 1→2: XY [px] |
| --- | ---: | --- | --- |
| AKAZE domyślne | 0/4 | odmowa | odmowa |
| AKAZE próg 0,0001 | 2/4 | −2,77; +3,26 | +12,82; +0,41 |
| AKAZE percentyle | 2/4 | −3,52; +4,28 | +13,96; +0,67 |
| LightGlue domyślne | 2/4 | −2; +5 | +14; +1 |
| LightGlue próg dopasowań 0,05 | 2/4 | −2; +5 | +13; +1 |
| LightGlue percentyle | 2/4 | −1; +5 | +14; 0 |

**MOVIE_4 1→2 i 29→30 zakończyły się odmową we wszystkich wariantach.**
Zmiana progu LightGlue nie dostarczyła wymaganych czterech zgodnych
wektorów: odpowiednio 3 i 3. Domyślny wariant miał 2 i 3.

AKAZE z progiem 0,0001 dał dla MOVIE_4 160→161 tylko 5 zgodnych wektorów,
a percentyle 4; to bardzo małe poparcie. Dla MOVIE_8 było to odpowiednio
79 i 43. LightGlue na MOVIE_4 160→161 miał 7–9 zgodnych wektorów,
na MOVIE_8 175–185. Te liczby nie są niezależnym potwierdzeniem jakości.

Czas samej próby AKAZE wynosił około 0,005–0,034 s. LightGlue około
0,009–0,039 s po pierwszej parze; pierwsza para każdego wariantu około
0,20 s. Pomiar zaczyna się po utworzeniu backendu, nie obejmuje ładowania
modelu. To pojedyncze czasy lokalne, nie benchmark ani gwarancja czasu GUI.

## Wzorce i ograniczenia

Na niezależnych wzorcach z zadanymi XY sprawdzono rzeczywisty AKAZE
i LightGlue, również zmienione progi, liczbę punktów, NMS, pełne obliczenia
i kontrast. Testy obejmują parę, łańcuch, graf, sesję oraz MPP.
Znane pozycje względem pierwszej klatki: (0, 0), (−7, +5), (+3, −4).

Nie wykonano nowego pełnego przebiegu MOVIE_4/MOVIE_8 ani pełnego przemiatania
parametrów. Próba nie porównuje wszystkich metod i nie zmienia wcześniejszych
wniosków o Deep Matcher/RoMa. Ocena wizualna przez użytkownika i odbiór
interaktywnego GUI pozostają otwarte. Samo zwiększenie liczby wyników AKAZE
z 0/4 do 2/4 nie oznacza wykazanej poprawy dokładności.
