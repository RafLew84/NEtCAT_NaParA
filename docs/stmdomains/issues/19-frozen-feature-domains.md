# Czy gotowe cechy sieci pomagają odkrywać domeny bez przykładów?

ID: 19
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: claimed
Assignee: Codex — domains/translation-consistency-trial
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 17, 18

## Question

Czy zamrożone cechy FCN–ResNet101 lub DINOv2 pomagają znaleźć domeny
na pełnych obrazach STM lepiej niż klasyczny opis tekstury, bez wskazania
przykładów, liczby grup i bez własnego treningu sieci? Porównać oba
podstawowe ekstraktory, o ile przygotowanie potwierdzi ich dostępność.
DINOv3 jest wariantem opcjonalnym, a nie warunkiem zakończenia próby.

## Porównanie

1. Zastosować gotowe ekstraktory do całego zakresu wspólnego zestawu
   oraz odpowiadających mu kontroli. Pokazać osobno regularną siatkę
   i otoczenia dostarczonych centrów. Ramki i poprzednie domeny MolTrack
   nie wyznaczają wejścia, miejsc pobrania cech, klas ani liczby grup.
2. Grupować cechy bez zadanego `K`, np. HDBSCAN z dopuszczeniem jednej
   grupy. Opisać normalizację i ewentualną redukcję wymiaru; dopasowywać je
   do nieoznaczonych danych wspólnie dla badanego zakresu, z jawną regułą
   próbkowania. Nie nadawać osobnym klatkom niezależnych katalogów typów.
3. Oddzielić podobieństwo cech od dowodu porządku i od przestrzennej
   łączności. Domena wymaga wsparcia uporządkowania oraz spójnego obszaru;
   rozłączne płaty nie stają się jedną domeną tylko przez wspólną etykietę.
   Odrzucenie punktu przez grupowanie nie jest automatycznie nieporządkiem.
4. Zestawić wyniki z autokorelacją/EWT, przy możliwie wspólnym grupowaniu,
   regule łączenia przestrzennego i ocenie porządku. Używać tej samej
   procedury doboru parametrów i zapisanego budżetu prób; identyczne
   wartości progów dla różnych skal cech nie są wymagane. Różnice etapów
   ujawnić, aby nie przypisywać poprawy samej sieci bez porównania.
5. Pokazać typ sieci i orientację oddzielnie. Nie zakładać, że DINO lub
   ResNet już rozdziela te cechy. Jeśli potrzebny jest dodatkowy pomiar
   kąta/rozstawu z geometrii albo autokorelacji, podać go w konfiguracji.
   Zmiana orientacji może dzielić domeny, zachowując wspólny typ.

Nie trenujemy wag, głowicy, autoenkodera ani modelu na pojedynczym obrazie.
Nie używamy ramek do doboru parametrów. Wspólna konfiguracja jest zapisywana
przed odsłonięciem częściowych referencji; kolejne korekty mają własną wersję.
Łączenie cech obrazu z geometrią molekuł może wynikać z ustaleń próby,
ale nie jest dodatkowym obowiązkowym eksperymentem w tym zadaniu.

## Gotowy punkt odniesienia — 2026-10-23

[Próba 17](../image-texture-domains-trial.md) jest zakończona i zachowana
przez użytkownika jako porównanie. Źródła: `prototype/stmdomains-texture`,
`3bb4d36`; cechy, katalogi, reguły i wyniki:
`.scratch/image-texture-domains/`. Wybrane konfiguracje obrazu przypisują
0.3–5.8% centrów w częściowych referencjach, bez RED/YELLOW. To wynik
negatywny, który nie blokuje niniejszego porównania.

Oddzielnie ocenić jakość nowych cech i wpływ bramki porządku: obecna ACF
przepuszcza jedynie 9.2–12.6% miejsc w referencjach. Nie przyjmować jej
bez sprawdzenia jako poprawnej dla wszystkich kandydatów. Zachować uczciwe
porównanie wspólnych etapów, pokazać ewentualną zmianę bramki jako osobny
wariant i nie przypisywać całej poprawy sieci. Do warunków doboru włączyć
liczbę domen/podziały pojedynczej sieci; filtr 17 sprawdzał tylko jej
przypisanie. Nie dobierać tych ustawień na ręcznych domenach TTMAPP.

## Dane i kryteria porównania

