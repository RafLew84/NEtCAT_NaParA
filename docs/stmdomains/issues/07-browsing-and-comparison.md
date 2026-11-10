# Jak przeglądać obrazy i oznaczenia w szkielecie?

ID: 07
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
Assignee: Codex — domains/browsing-contract
Parent: [STM Domains — etap 1: działający szkielet](../map.md)
Blocked by: 01

## Question

Jaki minimalny układ okna pozwala otworzyć zapis, sprawdzić zgodność oznaczeń
z obrazem i przejrzeć klatki bez wdrażania analizy domen?

Przygotujmy szkic do reakcji użytkownika: wybór zapisu, naprawa ścieżki do
obrazu, nawigacja serii, obraz z gotowymi oznaczeniami, zoom i gamma,
przełączanie original/aligned z użyciem zapisanej rejestracji oraz granica
oryginalnego pola pomiarowego. Ustalmy zachowanie przy pojedynczej klatce,
brakujących oznaczeniach, brakującej rejestracji i niewiarygodnej kalibracji.

Rozstrzygnięcie opisuje podstawowy ekran i przejścia zaakceptowane na szkicu.
Interfejs ma umożliwić wizualne sprawdzenie importu na rzeczywistych danych.
Wyniki metod, warstwy domen, wykresy i statystyki należą do etapu 2; ich brak
nie blokuje tego pytania. Wejściowe oznaczenia pozostają danymi do podglądu.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)

## Answer

### 2026-10-19 — przyjęty układ i zachowanie

Użytkownik obejrzał prototyp i wybrał **C — jeden podgląd i pasek miniatur**.
Przyjął też pokazane zachowanie: przywracanie zapisanej klatki i widoku,
play/pauzę z wyborem szybkości, zatrzymanie na końcu serii oraz zachowanie
poprzedniej serii przy anulowaniu lub błędzie otwierania. Zoom, gamma
oraz nakładki dotyczą wyłącznie podglądu. Wcześniejszy kontrakt importu
pozostaje wiążący.

Podstawowy ekran ma jeden duży obraz, przełącznik oryginał/wyrównany,
sterowanie obrazem i nakładkami oraz dolny pasek nawigacji z miniaturami.
Szczegóły bieżącej klatki są rozwijane na żądanie. Widok dwóch obrazów
obok siebie i boczna lista klatek nie wchodzą do przyjętego szkieletu.

Porównane warianty zachowano jako materiał decyzji:

- A: lista klatek i informacje z boku, jeden obraz z przełączaniem
  oryginał/wyrównany.
- B: oryginał i zapisane wyrównanie tej samej klatki obok siebie, wspólne
  sterowanie klatką, gammą, skalą powiększenia i przesuwaniem.
- C: jeden obraz z przełączaniem widoku, pasek miniatur na dole, informacje
  o klatce rozwijane na żądanie.

Artefakt lokalny:
`/home/rlew/projekty/NEtCAT-domains/.scratch/browsing-prototype/index.html`.
Otwieramy w przeglądarce, bez serwera; domyślnie uruchamia się wybrany C.
Dolne strzałki i parametr
`?variant=A/B/C` przełączają układ. Lista „Przykład stanu” pozwala obejrzeć
braki danych. Źródła i instrukcja odtworzenia są na osobnej gałęzi
`prototype/stmdomains-browsing`, commit
`cb51fbf04802620637dd7d10acc19863717de083`, katalog `stmdomains/prototypes/`.
**Nie scalać tej gałęzi do aplikacji.** Wygenerowane obrazy, HTML i zrzuty
pozostają lokalne, poza Git; po przeniesieniu repo trzeba je odtworzyć.

### Przyjęte zachowania podglądu

- Po otwarciu przywracamy zapisaną klatkę i tryb podglądu; TTMAPP otwiera
  klatkę 268 w widoku wyrównanym. Brak poprawnej rejestracji pozostawia oryginał.
- Nawigacja: poprzednia/następna, numer i suwak klatki oraz dolny pasek
  miniatur. Odtwarzanie 1, 2, 5, 10 lub 20 kl./s,
  domyślnie 5; pauza na bieżącej klatce, koniec zatrzymuje odtwarzanie.
  Ponowny start z końca jest opisany jako „Od początku”. Ręczna zmiana klatki
  i otwarcie dialogu zatrzymują odtwarzanie. To szybkość przeglądania,
  nie czas pomiaru. Jedna klatka wyłącza odtwarzanie i zbędną nawigację.
- Kółko powiększa wokół kursora, przeciąganie przesuwa, „Dopasuj” przywraca
  cały widok. Gamma, powiększenie i nakładki dotyczą podglądu. Zmiana klatki
  zachowuje te ustawienia; przełączenie oryginał/wyrównany zachowuje
  klatkę, gammę i nakładki, ale ponownie dopasowuje cały obraz.
- Ramki, maski i granica oryginalnego pola mają oddzielne przełączniki;
  maski mają regulację krycia. Kliknięcie ramki pokazuje identyfikator,
  źródło, pewność detektora i bbox w oryginale. Podświetlenie nie edytuje
  oznaczeń ani flagi `selected`. To dane wejściowe, nie wyniki analizy domen.
- Padding w wyrównaniu ma osobne tło, a pole pomiarowe przerywaną granicę.
  Informacja o niskiej pewności zapisanej rejestracji pozostaje widoczna;
  nie obliczamy nowego dopasowania.
