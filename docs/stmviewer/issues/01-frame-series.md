# Seria wejściowa i usuwanie klatek

Type: grilling
Label: wayfinder:grilling
Status: resolved
Assignee: rlew
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: none

## Question

Jak działa jedna otwarta seria: kolejność klatek, kolejne wczytanie plików,
wymagana zgodność wymiarów i skali oraz usuwanie klatki z analizy?

Do ustalenia pozostają: sposób sortowania, zastąpienie/dodanie serii przy kolejnym
otwarciu, obsługa niezgodnych klatek i błędnego pliku, usunięcie ostatniej klatki
oraz zachowanie identyfikacji i metadanych po usunięciu. Wpływ na gotową
rejestrację rozstrzygnie [Rejestracja i życie wyniku aligned](03-registration.md)
po ustaleniu modelu serii.

## Comments

### 2026-10-14 — wymagania i odpowiedź użytkownika

Jedna seria to dowolna liczba plików STP/S94 (także mieszanka obu formatów)
albo dokładnie jeden MPP zawierający wiele klatek. Nie łączymy MPP z STP/S94.
Usunięcie usuwa zaznaczoną klatkę z bieżącej analizy; bez funkcji cofania.
Nie jest to polecenie kasowania źródła z dysku. W MPP operacja dotyczy klatki,
nie wszystkich klatek pliku.

Istniejący loader spełnia regułę formatów i wymaga identycznych wymiarów,
ale nie sprawdza zgodności skali ani kanału. Fakty i odnośniki:
[Rozpoznanie istniejącego kodu](../reconnaissance.md).

### 2026-10-19 — korekta zakresu

W [decyzji o rejestracji](03-registration.md#answer) użytkownik wycofał
odwracanie kolejności z programu. Poniższa odpowiedź uwzględnia tę korektę;
pozostałe zasady serii pozostają w mocy.

## Answer

### Uzgodnione z użytkownikiem 2026-10-16, skorygowane 2026-10-19

Rozstrzygnięcie po dwóch rundach rozmowy: użytkownik potwierdził reguły
kolejności, zastępowania, błędów i usuwania, wybrał zgodność wyłącznie wymiarów,
a następnie potwierdził rozdzielenie numeru bieżącego od pochodzenia.
Późniejsza korekta usuwa funkcję odwracania kolejności.

### Seria i kolejność

- Otwarta jest jedna seria: co najmniej jeden plik STP/S94 (można mieszać
  te formaty) albo dokładnie jeden MPP. Nie łączymy MPP z STP/S94 ani kilku MPP.
- STP/S94 sortujemy naturalnie po nazwie: `klatka2` przed `klatka10`.
  MPP zachowuje kolejność klatek zapisaną w filmie.
- Program nie oferuje odwracania kolejności. Usuwanie klatek nie zmienia
  wzajemnej kolejności pozostałych obrazów.

### Wczytywanie i zgodność

- Kolejne otwarcie zastępuje całą serię dopiero po poprawnym wczytaniu
  wszystkich nowych danych. Nie ma dopisywania do bieżącej serii.
- Wymagamy jednakowej szerokości i wysokości obrazów w pikselach.
  Różna skala fizyczna, kanał i pozostałe metadane nie blokują importu.
  Brak metadanych także nie jest powodem odrzucenia poprawnych obrazów.
  Nie wykonujemy automatycznego skalowania ani przycinania do wspólnego rozmiaru.
- Uszkodzony, nieczytelny lub niezgodny plik odrzuca cały nowy import.
  Komunikat wskazuje problematyczne źródła i powody; nie powstaje seria częściowa.
  Wcześniejsza seria, jej kolejność i wyświetlana klatka pozostają bez zmian.
  Gdy nie było serii, program pozostaje pusty.

### Usuwanie i tożsamość klatki

- Usuwamy zaznaczoną klatkę wyłącznie z bieżącej serii, bez funkcji cofania.
  Źródła na dysku pozostają bez zmian; w MPP operacja dotyczy jednej klatki.
- Po usunięciu pokazujemy następną klatkę według bieżącej kolejności;
  po usunięciu ostatniej — poprzednią. Usunięcie jedynej klatki zostawia
  pusty program, bez aktywnego obrazu.
- Numer bieżący oznacza pozycję `1…N` w aktualnej serii i jest aktualizowany
  po usunięciu. Osobno zachowujemy pochodzenie: plik źródłowy
  oraz pierwotny numer klatki w MPP. Zmiana pozycji nie zmienia pochodzenia.
- Metadane są powiązane z konkretną klatką. Jej skala, kanał, pozostałe
  dostępne dane źródłowe i czas pomiaru pozostają przy tym samym obrazie.
  Nie przypisujemy automatycznie metadanych pierwszej klatki całej serii.
  Nieznane wartości pozostają nieznane.
- Usunięcie nie przepisuje czasów pomiaru. Dla czasów `[10, 20, 30]`
  usunięcie środka daje `[10, 30]`. Nie dopisujemy sztucznych czasów
  ani nie usuwamy przerw.

### Przykłady do weryfikacji implementacji

| Sytuacja | Oczekiwany wynik |
| --- | --- |
| Wybór `10.stp`, `2.s94`, `1.stp` | Kolejność `1.stp`, `2.s94`, `10.stp`. |
| MPP z klatkami A, B, C | Kolejność A, B, C zgodna ze źródłem. |
| Usunięcie aktywnej B z A, B, C | Pozostaje A, C; widać C jako `2/2`, z pierwotnym pochodzeniem i metadanymi C. |
| Usunięcie aktywnej C z A, B, C | Pozostaje A, B; widać B. |
| Usunięcie jedynej klatki | Pusty program; plik źródłowy nadal istnieje. |
| Nowy import zawiera uszkodzony plik lub inne wymiary | Cały import odrzucony; poprzednia seria i wybór pozostają bez zmian. |
| Równe wymiary, lecz różne skale lub kanały | Import zaakceptowany; każda klatka zachowuje swoje metadane. |
| Poprawne kolejne otwarcie | Nowa seria zastępuje starą w całości. |

### Granice rozstrzygnięcia

Układ informacji na ekranie i odtwarzanie rozstrzyga
[Podgląd, gamma i odtwarzanie serii](02-preview-playback.md).
Wpływ usunięcia na gotowy wynik dopasowania oraz wymagania
rejestracji dla serii o różnych skalach lub kanałach pozostają w
[Rejestracji i życiu wyniku aligned](03-registration.md).
Zachowanie metadanych i czasu w pliku wynikowym należy do
[Zapisu MPP z wartościami i metadanymi](04-mpp-export.md).
Akceptacja serii przy imporcie nie rozstrzyga tych dalszych kontraktów.

Rozbieżności istniejącego kodu z tym kontraktem i sprawdzenia opisuje
[Rozpoznanie istniejącego kodu](../reconnaissance.md#uzupełnienie-seria-i-usuwanie-klatek).
Ten ticket ustala specyfikację; nie wdraża funkcji aplikacji.
