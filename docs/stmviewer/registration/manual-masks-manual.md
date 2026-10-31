# REG-03 — ręczna próba masek rejestracji

Ticket: [REG-03](issues/03-manual-masks.md).
Wyniki i ograniczenia: [karta REG-03](reviews/REG-03.md).
Obowiązuje [wspólny protokół oceny](manual-protocol.md).
Poniższe kroki są instrukcją odbioru, nie deklaracją ich wykonania przez użytkownika.

## Uruchomienie i znaczenie masek

```bash
cd /home/rlew/projekty/NEtCAT-viewer
conda activate netcat
python -m stmviewer.main
```

Metoda **Korelacja z maskami (v1)** używa osobnych oznaczeń klatki bazowej
i przesuwanej. **Uwzględnij oznaczenia klatek** pojawia się tylko po wybraniu
tej metody. Wyłączenie tej opcji pozostawia ten sam algorytm masked NCC,
korzystający z całego dostępnego obrazu. To pozwala porównać wpływ samych masek.
Phase, Deep Matcher, Optical Flow i pozostałe metody nie używają tych oznaczeń.
Domyślną metodą po uruchomieniu nadal jest Phase.

**Edytuj maski…** w głównym oknie otwiera bieżącą klatkę. **Edytuj maski tej
pary…** w oknie pary otwiera klatkę przesuwaną; pole **Klatka:** w edytorze
pozwala przejść także do bazowej i pozostałych klatek. Każda klatka ma własne
prostokąty; program nie przenosi ich automatycznie na sąsiadów.

W oknie **Maski rejestracji — oryginalne klatki**:

- **Dodaj: użyj** wyznacza obszary brane pod uwagę. Jeśli ich nie ma, podstawą
  jest cały dostępny obraz. Jeśli jest ich kilka, podstawą jest ich suma.
- **Dodaj: pomiń** odejmuje wskazane prostokąty od podstawy, również tam, gdzie
  nakładają się na „użyj”. Brakujące próbki nigdy nie stają się ważne.
- **Pokaż maskę** włącza kolorowy podgląd: zielony oznacza używane próbki,
  czerwony pomijane. Lista pokazuje granice prostokątów w pikselach original,
  np. `[0, 80) × [0, 12)` obejmuje kolumny 0–79 i wiersze 0–11.
- **Przesuwaj** służy przeciąganiu widoku. W trybie dodawania przeciąganie
  rysuje prostokąt. Kółko myszy przybliża w obu trybach; dostępne są także
  **−**, **+**, **Pokaż cały obraz**, **Gamma** i **Proporcje pikselowe**.
- Zaznacz element listy i wybierz **Usuń wybrany prostokąt**, aby usunąć jedno
  oznaczenie. **Wyczyść maskę tej klatki** usuwa wszystkie jej prostokąty.

Edycja działa od razu w pamięci bieżącej sesji. Zamknięcie edytora zachowuje
oznaczenia; nie ma osobnego przycisku zatwierdzającego. Nie są zapisywane
w MPP, AVI ani w sesji na dysku — zapis sesji przewidziano w REG-07.
Zmiana maski nie przelicza istniejących wyników. Nowe obliczenie trzeba
uruchomić przez **Dopasuj automatycznie** dla pary albo **Rejestruj** dla serii.
Przełączniki **Uwzględnij oznaczenia klatek** w tych dwóch oknach są osobne.

## Wzorzec: ten sam algorytm z maskami wyłączonymi i włączonymi

Gotowy plik `tests/stmviewer/fixtures/registration/masked-artifact.mpp`
zawiera 3 klatki, każda o rozmiarze 80 × 64 piksele. Górne 12 wierszy to
mocny nieruchomy artefakt, a struktura poniżej niego przesuwa się między
klatkami. [Generator](../../../tests/stmviewer/make_mask_fixtures.py)
odtwarza ten wzorzec; nie trzeba tworzyć pliku ręcznie.

1. Otwórz wzorzec przez **Otwórz STP/S94/MPP…**. Wybierz klatkę 2 oraz
   **Porównaj parę…**. Pole **Klatka przesuwana:** ma wartość 2, bazową jest 1.
   Ustaw **Korelacja z maskami (v1)**, gamma 1, proporcje pikselowe oraz
   **Nakładka 50/50**.
