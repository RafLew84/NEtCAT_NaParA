# STM Viewer — instrukcja obsługi

Program służy do przeglądania obrazów STM, wyrównywania kolejnych klatek
i zapisywania wyników. **Rejestracja** oznacza tu wyznaczenie przesunięcia
obrazów, aby rozpoznawalne struktury pozostawały w podobnym miejscu filmu.

Jeżeli program nie jest jeszcze zainstalowany, zacznij od
[instrukcji instalacji](installation.md). Ta instrukcja opisuje dostępne
funkcje, włącznie z edytorem parametrów AKAZE i LightGlue.

## Pierwszy film w pięciu krokach

1. Kliknij **Otwórz STP/S94/MPP…** i wybierz swój MPP.
2. Obejrzyj kilka klatek przez **Play/Pause** i miniatury na dole.
3. Wybierz metodę **Phase**, a następnie **Rejestruj**.
4. Obejrzyj `aligned` i porównaj z `original`.
5. Zapisz **sesję**, aby zachować pracę. MPP i AVI zapisuj jako dodatkowe
   wyniki, zależnie od ich przeznaczenia.

Phase jest wygodną próbą uruchomienia. Na trudnych filmach porównaj
inne metody; jeden algorytm nie jest najlepszy dla wszystkich danych.

## 1. Wczytywanie danych

**Otwórz STP/S94/MPP…** lub **Ctrl+O** otwiera wybór danych.

| Co wybierasz | Jak zaznaczyć | Co dostaniesz |
| --- | --- | --- |
| Jeden MPP | Jeden plik | Wszystkie zawarte w nim klatki, w zapisanej kolejności |
| STP lub S94 | Jeden albo wiele plików; Ctrl/Shift w oknie wyboru | Serię obrazów, sortowaną naturalnie po nazwach, np. 2 przed 10 |
| Sesja `.stmsession` | Osobny przycisk **Otwórz sesję…** | Obrazy i zapisany stan pracy |

MPP otwieraj pojedynczo. Import wielu obrazów wymaga jednakowych wymiarów
w pikselach. Nie wykonuje automatycznego skalowania. Gdy nowego zestawu nie
uda się otworzyć, wcześniejszy pozostaje. Poprawny import zastępuje bieżącą
serię — przed zmianą filmu zapisz sesję, jeśli chcesz do niej wrócić.

Jeżeli obok MPP jest plik `.mpp.stmviewer.json`, zostaw oba razem.
Zawiera dodatkowe informacje potrzebne do pełnego odczytu historii
i obszarów bez pomiaru.

## 2. Poruszanie się po filmie

Na dole są miniatury, numer klatki oraz **← Poprzednia** / **Następna →**.
Kliknięcie miniatury lub zmiana numeru wybiera jedną klatkę.

- **Play** rozpoczyna odtwarzanie, **Pause** je zatrzymuje.
- Tempo wynosi domyślnie 5 kl./s; można wybrać 1–30.
- **Pętla** powtarza film. Bez niej odtwarzanie zatrzymuje się na końcu.
- Kliknięcie Play na ostatniej klatce zaczyna film od pierwszej.
- Ręczny wybór klatki zatrzymuje odtwarzanie.
- **Usuń klatkę** usuwa ją z bieżącej pracy, nie z pliku źródłowego.
  Po usunięciu zobaczysz następną, a przy końcu serii poprzednią.

Numer bieżący i numer źródłowy mogą się różnić. Po usunięciu dwóch
początkowych klatek dawna klatka 3 ma bieżący numer 1.
Pochodzenie nadal można odczytać w lewym panelu.

## 3. Powiększenie, przesuwanie i jasność

Kółko myszy powiększa i pomniejsza obraz. Przytrzymaj lewy przycisk myszy
na obrazie i przeciągnij, aby przesunąć widok. Przeciąganie zachowuje
powiększenie. Przyciski **+** i **−** także zmieniają zoom.

**Dopasuj** pokazuje cały obraz w oknie. Nie zmienia liczby pikseli
pomiaru ani nie wykonuje rejestracji. Przy przechodzeniu między klatkami
zoom zostaje; `original` i `aligned` mają osobno zapamiętany widok.

