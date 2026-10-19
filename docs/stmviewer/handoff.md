# Przekazanie — rejestracja STM Viewer

Data: 2026-10-19
Gałąź dokumentacji: `viewer/start`
Baza bieżącej zmiany: `db4cc7c`
Aktualizacja prototypu: `prototype/stmviewer-preview-playback`, commit `efb7e50`.
Commit dokumentacji: identyfikator w końcowej wiadomości sesji.

## Wynik

Rozstrzygnięto [Rejestrację i życie wyniku aligned](issues/03-registration.md)
po dwóch rundach odpowiedzi użytkownika. Wynik obejmuje sposób NanoTrack,
obliczanie z oryginałów, podmianę po sukcesie, postęp/anulowanie, zachowanie
dopasowania po usuwaniu, niepewność, dostępność metod oraz geometrię i maski.
Ticket ma status `resolved`; [mapa](map.md) i [słownik](GLOSSARY.md) są aktualne.

Użytkownik wycofał odwracanie kolejności z programu. Skorygowano odpowiedzi
o serii i podglądzie oraz usunięto operację z prototypu. Jego
[dokumentacja](preview-playback-prototype.md) wskazuje aktualny commit
i zachowuje odnośnik do pierwotnego eksperymentu. Prototyp jest na osobnej
gałęzi, nieprzeznaczonej do scalenia do kodu produkcyjnego.

Na `viewer/start` zmienia się tylko dokumentacja. Aplikacja nadal jest szkieletem;
nie wdrożono rejestracji. Do ticketów eksportu dopisano wynikające z decyzji
ograniczenia i wymagania dotyczące danych.

Dostępne są teraz [Zapis MPP z wartościami i metadanymi](issues/04-mpp-export.md)
oraz [Opcje filmu AVI](issues/05-avi-export.md).

## Wykonane sprawdzenia

- Przegląd rejestracji, materializacji aligned, modeli, UI i istniejących testów.
- Dwie próby w pamięci: geometria i skończone próbki po przesunięciu subpikselowym
  oraz propagowanie niskiej pewności przez łańcuch dopasowań.
- Odczyt lokalnych źródeł Kornia/Torch potwierdzający możliwość pobierania wag
  przez obecny Deep Matcher; bez inicjalizacji modelu i bez sieci.
- Uruchomienie poprawionego prototypu w Qt WebEngine: A/B/C, Play/Pause, wybór
  klatki, usuwanie do pustej serii, ponowne wczytanie i Stop na końcu;
  brak przycisku odwracania i brak błędów JavaScript.
- Kontrola lokalnych linków, statusów i zależności ticketów, zgodności kopii
  prototypu z commitem oraz `git diff --check`.

Nie uruchamiano zestawu testów aplikacji ani produkcyjnego GUI. Nie oceniano
jakości dopasowania pomiarów, wydajności dużych serii ani eksportu.
Szczegóły i odnośniki: [rozpoznanie](reconnaissance.md#uzupełnienie-rejestracja-i-geometria-wyniku).

## Potrzeby implementacji i integracji

- Obecne UI NanoTrack kasuje stary wynik po błędzie i nie obsługuje anulowania.
  Potrzebne są responsywna operacja z anulowaniem, postęp obejmujący także
  przygotowanie aligned i publikacja dopiero kompletnego wyniku.
- Zachowanie aligned po usunięciu wymaga stabilnego powiązania z pochodzeniem
  klatek, historycznym odniesieniem i niezmienioną geometrią obszaru.
  Nie należy kopiować unieważniania wyniku z MolTrack ani ponownie przeliczać
  zachowanych obrazów tylko z powodu zmiany ich bieżących indeksów.
- Wynik musi rozróżniać pole oryginalnej klatki i maskę ważnych próbek.
  Obecny `ViewerWidget` wypełnia NaN medianą w kopii podglądu; szachownica
  wymaga osobnej obsługi maski. Uproszczony helper aligned obcinający obraz
  i powielający brzegi nie spełnia kontraktu.
- Wspólne modele/materializator używają jednej metadanej serii. Trzeba zachować
  metadane poszczególnych klatek, również po usuwaniu. Pozostaje wcześniejszy
  problem czasów nieusuwanych razem z obrazem w MolTrack i pól pierwszej klatki
  używanych przez loader STP/S94 do opisu całej serii.
- Deep Matcher wymaga sprawdzenia lokalnej dostępności bez pobierania wag
  oraz ścieżki uruchomienia, która nie inicjuje automatycznego pobierania.
  Samo istnienie pliku cache nie zapewnia poprawnego załadowania modelu.
- Czytnik STP pomija warianty nazw offsetu i kanału obecne w fixture. Jednostki,
  precyzja, kodowanie braków i ponowny odczyt pozostają w decyzji eksportu MPP.
  Zależności przyszłych funkcji wykraczają poza minimalny szkielet PyQt6.

Miejsce realizacji zmian (warstwa STM Viewer czy rozszerzenie wspólnego modułu)
należy ustalić przy podziale implementacji. Wspólnego kodu i konfiguracji
głównej w tej sesji nie zmieniono. Wcześniejszy błąd odwracania przy odtwarzaniu
sesji NanoTrack jest opisany w rozpoznaniu, ale nie blokuje zakresu STM Viewer
po wycofaniu odwracania.
