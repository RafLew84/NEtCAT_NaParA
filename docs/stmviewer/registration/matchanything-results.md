# REG-12: MatchAnything-ELoFTR — wyniki

Data: 2026-11-02. Implementacja `b4d9441`, baza przeglądu `1c30ef5`.
Status **done**; użytkownik potwierdził „testy manualne ok” 2026-11-02.
Poniższe pomiary i ograniczenia pozostają bez zmian. Potwierdzenie nie
określa osobno Windows, VLC ani stanowiska z kartą 8 GB VRAM.
[Instrukcja GUI](matchanything-manual.md), [zasoby i dokładny preset](matchanything-environment.md),
[karta sprawdzeń](reviews/REG-12.md).

## Wdrożone zachowanie

MatchAnything-ELoFTR działa jako osobna metoda pary, filmu i grafu w `netcat`.
Nie instalowano nowych bibliotek. Wagi i kod są sprawdzane po SHA przed
uruchomieniem, model jest używany ponownie w ramach zadania. Nie ma
pobierania, zmiany urządzenia ani rozdzielczości po błędzie/OOM.

Używamy jawnie przypiętego **presetu biblioteki autorów**
`hf-match-images-preset-v1`: próg 0,001, NPE 832, przygotowanie 640×480
z dolnym paddingiem do 640² i maską. Skale X/Y oraz środki pikseli są
odwracane przed wspólnym konsensusem v2. Różni się to od natywnego wejścia
EfficientLoFTR; próba porównuje wariant modelu wraz z jego inference.
Żaden z modeli nie zmienia oryginalnych danych, gamma ani solvera grafu.

Sesja v7 zachowuje również nieaktywne ustawienia MatchAnything, graf v7
i MPP v10 zapisują tożsamość, konfigurację i diagnostykę. Starsze formaty
nadal są odczytywane. Odtworzenie sesji nie importuje modelu ani nie stosuje
niezatwierdzonego kandydata. Ręczna korekta, przywrócenie poprzednika
oraz eksport korzystają z istniejącej geometrii i renderowania z oryginałów.

## Rzeczywiste sprawdzenia modelu

- 9 prób rzeczywistych: para CPU/CUDA, łańcuch, graf/LS/Huber/zastosowanie,
  mały obraz i różne proporcje. Osiem CPU oraz jedna CUDA zaliczone.
- 3 porównania przygotowanych pikseli z przypiętymi funkcjami referencyjnymi
  autorów: 80², 137×219, 1001×301. Wszystkie identyczne piksel po pikselu.
- Niezależne uruchomienie oryginalnego modelu i kodu referencyjnego dla trzech
  par wzorca dało identyczne XY jak adapter do `1e-12`.
- Maksymalny błąd osi w łańcuchu wzorca 256²: **0,256136 px**.
  Tolerancja testu łańcucha/grafu wynosi 0,3 px, jak w istniejących próbach
  rzeczywistych modeli. Początkowe 0,25 px okazało się ciaśniejsze od błędu
  samego modelu; nie zmieniano wag ani parametrów, by dopasować wynik do testu.
- 2 rzeczywiste próby Qt offscreen CPU/CUDA: sprawdzenie modelu, rejestracja,
  informacja o metodzie/urządzeniu. Anulowanie i zła suma checkpointu na CUDA
  zachowały poprzedni obraz aligned i jego opis. To testy automatyczne GUI,
  nie ręczny odbiór użytkownika.

Raport zgodności oryginalnego modelu:
`/tmp/reg12-author-core-equivalence.json`. Raporty GUI i zrzuty:
`/tmp/stmviewer-reg12-gui/`. Źródła referencyjne oraz ich sumy:
`/home/rlew/.cache/stmviewer/matchanything/reference/`.

## Porównanie pełnych filmów

Te same oryginały/SHA, lista par, konsensus v2, okno 3, równe wagi LS
oraz domyślny Huber. MOVIE_4 po usunięciu źródłowych 1 i 2: **362 klatki,
1080 par**. MOVIE_8: **84 klatki, 246 par**. Urządzenie CUDA, RTX 5090.

| Film / metoda | Łańcuch | Brakujące relacje grafu | Słabe / pozostałe relacje | LS | Huber |
| --- | --- | ---: | --- | --- | --- |
| MOVIE_4 / EfficientLoFTR | odmowa 35→36 | 24 | 383 / 673 | kompletny | limit 200 iteracji |
| MOVIE_4 / MatchAnything | kompletny | 0 | 1058 / 22 | kompletny | limit 200 iteracji |
| MOVIE_8 / EfficientLoFTR | kompletny | 0 | 206 / 40 | kompletny | zbieżny, 49 iteracji |
| MOVIE_8 / MatchAnything | kompletny | 0 | 246 / 0 | kompletny | zbieżny, 38 iteracji |

Pozostałe relacje mają status `manual_review`, nie „zweryfikowane”.
W obu łańcuchach MatchAnything wszystkie estymowane przejścia są oznaczone
jako niepewne. Kompletność jest wynikiem funkcjonalnym, a nie dowodem
poprawnej kompensacji dryfu. EfficientLoFTR odmawia w bieżącej parze
MOVIE_4 35→36 (źródłowa 37→38): tylko 3 zgodne wektory z wymaganych 4.

