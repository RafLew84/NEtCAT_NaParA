# REG-14: AKAZE — wyniki prób

Data: 2026-11-02. Implementacja a9abf0f, poprawka skrajnego wymiaru 9dd0337.
Status ready-for-review; manualny odbiór użytkownika niewykonany.

**Przy ustalonej konfiguracji AKAZE nie dostarczył wyniku dla żadnej z 18
wybranych par STM. Nie utworzył kompletnego łańcucha ani grafu MOVIE_4/MOVIE_8.**
Wzorce z wyraźną teksturą potwierdzają poprawne XY i działanie aplikacji,
ale na tych pomiarach obecny wariant jest mniej użyteczny od Deep/RoMa.
Nie obniżano progów ani nie strojono detektora osobno dla trudnych klatek.

## Warunki i odtwarzalność

Dodano 18 prób AKAZE do 54 prób REG-13: razem **72 próby czterech metod**.
Zachowano także dziewięć wspólnych par wzorcowych, z odmowami i niepowodzeniami.
Oryginały, wartości wszystkich par oraz niezmieniony kod estymatorów
Deep/RoMa/LightGlue zweryfikowano; raportów bazowych nie przeliczano.
Ich czasy dotyczą wcześniejszego wykonania CUDA, a AKAZE wykonano na CPU.
To porównanie oszacowań, nie kontrolowany pomiar względnej szybkości urządzeń.
Deep ma historyczny konsensus; trzy nowsze metody używają wspólnego v2.

[Środowisko, parametry, źródła i polecenia](akaze-environment.md).
Adapter używa MLDB, wzajemnego Hamming, natywnych wymiarów i min/max uint8,
bez gamma. Minimum osiem korespondencji/cztery zgodne wektory pozostaje stałe.
MOVIE_4 ma 362 klatki 256 × 256 po usunięciu pierwszych dwóch; MOVIE_8:
84 klatki 512 × 512. Wszystkie numery poniżej są numerami bieżącymi.

Artefakty lokalne: data/registration-reg14. Raporty pairs-*.json,
patterns-*.json, baseline-verification.json zawierają sumy wejść, konfigurację,
XY, diagnostykę i odmowy. Kod pilotażu odpowiada a9abf0f; późniejsza poprawka
obsługi obrazów jednowierszowych/jednokolumnowych nie zmienia tych wejść ani
parametrów. Sumy źródeł z wykonania pozostawiono w raportach.

## Wspólne pary STM

| Metoda | Wynik / 18 | Odmowy | Statusy wyników |
| --- | ---: | ---: | --- |
| deep | 18 | 0 | 16 low_confidence, 2 ok |
| roma | 18 | 0 | 12 manual_review, 6 low_confidence |
| lightglue | 12 | 6 | 10 low_confidence, 2 manual_review |
| akaze | 0 | 18 | — |

W tabeli XY oznacza translację nakładaną na drugą klatkę w pikselach original.
Odmowa nie jest zerowym przesunięciem ani pomiarem braku dryfu.

| Film | Para | Deep outdoor | RoMa Turbo | LightGlue/SuperPoint | AKAZE |
| --- | --- | --- | --- | --- | --- |
| MOVIE_4.mpp | 1→2 | (22.37, 13.48) | (19.73, 11.63) | odmowa | odmowa |
| MOVIE_4.mpp | 31→32 | (-22.94, -31.58) | (-22.92, -32.05) | odmowa | odmowa |
| MOVIE_4.mpp | 118→119 | (31.43, 22.28) | (38.51, 24.67) | (32.00, 22.00) | odmowa |
| MOVIE_4.mpp | 29→30 | (0.68, 7.23) | (13.86, -2.93) | odmowa | odmowa |
| MOVIE_4.mpp | 35→36 | (0.09, -5.30) | (-12.37, -4.58) | odmowa | odmowa |
| MOVIE_4.mpp | 44→45 | (23.39, 8.11) | (28.50, 11.71) | (26.00, 11.50) | odmowa |
| MOVIE_4.mpp | 45→46 | (0.36, 17.28) | (-29.02, -10.34) | odmowa | odmowa |
| MOVIE_4.mpp | 61→62 | (-0.34, -0.80) | (10.27, 3.68) | (0.00, -1.00) | odmowa |
| MOVIE_4.mpp | 94→95 | (38.22, 9.23) | (41.81, 12.80) | odmowa | odmowa |
| MOVIE_4.mpp | 95→96 | (-15.46, -6.95) | (-29.29, -14.62) | (-19.00, -9.00) | odmowa |
| MOVIE_4.mpp | 96→97 | (-15.65, -6.58) | (-15.08, -6.38) | (-16.00, -7.00) | odmowa |
| MOVIE_4.mpp | 160→161 | (-1.50, 1.94) | (-3.03, 3.79) | (-2.00, 5.00) | odmowa |
| MOVIE_4.mpp | 250→251 | (-1.60, 4.54) | (-2.05, 3.99) | (-3.00, 3.00) | odmowa |
| MOVIE_8.mpp | 1→2 | (15.11, 0.43) | (16.89, 0.51) | (14.00, 1.00) | odmowa |
| MOVIE_8.mpp | 16→17 | (-24.51, -32.17) | (-26.34, -31.20) | (-25.00, -29.00) | odmowa |
| MOVIE_8.mpp | 56→57 | (-39.61, 7.04) | (-37.91, 4.06) | (-40.00, 4.00) | odmowa |
| MOVIE_8.mpp | 25→26 | (15.05, 0.27) | (15.06, 0.41) | (13.00, 0.00) | odmowa |
| MOVIE_8.mpp | 70→71 | (-7.83, -31.15) | (-7.49, -29.70) | (-10.00, -30.00) | odmowa |

