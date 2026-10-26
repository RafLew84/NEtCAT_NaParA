# Czy gotowe cechy sieci pomagają odkrywać domeny bez przykładów?

ID: 19
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: claimed
Assignee: Codex — domains/frozen-domain-trial
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
uśredniania map. To nowy, jeszcze niewykonany etap wymagający osobnego
protokołu; aktualnych wyników nie dostrajano po referencjach.
