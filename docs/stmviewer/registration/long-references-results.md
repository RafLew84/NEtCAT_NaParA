# REG-08d — wyniki prób dalszych odniesień

Data: 2026-11-01. Baza kodu `38d2cb6`; implementacja `4c4ffa9`, wspólny pomiar pary po przeglądzie `a811636`.
Status: oczekuje na ręczny odbiór użytkownika.
[Instrukcja i sesje](long-references-manual.md), [karta testów](reviews/REG-08d.md).

## Wzorzec z podanymi relacjami

18 klatek 256×256 wyciętych z jednej większej sceny, z zapisanym ruchem
obejmującym różne kierunki. Model Deep nie bierze udziału w tych próbach.
Do okna 3 dodano 12 par: odniesienie 1, zakres 7–18.

| Przypadek | Maks. błąd jednej współrzędnej przed | Po | Wynik |
| --- | ---: | ---: | --- |
| Lokalne relacje z błędem +0,8 px/krok, poprawne dalsze relacje | 13,600 px | 2,352 px | Poprawa znanego XY, bez całkowitego usunięcia błędu bazowych pomiarów. |
| Spójny alias wzoru okresowego o 24 px | 24,000 px | 24,000 px | Błędny ruch pozostaje przy resztach około 1e−14 px. |
| Wszystkie dalsze relacje bez wyniku | 13,600 px | 13,600 px | Zachowane bazowe położenia, 12 jawnych odmów. |

Raport: `/tmp/reg08d-known-v2/report.json`; generator w
`tests/stmviewer/diagnostics/long_reference_fixtures.py`.
Te próby sprawdzają solver i obsługę braków, nie skuteczność modelu na STM.

## Pomiary rzeczywiste

Bazą są zachowane sesje REG-08b. Wszystkie wcześniejsze surowe pomiary
pozostały identyczne; zmierzono wyłącznie dodatkowe pary. Jeden zestaw nowych
pomiarów wykorzystano dla LS oraz Hubera przy jego niezmienionych ustawieniach:
próg 2 px, limit 200 iteracji, tolerancje i kotwica jak w bazie.

| Film | Okno | Odniesienia / zakres bieżący | Nowe pary / odmowy | Maks. zmiana współrzędnej LS | Huber |
| --- | --- | --- | --- | --- | --- |
| MOVIE_4 | 5 | 20,110 / 25–100 | 151 / 8 | 40,617 px | Zbieżny w 111 iteracjach; maks. zmiana 3,375 px. |
| MOVIE_8 | 3 | 1,50 / 17–40 | 48 / 0 | 130,783 px | Limit 200; brak kompletnego wyniku i zastosowania. |

Zmiana położeń nie jest pomiarem poprawy. Szczególnie duża zmiana LS w MOVIE_8
wymaga oceny struktur przez użytkownika. Nie dobierano następnych odniesień
ani progu po obejrzeniu tych liczb. Braki pozostają bez XY, z przyczyną
odmowy modelu. Spójne, ale błędne relacje nadal mogą przejść kwalifikację Deep.

MOVIE_4: 362 klatki, źródłowe MPP 3–364; MOVIE_8: 84 klatki, źródłowe 1–84.
SHA-256 źródeł:

- MOVIE_4: `9d066676a3f947ed53610438051537eb3b30288aadc11d774ec52e509f31f961`.
- MOVIE_8: `a06ab5d34250ca564b11eb9da4e9ea65131b80d2a2e3ceaf09f0709569cdbde7`.

LoFTR outdoor: SHA-256
`21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec`.
Lokalne wagi:
`/home/rlew/projekty/tracker-import-20261008/trackers-windows-20261008/model_cache/torch/hub/checkpoints/loftr_outdoor.ckpt`.
NumPy 2.2.5, SciPy 1.15.2, Torch 2.9.1+cu128, Kornia 0.8.2;
CUDA:0, NVIDIA RTX 5090. Przygotowanie wejścia i translacyjny konsensus
pozostają bazowym Deep, bez ECC. Podczas prób pobieranie wag zablokowano.

| Film | Identyfikacja + model + nowe pary | LS | Huber | Render p95 LS/Huber | Szczyt RSS | Szczyt przydzielonej VRAM |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| MOVIE_4 | 1.745 s | 0.0081 s | 0.102 s | 2.47 ms / 2.39 ms | 4223 MiB | 331 MiB |
| MOVIE_8 | 1.695 s | 0.0017 s | 0.059 s | 11.78 ms / brak kompletnego wyniku | 4189 MiB | 937 MiB |

RSS obejmuje cały skrypt z sesjami, renderowaniem i eksportami; to nie sam model.
Próba na RTX 5090 nie zalicza stanowiska z 8 GB VRAM ani Windows 11.

Dla kompletnych wariantów sprawdzono:

- Renderowanie wszystkich klatek bazy i rozszerzenia; wspólny układ współrzędnych.
- Zapis i ponowny odczyt sesji: aktywne okno oraz niezastosowany kandydat osobno.
- Zastosowanie, demonstracyjną korektę +1Y, dokładne przywrócenie poprzedniego filmu.
- Mały MPP po usunięciu dalszych klatek: identyczne wartości, XY i historia korekt.
- AVI FFV1 przed/po: OpenCV odczytał wszystkie 76 klatek MOVIE_4 i 24 MOVIE_8,
  tempo 5 kl./s. Cztery filmy MOVIE_4 i dwa MOVIE_8; nie odtwarzano ich ręcznie w VLC.
- Niekompletny Huber MOVIE_8 pozostaje zapisany jako diagnostyka. Nie zastosowano
  LS automatycznie zamiast niego.

Raporty: `/tmp/reg08d-movie4-v1/report.json`, `/tmp/reg08d-movie8-v1/report.json`.
Sesje i AVI są w tych samych katalogach. Skrypt odtwarzający:
`tests/stmviewer/diagnostics/long_reference_trial.py`.

## GUI i trwałość

Obejrzano zrzuty Qt offscreen na wzorcu i rzeczywistym MOVIE_4:
`/tmp/reg08d-movie4-plan.png`, `/tmp/reg08d-movie4-film.png`.
Tabela pokazuje nowe pary i źródłowe numery MPP; podgląd porównuje bazę przy
tej samej konfiguracji solvera i wskazuje różnicę globalnych XY. Wybór samej
bazy blokuje zastosowanie innego wariantu. To automatyczna próba GUI,
nie ręczny odbiór użytkownika ani pełna ocena jakości dopasowania struktur.

Rozszerzony graf ma format zagnieżdżony `stmviewer-graph-v3`; zewnętrzny format
sesji pozostaje v3, stare grafy v1/v2 są czytane. Bazowy graf jest przechowywany
raz, bez rekurencyjnego rozszerzania. Wersja kodu estymatora jest odrębna od
wersji solvera; znany stary digest REG-08a–08c ma jawną migrację. Nieznana
lub zmieniona wersja estymatora nie może domierzać par do istniejącej bazy.

MPP z rozszerzonym grafem dostaje metadane v6 z odniesieniami, zakresem,
indeksami bazowych/dodanych par i pochodzeniem konfiguracji. Pełne surowe
relacje, reszty i bazowy wynik do porównania należą do sesji. Eksport samego
okna nadal używa v5; zachowano starsze warianty MPP i sesji.

Ręczna ocena funkcji i jakości, Windows 11 oraz docelowy sprzęt pozostają
niewykonane. Kolejny ticket nie jest uruchamiany automatycznie.