AKAZE odmówił 10 razy przed konsensusem (mniej niż osiem korespondencji)
i osiem razy z powodu mniej niż czterech zgodnych wektorów.
Pierwsza para MOVIE_4: jedna korespondencja; MOVIE_8: jeden zgodny wektor
z 27. Wszystkie przyczyny i diagnostykę zachowano w JSON.
Nie utożsamiamy odmowy z błędem UI ani poprawnym dopasowaniem.

Sześć tablic movie_4-pairs-*.png i movie_8-pairs-*.png pokazuje wszystkie
18 par: wspólne oryginalne pole widzenia, obraz bazowy czerwony, przesuwany
turkusowy, odmowy jawnie puste. Obejrzano pierwszą tablicę MOVIE_4 jako
kontrolę prezentacji. Nie wykonano ręcznej oceny wszystkich konturów STM;
brak niezależnej prawdy o fizycznym dryfie nie pozwala ogłosić zwycięzcy
na podstawie zgodności metod lub liczby punktów.

## Wspólne wzorce

Poniżej maksymalny bezwzględny błąd jednej osi w px tam, gdzie znane jest
jedno globalne XY. Dla rozdzielonego ruchu i periodycznego wzoru podano
oszacowanie, nie błąd względem arbitralnie wybranej prawdy.

| Wzorzec / para | Deep | RoMa | LightGlue | AKAZE |
| --- | --- | --- | --- | --- |
| cpu.mpp 1→2 | 0.0722 | 0.0032 | 0.0000 | odmowa |
| cpu.mpp 2→3 | 0.2977 | 0.0057 | 0.0000 | odmowa |
| translation.mpp 1→2 | 0.0557 | 0.0056 | odmowa | 0.0011 |
| translation.mpp 2→3 | 0.0533 | 0.0228 | odmowa | 0.0042 |
| stationary-artifact.mpp 1→2 | 7.0109 | 6.9963 | 7.0000 | 7.0009 |
| one-band.mpp 1→2 | 0.0465 | 0.0109 | 0.0000 | 0.0000 |
| split-motion.mpp 1→2 | (2.97, -1.97) | (2.98, -1.99) | odmowa | (-5.00, 4.00) |
| periodic.mpp 1→2 | odmowa | (-12.99, -9.97) | odmowa | (3.00, -2.00) |
| noisy.mpp 1→2 | 0.3503 | 0.2154 | odmowa | 0.1409 |

AKAZE otrzymał siedem wyników i dwie odmowy na małym cpu.mpp (80 × 80).
Na translacji subpikselowej błąd wyniósł 0,0011 i 0,0042 px; na zaszumionym
wzorcu 0,1409 px. Te pojedyncze, dobrane wzorce nie określają ogólnej dokładności.

**Niepowodzenia:** nieruchomy artefakt sprowadził AKAZE do XY≈(0,0), mimo
znanego ruchu sceny (7,−5), podobnie jak trzy bazy. Ostrzeżenie low_confidence
nie usuwa tego błędu. Jeden pas i rozdzielony ruch dały ostrzeżenia; dla
wzoru periodycznego zwrócono (3,−2) ze statusem manual_review, który nie
rozstrzyga wieloznaczności translacji o okres. Nie dodano detekcji tej
wieloznaczności do wspólnego konsensusu.