**Gamma** rozjaśnia lub przyciemnia podgląd. **Reset gamma** przywraca 1.
Nie zmienia wartości pomiarowych ani ustawień algorytmu rejestracji.
Przy AVI można wybrać gamma podglądu albo neutralną.

**Proporcje pikselowe** pomijają skalę fizyczną z nagłówka przy wyświetlaniu.
Użyj tej opcji, jeśli skala jest nieznana lub zastępcza. Nie poprawia ona
metadanych i nie wyznacza rzeczywistej kalibracji.

## 4. Rejestracja całego filmu

1. Usuń niepotrzebne klatki **przed** obliczeniem.
2. Wybierz metodę w lewym panelu.
3. Przy modelach sprawdź automatycznie uzupełnione ścieżki (lub wskaż pliki)
   i wybierz urządzenie; możesz najpierw użyć
   **Sprawdź model**. Przy metodach podstawowych ten krok nie jest potrzebny.
4. Kliknij **Rejestruj**.
5. Poczekaj na zakończenie. Przycisk **Anuluj rejestrację** przerywa zadanie;
   wcześniejszy kompletny wynik pozostaje.
6. Po sukcesie program pokazuje `aligned`. Obejrzyj film i przejścia,
   przy których struktury nadal skaczą.

Rejestracja w głównym oknie dopasowuje 2→1, 3→2 itd. i sumuje przesunięcia
względem pierwszej klatki. Aktualnie oglądana klatka nie wybiera odniesienia.
Ponowne obliczenie korzysta z wejściowych obrazów bieżącej serii.

`original` to dane wczytane do tej pracy, a `aligned` to aktualny wynik.
Aby zmieścić przesuwane obrazy, program powiększa wspólny obszar.
Nie zmniejsza przez to oryginalnych obrazów. Dopasowanie całego obszaru
do ekranu może jednak sprawiać wrażenie oddalenia. Przesunięcia ułamkowe
wymagają interpolacji; przy ostrych krawędziach mogą być widoczne
wartości pośrednie.

Puste brzegi nie są nowym pomiarem. Żółty obrys pomaga odnaleźć zakres
oryginalnej klatki. Brakujące obszary są prezentowane na jasnym tle;
eksport AVI pozwala wybrać jego kolor.

### Którą metodę wybrać

| Grupa | Dostępne metody | Zastosowanie w pracy |
| --- | --- | --- |
| Bez modeli i wag | Phase, korelacja bez normalizacji, Tile+RANSAC, ECC, Optical Flow, AKAZE | Porównanie różnych sposobów estymacji; działają na CPU |
| Z modelem | Deep Matcher, EfficientLoFTR, RoMa v2, MatchAnything-ELoFTR, LightGlue + SuperPoint | Dopasowania rozpoznawalnych elementów; wymagają przygotowania modelu |
| Warianty Deep | Deep Matcher + ECC, Deep Matcher + lokalne fragmenty | Dodatkowe doprecyzowanie lub ocena zgodności po Deep |

Wszystkie te metody dostarczają pojedyncze przesunięcie X/Y na parę.
Nie usuwają dowolnych deformacji wewnątrz klatki ani tearingu.
Wcześniejsze obserwacje użytkownika na trudnych filmach wskazywały dobre wyniki
Deep outdoor i RoMa, ale nie stanowi to gwarancji dla nowego pomiaru.

Wynik oznaczony jako niepewny wymaga obejrzenia.
Komunikat o zbyt małej liczbie zgodnych wektorów oznacza brak dostatecznego
poparcia dla przesunięcia przy tych ustawieniach, niekoniecznie błąd instalacji.

## 5. Parametry AKAZE i LightGlue

Otwórz **Rejestracja → Parametry metod…**. Małe okno może pozostać obok filmu.

- Wybór metody w tym oknie zmienia **formularz do edycji**. Metodę obliczeń
  nadal wybierasz osobno w oknie głównym, parze albo grafie.
- **OK** zatwierdza zmiany; **Anuluj** lub krzyżyk je odrzucają.
- **Przywróć domyślne** dotyczy wyłącznie obecnie widocznej metody.
- Zatwierdzone ustawienia dotyczą następnego obliczenia. Gotowy aligned
  i wcześniejsze wyniki nie są automatycznie przeliczane.
- Obie konfiguracje są zapisywane w sesji.

