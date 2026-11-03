# 23a: Scalaj i dziel klasy ręcznie

**ID:** SD-V4-23a

**What to build:** Użytkownik wybiera klasy do scalenia albo członków klasy do wydzielenia, określa zakres klatek i zatwierdza podgląd. Widzi poprawione kolory, członkostwo i liczniki; całą operację może cofnąć lub ponowić jednym krokiem.

**Blocked by:** [23: Twórz klasy ręcznie i poprawiaj ich przypisania](23-manual-classes.md).

**Status:** ready-for-agent — dodanie zlecone przez użytkownika 2026-11-03; wykonanie po 23.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady edycji ręcznej](README.md#edycja-ręczna-klas-i-domen). Uruchamianie i testy w **netcat**; cel **1000**, twardy limit **1500 fizycznych linii** na plik kodu i testów.

## Kryteria akceptacji

- [ ] W oknie ręcznych klas są jawne operacje **Scal klasy** i **Podziel klasę**, działające na przypisaniach wyniku Po korektach, także przy pracy ręcznej bez modelu. Użytkownik wybiera konkretną listę klas i jej wersję; jednakowe numery, nazwy lub kolory w innych katalogach nie oznaczają tej samej klasy.
- [ ] Scalenie wymaga przynajmniej dwóch różnych klas źródłowych z członkami w wybranym zakresie. Klasa docelowa to jedna z wybranych źródłowych albo nowa klasa ręczna z nazwą i kolorem. Po zatwierdzeniu otrzymuje sumę członków źródeł w tym zakresie, bez duplikatów i bez przypisywania punktów, których użytkownik nie objął operacją.
- [ ] Podział wydziela jawnie zaznaczony, niepusty i właściwy podzbiór członków jednej klasy do nowej klasy ręcznej. Pozostali członkowie zachowują klasę źródłową. Można wskazać całe domeny albo molekuły, również bez domeny. Pusty wybór, wszyscy członkowie źródła w zakresie lub wskazania z kilku klas dają wyjaśnienie, bez tworzenia pustego wyniku podziału.
- [ ] Zakres to **bieżąca klatka**, **wybrany zakres** lub **wszystkie klatki wybranego wyniku korzystające z tej listy klas**. Przed startem UI pokazuje dokładne klatki, liczności i pominięte klatki z przyczyną (np. inny katalog, brak przypisań). Bieżąca klatka jest domyślna. Podział na wielu klatkach wymaga jawnych wskazań na każdej z nich; lasso z jednej klatki nie przenosi się na inne. Start utrwala zakres i wersje wyników; nawigacja ich nie podmienia, a zmiana danych unieważnia podgląd i wymaga jego odświeżenia.
- [ ] Podgląd pokazuje klasy źródłowe/docelową, nazwę i kolor, liczniki przed/po dla każdej klatki oraz zaznaczenie na obrazie. Można obejrzeć każdą objętą klatkę przed zatwierdzeniem. Anulowanie nie zmienia przypisań, listy klas ani historii. Nie ma cichego scalania klas w innych wynikach ani globalnego aliasu zmieniającego znaczenie klasy poza zakresem.
- [ ] **Scalenie klas nie scala domen:** ich ID, członkostwo, liczba i obrysy pozostają; zmieniają się przypisania klas. Rozdzielone przestrzennie domeny mogą mieć jedną klasę. Podział klasy obejmujący całe domeny również zachowuje ich geometrię. Gdy zaznaczenie obejmuje tylko część domeny, podgląd pokazuje wydzielenie przez reguły z 22/23; jest to część tej samej operacji. Nie powstają domeny wieloklasowe, nakładające się obszary ani mosty przez przerwy. Molekuła bez domeny nadal pozostaje bez domeny.
- [ ] Klasy źródłowe zachowują trwałe ID i pochodzenie; częściowe scalenie nie usuwa ich z listy ani nie zmienia członków poza zakresem. Nowa klasa ma odrębne ID. Źródła mogą pozostać puste w wybranym zakresie; ewentualne usuwanie pustych klas ręcznych nadal podlega zasadom 23. Historia wiąże źródła, cel, członków, klatki i rewizje, bez renumeracji niepowiązanych klas/domen.
- [ ] Całość, także wieloklatkowa zmiana i potrzebne podziały domen, jest jednym atomowym krokiem **Cofnij/Ponów**. Błąd lub anulowanie przed zatwierdzeniem zachowuje poprzedni stan we wszystkich klatkach. Historia wspólnej listy respektuje kolejność późniejszych edycji z 21–23; cofanie nie usuwa klasy używanej przez jeszcze niecofniętą operację. Liczniki zachowują sumę molekuł, a podgląd Automatyczny/Po korektach ma własne legendy.
- [ ] Model, jego K, centroidy, ufności i bazowy wynik pozostają niezmienione. Scalenie/podział nie uczy nowych wzorców ani nie zmienia automatycznych przypisań innych klatek. Nowa analiza zachowuje wariant ręczny zgodnie z 21. UI rozróżnia liczbę klas modelu, listę klas ręcznych i klasy obecne w danym zakresie.
- [ ] Kontrole automatyczne i GUI obejmują scalenie do istniejącej/nowej klasy, podział przez domeny i molekuły, klasę bez domeny, zakres wielu klatek, obce katalogi, pusty/niepoprawny wybór, podgląd/anulowanie, błąd oraz Cofnij/Ponów. Wykonawca dostarcza gotowy mały przykład, instrukcję z oczekiwanymi licznikami i próbę TTMAPP, raportując osobno sprawdzenia agenta i odbiór użytkownika, netcat oraz limit linii.

## Test ręczny użytkownika

Wykonawca dostarcza przykład dwóch klatek ze wspólną listą klas. Na klatce 1 są dwie osobne domeny: 4 molekuły klasy A i 3 klasy B, oraz 2 molekuły A bez domeny. Klatka 2 ma osobne domeny 4 × A i 3 × B. Dodatkowa kontrola ma inny katalog, mimo tych samych nazw klas. Geometria pozwala na opisany podział części domeny.

1. W netcat otwórz przykład. Na klatce 1 wybierz A i B, **Scal klasy → nowa C**, zakres bieżący. Podgląd pokazuje A=6, B=3 → C=9; anuluj i sprawdź, że nic nie zmieniło się w obrazie ani historii.
2. Powtórz i zatwierdź. Klatka 1 ma C=9, nadal dwie domeny i dwa wskazania bez domeny. Klatka 2 pozostaje A=4, B=3. Cofnij i ponów jednym krokiem; następnie cofnij do początku. Sprawdź też scalenie do istniejącej A: A=9, bez nowej klasy.
3. Z pierwotnego stanu scal A i B do nowej C na obu klatkach. Podgląd i wynik: C=9 na pierwszej, C=7 na drugiej, suma 16, nadal po dwie domeny. Przejście do innej klatki podczas podglądu nie zmienia zakresu. Cofnij odtwarza obie klatki razem; Ponów przywraca C. Obcy katalog pozostaje bez zmian i jest jawnie wyłączony z zakresu.
4. Na klatce 1 wydziel z C do nowej D całą domenę czterech molekuł oraz jedno wskazanie bez domeny. Oczekiwane D=5, C=4, nadal dwie domeny i dwa wskazania bez domeny. Klatka 2 pozostaje C=7. Cofnij.
5. Wydziel teraz jedną molekułę z trzycząsteczkowej domeny na klatce 1. Podgląd pokazuje również podział domeny. Po zatwierdzeniu nowa klasa ma 1 członka, C ma 8, a liczba domen wzrasta do 3. Suma członków pozostaje 9; Cofnij odtwarza zarówno klasę, jak i domenę jednym krokiem.
6. Sprawdź pusty wybór, wybór całej klasy do podziału, jednej klasy do scalenia i mieszanie katalogów. Brak przypadkowych zmian. Na wariancie bez analizy sprawdź te same operacje na ręcznych klasach, bez wymyślonego modelu lub ufności.
7. Na TTMAPP oblicz 259–260 ze wspólnym katalogiem, scal dwie klasy w jawnym zakresie, potem wydziel wskazaną domenę do nowej klasy. Porównaj Automatyczny/Po korektach, liczniki, obrysy raw/wyrównany oraz Cofnij/Ponów. K modelu i bazowe przypisania pozostają bez zmian. Zapisz dokładne wyniki tej próby w raporcie wykonania.

## Granice zadania

Ręczne przegrupowanie istniejących przypisań. Bez ponownego klastrowania, douczania, dopasowywania wzorców, automatycznego przenoszenia zaznaczeń pomiędzy klatkami lub łączenia różnych katalogów. Wybrany zakres stanowi jawne zlecenie zmian na konkretnych klatkach, nie automatyczną propagację podobieństwa. Nie dodaje swobodnego rysowania granic. Zapis i odtwarzanie operacji dodaje 24, eksport 25; do tego czasu obowiązuje ochrona niezapisanej pracy z 21.
