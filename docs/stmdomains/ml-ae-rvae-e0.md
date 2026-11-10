# E0 — przypadki domen i audyt dostępnej referencji

2026-11-10. Gałąź `ml_domain`, baza `308b455`, środowisko `netcat`.
**E0 wykonane:** tabela przypadków, audyt danych, role grup i lista obszarów
do przeglądu. Nie wykonano nowych anotacji ani eksperymentów E1–E7.
[Plan](ml-ae-rvae-experiments.md),
[manifest z pochodzeniem i współrzędnymi](ml-ae-rvae-e0-reference-manifest.json).

## Wynik i gotowość następnego kroku

**E1 może ruszyć na obecnych danych.** Do mocnej oceny granic i nadzorowanego
E7 nadal potrzebne są przejrzane lokalne relacje oraz audyt rozdzielenia
fizycznych miejsc. To konkretna potrzeba, nie wymaganie dużego zbioru masek.

Potwierdzono 24 przygotowane obrazy jednej akwizycji, 18 par ręcznych/czystych
PNG i 54 konserwatywne wnętrza. Odtworzenie wszystkich 18 czystych PNG dało
różnicę **0/255**, a ponowna ekstrakcja kresek dała **identyczne 18 masek raw**.
Nie zmieniono źródłowych obrazów, oznaczeń, modeli ani etykiet kontroli.

## Przeglądarka E0

Otwórz lokalny plik:

`.scratch/ml-e0-20261110-reviewed/index.html`

Z katalogu repozytorium można użyć:

```bash
xdg-open .scratch/ml-e0-20261110-reviewed/index.html
```

Samodzielny HTML zawiera **34 przykłady: 24 obrazy STM i 10 ilustracji
syntetycznych**. Wybór klatki, poprzednia/następna, suwak i przełączniki
centrów, wnętrz oraz proponowanych ROI. Nie wymaga serwera ani treningu.
Domyślnie pokazuje TTMAPP259. Obraz i centra mają wspólne współrzędne raw.

- R1/R2… to ID istniejących regionów danej klatki, nie wynik AE/rVAE.
- Kolor centrum wynika z jego położenia w konserwatywnym wnętrzu; nie jest
  nową ręcznie zatwierdzoną etykietą molekuły. Szare centra są nieoznaczone.
- Nazwy BLACK/RED/YELLOW są historycznymi etykietami referencji, bez przypisania
  dokładnych kątów lub obowiązkowych klas typu. BLACK pokazano na niebiesko
  dla czytelności, pozostałe dwa kolory odpowiadają nazwom.
- Pomarańczowe prostokąty są propozycjami obszarów do przeglądu. Nie są domenami.
- Na syntetykach pokazano prawdę generatora poza wyłączonym pasem granicy;
  w przykładach o niewystarczających danych nie wymuszono lokalnej etykiety.

Odbiór ręczny: przejść suwakiem między klatkami, wyłączyć wszystkie warstwy,
następnie włączyć centra i wnętrza. Obejrzeć 251, 259 oraz parę „Rzeczywista
przerwa” / „Brak samych oznaczeń”. Obrazy tej pary mają różny sygnał w pasie,
choć pokazane centra są takie same. „Dwa rzędy — nierozstrzygnięte” musi
pozostawać bez lokalnego przypisania domeny. Odbiór użytkownika nie był
jeszcze wykonany; przeprowadzono sprawdzenie techniczne opisane poniżej.

## Tabela przypadków celu

| Przypadek w galerii | Oczekiwane znaczenie | Ograniczenie |
| --- | --- | --- |
| Jedna sieć | Jedna domena | Idealizowany syntetyk, nie symulacja całego STM. |
| Dwie orientacje | Dwie domeny tego samego typu, 0°/27° | Typ nie jest ID instancji. |
| Granica przesunięcia | Dwie domeny; tylko prawa połowa przesunięta o 4 px w Y | Jednakowy kąt nie znosi granicy niedopasowania. |
| Przesunięcie początku wycinka | Jedna domena zachowuje ID | Brzeg kadru nie jest nową granicą wewnętrzną. |
| Rzeczywista przerwa | Dwie domeny, pas bez molekuł w obrazie | Prawda dotyczy tego generatora. |
| Brak samych oznaczeń | Jedna domena, sygnał sieci nadal obecny | Brak centrów nie dowodzi braku materiału. |
| Niezależne rzędy | Zachowany negatyw wspólnej sieci 2D w całym polu | Losowe fazy mogą dawać przypadkowe lokalne dopasowanie. |
| Zbyt małe pole | Brak dostatecznych danych, a nie nieporządek | Generator zna jedną sieć; pole ma 20×20 px. |
| Dwa rzędy ze znanej sieci | Znane pochodzenie jednej sieci, niewystarczające lokalne wsparcie | Crop 180×24 px nie jest fizycznym płatem na podłożu. |
| Dwa rzędy z niezależnych rzędów | Lokalnie nierozstrzygnięte | Nie przenosimy automatycznie negatywnej etykiety całego pola. |

