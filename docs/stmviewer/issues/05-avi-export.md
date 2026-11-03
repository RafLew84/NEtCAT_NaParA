# Opcje filmu AVI

Type: grilling
Label: wayfinder:grilling
Status: resolved
Assignee: rlew
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 02, 03

Zależy od: [Podgląd, gamma i odtwarzanie serii](02-preview-playback.md)
oraz [Rejestracja i życie wyniku aligned](03-registration.md).

## Question

Jakie wybory przy zapisie AVI ma otrzymać użytkownik i co dokładnie znajdzie się
w wyeksportowanym filmie?

Do ustalenia: pełne klatki lub wycinek podglądu; gamma i poziomy obrazu;
original/aligned; FPS i jego relacja do prędkości Play; wszystkie klatki lub
zakres; osie/podziałka/opisy; wygląd pustych obszarów; zgodność odtwarzania
i domyślny kodek. Wybrany wycinek musi mieć jednoznaczne znaczenie dla całej serii.

## Comments

### 2026-10-14 — odpowiedź użytkownika

Na propozycję filmu z gamma i zadanym FPS, z pełnych klatek niezależnie od
zoomu, użytkownik odpowiedział: „przy zapisie avi do wyboru dla użytkownika”.
Wymagany jest zatem wybór przy eksporcie; dokładny zestaw opcji pozostaje
otwarty. Nie przyjmujemy jeszcze automatycznie jednego sposobu kadrowania.

W repo nie znaleziono eksportera AVI. Lokalny netcat zawiera OpenCV
z deklarowaną obsługą FFmpeg; dostępność konkretnego kodeka wymaga sprawdzenia
zapisu i odczytu. Zobacz [rozpoznanie środowiska](../reconnaissance.md).

### 2026-10-19 — kontrakt podglądu

[Podgląd, gamma i odtwarzanie serii](02-preview-playback.md) ustala tempo Play,
wspólną gamma, osobne obszary podglądu original/aligned oraz szachownicę poza
pomiarem. Ich przeniesienie do filmu, w tym wybór FPS i kadrowania, pozostaje
decyzją tego ticketu; nie wynika automatycznie z ustawień podglądu.

### 2026-10-19 — geometria rejestracji

