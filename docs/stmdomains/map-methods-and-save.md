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
Ten cykl można podejmować przed odbiorem szkieletu. Najpierw przygotowujemy
wspólne wejście i kontrole, potem porównujemy trzy niezależne kierunki.
Zalecana pierwsza próba wykorzystuje otoczenie zaznaczonych molekuł.
Aktualizacja mapy nie uruchamia eksperymentów ani nie rozstrzyga ich wyniku.

[Przegląd ML bez własnego treningu](research-training-free-ml-domain-discovery.md)
z 2026-10-21 dodaje propozycję porównania gotowych cech CNN/DINO w
[próbie obrazowej 17](issues/17-image-texture-domains.md). Grupowanie
nienadzorowane już należy do planu; gotowa sieć może dostarczyć dodatkowej
reprezentacji bez uczenia na ramkach użytkownika. Jakość wymaga sprawdzenia.
Krok 15 pozostaje bazą geometryczną, a kolejność to 14 → próby 15–17 →
odbiór 13, przy zachowaniu wymaganego protokołu jakości 04.

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

- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](issues/02-order-types-and-domains.md): uzgodniono płat warstwy, osobny typ i orientację, granice oraz stany niepewności.
- [Jak porównać metody wykrywania wysp i domen w serii?](issues/05-stable-types-across-frames.md): katalog wspólny dla zakresu; pilotaż wskazał luki skali, rozstawu i granic.
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](issues/06-frame-statistics.md): dwa mianowniki powierzchni, środki oznaczeń, wyniki częściowe i korekty konfliktów.
- [Co zapisujemy i eksportujemy po próbach metod?](issues/08-save-and-export.md): samowystarczalny plik z obrazem i opcjonalnym wynikiem, odtworzenie bez przeliczania, CSV/PNG.
- [Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?](issues/10-coverage-and-scale.md): próba zakończona; zależność od centrów i wybiórczość obrazu wykluczają uznanie jej za gotowy pomiar.
- [Jak rozpoznawać typy przy obrocie, zmianie rozstawu i rzadkich wzorach?](issues/11-structural-type-catalogue.md): próba zakończona; prostsze kontrole działają, katalog TTMAPP pozostaje nadmiernie podzielony i zależny od zakresu.
- [Jak rozdzielać domeny o tym samym typie i orientacji?](issues/12-phase-boundaries.md): próba zakończona; niedopasowanie centrów działa na części kontroli, dostępność sieci i kontrast ograniczają wynik.

Nie wybrano ani nie zwalidowano metod. Kontrakt zapisu jest ustalony;
jego implementacja i odbiór na wynikach metod pozostają do wykonania.

## Not yet specified

Kolejne akwizycje i wyniki nowych prób mogą ujawnić dodatkowe klasy błędów,
potrzebę innych cech lub konkretnego połączenia informacji obrazu i centrów.
Nie rozpisujemy jeszcze takiej metody łączonej ani następnych zestawów
anotacji. Szczegółowe metadane wybranego algorytmu i zadania jego wdrożenia
wynikną z porównań, przy zachowaniu kontraktu zapisu i znaczenia danych.

## Out of scope

- Pomiar orientacji pojedynczej molekuły — [odłożone pytanie](issues/03-molecular-orientation.md), bez rozstrzygnięcia naukowego.
- Detekcja YOLO, tworzenie oznaczeń i trenowanie detektora.
- Śledzenie konkretnych molekuł i domen, historii podziałów, scaleń i narodzin.
- Stały ROI całej serii, ponowne liczenie rejestracji oraz rozwój STM Viewer.
