# 23: Twórz klasy ręcznie i poprawiaj ich przypisania

**ID:** SD-V4-23

**What to build:** Użytkownik dodaje własną klasę z nazwą i kolorem, przypisuje do niej domeny lub zaznaczone molekuły oraz rozszerza istniejącą klasę o kolejne wskazania. Widok Klasy pokazuje poprawione przypisania, a widok Domeny zachowuje osobne przestrzenne obiekty.

**Blocked by:** [07: Wybierz liczbę klas i zakres ich odkrywania](07-fit-shared-classes.md), [22: Dziel i łącz domeny na obrazie](22-split-merge-domains.md).

**Status:** ready-for-agent — dodanie do planu zlecone przez użytkownika 2026-11-03; wykonanie po zależnościach.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady edycji ręcznej](README.md#edycja-ręczna-klas-i-domen).

## Kryteria akceptacji

- [ ] Okno klas umożliwia dodanie klasy, zmianę nazwy/koloru oraz wybór klasy docelowej. Każda ma trwałe ID i pochodzenie automatyczne lub ręczne; zmiana nazwy/koloru nie zmienia jej tożsamości. Nowa klasa może początkowo nie mieć członków. Usunięcie jest dostępne tylko dla pustej klasy utworzonej ręcznie.
- [ ] Można nadać klasę całej domenie lub kilku wskazanym domenom, dodać kolejne molekuły do istniejącej klasy, zmienić klasę i przywrócić stan nieustalony. Usunięcie klasy z przypisania nie usuwa molekuły ani domeny. Dwie rozdzielone domeny tej samej klasy mają wspólny kolor Klasy i odrębne ID/obrysy Domeny.
- [ ] Zmiana klasy tylko części domeny pokazuje podgląd wydzielenia jej do osobnej domeny przez operację z 22. Nie zmienia pozostałych członków i nie pozostawia wieloklasowej domeny. Przypisanie klasy molekułom bez domeny nie tworzy domeny samoczynnie; widok oraz licznik klasy potrafią pokazać takie wskazania osobno od udziału domen.
- [ ] Lista klas do ręcznych przypisań ma jawną tożsamość i wersję, powiązaną z konkretnym katalogiem automatycznym albo z ręczną pracą bez dopasowania. Zmiany nazwy/koloru dotyczą tej listy i są widoczne na korzystających z niej klatkach; historyczne wersje są zachowane. Przypisania zmieniają się tylko dla wskazanych molekuł na bieżącej klatce.
- [ ] Na kolejnej klatce korzystającej z tej samej listy można jawnie wybrać istniejącą klasę i dodać do niej wskazania. Zgodność numeru lub nazwy w innym katalogu nie pozwala automatycznie utożsamić klas. UI pokazuje zakres listy i odróżnia ustawione K modelu od liczby ręcznych klas oraz klas obecnych na klatce.
- [ ] Model dopasowany w 07/08/12 pozostaje niezmieniony. Ręczna klasa nie dostaje fikcyjnego centroidu, ufności ani statusu rozpoznania przez model. Nowa analiza nie przypisuje tej klasy automatycznie; wynik i korekty pozostają rozdzielone. Nazwa klasy nie jest potwierdzeniem fizycznego typu z 20.
- [ ] Cofnij/Ponów obejmuje utworzenie klasy, metadane, przypisania i ewentualny podział jako jedną operację. Podgląd Automatyczny/Po korektach zachowuje własne legendy i liczniki. Zmiana listy klas oraz nawigacja nie przenoszą korekt do innych katalogów.
- [ ] Kontrole obejmują nową/pustą klasę, dodawanie członków, wspólną klasę kilku domen, podział przy częściowej zmianie, klasę bez domeny, różne katalogi i niezmienność modelu. Wykonano test GUI na TTMAPP oraz opisanych przykładach, w netcat; kod i testy spełniają 1000/1500 linii.

## Test ręczny użytkownika

1. W netcat uruchom aplikację, dopasuj wspólne klasy z klatek 259–260 i oblicz obie klatki. W oknie klas utwórz „Moja klasa A” z wybranym kolorem i przypisz do niej domenę na 259.
2. Dodaj do tej klasy drugą domenę. Widok Klasy ma wspólny kolor, Domeny zachowuje dwa ID. Zmień nazwę/kolor, cofnij i ponów; ustawione K modelu pozostaje takie samo.
3. Wybierz część domeny i przypisz do nowej klasy. Zobacz podgląd podziału, zatwierdź i cofnij całą zmianę jednym krokiem. Pozostali członkowie nie zmieniają klasy.
4. Przypisz klasę nieprzypisanym molekułom bez domeny na dostarczonym przykładzie. Sprawdź, że widok Klasy je koloruje, a liczba domen nie rośnie. Usuń samo przypisanie klasy.
5. Na 260 wybierz tę samą klasę i ręcznie dodaj członków. Samo przejście do tej klatki nie zmienia jej przypisań. Porównaj z innym katalogiem, wykonaj ponowną analizę i sprawdź zachowanie wcześniejszych korekt oraz niezmienność modelu.
6. Na osobnej klatce bez analizy utwórz klasę i ręczne przypisanie. UI ma pokazać brak dopasowanego modelu, a nie dopisać tej klasy do modelu z innego wyniku.

## Granice zadania

Ręczne etykietowanie i poprawianie wyniku, bez douczania, wyznaczania wzorca z przykładów, automatycznego rozszerzania klasy na podobne molekuły ani zmiany algorytmu K/Auto. Użycie korekt do przyszłego uczenia wymaga osobnej decyzji i planu. Zapis z historią dodaje 24, eksport 25.
