# REG-08b — wyniki obliczeń i materiały do odbioru

Data: 2026-11-01. Próby numeryczne i renderowanie wykonane automatycznie;
**ocena wizualna użytkownika pozostaje niewykonana**. Zmniejszenie kosztu
Hubera nie dowodzi poprawnego dopasowania struktur STM.

## Metoda i ustawienia

Blokowy Huber dla `||(p_j-p_i)-d_ij||₂`, jedna waga dla obu osi:
`w=min(1, δ/||r||₂)`, a dla zerowej reszty `w=1`. Start to zapisane LS
z równymi wagami, kotwica to pierwsza klatka. Zapisane relacje, braki i źródła
pozostają identyczne. Nie ma kary za kierunek, prędkość ani odległość od zera.

Domyślne parametry: próg **2 px**, **200 iteracji**, maksymalny krok pozycji
`1e-5 px`, względna zmiana kosztu `1e-8`, maksimum bezwzględnego gradientu
`1e-6`. Wszystkie trzy warunki muszą być spełnione. Kontrola układu:
`cond₁` zakotwiczonego ważonego Laplasjanu nie większe niż `1e12`, wersja
`anchored-laplacian-1norm-v1`; solver `block-huber-irls-v1`. Miara uwarunkowania
dotyczy układu ostatniego rozwiązanego kroku IRLS. Warunki, limit, iteracje,
miary i przyczyna zakończenia są zapisane w sesji. Brak zbieżności zachowuje
ostatnią skończoną iterację wyłącznie jako diagnostykę, bez filmu Hubera.

## Dobór progu na osobnych danych rozwojowych

Generator `tests/stmviewer/diagnostics/robust_graph_fixtures.py development`
używa trzech ziaren 808100–808102, 17 znanych pozycji z nawrotami, okna 3,
szumu pomiarów σ=0,8 px oraz osobno jednego błędu `(20,-16)` px. To pomiary
zadane, bez modelu. Wykonano 30 rozwiązań; wszystkie zbieżne w limicie 200.

| Próg px | Średni RMSE czystej sieci px | Średni RMSE z odstającą relacją px |
| --- | ---: | ---: |
| 0,5 | 0,727 | 0,621 |
| 1 | 0,656 | 0,500 |
| **2** | **0,633** | **0,508** |
| 4 | 0,623 | 0,707 |
| 8 | 0,623 | 1,352 |
| Zwykłe LS | 0,623 | 2,767 |

Wybrano 2 px: w czystych sieciach znacząco osłabia tylko 1 ze 135 relacji
(`w<0,99`), zachowując ograniczenie wpływu błędu. Nie jest to uniwersalny
optymalny próg. Wyniki: `/tmp/stmviewer-reg08b-development-final/development.json`.
Po rozpoczęciu prób odbiorczych nie zmieniano domyślnych progów ani tolerancji.

## Niezależne sceny odbiorcze

Nowe ziarno 808290, inne dziewięć pozycji, tekstura z rozpoznawalnymi cechami
oraz osobny wzór okresowy 24 px. Sesje i manifest:
`/tmp/stmviewer-reg08b-fixtures/`. Generator i [instrukcja](robust-graph-manual.md)
podają prawdziwe położenia. Model Deep nie uczestniczy w tworzeniu tych relacji.

| Przypadek | Wynik przy domyślnych ustawieniach |
| --- | --- |
| Jeden błąd `(18,-14)` px, para 3→6 | Maks. błąd współrzędnej LS 5,022 px → Huber 0,712 px; waga błędnej relacji 0,0927. |
| Jedyny most ma ten sam błąd | LS i Huber zachowują błąd 18 px; wagi 1. Brak niezależnego obejścia. |
| Drzewo poprawnych relacji | Obie metody odtwarzają znane XY z dokładnością numeryczną. |
| Graf rozłączny | Jawny brak pełnych XY; nie powstaje film Hubera. |
| Spójny fałszywy alias okresowy | Błąd 192 px pozostaje przy wagach 1; mała reszta nie wykrywa aliasu. |
| Przewaga spójnych błędnych pomiarów | Maks. błąd LS 190,094 px → Huber 191,763 px. Odporność nie gwarantuje prawdy. |

Każdy scenariusz zapisano jako sesję wejściową LS i `*-with-huber.stmsession`.
Zapis waliduje pełny odczyt metadanych; osobne testy i rzeczywiste próby poniżej
sprawdzają odtworzenie archiwum. Wyniki syntetyczne nie zastępują oceny STM.

