# Próby samodzielnego wykrywania domen

Data: 2026-10-21. **Plan eksperymentów, jeszcze niewykonany.** Wynika
z doprecyzowania użytkownika i [przeglądu STM/AFM](research-stm-afm-unsupervised-domain-discovery.md).
Nie otwiera ponownie zakończonych prób 10–12 ani nie zatwierdza metody.
Wyniki zasilą [odbiór 13](issues/13-method-acceptance.md).

## Cel i granice próby

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

Najpierw porównujemy przypisania molekuł, lokalne typy/orientacje i obszary
z wiarygodnym wsparciem. Nie przeliczamy ich automatycznie na powierzchnie
całych płatów materiału. Dokładny kontur, pokrycie oraz granice przesunięcia
pozostają osobnymi wymaganiami, z lukami ujawnionymi w krokach 10–12.

## E0 — wspólne wejście i próby kontrolne

**Wejście analizy:** MPP, bieżące oznaczenia z MolTrack i geometria pola
pomiarowego. Nie używamy dawnych wyników domen MolTrack jako etykiet.
Punktem startowym są pliki w
`/home/rlew/projekty/NEtCAT-domains/data/TTMAPP/`:

| Plik | Oczekiwany SHA-256 z wcześniejszego audytu |
| --- | --- |
| `MOVIE_23raw_TTMAPP_I_AU111.MPP` | `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66` |
| `detection_full.moltrack.json` | `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e` |

Przed obliczeniami sprawdzić zgodność plików, indeksów, współrzędnych i maski
pomiaru z [audytem geometrii](import-geometry-audit.md). W zapisanym wejściu
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
z [audytem referencji](partial-domain-reference-audit.md). Moduł analizy nie
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

Każdą losową kontrolę powtórzyć dla zapisanych ziaren. Przed oceną TTMAPP
zamrozić konfigurację próby. Zmiany po obejrzeniu wyniku oznaczać jako kolejną
wersję rozwojową. Skalę dobierać automatycznie z danych lub z jawnej siatki
parametrów, nie z rozmiarów ręcznych domen. Wyniki na kontrolach użytych
do strojenia raportować osobno od powtórzeń z nowymi ziarnami.

## E1 — lokalne otoczenie oznaczonych molekuł

Pytanie: czy geometria dostępnych centrów wystarcza do znalezienia spójnych
obszarów podobnego uporządkowania bez przykładów domen?

1. Zbudować lokalne opisy kilku rozmiarów sąsiedztwa: rozkłady odległości
   i kątów oraz powtarzalność otoczenia. Zachować rozstaw w px; normalizacja
   nie może ukryć różnicy rozstawu. Porównać prosty opis z SOAP, jeśli prosty
   opis nie rozdziela kontrolnych struktur. Nie narzucać liczby sąsiadów
   odpowiadającej jednej symetrii.
2. Grupować opisy we wspólnym katalogu całego wybranego zakresu, bez zadania
   `K`. Kandydatem jest HDBSCAN z dopuszczonym jednym klastrem. Typ ma być
   odporny na obrót; kąt analizować osobno, z symetrią oszacowanej struktury.
3. Łączyć przestrzennie sąsiednie, zgodne obiekty. Oddzielić rozłączne
   fragmenty. Zgodność opisu nie wystarcza: wymagać dowodów powtarzalności
   wykraczających poza kontrole losowe. Nie traktować etykiety „noise”
   algorytmu jako fizycznego nieuporządkowania.

Zapisać osobno wynik grupowania i wynik po ocenie porządku. Mierzyć
nadmierne podziały, scalanie, pozostawione bez przypisania molekuły i wpływ
braków centrów. Warunek zatrzymania: brak ustawień odróżniających kontrole
losowe od regularnej pojedynczej domeny. Nie naprawiać tego ręcznym `K=3`.
Uzasadnienie i biblioteki: [przegląd grupowania](research-domain-discovery-and-object-clustering.md).

## E2 — odtwarzanie komórki z punktów, SBC/MatID

Pytanie: czy lokalne powtórzenia centrów pozwalają odtworzyć komórki różnych
sieci, a następnie rozdzielić domeny? To transfer metody atomistycznej,
nie potwierdzona metoda dla TTMAPP.

Użyć centrów jako punktów 2D jednej kategorii. Jawnie dostosować skalę,
promienie połączeń, tolerancję pozycji i maksymalny rozmiar komórki; nie
interpretować molekuł jako atomów o domyślnych promieniach w Å. Rejestrować
znalezioną komórkę i wsparcie dla każdego obszaru, także niepowodzenie.

Najpierw sprawdzić zero/jedną/wiele sieci, dwa rozłączne identyczne płaty,
zmianę kolejności punktów, ubytki i szum. Wcześniejszy audyt kodu wskazał
zachowywanie największego komponentu podczas końcowego czyszczenia;
sprawdzić utratę pozostałych fragmentów przed próbą pełnej serii.
Nie przejmować losowego rozstrzygania niepewnych nakładających się regionów
jako pewnej decyzji domenowej: takie miejsca mają pozostać niejednoznaczne.
[Źródło SBC](https://www.nature.com/articles/s41524-024-01498-x),
[audyt kandydata](research-domain-discovery-and-object-clustering.md).

## E3 — lokalna struktura obrazu STM

Pytanie: czy obraz uzupełnia brakujące centra i ujawnia orientacje oraz
rozstaw bez etykiet domen? Porównać lokalną autokorelację/widmo z EWT,
inspirowanym bezpośrednią publikacją STM z przeglądu.

Cechy pobierać na regularnej siatce całego pola, w kilku skalach. Dodatkowy
wariant pomiaru przy centrach pozwoli ocenić znaczenie oznaczeń. Nie wybierać
okien według poprzednich domen MolTrack. Energię, rozstaw i orientację
traktować osobno; sama jasność nie jest rozpoznaniem struktury.

Oryginalny wariant EWT z zadanym `K` może być porównaniem, lecz nie spełnia
warunku docelowego. Próba samodzielnego znajdowania grup musi dopuścić
jedną grupę i brak wiarygodnego porządku. Zamiana końcowego grupowania jest
naszą adaptacją wymagającą sprawdzenia. Przetestować pasy skanowania,
odwrócenie kontrastu i obszary z ubytkami oznaczeń. Użycie level set do
poprawy konturu rozważyć dopiero po uzyskaniu wiarygodnej informacji
o strukturze; nie rozwiązuje on sam wyboru i istnienia domen.

## Wyniki, ocena i kolejność wykonania

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

Najpierw E0 i E1, następnie E2 oraz E3 na tym samym wejściu. Kandydat,
który odrzuca wszystko, nie przechodzi kontroli jednej regularnej domeny.
Kandydat kolorujący szum jak sieć nie przechodzi kontroli zerowej. Nie
zastępujemy tych sprawdzeń samym wynikiem silhouette lub trwałości klastra.
Pozostałe miary przedstawiamy z odmowami, bez wybierania tylko łatwych miejsc.

Pierwszy rezultat dla użytkownika: wspólny podgląd pełnych klatek i tabela
tych kontroli, z propozycją dalszej metody albo konkretną przyczyną braku
wyboru. Dalsze oznaczenia prosimy przygotować dopiero dla ujawnionej luki
(np. rzeczywistej granicy przesunięcia). Obecne dane wystarczą do rozpoczęcia
porównania. Przyjęcie rozwiązania produkcyjnego pozostaje wynikiem odbioru 13.