Pierwszych osiem przykładów pochodzi z istniejących kontroli, seed 920001.
Sprawdzono hashe wejścia i prawdy. Dwa ostatnie są wyłącznie ilustracyjnymi
wycinkami, po 30 centrów; nie rozszerzają benchmarku o nowe rozstrzygnięte
etykiety. Źródłowe etykiety pozostały bez zmian. Wszystkie te przypadki są
materiałem rozwojowym, nie nowym niezależnym testem.

Realny przykład wąskiego obszaru to czerwona referencja klatki 251,
bbox jej wnętrza raw `[227,89,243,125]`, 119 pikseli. Nie potwierdza dokładnie
dwóch rzędów ani tarasu. Kontrast sam nie dowodzi uskoku wysokości.
Podstawy interpretacji: [decyzja 02](issues/02-order-types-and-domains.md),
[audyt dopasowania dwóch rzędów](fit-quality-diagnosis.md).

## Dostępna referencja i brakujące informacje

Źródła: `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`,
`data/TTMAPP/detection_full.moltrack.json` oraz
`data/ttmapp_frames_250_268_domain_review/`. Hashe MPP i MolTrack są zgodne
z wcześniejszym audytem i zapisane w manifeście E0.

| Zasób | Potwierdzona zawartość | Dozwolona interpretacja |
| --- | --- | --- |
| Pilot obrazów | 24 klatki: 1,50,100,150,200 i 250–268; 6730 centrów | Centra molekuł z MolTrack; nie etykiety domen. |
| Ręczne pary PNG | 18 klatek: 250–254,256–268; brak 255 | Przybliżone granice wybranych domen, zaakceptowane do prób 2026-10-21. |
| Konserwatywne wnętrza | 54 regiony; po 18 BLACK/RED/YELLOW | Pochodne ręcznych kresek z marginesem 3 raw px, nie dokładne granice. |
| Centra w klatkach z referencją | 5452, z czego 1678 wpada do wnętrz | Pomocnicze przypisanie przez zawieranie centrum; nie 1678 niezależnych próbek. |
| Dokładne granice i jawne pary sąsiadów | Nie znaleziono zatwierdzonego zestawu | Do przygotowania przed rozstrzygającą oceną granic i E7. |
| Niezależny test | Brak w tym pilocie | Inne lokalne materiały nie zostały włączone ani zwalidowane w E0. |

Klatka 252 ma dwa wydobyte regiony, 258 cztery; ID regionu jest lokalne
dla klatki. Kolor nie łączy wszystkich jego wystąpień w jedną domenę.
Dokładne kąty, tolerancja brzegu i jednorodność każdego wnętrza nie są
zatwierdzone. Nie liczymy globalnego IoU ani fałszywych domen poza ramkami.
Jednostką geometryczną pilota jest px; zaufanej skali nm nie potwierdzono.

Dodatkowy, ograniczony census `data/` i `.scratch/` objął **29 projektów**
`.stmdomains`. Jedyny zapis w `data/`, `detection_full.moltrack.stmdomains`,
zawiera automat K5 klatki 268 bez ręcznej warstwy. Korekty TTMAPP znalezione
w `.scratch/stmdomains-ui-24/` i `stmdomains-ui-26/` są udokumentowanymi
próbami wykonawcy, nie nową zatwierdzoną referencją użytkownika.
Nie wnioskowano o niezapisanym GUI ani plikach poza sprawdzonymi katalogami.
Źródłowy MolTrack zawiera też 3268 rekordów `origin=manual`, ale dotyczą one
molekuł, nie ich przynależności do domen.

## Role danych i kolejka przeglądu

Jedna wspólna grupa akwizycji: `ttmapp-8fbbfa5d515a`. Wszystkie obecne dane
są rozwojowe; **`independent_test=[]`, `supervised_split_ready=false`**.
Historyczny podział z 20/21/21a zachowano jako pochodzenie, bez zmiany
znaczenia dawnych raportów. Modele transdukcyjne widziały wszystkie 24 pola.

