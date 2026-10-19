# Zapis MPP z wartościami i metadanymi

Type: grilling
Label: wayfinder:grilling
Status: claimed
Assignee: rlew
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 03

Zależy od: [Rejestracja i życie wyniku aligned](03-registration.md).

## Question

Jaki kontrakt eksportu MPP zachowa właściwe wartości, orientację, skalę,
metadane i brakujące piksele dla serii original oraz aligned?

Do ustalenia: wybór eksportowanej wersji i klatek; niezależność danych MPP od
gamma; jednostki wartości STP/S94; metadane po połączeniu plików i usunięciu
klatek; sposób kodowania brakujących pikseli; wymagane czytniki odbiorcze.
Ponowny odczyt ma obejmować wartości, orientację, rozmiar piksela, offset,
liczbę i kolejność klatek. Osobno trzeba określić możliwość ponownej rejestracji
zapisanego aligned.

## Comments

### 2026-10-14 — stan rozpoznania

Eksport MPP jest wymaganiem użytkownika. Zaproponowano zapis danych niezależny
od gamma; odpowiedź użytkownika dotyczyła opcji AVI, więc szczegółowy kontrakt
MPP pozostaje do uzgodnienia.

Nie znaleziono istniejącego eksportera MPP. Obecny czytnik obsługuje float64,
ale brakujące piksele aligned to NaN, a rejestracja wymaga skończonych wartości.
Istotne są także różne miejsca obrotu danych i różne jednostki wejścia.
Zobacz [rozpoznanie czytników](../reconnaissance.md).

### 2026-10-16 — konsekwencje kontraktu serii

[Seria wejściowa i usuwanie klatek](01-frame-series.md) dopuszcza różne skale
i kanały przy jednakowych wymiarach. Każda klatka zachowuje własne metadane,
pochodzenie i dostępny czas pomiaru, również po usunięciu innych lub odwróceniu
kolejności. Kontrakt MPP musi rozstrzygnąć zapis takiej serii, w tym różnych
metadanych, przerw w czasach pomiaru i ich odwróconej kolejności. Nie można
zakładać, że metadane pierwszej klatki opisują wszystkie pozostałe.

### 2026-10-19 — rozstrzygnięta rejestracja i aktualny zakres

[Rejestracja i życie wyniku aligned](03-registration.md#answer) ustala wspólny
powiększony obszar, zachowanie jego rozmiaru po usuwaniu i osobne informacje
o polu oryginalnej klatki oraz ważności próbek aligned. Eksport musi zachować
powiązanie z pochodzeniem i metadanymi każdej klatki; przy niespójnej skali
wynik nie ma jednej potwierdzonej skali fizycznej. Nie wolno mylić braku pomiaru
z zerem ani wyliczać pola oryginalnej klatki z liczby ważnych próbek aligned.

Odwracanie kolejności zostało wycofane z programu; wcześniejsze wzmianki o nim
w komentarzach opisują poprzedni zakres. Pozostają do ustalenia zapis przerw
w czasach po usuwaniu i pozostałe szczegóły eksportu. Obecny materializator
tworzy float32, a rejestracja wymaga skończonych wejść; precyzja zapisu,
kodowanie braków i możliwość ponownej rejestracji aligned wymagają decyzji.

### 2026-10-19 — rozpoczęcie rozmowy o eksporcie

Ticket przejęty do uzgodnienia specyfikacji, bez implementacji eksportera.
Pierwsza runda pytań czeka na odpowiedzi użytkownika:

1. Propozycja: wszystkie pozostałe klatki w bieżącej kolejności do jednego
   MPP; wybór original/aligned, domyślnie aktualny widok; bez wyboru zakresu.
2. Propozycja: wartości danych niezależne od gamma, zoomu i kolorów;
   aligned zawiera wartości po interpolacji rejestracji.
3. Wymagane programy odbiorcze: czy wystarczą STM Viewer, NaPara, NanoTrack
   i MolTrack, czy potrzebny jest też wskazany program zewnętrzny?

To pytania i rekomendacje, nie zatwierdzone decyzje. Wybór odbiorców wpływa
na dalsze ustalenia dotyczące metadanych, brakujących próbek i zgodności.
Fakty z kodu i prób zapisano w
[rozpoznaniu eksportu MPP](../reconnaissance.md#uzupełnienie-kontrakt-odczytu-mpp).