- Brak masek wyłącza ich przełącznik bez ukrywania poprawnych ramek. Brak
  zapisanych oznaczeń daje komunikat i nadal pokazuje obraz; nie oznacza
  braku molekuł. Brak rejestracji blokuje współrzędne `expanded_aligned`,
  których położenia nie można ustalić. Dla wejścia zawierającego ramki `raw`
  obowiązuje dostępny podgląd z kontraktu importu; fixture nie ma tego przypadku.
- Rozmiar i współrzędne są w px; nieznana kalibracja i czas są opisane
  wprost. Numery klatek nie sugerują odstępu czasowego.
- Pusty start prowadzi do otwarcia MolTrack. Dialogi pokazują szukanie MPP,
  wskazanie nowej ścieżki, odrzucenie niezgodnego źródła i potwierdzenie
  zgodnego źródła mimo zmienionego mtime. Anulowanie lub błąd zachowują
  poprzednią serię, klatkę i ustawienia podglądu; nowy zapis zastępuje ją
  dopiero po sprawdzeniu źródła i wymaganym potwierdzeniu.

### Dane, sprawdzenia i ograniczenia

Szkic wykorzystuje parę TTMAPP z [audytu importu](../import-geometry-audit.md):
268 obrazów 256 × 256 px, 52 494 ramki oraz 11 993 maski SAM. Maski występują
na klatkach 1–40; klatki 64–68 nie mają zapisanych ramek. Canvas wyrównania
480 × 408 px, padding LTRB 224, 139, 0, 13; globalne translacje nie są sumowane.
Ramki zachowują ułamkowe współrzędne, obraz jest interpolowany liniowo,
a maski najbliższym sąsiadem. Wyświetlana maska jest unią masek molekuł,
nie definicją powierzchni wyspy.

Generator w lokalnym środowisku `netcat` przygotował HTML około 53,5 MiB
w 5,72 s, przy szczycie RSS 554,2 MiB. Maski dekoduje po jednej. Te liczby
opisują generator fixture'a; nie są pomiarem kosztu docelowego importera.
Źródła identyfikuje `index.json` obok HTML oraz SHA-256 zgodne z audytem.

W QtWebEngine sprawdzono przejścia A/B/C, maski i ich braki, brak ramek,
brak rejestracji, jedną klatkę, pusty start, symulowane otwieranie i naprawę
ścieżki, błędny MPP/JSON, potwierdzenie mtime, zmianę klatki/gamma/zoom,
podświetlenie ramki, play/pauzę i zatrzymanie na końcu. Anulowanie i błędny
zapis pozostawiły poprzednią serię oraz klatkę. Inspekcja w oknie 1100 × 760:
brak błędów JS i poziomego przepełnienia, obejrzane zrzuty A/B/C.
Log `inspection.json` i zrzuty są w tym samym lokalnym katalogu co HTML.
Inspekcja dotyczy źródeł `d9c7eb8`; po wyborze użytkownika `cb51fbf` zmienia
wyłącznie wariant domyślny na sprawdzony C i zapisuje wybór w README prototypu.

Nie jest to gotowy importer ani natywne okno PyQt. Wybór plików, walidacja
nowego źródła, pojedyncza klatka i brak rejestracji są symulowane. Rzeczywiste
obrazy, ramki, maski i przesunięcia pochodzą z wejścia. Wyświetlanie używa
percentyli 2–98 na klatkę i 8-bitowych PNG; nie rozstrzyga to jeszcze polityki
normalizacji intensywności aplikacji. Nie oceniano jakości rejestracji ani
metod wykrywania. Kod aplikacji i współdzielonych modułów nie był zmieniany.

### Granice rozstrzygnięcia

To wybór ekranu i zachowania szkieletu; nie oznacza wykonania natywnego
programu. Odtworzenie miniaturek, koszt importu i płynność nawigacji w PyQt
wymagają sprawdzenia podczas implementacji. Politykę normalizacji oraz zachowanie
odtwarzania przy wolnym przygotowaniu klatki doprecyzowano w [przekazaniu do implementacji](09-implementation-handoff.md#answer--2026-10-19).
Nie wolno traktować wartości 8-bitowego szkicu jako danych pomiarowych.

Dalsze [przekazanie do implementacji i kryteria odbioru](09-implementation-handoff.md)
korzysta z tego wyboru. Analiza domen, statystyki, korekty konfliktów oraz
zapis i eksport wyników pozostają w etapie 2.

## Comments

### 2026-10-16 — podział zakresu zatwierdzony przez użytkownika

Zawężono wcześniejsze pytanie o kompletny interfejs analizy do podglądu
szkieletu. Prezentację prób metod przeniesiono do
[Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md), a interakcje
z trwałymi wynikami do [Co zapisujemy i eksportujemy po próbach metod?](08-save-and-export.md).

### 2026-10-19 — rozpoczęcie prototypu

Przygotowujemy trzy warianty podstawowego podglądu na rzeczywistych obrazach
i oznaczeniach TTMAPP. Źródła prototypu pozostają na osobnej gałęzi; jego wybór
rozstrzyga układ i zachowanie szkieletu, nie implementuje aplikacji ani analizy.

### 2026-10-19 — odpowiedź użytkownika

Wybrano „C — jeden podgląd i pasek miniatur” i potwierdzono „Tak — przyjmij
pokazane zachowanie”. Wybór zamyka pytanie o podstawowy podgląd; źródła
prototypu pozostają oddzielone od kodu aplikacji.
