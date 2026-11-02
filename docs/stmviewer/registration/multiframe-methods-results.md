# REG-08e — pomiary i materiały do odbioru

Data: 2026-11-02. [Ticket](issues/08e-multiframe-methods.md),
[instrukcja manualna](multiframe-methods-manual.md).
To wykonane próby automatyczne; ręczny odbiór użytkownika pozostaje niewykonany.

## Dane ze znanymi przesunięciami

Osiem klatek 256×256 wyciętych z większego obrazu z teksturą i asymetrycznymi
znacznikami, bez zawijania obrazu. Pozycje XY: (0,0), (2,−1), (1,1), (−2,0),
(3,2), (−1,−2), (0,1), (2,0). Kierunek ruchu zmienia się w serii.
Plik do otwarcia: `/tmp/reg08e-cpu-known-v3/known.mpp`.
Generator: `tests/stmviewer/diagnostics/graph_methods_trial.py`.

Wszystkie osiem metod dało kompletne LS i zbieżnego Hubera dla okien 3 i 5.
Poniżej największy błąd pojedynczej współrzędnej LS względem znanego ruchu,
w pikselach. Na tym wzorcu Huber dał te same pozycje co LS.

| Metoda | Okno 3 | Okno 5 |
| --- | ---: | ---: |
| Phase | 0.01165 | 0.02129 |
| Korelacja bez normalizacji | 0.00000 | 0.00000 |
| Tile+RANSAC | 0.75076 | 0.35294 |
| ECC | 0.00543 | 0.00707 |
| Optical Flow | 0.00062 | 0.00041 |
| Deep Matcher | 0.05404 | 0.05349 |
| Deep+ECC | 0.01211 | 0.00587 |
| Deep+lokalne fragmenty | 0.00553 | 0.00401 |

To wynik tego wzorca, nie ranking jakości dla obrazów STM. Warianty metod i ich
progi pozostały takie jak w rejestracji par. Korelacja bez normalizacji oraz
metody złożone zachowują `manual_review` i brak wskaźnika pewności.
Zmiana okna 3→5 wykorzystała 18 wcześniejszych pomiarów i dołożyła 7.
LS i Huber pracowały na tym samym zbiorze pomiarów.

Wszystkie pięć metod CPU działało z zablokowanym importem Torch/Kornia.
Metody Deep użyły lokalnego LoFTR outdoor na CUDA, z zablokowanym pobieraniem.
Wagi: `loftr_outdoor.ckpt`, SHA256
`21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec`.

## Pełne filmy STM

MOVIE_4: 362 klatki 256×256, po odrzuceniu dwóch pierwszych źródłowych klatek.
MOVIE_8: 84 klatki 512×512. Okno 3; odpowiednio 1080 i 246 planowanych par.
Huber: próg 2 px, limit 200 iteracji, pozostałe ustawienia domyślne.

| Film | Metoda | Pomiar i LS, s | Brakujące pary | Huber | Render p95, ms |
| --- | --- | ---: | ---: | --- | ---: |
| MOVIE_4 | Optical Flow | 241.69 | 0 | zbieżny, 46 iteracji | 4.22 |
| MOVIE_4 | Deep Matcher | 13.34 | 3 | limit 200, niekompletny | 3.42 |
| MOVIE_8 | Optical Flow | 188.35 | 0 | limit 200, niekompletny | 11.96 |
| MOVIE_8 | Deep Matcher | 12.87 | 0 | zbieżny, 46 iteracji | 12.63 |

LS był kompletny we wszystkich czterech próbach. Trzy odmowy Deep na MOVIE_4
dotyczyły za małej liczby dopasowanych punktów; graf pozostał spójny przez
inne relacje. Nie zastąpiono braków zerowym przesunięciem. Niekompletne
warianty Hubera zapisano jako diagnostykę i nie stosowano do filmu.

Pomiary na lokalnym `netcat`, RTX 5090 32 GB; część prac wykonywano równolegle.
Są to czasy obserwowane, nie izolowany benchmark ani odbiór stanowiska 8 GB VRAM.
Największy zmierzony przydział CUDA: około 937 MiB; szczyt RSS procesu:
około 3665 MiB. Render dotyczy pojedynczych klatek podglądu, nie mierzy reakcji
GUI ani odtwarzania na komputerze docelowym.

Raporty, sesje i eksporty pozostają lokalnie:

- `/tmp/reg08e-cpu-known-v3/report.json` — pięć metod CPU, okna 3 i 5.
- `/tmp/reg08e-deep-known-v1/report.json` — trzy metody Deep, okna 3 i 5.
- `/tmp/reg08e-movie4-v1/report.json` — pełny MOVIE_4, Optical Flow i Deep.
- `/tmp/reg08e-movie8-v1/report.json` — pełny MOVIE_8, Optical Flow i Deep.

W każdym katalogu znajduje się podkatalog `<identyfikator-metody>-window3`
(dla wzorca również `window5`). `candidate.stmsession` zawiera kandydatów
LS/Hubera bez aktywnego aligned. `ls-corrected.stmsession` i, dla zbieżnego
Hubera, `huber-corrected.stmsession` zawierają zastosowany film i przykładową
korektę +1 px Y od drugiej klatki. To próba działania historii, **nie propozycja
poprawki fizycznego dryfu**. Do oceny algorytmu otwórz `candidate.stmsession`.

Przebiegi sprawdziły niezmienność oryginałów, zastosowanie kompletnego wyniku,
korektę ręczną, dokładny zapis/odczyt sesji, przywrócenie poprzedniego wyniku
tam, gdzie dostępne były oba solvery, MPP po pozostawieniu pięciu klatek
oraz AVI MJPG/FFV1. MPP zachował wartości i XY. Małe AVI zawierają pierwsze
12 klatek (8 dla wzorca), 5 kl./s. Pliki `*-five-frames.mpp` mają dodatki
metadanych i pochodzenie metody; `*-FFV1.avi` i `*-MJPG.avi` są filmami prezentacyjnymi.

MOVIE_4 zapisał oba wpisy raportu i zakończenie wszystkich asercji; późniejszy
odczyt stanu procesu zwrócił kod 143 (SIGTERM). Przyczyny sygnału nie ustalono.
Kompletność zapisanych artefaktów zweryfikowano osobnym odczytem; nie opisujemy
tego przebiegu jako procesu zakończonego kodem 0. Wzorce i MOVIE_8 zakończyły się kodem 0.

## Ograniczenia oceny jakości

Nie przypisujemy wynikowi przewagi wizualnej na MOVIE_4/MOVIE_8 na podstawie
samej zbieżności, rozmiaru aligned ani wielkości ruchu. Użytkownik powinien
obejrzeć pierwsze 150 klatek MOVIE_4 i pary 29→30, 35→36, 44–46, 61→62, 94–97,
w numeracji po usunięciu pierwszych dwóch klatek. Oddzielnie ocenia tearing.
Instrukcja manualna podaje ścieżkę porównania. Windows 11, VLC i stanowisko
docelowe nie zostały w tym zadaniu odebrane ręcznie.
