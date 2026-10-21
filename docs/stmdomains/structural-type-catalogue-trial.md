# Próba wspólnego katalogu typów struktury

Data: 2026-10-21. [Zadanie 11](issues/11-structural-type-catalogue.md).
Źródła: `prototype/stmdomains-types`, commit **`f2608c7`**. Nie scalać prototypu
do aplikacji. Dokumentacja: `domains/structural-type-catalogue`.

## Wynik

Wykonano dziewięć wariantów katalogu na 18 klatkach TTMAPP i osobno na
19 kontrolach syntetycznych. **Eksperyment zakończony; metody nie zatwierdzono.**
Użytkownik doprecyzował, że BLACK/RED/YELLOW oznaczają **głównie różne orientacje
tej samej sieci**. Nie oczekujemy trzech różnych typów odpowiadających kolorom.
Nie dopasowujemy liczby grup ani wag do rozdzielenia tych etykiet.

Na dostępnych próbkach prostych kontroli cechy kątowe, rozstaw i zróżnicowanie
odległości sąsiadów rozdzielają kwadrat 16 px, kwadrat 20 px, prostokąt 16×20 px
i sieć trójkątną 16 px, zachowując typ po obrocie i zmianie rozstawu o 2%.
Na TTMAPP ten wariant tworzy jednak 34 grupy kandydatów i zmienia podział po
skróceniu zakresu. To nie dowód istnienia 34 typów. Pojedynczy defekt, brak
detekcji i losowy układ nadal mogą tworzyć dodatkowe grupy.

Warianty obrazowe są niezależne od braków centrów, ale zależą od rozmiaru
okna, fazy wzoru i estymacji okresu. Potrafią odrzucić regularną sieć oraz
przepuścić szum. Samo połączenie obu źródeł nie rozstrzyga ich sprzeczności.
Następna próba powinna najpierw ustabilizować lokalne sąsiedztwo i ocenę
wystarczalności danych, a dopiero potem grupować cechy w katalog.

## Dane i zakres referencji

Użyto [niezmienionych konserwatywnych wnętrz](partial-domain-reference-audit.md):
54 regiony, po 18 BLACK/RED/YELLOW, klatki 250–254 i 256–268. Nie ma pary PNG
dla klatki 255. Numery klatek są od 1. Część poza ramkami jest nieoznaczona.
Kreska, pas domknięcia i dodatkowy margines 3 px raw są wyłączone.
Cały obszar używany do obliczenia cechy musi mieścić się w jednym wnętrzu
i w oryginalnym polu obrazu. Nie dopuszczamy pobierania obrazu spoza referencji.

Obraz pochodzi z MPP, centra z zapisu MolTrack; nie z ręcznie pokolorowanego PNG.
Raw ma 256×256 px, płótno rejestracji 480×408 px, PNG 960×816 px. Przeliczenie
centrów korzysta z zapisanych przesunięć i paddingu LTRB 224,139,0,13.
Wcześniejszy audyt odtworzył wszystkie 18 czystych PNG bez różnicy pikseli.
Obecny generator ponownie sprawdził hashe MPP, sesji, 36 PNG oraz geometrię
wejściowych masek; hashe wszystkich NPZ zapisał w pochodzeniu wyniku.

| Wejście | SHA-256 |
| --- | --- |
| `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP` | `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66` |
| `data/TTMAPP/detection_full.moltrack.json` | `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e` |
| Manifest `.scratch/partial-domain-reference` | `30eeda806622d428900d60f6391e749a66a154f53aeb40c8d8f48097c48ef637` |

Kontrole obejmują obroty 17°/43°, rozstawy 16/20 px, zmianę +2%, sieci kwadratową,
prostokątną i trójkątną, mały rzadki wzór, ubytki detekcji, fizyczny defekt,
ucięcie brzegiem, losowe centra, szum i płaski obraz. Obrazy syntetyczne to
plamki Gaussa σ=2,2 px z szumem σ=0,015; centra są znane dokładnie. To proste
kontrole geometrii, nie realistyczny model błędów detektora ani obrazu STM.
Rzadki wzór ma ROI 80×80 px zamiast 192×192 px. Stałe ziarna są w źródłach.

