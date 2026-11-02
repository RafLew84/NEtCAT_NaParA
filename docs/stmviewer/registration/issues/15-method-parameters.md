# REG-15: Okno parametrów AKAZE i LightGlue/SuperPoint

**What to build:** Z menu głównego użytkownik otwiera małe okno parametrów
wybranej metody, zmienia przygotowanie kontrastu i ustawienia dopasowania,
sprawdza parę, a następnie używa tej samej konfiguracji w filmie lub grafie.
**Blocked by:** [REG-13](13-lightglue-superpoint.md) oraz [REG-14](14-akaze.md).
REG-13 jest odebrany; REG-14 ma implementację i status ready-for-review,
oczekuje manualnego odbioru. Dodanie ticketu nie oznacza tego odbioru.
**Status:** ready-for-agent — zakres przygotowany; zależność REG-14 otwarta.
**Manualny odbiór:** niewykonany; funkcja jeszcze niewdrożona.
**Dodano do planu:** 2026-11-02, na zlecenie użytkownika.

Obowiązują [plan](../README.md), [protokół](../manual-protocol.md)
i [zasady wykonania](../../implementation/README.md).
Podstawa zakresu: uzgodniona propozycja małego okna parametrów oraz
[diagnoza jasności/kontrastu](../brightness-diagnosis.md).
Historyczne stałe konfiguracje REG-13/14 stają się ustawieniami domyślnymi;
ten ticket rozszerza je o świadomą edycję, bez zmiany wcześniejszych wyników.

## Wynik widoczny w aplikacji

Menu **Rejestracja → Parametry metod…** otwiera jedno kompaktowe okno.
Na początek obsługiwane są wyłącznie **AKAZE** i **LightGlue + SuperPoint**.
Domyślnie wskazana jest metoda wybrana w głównym oknie, jeżeli należy do
obsługiwanych; w przeciwnym razie ostatnio edytowana, a przy pierwszym
otwarciu AKAZE. Lista w dialogu wybiera konfigurację do edycji — nie
przełącza samoczynnie metody obliczeń w głównym oknie, parze ani grafie.

Widok podstawowy zawiera najważniejsze pola danej metody.
**Przygotowanie kontrastu** i **Ustawienia zaawansowane** są rozwijane.
Krótkie opisy wyjaśniają wpływ wartości, np. „Mniejszy próg wykrywa więcej
punktów, również pochodzących z szumu”. Przy tolerancji podajemy jednostkę
px original. Nie opisujemy większej liczby punktów jako gwarancji dokładności.

Przyciski: **Przywróć domyślne**, **Anuluj**, **OK**.
Pod formularzem: **„Zmiany dotyczą kolejnego obliczenia.”**

## Parametry pierwszej wersji

| Metoda / grupa | Edytowane ustawienie | Wartość domyślna / zachowanie |
| --- | --- | --- |
| AKAZE | Próg odpowiedzi detektora | 0,001; dodatnia liczba, obsługa co najmniej 0,000001–0,01 |
| SuperPoint | Próg wykrywania punktów | 0,0005; zakres (0,1] |
| SuperPoint | Promień NMS | 4 px; nieujemna liczba całkowita |
| SuperPoint | Maksymalna liczba punktów | 2048; dodatnia liczba całkowita |
| LightGlue | Próg akceptacji korespondencji | 0,1; zakres [0,1] |
| LightGlue — zaawansowane | Pełne obliczenia | Wyłączone; po włączeniu depth_confidence=−1 i width_confidence=−1 |
| Każda z dwóch metod, osobno | Tolerancja zgodności przesunięć | 2 px original; liczba dodatnia |
| Każda z dwóch metod, osobno | Przygotowanie kontrastu | Obecne min–max; alternatywnie percentyle lub CLAHE |

To zakres edycji, nie lista zaleconych parametrów optymalnych.
Walidacja odrzuca NaN/Inf, niewłaściwy typ oraz wartości spoza dziedziny.
Pola liczbowe umożliwiają wygodne wpisanie małych progów, bez ich obcięcia
do zera. Ewentualne techniczne górne limity kontrolek są jawne i opisane.

Przy wyłączonych pełnych obliczeniach LightGlue zachowuje obecne
depth_confidence=0,95, width_confidence=0,99. Nie zmieniamy liczby warstw,
checkpointów, wariantu deskryptorów ani precyzji inferencji.
AKAZE zachowuje MLDB, wzajemny Hamming i pozostałe ustawienia REG-14.
Minimum ośmiu korespondencji i czterech zgodnych wektorów, pozostałe reguły
ostrzeżeń oraz algorytm konsensusu pozostają stałe.
Tolerancja konsensusu jest parametrem estymacji pary, nie progiem Hubera.

### Przygotowanie kontrastu