| Kandydaci ROI | Rola obecnie | Centra z pełnym wsparciem 70 px w ROI |
| --- | --- | ---: |
| Klatka 1, pas expanded X[328,480] | Kandydat do uczenia odczytu; relacje do przeglądu | 71 |
| Klatka 50, ten sam pas | Ta sama grupa co klatka 1 | 10 |
| Klatka 100, ten sam pas | Kandydat ograniczony skalą | 0 |
| Klatka 150, pas expanded X[168,312] | Kandydat do walidacji; relacje do przeglądu | 21 |
| Klatka 200, ten sam pas | Ta sama grupa co klatka 150 | 10 |
| Klatka 251, wąska referencja | Diagnostyka niepewności | 0 |
| Klatka 258, styki regionów | Diagnostyka granic | 29 |
| Klatka 259, górne styki | Diagnostyka granic | 23 |
| Klatka 259, nieoznaczony dół | Diagnostyka brakujących oznaczeń | 25 |
| Klatka 268, nieoznaczony dół | Diagnostyka brakujących oznaczeń | 32 |

Współrzędne raw/expanded, klatki i status każdego z **10 ROI** są w manifeście
i galerii. To kolejka przeglądu, nie zestaw etykiet. 70 px oznacza największe
okno 64 px plus przesunięcie ±2 i margines interpolacji 1 px. W klatce 100
obszar ma około 62 px szerokości: nie mieści takiego okna. Liczba wspartych
centrów nie gwarantuje dostępności obu rodzajów relacji lub granicy.

Bufor rejestracji 8 px nie jest skalibrowanym błędem; większość klatek ma
niski poziom ufności rejestracji. Przed nadzorowanym E7 trzeba przejrzeć
relacje i sprawdzić, czy grupy rzeczywiście nie współdzielą fizycznych miejsc.
Klatki 250–268 pozostają razem w `late-review`; nie dzielić ich czasowo
między uczenie i walidację. Późne obrazy nie sięgają dawnego pasa train.
Nowe oznaczenia w późnych klatkach mogą wspomóc diagnostykę, ale ich użycie
do uczenia i walidacji wymaga osobnego jawnego podziału przestrzennego.

## Odtworzenie i sprawdzenia

```bash
conda activate netcat
python -m stmdomains.experiments.e0_audit --out .scratch/ml-e0-new
python -m stmdomains.experiments.e0_check_gallery \
  .scratch/ml-e0-new/index.html --out .scratch/ml-e0-new/browser \
  --uncertain-id two_rows_uncertain
```

Generator wymaga nowego katalogu i istniejących źródeł opisanych powyżej;
nie nadpisuje poprzedniego audytu. Wersjonowany manifest jest kopią wyniku
końcowego. Lokalne obrazy, HTML i pełny JSON galerii pozostają poza Git.
Osobny census projektów: `.scratch/ml-e0-project-census.py` i `.json`;
jego SHA-256 i zakres zapisano w manifeście.

W netcat: 24 pliki analizy sprawdzone przez hashe i walidację geometrii,
18 par PNG zgodnych z hashami, 18 dokładnych odtworzeń PNG, 18 identycznych
ponownych ekstrakcji masek, osiem zgodnych kontroli syntetycznych. Źródłowe
hashe nie zmieniły się. Kompilacja trzech modułów Python poprawna.
QtWebEngine: **13 sprawdzeń PASS**, dwa zrzuty obejrzane, zero błędów JS.
Pierwsze uruchomienie Chromium zablokowała piaskownica procesu; ponowione
lokalne sprawdzenie poza nią zakończyło się poprawnie. Bez odbioru użytkownika
oraz bez uruchamiania produkcyjnego GUI, modeli lub treningu.

Niezależny przegląd potwierdził role danych, rozdzielenie etykiet od membership
centrum, zgodność odtworzenia i interpretację cropów. Trzy moduły mają po
mniej niż 1000 linii. Nie zmieniono kodu produkcyjnej aplikacji ani zależności.
Procedury `experimental-design` i `scientific-critical-thinking` wykorzystano
do kontroli zależności i zakresu wniosków; pochodzenie:
Kassis i in. (2026), [Scientific Agent Skills](https://doi.org/10.48550/arXiv.2609.00065).