## Cechy i parametry

**Centra:** `point135`/`point165`, promień 1,35/1,65 odległości najbliższego
sąsiada; zapytanie obejmuje maksymalnie 12 centrów wraz z badanym. Wymagane
co najmniej trzy sąsiednie centra i pełne koło we wnętrzu z zapasem 1 px.
Momenty `q_m = mean(exp(i·m·θ))`, m=2,4,6, używają kąta z osią y skierowaną
w górę. Do typu trafiają moduły, kąt przechowujemy osobno jako arg(q_m)/m
modulo 360°/m. Takie rozdzielenie modułu i fazy opisuje również
[dokumentacja momentów porządku freud](https://freud.readthedocs.io/en/latest/modules/order.html);
w prototypie oblicza je NumPy, bez biblioteki freud. Rozstaw to mediana
odległości wybranych sąsiadów, dodatkowa cecha to log(P75/P25) tych odległości.

**Obraz:** `fft25`/`fft33`/`fft49`, koliste okno Hanna w wycinku 25/33/49 px.
Usuwamy płaszczyznę dopasowaną wyłącznie z niezerowego obszaru okna. FFT ma
128×128 punktów; dopełnienie zerami zagęszcza próbkowanie widma, nie dodaje
rozmiaru fizycznego okna. Szukamy maksimum średniej radialnej mocy w paśmie
okresów 6–28 px, w 64 przedziałach, po wygładzeniu o 1 przedział. Momenty
kątowe liczymy w pierścieniu wokół maksimum, o półszerokości 0,5/rozmiar okna.
Siatka pomiarów co 8 px na TTMAPP, co 16 px na kontrolach, początek 4 px.
MPP normalizujemy percentylami 2–98. Gamma wpływa tylko na podgląd.

Okres FFT nie jest automatycznie odległością najbliższych molekuł. Kierunek
sieci odwrotnej również nie musi pokrywać się z kierunkiem sieci bezpośredniej:
na kontroli trójkątnej występuje przesunięcie o około 30°. Oceniając obrót,
porównujemy zmianę kierunku w obrębie tej samej definicji. Nakładki q4/q6 są
diagnostyczne; kąt pokazujemy przy odpowiednim module ≥0,25. Brak kalibracji nm.

## Wspólny katalog i stany

Każdy wariant korzysta wspólnie ze wszystkich dostępnych próbek danego zbioru:
18 klatek realnych albo 19 kontroli. Nie miesza tych zbiorów. Metoda
[complete linkage](https://docs.scipy.org/doc/scipy-1.15.2/reference/generated/scipy.cluster.hierarchy.linkage.html)
korzysta z odległości euklidesowej, z
[cięciem według odległości](https://docs.scipy.org/doc/scipy-1.15.2/reference/generated/scipy.cluster.hierarchy.fcluster.html)
1, bez zadanej liczby grup. Wektor zawiera q/(0,20√3), w·log(rozstawu)/0,12
i opcjonalnie log(P75/P25)/0,10. Warianty i wagi są w tabeli wyników poniżej.
Wagi i progi są robocze, nie skalibrowane na niezależnej referencji.

- `measured`: cecha przeszła roboczy próg; nie oznacza rozpoznanego typu.
  Dla centrów max|q|≥0,45. Dla FFT max|q|≥0,25 i maksimum profilu/mediana≥2.
- `insufficient`: brak pełnego okna, sąsiadów, kontrastu (energia <10⁻¹²)
  albo mniej niż dwa oszacowane okresy w oknie. Nie oznacza podłoża ani nieporządku.
- `no_order`: niespełnienie progu porządku. Kontrole wykazują błędy tego
  kryterium, więc nie wolno utożsamiać etykiety z potwierdzonym nieporządkiem.
- `ambiguous` pomiaru: maksimum widma na brzegu badanego pasma.

Medoid jest próbką o najmniejszej sumie odległości do innych członków grupy.
Przypisanie jest niejednoznaczne, gdy różnica odległości do dwóch najbliższych
medoidów <0,15 albo najbliższy medoid nie należy do surowej grupy próbki.
Grupa z mniej niż 5 próbkami lub występująca w mniej niż 2 przypadkach pozostaje
rzadkim kandydatem. Pozostałe są kandydatami, nie zatwierdzonymi typami.
HTML zachowuje surową grupę oraz oddzielnie pokazuje stan przypisania.

Osobny sprawdzian usuwa rzadki przypadek z katalogu i pyta o jego przypisanie:
odległość do najbliższego medoida >1 oznacza `ordered_uncatalogued`, mały odstęp
do drugiego — niejednoznaczność. To diagnostyka zakresu, nie powrót do katalogu
zamrożonego na klatkach referencyjnych.

## Dostępność pomiaru na TTMAPP

Liczby dotyczą lokalnych próbek cech, nie molekuł przypisanych do domen.
Różne rodziny próbkują w różnych miejscach, więc ich odsetki nie są rankingiem
trafności. Dostępne okna często nakładają się i nie są niezależnymi obserwacjami.

| Rodzina | Miejsca próbkowania | Pomiar | Za mało danych | Brak porządku według progu | Pomiar BLACK / RED / YELLOW |
| --- | ---: | ---: | ---: | ---: | --- |
| point135 | 1678 | 542 | 1131 | 5 | 511 / 0 / 31 |
| point165 | 1678 | 415 | 1250 | 13 | 398 / 0 / 17 |
| fft25 | 4464 | 1410 | 2896 | 158 | 1292 / 10 / 108 |
| fft33 | 4464 | 1368 | 3066 | 30 | 1293 / 0 / 75 |
| fft49 | 4464 | 684 | 3750 | 30 | 680 / 0 / 4 |

RED daje jakikolwiek pomiar tylko dla fft25: 10 próbek z 4 spośród 18 wnętrz.
Mediana promienia największego wpisanego koła wynosi tam 13 px, wobec 45,14 px
dla BLACK i 22,81 px dla YELLOW. Poszerzanie okna nie rozwiązuje tego ograniczenia.
Nie można rzetelnie porównać wszystkich trzech orientacji, rozszerzając pomiar
poza wskazaną referencję albo nazywając brak pomiaru nieporządkiem.

## Co rozstrzygają kontrole

| Próba | Obserwacja |
| --- | --- |
| Same momenty kątowe | Łączą kwadraty 16/20 px i prostokąt; brakuje informacji o rozstawie. |
| Momenty + mediana rozstawu | Rozdzielają kwadraty 16/20 px, lecz prostokąt nadal trafia do grupy kwadratu 16 px; jego 63 próbki są niejednoznaczne. |
| Dodanie log(P75/P25), `point_geometry` | Cztery proste struktury mają różne grupy; wszystkie dostępne próbki obrotów i zmiany +2% zachowują oczekiwany typ. |
| Promień 1,65 zamiast 1,35 | Dołączenie kolejnej powłoki odrzuca wszystkie 81 wcześniej dostępnych próbek kwadratu 16 px przez próg porządku. |
| Usunięcie 75% centrów | `point_geometry`: tylko 4 dostępne próbki, rozrzucone po 3 grupach. FFT pozostaje identyczne dla tego samego obrazu. |
| Pas brakujących detekcji | `point_geometry`: 36 próbek w 2 grupach, tylko połowa pozostaje w grupie wzorca. |
| Jeden fizyczny defekt | `point_geometry`: 80 próbek, 95% w grupie wzorca, pozostałe tworzą drugą grupę. FFT49: 96,3% z 81 próbek pozostaje w grupie wzorca. |
| Ucięcie brzegiem obrazu | Wszystkie 45 dostępnych próbek `point_geometry` zachowują grupę wzorca; pozostałe nie mają pełnego sąsiedztwa. |
| Rzadki wzór trójkątny 20 px | `point_geometry`: tylko 1 z 19 centrów daje pomiar, zachowany jako rzadki kandydat. Po wyłączeniu tego przypadku z katalogu jest poza katalogiem, odległość 1,69. To za mało na uznanie typu. |
| Losowe centra i plamki | `point_geometry`: 18 pomiarów tworzy 15 grup, w tym 17 rzadkich przypisań i 1 niejednoznaczne. Progi przepuszczają przypadkowy lokalny porządek. |
| Sam szum | FFT49 przepuszcza 12 z 81 okien mieszczących się w referencji; 63 kolejne pozycje nie mają pełnego okna. Odmowa nie jest wiarygodna. |

Cecha `point_geometry` powstała po zaobserwowaniu pomyłki prostokąta na tych
kontrolach. Jest to rozwój i sprawdzenie zachowania na znanych przykładach,
**nie niezależna walidacja ani 100% skuteczności na obrazach**.
Przykładowo kwadrat 16 px ma 81 dostępnych pomiarów ze 144 centrów we wnętrzu.

FFT49 zachowuje grupę dla obrotów kwadratu 16 px i sieci trójkątnej 16 px,
ale dla kwadratu 20 px daje dwie grupy, a po obrocie 17° jeszcze inną grupę.
FFT33 odrzuca wszystkie 100 pełnych okien nieobróconego kwadratu 16 px, podczas
gdy po obrocie 17° dopuszcza 35 próbek. Małe okno i robocze progi mogą więc
mylić zmianę orientacji z zanikiem porządku lub zmianą struktury.
FFT49 dla rzadkiego wzoru daje cztery pomiary; po wyłączeniu go z katalogu dwa
trafiają poza katalog, a dwa do istniejących grup. Rozdzielenie nie jest pełne.

## Stabilność katalogu

Porównujemy, czy **te same pary próbek** pozostają razem, a nie numery grup.
Tabela dotyczy katalogu TTMAPP: pełne 18 klatek kontra pierwsze 9 klatek
(250–254, 256–259), oceniane na wspólnych próbkach. Jaccard dotyczy zbiorów
par połączonych w którymkolwiek wariancie; uzupełnia odsetek zmienionych relacji,
który może być mały przy przewadze par od początku rozdzielonych.

| Wariant | Grupy w pełnym zakresie | Zmienione relacje par | Jaccard par połączonych |
| --- | ---: | ---: | ---: |
| point_shape, bez rozstawu | 11 | 12,05% | 0,746 |
| point_scale, waga rozstawu 1 | 21 | 21,43% | 0,352 |
| point_geometry, dodatkowe różnice odległości | 34 | 11,29% | 0,389 |
| point_wide, promień 1,65 | 12 | 5,04% | 0,926 |
| fft_shape, okno 33, bez okresu | 10 | 17,18% | 0,513 |
| fft25_scale, waga okresu 1 | 21 | 8,70% | 0,393 |
| fft33_scale, waga okresu 1 | 23 | 9,75% | 0,591 |
| fft49_scale, waga okresu 1 | 13 | 19,09% | 0,530 |
| fft33_weight2, waga okresu 2 | 28 | 10,88% | 0,522 |

Odwrócenie kolejności i pięciokrotne powielenie próbek pierwszej klatki TTMAPP
nie zmieniło surowych podziałów (0% zmienionych relacji we wszystkich wariantach).
Nie oznacza to dowiedzionej odporności na liczebność: medoidy i stany odmowy
nie są objęte tym sprawdzianem, a niejednakowych wag klatek nie wprowadzono.
Na kontrolach wariant bez pomiarów pierwszego przypadku ma pustą próbę powielenia.
Powtarzanie tej samej klatki nie jest dodatkową niezależną referencją.

Zapisano także wyniki progów 0,75 i 1,25. Na przykład fft33_scale zmienia
liczbę grup TTMAPP z 23 na odpowiednio 36 i 12. Mniejsza liczba grup sama
nie świadczy o lepszym katalogu. Porównanie znaczeń wymaga cech reprezentantów,
lokalizacji próbek i dostępności danych, które są widoczne w HTML i JSON.

## Odtworzenie i inspekcja

Otwórz lokalny plik:
`/home/rlew/projekty/NEtCAT-domains/.scratch/type-catalogue-trial/index.html`.
Warto zacząć od „Prostokąt i różnice odległości”, potem obejrzeć „Wąski RED — 251”,
„Szersze sąsiedztwo” i „Sam szum”. Można wybrać dowolne dwie metody oraz
nakładkę grup, rozstawu lub kierunku q4/q6. Kolory grup nie są kolorami referencji.

Na gałęzi prototypu, z jej katalogu głównego, w środowisku `netcat`:

```bash
python stmdomains/prototypes/type_catalogue.py \
  --session /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/detection_full.moltrack.json \
  --mpp /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  --reference /home/rlew/projekty/NEtCAT-domains/.scratch/partial-domain-reference \
  --review /home/rlew/projekty/NEtCAT-domains/data/ttmapp_frames_250_268_domain_review \
  --out /tmp/netcat-type-catalogue-reproduction
```

Python 3.12.12, NumPy 2.2.5, SciPy 1.15.2. Interpreter lokalny:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Źródło generatora SHA-256 `88445ad081def5e1d2cf8344f60ecf284773d83bed3882616775c186f4b87a95`;
szablon HTML `558e621e53a44d8dd5922ff1b2fcc3ccf59eb31d93c81ff07ad79bf89ecccd64`.
Hashe pozostałych modułów i NPZ znajdują się w `results.json`.

Obok HTML zapisano pełny JSON, CSV dostępności/cech/przypisań, skrócone
zestawienie JSON oraz wyniki inspekcji i zrzuty. Generator raportował 7,10 s
do przygotowania HTML/JSON, przed eksportem CSV; szczyt RSS 618,43 MiB.
HTML ma 16 068 171 B, JSON 24 476 803 B. To jednorazowy pomiar tej próby,
nie budżet pamięci, czasu ani anulowania docelowej aplikacji.

Sprawdzenia wykonane przez agenta: 7014 dostępnych pomiarów z całym wsparciem
we właściwym wnętrzu i polu; 349 grup ze średnicą ≤1 i zgodnymi przypisaniami;
81 pomiarów FFT49 niezmienionych po zastąpieniu całego otoczenia referencji
losowymi wartościami. Cechy FFT są identyczne po usunięciu samych centrów.
QtWebEngine: 37 przypadków, 9 wariantów, 26 kroków scenariuszy, wybory,
gamma, nakładki, nawigacja, reset i brak wyniku; bez błędów JavaScript.
Obejrzano zrzuty rzeczywistych danych, prostokąta i kierunków. To inspekcja
eksperymentu; nie uruchamiano testów aplikacji ani nie wykonano odbioru przez użytkownika.

## Co pozostaje przed przyjęciem metody

Do [odbioru metod](issues/13-method-acceptance.md) przekazujemy konkretne luki:
stabilne wybieranie pierwszej powłoki sąsiadów, odróżnienie ubytków detekcji
od zmiany sieci, pomiar okresu odporny na orientację/fazę przy małym oknie,
odmowa na szumie bez odrzucania regularnej sieci i porównanie znaczenia katalogu
po zmianie zakresu. Obecne referencje wystarczą do dalszych lokalnych prób;
nie żądamy teraz kolejnych oznaczeń. Dokładna ocena orientacji w wąskim RED
może wymagać innego sposobu pomiaru albo dopiero później dodatkowego przykładu.

Zadanie 12 osobno bada granice niedopasowania; tutaj nie segmentowano granic
ani nie śledzono domen. Zakończenie kroku 11 nie czeka na 12, nie zatwierdza
algorytmu i nie zamyka pytań 04 ani 13. Produkcyjna aplikacja pozostaje bez zmian.