| Film / metoda | Łańcuch [s] | Graf [s] | Model / konsensus grafu [s] | Szczyt RSS z zapisem [MiB] | Szczyt alokacji Torch CUDA [MiB] |
| --- | ---: | ---: | --- | ---: | ---: |
| MOVIE_4 / EfficientLoFTR | 2,53 do odmowy | 10,34 | 7,12 / 2,33 | 3563 | 450 |
| MOVIE_4 / MatchAnything | 34,94 | 99,38 | 37,27 / 59,31 | 5324 | 4880 |
| MOVIE_8 / EfficientLoFTR | 4,50 | 5,15 | 3,40 / 1,02 | 4424 | 996 |
| MOVIE_8 / MatchAnything | 8,86 | 22,21 | 8,24 / 12,73 | 4158 | 3903 |

LS: około 0,010 s dla MOVIE_4 i 0,003 s dla MOVIE_8. Huber MatchAnything:
0,180 s do limitu MOVIE_4 i 0,034 s dla MOVIE_8. Renderowanie łańcuchów
MatchAnything: 1,119 s / 0,626 s; zastosowanie LS: 0,980 s / 0,613 s.
To pojedyncze pomiary z profilowaniem na lokalnym stanowisku, nie gwarancja
wydajności. Alokacja Torch nie obejmuje całego zużycia sterownika; karta
32 GB nie zalicza osobnego odbioru na 8 GB VRAM.

Dla kompletnych wariantów sprawdzono zapis/odczyt sesji, zastosowanie LS
(i Hubera dla MOVIE_8), ręczną korektę przez API, przywrócenie poprzednika,
MPP+metadane i ponowny odczyt pikseli oraz małe MJPG/FFV1. Odmowy i limit
Hubera nie były zastępowane zerami lub inną metodą. VLC niewykonane.

## Wzorce i ograniczenia jakości

Raport dziewięciu par dla każdego modelu: `/tmp/stmviewer-reg12-patterns/report.json`.
Próba CPU obejmuje `cpu.mpp`, translację podpikselową, nieruchomy pas,
pojedynczy pas, różny ruch góry/dół, obraz okresowy i szum.

- Na dwóch bogatszych wzorcach translacji maks. błąd osi MatchAnything
  wynosi około 0,094 i 0,146 px; EfficientLoFTR około 0,336 i 0,175 px.
- **Na prostym `cpu.mpp` MatchAnything ma błąd Y około 1,00 i 0,66 px**,
  mimo statusu `manual_review`; EfficientLoFTR ma tu błąd osi poniżej 0,017 px.
  Próba uruchomienia GUI na tym pliku nie oznacza zaliczenia dokładności XY.
- Na nieruchomym pasie i szumie MatchAnything różni się od znanego ruchu
  o około 0,20 px, z ostrzeżeniem. EfficientLoFTR jest bliżej znanej translacji.
- Różny ruch dwóch części obrazu daje różne wybrane przesunięcia u obu
  modeli. Jedno globalne XY nie koryguje takiego obrazu w całości.
- Obraz okresowy: MatchAnything odmawia (1 korespondencja, wymagane 8),
  EfficientLoFTR zwraca niepewne przesunięcie. Odmowa nie jest awarią systemu.

Nakładki na tym samym polu odniesienia i z tym samym kontrastem:
`/tmp/stmviewer-reg12-visuals/{movie4-early,movie4-middle,movie4-later,movie8}.png`.
Obejmują zgłoszone pary MOVIE_4 oraz 1→2, 16→17 i 56→57 MOVIE_8.
Oględziny zrzutów pokazują rozbieżne XY i pozostające różnice pasów/tearingu.
W MOVIE_8 16→17 i 56→57 większe struktury zbliżają się w obu wariantach;
nie ma podstaw do ogłoszenia jednego zwycięzcy dla całych filmów.
Agent nie obejrzał ręcznie pełnego odtwarzania pierwszych 150 klatek
i reszty MOVIE_4. Następnie użytkownik potwierdził „testy manualne ok”
2026-11-02, zamykając odbiór REG-12. Nie podał szczegółowej oceny
poszczególnych fragmentów; nie dopisujemy jej do pomiarów powyżej.
Brak niezależnej prawdy fizycznej STM; REG-06 pozostaje odłożony.

## Odtwarzanie prób

Końcowe wyniki, duże pliki wyłącznie lokalnie:

```text
/tmp/stmviewer-reg12-author-movie4/
/tmp/stmviewer-reg12-author-movie8/
/tmp/stmviewer-reg12-efficient-movie4/
/tmp/stmviewer-reg12-efficient-movie8/
```

Każdy katalog zawiera `report.json` i `graph-candidate.stmsession`;
kompletny łańcuch także `chain.stmsession`. Sesja kandydata nie zmienia
aktywnego filmu przed jawnym zastosowaniem. `ls-corrected.stmsession` oraz
wariant Huber to materiały kontroli cyklu pracy, z testową ręczną korektą
+1 px Y — nie należy traktować ich jako niezmienionego wyniku modelu.
Małe eksporty są obok sesji. Wcześniejsze katalogi
`stmviewer-reg12-matchanything-movie4/8` dotyczyły porzuconej konfiguracji
natywnej; nie stanowią wyników końcowego adaptera.

```bash
PYTHONPATH=.:tests/stmviewer:tests/stmviewer/diagnostics \
  python tests/stmviewer/diagnostics/efficient_trial.py /tmp/reg12-recheck \
  --source data/MOVIE_4.mpp --drop-first 2 \
  --method matchanything_eloftr --device cuda
```

Wyniki testów automatycznych i ograniczenia platform zapisano w karcie
przeglądu. Nie zmieniono domyślnej metody aplikacji.