[Przygotowanie 18](../frozen-feature-preparation.md) zakończono 2026-10-26.
Oba wymagane ekstraktory działają; kod `e6e7248` jest w
`stmdomains/experiments/frozen/`, cechy i manifesty w
`.scratch/frozen-features/`, wagi w `.scratch/frozen-feature-assets/`.
Zależności 17 i 18 są spełnione; próba została wykonana i pozostaje
do dalszego omówienia zgodnie z decyzją użytkownika opisaną poniżej.

Przygotowanie obejmowało 12 obrazów i 16 konfiguracji, nie cały zakres
porównania. Rozszerzyć ekstrakcję na wspólny zestaw zgodnie z protokołem.
Zachować jawność adaptacji: wektory są średnimi lokalnych map, a okna mają
szerokość 48/72 pikseli odniesienia wobec 49/73 w próbie 17. Podparcie
pomiaru jest zapisane, bez gotowej decyzji przyjęcia/odmowy. Pooling,
normalizację i skalę należy uwzględnić w budżecie porównania. Przygotowanie
nie dowodzi jeszcze, że cechy rozróżniają typy, orientacje lub granice.

Obowiązuje [wspólny manifest, format wyników i ocena](14-unsupervised-input-and-controls.md).
Należy sprawdzić przypadki zero/jedna/wiele domen, rozstaw, orientację,
granicę przesunięcia, pojedyncze defekty i pas nieuporządkowany, niepełne
centra, szum i pasy skanowania. Kandydat odrzucający wszystko albo znajdujący
porządek na szumie nie jest sukcesem, nawet jeśli ma stabilne klastry.

Dodatkowo porównać skale wejścia i okna z natywną rozdzielczością cech.
Wykazać, co zostaje z różnic rozstawu i granic po przeskalowaniu obrazu;
gładka interpolacja mapy cech nie dowodzi precyzyjnej lokalizacji granicy.
Zmieniony kontrast lub jasność nie powinny samodzielnie tworzyć typu sieci.
Osobno raportować odmowy i zależność od preprocessing oraz zakresu klatek.

Na TTMAPP oceniać dostępne wnętrza referencji, bez globalnej trafności
nieoznaczonych części. Zmiana/usunięcie samych referencji ma pozostawić
identyczne predykcje. Wynik na używanych już ramkach nie jest niezależną
walidacją. Zmierzyć czas, pamięć oraz koszt przechowania cech; zakres całej
serii badać zgodnie z kwalifikacją kandydatów we wspólnym protokole.

## Wynik do omówienia

Odtwarzalny prototyp i pełne nakładki, tabela wspólnych kontroli oraz
porównanie cech klasycznych z gotowymi cechami sieci. Raport zawiera
konfiguracje, przypisania i odmowy, rozdzielenie typu/orientacji, koszt
oraz ograniczenia. Brak któregoś modelu pozostaje jawnym ograniczeniem
porównania, a nie dowodem jego nieskuteczności.

Omówić z użytkownikiem, czy gotowe cechy dają poprawę uzasadniającą koszt,
czy któryś kandydat odpada i jaka konkretna luka wymaga dalszej pracy.
Wynik negatywny także kończy badanie po omówieniu. Nie potrzeba sukcesu
klasycznej tekstury, żeby przeprowadzić tę próbę; potrzebny jest jej
udokumentowany wynik jako punkt odniesienia. Przyjęcie metody do programu
pozostaje [osobnym odbiorem](13-method-acceptance.md), wspólnym z pozostałymi kandydatami.

## Dependencies

- [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](17-image-texture-domains.md)
- [Jak przygotować cechy gotowych sieci bez treningu na naszych danych?](18-frozen-feature-preparation.md)

## Kontekst

- [ML i deep learning bez własnego treningu](../research-training-free-ml-domain-discovery.md)


## Answer — 2026-10-26, próba do dalszego omówienia

Wykonano [porównanie zamrożonych cech](../frozen-feature-domains-trial.md):
24 pełne klatki TTMAPP i 204 kontrole, FCN/DINO oraz FFT/EWT, siatka i centra.
64 konfiguracje podstawowe ze wspólnym budżetem oraz 96 wariantów
wrażliwości. Bez przykładów domen, zadanego K i treningu sieci.
Źródło prototypu: `prototype/stmdomains-frozen-domains`, **`652ab96`**;
podgląd: `.scratch/frozen-feature-domains/index.html`.

