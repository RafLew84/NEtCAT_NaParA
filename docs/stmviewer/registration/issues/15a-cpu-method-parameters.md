# REG-15a: Parametry Phase, korelacji, Tile+RANSAC, ECC i Optical Flow

**What to build:** Rozszerzyć istniejące okno **Rejestracja → Parametry metod…**
o pięć pozostałych metod klasycznych. Użytkownik zmienia ustawienia, sprawdza
wybraną parę, a następnie używa tej konfiguracji w filmie lub grafie.
**Blocked by:** [REG-15](15-method-parameters.md), z odbiorem manualnym.
**Status:** ready-for-agent — zakres przygotowany; zależność od REG-15 spełniona
po odbiorze manualnym 2026-11-03. Wykonanie czeka na osobne zlecenie.
**Manualny odbiór:** niewykonany; rozszerzenie jeszcze niewdrożone.
**Dodano do planu:** 2026-11-02, na zlecenie użytkownika.

Obowiązują [plan](../README.md), [protokół](../manual-protocol.md),
[zasady wykonania](../../implementation/README.md) oraz wszystkie kontrakty
konfiguracji i wyników z REG-15. Ten etap dodaje profile do tego samego
okna, bez drugiego edytora i bez nowych algorytmów.

## Wynik widoczny w aplikacji

Wybór konfiguracji obejmuje dodatkowo **Phase**, **Korelację bez normalizacji**,
**Tile+RANSAC**, **ECC** i **Optical Flow**. Każda metoda pamięta własne wartości,
także po przełączeniu na inną. Edycja nie przełącza metody obliczeń.
Podstawowe pola są widoczne od razu, pozostałe w rozwijanych ustawieniach.
Opisy wyjaśniają kompromis dokładności, odporności i czasu; większa liczba
iteracji ani gęstsza siatka przesunięć nie oznaczają pewniejszego dopasowania.

| Metoda | Parametr | Obecna wartość domyślna |
| --- | --- | --- |
| Phase | Współczynnik doprecyzowania podpikselowego (upsample_factor) | 20 |
| Korelacja bez normalizacji | Współczynnik doprecyzowania podpikselowego | 20, osobno od Phase |
| Tile+RANSAC | Rozmiar fragmentu / krok między fragmentami | 32 / 16 px original |
| Tile+RANSAC | Doprecyzowanie podpikselowe | 1 |
| Tile+RANSAC | Tolerancja zgodności przesunięć fragmentów | 1,5 px original |
| ECC | Maksymalna liczba iteracji | 100 |
| ECC — zaawansowane | Kryterium zakończenia epsilon | 0,000001 |
| ECC — zaawansowane | Rozmiar filtra Gaussa | 5 px; 1 wyłącza wygładzanie |
| ECC — zaawansowane | Doprecyzowanie początkowego przesunięcia Phase | 20 |
| Optical Flow (TV-L1) | Przywiązanie do danych (attachment) | 15 |
| Optical Flow (TV-L1) | Parametr tightness | 0,3 |
| Optical Flow — zaawansowane | Liczba przeliczeń przepływu (num_warp) / iteracji | 5 / 10 |
| Optical Flow — zaawansowane | Tolerancja zakończenia | 0,0001 |
| Optical Flow — zaawansowane | Wstępny filtr przepływu (prefilter) | Wyłączony |

To wartości sprawdzone w obecnych backendach, nie nowy rekomendowany preset.
Współczynnik doprecyzowania opisujemy jako krok siatki 1/n piksela,
bez utożsamiania go z niepewnością pomiaru.

## Kontrakty obliczeń i walidacji

- [ ] Domyślna konfiguracja odtwarza dotychczasowe obliczenia każdej metody.
  Phase nadal używa normalizacji fazowej, a korelacja bez normalizacji —
  dotychczasowego wariantu bez tej normalizacji. Osobne profile nie
  przełączają tych zasad. Zmienione parametry są widoczne w opisie wyniku.
- [ ] Przygotowanie kontrastu ma domyślny tryb **Dotychczasowe przygotowanie**.
  Nie dokładamy min–max do metod, które wcześniej go nie stosowały.
  Opcjonalne percentyle i CLAHE korzystają z mechanizmu REG-15, wyłącznie
  na kopiach danych estymatora. Kolejność dodatkowego przygotowania oraz
  operacji backendu jest jednoznaczna i wersjonowana. Gamma pozostaje
  ustawieniem podglądu; dane original/aligned/eksportu zachowują wartości.
- [ ] Liczby iteracji, przeliczeń, rozmiary, krok i upsample są dodatnimi
  liczbami całkowitymi. Filtr Gaussa wymaga nieparzystego rozmiaru.
  Epsilon, tolerancje, attachment i tightness są skończone i dodatnie.
  UI pozwala wpisać małe wartości bez zaokrąglenia do zera.
  Techniczne górne limity są jawne; nie są przedstawiane jako naukowe progi.
- [ ] Parametry zależne od rozmiaru obrazu są sprawdzane przy obliczeniu.
  Za duży fragment lub brak dostatecznego poparcia daje czytelną odmowę.
  Nie korygujemy po cichu konfiguracji, nie dodajemy paddingu udającego dane
  i nie obniżamy dotychczasowych minimów poparcia, w tym trzech fragmentów
  dla Tile+RANSAC.