2. Wyłącz **Uwzględnij oznaczenia klatek**, kliknij **Dopasuj automatycznie**.
   Oczekuj **ΔX=0 px, ΔY=0 px**: estymator dopasował dominujący nieruchomy pas.
   Kliknij **Zachowaj do porównania**.
3. Wybierz **Edytuj maski tej pary…**. Ustaw **Dodaj: pomiń** i zaznacz górny
   pas od `(0,0)` do `(80,12)`. Sprawdź na liście `[0, 80) × [0, 12)` oraz
   **Używane próbki: 4160 / 5120**. Jeśli granice są inne, usuń prostokąt
   i narysuj go ponownie przy większym zoomie. Prawy koniec przeciągnięcia
   może wyjść poza obraz — współrzędne są przycinane do jego granicy.
4. Przez pole **Klatka:** przejdź do klatki 1 i zaznacz ten sam pas.
   Następnie zrób to na klatce 3. Na każdej pozostaje **4160 / 5120** próbek.
   Sprawdź osobno obie klatki pary; maska jednej nie zastępuje maski drugiej.
5. Przełącz **Przesuwaj**, przybliż, przesuń widok, zmień gamma i wróć do
   **Pokaż cały obraz**. Zmień klatkę i wróć. Oznaczenia nadal obejmują górne
   12 wierszy original, niezależnie od powiększenia i położenia podglądu.
   Wyłącz **Pokaż maskę**, aby obejrzeć sam obraz bez kolorowego wypełnienia.
6. Zamknij edytor. Dotychczasowe karty pary i główny obraz pozostają bez zmian.
   Włącz **Uwzględnij oznaczenia klatek**, kliknij **Dopasuj automatycznie**.
   Oczekuj **ΔX=−4 px, ΔY=+3 px**. Przełączaj **Wynik bieżący** i **Wynik
   zachowany**, a także **Bez przesunięcia / Z dopasowaniem**. Z maskami
   rozpoznawalne struktury poniżej pasa powinny się pokrywać; sam zakłócający
   pas może teraz różnić się położeniem.
7. Rozwiń **Szczegóły wybranego wyniku**. Wynik bieżący opisuje maski włączone,
   współrzędne prostokątów oraz niezweryfikowaną pewność. Zachowany nadal ma
   maski wyłączone i XY=(0,0). Nowa edycja oznaczeń nie zmienia zapisanych
   ustawień ani obrazu żadnego z tych ukończonych wyników. Zmiana pary czyści
   jej karty, więc kolejne porównanie zacznij od nowego wyniku bez masek.
8. Zamknij okno pary. W głównym oknie wybierz **Korelacja z maskami (v1)**,
   włącz **Uwzględnij oznaczenia klatek** i kliknij **Rejestruj**. Oczekiwane
   przesunięcia skumulowane klatek 1–3 to **(0,0), (−4,+3), (−7,+1)**,
   a rozmiar aligned to **87 × 67 pikseli**. Sprawdź original/aligned,
   zoom, przesuwanie, gamma i Play. Górny pas nadal jest częścią obrazu.

Pełne obliczenie używa niezmiennej kopii masek z chwili uruchomienia. Nowa
edycja dotyczy następnej próby. Wykonanie prób pary samo nie zastępuje pełnego
aligned; **Rejestruj** tworzy nowy wynik całej serii i podmienia go po sukcesie.

## Dodawanie, odejmowanie i odmowa obliczenia

Te próby wykonaj po zapisaniu wyników porównania. Potem przywróć górny pas
„pomiń” na każdej klatce, jeżeli chcesz ponownie uzyskać liczby wzorca.

1. Wyczyść maskę klatki 1. Dodaj dwa częściowo nakładające się prostokąty
   **użyj**, a następnie **pomiń** przecinający oba. Nakładka ma pokazywać
   sumę zielonych obszarów pomniejszoną o pominięty fragment. Usuwaj elementy
   listy i obserwuj zmianę licznika. Po usunięciu ostatniego „użyj” podstawą
   ponownie staje się cały obraz, z zachowaniem pozostałych „pomiń”.
2. Na klatce 2 wybierz **Wyczyść maskę tej klatki** i dodaj **pomiń** dla
   całego `(0,0)–(80,64)`. Oczekuj **0 / 5120**. Gotowy aligned oraz wcześniejsze
   wyniki pary nie zmieniają się podczas tej edycji.
