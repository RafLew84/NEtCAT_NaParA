# Jak przygotować wspólne wejście i kontrole bez narzucania domen?

ID: 14
Type: task
Labels: wayfinder:task
Mode: AFK
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 01, 02

## Question

Przygotować odtwarzalny zestaw danych i kontroli dla porównań metod,
bez wskazywania im domen lub liczby grup. Zakres wejścia jest określony
poniżej; to praca przygotowawcza umożliwiająca badanie, a nie wybór algorytmu
ani rozstrzygnięcie pełnego protokołu jakości.

## Wspólny kontrakt następnych prób

Na dostarczonych obrazach i oznaczeniach molekuł metoda ma znaleźć domeny,
jeżeli dane dają na nie podstawy. Nie otrzymuje przykładów domen, liczby grup,
klas A/B/C ani założenia, że każda klatka musi zawierać domeny. Dopuszczamy
zero, jedną i wiele domen oraz pozostawienie części obrazu bez rozstrzygnięcia.
Brak dowodów przy słabym pomiarze nie oznacza rozpoznanego nieuporządkowania.

Automatyczne dopasowanie grup do nieopisanych danych jest dopuszczalne;
nie jest treningiem na wybranych domenach użytkownika. Skala sąsiedztwa,
tolerancja szumu i minimalne wsparcie nadal wymagają jawnego określenia.
Grupowanie podobnych obiektów, dowód uporządkowania i rozdzielenie
przestrzennych domen są osobnymi etapami oceny.

W porównaniu ML dopuszczamy modele wcześniej wytrenowane przez autorów,
używane bez zmiany wag i statystyk na naszych obrazach. Format manifestu
wyników przewiduje model, warstwy/tokeny, źródło i hash wag oraz sposób
przygotowania wejścia; pola te wypełnimy podczas przygotowania ekstraktorów.
Przygotowanie ekstraktorów jest osobnym zadaniem i nie blokuje
zakończenia tego wspólnego zestawu. Dotychczasowe próby gotowych cech
pozostają porównaniem bez treningu. Po dopuszczeniu przez użytkownika
osobnych prób treningu bez etykiet ich protokół będzie wymagał także
manifestu podziału danych i augmentacji, zgodnie z
[nowym przeglądem](../research-self-supervised-domain-learning.md).
Nie wolno używać ramek referencyjnych jako klas ani wzorców treningowych.

Najpierw porównujemy przypisania molekuł, lokalne typy/orientacje i obszary
z wiarygodnym wsparciem. Nie przeliczamy ich automatycznie na powierzchnie
całych płatów materiału. Dokładny kontur, pokrycie oraz granice przesunięcia
pozostają osobnymi wymaganiami, z lukami ujawnionymi w krokach 10–12.

## Przygotowanie wejścia i kontroli

**Wejście analizy:** MPP, bieżące oznaczenia z MolTrack i geometria pola
pomiarowego. Nie używamy dawnych wyników domen MolTrack jako etykiet.
Punktem startowym są pliki w
`/home/rlew/projekty/NEtCAT-domains/data/TTMAPP/`:

| Plik | Oczekiwany SHA-256 z wcześniejszego audytu |
| --- | --- |
| `MOVIE_23raw_TTMAPP_I_AU111.MPP` | `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66` |
| `detection_full.moltrack.json` | `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e` |

Przed obliczeniami sprawdzić zgodność plików, indeksów, współrzędnych i maski
pomiaru z [audytem geometrii](../import-geometry-audit.md). W zapisanym wejściu
jest 268 klatek; pierwszy zakres porównania to **całe klatki 250–268**
(numery od 1, indeksy 249–267). Klatka 255 ma być analizowana, jeśli nadal
jest dostępna w wejściu; brakuje jej anotacji, nie wynika z tego brak obrazu.
Do pierwszego zakresu dołączyć klatki 1, 50, 100, 150, 200 wybrane według
numerów, bez oglądania wyników. To szersza próba jednej akwizycji, nie
niezależny zbiór. Po kwalifikacji kandydatów zbadać koszt całych 268 klatek.