## Rzeczywiste filmy — te same pomiary co REG-08a

Wczytano sesje `/tmp/reg08a-movie{4,8}-final/window-{3,5}.stmsession`.
MOVIE_4 ma 362 klatki po usunięciu dwóch początkowych; MOVIE_8 ma 84 klatki.
W świeżych procesach blokowano import Torch/Kornia; Deep nie był uruchamiany.
Identyfikator pomiarów, wszystkie relacje i braki porównano przed i po.

| Film / okno | Próg 2 px, limit 200 | Próg 1 px, limit 200 | Dodatkowa jawna próba z limitem 5000 |
| --- | --- | --- | --- |
| MOVIE_4 / 3 | Limit 200, brak pełnego wyniku | Limit 200, brak pełnego wyniku | Oba progi nadal bez wymaganej zbieżności. |
| MOVIE_4 / 5 | Zbieżność po 111 iteracjach | Limit 200 | Próg 1: zbieżność po 433 iteracjach. |
| MOVIE_8 / 3 | Zbieżność po 46 iteracjach | Limit 200 | Próg 1: zbieżność po 685 iteracjach. |
| MOVIE_8 / 5 | Zbieżność po 45 iteracjach | Zbieżność po 138 iteracjach | Niepotrzebna. |

W MOVIE_4/3 po 5000 iteracjach gradient nadal wynosi `2,96e-5` / `9,28e-5`,
a maksymalny krok `1,79e-5` / `8,84e-5` px. Koszt zmienia się już bardzo mało,
ale to nie wystarcza do spełnienia wszystkich warunków. Nie rozluźniono
kryteriów ani nie przedstawiono ostatniej iteracji jako kompletnego wyniku.

Sesje z oboma progami i raportami `report.json`:

- `/tmp/reg08b-movie4-window3-long/comparison.stmsession`: LS i cztery nieukończone próby (200/5000).
- `/tmp/reg08b-movie4-window5-long/comparison.stmsession`: dwa poprawne progi, zachowane wcześniejsze próby.
- `/tmp/reg08b-movie8-window3-long/comparison.stmsession`: dwa poprawne progi, zachowane wcześniejsze próby.
- `/tmp/reg08b-movie8-window5/comparison.stmsession`: dwa poprawne progi przy domyślnym limicie.

Próg 2 powtórzony z większym limitem daje te same pozycje i liczbę iteracji;
wcześniejszy wariant pozostaje. To świadomie wybrany limit dodatkowej próby,
nie zmiana ustawień domyślnych na podstawie danych odbiorczych.

Każda sesja przeszła zapis i odczyt z identycznym stanem grafu. Kontrolowano
niezmienność pikseli aktywnego aligned, jeśli był obecny. Każdą klatkę LS
i wszystkich kompletnych wariantów Hubera wyrenderowano na żądanie, bez
materializowania dodatkowych stosów. Render p95: około 2,5–2,7 ms dla MOVIE_4
i 12,5–12,9 ms dla MOVIE_8. RSS procesu 1,2–1,4 GiB obejmuje jednocześnie
źródłową i ponownie odczytaną sesję; nie jest to pomiar RAM samego solvera.
Czasy solvera: około 0,03–0,19 s dla zakończonych prób, 1,5–1,6 s dla 5000
iteracji MOVIE_4/3. Pomiary zależą od tego stanowiska.

## Odtworzenie

W środowisku `netcat`, katalog `NEtCAT-viewer`:

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/robust_graph_fixtures.py development /tmp/nowy-reg08b-development
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/robust_graph_fixtures.py acceptance /tmp/nowy-reg08b-fixtures
PYTHONPATH=. python tests/stmviewer/diagnostics/robust_graph_trial.py /tmp/reg08a-movie4-final/window-5.stmsession /tmp/nowa-proba-reg08b --max-iterations 5000
```

Skrypt rejestruje numeryczne wyniki i renderowanie; jakość wizualną ocenia
użytkownik według [instrukcji](robust-graph-manual.md). Katalog docelowy próby
musi być nowy. Pliki `/tmp` są tymczasowe, a nie wersjonowanymi danymi projektu.
Nie wykonano odbioru Windows 11 ani sprzętu docelowego. Zastosowanie wyniku
i eksport jego pikseli pozostają zakresem REG-08c.
