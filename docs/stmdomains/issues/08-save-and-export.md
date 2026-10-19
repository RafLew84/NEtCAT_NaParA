# Co zapisujemy i eksportujemy po próbach metod?

ID: 08
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: resolved
Assignee: Codex — domains/save-export-contract
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 01, 06, 07

## Question

Jaki własny zapis wyników STM Domains i eksport są potrzebne po próbach metod
do ponownego otwarcia pracy, odtworzenia obliczeń i porównywania serii?

Zakończony pilotaż wskazał braki i nie wybrał metody. Na polecenie użytkownika
ustalamy wcześniej kontrakt niezależny od konkretnego algorytmu. Odbiór metod
sprawdzi jego realizację na wynikach dalszych prób; nie nadajemy numerom
klastrów prototypu znaczenia trwałych typów.

[Uzgodnione statystyki klatek](06-frame-statistics.md#answer--2026-10-19)
wymagają zachowania obu mianowników powierzchni, liczby wszystkich poprawnych
oznaczeń ze środkiem w polu, jednostek i dostępności poszczególnych miar.
Wynik częściowy, zero i brak pomiaru pozostają rozróżnialne. Zapis nie może
gubić przyczyn nieprzypisania, ucięć brzegiem ani wersji wspólnego katalogu.

Użytkownik dopuścił ręczne rozstrzygnięcie konkretnego nakładania domen przez
wybór jednej z propozycji. Ustalmy sposób zachowania obszaru konfliktu,
automatycznych propozycji i decyzji użytkownika, aby odtworzyć geometrię oraz
przeliczyć statystyki bez udawania automatycznego wyniku. Korekta odnosi się
do konkretnej analizy; nie przechodzi po numerze domeny na nowy katalog.
Nie rozszerza to zakresu do pełnego edytora granic ani tworzenia oznaczeń.

Ustalmy rozdzielenie wejściowego zapisu z innego programu od wyników analizy,
identyfikację obrazów i klatek, geometrię, parametry i wersje metod, maski
pokrycia i wysp, orientacje sieci, wspólną definicję typów, przypisania molekuł,
granice i statystyki.
Które elementy są konieczne, a które można bezpiecznie przeliczyć?

Jak zapamiętujemy niepewność i ewentualne zaakceptowane korekty, jeśli próby
ujawnią taką potrzebę? Kiedy zmiana parametrów, geometrii albo danych unieważnia stare
wyniki? Jakie tabele i obrazy użytkownik chce wyeksportować, wraz z jednostkami,
obszarem odniesienia i rozróżnieniem zera od braku danych?

Rozstrzygnięcie to kontrakt trwałości i potrzebne formaty wyników. Użytkownik
wybrał samowystarczalny zapis z osadzonym MPP, więc przeniesienie pliku
nie wymaga naprawiania odnośnika do zewnętrznego obrazu. Naprawa ścieżki
pozostaje częścią importu MolTrack. Duże dane i modele pozostają poza Git.

Ustalmy również sposób ponownego pokazania zapisanych warstw, wyboru typu
i powiązania tabeli lub wykresu z klatką. Zapisywanie oraz porównywanie wyników
rozwija etap 2 i nie jest warunkiem odbioru podstawowej przeglądarki.

Kontekst: [obecny eksport MolTrack](../../../moltrack/persistence/domain_analysis_export.py)
jest przykładem związanym z M6, nie gotowym kontraktem nowej analizy.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](06-frame-statistics.md)
- [Jak przeglądać obrazy i oznaczenia w szkielecie?](07-browsing-and-comparison.md)

## Discussion — 2026-10-19

### Pierwsza runda — przyjęte przez użytkownika

- Jeden samowystarczalny plik zawiera także obrazy MPP. Odrzucono propozycję
  przechowywania obrazu jako zewnętrznego odnośnika. Ponowne otwarcie nie
  wymaga ani źródłowego MPP obok pliku, ani pierwotnego zapisu MolTrack.
- Jeden wybrany wynik analizy w pliku. Warianty parametrów można zachować
  w osobnych plikach przez „Zapisz jako”; bez historii wielu prób w projekcie.
