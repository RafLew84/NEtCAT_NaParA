# REG-15b: Parametry modeli i wariantów Deep Matcher

**What to build:** Uzupełnić wspólne okno parametrów o Deep Matcher,
Deep + ECC, Deep + lokalne fragmenty, EfficientLoFTR, RoMa v2
i MatchAnything-ELoFTR. Po tym etapie wszystkie 13 obecnych metod
rejestracji ma edytowalny profil.
**Blocked by:** [REG-15a](15a-cpu-method-parameters.md), z odbiorem manualnym.
**Status:** ready-for-agent — zakres przygotowany; zależność otwarta.
**Manualny odbiór:** niewykonany; rozszerzenie jeszcze niewdrożone.
**Dodano do planu:** 2026-11-02, na zlecenie użytkownika.

Obowiązują [plan](../README.md), [protokół](../manual-protocol.md),
[zasady wykonania](../../implementation/README.md) i kontrakty konfiguracji,
cache oraz zapisanych wyników z [REG-15](15-method-parameters.md).
To rozszerzenie istniejącego okna, bez nowych modeli, wag i treningu.

## Wynik widoczny w aplikacji

W **Rejestracja → Parametry metod…** użytkownik wybiera każdą z sześciu
metod. Pola pokazujemy tylko wtedy, gdy są używane przez dany backend.
W hybrydach rozdzielamy podpisane grupy **Deep Matcher** i **Doprecyzowanie ECC**
albo **Lokalne fragmenty**. Każda z trzech konfiguracji Deep jest samodzielna:
zmiana bazowego Deep nie zmienia po cichu ustawień hybryd.

| Metoda / etap | Edytowane parametry | Obecne wartości domyślne |
| --- | --- | --- |
| Deep Matcher (LoFTR) | Próg dopasowań zgrubnych / tolerancja zgodności wektorów | 0,2 / 2 px original |
| Deep + ECC — Deep | Te same dwa parametry Deep, w osobnym profilu | 0,2 / 2 px original |
| Deep + ECC — ECC | Limit iteracji, epsilon, rozmiar filtra Gaussa | 100; 0,000001; 5 px |
| Deep + lokalne fragmenty — Deep | Te same dwa parametry Deep, w osobnym profilu | 0,2 / 2 px original |
| Deep + lokalne fragmenty — fragmenty | Liczba wierszy/kolumn siatki; rozmiar fragmentu; promień szukania; tolerancja zgodności | 4 × 4; 32 px; 16 px; 1,5 px original |
| EfficientLoFTR | Próg dopasowań zgrubnych / tolerancja zgodności wektorów | 0,2 / 2 px original |
| MatchAnything-ELoFTR | Próg dopasowań zgrubnych / tolerancja zgodności wektorów | 0,001 / 2 px original |
| RoMa v2 | Preset; liczba próbkowanych korespondencji; ziarno losowania; tolerancja zgodności wektorów | Turbo; 1000; 20261102; 2 px original |

Domyślne progi matcherów pochodzą z aktualnie używanych lokalnych konfiguracji;
MatchAnything zachowuje własne 0,001, a nie próg EfficientLoFTR.
Mały próg może dopuścić więcej błędnych dopasowań. Więcej próbek RoMa
nie gwarantuje poprawnego XY. Tolerancja zgodności wektorów dotyczy
estymacji pary, **nie progu Hubera** w optymalizacji grafu.

## Jedno miejsce edycji i przygotowanie obrazów

- [ ] Preset RoMa (Turbo/Fast/Base/Precise), liczba próbek i ziarno zostają
  przeniesione z dotychczasowych kontrolek do tego okna. Nie utrzymujemy
  dwóch edytowalnych kopii. Główne okno może pokazywać krótkie podsumowanie
  i odnośnik do parametrów. Migracja zachowuje wartości starszych sesji.
- [ ] Ścieżki kodu, wag, interpretera RoMa oraz wybór urządzenia pozostają
  w dotychczasowych ustawieniach zasobów. Parametry nie podmieniają
  checkpointu; obecny wybór indoor/outdoor Deep zachowuje działanie.
- [ ] Domyślny kontrast to **Dotychczasowe przygotowanie**, zgodne z każdą
  metodą. Percentyle/CLAHE korzystają z mechanizmu REG-15 na kopiach
  wejścia. Kolejność operacji jest jednoznaczna, wersjonowana i zapisana
  z wynikiem. Nie nakładamy dodatkowej korekcji dwukrotnie.
  Hybrydy używają tej samej przygotowanej pary na obu etapach; ich wewnętrzne
  operacje wejściowe pozostają jawne.
