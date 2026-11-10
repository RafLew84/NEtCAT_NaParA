# Przegląd dostarczonych paczek STM Domains v0.4

Data: **2026-11-02**. Przegląd na polecenie użytkownika katalogu
`data/new_code`. Obejmuje dokumentację, kod i zapisane wyniki, bez ponownego
uruchamiania analizy. Nie przyjęto nowego detektora ani nie zmieniono protokołu prób.

**Wniosek:** paczki zawierają prototyp klasycznej analizy geometrii molekuł,
wraz z zapisanymi przypisaniami i maskami
domen na naszym TTMAPP. To wartościowy kandydat do osobnego porównania.
Jego wynik nie dowodzi jeszcze przewagi nad próbami 21–26: ma inne kryterium
porządku, zakres danych i sposób wyboru klas. Gotowy podgląd wymaga również
uproszczenia do uzgodnionego widoku końcowych przypisań molekuł.

## Zawartość i tożsamość danych

| Paczka | Rozmiar | Pliki | Zawartość |
| --- | ---: | ---: | --- |
| [stm_domains_source_v04.zip](../../data/new_code/stm_domains_source_v04.zip) | 188 131 B, około 184 KiB | 36 | Kod, konfiguracja, zależności, dokumentacja wersji 0.1–0.4 i pomocnicze ROI. Bez obrazów i zapisanych modeli. |
| [stm_domains_prototype_v04.zip](../../data/new_code/stm_domains_prototype_v04.zip) | 129 770 602 B, około 123,8 MiB | 300 | Ten sam kod oraz wejście 56 klatek, modele PCA/KMeans, wyniki, porównania wersji, PNG, CSV, NPZ i HTML. |

Wspólne 35 plików treści jest identyczne bajtowo. Różni się tylko wspólny
nazwą `MANIFEST_v04.json`, ponieważ opisuje inną zawartość każdej paczki.
Obie mają wewnętrzny katalog `stm_domains_prototype`.

SHA-256 archiwów:

- source: `e764532e520a93770d62ab851aa48110fe9201f0062139835f278e5120aa27eb`;
- prototype: `118bbd803fbe48b32af5d414d0b00060290d60ce24a001ef84e15ca9143aecd0`.

Rozpakowano je osobno do `.scratch/new-code-v04-review/source/` oraz
`.scratch/new-code-v04-review/prototype/`. Oryginalne ZIP pozostały bez zmian.
Lokalny `inventory.json` zawiera identyfikację archiwów i porównanie treści.

Hashe źródeł z `work/expanded/metadata.json` są zgodne z naszymi
`data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP` oraz
`data/TTMAPP/detection_full.moltrack.json`. Nazwa MPP z dopiskiem `(2)`
w dokumentacji paczki nie oznacza innego pomiaru. Pełnych źródeł MPP/JSON
nie ma w ZIP; większa paczka zawiera przygotowany wyciąg.
Sprawdzono również 9697 ID i współrzędnych względem naszej sesji MolTrack:
środki bboxów po odjęciu początku klatki zgadzają się z CSV paczki,
z maksymalną różnicą numeryczną około `2.84e-14 px`.

## Jak działa metoda

1. Odczytuje zapisane centra molekuł i przelicza je do obrazu 256 × 256 px.
   Zachowuje identyfikatory, usuwa z obliczeń dwa bliskie duplikaty,
   pozostawiając oba oryginalne rekordy w eksporcie.
2. Opisuje otoczenie przez histogram odległości i kierunków par molekuł:
   504 cechy, następnie PCA do 24 składowych.
3. Dopasowuje KMeans dla K=2–6 na wspólnym zestawie wybranych klatek.
   W v0.4 wybrano **K=5**, czyli robocze klasy `q`, `w`, `e`, `r`, `t`.
   To pięć rodzajów opisu geometrii, nie pięć domen ani pięć potwierdzonych faz.
4. Osobno ocenia lokalną periodyczność położeń za pomocą koherencji Fouriera
   i kontroli losowych. **Jeden kierunek periodyczności wystarcza.**
5. Łączy zaakceptowane, pobliskie punkty tej samej klasy, uwzględniając
   bariery z obrazu i podobieństwo geometrii. Końcowy fragment ma co najmniej
   osiem centrów; z punktów powstaje przybliżona, spójna maska.

