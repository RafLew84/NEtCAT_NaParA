# SD-V4-23 — ręczne klasy i przypisania

2026-11-09. Gałąź `domains/interactive-v04-ui`, baza `09d8001`.
Implementacja `94d5a94`, poprawka `b11d09a`.
Odbiór ręczny użytkownika pozostaje otwarty.

## Poprawka podpisów po zgłoszeniu użytkownika — 2026-11-09

Implementacja: `8d4ec04`, baza `a42ca1c`.

Użytkownik wskazał, że wybór **Klasy** nadal zostawiał na obrazie `D1, D2…`,
a oczekiwane znaczenie to klasa **D** i jej domeny **D1, D2…**.
Przyczyną był stały podpis `D + domain_local_id` w warstwie obszarów,
niezależny od trybu wyświetlania. Test rzeczywistego rysowania Qt odtworzył
błąd: oczekiwane `A, A`, otrzymane `D1, D2`; po poprawce przechodzi.

- Automatyczne nazwy klas: **A, B, C… Z, AA, AB…**, według pełnej kolejności
  katalogu. Brak klasy na klatce nie przesuwa liter pozostałych klas.
- **Klasy**: na każdym obszarze nazwa klasy, np. dwa osobne obszary `D`.
  **Domeny**: nazwa klasy i kolejny numer jej domeny, np. `D1`, `D2`.
  Numeracja według wewnętrznych ID, osobno w każdej klasie i klatce.
- Własne nazwy nadal można ustawiać. Nazwa `Wyspa` daje domeny
  `Wyspa · 1`, `Wyspa · 2`; wielkie litery, np. `D`, dają `D1`, `D2`.
  Nieustalona klasa: `?`; jej domeny: `?1`, `?2`.
- Obraz, legenda, panel edycji, szczegóły molekuły/pomiaru i PNG używają
  tej samej reguły. **Obszary… → Podpisy klas / domen** włącza podpisy.
  Panel wyboru domen pokazuje dodatkowo wewnętrzne ID.
- To nazwy prezentacyjne. Wewnętrzne ID, maski, członkostwo i model się
  nie zmieniają. Numer może zmienić się po usunięciu lub zmianie klasy
  innej domeny; nie oznacza śledzenia między klatkami. Pola CSV/JSON
  `class_id` i `domain_local_id` nadal zawierają oryginalne identyfikatory.
  Powtórzenie ręcznej nazwy nie scala różnych klas — rozróżnia je ID.

**Test ręczny poprawki:** uruchom ponownie aplikację w netcat, oblicz lub
otwórz wynik z kilkoma domenami tej samej klasy. Przełącz **Klasy / Domeny**:
litery na obrazie mają odpowiadać legendzie, a osobne domeny mają różne
numery w obrębie klasy. W **Klasy ręczne…** zmień nazwę klasy, zastosuj,
cofnij i ponów; podpisy mają podążać za wyświetlaną wersją. Wyłącz i włącz
podpisy przez **Obszary…**. Sprawdź też **Automatyczny przed korektą**.

Sprawdzenie autora: natywne Qt/X11/netcat, kontrola dwóch domen klasy D
(`D, D` ↔ `D1, D2`), porównanie i Cofnij/Ponów PASS. TTMAPP268, K5
wspólny 259–268: 4 domeny, 119/308 przypisań; podpisy obrazu i PNG PASS.
Obejrzano zrzuty; nie jest to ocena skuteczności metody ani odbiór użytkownika.
Artefakty lokalne: `.scratch/stmdomains-class-names/`.

Weryfikacja poprawki: **40 testów celowanych PASS / 20,59 s**;
pełna regresja **600 PASS / 274,03 s**, mypy **115 modułów PASS**.
Pełny przebieg wykonano poza sandboxem po przerwaniu pierwszej próby
sygnałem SIGTERM. Kod/testy: 16 plików, maksimum 341 linii.

## Obsługa

W **netcat** uruchom `python -m stmdomains.main`. Po otwarciu danych
wybierz **Edytuj domeny → Klasy ręczne…**. Okno klas jest niemodalne:
można pozostawić je obok głównego okna i dalej zaznaczać molekuły.

- **Nowa pusta — podgląd** tworzy klasę z podaną nazwą i kolorem.
  **Nazwa/kolor — podgląd** edytuje wybraną klasę bez zmiany jej ID.
  **Usuń pustą — podgląd** jest dostępne tylko dla ręcznej klasy bez
  członków we wszystkich wariantach korzystających z tej listy.