- **Min–max:** dokładne zachowanie domyślne REG-13/14, bez zmiany rozmiaru.
- **Percentyle:** dolny i górny percentyl, domyślnie 1 i 99;
  0 ≤ dolny < górny ≤ 100. Zakres wyznaczany osobno dla każdego obrazu,
  wartości poza nim obcinane, następnie mapowane do zakresu wejścia metody.
- **CLAHE:** limit kontrastu domyślnie 2 oraz liczba pól siatki X/Y domyślnie
  8 × 8. Limit dodatni, wymiary siatki dodatnie całkowite. Konwersja do uint8,
  zaokrąglenie, kolejność normalizacji i dalsze wejście LightGlue są
  jednoznaczne, wersjonowane i zapisane z wynikiem. Punktem wyjścia jest
  odtwarzalna próba z diagnozy, nie niejawne wykorzystanie gamma podglądu.

Jedno przygotowanie stosujemy osobno do obu obrazów pary.
Stały lub zdegenerowany zakres daje kontrolowaną odmowę, bez dzielenia
przez zero. Istniejąca polityka braku ważnych próbek pozostaje: NaN/Inf
nie są wypełniane w celu tworzenia cech. Nie dodajemy resize ani masek.
Przygotowanie dotyczy roboczych danych estymatora; oryginały, obrazy używane
do renderowania aligned i dane eksportu zachowują wartości pomiarowe.

## Zachowanie konfiguracji i wyników

- [ ] **OK** waliduje i zatwierdza edytowane konfiguracje obu metod jako
  jedną operację. Przełączenie metody wewnątrz dialogu zachowuje robocze
  zmiany; Anuluj/zamknięcie krzyżykiem odrzuca cały niezatwierdzony formularz.
  Przywrócenie domyślnych dotyczy tylko aktualnie edytowanej metody i wymaga OK.
- [ ] Otwarcie edytora nie wymaga danych, wag, Torch ani CUDA. W trakcie
  zadania blokujemy zatwierdzanie zmian; zadanie korzysta z niezmiennej
  kopii ustawień pobranej przy jego starcie.
- [ ] Ustawienia są osobne dla każdej metody i wspólne dla pary, łańcucha
  oraz grafu. Także już otwarte okna pary/grafu pobierają bieżącą
  konfigurację przy następnym **Oblicz**. Powrót do metody odtwarza jej wartości.
- [ ] OK nie uruchamia zadania ani nie zmienia aktywnego aligned, ręcznych
  korekt, istniejącej próby pary lub kandydata grafu. Błąd/anulowanie następnej
  rejestracji zachowuje wcześniejszą pracę.
- [ ] Każdy wynik ma niezmienny zapis rzeczywiście użytych parametrów,
  przygotowania, wersji i diagnostyki. Gdy bieżące ustawienia różnią się od
  tych w oglądanym wyniku, UI jasno wskazuje tę różnicę.
- [ ] Nowe obliczenie grafu identyfikuje pomiary pełną konfiguracją:
  detektor, matcher, przygotowanie kontrastu, tolerancja, wersja i zasoby.
  Nie miesza krawędzi z różnych konfiguracji. Po zmianie ustawień nie wolno
  użyć starych pomiarów jako nowego wyniku.
- [ ] Ponowne LS/Huber na zapisanym grafie nadal używa jego wcześniejszych
  krawędzi i konfiguracji; nie uruchamia automatycznie nowych dopasowań.
  Gotowy wcześniejszy kandydat zachowuje możliwość jawnego zastosowania.
- [ ] Sesja zapisuje obie konfiguracje, także nieaktywną, oraz niezależne
  konfiguracje gotowych wyników. Niezastosowany kandydat pozostaje kandydatem.
  Odczyt starszych sesji zachowuje ich historyczne ustawienia i wyniki.
- [ ] Metadane MPP zachowują konfigurację wyniku oraz historię korekt
  i poprzedników; odczyt nie przypisuje wynikom aktualnych wartości formularza.
  Sam gotowy wynik można przeglądać/eksportować bez runtime estymatora.
  Wersjonowanie i walidacja obsługują zarówno stare stałe, jak i nowe
  edytowalne konfiguracje. Nie luzujemy walidacji przez akceptowanie dowolnych pól.
- [ ] Odświeżenie konfiguracji backendu/workera jest jawne; nie pozostawia
  modelu działającego ze starymi parametrami. Korzystamy z istniejących
  lokalnych wag i bibliotek, bez pobierania oraz zastępowania metody.

## Podział kodu i granice TDD

Osobny moduł konfiguracji/walidacji oraz osobny moduł dialogu.
Główne okno podłącza menu i przekazuje stan; nie przechowuje kopii reguł
algorytmu w kontrolkach. Wspólne przygotowanie kontrastu nie powiela
implementacji w parze, łańcuchu i grafie. Nie dodajemy ogólnego systemu
wtyczek ani szerokiego refaktoru innych metod.

Proponowane publiczne granice do realizacji skillem implement:

- **Dialog → konfiguracja:** wartości domyślne, osobna pamięć obu metod,
  walidacja małych progów i percentyli, OK/Anuluj/reset, stan zajętości.
