# 21: Twórz domeny ręcznie i zmieniaj ich skład

**ID:** SD-V4-21

**What to build:** Użytkownik zaznacza istniejące molekuły kliknięciami lub lassem, tworzy z nich domenę albo rozszerza istniejącą. Może usunąć przypisanie, cofnąć zmianę i porównać poprawiony obraz z wynikiem automatycznym.

**Blocked by:** [05a: Obszary i granice domen](05a-domain-regions.md).

**Status:** done — implementacja 2026-11-05, wybrany Panel A.
Commity `a61e1b2`, `47bafe0`. [Raport i test ręczny](acceptance-21.md),
[przegląd](review-21.md). **Odbiór ręczny użytkownika otwarty.**

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady edycji ręcznej](README.md#edycja-ręczna-klas-i-domen).

**2026-11-05 — [interaktywny prototyp UI A/B/C](prototype-21-layouts.md).**
A — panel boczny, B — pasek pod obrazem, C — karta na obrazie.
Użytkownik wybrał A 2026-11-05: panel widoczny wyłącznie podczas edycji ręcznej, otwierany przez „Edytuj domeny” i chowany przez „Zakończ edycję”. Korekty pozostają widoczne po schowaniu panelu. Źródło pierwotne:
`prototype/stmdomains-manual-domains-ui`, commit `f2db201` (baza `65b22f0`).
Prototyp sprawdza wygodę zaznaczania i podglądu zmian, nie jest implementacją
ticketu. Źródłem implementacji są poniższe kryteria i wybór użytkownika.

## Kryteria akceptacji

- [x] Tryb edycji ma widoczną selekcję i licznik: pojedyncze kliknięcie, dodawanie/odejmowanie molekuł, lasso i wyczyszczenie wyboru. Lasso wybiera oznaczenia według środka; zoom, raw/aligned i przesunięcia ułamkowe nie zmieniają wybranych ID. Wyjście z trybu przywraca zwykłą nawigację.
- [x] Nowa domena, Dodaj do domeny oraz Usuń z domeny działają na bieżącej klatce. Można utworzyć domenę bez wcześniejszej analizy, przy zerowym wyniku oraz z nieprzypisanych molekuł. Brak automatycznej analizy pozostaje jawny. Nie dodaje się nowych detekcji ani nie zmienia ich pozycji.
- [x] Przed zatwierdzeniem widać docelową domenę, liczbę członków i podgląd zmiany. Przeniesienie z innej domeny wymaga jawnej operacji przeniesienia; jedna molekuła ma najwyżej jedną domenę. Usunięcie ostatniego członka usuwa pustą domenę. Pusta selekcja nie tworzy wyniku.
- [x] Ręczne przypisanie może zastąpić odmowę metody, zachowując jej pierwotną przyczynę. Oznaczenia poza polem i wyłączone duplikaty pozostają wyłączone. Domena zachowuje wspólną dotychczasową klasę tylko przy zgodnych przypisaniach; w przeciwnym razie widnieje jako klasa nieustalona, z zachowaniem źródłowej klasyfikacji do porównania. Nadawanie własnych klas dodaje 23.
- [x] Po zatwierdzeniu razem zmieniają się centra, obszary, obrysy, legenda i liczniki. Przybliżona geometria odpowiada członkostwu, nie dopisuje sąsiednich molekuł, nie wychodzi poza pole i nie zasłania innej domeny. Dla niewystarczającego wsparcia pozostają punkty i jawny brak obszaru. Reguła budowy obszaru oraz konfliktów jest opisana i objęta kontrolami.
- [x] Cofnij/Ponów obejmuje całą zatwierdzoną operację, łącznie z geometrią, klasą i licznikami. Przełącznik Automatyczny/Po korektach zachowuje oba stany; przy pracy bez analizy pokazuje brak wyniku automatycznego. Zmiana klatki i powrót zachowują korekty oraz ich historię w sesji.
- [x] Nowa analiza, strojenie i zmiana katalogu nie dziedziczą korekt po numerach domen ani nie usuwają poprawionego wariantu. Spóźniony worker nie nadpisuje edycji. Edycja nie zmienia pierwotnej tabeli przebiegu serii; poprawiony wariant jest oznaczony osobno. Do czasu 24 UI jasno informuje o przechowywaniu korekt tylko w sesji i pozwala anulować zamknięcie/otwarcie innych danych, jeśli utraciłoby pracę.
- [x] Testy obejmują przenoszenie, usunięcie ostatniego członka, odmowę automatu, undo/redo, geometrię selekcji i maski oraz izolację klatek/wyników. Wykonawca dostarcza przykłady do GUI i sprawdza TTMAPP, odróżniając własne sprawdzenie od odbioru użytkownika. Kod i testy spełniają limit 1000/1500 linii; użyto netcat.

## Test ręczny użytkownika

1. W netcat uruchom `python -m stmdomains.main`, otwórz dane TTMAPP wskazane w indeksie planu i przejdź do 259. Bez analizy zaznacz kilka molekuł i utwórz domenę; ma być oznaczona jako ręczna, bez przypisywania jej skuteczności automatu.
2. Dodaj sąsiednie molekuły, usuń jedną, użyj Cofnij/Ponów. Sprawdź równoczesną zmianę oznaczeń, obszaru i liczników. Zmień zoom oraz raw/aligned i powtórz wybór lassem.
3. Oblicz automatyczny wynik jako osobny wariant. Rozszerz jego domenę o nieprzypisane molekuły, jawnie przenieś członka drugiej domeny i porównaj Automatyczny/Po korektach. Oryginalny wynik oraz wcześniejszy ręczny wariant mają pozostać dostępne.
4. Przejdź do 260 i wróć. Korekty 259 pozostają, 260 się nie zmienia. Uruchom ponowną analizę i sprawdź zachowanie poprawionego wariantu; spróbuj zamknąć aplikację, a następnie anuluj utratę niezapisanej pracy.
5. Na dostarczonej kontroli sprawdź zero domen, pojedynczy punkt, konflikt obszarów i brak oznaczeń. Brak danych nie tworzy fikcyjnej domeny ani maski.

## Granice zadania

Edycja członkostwa istniejących molekuł i wynikającego z niego obszaru. Nie obejmuje swobodnego rysowania pikselowej granicy, przesuwania/dorysowywania molekuł, podziału/scalania z 22, własnych klas z 23 ani uczenia modelu. Trwały zapis korekt dodaje 24, eksport 25; do tego czasu istniejące operacje zapisu/eksportu nie mogą przedstawiać samego automatu jako zapisu widocznych korekt.