- Pole **Klasa docelowa** zawiera ID obok nazw oraz pozycję
  **Nieustalona — usuń przypisanie klasy**. Nazwa nie jest tożsamością;
  dwie klasy mogą mieć tę samą nazwę. Tabela pokazuje pochodzenie,
  liczbę członków na klatce i liczbę członków bez domeny; pełne ID w dymkach.
- **Przypisz wybraną — podgląd** zmienia klasę wskazań.
  **Nowa klasa i przypisanie — podgląd** tworzy klasę i przypisuje wskazania
  jako jedną operację Cofnij/Ponów.
- Zakres **Tylko zaznaczone molekuły** wydziela część domeny, jeżeli
  zmienia się jej klasa. Zakres **Całe domeny wskazane przez zaznaczone
  molekuły** obejmuje wszystkich członków tych domen. Wystarczy wskazać
  po jednej molekule; wybór punktu bez domeny w tym trybie daje wyjaśnienie.
- Po obejrzeniu podglądu wybierz **Zastosuj** albo **Anuluj podgląd**.
  Zmiana pól unieważnia podgląd. Dostępne są Cofnij/Ponów i porównanie
  **Automatyczny przed korektą** z jego własną legendą oraz licznikami.

Widok **Klasy** pokazuje nazwy/kolory listy i jawne „bez domeny”.
Widok **Domeny** zachowuje ID i osobne obrysy, także przy wspólnej klasie.
Przypisanie klasy nieprzypisanej molekule nie tworzy domeny, a usunięcie
klasy nie usuwa molekuły ani domeny. Ręczne etykiety nie potwierdzają
fizycznego typu struktury i nie uczą modelu.

## Tożsamość, zakres i historia

Lista ręcznych przypisań ma własny UUID i niezmienne wersje UUID. Etykiety
automatyczne zachowują ID katalogu, etykiety ręczne mają osobne UUID.
Lista jest powiązana z dokładną tożsamością dopasowanego katalogu oraz
serią. Klatki używające tego katalogu współdzielą nazwy/kolory, ale
przypisania zmieniają się tylko na bieżącej klatce. Numer lub nazwa klasy
w innym katalogu nie przenosi ani listy, ani korekt.

Dla klatek bez analizy istnieje osobna lista sesji bez modelu. Wyniki
lokalne bez katalogu, np. freud, mają własne listy związane z danym wynikiem.
Nagłówek okna pokazuje listę, wersję, źródło, korzystające z niej warianty
klatek, K modelu (albo jego brak), liczbę ręcznych klas i liczbę klas
obecnych na klatce. W podglądzie pokazana jest wersja podglądu; oryginał
ma pierwotne nazwy i kolory. Jawny wybór bieżącego automatu zachowuje
niezmieniony widok automatyczny.