| Ustawienie | Jak rozumieć zmianę |
| --- | --- |
| Próg detektora AKAZE / SuperPoint | Mniejszy dopuszcza więcej punktów, również z zakłóceń |
| Próg dopasowań LightGlue | Mniejszy dopuszcza więcej korespondencji, również błędnych |
| Maksymalna liczba punktów | Większa może zwiększyć czas i zużycie pamięci |
| Tolerancja zgodności | Dopuszczalna różnica wektorów w parze, w pikselach original |
| Percentyle | Ograniczenie wpływu skrajnie jasnych i ciemnych próbek |
| CLAHE | Wzmocnienie lokalnego kontrastu; może wzmacniać też szum |
| Pełne obliczenia LightGlue | Wyłączenie wczesnego zakończenia i redukcji punktów |

Zmieniaj jedno ustawienie naraz i oceniaj tę samą parę.
Więcej znalezionych punktów nie oznacza automatycznie dokładniejszego
wyrównania. Przygotowanie kontrastu zmienia tylko wejście algorytmu;
nie zastępuje obrazów pomiarowych.

Obecnie edytor obejmuje te dwie metody. Rozszerzenie na pozostałe jest
zaplanowane, ale nie jest jeszcze dostępne w tym oknie.

## 6. Obejrzenie i ręczna poprawa pary

Wybierz drugą klatkę problematycznej pary, np. 30 dla 29→30,
i kliknij **Porównaj parę…**. Porównuj nakładkę 50/50 albo przełączaj
klatkę bazową i przesuwaną. Zoom i gamma pomagają ocenić tę samą strukturę.

Jeżeli chcesz poprawić **gotowy film**:

1. Najpierw musi istnieć kompletne dopasowanie całej serii.
2. W sekcji **Korekta całego filmu** kliknij **Popraw dopasowanie z filmu**.
3. Przesuń klatkę strzałkami o ±1 piksel w X/Y.
4. Kliknij **Zakończ korektę** — to kończy edycję próby, ale jeszcze nie filmu.
5. Kliknij **Zastosuj do filmu** — dopiero ten krok zmienia aligned i eksport.
6. Sprawdź również dalsze klatki i zapisz sesję.

Poprawienie pary 1→2 przesuwa klatkę 2 **oraz wszystkie następne**.
Zachowuje to ich wzajemne ustawienie. **Usuń korektę tej pary z filmu**
cofa zastosowaną poprawkę tej pary.

**Zachowaj do porównania** przechowuje wariant pary obok nowej próby.
Nie zapisuje filmu na dysk i nie stosuje przesunięcia do całej serii.

Po usunięciu klatki gotowy aligned pozostałych obrazów pozostaje dostępny,
ale dalsza korekta filmu może wymagać nowej pełnej rejestracji.
Udana nowa rejestracja zastępuje wcześniejsze ręczne poprawki;
warto wcześniej zapisać sesję.

## 7. Dopasowanie wieloklatkowe

Ten tryb bierze pod uwagę relacje z kilkoma wcześniejszymi klatkami,
zamiast sumować wyłącznie kolejne pary.

1. Kliknij **Dopasowanie wieloklatkowe…**.
2. Wybierz metodę dopasowania par i okno do 3 lub do 5 poprzednich klatek.
   Sprawdź wybór metody w tym oknie — nie zakładaj, że jest taki sam
   jak w głównym panelu.
3. Kliknij **Oblicz kandydata grafu**.
4. Obejrzyj wynik LS i, jeśli chcesz, oblicz wariant Hubera.
5. W grupie **Aktywny film** wybierz kompletny wynik.
6. Kliknij **Zastosuj wynik do filmu**, aby stał się aligned w głównym oknie.
7. Zapisz sesję.

**LS** znajduje wspólne położenia klatek z pomiarów par.
**Huber** ogranicza wpływ relacji, które mocno odstają od wspólnego wyniku.
Próg Hubera nie jest tolerancją detektora: reguluje wpływ rozbieżności
w grafie. Limit iteracji określa maksymalną liczbę kroków obliczenia.
Większy limit nie gwarantuje lepszego dopasowania ani zbieżności.