- Podstawowy eksport: tabele CSV i obrazy PNG z nakładkami; wykresy również PNG.

### Druga runda — przyjęte przez użytkownika

- Ponowne otwarcie odtwarza zapisany wynik, korekty i ustawienia widoku bez
  uruchamiania metod. Brak modelu lub nowszy algorytm nie blokują tego podglądu.
- Nowa analiza zachowuje poprzedni wynik do zastąpienia, umożliwiając jego
  zapis do osobnego pliku. Anulowanie/błąd nie usuwa poprzedniego wyniku;
  korekty nie przechodzą automatycznie na nową analizę.
- Przy PNG użytkownik wybiera całą klatkę albo oglądany wycinek, z gammą,
  widocznymi nakładkami, numerem klatki, opisem widoku i legendą typów.
  Brak wiarygodnej kalibracji wyklucza skalę nm.

### Trzecia runda — przyjęte przez użytkownika

- CSV obejmuje podsumowania klatek/typów i szczegółowe tabele wysp, domen
  oraz przypisań oznaczonych molekuł, z jednostkami, brakami i korektami.
- Wybór typu podświetla jego obszary, a tabela i wykres wskazują klatkę
  podglądu. To wybór prezentacji, bez zmiany obliczeń i mianowników.
- Zapis jest dostępny także przed analizą: obrazy, oznaczenia, podgląd
  oraz jawny stan „jeszcze nie analizowano”. Plik ma zero albo jeden wynik.

Odpowiedzi zamykają decyzje użytkownika dotyczące pierwszej wersji zapisu.
Poniższy kontrakt zbiera je wraz z konsekwencjami technicznymi i wcześniej
przyjętymi definicjami importu oraz statystyk. Nie jest implementacją formatu.

### Fakty z audytu lokalnego kodu

Audyt był tylko do odczytu; nie uruchamiano starych testów ani eksportera.

- [Eksporter Domain Analysis](../../../moltrack/persistence/domain_analysis_export.py)
  zapisuje manifest i CSV w katalogu i wymaga opublikowanego wyniku M6.
  [Nagłówki tabel](../../../moltrack/persistence/domain_analysis_export_schema.py)
  nie realizują definicji powierzchni, jednostek i stanów STM Domains.
- [UI eksportera](../../../moltrack/ui/domain_analysis_runtime.py) przekazuje
  jako tożsamość źródła jego nazwę i ścieżkę. Hash takiego słownika nie jest
  sumą kontrolną danych obrazu. [Sesja MolTrack](../../../moltrack/persistence/session_store.py)
  sprawdza wielkość i datę źródła; nie wystarcza to do mocnej identyfikacji.
- [Eksport z korektami](../../../moltrack/persistence/correction_aware_export.py)
  pokazuje rozdzielenie automatu i wyniku po decyzjach użytkownika. Jego
  mechanizm rewizji/rebase i znaczenia orientacyjne nie przechodzą automatycznie
  do niewielkiego STM Domains.
- [Sesja NanoTrack](../../../nanotrack/persistence/session_store.py) jest
  przykładem jednego archiwum ZIP z JSON i tablicami NPZ. Wciąż doczytuje obraz
  ze źródła zewnętrznego; dołączenie MPP jest nowym wymaganiem STM Domains.
- [Zapis atomowy JSON](../../../moltrack/persistence/atomic_json.py) i
  [publikowanie pakietu](../../../moltrack/persistence/package_io.py) pokazują
  zapis tymczasowy przed zastąpieniem celu oraz strumieniowe sumy SHA-256.
  To wzorce do oceny, nie zadanie zmiany wspólnych modułów.

## Answer — 2026-10-19

Uzgodniono samowystarczalny zapis pracy i eksport po trzech rundach odpowiedzi.
Jest to kontrakt do implementacji w etapie 2. Zapis pracy przed analizą jest
jego częścią, lecz nie dodaje obowiązku implementowania zapisu w szkielecie.
Metody pozostają do wyboru i odbioru.

### Jeden samowystarczalny zapis pracy