To uczenie klasycznego modelu grupowania, bez sieci AE/rVAE/DINO.
Dopasowanie jest wspólne dla analizowanych klatek, nie jest testem transferu
na oddzielny pomiar. K i parametry wybrano eksploracyjnie po obejrzeniu tej
serii. Same modele są dopasowywane bez ręcznych etykiet klas; cały proces
wyboru rozwiązania korzystał jednak z oceny wizualnej. ROI nie wchodzą
bezpośrednio jako maski narzucające końcową segmentację.

W v0.4 zmieniono K4 na K5 oraz dodano kontrolę odległości Hellingera:
maksimum 0,20 dla łączonej pary i 0,50 między dowolnymi opisami wewnątrz
regionu. Ma to ograniczać połączenie różnych końców przez łańcuch lokalnie
podobnych punktów. Główny efekt rozróżnienia prawych obszarów pochodzi z K5.
Źródła: `README.md`, `analysis_config.json`, `discover_classes.py`,
`assess_order.py`, `geometry_segmentation.py`, `run_discovery.py` w paczce.

## Co zawierają zapisane wyniki

Analiza obejmuje 56 z 268 klatek, numerowanych od 1. Zachowano 9697 rekordów,
9695 aktywnych po deduplikacji. Przypisano **4190 pozycji, czyli 43,2%,
do 122 lokalnych domen**. Sumy dotyczą obserwacji na klatkach, nie unikalnych
molekuł lub domen śledzonych w czasie.

| Klatki | Aktywne pozycje | Przypisane | Udział | Domeny |
| --- | ---: | ---: | ---: | ---: |
| 1–10 | 3051 | 2542 | 83,3% | 56 |
| 120–123 | 980 | 236 | 24,1% | 10 |
| 160–170 | 1805 | 0 | 0% | 0 |
| 200–220 | 805 | 0 | 0% | 0 |
| 259–268 | 3054 | 1412 | 46,2% | 56 |

CSV potwierdzają te liczby. Mianowniki nie odpowiadają częściowym referencjom
174/782 miejsc z prób 21–26. **43,2% to udział przypisań, nie accuracy.**
Brak domen na 32 klatkach nie dowodzi braku fizycznego uporządkowania.

| Zachowany wariant | Przypisane pozycje | Domeny |
| --- | ---: | ---: |
| v0.3 / K4 | 4099 | 99 |
| K5 bez kontroli geometrii | 4199 | 115 |
| v0.4 / K5 z kontrolą geometrii | 4190 | 122 |

Porównanie zapisanych tablic potwierdza, że kontrola geometrii usuwa dziewięć
przypisań i nie dodaje nowych. Zachowuje skład 106 domen wariantu K5-only,
dzieli sześć i zmniejsza trzy. W późnych klatkach pozostaje częściowe scalanie
wskazanych prawych obszarów A/B: na 259 i 261–264 mają wspólną instancję
dla części punktów; na 260 obszar B nie ma końcowych przypisań.
Węższe regiony i większa liczba klas nie usunęły całego problemu.
Źródła: `results_discovery/*summary.csv`, `detections_with_domains.csv`,
`domains.csv`, `work/validation/comparison_metrics.json`, `visual_review_pl.json`.

## Podgląd i zgodność z naszym wymaganiem

Gotowa [przeglądarka 56 klatek](../../.scratch/new-code-v04-review/prototype/stm_domains_prototype/results_discovery/domeny_STM_56_klatek.html)
działa według konstrukcji HTML offline: obrazy i dane są osadzone w pliku.
Są także [przykładowe plansze](../../.scratch/new-code-v04-review/prototype/stm_domains_prototype/results_discovery/selected_examples.png).
Obejrzano zapisane PNG; nie wykonano w tej sesji odbioru interakcji w przeglądarce.

Obecny HTML pokazuje domyślnie obraz i maski w dwóch panelach. Kolor oznacza
klasę `q/w/e/r/t`; różne domeny tej samej klasy mają ten sam kolor, z osobnymi
etykietami np. `e1/e2`. Przełącznik „Wstępne klasy punktów” pokazuje klasy
przed końcowymi filtrami, także dla molekuł bez końcowej domeny.
Kod podglądu nie zawiera obsługi powiększania i przesuwania obrazu.
Dlatego ten widok nie spełnia jeszcze [naszego wymagania](trial-result-browser.md)
kolorowania molekuł według końcowej przynależności do konkretnej domeny.

