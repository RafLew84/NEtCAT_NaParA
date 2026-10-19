# STM Domains — etap 1: działający szkielet

ID: stmdomains-map
Labels: wayfinder:map
Status: open
Assignee:

## Destination

Uzgodniona specyfikacja szkieletu STM Domains, który otwiera istniejący zapis
z oznaczeniami molekuł, doczytuje obrazy i pozwala sprawdzić je na kolejnych
klatkach. Mapa kończy się przygotowaniem implementacji i kryteriów odbioru
tego zakresu, bez oczekiwania na wybór metod analizy ani formatu wyników.

## Notes

Podział na dwa etapy zatwierdzony przez użytkownika 2026-10-16 zastępuje
wcześniejsze założenie jednej specyfikacji całego programu.

- Etap 1 obejmuje otwarcie zapisu MolTrack, automatyczne doczytanie obrazów
  z możliwością poprawienia ścieżki, nawigację klatek, zoom, gamma,
  oznaczenia molekuł oraz podgląd zapisanej rejestracji.
- Punktem odniesienia jest `data/TTMAPP/detection_full.moltrack.json`.
  Jedna analiza otwiera jeden zapis i należące do niego klatki; dopuszczona
  jest także seria z jedną klatką.
- Szkielet ma działać na rzeczywistych danych. Odbiór sprawdza zgodność obrazu,
  oznaczeń i współrzędnych; samo otwarcie pustego okna nie kończy etapu.
- Rejestrację odtwarzamy z wejścia. Oryginalny rozmiar klatki i zapisane
  przesunięcie wyznaczają pole pomiarowe po wyrównaniu; dopełnienie jest
  oddzielone od pomiaru. Zakres nie obejmuje ponownego liczenia rejestracji.
- Parametry fizyczne przykładowego MPP są zastępcze. Przy braku wiarygodnej
  kalibracji pokazujemy piksele, a przy braku czasu — numery klatek.
- Po uzgodnieniu tej mapy można przygotować i wykonać zadania implementacji
  szkieletu. Otwarte pytania drugiej mapy nie są warunkiem tego kroku.
- Po odbiorze działającego szkieletu przechodzimy do
  [etapu 2: metod i zapisu wyników](map-methods-and-save.md).
  Decyzji drugiego etapu nie rozstrzygamy przy projektowaniu szkieletu.

To mapa decyzji `wayfinder`; aktualizacja planu nie oznacza implementacji.
Przy rozstrzyganiu pytań używamy `grilling` i `domain-modeling`, a przy szkicu UI
`prototype`. [Rejestr pytań](issues/README.md) wskazuje aktywną mapę, zależności
i zasady wyboru ticketu. [Słownik](GLOSSARY.md) definiuje pojęcia.

Przed ustaleniem importu należy przeczytać
[audyt wejścia i orientacji obrazu](research-molecular-orientation.md).
Jego część o pomiarze kąta molekuły jest materiałem na późniejszą pracę.

## Decisions so far

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](issues/01-import-and-geometry.md):
  uzgodniono import MolTrack z jednym MPP, geometrię obu widoków i zachowanie
  przy przeniesionym źródle, brakach oznaczeń oraz słabej rejestracji.

- [Jak przeglądać obrazy i oznaczenia w szkielecie?](issues/07-browsing-and-comparison.md):
  po obejrzeniu prototypu TTMAPP wybrano jeden podgląd z paskiem miniatur,
  przełączaniem oryginał/wyrównany oraz nawigacją z play/pauzą.

## Not yet specified

Dodatkowe przypadki niespójnego wejścia mogą pojawić się podczas sprawdzania
kolejnych zapisów. Gdy ujawni się konkretny przypadek, należy doprecyzować
kontrakt importu lub dodać osobne pytanie blokujące szkielet.

## Out of scope

- Wykrywanie wysp i domen sieci, wybór metod, próby jakości, statystyki oraz
  własny zapis/eksport wyników — [osobna mapa etapu 2](map-methods-and-save.md).
- Pomiar orientacji pojedynczej molekuły — odłożony poza oba etapy;
  [wcześniejsze pytanie](issues/03-molecular-orientation.md) zamknięto jako
  odłożone, bez wyboru metody.
- Samodzielny import STP/MPP/S94 jako alternatywa dla zapisu z oznaczeniami.
  Doczytanie obrazu wskazanego w zapisie pozostaje częścią szkieletu.
- Detekcja YOLO, ręczne tworzenie oznaczeń i trenowanie detektora.
- Śledzenie tożsamości molekuł lub konkretnych domen między klatkami.
- Stały ROI dla całej serii oraz rozwój STM Viewer.
