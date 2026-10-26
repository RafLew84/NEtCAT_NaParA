# STM Domains — etap 2: metody i zapis wyników

ID: stmdomains-methods-map
Labels: wayfinder:map
Status: open
Assignee:

## Destination

Uzgodnione na próbach metody samodzielnego wykrywania domen sieci oraz
pokrycia/wysp, z oceną jakości, statystykami i kontraktem zapisu wyników.
Metody korzystają z obrazów i gotowych oznaczeń molekuł, bez narzucania
istnienia domen, ich liczby ani uczenia klas z wybranych domen użytkownika.
Ustalenia mają pozwolić rozwinąć odebrany szkielet STM Domains.

## Notes

Zwykły tok tego etapu następuje po odbiorze działającego szkieletu z
[pierwszej mapy](map.md), zgodnie z decyzją użytkownika z 2026-10-16.
Otwarte pytania metod nie blokują implementacji ani odbioru szkieletu.
Na bezpośrednie polecenia użytkownika wcześniej uzgodniono definicje,
statystyki i zapis oraz przeprowadzono pilotaż i próby pokrycia, typów
oraz granic. Nie oznacza to wykonania aplikacji ani wyboru gotowej metody.

Aktualny zakres badawczy to
[próby samodzielnego znajdowania domen](issues/README.md#próby-samodzielnego-znajdowania-domen),
rozpisane na polecenie użytkownika 2026-10-21 po przeglądzie STM/AFM.
Ten cykl można podejmować przed odbiorem szkieletu. 2026-10-23 zakończono
[przygotowanie wspólnego wejścia i kontroli](issues/14-unsupervised-input-and-controls.md);
[raport](unsupervised-input-preparation.md) i [protokół](experiment-input-protocol.md)
udostępniają zestaw do kolejnych porównań.
Następnie wykonano [pierwszą próbę otoczeń molekuł](local-neighborhood-domains-trial.md):
prosty opis i SOAP z katalogiem bez K oraz osobną oceną porządku. Nie
uzyskano ogólnego wykrywania; najwyższe przypisanie na częściowych
referencjach TTMAPP wynosi 31%, bez RED/YELLOW. Dodatkowa diagnoza
wskazuje odrzucenie tych obszarów przez kryterium powtarzalności.
Użytkownik wybrał dalsze omówienie lub rozwinięcie. Na kolejne polecenie
wykonano [próbę kryterium powtarzalności](recurrence-criterion-trial.md):
38 konfiguracji, kalibracja na syntezie, katalog i łączenie zamrożone.
Przypisanie w referencjach wzrosło do 62.5%, lecz 30.4% przypisanych par
z różnych regionów jest scalonych. Pozostają błędy orientacji/łączenia
i katalogu; samo przejście kryterium nie oznacza domeny. Wtedy issue 15
pozostawało `claimed`, bez automatycznego przejścia do 16 i bez wyboru metody.
Następnie na polecenie użytkownika [zbadano orientację i łączenie](orientation-and-joining-trial.md):
komórka sieci i zgodność ze startem poprawiają kontrolę braków, dają
70.7% przypisań na referencjach i 0/3801 scaleń ocenianych par różnych
regionów. Pozostają słaby RED/YELLOW, scalenia granicy przesunięcia
przy błędach centrów oraz nadmierne dzielenie deformacji. Użytkownik
następnie polecił przejść do 16: issue 15 jest `resolved` jako seria
porównań, a komórka pozostaje punktem odniesienia bez przyjęcia do aplikacji.

Wykonano [próbę SBC/MatID 16](sbc-matid-domains-trial.md) na tych samych
228 próbkach. SBC pomaga przy brakach i deformacji, lepiej rozdziela
trudną granicę przesunięcia, lecz scala różnicę orientacji 8°, tworzy
pozorne obszary na losowych punktach i zależy od ziarna wyszukiwania.
Adaptacja punktowa: 63.5% przypisań w częściowych referencjach, 5.5%
scaleń ocenianych par różnych regionów. Żaden z 18 wariantów nie spełnia
wszystkich warunków. Użytkownik zatwierdził zachowanie porównania i przejście do 17 — tekstury
obrazu; 16 ma status `resolved`. Nie wybrano algorytmu do aplikacji.

Wykonano [próbę tekstury 17](image-texture-domains-trial.md): lokalne widmo
oraz EWT, 32 konfiguracje, siatka i centra na 228 próbkach. Wariant obrazowy
pozostaje identyczny bez oznaczeń, ale wybrane ustawienia przypisują tylko
0.3–5.8% centrów w referencjach TTMAPP, bez RED/YELLOW. EWT scala małe
orientacje, widmo na siatce nadmiernie dzieli jedną sieć, a bramka porządku
odrzuca większość rzeczywistych wzorów. Użytkownik zaakceptował porównanie:
17 jest `resolved` jako klasyczny punkt odniesienia dla ML, bez wdrożenia.
Podgląd: `.scratch/image-texture-domains/index.html`.

2026-10-26 [przygotowanie 18](frozen-feature-preparation.md) zakończono
ze statusem `resolved`: oba ekstraktory, FCN–ResNet101 i DINOv2 ViT-S/14,
działają z niezmienionymi wagami na siatce oraz przy centrach molekuł.
Sprawdzono geometrię, cache i niezależność od referencji; 192/192 zestawy
siatki są bitowo identyczne po usunięciu centrów. Pilotaż 12 obrazów
i 16 konfiguracji przygotowuje cechy, bez wykrywania domen. Porównanie
19 wykonano i opisano poniżej; niezależne 20 pozostaje do wykonania.

[Przegląd ML bez własnego treningu](research-training-free-ml-domain-discovery.md)
z 2026-10-21 rozwinięto na polecenie użytkownika w
[przygotowanie gotowych cech](issues/18-frozen-feature-preparation.md) oraz
[porównanie domen z tych cech](issues/19-frozen-feature-domains.md).
Przygotowanie korzysta ze wspólnego wejścia i może przebiegać obok prób
geometrii, SBC/MatID i klasycznej tekstury. Porównanie ML wymaga gotowych
cech oraz udokumentowanego wyniku klasycznej tekstury; jej sukces nie jest
warunkiem próby. DINOv3 pozostaje opcjonalny. Grupowanie dopasowuje się
do danych bez etykiet, a wagi sieci pozostają niezmienione.

[Odbiór metod](issues/13-method-acceptance.md) obejmie również wynik ML,
przy zachowaniu wymaganego protokołu jakości. Przygotowanie modeli nie
oznacza wyboru ani skuteczności metody.

2026-10-21 użytkownik dopuścił również własny trening na nieoznaczonych
danych. [Przegląd metod uczonych bez etykiet](research-self-supervised-domain-learning.md)
rozszerza kandydatów o rVAE, lokalne uczenie cech oraz reprezentacje grafu
molekuł. Ograniczenie braku przykładów domen i narzucanej liczby grup nadal
obowiązuje. Próby gotowych cech zachowują zakres bez treningu jako punkt
odniesienia; nowy przegląd nie oznacza wykonania ani wyboru metody uczonej.

Na kolejne polecenie użytkownika rozpisano
[zadania treningu bez etykiet 20–26](issues/README.md#trening-bez-etykiet-domen).
Po wspólnym wejściu przygotujemy protokół treningu, podział danych i pomiar
GPU. Pierwsze próby to AE/rVAE oraz lokalne SSL, niezależne od siebie,
z wynikiem tekstury jako punktem odniesienia. Ich zestawienie z gotowymi
cechami sieci kończy się [decyzją o dalszym zakresie](issues/23-training-comparison-and-next-step.md).
Grafy molekuł, maskowany autoenkoder i adaptacja gotowego modelu są
warunkowymi rozszerzeniami, wybieranymi na podstawie konkretnej luki.
Odbiór 13 czeka na decyzję 23; wybrane w niej rozszerzenia dopisujemy do
jego zależności. Niewybrane warianty nie blokują odbioru. Przygotowanie
treningu może przebiegać obok przygotowania zamrożonych modeli.

Sprzęt do pierwszych prób: RTX 5090 z 32 GB VRAM i 128 GB RAM.
Użytkownik wskazał także drugi komputer z kartą Blackwell Max-Q 96 GB VRAM
oraz Colab jako możliwości dalszych prób, jeśli wyniki uzasadnią rozszerzenie.
Protokół treningu powinien rozdzielać analizę obecnej serii od oceny
uogólnienia na niezależnych danych, z kontrolą przecieku między wycinkami
i sąsiednimi klatkami. Większy model nie zastępuje takiej oceny.

Zakres i warunki poszczególnych prób są w ticketach; indeks powyżej oraz
[odnośniki ze wcześniejszego planu](unsupervised-domain-experiments.md)
prowadzą do ich aktualnych treści. Odbiór metod pozostaje osobnym pytaniem:
zestawi wyniki kandydatów z protokołem jakości, statystykami i zapisem.
Zakończone próby pokrycia, katalogu typów i granic zachowują statusy oraz
raporty; ich ograniczenia przechodzą do dalszej oceny.

Stałe zasady:

- Korzystamy z odtworzonych obrazów i gotowych oznaczeń. Katalog typów
  ustalamy wspólnie dla wybranego zakresu, z orientacją oddzieloną od typu;
  nie zakładamy klas A/B/C ani obowiązkowej symetrii M6.
- Analizujemy całe oryginalne pola klatek. Padding po rejestracji nie jest
  pomiarem. Ramki referencyjne służą późniejszej ocenie, nie wyborowi miejsc
  poszukiwania, treningowi lub zadaniu liczby grup.
- [Obecne częściowe referencje](partial-domain-reference-audit.md) wystarczą
  do rozpoczęcia porównań. Nieoznaczone otoczenie nie jest negatywnym
  przykładem. Potrzebę nowych oznaczeń ma wykazać konkretny wynik próby.
- Dopuszczamy zero, jedną i wiele domen; brak danych i wykryty nieporządek
  są odrębnymi wynikami. Stabilny klaster cech sam nie dowodzi uporządkowania.
- Pokrycie materiałem na dowolnym widocznym poziomie warstwy oraz domeny
  sieci są osobnymi wynikami. Ciemne miejsca bez wystarczających przesłanek
  pozostają nierozstrzygnięte. Otoczka punktów nie jest automatycznie
  powierzchnią całego płata.
- Badanie wykazujące nieskuteczność metody może być zakończone. Samo
  uruchomienie kodu lub kolorowa nakładka nie oznacza przyjęcia algorytmu.
- Porównania i podglądy prototypów służą decyzjom; produkcyjne zmiany
  wymagają zadań wynikających z ich wyników. Nie śledzimy tożsamości domen.

[Audyt MolTrack](moltrack-method-audit.md) wyjaśnia ograniczenia wcześniejszych
metod. [Przegląd grupowania obiektów](research-domain-discovery-and-object-clustering.md)
i [przegląd STM/AFM](research-stm-afm-unsupervised-domain-discovery.md)
uzasadniają kandydatów; nie stanowią ich walidacji na TTMAPP.
Starsze materiały: [wykrywanie domen](research-general-domain-detection.md)
oraz [wyspy, orientacja i level set](research-domain-detection-level-sets.md).

To mapa `wayfinder`. [Rejestr pytań](issues/README.md) określa typy, statusy,
zależności i wybór kolejnego zadania. Próby metod korzystają z `prototype`,
rozmowy decyzyjne z `grilling` i `domain-modeling`, a badania źródeł z `research`.
Przygotowanie wspólnych danych jest zadaniem AFK. Żadnego nowego ticketu
nie zamknięto przez samo dodanie go do mapy.

## Decisions so far

- [Czy gotowe cechy sieci pomagają znaleźć domeny?](issues/19-frozen-feature-domains.md): [próba wykonana](frozen-feature-domains-trial.md), **`claimed` do dalszego omówienia/rozwinięcia na życzenie użytkownika**. [Diagnoza cech/PCA](feature-separation-trial.md) wykazała rozróżnialność syntetycznych orientacji/rozstawu, lecz pełne cechy i epsilon=0 nie naprawiły podziału. Następnie wykonano [lokalny graf i przesunięcie siatki](local-feature-graph-trial.md): mniej części scaleń kosztem podziałów jednej sieci, zależność od siatki, 0/32 zakwalifikowanych konfiguracji. Wykonana później [skala/podparcie ACF](acf-scale-support-trial.md) odzyskuje fragmenty RED/YELLOW, ale większe okna łączą rozłączne płaty; 0/512 nowych konfiguracji detektora spełnia komplet warunków. Kolejny kierunek do omówienia: osobna ablacja warunku drugiego kierunku widma, z kontrolami rzędów, pasów i przerw. Nie wybrano metody.

- [Jak przygotować cechy gotowych sieci bez treningu?](issues/18-frozen-feature-preparation.md): [przygotowanie zakończone](frozen-feature-preparation.md). FCN i DINOv2 działają z niezmienionymi wagami; geometria, cache i niezależność od referencji sprawdzone. Gotowe wejście techniczne do 19, bez oceny skuteczności domen.
- [Czy otoczenie molekuł pozwala znaleźć domeny?](issues/15-local-neighborhood-domains.md): zakończono trzy porównania; użytkownik polecił przejść do 16. Lokalna komórka jest punktem odniesienia, bez przyjęcia metody; pozostają błędy trudnych granic i RED/YELLOW. [Raport orientacji i łączenia](orientation-and-joining-trial.md).
- [Czy SBC/MatID odtwarza domeny z centrów?](issues/16-sbc-matid-domains.md): [próba wykonana](sbc-matid-domains-trial.md), **próba zakończona**. Użytkownik zachował porównanie i wybrał przejście do 17. Poprawa braków i deformacji nie usuwa pozornego porządku ani błędów małej orientacji; nie przyjęto do aplikacji.
- [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](issues/14-unsupervised-input-and-controls.md): przygotowano 24 pełne klatki, 132 kontrole, osobne referencje i format wyników; potwierdzono geometrię, powtarzalność i brak wpływu referencji na wejście. Bez uruchamiania metod.
- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](issues/02-order-types-and-domains.md): uzgodniono płat warstwy, osobny typ i orientację, granice oraz stany niepewności.
- [Jak porównać metody wykrywania wysp i domen w serii?](issues/05-stable-types-across-frames.md): katalog wspólny dla zakresu; pilotaż wskazał luki skali, rozstawu i granic.
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](issues/06-frame-statistics.md): dwa mianowniki powierzchni, środki oznaczeń, wyniki częściowe i korekty konfliktów.
- [Co zapisujemy i eksportujemy po próbach metod?](issues/08-save-and-export.md): samowystarczalny plik z obrazem i opcjonalnym wynikiem, odtworzenie bez przeliczania, CSV/PNG.
- [Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?](issues/10-coverage-and-scale.md): próba zakończona; zależność od centrów i wybiórczość obrazu wykluczają uznanie jej za gotowy pomiar.
- [Jak rozpoznawać typy przy obrocie, zmianie rozstawu i rzadkich wzorach?](issues/11-structural-type-catalogue.md): próba zakończona; prostsze kontrole działają, katalog TTMAPP pozostaje nadmiernie podzielony i zależny od zakresu.
- [Jak rozdzielać domeny o tym samym typie i orientacji?](issues/12-phase-boundaries.md): próba zakończona; niedopasowanie centrów działa na części kontroli, dostępność sieci i kontrast ograniczają wynik.

