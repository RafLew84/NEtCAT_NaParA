# Pokrycie na częściowej referencji domen TTMAPP

Data: 2026-10-21. Dalsza próba [zadania 10](issues/10-coverage-and-scale.md),
wykonana po akceptacji obecnego zbioru przez użytkownika.

## Wynik

**Warianty z centrów zachowują większość oznaczonych wnętrz przy pełnej liście
molekuł, ale zawodzą przy ubytkach detekcji. Proste warianty jasności i lokalnej
amplitudy zmian odrzucają znaczną część znanego materiału.** Nie wybrano metody
produkcyjnej. To pomiar zachowania materiału w referencji, nie trafności całej
maski ani jakości rozdzielania typów lub domen.

Interaktywny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/coverage-partial-trial/index.html`.
W zakładkach „Oznaczone wnętrza”, „Wpływ skali”, „Ubytki oznaczeń”, „Jasność
i kontrast” i „Granica tej oceny” można przejść przez konkretne przykłady.
Wybór dwóch metod oraz klatki działa także niezależnie od scenariuszy.
Zielony to zachowany materiał we wnętrzu, różowy — odrzucony. Pełna maska
poza referencją jest dostępna przełącznikiem; nie ma tam oceny poprawności.

## Dane i zakres oceny

- Wszystkie **18 klatek** dostarczonej referencji: 250–254 i 256–268.
  Brak 255. **54 robocze wnętrza regionów**, po 18 etykiet BLACK, RED i YELLOW;
  nie są to 54 niezależne fizyczne domeny ani trzy zatwierdzone typy sieci.
- Maski przygotowano wcześniej zgodnie z [audytem](partial-domain-reference-audit.md).
  Usunięto kreski/pas domykania i dodatkowy margines 3 px raw. Ten margines
  nie jest skalibrowaną tolerancją fizycznej granicy. Wnętrza w tej próbie
  pozostawiono niezmienione.
- Każda metoda otrzymała pełny czysty obraz MPP **256×256 px**, bez paddingu.
  Ręczne etykiety są użyte dopiero przy liczeniu miar. Kolorowe PNG nie są
  wejściem algorytmu. Centra pochodzą z `detection_full.moltrack.json`,
  przeliczone z zapisanej geometrii; w oryginalnych klatkach jest ich 290–318.
- Cztery dodatkowe przypadki wykorzystują niezmieniony obraz i referencję
  klatki 250: pozostaje 25% centrów, usunięto centra pasa x=88–168 px,
  pozostają trzy centra albo nie ma żadnego. Losowanie: seed 20261021;
  trzy centra to pierwszy, środkowy i ostatni element źródłowej listy.
- Każdy z 22 przypadków ma 10 wariantów i kontrolę „całe pole jako materiał”.
  Łącznie 238 masek i 4 jawne braki wyniku przy braku centrów.

Poza oznaczonymi wnętrzami nie ma etykiet materiału/podłoża. Nie liczymy tam
fałszywych wykryć, globalnego IoU, błędu powierzchni ani dokładności granic.
Podział na wyspy lub domeny nie jest oceniany z granic wycinków referencyjnych.
Rejestrację odtworzono, nie przeliczano; jej niska pewność pozostaje ograniczeniem.

## Parametry zamrożone przed próbą

Ponownie użyto `segment` z pierwszego [pilotażu pokrycia](coverage-and-scale-pilot.md),
bez dostrajania progów do ręcznych ramek:

- Obraz: percentyle 2–98, obcięcie do [0,1]; filtry Gaussa z `reflect`.
  Gamma służy wyłącznie oglądaniu wyniku.
- Gęstość centrów: sigma = 0,45 lub 0,65 × rozstaw; próg 20% maksimum pola.
  Rozstaw lokalny = mediana najbliższego sąsiada. Wspólny = **12,2222459051 px**,
  odtworzony dokładnie z tych samych sześciu klatek co w pierwszej próbie
  (indeksy 0,39,40,120,200,267). Nie jest niezależną kalibracją fizyczną.
- Morfologiczny Chan–Vese: 45 iteracji, lambda1=lambda2=1, start powyżej mediany
  cechy. Jasność po Gaussie sigma 3 lub 6 px, wygładzanie konturu 2; osobno
  sigma 3 i wygładzanie 4 oraz wybór ciemnej fazy przy sigma 3 / wygładzaniu 2.
- Lokalna amplituda zmian: `sqrt(G_sigma((G_1(I)-G_3(I))**2))`, sigma 3 lub 6 px,
  ten sam Chan–Vese z wygładzaniem 2; faza większej amplitudy jako kandydat
  materiału. To prosta cecha kontrastu, nie detektor okresowości sieci.
- Kontrola całego pola: stała maska true, celowo bez detekcji.

Nie wykonywano implementacji Gibou–Fedkiwa. Ta próba nie ocenia jego skuteczności.

## Miary i wyniki na oryginalnych oznaczeniach

Dla wnętrza R i maski M: **zachowane = |M ∩ R| / |R|**. Podajemy liczby
zachowanych/utraconych pikseli dla każdego regionu oraz całej oznaczonej części
klatki. Regiony są rozłączne; obszary z etykietą zero są wyłączone.
Brak propozycji to null / puste pole CSV, nie wartość 0%.

Poniższe mediany dotyczą **18 klatek z oryginalnymi oznaczeniami**, bez kontroli
ubytków. Każda klatka ma równy udział w medianie; nie sumujemy powtarzającej się
powierzchni jako materiału całej próbki. „Maska / całe pole” opisuje rozmiar
propozycji, nie potwierdzone pokrycie.

| Wariant | Mediana zachowanych wnętrz klatki | Zakres klatek | Mediana maski / całe pole |
| --- | ---: | ---: | ---: |
| Centra: skala z tej klatki × 0,45 | 97.58% | 95.43–99.05% | 85.23% |
| Centra: skala z tej klatki × 0,65 | 99.48% | 97.80–100.00% | 93.98% |
| Centra: wspólna skala × 0,45 | 97.71% | 95.62–99.07% | 85.74% |
| Centra: wspólna skala × 0,65 | 99.51% | 97.80–100.00% | 94.11% |
| Jasna warstwa: rozmycie 3 px | 45.00% | 36.04–54.24% | 47.53% |
| Jasna warstwa: rozmycie 6 px | 39.78% | 32.12–51.49% | 45.77% |
| Jasna warstwa: wygładzanie konturu 4 | 39.92% | 33.88–49.77% | 45.87% |
| Ciemna warstwa: rozmycie 3 px | 55.00% | 45.76–63.96% | 52.47% |
| Zmiany jasności: okno 3 px | 23.87% | 14.34–43.70% | 40.18% |
| Zmiany jasności: okno 6 px | 19.86% | 14.33–47.49% | 43.29% |
| Kontrola: całe pole jako materiał | 100.00% | 100.00–100.00% | 100.00% |

Kolejne klatki tej samej serii są skorelowane. Nie traktujemy ich jako
niezależnego testu; nie wyznaczamy przedziałów ufności z liczby pikseli.
Reguła wspólnej skali obejmuje też klatkę 268. Nie użyto tutaj historycznego
podziału do deklaracji nowego holdoutu ani nie dopasowano klasyfikatora.

Szczegóły pokazują ograniczenia wyników zbiorczych. Poniższe mediany dla
etykiet są liczone po regionach danej etykiety, z równą wagą każdego regionu:

- `fixed45`: mediana zachowania BLACK 99,80%, RED 100%, YELLOW 92,41%.
  Mimo dobrego wyniku ogólnego, RED w klatce 254 zachowuje tylko **286/390 px
  (73,33%)**. To konkretny fragment do oglądania, nie dowód błędu całej granicy.
- `fixed65` zachowuje więcej, lecz maska medianowo zajmuje **94,11% całego pola**.
  Bez etykiet otoczenia nie rozstrzygamy, ile tego rozrostu jest poprawne.
  W YELLOW klatki 260 nadal pomija **280/2331 px** wnętrza.
- `bright3`: mediana zachowania BLACK 29,52%, RED 78,05%, YELLOW 94,63%.
  Jedna faza jasności wybiórczo zachowuje materiał. Zamiana na ciemną fazę
  nie rozwiązuje problemu: mediana YELLOW spada do 5,37%.
- `texture3`: mediany BLACK 28,54%, RED 14,84%, YELLOW 9,99%.
  W YELLOW klatki 260 zostaje **20/2331 px (0,86%)**; `texture6` usuwa całe
  wnętrze RED klatki 254. Sama większa amplituda zmian nie oznacza materiału.

## Kontrolowane ubytki centrów — ten sam obraz klatki 250

| Oznaczenia | Liczba centrów | Zachowane wnętrza, fixed45 | Zachowane wnętrza, texture3 |
| --- | ---: | ---: | ---: |
| Oryginalne | 301 | 97,63% | 15,40% |
| Pozostaje 25% | 75 | 26,30% | 15,40% |
| Luka pasa x=88–168 | 205 | 54,40% | 15,40% |
| Trzy centra | 3 | 2,70% | 15,40% |
| Brak centrów | 0 | brak wyniku | 15,40% |

Wszystkie sześć wariantów obrazowych zachowało identyczne maski w tych
kontrolach. Zmieniła się wyłącznie lista oznaczeń; referencja i obraz są te same.

Przy trzech centrach lokalny rozstaw rośnie z 12,14 do **149,47 px**.
`auto45` obejmuje 96,64% całego pola, a `auto65` **100% pola**; oba zachowują
100% referencji. Wspólna skala ogranicza ten rozrost, ale nie odtwarza brakującego
materiału (fixed65 zachowuje tylko 5,37% wnętrz). To uzasadnia kontrolę podstaw
estymacji i możliwość odmowy pomiaru, nie akceptację skali z trzech punktów.
Nie ustalono uniwersalnego progu minimalnej liczby oznaczeń.

Kontrola całego pola także ma zawsze 100%. Miara na dodatnich referencjach
pozwala wykazać utratę materiału, ale sama nie może wyłonić poprawnej maski.

## Wniosek i dalszy zakres

Próba została wykonana. Obecna referencja wystarczyła do wykazania wybiórczości
faz jasności, słabości prostej cechy amplitudy oraz zależności masek z centrów
od kompletności detekcji. `fixed45`/`fixed65` można zachować jako punkty odniesienia
w dalszych porównaniach, bez uznania ich za gotową metodę pomiarową.

Do następnych lokalnych porównań nadal używamy tego zbioru. Nie prosimy teraz
o dodatkowe klatki. Konkretny nierozstrzygnięty aspekt to nadmiar maski poza
ramkami: jeżeli kolejnym celem będzie wybór rozrostu 0,45 / 0,65 według błędów
w otoczeniu, potrzebne będą etykiety materiału/podłoża w tych właśnie miejscach.
Nie trzeba w tym celu od razu oznaczać całych klatek.

Wynik dotyczy pokrycia, nie rozpoznawania etykiet BLACK/RED/YELLOW ani tworzenia
katalogu typów. Nie przenosimy tych kolorów automatycznie do wyników domen.
Zadanie 10 pozostaje `claimed` do omówienia wyniku i ustalenia dalszego zakresu;
wykonanie tej próby nie czeka na nowe referencje.

## Odtworzenie i sprawdzenia

Źródła: **`prototype/stmdomains-coverage`, commit `e67ca93`**,
`stmdomains/prototypes/coverage_partial.py` i `.html`; polecenie poniżej oraz
`README-coverage-scale.md`. Nie scalać gałęzi prototypu do aplikacji.

```bash
python stmdomains/prototypes/coverage_partial.py \
  --session /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/detection_full.moltrack.json \
  --mpp /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  --reference /home/rlew/projekty/NEtCAT-domains/.scratch/partial-domain-reference \
  --review /home/rlew/projekty/NEtCAT-domains/data/ttmapp_frames_250_268_domain_review \
  --out .scratch/coverage-partial-trial
