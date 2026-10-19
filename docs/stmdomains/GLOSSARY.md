# STM Domains

Pojęcia przeglądania obrazów, pokrycia materiałem i uporządkowania sieci molekuł.
Słownik dotyczy zakresu ustalonego z użytkownikiem podczas tworzenia mapy.

## Language

**Zapis wejściowy**:
Zapis z innego programu zawierający gotowe oznaczenia molekuł oraz informacje
pozwalające powiązać je z obrazami i klatkami.
_Avoid_: Model detekcji, wynik STM Domains

**Zapis pracy STM Domains**:
Samowystarczalny zapis obrazów, oznaczeń wejściowych i podglądu, opcjonalnie
z jednym wynikiem analizy, jego ustawieniami i korektami, pozwalający wznowić pracę.
_Avoid_: Zapis wejściowy MolTrack, tabela eksportowa, historia wielu prób

**Wynik analizy**:
Rezultat jednej analizy określonego zakresu klatek, z przypisanymi ustawieniami,
katalogiem typów, oceną dostępności danych i ewentualnymi korektami użytkownika.
_Avoid_: Sam obraz nakładki, numer klastra bez katalogu, kompletna ocena każdej klatki

**Eksport wyników**:
Tabele lub ilustracje wybranych wyników przeznaczone do dalszego opracowania
albo prezentacji; nie zastępują zapisu pracy STM Domains.
_Avoid_: Samowystarczalna kopia pracy, obraz pomiarowy po zmianie gamma

**Klatka**:
Pojedynczy obraz pomiarowy powierzchni próbki w serii.
_Avoid_: Cały film, powiększone płótno

**Obraz oryginalny**:
Obraz pomiarowy w orientacji przyjętej podczas importu, przed zastosowaniem
rejestracji. Jego orientacja może różnić się od macierzy zapisanej w pliku.
_Avoid_: Niezmieniona macierz pliku, obraz wyrównany

**Obraz wyrównany**:
Obraz oryginalny umieszczony we wspólnym układzie zgodnie z zapisaną rejestracją,
z dopełnieniem potrzebnym do pokazania całego pola klatki.
_Avoid_: Nowy pomiar, powiększony obszar próbki

**Seria**:
Uporządkowany zbiór klatek należących do jednego otwartego zapisu.
Kolejność klatek nie określa sama w sobie odstępu czasu.
_Avoid_: Jeden obraz, jedna domena

**Oznaczenie molekuły**:
Wskazanie położenia lub obszaru molekuły na konkretnej klatce. Samo oznaczenie
nie jest pomiarem jej orientacji ani tożsamością śledzoną przez całą serię.
_Avoid_: Orientacja, trajektoria

**Brak zapisanych oznaczeń**:
Stan klatki, dla której dostępny zbiór oznaczeń nie zawiera żadnego rekordu.
Nie dowodzi braku molekuł ani tego, czy klatkę wcześniej oceniono.
_Avoid_: Zero molekuł, potwierdzona pusta powierzchnia

**Niedostępne oznaczenia**:
Oznaczenia, których nie zapisano albo których treści lub położenia nie można
poprawnie odtworzyć. Przyczyna niedostępności jest odrębna od liczby molekuł.
_Avoid_: Pusta lista, brak molekuł

**Uporządkowanie położeń**:
Regularność przestrzennego układu centrów molekuł.
_Avoid_: Orientacja pojedynczej molekuły

**Orientacja molekuły**:
Kierunek rozróżnialnego motywu pojedynczej molekuły, z określonym odniesieniem
i równoważnymi obrotami. W tym zakresie badamy motyw widoczny na obrazie STM.
_Avoid_: Orientacja sieci, kąt bboxa

**Orientacja sieci**:
Kierunek lokalnego układu sąsiednich centrów molekuł.
_Avoid_: Orientacja molekuły

**Pokrycie materiałem**:
Obszar poprawnego pola pomiarowego zajęty przez płaty warstwy molekularnej,
obejmujący normalne odstępy między molekułami, bez większych odsłoniętych
obszarów podłoża i dopełnienia obrazu.
_Avoid_: Suma powierzchni samych molekuł, całe płótno, miara uporządkowania sieci

**Wyspa**:
Przestrzennie spójny płat warstwy molekularnej wraz z normalnymi odstępami
między molekułami. Może zawierać kilka domen sieci i lokalne defekty.
_Avoid_: Typ uporządkowania, pojedyncza domena orientacyjna

**Typ uporządkowania**:
Klasa struktur o podobnym układzie i charakterystycznym rozstawie molekuł,
zachowująca znaczenie w całej serii niezależnie od obrotu lub jednolitego
przesunięcia sieci. Kilka domen o różnych orientacjach może mieć ten sam typ.
_Avoid_: Orientacja sieci, tożsamość konkretnej domeny, numer klastra ustalany niezależnie w każdej klatce