Analiza obejmuje całe oryginalne pole każdej klatki i poprawne oznaczenia
w tym polu. Padding po rejestracji jest wyłączony. Obliczenia obrazu
wykonywać na danych MPP, bez gamma podglądu; zapisać preprocessing i skalę.
Przy niewiarygodnej kalibracji zachować px, nie zastępcze nm.

**Wejście oceny:** dotychczasowe 18 par PNG / 54 wnętrza, zgodnie
z [audytem referencji](../partial-domain-reference-audit.md). Moduł analizy nie
czyta tych masek, kolorowych obrazów ani liczby kolorów. Najpierw zapisujemy
pełny wynik i konfigurację, potem odczytujemy referencje do porównania.
Okno cechy może wychodzić poza ramkę referencji, o ile mieści się w polu
pomiaru: ramka ogranicza ocenę, a nie dane wejściowe.

To świadoma zmiana względem lokalnych prób 10–12, które badały wybrane
wnętrza. Ramki nie wyznaczają już miejsc poszukiwania domen. BLACK/RED/YELLOW
opisują głównie orientacje jednej sieci. Nie stroimy do trzech kolorów
ani nie traktujemy nieoznaczonego otoczenia jako błędu. Referencje były już
używane: obecny rozdział analizy i oceny nie czyni ich nowym niezależnym testem.

Kontrole syntetyczne przygotować jako punkty i odpowiadające im obrazy;
osobno zmieniać kompletność detekcji i wygląd obrazu:

| Kontrola | Co ma ujawnić |
| --- | --- |
| Losowe punkty, także z minimalnym odstępem i gradientem gęstości | Sama odległość lub lokalna gęstość nie powinna tworzyć domen sieci |
| Szum obrazu i pasy skanowania | Brak utożsamiania dowolnej tekstury z uporządkowaniem molekuł |
| Jedna regularna sieć | Jedna domena musi być dopuszczalnym wynikiem |
| Dwie orientacje tej samej sieci | Wspólny typ, osobne domeny, bez zadania liczby dwa |
| Wyraźnie różne rozstawy oraz sieć skośna | Brak ograniczenia do jednego rozstawu i katalogu M3/M6 |
| Dwa rozłączne płaty tej samej sieci | Ten sam typ nie oznacza jednej przestrzennej domeny |
| Wyraźna granica przesunięcia przy wspólnym kącie | Ujawnienie ograniczeń cech niewrażliwych na fazę |
| Pojedynczy defekt oraz pas nieuporządkowany | Defekt nie musi rozcinać domeny; pas może ją rozdzielać |
| Losowe braki 10/30/50% centrów i lokalna luka detekcji | Nie mylić braków oznaczeń z granicą lub brakiem materiału |
| Zmienny kontrast, odwrócenie kontrastu, ucięcie pola | Odporność lub jawna odmowa, bez ukrywania ograniczeń |
| Przeskalowanie obrazu przy zachowaniu geometrii pomiaru oraz osobno zmiana rozstawu sieci | Rozróżnienie wpływu rozdzielczości wejścia od rzeczywistej różnicy struktury |

Każdą losową kontrolę powtórzyć dla zapisanych ziaren. Przed oceną TTMAPP
zamrozić konfigurację próby. Zmiany po obejrzeniu wyniku oznaczać jako kolejną
wersję rozwojową. Skalę dobierać automatycznie z danych lub z jawnej siatki
parametrów, nie z rozmiarów ręcznych domen. Wyniki na kontrolach użytych
do strojenia raportować osobno od powtórzeń z nowymi ziarnami.

## Wspólny wynik i ocena kandydatów

Każdy kandydat zwraca pełny podgląd klatki, przypisania obiektów lub okien,
typ/orientację, domenę przestrzenną i powód odmowy. Zapis obejmuje parametry,
wersje bibliotek, hashe wejścia, ziarna, czas i maksymalną pamięć. Nakładka
ma odróżniać wynik od niepewnej granicy i nieoznaczonego obszaru referencji.