- [ ] ECC nadal wyznacza translację, nie obrót ani deformację. Optical Flow
  nadal używa TV-L1 i redukuje wektory do jednego globalnego XY.
  Parametry nie włączają lokalnego przekształcania pikseli ani nowego
  wariantu ILK. Nie pokazujemy pól backendu, które nie są używane.
- [ ] Obowiązują atomowe OK, Anuluj/reset, blokada zatwierdzenia podczas
  obliczeń oraz niezmienna kopia konfiguracji zadania z REG-15.
  Już otwarte okna pary/grafu pobierają nowe wartości przy kolejnym Oblicz.
- [ ] Para, łańcuch i graf rzeczywiście przekazują wszystkie ustawienia do
  tego samego backendu. Zmiana parametrów unieważnia możliwość ponownego
  użycia wcześniejszych pomiarów jako nowej próby. Gotowe wyniki, ręczne
  korekty oraz wcześniejsze LS/Huber zachowują swoją konfigurację.
- [ ] Sesja pamięta wszystkie siedem profili dostępnych po tym etapie,
  także nieaktywne. Konfiguracja formularza jest niezależna od konfiguracji
  zapisanych wyników i kandydatów. Starsze sesje i MPP zachowują historyczne
  ustawienia; nowe metadane opisują rzeczywiście użyte wartości.
  Odczyt gotowych wyników nie wymaga dostępności estymatorów.

## Wskazówki implementacyjne i granice TDD

Parametry są już dostępne w publicznych konfiguracjach modułów
nanotrack/registration: phase_correlation, tile_correlation, ecc_translation
i optical_flow. Integracja i edytor należą do stmviewer.
**Obecna fabryka wspólna ignoruje backend_params dla Phase** — należy
przekazać konfigurację przez publiczny konstruktor backendu we Viewerze,
a nie ograniczyć się do zapisu pól, których algorytm nie użyje.
Potrzebne zmiany wspólne należy zgłosić w handoff zgodnie z instrukcjami repo.

Publiczne granice sprawdzeń:

- **Dialog → konfiguracja:** wartości domyślne pięciu metod, niezależność
  profili, walidacja, OK/Anuluj/reset i zachowanie wcześniejszych profili.
- **Konfiguracja + obrazy → wynik:** rzeczywiste pięć backendów, znane XY,
  wartości domyślne i zmienione. Sprawdzić faktyczne przekazanie parametrów
  oraz niezmienione zachowanie domyślne normalizacji obu korelacji.
- **Konfiguracja → cykl pracy:** para/film/graf, okna otwarte przed edycją,
  cache, ochrona poprzedniego wyniku i oryginalnych wartości.
- **Sesja/MPP → odczyt:** nowe i stare formaty, nieaktywne profile, wynik
  policzony innymi ustawieniami niż obecny formularz, kandydat i korekty.

Testy obserwują zachowanie na publicznych granicach; nie wymagają, by każdy
parametr zmieniał XY na łatwym obrazie. Obowiązują typecheck, regresje,
pełny zestaw repo raz na końcu i przeglądy zgodnie z zasadami wykonania.
Nie rozbudowywać głównego okna o logikę algorytmów.
Cel pliku do 1000 linii; twardy limit **1500 linii fizycznych**.

## Próba manualna po tickecie

1. Uruchom conda activate netcat, python -m stmviewer.main.
   W **Rejestracja → Parametry metod…** sprawdź pięć nowych metod, opisy,
   wartości domyślne, niezależność, Anuluj, OK i reset jednej konfiguracji.
2. Otwórz tests/stmviewer/fixtures/registration/cpu.mpp.
   Dla każdej metody policz parę przy ustawieniach domyślnych i po zmianie
   jednego parametru. Porównaj znane XY, parametry wyniku i podgląd.
   Użyj także przygotowanego wzorca z niecałkowitym XY dla upsample;
   implementacja dostarcza sposób jego odtworzenia.
3. Dla każdej metody policz krótki film i graf. Przy otwartym oknie pary
   lub grafu zmień ustawienie przez menu, ponów obliczenie i sprawdź
   rzeczywiście używaną konfigurację. Stary wynik zachowuje swój opis.
4. Sprawdź percentyle/CLAHE względem domyślnego przygotowania na kopii
   tej samej pary. Original, gamma i eksportowane wartości nie zmieniają się.
   Wpisz błędny rozmiar filtra i zbyt duży fragment: komunikat ma wyjaśniać
   problem bez utraty wcześniejszego aligned.
5. MOVIE_4 po usunięciu pierwszych dwóch klatek: porównaj bieżące pary
   1→2, 29→30 oraz 160→161; MOVIE_8: 1→2. Zmieniaj jeden parametr naraz,
   zapisując XY, ustawienia, czas i ocenę wizualną, również pogorszenie
   lub odmowę. Nie ma wymagania poprawy wszystkich metod na tych parach.
6. Zapisz sesję z nieaktywnymi zmienionymi profilami i wcześniejszym wynikiem.
   Otwórz ją, sprawdź profile, stary wynik, kandydat, LS/Huber i zastosowanie.
   Sprawdź starszą sesję oraz zapis/odczyt MPP i krótki AVI.

**Oczekiwany wynik:** wszystkie klasyczne metody mają użyteczne ustawienia
w jednym oknie, odtwarzalne między parą, filmem i grafem. Manualny odbiór
obejmuje funkcję i ocenę jakości osobno; nie jest zastępowany Qt offscreen.
Następny etap: [REG-15b](15b-model-method-parameters.md).
