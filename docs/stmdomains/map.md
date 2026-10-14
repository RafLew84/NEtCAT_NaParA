# STM Domains — specyfikacja analizy typów uporządkowania w serii

ID: stmdomains-map
Labels: wayfinder:map
Status: open
Assignee:

## Destination

Uzgodniona specyfikacja STM Domains: od otwarcia zapisu z gotowymi oznaczeniami
molekuł i powiązanymi obrazami, przez analizę uporządkowania położeń i orientacji,
do porównania stałych typów uporządkowania i ich ilości na kolejnych klatkach.
Mapa kończy się, gdy decyzje pozwalają przygotować zadania implementacyjne.

## Notes

Zakres uzgodniony z użytkownikiem 2026-10-14:

- Punktem wejścia jest zapis z innego programu; przykładem jest
  `data/TTMAPP/detection_full.moltrack.json`. Obrazy wskazane w zapisie są
  doczytywane automatycznie, z możliwością poprawienia ścieżki.
  W ramach jednej analizy otwieramy jeden zapis i należące do niego klatki.
- Potrzebne jest przeglądanie klatek i oznaczeń otwartego zapisu, wyników analizy
  oraz zmian ilościowych w serii. Zapis z jedną klatką też należy do zakresu.
- Typy uporządkowania mają to samo znaczenie w całej serii. Analiza obejmuje
  regularność położeń oraz orientację samych molekuł; nie zakładamy katalogu A/B/C
  ani obowiązkowej symetrii M6. Definicja kąta molekuły pozostaje do ustalenia.
- Wyniki ilościowe: liczba molekuł według typu, powierzchnia i udział domen
  oraz liczba oddzielnych domen na każdej klatce.
- Rejestracja jest już częścią przykładowego zapisu. Oryginalny rozmiar klatki
  i zapisane przesunięcie wyznaczają jej pole pomiarowe po wyrównaniu.
  Dodatkowe dopełnienie nie należy do powierzchni odniesienia ani do domen.
- Wartości fizyczne z nagłówka przykładowego MPP są zastępcze. Nie traktujemy
  ich jako kalibracji; brak rzeczywistego czasu również nie uprawnia do wymyślania
  osi czasu zamiast numerów klatek.

To mapa decyzji, nie lista implementacji. Nie zamyka się pytań na podstawie
samego działania kodu; skuteczność metod wymaga osobnej oceny.

Lokalny tracker znajduje się w wersjonowanym `docs/stmdomains/`, zgodnie
z instrukcjami repozytorium. Jego [operacje i zależności](issues/README.md)
prowadzą do pytań, które można podjąć. Ta mapa nie powiela ich treści.
Przy pracy używamy `wayfinder`, `grilling` i `domain-modeling`, a dla prototypów
`prototype`. [Słownik](GLOSSARY.md) porządkuje nazwy używane w rozmowie.

Źródła istniejących ustaleń technicznych:
[wykrywanie domen](research-general-domain-detection.md),
[orientacja molekuły i audyt wejścia](research-molecular-orientation.md).
Nie są zatwierdzeniem konkretnego algorytmu. Na starcie nie dodajemy nowych
pytań typu research: obecne pytania dotyczą wyborów użytkownika i prób na
posiadanych danych. Konkretna luka wymagająca źródeł zewnętrznych może utworzyć
nowe pytanie badawcze podczas dalszej pracy.

## Decisions so far

<!-- Brak zamkniętych ticketów. Ustalenia zakresu pochodzą ze zlecenia;
     ich zapis w Notes nie oznacza rozstrzygnięcia pytań metodycznych. -->

## Not yet specified

Nie znamy jeszcze dodatkowych problemów, które ujawnią próby na kolejnych
akwizycjach: zmian wyglądu motywu, niespójności eksportów lub klas błędów
wymagających własnego sposobu oceny. Gdy pojawi się konkretny przypadek,
powstanie osobne pytanie albo zostanie zawężone istniejące.

## Out of scope

- Samodzielne dodawanie STP, MPP i S94 jako alternatywnego wejścia aplikacji.
  Czytanie obrazu wskazanego przez zapis nadal należy do zakresu.
- Detekcja YOLO, tworzenie oznaczeń ręcznych i trenowanie detektora w STM Domains;
  użytkownik dostarcza gotowe oznaczenia.
- Śledzenie tożsamości pojedynczych molekuł i konkretnych domen między klatkami,
  w tym historie podziałów, scaleń i narodzin domen.
- Stały ROI lub wspólne pole wybrane do porównania całej serii. Liczymy oryginalne
  pole każdej klatki, przemieszczone zgodnie z rejestracją.
- Implementacja produkcyjnej aplikacji podczas wytyczania tej mapy; poza celem
  pozostaje też niezależny rozwój STM Viewer.