## Pełne filmy

Okno grafu 3, te same reguły planowania par i LS/Huber co w REG-13.

| Film | Łańcuch | Relacje z wynikiem | Braki | Składowe grafu | Największa składowa | LS / Huber |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| MOVIE_4 | odmowa pary 1→2 | 192/1080 | 888 | 243 | 34 | rozłączny / rozłączny |
| MOVIE_8 | odmowa pary 1→2 | 33/246 | 213 | 55 | 10 | rozłączny / rozłączny |

MOVIE_4: 184 relacje low_confidence i 8 manual_review; MOVIE_8: 30 i 3.
Graf nie zastępuje braków zerami i nie daje zastosować niekompletnego filmu.
Zapis i odczyt obu graph-candidate.stmsession zachował graf oraz brak aktywnego
aligned. Pełne wyniki wcześniejszych metod:
[REG-13 i jego historyczne bazy](lightglue-results.md). LightGlue miał
odpowiednio 41 i 3 składowe, więc AKAZE rozłączył te filmy jeszcze silniej.

## Kompletny cykl na znanym filmie

Dodatkowy known.mpp: osiem wycinków 256 × 256 z deterministycznej sceny,
seed 8085, znane pozycje zapisane w known.json.
Łańcuch odtworzył wszystkie pozycje dokładnie; LS i Huber różniły się od
nich maksymalnie o 1,78e−15 px (precyzja obliczeń).
To wzorzec bez tearingu i zmian obiektów, nie model pełnej złożoności STM.

Automatycznie sprawdzono: oba solvery, jawne zastosowanie, korektę o 1 px,
cofnięcie do poprzedniego wyniku, samodzielne sesje, MPP oraz AVI MJPG/FFV1.
Osiem klatek z poprawionej sesji wyeksportowano przy 5 kl./s, rozmiar
262 × 262 (dopełnienie do parzystych wymiarów kodeka).
save_avi ponownie dekoduje wynik; dla FFV1 sprawdza identyczny raster.
Znacznik session_mpp_avi_manual_roundtrip w odziedziczonym harnessie oznacza
wykonanie operacji korekty ręcznej przez API, **nie ręczny odbiór GUI**.

## Czas i RAM

Jedno wykonanie na tym samym lokalnym Linuksie, netcat, cztery wątki
OpenCV w harnessie. Bez rozgrzewki/powtórzeń i przedziałów niepewności.
Czas nie obejmuje odczytu wejść i późniejszego zapisu sesji, o ile wiersz
dotyczy samego grafu lub łańcucha. RAM to maksimum RSS całego procesu
od uruchomienia, zawierające także wcześniejsze etapy i wczytane oryginały.

| Próba AKAZE | Czas ścienny [s] | CPU procesu [s] | Maksimum RSS [MiB] |
| --- | ---: | ---: | ---: |
| 18 par STM | 0.1627 | 0.4039 | 417.3 |
| 9 par wzorcowych | 0.0480 | 0.2346 | 110.9 |
| movie_4 chain | 0.0111 | 0.0216 | 259.7 |
| movie_4 graph | 4.1968 | 12.3251 | 299.9 |
| movie_8 chain | 0.0292 | 0.0614 | 274.3 |
| movie_8 graph | 4.0483 | 9.6636 | 312.2 |
| known chain | 0.0383 | 0.1615 | 114.0 |
| known graph | 0.0715 | 0.2026 | 125.8 |

Krótki czas odmowy nie jest czasem poprawnej rejestracji filmu.
Nie wyciągamy wniosków o przewadze CPU/GPU ani minimalnej pamięci stanowiska.

## Zakres odbioru

[Instrukcja ręczna](akaze-manual.md) używa known.mpp do pełnego cyklu
i cpu.mpp do kontrolowanej odmowy. Rzeczywisty OpenCV, testy Qt offscreen,
sesje bez runtime i automatyczne dekodowanie AVI sprawdzono.
Ręczna jakość GUI/VLC, Windows 11 i stanowisko referencyjne pozostają
niezweryfikowane. AKAZE pozostaje dodatkową metodą CPU; dotychczasowe
domyślne metody i wyniki odbioru innych modeli są bez zmian.