```

Wejście identyczne jak w audycie:
MPP `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`,
MolTrack `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`,
manifest referencji `30eeda806622d428900d60f6391e749a66a154f53aeb40c8d8f48097c48ef637`.
`results.json` zapisuje także hashe 18 NPZ, kodu i każdej maski, parametry,
metryki i koszty. Obok: CSV klatek i regionów, NPZ masek, zestawienia PNG,
zrzuty podglądu oraz raporty inspekcji. Duże wyniki i dane pozostają poza Git.

Sprawdzono hashe 36 źródłowych PNG, MPP i sesji, odwzorowanie raw/PNG,
wyłączenie kresek i paddingu, sumowanie rozłącznych regionów oraz miary wszystkich
238 zapisanych masek. Dziesięć masek klatki 268 jest identycznych z poprzednim
pilotażem. Brak centrów zachowuje brak wyniku; metoda obrazowa pozostaje niezależna
od listy centrów. Obejrzano zestawienia wszystkich 18 klatek dla fixed45 i texture3.

QtWebEngine: otwarcie HTML, 22 przypadki, 15 kroków scenariuszy, wybór metod,
gamma, nakładki, nawigacja, reset i stan bez wyniku; brak błędów JavaScript
(jedynie wskazówka wydajnościowa odczytu canvas). Obejrzano zrzut podglądu.
Python 3.12.12, NumPy 2.2.5, SciPy 1.15.2, scikit-image 0.25.2 w conda `netcat`.
Pełny generator: **28,49 s**, **590,40 MiB** szczytowego RSS; zawiera odczyt
pełnego MPP i JSON oraz artefakty. Sumaryczny czas wywołań 10 metod dla
22 przypadków: **25,36 s**. HTML: **3 839 863 B**. To pojedynczy pomiar wykonania,
nie benchmark programu produkcyjnego. Nie uruchamiano testów aplikacji.