**Udział powierzchni typu w polu klatki**:
Część oryginalnego pola pomiarowego zajęta przez obszary danego typu.
Dopełnienie obrazu nie należy do pola odniesienia.
_Avoid_: Udział typu w warstwie, procent powiększonego płótna

**Udział powierzchni typu w pokryciu**:
Część powierzchni warstwy molekularnej zajęta przez obszary danego typu.
Materiał bez rozpoznanego typu nadal należy do powierzchni odniesienia.
_Avoid_: Udział typu w całej klatce, udział tylko w rozpoznanych typach

**Przypisanie molekuły do domeny**:
Powiązanie oznaczenia molekuły z jedną domeną według położenia środka oznaczenia;
przypisana molekuła przyjmuje typ tej domeny, jeśli typ jest rozpoznany.
_Avoid_: Niezależny pomiar typu molekuły, wielokrotne zliczenie na granicy

**Udział liczebności typu**:
Część wszystkich poprawnych oznaczeń ze środkiem w oryginalnym polu klatki
przypisana do danego typu; oznaczenia bez typu pozostają w podstawie porównania.
_Avoid_: Udział tylko w rozpoznanych typach, udział wszystkich rzeczywistych molekuł próbki

**Częściowy wynik statystyki**:
Dostępna liczba lub powierzchnia rozpoznanych obszarów przy niepełnej ocenie
klatki, z zachowaną informacją o niepewności i brakach.
_Avoid_: Kompletny pomiar, zero w miejscu braku danych

**Ręczne rozstrzygnięcie konfliktu domen**:
Decyzja użytkownika o przynależności konkretnego spornego obszaru do jednej
z proponowanych domen, zachowana jako korekta wyniku automatycznego.
_Avoid_: Automatyczny wybór pewniejszej domeny, nowa detekcja molekuł

**Obserwowany fragment domeny**:
Spójna, rozpoznana część domeny w polu jednej klatki. Jej rozmiar i połączenia
poza polem pozostają nieznane; oddzielne widoczne fragmenty liczymy osobno.
_Avoid_: Pełna domena poza kadrem, tożsamość domeny śledzona w serii

**Domena sieci**:
Przestrzennie spójny obszar uporządkowania na jednej klatce, oddzielony od innych
przerwą, pasem bez uporządkowania lub wyraźną granicą niedopasowania sieci.
Pojedyncze defekty nie muszą go rozdzielać; różne domeny mogą mieć ten sam typ
i orientację.
_Avoid_: Typ uporządkowania, śledzona domena, cała wyspa niezależnie od uporządkowania

**Granica niedopasowania sieci**:
Linia rozdzielająca obszary, których uporządkowane wzory nie łączą się spójnie,
także przy jednakowym typie i orientacji po obu stronach.
_Avoid_: Pojedynczy defekt, jednolite przesunięcie całej domeny

**Obszar bez wykrytego porządku**:
Obszar, w którym wystarczające dane nie potwierdzają badanej regularności
rozmieszczenia molekuł. Może nadal należeć do wyspy materiału.
_Avoid_: Brak materiału, zbyt słaby sygnał, brak oznaczeń

**Uporządkowanie bez rozpoznanego typu**:
Rozpoznana regularność struktury, której nie można przypisać do znanego typu.
Jest kandydatem do rozszerzenia katalogu typów, a nie brakiem uporządkowania.
_Avoid_: Nieporządek, automatycznie nowa faza materiału

**Domena ucięta brzegiem**:
Domena, której obserwowany fragment dochodzi do granicy pola pomiarowego.
Jej zasięg i połączenia poza tym polem pozostają nieznane.
_Avoid_: Pełna domena o zmierzonej powierzchni, automatycznie błędna domena

**Rejestracja obrazów**:
Wyznaczenie przekształceń umieszczających klatki we wspólnym układzie odniesienia.
Wyrównanie nie dostarcza pomiarów spoza oryginalnych klatek.
_Avoid_: Detekcja domen, śledzenie molekuł

**Oryginalne pole klatki**:
Obszar pomiarowy o oryginalnym rozmiarze obrazu, przeniesiony zgodnie z rejestracją.
_Avoid_: Całe płótno po wyrównaniu, wspólny ROI wszystkich klatek

**Dopełnienie obrazu**:
Dodatkowy obszar płótna potrzebny do pokazania przesuniętych klatek, który nie
należy do oryginalnego pola danej klatki i nie wnosi jej pomiarów.
_Avoid_: Pusta powierzchnia próbki, obszar bez domen
