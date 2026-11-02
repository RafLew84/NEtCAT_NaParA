# STM Domains — etap 1: działający szkielet

ID: stmdomains-map
Labels: wayfinder:map
Status: resolved
Assignee:

## Destination

Uzgodniona specyfikacja szkieletu STM Domains, który otwiera istniejący zapis
z oznaczeniami molekuł, doczytuje obrazy i pozwala sprawdzić je na kolejnych
klatkach. Mapa kończy się przygotowaniem implementacji i kryteriów odbioru
tego zakresu, bez oczekiwania na wybór metod analizy ani formatu wyników.

## Notes

**Implementacja SD-V4-02 — 2026-11-02:** działają oznaczenia molekuł,
maski z regulacją krycia, kliknięcie metadanych i odtworzenie zapisanej
rejestracji w widokach raw/aligned. [Raport i test ręczny](implementation/interactive-v04/acceptance-02.md).
279 testów aplikacji PASS, GUI sprawdzone na TTMAPP; odbiór użytkownika 02
pozostaje otwarty. Pełny zakres szkieletu wymaga jeszcze m.in. miniatur,
gamma i odtwarzania z 03.

**Implementacja SD-V4-01 — 2026-11-02:** wykonano pierwszy przekrój
obejmujący import MolTrack/MPP i przeglądanie oryginałów w działającym oknie.
[Raport i odbiór ręczny](implementation/interactive-v04/acceptance-01.md).
Użytkownik potwierdził testy ręczne 01; na jego kolejne zlecenie dodano
suwak pod obrazem do przełączania klatek podczas przeciągania.
Ręczny odbiór dodatku (`ee54638`) również potwierdzono 2026-11-02.
Oznaczenia i wyrównanie dodano następnie w 02, zgodnie z aktualizacją powyżej.

Specyfikację pierwszej mapy zakończono 2026-10-19.
[Zadania budowy i odbioru](implementation/README.md) są gotowe do podjęcia;
pełny szkielet nie został jeszcze zaimplementowany ani odebrany. Status mapy
odnosi się do decyzji, nie do gotowości programu.

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

- [Jak przekazać szkielet do implementacji i go odebrać?](issues/09-implementation-handoff.md):
  ustalono lokalne moduły, ponowne użycie czytnika, kontrast i pełne odtwarzanie
  klatek; trzy zadania wykonawcze rozdzielają kod, testy oraz odbiór danych i GUI.

## Not yet specified

Nie pozostały znane decyzje blokujące rozpoczęcie implementacji szkieletu.
Nowy przypadek niespójnego wejścia ujawniony podczas budowy wymaga opisania
w zadaniu wykonawczym; jeśli zmienia kontrakt, należy doprecyzować odpowiednią
decyzję albo dodać konkretne pytanie. Nie jest to warunek odkładania obecnej budowy.

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