- [ ] Dotychczasowe skalowanie, padding, kolejność konwersji i mapowanie
  współrzędnych do original pozostają zachowane. W szczególności progi
  liczone w px original nie stają się progami w pikselach sieci.
  Nie dodajemy edycji rozdzielczości sieci, architektury ani precyzji inferencji.
  Aligned nadal powstaje z oryginalnych wartości, a gamma nie wpływa na XY.

## Walidacja i zachowanie wyników

- [ ] Progi dopasowań zgrubnych są skończone i mieszczą się w [0,1].
  Tolerancje zgodności, epsilon i liczby iteracji są dodatnie; filtr
  Gaussa ma dodatni nieparzysty rozmiar, a 1 wyłącza wygładzanie.
  Małe wartości progów można wpisać bez zaokrąglenia do zera.
- [ ] Lokalna siatka ma co najmniej dwa wiersze i dwie kolumny, rozmiar
  fragmentu co najmniej obecne minimum 16 px, a promień szukania jest
  dodatnią liczbą całkowitą. Wymiary i ilość ważnych danych sprawdzamy
  przy obliczeniu; sprzeczna konfiguracja daje przyczynę odmowy.
  Nie obniżamy minimów poparcia i pokrycia przestrzennego REG-05.
- [ ] RoMa zachowuje zakres 8–10000 próbek i całkowite ziarno 0–2147483647,
  oraz cztery dostępne presety. Ziarno służy odtwarzalności próbkowania,
  nie stanowi automatycznej oceny jakości. Nie dodajemy nowych presetów.
- [ ] Minimum korespondencji/wektorów i pozostałe reguły ostrzeżeń pozostają
  dotychczasowe dla każdej metody. Nie zamieniamy konsensusu starego Deep
  na konsensus nowych modeli. Odmowa nadal może wystąpić mimo większej
  liczby cech; nie zwracamy wtedy fałszywego (0,0).
- [ ] Deep + ECC nadal zaczyna od XY Deep. Nie pokazujemy parametrów
  inicjalizacji Phase, których ta hybryda nie wykorzystuje. Lokalny wariant
  nadal ocenia poparcie fragmentów, bez dołączania masek ani deformacji.
- [ ] Konfiguracja jest wspólna dla pary/łańcucha/grafu i pobierana także
  przez już otwarte okna przy następnym Oblicz. Zadanie otrzymuje niezmienną
  kopię; zatwierdzanie edycji podczas obliczeń jest zablokowane.
- [ ] Zmienione parametry faktycznie trafiają do konstruktora/modelu/workera.
  Pamięć modeli uwzględnia konfigurację; przy potrzebie przebudowy robi ją
  jawnie. RoMa nadal działa w osobnym środowisku, a aplikacja w netcat.
  Otwarcie edytora nie uruchamia modelu, nie wymaga wag i niczego nie pobiera.
- [ ] Cache grafu identyfikuje pełną konfigurację metody, kontrastu i zasobów.
  Nie miesza pomiarów po zmianie progu/presetu. LS/Huber na starych krawędziach
  nadal wykorzystuje ustawienia tych pomiarów, nie aktualny formularz.
- [ ] Sesja zachowuje wszystkie 13 profili, niezależnie od aktywnej metody,
  oraz konfiguracje wcześniejszych wyników, kandydatów i ręcznych korekt.
  MPP opisuje rzeczywiście użyte ustawienia. Starsze sesje/MPP zachowują
  historyczne wartości i odczyt bez modeli; walidacja pozostaje ścisła
  i wersjonowana. Nie podpisujemy starych wyników nowymi parametrami.
- [ ] OK nie przelicza ani nie zastępuje gotowego aligned. Błąd, odmowa
  lub anulowanie następnej próby zachowują wcześniejszą pracę.
  UI odróżnia parametry obecnego formularza od użytych w oglądanym wyniku.

## Podział kodu i granice TDD

Rozszerzyć profile oraz osobny dialog z REG-15. Konfigurację backendów
i workerów przekazywać przez wyraźne interfejsy we Viewerze. Nie dodawać
sześciu oddzielnych dialogów ani ogólnego systemu wtyczek.
Publiczna konfiguracja Deep w NanoTrack oraz lokalne konfiguracje modeli
są punktami integracji; nie edytować współdzielonych modułów w tej sesji.