- [Czy tekstura obrazu znajduje domeny bez przykładów?](issues/17-image-texture-domains.md): [próba zakończona](image-texture-domains-trial.md), zatwierdzona jako porównanie. Niezależność od anotacji potwierdzona; odmowy na TTMAPP i błędy podziałów/orientacji wykluczają przyjęcie obecnych konfiguracji. Zachowano cechy do ML.

Nie wybrano ani nie zwalidowano metod. Kontrakt zapisu jest ustalony;
jego implementacja i odbiór na wynikach metod pozostają do wykonania.

## Not yet specified

Kolejne akwizycje i wyniki nowych prób mogą ujawnić dodatkowe klasy błędów,
potrzebę innych cech lub konkretnego połączenia informacji obrazu i centrów.
Nie rozpisujemy jeszcze takiej metody łączonej ani następnych zestawów
anotacji. Rodziny uczenia z ostatniego przeglądu mają już tickety 20–26;
konkretne architektury, budżety i wybór rozszerzeń rozstrzygną te zadania.
Szczegółowe metadane wybranego algorytmu i zadania jego wdrożenia
wynikną z porównań, przy zachowaniu kontraktu zapisu i znaczenia danych.

## Out of scope

- Pomiar orientacji pojedynczej molekuły — [odłożone pytanie](issues/03-molecular-orientation.md), bez rozstrzygnięcia naukowego.
- Detekcja YOLO, tworzenie oznaczeń i trenowanie detektora.
- Śledzenie konkretnych molekuł i domen, historii podziałów, scaleń i narodzin.
- Stały ROI całej serii, ponowne liczenie rejestracji oraz rozwój STM Viewer.