Żaden wariant nie spełnia kompletu warunków rozwojowych. Wybrane sieci
przypisują 0–5.1% centrów we wnętrzach TTMAPP, wyłącznie BLACK; pozostają
błędy jednej sieci, małych orientacji i granic przesunięcia. Siedem z ośmiu
wybranych konfiguracji tworzy jeden klaster wyglądu całego zakresu,
a DINO/centra odmawia wszystkim. Kryterium porządku usuwa większość
pozostałych miejsc. Nowa ACF z korektą nakładania nie naprawia problemu.
Nie utożsamiamy tego wyniku z oceną wszystkich możliwych cech tych sieci.

912 zestawów cech sieci siatki bitowo identycznych bez oznaczeń;
1824/1824 powtórzone wyniki wybranych konfiguracji identyczne. Przeszło
46 kontroli podglądu. Typy strukturalne pozostają nieustalone; wynik
zapisuje osobno grupy wyglądu, kandydatów kierunku ACF i fragmenty.
[Manifest](../frozen-feature-domains-manifest.json) oraz
[audyt grupowania](../research-frozen-domain-clustering-audit.md).

Użytkownik: **„Najpierw omówmy lub rozwińmy tę próbę”**. Status pozostaje
`claimed`; nie zamykamy 19 i nie przyjmujemy metody do programu.
Propozycja dalszego badania: sprawdzić na kontrolach rozróżnialność cech
przed/po PCA, następnie wpływ grupowania bez scalającego epsilon lub
uśredniania map. Ten etap wykonano w osobnym protokole opisanym poniżej;
pierwotnych wyników nie dostrajano po referencjach.


## Rozwinięcie — 2026-10-26: informacja, PCA i epsilon

Na polecenie „wykonaj kolejne badanie” wykonano
[diagnozę rozróżnialności cech i grupowania](../feature-separation-trial.md).
Protokół zapisano przed oceną: osiem kombinacji cecha/miejsca,
pełne wektory i PCA, 32 konfiguracje grupowania. Te same 24 klatki
TTMAPP i 204 kontrole; bez zadanego K, przykładów domen lub treningu.

Uśrednione cechy obu sieci rozróżniają wnętrza sieci o obrocie 8°/27°
i innym rozstawie; PCA zmienia AUC najwyżej o 0.000486 na tych kontrolach.
Pominięcie PCA i epsilon=0 nie rozwiązują jednak podziału: na TTMAPP
30 wariantów daje jeden klaster wyglądu, dwa odmawiają. DINO/centra
odzyskuje 46/1678 oznaczeń, nadal tylko BLACK. Żaden wariant nie spełnia
wszystkich warunków; typy strukturalne pozostają nieustalone.

Źródło: `prototype/stmdomains-feature-separation`, **`cf88e8a`**.
Podgląd: `.scratch/feature-separation/index.html`.
[Manifest](../feature-separation-manifest.json); dokładnie odtworzono
1824 poprzednie wyniki, przeszło 68 kontroli HTML. Znane już ziarna
oraz referencje oznaczają diagnozę rozwojową, bez niezależnej walidacji.

Status nadal **`claimed`**, do omówienia wyniku. Zaproponowano lokalne
granice różnic cech zamiast wyłącznie globalnego HDBSCAN, z osobną oceną
kryterium porządku. Próbę lokalnego grafu wykonano poniżej; nie przyjęto
metody ani nie uruchomiono treningu 20.

## Rozwinięcie — 2026-10-26: lokalny graf i początek siatki

Wykonano [porównanie lokalnego grafu cech](../local-feature-graph-trial.md)
na tych samych 24 całych klatkach TTMAPP i 204 kontrolach: 32 warianty
grafu, osiem zachowanych wyników HDBSCAN oraz osiem kontroli maksymalnego
zakresu obecnej bramki. Cechy, PCA i ocena porządku pozostają niezmienione.
Bez liczby domen K, przykładów domen, treningu lub dostrajania do ramek.
Protokół zapisano przed obliczeniami; użyte dane były już znane.