Format STM Domains: jeden plik `.stmdomains`, wersjonowane archiwum ZIP
z manifestem JSON, metadanymi i tablicami wyników oraz osadzonym oryginalnym
MPP. Rozszerzenie odróżnia go od wejściowego MolTrack i eksportu tabel.
Kontener jest wyborem technicznym dla tego zakresu, nie ponownym użyciem
schematu M6 ani wymaganiem bazy danych. Szczegółowe nazwy pól i kodowanie tablic
zostaną domknięte przy implementacji z adapterami zaakceptowanych metod.

Dołączamy cały oryginalny MPP bez zmiany bajtów. Wybrana seria i zakres analizy
są osobnymi mapami klatek; nie przycinamy po cichu źródła do klatek z wynikiem.
Obrazy wyrównane, miniatury i nakładki nie zastępują danych pomiarowych.
MPP wewnątrz paczki oraz wszystkie wymagane oznaczenia pozwalają otworzyć pracę
po przeniesieniu samego `.stmdomains` na inny komputer. Zewnętrzne ścieżki
MolTrack/MPP są wyłącznie informacją o pochodzeniu; nie warunkiem otwarcia.
Naprawa odnośnika z ticketu importu nadal dotyczy pierwszego otwarcia MolTrack,
a nie szukania kopii obrazu prawidłowego samowystarczalnego zapisu.

Jeden plik zawiera zero albo jeden wynik analizy, wraz z automatyczną podstawą
i jego bieżącymi korektami. To dwa stany tego samego wyniku, nie kolekcja prób.
„Zapisz jako” pozwala zachować inny wariant w osobnym pliku. Nie dodajemy
historii wszystkich przebiegów, kont użytkowników ani wspólnej bazy.

Przed analizą zapis zawiera obrazy, oznaczenia, geometrię, podgląd i ewentualnie
przygotowane parametry; wynik i katalog są nieobecne. Stan „jeszcze nie
analizowano” nie jest pustym wynikiem ani zestawem zer. Wyniki częściowe
pozostają zapisywalne z dostępnością poszczególnych miar i stanem każdej klatki.

### Obowiązkowa zawartość

Sekcje wynikowe poniżej są wymagane, jeśli dana analiza wytworzyła taki wynik;
przed analizą albo przy braku danej wielkości zapisujemy jawną nieobecność
z przyczyną. Nie fabrykujemy masek, katalogu, kątów ani statystyk.

| Obszar | Zachowane informacje |
| --- | --- |
| Identyfikacja | Wersja formatu i aplikacji, ID wyniku, rewizja wyniku po korektach, ID źródła i katalogu, czas utworzenia/zapisu. SHA-256 rzeczywistych bajtów MPP i kontrola zawartości wymaganych części paczki. Ścieżka, nazwa i mtime nie zastępują zgodności zawartości. |
| Pochodzenie wejścia | Opis i hash wczytanego MolTrack, wersja adaptera, decyzja o przyjęciu źródła mimo dawnych niepełnych metadanych. Nowy hash nie dowodzi zgodności z historycznym obrazem, którego hash nie istniał. |
| Klatki | Uporządkowana mapa indeksów roboczych do źródłowych, trwały klucz klatki związany ze źródłem, jawnie wybrany zakres analizy oraz status każdej jego klatki. Klatki bez wyniku nie znikają z mapy. |
| Obraz i geometria | MPP, rozmiar oryginału, orientacja przyjęta przez importer, układy współrzędnych, globalne translacje, referencja, jakość rejestracji, padding i powiązanie z oryginalnym polem. Kalibracja/czas razem z jednostką, pochodzeniem i wiarygodnością. |
| Oznaczenia wejściowe | ID, bieżące i historyczne bboxy/polygony/maski, związki maska–detekcja, źródło, confidence, selected i układ współrzędnych zgodnie z kontraktem importu. Stan niedostępności i przyczyna pozostają jawne. Brak masek nie usuwa ramek. |
| Metoda | Nazwa i wersja każdego etapu, rzeczywiście użyte parametry, przetwarzanie wstępne, zakres budowy katalogu, identyfikatory modeli/zasobów i ich sumy, jeżeli są używane; ziarno i istotne ustawienia numeryczne, jeśli wpływają na odtwarzalność. |
| Pokrycie | Maski pokrycia i wysp oraz rozróżnienie podłoża, ocenionej części, niepewności i braków. Sama unia masek molekuł nie zastępuje płata warstwy. |
| Struktura | Wspólny katalog z definicjami typów i jego wersją; geometria fragmentów domen, ich typ/orientacja, granice i obszary niedopasowania, lokalne stany braku porządku/typu, niejednoznaczności i niewystarczających danych. Zachowujemy definicję kąta, równoważne obroty i jednostki, jeśli metoda zwraca orientację. |
| Przypisania | Powiązanie każdego dostępnego oznaczenia z domeną/typem albo powód nieprzypisania/wyłączenia. Wyspy i fragmenty domen mają identyfikatory w obrębie wyniku i klatki, bez deklaracji śledzenia w serii. |
| Korekty | Niezmieniony wynik automatyczny, obszar i kandydaci konkretnego konfliktu, decyzja użytkownika związana z ID analizy/katalogu/geometrii oraz końcowa geometria i przypisania. Korekta pozostaje widoczna po ponownym otwarciu. |
| Statystyki | Wartości, jednostki, oba mianowniki powierzchni, mianownik liczebności, dostępność każdej miary, przyczyny braków, ucięcia brzegiem i informacja o korekcie. Brak oraz zero są różne. |
| Podgląd | Bieżąca klatka, oryginał/wyrównany, zoom/przesunięcie, gamma, warstwy i ich krycie, wybrany typ, zakres prezentacji oraz wybór miary tabeli/wykresu. Stan odtwarzania przy otwarciu: pauza. |