3. Uruchom **Rejestruj** z maskami włączonymi. Program powinien odmówić
   obliczenia, podać przyczynę braku danych i zachować poprzedni aligned.
   W oknie pary 1→2 analogicznie sprawdź **Dopasuj automatycznie**: po błędzie
   wcześniejsze wyniki bieżący i zachowany pozostają dostępne. Powtórz
   wykluczenie całego obrazu na klatce bazowej, aby sprawdzić obie strony pary.
4. Przy takim samym oznaczeniu wyłącz **Uwzględnij oznaczenia klatek**
   i ponów dopasowanie pary. Obliczenie powinno się udać z XY=(0,0), bo
   użytkownik jawnie wybrał cały obraz. Lista oznaczeń pozostaje zachowana.
5. Przełącz metodę na Phase lub Deep Matcher. Checkbox masek znika; oznaczenia
   pozostają w edytorze, ale ta metoda ich nie uwzględnia. Wróć do
   **Korelacja z maskami (v1)** i sprawdź dostępność przełącznika.

Wersja v1 wymaga co najmniej 64 wybranych ważnych pikseli, rozpiętości co
najmniej 4 pikseli w obu osiach i tekstury w wybranych danych. Po dopasowaniu
wymaga wspólnego poparcia co najmniej 64 pikseli i 30% mniejszej maski
(`overlap_ratio=0.3`) oraz tekstury we wspólnej części. Spełnienie tych warunków
nie dowodzi poprawnego dopasowania. Wynik ma **pewność niezweryfikowaną**;
nie ma niezależnej oceny jakości ani cichego powrotu do danych bez maski.

## Powiązanie ze źródłem, import i anulowanie

1. Odtwórz oznaczenia trzech klatek wzorca i zapisz prostokąty klatki źródłowej
   MPP 3. W głównym oknie wybierz klatkę 2 i **Usuń klatkę**. Edytor zostanie
   zamknięty. Otwórz go ponownie na nowej pozycji 2: nagłówek ma wskazywać
   **MPP 3**, a jej prostokąty pozostać bez zmian. Maska źródłowej klatki 2
   została usunięta, plik źródłowy pozostaje nienaruszony.
2. Spróbuj otworzyć dostarczony uszkodzony plik
   `tests/stmviewer/fixtures/truncated.stp`. Po błędzie dotychczasowa
   seria, oznaczenia i wynik mają pozostać dostępne.
3. Ponownie poprawnie otwórz `masked-artifact.mpp`. To nowa seria: licznik
   oznaczonych klatek ma wynosić **0 / 3**. Również ponowne otwarcie tego samego
   źródła usuwa poprzednie edytowalne maski.
4. Próbę anulowania wykonaj na dłuższym MOVIE_4 lub MOVIE_8 po uzyskaniu
   pełnego aligned. Zanotuj nazwę i XY wyniku, otwórz edytor, ponów **Rejestruj**.
   Podczas obliczeń rysowanie i usuwanie oznaczeń są zablokowane. W edytorze
   nadal można przechodzić między klatkami, oglądać obraz, przesuwać podgląd,
   zmieniać zoom i gamma.
5. Kliknij **Anuluj rejestrację**. Po zakończeniu bieżącego kroku oczekuj
   zachowania poprzedniego aligned i odblokowania edycji. Analogiczną próbę
   pary można zatrzymać przez **Przerwij obliczanie**. Jeżeli obliczenie zdąży
   zakończyć się sukcesem, nie zalicza to próby anulowania; zapisz ten fakt
   i ponów na dłuższej serii. Nie usuwaj klatek w trakcie obliczeń.

## MOVIE_4 i MOVIE_8 — ocena struktur

W MOVIE_4 usuń pierwszą klatkę, a następnie ponownie pierwszą **przed nową
rejestracją**. Pozostają 362 klatki: źródłowe 3–364. Plik na dysku nie zmienia
się. Samo usunięcie z gotowego aligned zachowuje dawną geometrię, więc wykonaj
nowe **Rejestruj** na poprawionej serii.