Graf ogranicza część scaleń orientacji, ale rozcina pojedynczą sieć.
Przykładowo FCN/siatka przy skali 4 zmniejsza scalenia obrotu 8° ze 100%
do 1.9%, jednocześnie daje 7/5/5 fragmentów jednej sieci w trzech ziarnach.
Żaden z 32 wariantów nie spełnia wszystkich warunków rozwojowych.
Maksymalny zakres obecnej bramki to 2.0–5.8% molekuł w częściowych
referencjach TTMAPP; nadal brak RED/YELLOW. Sama rezygnacja z bramki
nie naprawia scaleń obszarów wyglądu.

Na 53 obrazach pobrano świeże cechy przy czterech początkach siatki:
424 zestawy cech i 1696 wyników grafu. Zależność od początku siatki
utrzymuje się także po wykluczeniu brzegu: jedna sieć zmienia końcowy
podział w 69/144 powiązanych porównań. Audyt wnętrza dodano po zamrożeniu
predykcji i oznaczono jako pomocniczy; nie zmieniano parametrów.

Źródło: `prototype/stmdomains-local-feature-graph`, **`1ae0706`**.
[Manifest](../local-feature-graph-manifest.json), podgląd:
`.scratch/local-feature-graph/index.html`. Sprawdzono 7296 permutacji,
128 małych grafów niezależną implementacją, 106 dokładnych odtworzeń
cech i 424 odtworzenia grafu dla zerowego przesunięcia; 107 kontroli HTML.
Nie wdrożono algorytmu do aplikacji ani nie zbudowano katalogu typów.

**19 pozostaje `claimed`, do omówienia.** Kolejne ograniczone badanie
może dotyczyć skali i podparcia kryterium porządku ACF, przy zamrożonych
cechach/podziałach i kontrolach negatywnych. Nie wystarczy obniżyć progu
na TTMAPP; nawet poprawna bramka nie rozwiąże niestabilności granic.
Próbę skali i podparcia wykonano poniżej; nie rozpoczęto treningu 20–23.

## Rozwinięcie — 2026-10-26: skala i podparcie ACF

Wykonano [badanie kryterium porządku](../acf-scale-support-trial.md)
przy niezmienionych cechach i zapisanych podziałach: 24 pełne klatki
TTMAPP i 204 kontrole. 32 bramki (cztery promienie, cztery oceny ACF,
dwa wymagania podparcia), 512 konfiguracji detektora, 64 kontrole limitu
przypisań oraz 16 zachowanych wyników początkowych. Progi według stałej
reguły na znanych kontrolach negatywnych; predykcje przed oceną ramek.

Większe okno odzyskuje fragmenty RED/YELLOW: przy `windowed`, podparciu
50%, limit na siatce rośnie z 98/1678 przy r24 do 430/1678 przy r48.
Jednak r48 łączy rozłączne płaty przez pustą przerwę. Zapisane podziały
wyglądu nadal nadmiernie dzielą jedną sieć lub scalają różne obszary.
**0/512 nowych konfiguracji detektora** spełnia komplet warunków.
Samo użycie zmierzonych par pikseli nie rozwiązuje problemu.

W znanych wnętrzach przy r24 podparcie 50% nie odrzuca miejsc, natomiast
widmowy warunek drugiego kierunku odrzuca 953/1916 miejsc siatki
lub 835/1678 centrów. To hipoteza do następnej osobnej ablacji;
nie wolno po prostu usunąć warunku, który chroni też przed pasami.

Źródło: `prototype/stmdomains-acf-scale-support`, **`2ccf9ad`**.
[Manifest](../acf-scale-support-manifest.json), podgląd:
`.scratch/acf-scale-support/index.html`. Sprawdzono 5836 korelacji
bezpośrednim rachunkiem, 912 odtworzeń ACF, cztery progi, 3648 wyników
początkowych i niezależność siatki od braków oznaczeń; 92 kontrole HTML.
Dane były już znane, bez nowej niezależnej walidacji.

**19 nadal `claimed`, do omówienia.** Następna próba może zbadać drugi
kierunek przy różnym kontraście rzędów molekuł, pasach skanowania
i rzędach bez wzajemnego porządku. Zachować kontrole pustej przerwy
i nieuporządkowanego pasa. Próbę drugiego kierunku wykonano poniżej;
nie rozpoczęto treningu 20–23 ani odbioru metody 13.

## Rozwinięcie — 2026-10-26: drugi kierunek i wzajemna zgodność rzędów

