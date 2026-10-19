# Przekazanie — film AVI STM Viewer

Data: 2026-10-19
Gałąź: `viewer/start`
Baza bieżącej zmiany: `08c9ca6`
Commit zamykający: identyfikator w końcowej wiadomości sesji.

## Wynik

Rozstrzygnięto [Opcje filmu AVI](issues/05-avi-export.md#answer) po dwóch rundach
odpowiedzi. Wyłącznie pełne obrazy, wybór original/aligned i zakresu klatek,
gamma z podglądu lub 1,0, FPS przy eksporcie, tło czarne/szare/białe,
opcjonalna podziałka i numer/czas, dwa tryby kontrastu, proporcje z danych,
MJPG domyślnie albo FFV1. Ciche obcinanie nieparzystych wymiarów zastępuje
jawne dopełnienie zachowujące wszystkie krawędzie.

Użytkownik wycofał proponowany wycinek i szachownicę z AVI. Przeniesiono
wynik do mapy, słownika, odnośników z podglądu/rejestracji oraz kryteriów
odbioru. Wszystkie zmiany dotyczą specyfikacji i dowodów z małej próby;
nie wdrożono eksportera ani nie zmieniono wspólnych modułów.

Następny dostępny ticket: [Dane i kryteria odbioru pierwszej wersji](issues/06-acceptance.md).
Mapa pozostaje otwarta; ten ticket ma ustalić konkretne dane i środowiska
oraz sprawdzić pozostałe blokady implementacji. Nie zidentyfikowano nowego
pytania wymagającego osobnego ticketu poza już zapisaną decyzją odbioru.

Wcześniejszy kontrakt MPP i jego potrzeby integracji są zachowane w
[decyzji MPP](issues/04-mpp-export.md#answer), [rozpoznaniu](reconnaissance.md)
i historii `08c9ca6`. Prototyp podglądu pozostaje w wersji `efb7e50`.

## Wykonane sprawdzenia

- Przeczytano kod ViewerWidget, SequenceViewerWidget i lokalnego pyqtgraph:
  gamma LUT, automatyczne poziomy per klatka, wpływ skali X/Y, zastępowanie
  NaN medianą w kopii wyświetlanej i ustawienie row-major.
- Sześć małych syntetycznych prób AVI w conda netcat, OpenCV 4.11.0/FFmpeg:
  MJPG/FFV1 × parzyste, nieparzyste i dopełnione wymiary. Każda zapisywała
  siedem klatek przy 7,5 FPS. Sprawdzono backend, liczbę i rozmiary faktycznie
  odczytanych klatek, FPS i różnice pikseli. [Raport i odtwarzalny skrypt](avi-export-reconnaissance.md).
- FFV1 po dopełnieniu/parzystych wymiarach odtwarzał raster dokładnie;
  MJPG zmieniał piksele stratnie. Sam sukces otwarcia writera nie wykrył
  obcięcia ostatniego wiersza/kolumny.
- Sprawdzono 125 lokalnych odnośników/kotwic, statusy i brak cykli zależności
  sześciu ticketów oraz zachowanie pierwotnego pytania. Dostępny jest ticket
  odbioru. `git diff --check` przeszedł poprawnie; zapisany skrypt próby jest
  identyczny z wykonanym, a jego składnia została sprawdzona przez AST.

Nie uruchamiano pełnego zestawu testów, produkcyjnego GUI ani odtwarzacza
zewnętrznego. Nie sprawdzano wielkich filmów, anulowania i błędów zapisu,
renderowania NaN/opisów przez nową aplikację ani prawdziwego eksportera.
Nie instalowano zależności. Minimalny szkielet nadal nie obejmuje OpenCV.

## Potrzeby implementacji i integracji

- Renderer pełnej klatki oddzielony od zrzutów okna: ważne próbki, wybrany
  kontrast/gamma, proporcje, maska, tło, opisy i dopełnienie. Przypisanie NaN
  do mediany w starym widgetcie nie spełnia kontraktu.
- Wspólny kontrast liczyć wyłącznie z wybranych klatek i ważnych próbek.
  Obsłużyć stały obraz, brak ważnych próbek i serie o różnych jednostkach;
  korekcja jasności nie ujednolica jednostek pomiaru.
- Zachować cały istniejący obszar aligned i powiązanie klatek z czasami.
  Nie przeliczać rejestracji i rozmiaru obszaru dla wybranego zakresu.
- Fizyczne proporcje i podziałka wymagają wspólnej wiarygodnej kalibracji;
  przy jej braku film używa pikseli. Maska i opisy muszą uwzględniać tę samą
  geometrię. Techniczny padding nie zmienia skali pomiaru.
- Wybrany kodek sprawdzić w środowisku; brak metody ma być jawny, bez
  automatycznego zastąpienia. Nieparzystych wymiarów nie przekazywać bez
  dopełnienia do obecnego writera. Zapis tymczasowy, postęp i anulowanie
  powinny chronić poprzedni wynik przed błędem nowego eksportu.
- Zależności i testy współdzielonych zmian uzgodnić z sesją integracyjną.
  Dalszy odbiór ma wskazać docelowe odtwarzacze, formaty danych i rozmiary
  oraz objąć wcześniejsze wymagania MPP/WSxM. Nie trzeba ich rozstrzygać
  ponownie w osobnym tickecie AVI.