Ważne obecne miejsca: stmviewer/deep_matcher.py, deep_ecc.py,
local_registration.py, local_consensus.py, efficient_runtime.py,
matchanything_runtime.py, roma_matcher.py, roma_worker.py i ui/roma_controls.py.
Nie wystarczy zmienić podpisu ustawień: np. próg MatchAnything jest dziś
ustawiany jawnie w runtime, a Deep/Efficient mają domyślne konfiguracje
konstruktorów modeli. Te wartości muszą wynikać z profilu zadania.

Publiczne granice sprawdzeń:

- **Dialog → konfiguracja:** sześć profili, osobne ustawienia hybryd,
  walidacja, reset/anulowanie, jedno miejsce edycji RoMa, brak wymogu modeli.
- **Konfiguracja → rzeczywisty runtime:** dla każdego z sześciu wariantów
  krótka próba z lokalnym modelem, ustawienia domyślne i zmienione,
  faktyczne przekazanie progów oraz przebudowa modelu/workera po zmianie.
  Testy jednostkowe mogą obejmować granicę biblioteki; nie zastępują całej
  walidacji atrapy backendu.
- **Obrazy → XY:** wzorzec o znanym przesunięciu, niekwadratowe wejście,
  zachowana geometria i wartości original; dla hybryd wynik i parametry
  obu etapów. Zmiana parametru nie musi zmienić XY łatwego obrazu.
- **Para/film/graf → zapis:** zgodne konfiguracje, cache, ochrona aktywnego
  wyniku, starsze i nowe sesje/MPP, pamięć nieaktywnego profilu, wcześniejszy
  wynik przy nowym formularzu oraz odczyt bez opcjonalnych runtime.

Typecheck, właściwe regresje, pełny zestaw repo raz na końcu i przeglądy
zgodnie z zasadami wykonania. Pliki kodu docelowo do 1000 linii,
maksymalnie **1500 linii fizycznych**.

## Próba manualna po tickecie

1. Uruchom conda activate netcat, python -m stmviewer.main.
   Otwórz **Rejestracja → Parametry metod…**. Sprawdź wszystkie 13 metod,
   opisy i domyślne wartości. Zmień Deep: profile obu hybryd mają pozostać
   niezależne. Sprawdź OK/Anuluj/reset i zachowanie siedmiu wcześniejszych metod.
2. Sprawdź przeniesione pola RoMa i zgodność ich podsumowania. Przełącz
   preset/liczbę próbek, zamknij i otwórz dialog; brak drugiej kopii edycji.
   Wskaż lokalne modele jak wcześniej — bez nowych pobrań.
3. Dla każdego z sześciu wariantów oblicz krótką serię na dostarczonym wzorcu
   znanego XY oraz wybraną parę na ustawieniach domyślnych i po zmianie
   jednego parametru. Sprawdź rzeczywiste ustawienia wyniku, czas i podgląd.
   Wersja implementacyjna instrukcji ma podać konkretne pliki/reproduktor.
4. Sprawdź graf i ponowne obliczenie po zmianie konfiguracji. Obie hybrydy
   pokazują ustawienia swoich etapów. Już otwarte okna pobierają nowe
   parametry, a zapisany graf nadal pozwala uruchomić LS/Huber na starych
   pomiarach i jawnie zastosować jego wynik.
5. MOVIE_4 po usunięciu dwóch początkowych klatek: bieżące pary 1→2,
   29→30 oraz 160→161; MOVIE_8: 1→2. Porównaj wybrany parametr z wartością
   domyślną na tych samych parach. Zapisz XY, poparcie, czas, ustawienia
   i ocenę wizualną; również odmowy, pogorszenia i brak rozstrzygnięcia.
   Nie ma wymogu pełnego przemiatania parametrów ani poprawy wszystkich metod.
6. Zapisz sesję ze zmienionymi nieaktywnymi profilami oraz wynikiem z dawnej
   konfiguracji. Otwórz ją i starszą sesję z ustawieniami RoMa. Sprawdź profile,
   wynik, kandydat, korekty, MPP i AVI. Bez dostępnego modelu można odczytać
   i obejrzeć gotowy wynik; nowe obliczenie jasno zgłasza brak zasobu.

**Oczekiwany wynik:** jeden edytor obejmuje wszystkie obecne metody, a
parametry można świadomie porównać na tych samych obrazach i odtworzyć z sesji.
Odbiór manualny jest osobny od testów automatycznych i oceny skuteczności.
Poza zakresem: automatyczne strojenie, nowe checkpointy, zmiana architektury,
nowe metody rejestracji, deformacje oraz przywracanie odłożonych etapów.
