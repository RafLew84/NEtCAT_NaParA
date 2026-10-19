# Zapis MPP z wartościami i metadanymi

Type: grilling
Label: wayfinder:grilling
Status: resolved
Assignee: rlew
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 03

Zależy od: [Rejestracja i życie wyniku aligned](03-registration.md).

## Question

Jaki kontrakt eksportu MPP zachowa właściwe wartości, orientację, skalę,
metadane i brakujące piksele dla serii original oraz aligned?

Do ustalenia: wybór eksportowanej wersji i klatek; niezależność danych MPP od
gamma; jednostki wartości STP/S94; metadane po połączeniu plików i usunięciu
klatek; sposób kodowania brakujących pikseli; wymagane czytniki odbiorcze.
Ponowny odczyt ma obejmować wartości, orientację, rozmiar piksela, offset,
liczbę i kolejność klatek. Osobno trzeba określić możliwość ponownej rejestracji
zapisanego aligned.

## Comments

### 2026-10-14 — stan rozpoznania

Eksport MPP jest wymaganiem użytkownika. Zaproponowano zapis danych niezależny
od gamma; odpowiedź użytkownika dotyczyła opcji AVI, więc szczegółowy kontrakt
MPP pozostaje do uzgodnienia.

Nie znaleziono istniejącego eksportera MPP. Obecny czytnik obsługuje float64,
ale brakujące piksele aligned to NaN, a rejestracja wymaga skończonych wartości.
Istotne są także różne miejsca obrotu danych i różne jednostki wejścia.
Zobacz [rozpoznanie czytników](../reconnaissance.md).

### 2026-10-16 — konsekwencje kontraktu serii

[Seria wejściowa i usuwanie klatek](01-frame-series.md) dopuszcza różne skale
i kanały przy jednakowych wymiarach. Każda klatka zachowuje własne metadane,
pochodzenie i dostępny czas pomiaru, również po usunięciu innych lub odwróceniu
kolejności. Kontrakt MPP musi rozstrzygnąć zapis takiej serii, w tym różnych
metadanych, przerw w czasach pomiaru i ich odwróconej kolejności. Nie można
zakładać, że metadane pierwszej klatki opisują wszystkie pozostałe.

### 2026-10-19 — rozstrzygnięta rejestracja i aktualny zakres