Podział przy zmianie klasy korzysta z reguły istniejącego obszaru z
[22](acceptance-22.md#reguła-obszarów). Zmiana klasy kilku domen nie scala
ich geometrii. Tworzenie klasy z przypisaniem i ewentualnym podziałem
jest jednym krokiem historii; osobne zmiany metadanych również można
cofać. Historia sesji obejmuje klatki i wersje wspólnej listy, a przyciski
wskazują klatkę oraz zmianę listy. Zachowane wersje nie modyfikują modelu.

Dopasowany katalog, centroidy, K i automatyczne wyniki pozostają bez zmian.
Nowa analiza nie rozpoznaje klas ręcznych; wcześniejsza korekta i jej
oryginał pozostają do wyboru. Dawne dane oceny zmienionego przypisania
są zachowane jako pochodzenie, bez przypisywania ręcznej klasie ufności
modelu. Operacje domen z 21–22 respektują bieżące ręczne klasy.

Korekty pozostają **tylko w pamięci sesji**; zapis z historią należy do 24,
eksport do 25. Działa ochrona pracy z 21. Scalanie/dzielenie samych klas
w zakresie wielu klatek należy do 23a. Bez nowych zależności i wspólnych zmian.

## Test ręczny użytkownika

1. Otwórz TTMAPP, w **Analiza → Analiza…** wybierz K5, wspólny zakres
   odkrywania 259–260 i oblicz obie klatki. Na 259 otwórz **Klasy ręczne…**,
   wpisz „Moja klasa A”, wybierz kolor i utwórz pustą klasę przez podgląd.
   Anuluj pierwszą próbę, powtórz i zastosuj. Klasa ma 0 członków, K nadal 5.
2. Wskaż członka jednej domeny. W oknie klas wybierz tę klasę i zakres
   **Całe domeny…**, pokaż podgląd i zastosuj. Powtórz dla drugiej domeny.
   Klasy mają wspólny kolor; Domeny nadal dwa ID i osobne obrysy.
3. Zmień nazwę/kolor i zastosuj. Na 260 wybierz tę samą klasę; samo przejście
   nie przenosi do niej członków. Jawnie dodaj wskazania. Wróć na 259;
   nazwa/kolor wspólne, przypisania osobne. Cofnij i ponów ostatnią operację.
4. Wybierz część domeny, zakres **Tylko zaznaczone molekuły** i **Nowa klasa
   i przypisanie**. Podgląd ma podać podział D…→D…+D…. Anuluj, powtórz,
   zastosuj, cofnij i ponów. Członkowie poza zaznaczeniem zachowują klasę.
5. Wskaż molekułę bez domeny, przypisz jej klasę. Licznik „bez domeny” rośnie,
   liczba domen i udział domen nie. Wybierz **Nieustalona** i usuń samo
   przypisanie klasy. Sprawdź też pustą klasę: utwórz, usuń, cofnij.
6. Porównaj **Automatyczny przed korektą**, także legendę i tabelę klas.
   Wykonaj nowe dopasowanie z innym K i wybierz bieżący automat, potem
   jego nowy wariant edycji. Ręczna klasa ze starego katalogu nie przechodzi
   do nowej listy; wcześniejsza korekta nadal dostępna w wyborze wariantu.
7. Na klatce bez analizy utwórz klasę i przypisz punkt. UI ma pokazać brak
   dopasowanego modelu oraz 0 domen. Sprawdź raw/aligned i wybór lassem.

Małe powtarzalne dane kontrolne można utworzyć w netcat:

```bash
python -m stmdomains.tools.class_discovery_demo --output .scratch/stmdomains-ui-23/demo
```

Otwórz `pair_a.moltrack.json` z tego katalogu. W aktualnym oknie **Analiza**
użyj K2 i wspólnego dopasowania z klatek 1–2, oblicz obie; trzecią pozostaw
bez analizy. Daje to kontrolę wspólnej listy, punktów bez domeny i pracy
bez modelu. Dane są syntetyczne, bez etykiet wynikowych; klasy/domeny
oblicza aplikacja. Historyczna instrukcja generatora dotyczy menu z 07;
obecnie wszystkie ustawienia są w **Analiza → Analiza…**.

## Wykonane sprawdzenia autora

Interpreter: `/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Testy publicznych operacji oraz okna obejmują puste klasy, metadane,
przypisania/podziały, klasy bez domeny, historię, różne katalogi,
ponowną analizę i ochronę modelu. Po poprawce nawigacji: **16 testów UI
PASS / 17,14 s**, mypy **114 modułów PASS**. **Pełna regresja: 596 testów PASS / 272,59 s** po poprawce `b11d09a`.

```bash
QT_QPA_PLATFORM=offscreen MPLCONFIGDIR=/tmp/netcat-stmdomains-mpl python -m pytest -q tests/stmdomains
python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/core stmdomains/analysis stmdomains/ui stmdomains/io
```

Przegląd Standards zamknął 1 uwagę heurystyczną; Spec oraz ponowny przegląd
poprawki nawigacji: **0 otwartych uwag**. Test widocznej legendy odtworzył
błąd przed poprawką i przeszedł po przygotowaniu wariantu przed publikacją
klatki. 11 zmienionych plików kodu/testów, maksimum **875 linii**,
wszystkie <1000. Sprawdzono odnośniki dokumentacji, graf 27 ticketów i diff.

Natywne Qt/X11/netcat: główne okno **1024×768**, klasy **620×680**.
Kontrola K2: 357 przypisań / 405 centrów, 17 domen. TTMAPP259 przy K5
dopasowanym wspólnie z 259–260: **116/312, 7 domen**. Nadanie wspólnej
klasy dwóm domenom zachowało dokładną maskę i liczniki domen. Punkt bez
domeny otrzymał klasę bez tworzenia obszaru; częściowa zmiana klasy
wydzieliła domenę jednym cofanym krokiem. Metadane wspólne na 260,
przypisania lokalne, porównanie oryginału, Cofnij/Ponów, raw/aligned oraz
osobna lista bez modelu PASS. Obejrzano zrzuty i poprawiono czytelność
etykiet przy ciemnym kolorze oraz opis wersji w podglądzie.

Skrypt, zrzuty, dane kontrolne i raport: `.scratch/stmdomains-ui-23/`.
To sprawdzenie autora, **nie odbiór użytkownika ani ocena jakości detekcji**.
Liczby bazowe zależą od zakresu dopasowania; różnica względem prób
wcześniejszych ticketów nie jest efektem ręcznej klasy ani dowodem poprawy.
