# STM Domains

Pojęcia analizy uporządkowania molekuł na kolejnych obrazach STM.
Słownik dotyczy zakresu ustalonego z użytkownikiem podczas tworzenia mapy.

## Language

**Zapis wejściowy**:
Zapis z innego programu zawierający gotowe oznaczenia molekuł oraz informacje
pozwalające powiązać je z obrazami i klatkami.
_Avoid_: Model detekcji, wynik STM Domains

**Klatka**:
Pojedynczy obraz pomiarowy powierzchni próbki w serii.
_Avoid_: Cały film, powiększone płótno

**Seria**:
Uporządkowany zbiór klatek analizowanych z zachowaniem tego samego znaczenia
typów uporządkowania. Kolejność klatek nie określa sama w sobie odstępu czasu.
_Avoid_: Jeden obraz, jedna domena

**Oznaczenie molekuły**:
Wskazanie położenia lub obszaru molekuły na konkretnej klatce. Samo oznaczenie
nie jest pomiarem jej orientacji ani tożsamością śledzoną przez całą serię.
_Avoid_: Orientacja, trajektoria

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

**Typ uporządkowania**:
Klasa podobnych wzorów rozmieszczenia lub orientacji molekuł, zachowująca znaczenie
w całej analizowanej serii. Kilka oddzielnych domen może mieć ten sam typ.
_Avoid_: Tożsamość konkretnej domeny, numer klastra ustalany niezależnie w każdej klatce

**Domena**:
Przestrzennie spójny obszar uporządkowania na jednej klatce. Oddzielne obszary
mogą należeć do tego samego typu uporządkowania.
_Avoid_: Typ uporządkowania, śledzona domena

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