[Rejestracja i życie wyniku aligned](03-registration.md#answer) ustala wspólny
powiększony obszar, zachowanie jego rozmiaru po usuwaniu i osobne informacje
o polu oryginalnej klatki oraz ważności próbek aligned. Eksport musi zachować
powiązanie z pochodzeniem i metadanymi każdej klatki; przy niespójnej skali
wynik nie ma jednej potwierdzonej skali fizycznej. Nie wolno mylić braku pomiaru
z zerem ani wyliczać pola oryginalnej klatki z liczby ważnych próbek aligned.

Odwracanie kolejności zostało wycofane z programu; wcześniejsze wzmianki o nim
w komentarzach opisują poprzedni zakres. Pozostają do ustalenia zapis przerw
w czasach po usuwaniu i pozostałe szczegóły eksportu. Obecny materializator
tworzy float32, a rejestracja wymaga skończonych wejść; precyzja zapisu,
kodowanie braków i możliwość ponownej rejestracji aligned wymagają decyzji.

### 2026-10-19 — rozpoczęcie rozmowy o eksporcie

Ticket przejęty do uzgodnienia specyfikacji, bez implementacji eksportera.
Pierwsza runda pytań czeka na odpowiedzi użytkownika:

1. Propozycja: wszystkie pozostałe klatki w bieżącej kolejności do jednego
   MPP; wybór original/aligned, domyślnie aktualny widok; bez wyboru zakresu.
2. Propozycja: wartości danych niezależne od gamma, zoomu i kolorów;
   aligned zawiera wartości po interpolacji rejestracji.
3. Wymagane programy odbiorcze: czy wystarczą STM Viewer, NaPara, NanoTrack
   i MolTrack, czy potrzebny jest też wskazany program zewnętrzny?

To pytania i rekomendacje, nie zatwierdzone decyzje. Wybór odbiorców wpływa
na dalsze ustalenia dotyczące metadanych, brakujących próbek i zgodności.
Fakty z kodu i prób zapisano w
[rozpoznaniu eksportu MPP](../reconnaissance.md#uzupełnienie-kontrakt-odczytu-mpp).

### 2026-10-19 — odpowiedzi: zakres, wartości i WSxM

Użytkownik potwierdził zapis całej pozostałej serii do jednego MPP z wyborem
original/aligned (domyślnie aktualny widok), bez wyboru zakresu klatek.
Potwierdził dane niezależne od gamma, zoomu i kolorów; aligned zapisuje
wartości po interpolacji rejestracji. Jako wymagany program zewnętrzny
wskazał WSxM. Dochodzi on do odbiorców z repozytorium.

Zgodność z WSxM wymaga osobnego sprawdzenia. Dotychczasowe próby własnego
czytnika nie potwierdzają odczytu NaN ani dodatkowych metadanych w WSxM.
Oczekują kolejne dwa pytania:

4. Propozycja: aligned jest eksportem wyniku bez dodatkowej kopii oryginałów;
   do ponownej rejestracji użytkownik wczytuje original.
5. Propozycja: znane czasy pomiaru i przerwy pozostają bez zmian, brak czasu
   nie jest zastępowany czasem wynikającym z FPS; kolejne numery wyjściowe
   są odrębne od pochodzenia klatek.

Punkty 4–5 nie zostały jeszcze zatwierdzone. Sposób zachowania geometrii,
brakujących próbek i metadanych w eksporcie zgodnym z WSxM pozostaje otwarty.

### 2026-10-19 — czasy potwierdzone; pytanie o rozpoznawanie aligned

Użytkownik potwierdził zachowanie znanych czasów i pochodzenia klatek zgodnie
z punktem 5. W punkcie 4 zapytał: „w jaki sposób jesteś w stanie odróżnić
dopasowany mpp od oryginalnego?”. Nie jest to zatwierdzenie proponowanej
polityki ponownej rejestracji.

Wyjaśnienie: nie można wiarygodnie rozpoznać historii obróbki z samych pikseli.
Własny eksport może zawierać jawne metadane rodzaju obrazu i rejestracji;
w pliku zewnętrznym bez takich informacji historia pozostaje nieznana.
Brak znacznika nie dowodzi, że obraz nigdy nie był dopasowany. Wczytane
piksele mogą stanowić wejście do nowego dopasowania, lecz nie odtwarzają
oryginałów sprzed interpolacji. Osobną przeszkodą są brakujące próbki NaN,
których obecne backendy nie obsługują. Polityka pozostaje do uzgodnienia.

### 2026-10-19 — ponowna rejestracja rozstrzygnięta

Użytkownik potwierdził doprecyzowany punkt 4: o możliwości nowego dopasowania
decydują faktycznie wczytane dane, nie znacznik original/aligned. Program
nie odtwarza wcześniejszych oryginałów z interpolowanego wyniku. Przy
brakujących próbkach obecne metody odmawiają rejestracji i podają przyczynę.
Poprzednia propozycja ogólnego zakazu rejestracji aligned została zastąpiona.

[Rozpoznanie zgodności z WSxM](../wsxm-mpp-compatibility.md) nie potwierdziło
obsługi NaN ani własnych metadanych per klatka przez WSxM. Nie dowodzi to,
że program ich nie obsługuje. Potrzebny jest rzeczywisty test odbiorczy.

### 2026-10-19 — plik towarzyszący i korekta zakresu WSxM

Użytkownik zaakceptował MPP z towarzyszącymi metadanymi. STM Viewer ma je
odczytywać automatycznie; pełna informacja wymaga przenoszenia obu plików.
Dodatek zachowuje pochodzenie, czasy, pierwotne wymiary, przesunięcia
oraz informacje o brakujących próbkach.

Na propozycję blokowania niejednorodnej serii „przy eksporcie do WSxM”
użytkownik odpowiedział: „nie chcę eksportować do wsxm, chcę tylko tworzyć
plik”. Przyjmujemy zwykły zapis MPP, bez osobnego trybu eksportu do programu.
Nie zatwierdzono blokowania zapisu przy różnej kalibracji.

Oczekujące doprecyzowanie punktu 7: proponowany zapis także niejednorodnej
serii, z dokładnymi metadanymi per klatka w dodatku; wspólny nagłówek używa
jednostek umownych tam, gdzie nie istnieje wspólna skala/jednostka.

Oczekujący punkt 8: proponowany zapis braków aligned jako NaN, z zachowaniem
pełnego powiększonego obrazu oraz geometrii i informacji o ważności próbek
w metadanych. Działanie w WSxM pozostaje do sprawdzenia; nie przedstawiamy
niezweryfikowanej zgodności jako potwierdzonej.

### 2026-10-19 — komplet odpowiedzi

Użytkownik potwierdził doprecyzowany punkt 7: zapis także serii o różnych
skalach/kanałach, z parametrami per klatka w dodatku i jednostkami umownymi
we wspólnym nagłówku tam, gdzie nie istnieje wspólna kalibracja.
Potwierdził punkt 8: NaN jako brak wartości, pełny obszar aligned,
bez zastępowania braków zerem i bez przycinania. Zgodność takiego pliku
z WSxM pozostaje niezweryfikowana i wymaga sprawdzenia.

Wszystkie pytania tej decyzji zostały rozstrzygnięte. Obowiązujący kontrakt
poniżej zastępuje wcześniejsze propozycje z komentarzy, w szczególności
zakaz ponownej rejestracji aligned i blokadę zapisu niejednorodnej serii.

## Answer

Rozstrzygnięto 2026-10-19 na podstawie odpowiedzi użytkownika.
To specyfikacja pierwszej wersji, nie wdrożony eksporter.

### Co zapisujemy

- Jedna operacja tworzy **jeden film MPP i towarzyszący plik metadanych**.
  Film obejmuje wszystkie klatki pozostałe w bieżącej serii, w jej kolejności.
  Nie ma wyboru zakresu ani pojedynczych klatek; seria jednoklatkowa jest
  poprawna, pusta seria nie podlega zapisowi.
- W oknie zapisu wybieramy original albo aligned. Domyślny jest aktualnie
  oglądany wariant; aligned można wybrać tylko przy dostępnym kompletnym
  wyniku. Nie uruchamiamy rejestracji automatycznie podczas zapisywania.
- Zapisujemy całe obrazy wybranej wersji, niezależnie od zoomu i obszaru
  podglądu. Dla aligned zachowujemy pełny powiększony obszar, również po
  usunięciu pierwszej albo skrajnie przesuniętej klatki. Eksport nie powoduje
  ponownej interpolacji, zmiany położenia ani zmniejszania obszaru.
- Jest to zwykły zapis MPP. WSxM jest wskazanym programem odbiorczym;
  nie tworzymy osobnego trybu „eksport do WSxM”. Nie dodajemy do pliku
  drugiego zestawu obrazów ani stanu całej sesji programu.

### Wartości, jednostki i orientacja

- MPP zawiera wartości obrazu STM, niezależne od gamma, kolorów, poziomów
  jasności i powiększenia podglądu. Original zapisuje wartości z odczytu
  źródeł; aligned — gotowe wartości po interpolacji rejestracji.
- Format liczbowy zapisu to float64 little endian, zgodnie z obsługiwanym
  wariantem MPP. Eksporter nie kwantyzuje obrazu do 8/16 bitów, nie normalizuje
  jego zakresu i nie przelicza wartości według amplitudy Z z nagłówka.
  Przejście wcześniej obliczonego float32 do float64 nie odzyskuje utraconej
  precyzji; zapis ma zachować wartości już obecne w pamięci.
- Dla STP/MPP zachowujemy liczby oraz znaną jednostkę wartości ze źródła.
  Sama liczba w `Z Amplitude` nie służy do ponownego skalowania próbek.
  Dla S94 zachowujemy wynik kalibracji czytnika: nm dla znanej kalibracji
  topografii, nA dla prądu. Przy nieznanym wzmocnieniu/trybie jednostka
  pozostaje nieznana lub surowa; nie deklarujemy nm bez podstaw.
- Jednostka wartości sygnału jest odrębna od skali przestrzennej X/Y.
  Dokładne jednostki i parametry każdej klatki trafiają do metadanych.
- Ponowny odczyt w STM Viewer ma dawać tę samą orientację, wymiary,
  wartości i pozycje brakujących próbek. Różne miejsca obrotu w obecnych
  czytnikach trzeba uzgodnić na warstwie wejścia/wyjścia, a nie kompensować
  przypadkowym kolejnym obrotem. Odbiór obejmuje asymetryczny obraz oraz
  ścieżki STP → MPP, S94 → MPP i MPP → MPP.

### NaN i geometria aligned

- Brakujące próbki pozostają **NaN**. Nie zapisujemy w ich miejsce zera,
  mediany, powielonego brzegu ani obrazu szachownicy. Szachownica jest
  sposobem wyświetlenia braku pomiaru.
- Dla każdej klatki aligned zachowujemy w metadanych pierwotne wymiary,
  nanoszone przesunięcie XY oraz położenie pola oryginalnej klatki w obszarze
  zapisanego filmu. Zachowujemy rozmiar wspólnego obszaru, jego położenie
  względem odniesienia i pochodzenie historycznej klatki odniesienia,
  także jeśli została usunięta z serii.
- Pole oryginalnej klatki jest prostokątem wynikającym z wymiarów i
  transformacji. Maska ważności opisuje dostępność próbek po interpolacji.
  Nie wyznaczamy pola z liczby lub obwiedni skończonych próbek.
- Sposób zakodowania ważności w metadanych musi pozwalać ją jednoznacznie
  odtworzyć. Dla zapisu z NaN może wskazywać regułę odczytu ważności z próbek
  filmu; nie trzeba kopiować całej maski do rozbudowanej tablicy JSON.
- Geometria musi odnosić się do jasno określonego układu obrazu. W układzie
  aplikacji X rośnie w prawo, Y w dół, a przesunięcie jest nanoszone na obraz.
  Przekształcenie orientacji przy zapisie/odczycie nie może rozjechać geometrii
  i odpowiadających jej pikseli.

### Metadane całego filmu i każdej klatki

- Różne skale, kanały lub jednostki **nie blokują zapisu**. Nie zmieniamy
  wymiarów ani nie przeskalowujemy danych w celu ujednolicenia serii.
- Wspólny nagłówek zawiera parametry wspólne i znane. Przy różnej lub
  nieznanej skali przestrzennej używamy jednostek umownych; przy braku
  wspólnej jednostki sygnału również nie przypisujemy wszystkim jednej
  fizycznej jednostki. Różny/nieznany kanał jest oznaczony odpowiednio,
  zamiast kopiowania kanału pierwszej klatki.
- Wspólność oceniamy dla danej wielkości osobno: np. wspólny rozmiar piksela
  nie dowodzi wspólnej jednostki sygnału. Jednostki umowne w nagłówku nie
  zmieniają liczb próbek. Odbiorca samego MPP nie otrzymuje wówczas pełnej
  indywidualnej kalibracji; jest ona w pliku towarzyszącym.
- Dla zgodnej, znanej skali aligned zachowuje rozmiar piksela, a rozmiar
  fizyczny wynika z nowych wymiarów obszaru. Offset wynikowego obszaru musi
  odpowiadać jego układowi współrzędnych; źródłowe offsety zachowujemy osobno.
  Nie kopiujemy offsetu jednego źródła jako opisu wszystkich klatek.
- Dodatek zachowuje dla każdej klatki pochodzenie, pierwotny numer w źródle,
  dostępne czasy, kanał, jednostkę wartości, skalę X/Y, offset, kąt i pozostałe
  dostępne parametry pomiaru, a także źródłowe nagłówki. Informacja o braku
  parametru jest odrębna od rzeczywistego zera.
- Zachowujemy parametry zadeklarowane przez źródło; nie zgadujemy brakujących
  danych ani nie naprawiamy pomiaru na podstawie samej wielkości liczby.
  Dane wskazane jako zastępcze nie stają się potwierdzoną kalibracją po zapisie.
  Przykładowe 1000 nm i zera w zapisie TTMAPP nie są wzorcem prawidłowych
  warunków pomiaru.

### Czasy i pochodzenie

- Numery w nowym filmie są kolejne, odrębne od numerów źródłowych. Zapis po
  usunięciu B z [A, B, C] zawiera [A, C], a pochodzenie C nadal wskazuje C.
- Zachowujemy znane czasy pomiaru bez zerowania początku, usuwania przerw
  i zastępowania ich czasem odtwarzania. Przykład: [10, 20, 35] s po usunięciu
  środka daje [10, 35] s, a nie [0, 1/FPS].
- Brak czasu pozostaje brakiem. Metadane per klatka mogą przechować częściowo
  znane czasy. Wspólny nagłówek nie zawiera pozornie kompletnej osi czasu
  wytworzonej przez wpisanie zer za brakujące wartości.
- Znane czasy w `Frames Synchronization` zapisujemy w sekundach, z kluczami
  odpowiadającymi numerom wyjściowym. Źródłowe indeksy i oryginalny opis czasu
  pozostają osobno. Obecny parser wymaga poprawki dla niepełnych czasów
  i poprawnej interpretacji jednostek.

### Powiązanie plików i ponowne otwarcie

- Plik metadanych jest wersjonowany i jednoznacznie powiązany z konkretną
  zawartością MPP. Domyślna nazwa implementacyjna: `<nazwa>.mpp.stmviewer.json`
  obok `<nazwa>.mpp`. Nie wymaga dodatkowego wskazywania przy zwykłym otwarciu.
- Powiązanie sprawdzamy na podstawie zawartości filmu oraz zgodności liczby
  i wymiarów klatek; sama zbieżność nazw nie wystarcza. Przeniesienie pary
  plików do innego katalogu nie unieważnia powiązania.
- Bez dodatku film nadal można otworzyć. Dostępne są dane i informacje
  odczytane z nagłówka; nie obiecujemy pełnego pochodzenia i geometrii sprzed
  rejestracji. Niedopasowany, uszkodzony lub nierozumiany dodatek nie może
  zostać zastosowany do obrazu; aplikacja wyjaśnia brak jego użycia.
- Dodatek określa, którą wersję wyeksportowano, oraz znaną historię
  przekształceń. Nie dowodzimy wcześniejszego dopasowania z samych pikseli.
  Brak znacznika w zewnętrznym MPP oznacza nieznaną historię.
- Original zawsze oznacza obraz wejściowy bieżącej serii. Wczytany plik,
  który historycznie zawiera aligned, staje się takim wejściem; znacznik
  nie odtwarza nieobecnego zestawu wcześniejszych oryginałów ani widoku aligned
  bieżącej sesji. Nowy import zachowuje ustalone zasady startu podglądu.
- Ponowną rejestrację dopuszczamy według właściwości wczytanych danych.
  Nie blokuje jej sama etykieta aligned. Obecne metody wymagają skończonych,
  kompletnych wejść: brakujące próbki powodują czytelne odrzucenie operacji,
  bez ukrytego wypełniania i bez utraty wcześniejszego wyniku.

### Spójność operacji zapisu

Implementacja zapisuje spójny stan serii, wybranej wersji i jej metadanych;
zmiana klatki podglądu nie może zmienić zawartości rozpoczętego eksportu.
Sukces oznacza zapis MPP oraz poprawnie powiązanego dodatku. Przy błędzie
nie raportujemy sukcesu ani nie pozostawiamy pozornie poprawnej pary.
Stosujemy pliki tymczasowe i kontrolowaną podmianę; nadpisanie istniejącego
wyniku wymaga standardowego potwierdzenia w oknie zapisu. Operacja nie
zmienia danych bieżącej serii w pamięci.

Dwa zwykłe pliki nie tworzą jednej atomowej operacji systemu plików.
Kontrola zgodności musi więc odrzucić niedopasowane metadane także po
przerwaniu procesu między podmianami. Nie obiecujemy odtworzenia pełnych
metadanych po edycji lub ponownym zapisaniu samego MPP w innym programie.

### Odbiorcy i kryteria poprawności

Pełny kontrakt dotyczy ponownego otwarcia pary MPP/metadane w STM Viewer.
Obowiązkowo sprawdzamy też odczyt filmu przez NaPara, NanoTrack i MolTrack.
Zgodnie z późniejszą [decyzją odbioru](06-acceptance.md#answer), próba WSxM
jest dodatkowa i nie blokuje pierwszej wersji. Poprawne otwarcie nie wystarcza
do potwierdzenia wartości, orientacji, skali ani obsługi brakujących próbek.

**Obsługa NaN i zachowanie danych w WSxM nie zostały potwierdzone.**
Są przedmiotem dodatkowej próby, nie powodem do niejawnego wypełniania
braków, kadrowania albo blokowania zapisu mieszanej serii. W razie problemu
wynik testu trzeba ujawnić; alternatywny zapis wymaga osobnej decyzji.
Źródła i ograniczenia: [rozpoznanie WSxM](../wsxm-mpp-compatibility.md).

| Przypadek | Oczekiwany rezultat |
| --- | --- |
| Zmiana gamma, zoomu i kolorów przed zapisem | Te same wartości MPP i geometria. |
| Original z wartościami float64 | Po odczycie te same liczby i orientacja, bez kwantyzacji. |
| Aligned z przesunięciem subpikselowym | Zapis gotowych próbek bez kolejnej interpolacji; NaN i geometria zachowane. |
| Usunięta klatka skrajna lub odniesienia | Niezmienione wymiary aligned i położenia pozostałych; zachowane historyczne odniesienie. |
| Mieszane skale/kanały/jednostki | Zapis dozwolony; brak fałszywej wspólnej kalibracji, parametry per klatka w dodatku. |
| Usunięty środek serii z czasami | Kolejne numery wyjściowe, oryginalne pochodzenie i przerwa czasowa. |
| Nieznane czasy lub jednostka | Jawny brak/nieznana jednostka, bez fikcyjnych zer lub nm. |
| MPP bez metadanych towarzyszących | Film otwieralny; nieodtwarzalna historia/geometria nie jest zgadywana. |
| Metadane należące do innej zawartości MPP | Nie są nakładane na film; podana przyczyna. |
| Ponowne dopasowanie filmu oznaczonego aligned | Dopuszczone przy poprawnych wejściach; NaN odrzucane przez obecne metody. |
| Otwieranie w WSxM | Dodatkowa, nieblokująca próba orientacji, liczb, skali i braków; nie utożsamiamy jej z testem własnego czytnika. |

Wspólne czytniki wymagają uzgodnienia jednostek, orientacji, niepełnych czasów,
metadanych per klatka i nagłówków przekraczających obecny limit 1000 linii.
Nie zmieniono ich w tej sesji. Dane, tolerancje i wymagane środowiska określa
[odbiór pierwszej wersji](06-acceptance.md#answer).