Samo obliczenie kandydata nie zmienia filmu głównego.
Przy rozłącznym grafie lub nieukończonym Huberze **Zastosuj wynik do filmu**
pozostaje nieaktywne; przeczytaj informację o kompletności i powodzie odmowy.
Możesz wybrać inny kompletny wariant albo wykonać nowe obliczenie.

Ponowne liczenie Hubera korzysta z już zmierzonych par. Po zmianie parametrów
algorytmu wykonaj **nowe obliczenie grafu**, jeśli chcesz ponownie dopasować
obrazy. Tryb wieloklatkowy nie jest ograniczony do Deep Matchera.

**Przywróć zachowany wynik** pozwala wrócić do poprzedniego zastosowanego
filmu. Zachowywany jest jeden poprzednik, nie pełna historia wszystkich prób.

## 8. Co i kiedy zapisać

| Cel | Wybierz | Co zostaje zachowane |
| --- | --- | --- |
| Kontynuowanie pracy jutro lub na innym komputerze | **Zapisz sesję…** | Samodzielny `.stmsession`: obrazy, stan pracy, wyrównanie, korekty, kandydaci i ustawienia |
| Dane obrazowe do dalszej analizy | **Zapisz MPP…** | Wybrana wersja całej pozostałej serii oraz towarzyszące metadane |
| Film do oglądania/prezentacji | **Plik → Zapisz AVI…** | Wyrenderowany obraz z wybranym tempem i wyglądem |

### Sesja

Użyj **Zapisz sesję…** lub **Ctrl+Shift+S**.
**Otwórz sesję…** / **Ctrl+Shift+O** wznawia pracę z tego pliku.
Obrazy są wewnątrz sesji — nie trzeba szukać oryginalnych plików MPP/STP/S94.

Sesja nie zawiera środowiska Python ani plików modeli.
Na innym komputerze można obejrzeć gotowe wyniki bez modelu;
do ponownego obliczenia trzeba udostępnić jego pliki i poprawić ścieżki.

### MPP

Kliknij **Zapisz MPP…** lub **Ctrl+S**.
W polu **Typ pliku** wybierz **MPP original** albo **MPP aligned**.
Eksport obejmuje wszystkie pozostałe klatki, nie tylko aktualnie oglądaną.

Przenoś razem `wynik.mpp` i `wynik.mpp.stmviewer.json`.
Gamma oraz zoom podglądu nie zmieniają pomiarów w tym zapisie.
Aligned zawiera już interpolowane dane; białe wypełnienie braków jest
odtwarzane jako brak pomiaru dzięki dodatkowym metadanym.

Po ponownym otwarciu aligned MPP program może nazywać ten widok `original`:
to piksele wejściowe nowej pracy. Plik nie zawiera wcześniejszych oryginałów
sprzed wyrównania. Do kontynuacji z oryginałami użyj **sesji**.
Niektóre zapisane aligned mają brakujące próbki i nie nadają się
do ponownej rejestracji obecnymi metodami.

### AVI

Wybierz wersję `original` lub `aligned`, całą serię albo zakres,
tempo 1–30 kl./s, gamma i kontrast. Możesz dodać podziałkę, numer klatki
oraz dostępny czas pomiaru, a dla braków wybrać tło czarne, szare lub białe.

**MJPG** to kompresja stratna. **FFV1** zachowuje piksele wyrenderowanego filmu,
ale nie zastępuje MPP z wartościami pomiarowymi. AVI obejmuje pełny obraz;
zoom na ekranie nie wybiera kadru eksportu. FPS filmu nie zmienia czasów
pomiarów. Podziałka używa kalibracji danych; przy jej braku/proporcjach
pikselowych pokazuje piksele.

## 9. Gdy wynik nie wygląda dobrze

Najpierw sprawdź nakładkę trudnej pary, nie tylko płynność odtwarzania.
Algorytm może dopasować pasy zakłóceń zamiast struktury próbki.

Spróbuj innej metody, kontrolowanej zmiany jednego parametru, dopasowania
wieloklatkowego lub ręcznej korekty. Porównuj w podobnym zoomie i przy tych
samych klatkach. Zapamiętaj, czy numeracja jest przed czy po usunięciu klatek.

Przesunięcie X/Y nie naprawi każdego rozciągnięcia, uskoku linii czy
zmieniającego się kontrastu STM. Zapis sesji pozwala wrócić do wcześniejszego
wariantu bez ponownego liczenia.