[Rejestracja i życie wyniku aligned](03-registration.md#answer) zachowuje
rozmiar wspólnego obszaru po usuwaniu klatek, również skrajnych. Nowa udana
próba może zmienić ten rozmiar. Geometria pola oryginalnej klatki i maska
ważności próbek są osobne; opcje kadrowania oraz wygląd braków w filmie
powinny korzystać z właściwej informacji. Ich eksport nadal rozstrzyga ten ticket.

### 2026-10-19 — odpowiedzi użytkownika: zawartość i sterowanie

Użytkownik potwierdził original/aligned oraz całą serię lub zakres od–do,
z domyślną aktualną wersją i całą serią. Wybrał **tylko pełny obraz**;
nie dodajemy eksportu wycinka podglądu.

Potwierdził wybór gamma podglądu lub 1,0, domyślnie z podglądu. FPS ma
wybierać użytkownik przy eksporcie. Potwierdził czysty obraz z opcjonalną
podziałką i numerem klatki/czasem pomiaru, bez osi, paneli i obrysu źródła.
Zamiast proponowanej szachownicy wybrał tło **czarne, szare lub białe**.
Jako wartość początkową przyjęto czarne tło.

### 2026-10-19 — odpowiedzi użytkownika: kontrast, proporcje i kodek

Użytkownik potwierdził:

- automatyczny kontrast osobno dla każdej klatki (domyślnie) albo wspólny
  dla całego eksportowanego filmu;
- rozmiar wyznaczany z danych, niezależnie od okna, z proporcjami fizycznymi
  przy wspólnej znanej skali X/Y i pikselowymi przy nieznanej/niespójnej skali;
  w pierwszej wersji bez ręcznego wyboru rozdzielczości;
- wybór MJPG (domyślny) lub FFV1; bezstratność FFV1 dotyczy wyrenderowanego
  obrazu filmu, nie oryginalnych wartości pomiarowych.

[Lokalne rozpoznanie i próba kodeków](../avi-export-reconnaissance.md) wykazały
ciche obcinanie nieparzystych wymiarów przez obecny writer; jawne dopełnienie
zachowuje krawędzie. Przyjęto je jako konieczną realizację pełnego obrazu,
bez dodatkowej opcji przycinania. Zgodność z zewnętrznymi odtwarzaczami
pozostaje do potwierdzenia przy odbiorze.

## Answer

Rozstrzygnięto 2026-10-19. Specyfikacja eksportu prezentacyjnego AVI;
wartości pomiarowe przechowuje odrębny [zapis MPP](04-mpp-export.md#answer).

### Opcje okna zapisu

| Ustawienie | Wybór | Wartość początkowa |
| --- | --- | --- |
| Wersja | original / aligned | Aktualnie oglądana. |
| Klatki | Cała seria / zakres od–do | Cała pozostała seria. |
| Gamma | Z podglądu / neutralna 1,0 | Z podglądu. |
| Tempo | FPS ustawiane przy eksporcie | Aktualne tempo Play; kontrolka 1–30 FPS. |
| Kontrast | Osobno dla każdej klatki / wspólny dla filmu | Osobno dla każdej klatki. |
| Tło | Czarne / szare / białe | Czarne. |
| Podziałka długości | Włączona / wyłączona | Wyłączona. |
| Numer klatki i czas pomiaru | Włączone / wyłączone | Wyłączone. |
| Kodek | MJPG / FFV1 | MJPG. |

**Zapisujemy wyłącznie pełne obrazy.** Zoom, przesunięcie podglądu i rozmiar
okna nie wyznaczają kadru. Nie ma opcji wycinka ani ręcznej rozdzielczości.
Przed zapisem pokazujemy wynikowy rozmiar, liczbę klatek i czas filmu,
uwzględniając korektę proporcji oraz niezbędne dopełnienie.

### Wersja, zakres i tempo

- Aligned jest dostępne tylko wtedy, gdy seria ma kompletny wynik rejestracji.
  Zapis nie uruchamia rejestracji i nie zastępuje brakującego aligned przez
  original bez wiedzy użytkownika.
- Zakres od–do dotyczy pozycji w bieżącej serii, od 1 do N, z oboma końcami
  włącznie. Wymagane `1 ≤ od ≤ do ≤ N`. Usuniętych klatek nie przywracamy.
  Kolejność jest taka jak w serii; każda wybrana klatka trafia do filmu raz.
- Pusta seria nie podlega zapisowi. Jedna klatka lub zakres jednoklatkowy
  są dopuszczalne; film zawiera jedną klatkę, bez sztucznego przedłużania.
- Użytkownik wybiera FPS w oknie eksportu. Jest to stałe tempo filmu,
  niezależne od czasu pomiaru; czas trwania wynosi liczba klatek / FPS.
  Zmiana FPS eksportu nie zmienia tempa Play. Pętla podglądu nie dodaje
  powtórzeń ani pętli do pliku.
- Wybór aligned zachowuje cały rozmiar wyniku, również po usunięciu klatki
  skrajnej/odniesienia lub przy zapisie tylko części serii. Nie wyznaczamy
  nowego mniejszego obszaru z eksportowanego podzbioru.

### Kontrast i gamma

- Renderer tworzy prezentację w skali szarości. Osobno wyznacza poziomy
  kontrastu, a następnie stosuje wybraną gamma jednakową dla całego filmu.
  Gamma 1,0 oznacza neutralną korekcję gamma, nie zapis surowych liczb do AVI.
- Tryb osobny wyznacza poziomy na podstawie ważnych wartości każdej klatki.
  Tryb wspólny używa jednego minimum/maksimum ważnych wartości ze wszystkich
  eksportowanych klatek wybranej wersji. Klatki poza zakresem nie wpływają
  na wspólny kontrast.
- Brakujące próbki, tło, opisy i techniczne dopełnienie nie uczestniczą
  w obliczaniu poziomów. Nie wolno włączać do nich mediany/zera użytego
  wyłącznie do wyświetlania przez stary widget.
- Liczby pomiędzy poziomami są mapowane na jasność; gamma stosuje tę samą
  konwencję co podgląd (`u ** (1 / gamma)` dla znormalizowanej jasności).
  Nie należy interpretować wspólnego kontrastu jako ujednolicenia różnych
  jednostek pomiarowych w niejednorodnej serii.
- Stały zakres, gdy minimum równa się maksimum, musi mieć deterministyczne
  wypełnienie bez dzielenia przez zero: jasność `u = 0,5` przed gamma.
  Klatka bez ważnych próbek daje wybrane tło i ewentualne opisy; nie znika
  z filmu i nie powoduje przesunięcia numeracji/czasów.
- Wartość gamma jest pobrana przy ustalaniu parametrów zapisu. Późniejsza
  zmiana podglądu nie zmienia kolejnych klatek już rozpoczętego eksportu.
  Nie przechwytujemy zrzutów okna ani jego ekranowego zmniejszenia obrazu.

### Pełny obraz, proporcje i rozmiar

Cały eksportowany film ma jeden rozmiar obrazu i zachowuje pełną zawartość
wybranego wariantu. Ustawienie okna i DPI ekranu nie wpływają na wynik.

- Przy wspólnej, znanej i dodatniej skali X/Y eksportowanych klatek
  zachowujemy fizyczne proporcje obrazu. Sama wartość pola widzenia nie
  powiększa filmu; znaczenie ma stosunek rozmiarów piksela X/Y.
- Gdy skala jest nieznana albo niespójna, używamy proporcji pikselowych.
  Nie przyjmujemy kalibracji pierwszej klatki jako kalibracji całego filmu.
- Automatyczny rozmiar zaczyna od W×H danych. Przy anizotropii zwiększamy
  odpowiedni wymiar zgodnie ze stosunkiem skali X/Y, bez pomniejszania
  drugiego. Po zaokrągleniu do pełnych pikseli przykład 256×256 ze skalą
  X dwa razy większą od Y daje 512×256. Przy kwadratowym pikselu lub
  proporcjach pikselowych pozostaje 256×256.
- Przeliczenie proporcji jest renderowaniem filmu. Nie zmienia pomiaru ani
  nie wykonuje ponownej rejestracji. Maska ważności musi przejść tę samą
  zmianę geometrii; NaN nie może zostać zwykłą wartością obrazu, a tło nie
  może wpływać na poziomy kontrastu.
- Jeśli wynikowy wymiar jest nieparzysty, dodajemy najwyżej jeden piksel
  z prawej i/lub u dołu do najbliższego parzystego rozmiaru, w wybranym
  kolorze tła. Nie obcinamy ostatniej kolumny/wiersza ani nie zmniejszamy
  całego obrazu. To dopełnienie nie należy do pola pomiaru i nie zmienia
  przelicznika podziałki.
- Rozmiar i położenie obrazu, tła i dodatków są stałe w całym filmie.
  Brakujące obszary mogą zmieniać się zgodnie z maską każdej klatki;
  pełny obszar aligned nie podąża za poruszającym się polem pomiaru.

### Tło i dodatki

- Brakujące próbki pokazujemy wybranym tłem: czarnym, szarym lub białym
  (odpowiednio RGB 0, 128 lub 255 w każdym kanale). Nie ma szachownicy
  w AVI. Gamma nie działa na tło, podziałkę ani napisy.
- Do kodeka trafia kompletny raster uint8, bez NaN. Wypełnienie tłem jest
  elementem prezentacji; w źródłach i [zapisie MPP](04-mpp-export.md#answer)
  braki zachowują znaczenie braku pomiaru.
- Domyślnie zapis zawiera sam obraz z tłem. Opcjonalne dodatki są rysowane
  przez renderer filmu, bez osi, histogramu, paneli programu ani obrysu
  oryginalnego pola klatki.
- Podziałka wykorzystuje geometrię wynikowego filmu po zmianie proporcji.
  Przy wspólnej wiarygodnej kalibracji podaje jednostkę fizyczną; przy jej
  braku podaje piksele z jawnym oznaczeniem `px`. Nie dopisujemy fikcyjnych
  nm na podstawie danych zastępczych lub pierwszej klatki mieszanej serii.
- Numer odnosi się do pozycji w bieżącej serii, jak w aplikacji. Zapis zakresu
  5–10 z serii 20 klatek zachowuje oznaczenia 5/20 do 10/20. Pochodzenie
  źródłowe jest odrębnym pojęciem, nie numerem odtwarzanej klatki filmu.
- Czas to dostępny czas pomiaru przypisany klatce, z zachowaniem przerw.
  Nie wyliczamy go z FPS. Przy braku czasu opis wskazuje brak tej informacji;
  nie pokazuje fikcyjnego zera ani czasu od początku filmu.
- Dodatki pozostają czytelne na każdym z trzech teł. Gdy obraz jest za mały
  na czytelne dodatki, okno zapisu wskazuje problem przed startem; nie wolno
  po cichu kadrować obrazu lub usuwać wybranych opisów.

### Kodek i zapis

- Dostępne wybory: **MJPG** domyślnie, kompresja stratna, oraz **FFV1**,
  bezstratny zapis wyrenderowanego rastra. FFV1 nie przechowuje tym sposobem
  pierwotnych float64, masek ani metadanych pomiarowych.
- Dokładność FFV1 porównujemy do obrazu uint8 przygotowanego dla kodeka,
  po gamma, zmianie proporcji, tle i opisach. Dla MJPG dopuszczamy zmiany
  wynikające z kompresji, również przy krawędziach i napisach.
- Dostępność musi wynikać ze sprawdzenia wybranego backendu/kodeka w danym
  środowisku. Sama deklaracja FFmpeg lub udane otwarcie writera nie dowodzi
  poprawnego filmu. Nie pobieramy kodeków ani nie zmieniamy metody po cichu.
- Przyszły eksporter pracuje na spójnym zestawie klatek i parametrów.
  Przed startem waliduje zakres, FPS, dostępność aligned i rozmiar wyjściowy.
  Zapis powinien pozostawać responsywny, z postępem i anulowaniem.
- Film powstaje najpierw w pliku tymczasowym. Błąd/anulowanie nie zastępuje
  wcześniejszego wyniku; dopiero poprawne zakończenie publikuje docelowy AVI.
  Nadpisanie istniejącego pliku wymaga standardowego potwierdzenia.
- Lokalna próba potwierdziła oba kodeki przez OpenCV/FFmpeg, ale nie
  sprawdziła docelowych odtwarzaczy użytkowników. Taki test należy do
  [odbioru pierwszej wersji](06-acceptance.md), wraz z dużymi filmami
  i zachowaniem przy przerwaniu zapisu.

### Przykłady do odbioru implementacji

| Przypadek | Oczekiwany wynik |
| --- | --- |
| Zmieniony zoom/rozmiar okna | Nadal pełne klatki i ten sam wynikowy rozmiar filmu. |
| Zakres 5–10 przy 5 FPS | Sześć klatek w kolejności serii, czas 1,2 s; opisy 5/20–10/20 dla serii 20. |
| Gamma z podglądu lub 1,0 | Inna prezentacja obrazu; identyczne tło i opisy przed kompresją. |
| Jeden wspólny kontrast | Jeden zakres wyliczony z ważnych próbek tylko eksportowanych klatek. |
| NaN lub klatka bez ważnych próbek | Wybrane tło, bez NaN w rasterze, zachowana liczba klatek. |
| Wyeksportowany podzbiór aligned | Zachowany pełny obszar istniejącego wyniku, bez ponownej rejestracji. |
| Wspólna anizotropowa skala X/Y | Fizyczne proporcje i poprawna podziałka po przeliczeniu. |
| Różne/nieznane skale | Proporcje pikselowe i podziałka px, bez przypisania skali pierwszej klatki całemu filmowi. |
| Rozmiar 65×49 w proporcjach pikselowych | Wynik 66×50; oryginalna ostatnia kolumna i wiersz zachowane. |
| FFV1 po odczycie | Dokładnie ten sam raster uint8 co przed kodowaniem, pełna liczba klatek i zadane FPS. |
| MJPG po odczycie | Właściwa geometria, liczba klatek/FPS i akceptowalna prezentacja; bez wymogu identycznych pikseli. |
| Nieznany czas lub przerwy w pomiarze | Brak fikcyjnego czasu z FPS; znane wartości i przerwy zachowane w napisach. |
| Niedostępny kodek/błąd/anulowanie | Czytelny wynik operacji, wcześniejszy plik pozostaje; bez cichej zmiany metody. |

To rozstrzygnięcie specyfikacji. Nie wdrożono eksportera ani nie zmieniono
wspólnych modułów. Kod, wersje i wyniki małej próby są w
[rozpoznaniu AVI](../avi-export-reconnaissance.md).