Wykonano [ablację warunku drugiego kierunku](../second-direction-trial.md):
osłabienie do 0.10, wyłączenie przy stałym lub ponownie kalibrowanym progu
ACF oraz eksperymentalna krzywizna maksimów. Zachowano cechy i podziały.
24 całe klatki TTMAPP, 204 stare kontrole oraz 63 nowe obrazy rzędów,
pasów i przerw (21 przypadków, nowe ziarna 4101–4103). Nowe obrazy
sprawdzają sam porządek/łączność; nie dobierają progów ani grup wyglądu.

Przy r24/`windowed`, siatce, wyłączenie warunku zwiększa limit przypisań
z **98 do 636/1678**, nadal tylko BLACK. Odzyskuje też słabsze regularne
rzędy, ale przyjmuje **756/768 miejsc** rzędów z niezależną fazą jako
jeden płat. Krzywizna odrzuca słabsze rzędy i TTMAPP; obrócone niezależne
rzędy nadal dają fałszywe fragmenty. R48 wciąż łączy płaty przez przerwę.
**0/384 zmienionych konfiguracji detektora** spełnia komplet dotychczasowych
warunków. To diagnoza kryterium, nie poprawa samych cech FCN/DINO.

Źródło: `prototype/stmdomains-second-direction`, **`f648afe`**.
[Manifest](../second-direction-manifest.json), podgląd:
`.scratch/second-direction/index.html`. 130 kontroli rachunku krzywizny,
2736 dokładnych odtworzeń ACF i 24624 wyników początkowych; wszystkie
291 plików predykcji odtworzono identycznie przy blokadzie dostępu do
referencji. 170 kontroli HTML. Nowe ziarna są kontrolą syntetyczną,
nie niezależną walidacją pomiarów; progi pozostały zamrożone.

**19 nadal `claimed`, do omówienia.** Kolejna hipoteza: zgodność
przesunięć między rzędami oraz potwierdzenie sygnału w ocenianym miejscu,
bez wzorca, zadanej symetrii lub K. Zachować słabsze spójne rzędy,
losowe fazy, pasy i puste przerwy jako oddzielne kontrole. Kolejną
próbę zgodności i lokalnego sygnału wykonano poniżej; treningu 20–23
ani odbioru 13 nie uruchomiono.

## Rozwinięcie — 2026-10-28: zgodność przesunięć i lokalny sygnał

Wykonano [dwa porównania](../translation-consistency-trial.md) na
372 obrazach, w tym 81 nowych kontrolach (nowe ziarna, dodatkowe skośne
i prostokątne sieci). Zachowane cechy/podziały, bez wzorca domeny,
K lub treningu. Nowe kontrole nie kalibrowały progów. 20 kryteriów,
360 konfiguracji na starym zestawie; obrazy rzędów badają samą bramkę
i łączność, bez nowego grupowania cech.

Zgodność różnic obrazu po przesunięciu między rzędami przy r24/kwantylu
.99 zachowuje **79.7%** słabszej syntetycznej sieci, a przypisania
w niezależnych rzędach 0° spadają z **756 do 24/768** względem wariantu
bez drugiego kierunku. Jednak każde badane kryterium zgodności odrzuca
wszystkie wnętrza TTMAPP. Lokalny sygnał usuwa błędy w pustej przerwie,
lecz na siatce usuwa także poprawne płaty. Małe okno trafia między
molekuły; przy centrach ta sama kontrola zachowuje wynik.
**0/256 zmienionych konfiguracji detektora** spełnia komplet warunków.

Źródło: `prototype/stmdomains-translation-consistency`, **`89cd738`**.
[Manifest](../translation-consistency-manifest.json), podgląd:
`.scratch/translation-consistency/index.html`. 4656 zgodnych tablic
wcześniejszych pomiarów, 16920 dokładnych odtworzeń wyników;
372 pliki / 87840 wyników konfiguracji identyczne po ponowieniu
z zablokowanym odczytem referencji. **187 kontroli HTML**. Pomocniczy
audyt niepowodzeń wykonano po zamrożeniu, bez zmiany parametrów.

**19 nadal `claimed`, do omówienia.** Proponowany następny krok to 20:
przygotowanie uczenia bez etykiet, następnie 21/22. Zachować niniejsze
kontrole oraz oddzielić ocenę reprezentacji/podziału od odmów bramki.
Nie uznano pustego wyniku za brak domen; nie wybrano metody do programu.
Przygotowania 20 ani treningów nie uruchomiono.