Mierzymy:

- na kontrolach: liczbę domen, fałszywie przypisany porządek, błędy scaleń
  i podziałów, udział odmów oraz zachowanie poprawnej pojedynczej sieci;
- na oznaczonych wnętrzach TTMAPP: pary zgodnych/rozłączonych przypisań,
  nadmierne dzielenie, dostępność wyniku i zgodność wspólnego typu przy
  różnych orientacjach. Same kolory nie dają liczbowej prawdy o kącie;
- stabilność po zmianie skali, usunięciu detekcji i rozszerzeniu zakresu:
  porównanie relacji par i reprezentantów, nie surowych numerów etykiet;
- koszt, obszary odmowy i nowe propozycje poza ramkami. Bez pełnej referencji
  nie liczymy globalnej trafności, dokładnego IoU granic ani błędu liczby
  domen całej rzeczywistej klatki.

Najpierw przygotowanie wejścia i próba otoczenia molekuł, potem próby
SBC/MatID i tekstury na tym samym zestawie. Przygotowanie gotowych cech
sieci może przebiegać niezależnie od tych prób; ich porównanie domenowe
korzysta później z wyniku klasycznej tekstury. Nie wymaga sukcesu żadnego
innego kandydata, lecz udokumentowanego punktu odniesienia. Kandydat,
który odrzuca wszystko, nie przechodzi kontroli jednej regularnej domeny.
Kandydat kolorujący szum jak sieć nie przechodzi kontroli zerowej. Nie
zastępujemy tych sprawdzeń samym wynikiem silhouette lub trwałości klastra.
Pozostałe miary przedstawiamy z odmowami, bez wybierania tylko łatwych miejsc.

Pierwszy rezultat dla użytkownika: wspólny podgląd pełnych klatek i tabela
tych kontroli, z propozycją dalszej metody albo konkretną przyczyną braku
wyboru. Dalsze oznaczenia prosimy przygotować dopiero dla ujawnionej luki
(np. rzeczywistej granicy przesunięcia). Obecne dane wystarczą do rozpoczęcia
porównania. Przyjęcie rozwiązania produkcyjnego pozostaje wynikiem
[odbioru metod i warunków odmowy](13-method-acceptance.md).

## Warunek zakończenia zadania

- Gotowy, wersjonowany generator/protokół oraz lokalny manifest wejścia,
  geometrii, zakresu i kontroli z ziarnami; bez dużych danych w Git.
- Oddzielone wejścia analizy i oceny. Pakiet dla algorytmów nie zawiera
  ramek, kolorów ani poprzednich etykiet domen. Kolejne próby sprawdzą
  niezmienność predykcji po zmianie lub usunięciu samych referencji.
- Opisany format wyników eksperymentu, definicje miar i zestaw podglądów
  umożliwiający porównanie cech geometrycznych, SBC/MatID, tekstury i ML.
  Progi przyjęcia do programu pozostają przedmiotem protokołu jakości
  i odbioru metod.
- Raport przygotowania z poleceniem odtworzenia, wykonanymi kontrolami oraz
  jawnymi brakami. Nie jest wymagany wynik żadnego algorytmu domenowego.

Zadanie można wykonać na obecnych danych przed odbiorem szkieletu. Otwarte
[pytanie o referencje i jakość](04-reference-and-quality.md) nie blokuje
tego przygotowania; pozostaje warunkiem pełnego odbioru metody. Zakończenie
zadania oznacza gotowość zestawu porównawczego, nie skuteczność detekcji.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](02-order-types-and-domains.md)

## Następne pytania

- [Czy otoczenie zaznaczonych molekuł pozwala samodzielnie znaleźć domeny?](15-local-neighborhood-domains.md)
- [Czy SBC/MatID odtwarza domeny z niepełnych centrów molekuł?](16-sbc-matid-domains.md)
- [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](17-image-texture-domains.md)
- [Jak przygotować cechy gotowych sieci bez treningu na naszych danych?](18-frozen-feature-preparation.md)