Zapis nie musi przechowywać całego obcego stanu MolTrack, np. modeli detektora,
jego UI lub starej analizy M6. Przechowuje pełny potrzebny podzbiór oznaczeń
oraz diagnostykę elementów niedostępnych podczas importu. Własne wyniki są
oddzielone od tych oznaczeń; źródłowy JSON i MPP nigdy nie są nadpisywane.

Obszary do pomiaru mają kanoniczną siatkę oryginalnej klatki, zgodnie z
[definicjami statystyk](06-frame-statistics.md#answer--2026-10-19). Przejście
raw/aligned dotyczy renderowania, bez wielokrotnego przekształcania masek pomiaru.
Zapisana geometria konfliktu pozwala przywrócić niejednoznaczność i przeliczyć
przypisania oraz miary bez uruchamiania segmentacji lub tworzenia nowego katalogu.

### Wynik zapisany a ponowne obliczenie

Otwarcie odtwarza zapisany wynik automatyczny i efektywny, korekty oraz stan
podglądu, bez ponownego uruchamiania metod. Odtwarzanie klatek jest zatrzymane.
Brak checkpointu lub kodu dawnej metody nie blokuje oglądania zachowanych
obszarów i miar, jeśli program obsługuje wersję ich formatu. Parametry
wykonanej analizy są oddzielone od ustawień przygotowywanych do następnej próby.
Zmiana pól ustawień nie dopisuje ich wstecz do istniejącego wyniku.

Nowa próba powstaje obok bieżącego wyniku w pamięci/obszarze roboczym. Gdy
jest gotowa, użytkownik może zachować stary wariant przez „Zapisz jako”,
zastąpić go albo zrezygnować. Anulowanie próby lub nieudane wykonanie nie
usuwa starego wyniku i jego korekt. Nie zamieniamy przerwanej próby w wynik
z zerami. Zakończony przebieg może dać wynik częściowy/odmowę dla niektórych
klatek; są to jawne stany wyniku, nie ukryty sukces całej serii. Nieudana
próba techniczna nie zastępuje poprzedniej tylko dlatego, że zdążyła wytworzyć
kilka klatek.

Nowe wykonanie ma nowy identyfikator analizy. Korekta pozostaje przy starej
analizie, a nowa rozpoczyna się bez przenoszenia ręcznych rozstrzygnięć po
numerach domen. Zmiana decyzji w ramach tej samej analizy aktualizuje rewizję
wyniku efektywnego. Zapis jako kopia tego samego wyniku zachowuje jego tożsamość.
Przy zamykaniu lub otwarciu innej pracy niezapisane zmiany podlegają zwykłemu
wyborowi zapisania, odrzucenia lub anulowania; nie są gubione po cichu.

Dane wynikowe, katalog i wersjonowane definicje miar są zachowane. Nie polegamy
wyłącznie na parametrach z nadzieją, że przyszła metoda wytworzy ten sam rezultat.
Można odtworzyć miniatury, renderowanie wyrównania, kolory nakładek i wykresy
z zapisanych danych. Kontrolne przeliczenie statystyk jest możliwe z geometrii,
ale nowszy program nie zastępuje po cichu zachowanego wyniku inną definicją.
Pełne ponowienie obliczeń może potrzebować zewnętrznego modelu i zgodnej wersji
środowiska; nie obiecujemy identyczności numerycznej na dowolnej maszynie.

| Zmiana | Skutek |
| --- | --- |
| Gamma, zoom, warstwy, wybór typu lub oglądanych klatek | Nie unieważnia wyniku, nie przebudowuje katalogu i nie zmienia mianowników statystyk. |
| Nazwa/lokalizacja `.stmdomains` | Nie zmienia tożsamości wyniku. |
| MPP, oznaczenia, geometria albo przetwarzanie użyte do analizy | Nowa podstawa analizy; starego wyniku nie przedstawiamy jako obliczonego dla nowych danych. |
| Wykonanie z innymi parametrami/metodą/modelem albo zakresem katalogu | Nowy wynik/katalog; stare dane pozostają z dawnymi ustawieniami. Korekty nie przechodzą po zgodnym numerze domeny/typu. Samo przygotowanie parametrów nie zmienia starego wyniku. |
| Sama nowsza aplikacja/algorytm podczas otwarcia | Nie unieważnia historycznego wyniku i nie uruchamia obliczeń. Zapis pokazuje wersję, z której pochodzi. |
| Kalibracja używana wyłącznie do jednostek | Możliwe jawne przeliczenie jednostek z zachowaniem geometrii px i pochodzenia skali; bez cichej zmiany zapisanych wartości. Jeśli skala wpływała na klasyfikację, wymagana nowa analiza. Nie dodaje to edytora kalibracji. |
| Ręczne rozstrzygnięcie konfliktu | Zmiana wyniku efektywnego i jego statystyk przy zachowanej automatycznej podstawie. |

Numer lub kolor typu w dwóch osobnych plikach nie gwarantuje wspólnego znaczenia.
Tożsamość typu obejmuje katalog. Nie dodajemy automatycznego uzgadniania katalogów
różnych akwizycji; porównywanie CSV musi zachować to ograniczenie.

### Integralność i zapis

Zapis/Zapisz jako buduje kompletny plik tymczasowy i dopiero po powodzeniu
zastępuje cel. Błąd lub anulowanie pozostawia dotychczasowy plik i otwartą pracę.
Nadpisanie innego istniejącego pliku wymaga zwykłego potwierdzenia w aplikacji.
Sprawdzamy mapy klatek, odwołania do katalogu/oznaczeń/domen, wymiary i układy
masek, zgodność automatu/korekt/końcowego wyniku oraz integralność danych.
Nie zapisujemy półgotowego archiwum pod nazwą poprawnego wyniku. Zmiana MPP
od chwili importu nie może sprawić, że pod stare oznaczenia zostaną spakowane
inne obrazy: zapis musi korzystać z przyjętego źródła i sprawdzać jego tożsamość.

MPP kopiujemy strumieniowo, a maski zapisujemy/odczytujemy na potrzeby klatek;
format nie wymaga rozpakowania wszystkich masek do pamięci. Własny zapis
powinien pozwalać na odczyt konkretnej klatki i ograniczony cache. Jeśli
istniejący czytnik MPP wymaga ścieżki, wewnętrzna kopia robocza jest odtwarzalnym
cache, nie drugim plikiem wymaganym od użytkownika przy przenoszeniu pracy.

Przy otwarciu nieznana główna wersja formatu, uszkodzenie wymaganego obrazu
lub wyniku i sprzeczne odwołania dają błąd; poprzednia praca pozostaje.
Nie łączymy zachowanego wyniku z dowolnym zastępczym MPP. Możliwość importu
starego formatu wymaga jawnie obsługiwanej migracji, bez nadpisania oryginału.
Brak opcjonalnego cache podglądu pozwala go odbudować; oznaczony już podczas
importu brak opcjonalnej maski pozostaje opisanym brakiem, nie uszkodzeniem
wymaganych wyników. Archiwum nie przechowuje wykonywalnych obiektów Pythona.

### Tabele CSV

Eksport obejmuje jawnie wybrany zakres klatek z jednego zapisanego/bieżącego
wyniku i jego rewizji. Domyślnie jest to cały przeanalizowany zakres; ograniczenie
eksportu nie zmienia katalogu ani mianowników. Tabele trafiają do jednego
katalogu, z opisem kolumn i tożsamości źródła/wyniku/katalogu. Eksport nie
zmienia pliku pracy. Nie dodajemy sum ani średnich serii.

| Tabela | Wiersz i treść |
| --- | --- |
| Klatki | Każda wybrana klatka, także bez wyniku; dostępność analizy, pole, warstwa, pokrycie, liczebność oznaczeń, wysp i fragmentów domen, braki, ucięcia i korekty. |
| Typy na klatkach | Klatka × typ ze wspólnego katalogu; powierzchnia typu, udział w polu i warstwie, liczba oznaczeń i udział w pełnym mianowniku liczebności, liczba fragmentów domen oraz status każdej miary. |
| Wyspy | Pojedyncza wyspa danej klatki; obserwowana powierzchnia, ucięcie brzegiem, dostępność i powiązania z fragmentami domen. |
| Domeny | Obserwowany fragment domeny: typ lub przyczyna jego braku, orientacja jeśli dostępna, obserwowana powierzchnia, przypisane oznaczenia, ucięcie i informacja o ręcznej korekcie. |
| Oznaczenia molekuł | Każde zachowane oznaczenie w eksportowanych klatkach: ID, źródło, środek bboxa, domena/typ albo powód nieprzypisania lub wyłączenia, włączenie do mianownika i pochodzenie korekty. Niedostępne współrzędne nie stają się zerami. |

Opis eksportu zawiera definicje i etykiety katalogu, zakres, wersję schematu
tabel i definicji miar, użyte parametry/metody oraz jednostki. Jest dołączony
automatycznie; nie wymaga nowej operacji użytkownika. Szczegółowe granice/maski
pozostają w `.stmdomains`; tabela i PNG nie zastępują ich do ponownego otwarcia.
Domyślnie eksportujemy wynik efektywny, po korektach, z wyraźną informacją,
które rekordy są skorygowane. Automatyczny stan i pełne konflikty nadal są
w zapisie pracy, a eksport nie przedstawia korekt jako predykcji algorytmu.

Wiersze zachowują ID analizy, jej rewizję, katalog i klucz klatki, indeks roboczy
oraz źródłowy. Rozróżniamy indeksy od zera i prezentowane numery od jedynki
w nazwach/objaśnieniach kolumn. Domeny i oznaczenia nie zyskują przez to
tożsamości śledzonej między klatkami. ID typu odnosi się do konkretnego katalogu.

CSV: UTF-8, przecinek jako separator i kropka dziesiętna, standardowe cytowanie
tekstu. Wartość niedostępna ma puste pole liczbowe, a osobna kolumna stanu
oraz przyczyny wyjaśnia brak. Nie wpisujemy tekstu „brak” w kolumnę liczbową
ani zera zamiast null. Wymagane stany miary: kompletna, częściowa, niedostępna
albo niezdefiniowana (np. zerowy mianownik); status wykonania analizy i korekta
są osobnymi polami. Nie używamy jednego ogólnego statusu dla wszystkich miar.

Powierzchnie px² są zachowane zawsze, gdy geometria pozwala na pomiar;
kolumny jednostek fizycznych wypełniamy tylko przy wiarygodnej kalibracji.
Procenty zapisujemy jako wartości 0–100. Eksport zawiera liczniki i faktyczne
mianowniki, nie tylko zaokrąglony procent. Pole klatki, warstwa i liczebność
mają odrębne nazwy; nie zmienia ich wybrany typ ani widoczność nakładki.
Stany nieporządku, braku typu, niejednoznaczności, braku danych i wyłączenia
pozostają rozróżnialne. Wiersz bez rozpoznanego typu nie udaje kolejnego typu
struktury. Ograniczenie listy typów musi być jawne, nie renormalizuje udziałów.

Przykłady zgodne z kontraktem statystyk (wartości ilustracyjne):

| Przypadek | Wartość | Stan | Mianownik/przyczyna |
| --- | ---: | --- | --- |
| Typ A: 3000 px² w polu 10 000 px² | 30% | kompletna | całe pole 10 000 px² |
| Ten sam typ w warstwie 6000 px² | 50% | kompletna | warstwa 6000 px² |
| Typ A: 40 z 100 oznaczeń w polu | 40% | kompletna | wszystkie poprawne oznaczenia: 100 |
| Wiarygodna ocena bez typu A | 0 px² | kompletna | brak typu A potwierdzony oceną |
| Nie wykonano analizy klatki | puste | niedostępna | jeszcze nie analizowano |
| Potwierdzona warstwa 0 px²: udział typu w warstwie | puste | niezdefiniowana | mianownik 0 |
| Rozpoznana część materiału, reszta nieoceniona | dostępne px² | częściowa | pełne pole warstwy i udział typu w niej pozostają niedostępne |

Pusta tabela szczegółowa dla klatki bez wyniku nie dowodzi braku obiektów;
stan wynika z tabeli klatek. Przed analizą CSV może pokazać dostępne oznaczenia
i metadane, lecz nie tworzy zerowych statystyk domen.

### PNG i prezentacja wyników

Eksport obrazu pozwala wybrać pełny obszar bieżącego widoku albo aktualny
wycinek. Pełny oryginał to jego pole; pełny widok wyrównany to płótno wraz
z jawnie oznaczonym paddingiem i granicą oryginalnego pola. Wycinek jest
opisany jako wycinek i ma zachowane odniesienie do współrzędnych klatki.
Nie zmienia pola, do którego odnoszą się statystyki całej klatki.

PNG pokazuje ustawioną gammę/normalizację, tryb oryginał/wyrównany i wybrane
nakładki. Ustawienia eksportu i legenda opisują obraz, a nie zastępują danych
pomiarowych. Numer klatki, widok, legenda widocznych typów i istotny status
częściowości/korekty są czytelne. Skalę nm pokazujemy wyłącznie przy potwierdzonej
kalibracji; dla TTMAPP stosujemy px. Podpisy/legenda pozostają czytelne także
po eksporcie wycinka. Zachowujemy identyfikację analizy, rewizji, klatki,
zakres wycinka i ustawienia renderowania w metadanych towarzyszących eksportowi.

Wykres PNG przedstawia wybraną miarę po klatkach, z nazwą, jednostką, zakresem,
legendą typów i stanami wyniku. Brak pomiaru jest przerwą; brak wiarygodnego
czasu oznacza oś numerów klatek, a nie czas obliczony z szybkości odtwarzania.
Nie dodajemy AVI, MPP jako eksportu analizy, XLSX ani TIFF w tej wersji.

Po otwarciu pracy odtwarzamy warstwy, kolory typów z zapisanego katalogu,
wybrany typ, tabelę/miarę i klatkę. Kolor nie jest tożsamością typu. Wybór typu
podświetla jego obszary w pojedynczym podglądzie z paskiem miniatur przyjętym
w [kontrakcie przeglądania](07-browsing-and-comparison.md). Tabela/wykres są
rozszerzeniem etapu 2; kliknięcie wiersza lub punktu wskazuje odpowiednią klatkę,
a rekord szczegółowy może podświetlić jej obiekt. Nie dopisuje wyniku klatce,
która go nie ma. Warstwa konfliktów pozwala odróżnić pozostawione niejednoznaczności
od miejsc ręcznie rozstrzygniętych. Zmiana podświetlenia nie przelicza katalogu
ani nie zmienia podstaw procentów.

### Odbiór przyszłej implementacji

1. Zapisz i otwórz sam `.stmdomains` w innym katalogu po odłączeniu oryginalnego
   MolTrack i MPP. Porównaj hash osadzonego MPP, mapę klatek i oznaczenia.
   Zachowaj identyczny sygnał, geometrię oraz dostępność masek, również przy
   klatkach bez ramek i podzbiorze/odwróconej kolejności serii.
2. Otwórz zapis bez wyniku, a potem z kompletnym/częściowym wynikiem. Bez modeli
   i wywołania metod odtwórz maski, katalog, przypisania, miary, jednostki,
   źródła braków i ustawienia podglądu. Nie zamieniaj braków w zera.
3. Zapisz konkretny konflikt przed i po ręcznym wyborze. Sprawdź zachowanie
   automatu, obszaru konfliktu, kandydatów i decyzji oraz zgodność geometrii,
   obu udziałów powierzchni i przypisań molekuł. Przywróć nierozstrzygnięcie.
4. Uruchom nową próbę, anuluj ją i wywołaj błąd: poprzedni wynik, korekty
   i plik pozostają. Przy udanej zamianie zachowaj poprzedni przez „Zapisz jako”;
   nowa analiza ma nową tożsamość i nie dziedziczy korekt po numerach.
5. Wymuś przerwany zapis, brak miejsca, nieobsługiwaną wersję, uszkodzony MPP,
   zmieniony zewnętrzny MPP przed pierwszym zapisem i sprzeczne ID/shape.
   Nie publikuj wadliwej paczki ani nie zastępuj nią poprawnie otwartej pracy.
6. Porównaj CSV z zapisanym wynikiem: wszystkie wybrane klatki, w tym braki;
   poprawne liczniki/mianowniki, jednostki, zera, wartości częściowe, katalog
   i rewizja. Sprawdź cytowanie nazw i odczyt danych w arkuszu.
7. Sprawdź PNG całości i wycinka w obu widokach, gamma/nakładki/legendy,
   padding, skalę px/nm i opisy stanów. Kliknięcie tabeli/punktu prowadzi
   do właściwej klatki, bez zmiany wyniku lub mianowników.
8. Zmierz czas, pamięć i możliwość anulowania zapisu/otwarcia pełnej serii
   TTMAPP z maskami; nie materializuj wszystkich masek przy otwarciu.
   Koszty oraz zgodność adapterów wynikowych domyka
   [odbiór metod](13-method-acceptance.md), przed uznaniem zapisu za gotowy.

W tym zadaniu wykonano audyt kodu i uzgodniono kontrakt. Powyższe sprawdzenia
są kryteriami przyszłej implementacji, nie testami już zaliczonymi. Dokładne
rozszerzenia metadanych wybranych metod mogą powstać podczas ich prób, lecz
nie mogą usuwać uzgodnionych stanów, geometrii, mianowników ani pochodzenia korekt.


## Comments

### 2026-10-19 — podjęcie na bezpośrednie polecenie użytkownika

Rozmowę o zapisie rozpoczynamy przed odbiorem metod, jako wskazany przez
użytkownika wyjątek od kolejności mapy. Ustalamy kontrakt wspólny dla metod,
a szczegóły zależne od wyników prób pozostają do weryfikacji podczas ich
odbioru. Nie oznacza to wyboru ani zatwierdzenia algorytmu i nie rozszerza
pierwszego etapu o implementację zapisu.

### 2026-10-19 — zamknięcie kontraktu przed odbiorem metod

Po trzech rundach odpowiedzi ustalono kontrakt wspólny dla metod. Usunięto
zależność tego pytania od odbioru metod i dodano odwrotną: odbiór sprawdza
kompletność wyników względem przyjętego zapisu oraz jego odtworzenie na danych.
To zmiana kolejności decyzji wynikająca z bezpośredniego polecenia użytkownika,
bez uznania metod za gotowe. Pierwsza mapa nadal nie czeka na zapis wyników.