- **Konfiguracja + obrazy → wynik/odmowa:** rzeczywisty AKAZE i LightGlue
  ze zmienionymi parametrami; kontrola przekazania do zewnętrznej biblioteki
  oraz znane XY. Domyślny wariant odtwarza zachowanie REG-13/14.
- **Kontrast → wejście estymatora:** deterministyczne przygotowanie,
  przypadki stałego obrazu/braków, oryginalna geometria i nienaruszone dane.
- **Para/film/graf → życie wyniku:** spójna konfiguracja, brak użycia
  nieaktualnych pomiarów po zmianie, niezmienny stary wynik, ochrona przy
  błędzie/anulowaniu oraz użycie starego grafu przez LS/Huber.
- **Sesja/MPP → odczyt:** stare formaty i nowe parametry, pamięć niewybranej
  metody, konfiguracja historycznego wyniku różna od aktualnego formularza,
  korekty, kandydat, brak runtime; wartości eksportu i geometria bez zmian.

Testujemy zachowanie i rzeczywiste granice bibliotek, bez testów
powtarzających prywatną strukturę kodu. Typecheck, odpowiednie regresje,
pełny zestaw repo raz na końcu i dwa przeglądy zgodnie z zasadami wykonania.
Cel pliku kodu do 1000 linii, twardy limit **1500 linii fizycznych**.

## Próba manualna po tickecie

1. W katalogu Viewera uruchom conda activate netcat, python -m stmviewer.main.
   Bez filmu otwórz **Rejestracja → Parametry metod…**. Sprawdź rozmiar okna,
   opisy, obie metody, zwijane grupy i prawidłowe wartości domyślne.
2. Zmień próg AKAZE i ustawienie LightGlue, przełączając metodę w dialogu.
   Anuluj — oba mają pozostać bez zmian. Powtórz i zatwierdź OK; zamknij
   i otwórz dialog. Reset jednej metody nie może zmienić drugiej.
3. Użyj data/registration-reg14/known.mpp dla pełnego cyklu AKAZE oraz
   tests/stmviewer/fixtures/registration/cpu.mpp dla domyślnego LightGlue.
   Instrukcja implementacji ma podać odtwarzanie wzorców, jeśli plików brak.
   Oblicz parę, film i graf, sprawdź pokazane parametry i znane XY.
4. Przy gotowym wyniku zmień jeden parametr. Dotychczasowy obraz i jego
   opis pozostają; następna próba używa nowego ustawienia. Powtórz z oknem
   pary/grafu otwartym jeszcze przed zmianą konfiguracji.
5. Oblicz graf, zmień parametry, oblicz nowy graf. Sprawdź ponowne pomiary
   i brak mieszania konfiguracji. Osobno sprawdź Huber na wcześniej
   zapisanych pomiarach oraz jawne zastosowanie i ręczną korektę.
6. Zapisz sesję przy wybranym Phase, z nieaktywnymi zmienionymi ustawieniami
   obu metod i wynikiem obliczonym wcześniejszą konfiguracją. Otwórz sesję:
   formularz, wynik i kandydat muszą odtworzyć swoje odrębne konfiguracje.
   Sprawdź również przygotowaną sesję sprzed REG-15.
7. Przy istniejącym aligned sprawdź błąd/odmowę/anulowanie. Zapisz i odczytaj
   MPP, wyeksportuj AVI i obejrzyj w VLC. Przygotowanie kontrastu nie może
   trwale zmienić jasności danych pomiarowych ani nadpisać gamma podglądu.
8. MOVIE_4: usuń dwie początkowe klatki; porównaj bieżące pary 1→2, 29→30
   i 160→161. MOVIE_8: 1→2. Zmieniaj jeden parametr naraz względem ustawień
   domyślnych; uwzględnij próg detektora/matchera i przygotowanie kontrastu.
   Zapisz ustawienia, korespondencje, zgodne wektory, XY, czas i ocenę
   wizualną; także odmowy, pogorszenia i wynik nierozstrzygalny.

Próby nie wymagają kompletnego przemiatania parametrów ani ponowienia
całego pilotażu 72 prób. Automatyczne Qt, modele, GUI i VLC raportujemy osobno.

**Oczekiwany wynik:** wygodna, odtwarzalna regulacja parametrów z jednego
okna i spójne użycie ich w całej aplikacji. Samo zniknięcie odmowy nie jest
kryterium poprawności XY. Ticket nie obiecuje naprawy pierwszej pary MOVIE_4.

Poza zakresem: nowe metody/checkpointy, automatyczny dobór parametrów,
osobny zestaw dla każdej pary/klatki, optymalizacja progów pod przejście
odmowy, obniżanie minimalnej liczby korespondencji/wektorów, zmiana Hubera,
filtry pasów, maski, deformacje i przywrócenie odłożonych etapów.
Ścieżki modeli i wybór urządzenia pozostają w dotychczasowych kontrolkach.