| Film | Pary źródłowe, od 1 | Bieżące pary w aplikacji |
| --- | --- | --- |
| `data/MOVIE_4.mpp` po usunięciu źródłowych 1 i 2 | 3→4, 33→34, 120→121 | 1→2, 31→32, 118→119 |
| `data/MOVIE_8.mpp` | 1→2, 16→17, 56→57 | 1→2, 16→17, 56→57 |

Dla każdej pary oblicz **Korelację z maskami (v1)** z wyłączonymi oznaczeniami
i zachowaj wynik. W edytorze obejrzyj osobno oba oryginały; zaznacz widoczne
uszkodzone pasy jako „pomiń” albo wybierz obszary z rozpoznawalną strukturą
jako „użyj”. Zapisz dla każdej źródłowej klatki rodzaj i współrzędne wszystkich
prostokątów. Oblicz tę samą metodę z włączonymi oznaczeniami.

Porównuj wyniki przy jednakowym kadrze, kontraście, gamma i zoomie. Obejrzyj
co najmniej trzy rozpoznawalne fragmenty w różnych częściach klatki. Zapisz
XY oraz **lepiej / podobnie / gorzej / niejednoznacznie**, osobno dla fragmentów.
Opisz tearing i różnice góra–środek–dół; maska nie koryguje odkształceń
wewnątrz klatki. Odróżnij fragmenty użyte do estymacji od kontrolnych.

Wykonaj pełną rejestrację obu filmów kolejno z oznaczeniami wyłączonymi
i włączonymi; przed zastąpieniem wyniku zanotuj jego wygląd i XY. Zapisz,
które klatki miały maski — pozostałe korzystają z całego dostępnego obrazu.
Obejrzyj Play i dodatkowe podejrzane pary. Przy błędzie zapisz numer źródłowy
i przyczynę zamiast pomijać tę klatkę. Wyniki można odnieść dodatkowo do
dotychczasowego Deep Matcher, ale podstawowe porównanie wpływu maski zachowuje
ten sam algorytm NCC.

Próby robocze nadal pokazały duży dryf MOVIE_4. Nie zakładamy, że nowe maski
poprawią każdą parę lub cały film. Mniejsze płótno albo spokojniejszy ruch
nie zastępują oceny pokrycia rzeczywistych struktur. Werdykt należy zapisać
w [karcie REG-03](reviews/REG-03.md).

## Eksport i ponowny odczyt

1. Ponownie otwórz wzorzec, narysuj na wszystkich trzech klatkach „pomiń”
   `(0,0)–(80,12)` i wykonaj pełną rejestrację z maskami. Potwierdź skumulowane
   XY **(0,0), (−4,+3), (−7,+1)** i obecność zakłócającego pasa w aligned.
2. Kliknij **Zapisz MPP…**, wybierz **MPP aligned** i nową nazwę, np.
   `reg03-masked-aligned.mpp`. Zachowaj razem MPP oraz plik metadanych.
3. Przed zmianą serii kliknij **Zapisz AVI…**. Wybierz **aligned**, **Cała seria**,
   5 kl./s, **FFV1**, gamma **Neutralna (1)**, białe tło i wyłącz opisy.
   W VLC obejrzyj wszystkie trzy klatki: ma być widoczny cały obraz wraz
   z pasem wcześniej pominiętym w estymacji, bez zielonej/czerwonej nakładki.
4. Otwórz zapisany MPP wraz z metadanymi. Sprawdź 3 klatki, rozmiar aligned,
   pochodzenie, przesunięcia, nazwę metody i niezweryfikowaną pewność.
   Obejrzyj zakłócający pas we wszystkich klatkach. Nie wykonuj dodatkowej
   rejestracji przy tej kontroli. Edytowalne maski nie są odtwarzane z MPP.
5. Opcjonalnie zapisz także original: obrazy źródłowe i zakłócający pas mają
   pozostać identyczne wizualnie. Dokładną zgodność wartości MPP i zachowanie
   pikseli filmu FFV1 sprawdzają osobne testy automatyczne; oględziny GUI/VLC
   oceniają prezentację i nie zastępują porównania wartości liczbowych.

Maski wybierają dane do wyznaczenia XY. Wyłączone obszary nadal należą do
original, pełnego aligned i eksportowanych obrazów. Ewentualne nowe puste
marginesy wynikają z geometrii przesunięcia, a nie z prostokątów „pomiń”.