Potrzebne dane już istnieją w `detections_with_domains.csv`: ID, współrzędne,
`domain_local_id` i przyczyny braku przypisania. Można oprzeć na nich prosty
widok molekuł, bez treningu lub przeliczania samej segmentacji. Tego widoku
w ramach przeglądu nie implementowano.

## Co wymaga uwagi przed użyciem w STM Domains

- **Inna definicja akceptowanego porządku:** paczka dopuszcza regularność
  w jednym kierunku. Dotychczasowy [protokół](self-supervised-training-protocol.md)
  traktuje pasy i niezależne rzędy jako kontrole negatywne dla sieci 2D.
  Wyniki wymagają wspólnej oceny, nie porównania samych procentów przypisań.
- **Klasa geometrii a typ:** opis zachowuje kierunek względem obrazu, więc
  klasy nie są automatycznie typami niezmienniczymi na obrót z naszego
  [słownika](GLOSSARY.md). Nazwy domen są lokalne dla klatki; brak śledzenia.
- **Granice przesunięcia:** metoda nie zawiera jawnego testu zgodności fazy
  translacyjnej sieci. Reakcja histogramów na granice między obszarami o tym
  samym typie i kącie wymaga osobnego sprawdzenia.
- **Skala i bariery dopasowane do tej serii:** `run_discovery.py` ustala
  `r0=12.076277934383544 px`; detektor barier zakłada prawie poziome przejścia
  rozjaśniające się w dół. Inny materiał, skala lub kierunek skanowania
  wymagają osobnego sprawdzenia. Nie ma kalibracji powierzchni na nm².
- **Zapisany audyt nie mierzy trafności:** 367/367 kontroli potwierdza
  spójność danych, masek i reguł. Brakuje niezależnej oceny względem granic
  domen; zapisane maski przybliżają obszary wsparte przez centra.

Najbardziej użyteczne elementy to bezpośrednie przypisania do molekuł,
zachowanie powodów odmowy, ograniczenie różnorodności całego regionu oraz
kompletny eksport wyników. Moja rekomendacja: najpierw obejrzeć te przypisania
w uzgodnionym prostym widoku, następnie porównać metodę na wspólnych kontrolach
granic i pojedynczych sieci. Nie ma jeszcze podstaw do zastąpienia nią
dotychczasowego kontraktu domen lub rozpoczęcia kolejnego treningu.

## Odtwarzanie i wykonane sprawdzenia

Paczka deklaruje Python 3.12.14 i CPU, z przypiętymi NumPy 2.3.5,
SciPy 1.17.0, scikit-learn 1.8.0, Matplotlib 3.10.8 i Pillow 12.3.0.
Pełna paczka ma runner `reproduce_discovery.py`; kod bez danych zaczyna od
`bootstrap.py --mpp ... --session ...`. Skrypty zapisują do swojej kopii
prototypu i mogą zastąpić dołączone wyniki. Pipeline zakłada obrazy 256 × 256
i obecność pierwszych dziesięciu klatek do referencji; importer dotyczy
tego wariantu MPP. Deklarowanych wersji środowiska
nie instalowano ani nie sprawdzano przez odtworzenie obliczeń.

Wykonano: odczyt wszystkich elementów ZIP z kontrolą CRC, porównanie treści
paczek, weryfikację rozmiarów i SHA-256 wszystkich 35/299 wpisów manifestów,
sprawdzenie składni 27 plików Python bez importowania ich, zgodność hashy
MPP/JSON, przeliczenie liczników CSV i porównanie zapisanych tablic wariantów,
przegląd kodu, dokumentacji i PNG. Nie uruchamiano skryptów paczki ani nowych
analiz. Dołączony `viewer_validation.json` opisuje JavaScript z imitacją DOM,
nie pełny test układu CSS i interakcji w rzeczywistej przeglądarce.

Kod, dane i rozpakowane wyniki pozostają lokalnie poza Git. Wersjonowany
jest ten przegląd i aktualizacja nawigacji/przekazania. Statusy 04/13 pozostają
otwarte; nie utworzono nowych ticketów ani nie scalono kodu do aplikacji.
