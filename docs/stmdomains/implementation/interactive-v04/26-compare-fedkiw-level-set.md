# 26: Porównaj granice domen metodą level-set Gibou–Fedkiwa

**ID:** SD-V4-26

**What to build:** Użytkownik wybiera eksperymentalną metodę Level set we wspólnym oknie analizy, ustawia siłę regularyzacji granic i limit iteracji, oblicza bieżącą klatkę oraz przełącza wynik Geometria / Level set. Widzi rzeczywiste molekuły z przynależnością do domen, wypełnienia i obrysy; może przeglądać wcześniej obliczone klatki suwakiem.

**Blocked by:** [17: Domeny według tolerancji geometrycznych](17-segment-geometric-tolerances.md), [13: Zapis i otwarcie projektu](13-save-open-project.md), [14: Eksport CSV i PNG](14-export-csv-png.md).

**Status:** ready-for-agent — użytkownik zlecił dodanie osobnej próby na końcu planu 2026-11-04; implementacji nie rozpoczęto.

**Miejsce w kolejności:** po 25. To kolejność planu, nie zależność algorytmu od ręcznej edycji. Nie wymaga odłożonych 19–20; następny rekomendowany ticket nadal 18.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady rozszerzeń](README.md#rozszerzenia).
Uzasadnienie, źródła i ograniczenia: [przegląd Fedkiwa po 17](../../research-fedkiw-after-ticket-17.md).

## Pytanie próby i zakres metody

Czy użycie level-set na tych samych cechach sieci co porównywany graf
poprawia granice i ogranicza błędne rozdrobnienie, zachowując rzeczywiste
przerwy oraz małe domeny? Więcej przypisanych molekuł i gładszy obrys
nie są samodzielnym dowodem poprawy.

Wdrożyć jeden wariant inspirowany hybrydą Gibou–Fedkiwa: granice zależne
od cech, z jawną regularyzacją i kontrolą zakończenia. Przed oceną zapisać
konkretną adaptację i różnice względem publikacji wskazanej w przeglądzie.
Zwykły Chan–Vese na jasności nie zastępuje tej próby i nie może być
podpisany jako wykonany Gibou–Fedkiw. Nie wybieramy kilku konkurencyjnych
solverów w ramach jednego ticketu.

## Kryteria akceptacji

- [ ] Przed pomiarami powstaje krótki protokół: identyfikacja wejść, wersje metody, wspólny zestaw cech z 16/17, normalizacja, przygotowanie map przestrzennych, skala i maska poprawnego pola. Oba warianty dostają te same obrazy, centra i pomiary. Jawne są inicjalizacja, źródło liczby regionów modelu, reguła przypisania molekuł do regionów, warunki brzegowe oraz zatrzymania.
- [ ] Porównanie rozdziela różnice między etapami: wejście, kryterium podziału, regularyzacja i tworzenie maski. Mierzy dwa przebiegi analizy, nie izolowany wpływ solvera. Bariery obrazu z 17 są ujawnione i kontrolowane; nie zmienia się ich ukradkiem tylko w jednym wariancie.
- [ ] Cechy kierunkowe zachowują okresowość i dopasowanie rodzin kierunek–rozstaw. Brak pomiaru nie staje się kątem zero. Obszary bez wsparcia i rzeczywiste luki nie są bezwarunkowo wypełniane przez interpolację albo wygładzanie; odmowy mają powód. Kalibracja X/Y i raw/aligned zachowuje zgodność obrazu, centrów i wyniku.
- [ ] Rozłączne składowe otrzymują osobne ID domen. Region level-set nie staje się automatycznie klasą ani zwalidowanym typem struktury. Typ może pozostać nieznany; liczba regionów modelu, klas i końcowych domen jest rozróżniona. Ten ticket nie obiecuje nowego trybu odkrywania nieznanej liczby klas.
- [ ] **Analiza → Analiza… → Metoda domen → Level set (eksperymentalna)** uruchamia właściwe obliczenia bieżącej klatki. Siła regularyzacji i limit iteracji mają opis, zakresy oraz jednostki tam, gdzie występują. Zmiana pól nie zmienia dotychczasowego wyniku; dopiero Analizuj tworzy nowy. Wynik podaje faktycznie użyte parametry i stan zbieżności/osiągnięcia limitu.
- [ ] Przełącznik Geometria / Level set zachowuje klatkę, zoom oraz oba wyniki w sesji. Podstawowy widok to molekuły kolorowane według domeny, szare nieprzypisane, opcjonalne wypełnienia, obrysy i numery. Kliknięcie molekuły pokazuje przypisanie lub odmowę. Nie wystarczy wygładzić wyświetlanej maski przy niezmienionych, sprzecznych z nią przypisaniach.
- [ ] Wyniki ręcznie obliczonych kolejnych klatek pozostają dostępne przez suwak i miniatury. Klatka bez analizy nie dziedziczy wyniku sąsiedniej. Praca w tle, postęp, anulowanie i zamknięcie programu zachowują wcześniejsze wyniki i chronią przed spóźnioną podmianą. Ręczne korekty mają osobną rewizję i nie są nadpisywane ani traktowane jako wejściowa referencja tej próby.
- [ ] Zapis projektu oraz eksport obejmują wybrany wynik i jego rzeczywiste przypisania, maskę, parametry oraz nazwę metody, zgodnie z kontraktem 13/14. Otwarcie odtwarza wynik bez ponownej analizy. Nie jest wymagany zapis całej historii porównań; istniejące korekty i ich obsługa z 24/25 pozostają zachowane.
- [ ] Ocena używa z góry ograniczonego zestawu ustawień, wspólnych kontroli oraz TTMAPP259–266. Te same ustawienia są stosowane między klatkami; bez dopasowywania każdej aż do atrakcyjnego obrazu. Wykonawca dostarcza małe przykłady do otwarcia w GUI i opis oczekiwanego podziału: jedna sieć, dwie orientacje, skok fazy, brakujące centra, rzeczywista przerwa, mała domena, szum/artefakt skanu oraz rzędy bez potwierdzonej sieci 2D.
- [ ] Raport porównuje błędne scalenia, podziały i pominięcia, odmowy oraz czas obliczeń; udział przypisań podaje oddzielnie. Błąd granic liczy tylko przy dostępnej referencji i ustalonej tolerancji. Wynik zerowy na skoku fazy nie zalicza wykrycia granicy. Brak sygnału fazy w cechach i skutki nadmiernego wygładzania pozostają jawnymi ograniczeniami.
- [ ] TTMAPP259–266 to wielokrotnie oglądane klatki jednej akwizycji: ocena jest eksploracyjna, bez deklaracji accuracy lub przenoszenia na inne materiały. Rozdzielono odbiór funkcji w GUI od decyzji o przydatności metody; negatywny wynik badania może zakończyć poprawnie wykonany ticket.
- [ ] Testy i uruchomienie odbywają się w **netcat**. Wykonawca zapisuje komendy, dane, wersje potrzebnych zależności, rzeczywiście wykonane sprawdzenia i ograniczenia. Nowy/zmieniony kod oraz testy mają cel do 1000 linii na plik, twardy limit 1500; adapter metody, obsługa UI i testy pozostają rozdzielone według odpowiedzialności.

## Test ręczny użytkownika

Wykonawca dostarcza gotowe kontrole oraz instrukcję z ustawieniami użytymi
w próbie, bez konieczności samodzielnego przygotowania danych przez użytkownika.

1. Uruchom `conda activate netcat`, następnie `python -m stmdomains.main`.
   Otwórz dostarczoną kontrolę jednej sieci. Oblicz Geometrię i Level set
   z porównywalnym wejściem. Przełączaj wyniki bez utraty klatki i zoomu;
   sprawdź molekuły, wypełnienia, obrysy, liczniki i powody odmów.
2. Zmień siłę regularyzacji. Przed Analizuj wynik musi pozostać identyczny;
   po obliczeniu ma podawać nowe ustawienie. Przywrócenie parametrów
   odtwarza wcześniejsze przypisania i maskę w granicach zapisanej tolerancji.
3. Otwórz kontrole dwóch orientacji, małej domeny i rzeczywistej przerwy.
   Porównaj z opisanym podziałem: wygładzenie nie powinno usuwać małej domeny
   ani sklejać obszarów przez przerwę. Każde odstępstwo zapisz jako wynik
   badania, nie ukrywaj go zmianą progów wyłącznie dla tej kontroli.
4. Sprawdź skok fazy, brakujące centra i artefakt skanu. UI ma rozróżniać
   brak analizy, zero domen i częściowe przypisania. Jeżeli granica nie
   zostaje wykryta, raport musi pokazywać tę porażkę.
5. Otwórz TTMAPP i oblicz klatki 259–266 kolejno z tym samym zestawem
   ustawień. Przesuwaj suwak; każda obliczona klatka pokazuje własne
   molekuły i domeny obu metod. Nieobliczona klatka pokazuje brak wyniku.
6. Anuluj przeliczenie, zmień klatkę podczas pracy i sprawdź zamknięcie
   programu podczas zadania. Wcześniejsze wyniki oraz ręczne korekty
   pozostają bez zmian, nie pojawia się wynik przypisany do złej klatki.
7. Zapisz wybrany wynik Level set, otwórz projekt ponownie oraz wyeksportuj
   PNG/CSV. Porównaj maskę, ID molekuł/domen, odmowy i parametry z UI;
   otwarcie i eksport nie uruchamiają nowych obliczeń.

## Granice zadania

Ograniczona próba na obecnych danych, bez nowego treningu, nowych etykiet
treningowych, dołączania kolejnych materiałów ani pełnego przeszukiwania
parametrów. Oddzielny detektor pokrycia/wysp, automatyczne przeliczanie
całej serii tą metodą, śledzenie domen w czasie i nowy katalog klas nie
wchodzą w zakres. Przeglądanie już obliczonych klatek jest wymagane.

Ocena nie zastępuje porównania freud z 18 ani nie uzależnia próby od FFT/NMF
z 19. Brak poprawy zamyka eksperyment z opisem ograniczeń, a nie z deklaracją
gotowego detektora. Zmiany wspólnej konfiguracji wymagające sesji integracyjnej
opisać w przekazaniu; dane i duże artefakty pozostają poza Git.
