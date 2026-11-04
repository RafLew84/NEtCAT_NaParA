# Fedkiw i level sets po próbie domen geometrycznych 17

Data: 2026-11-04. Pytanie dotyczy wykrywania przestrzennie spójnych domen
sieci molekuł na obrazach STM, z przypisaniem konkretnych molekuł do domeny.
Przyjmujemy, że „Fedkiw” oznacza Ronalda Fedkiwa i metody level-set, nie
bibliotekę `freud`. To ukierunkowany przegląd źródeł i rekomendacja próby,
bez nowej implementacji, instalacji, benchmarku ani zmiany listy ticketów.

**Późniejsza decyzja użytkownika — 2026-11-04:** próbę zapisano jako
[SD-V4-26](implementation/interactive-v04/26-compare-fedkiw-level-set.md)
na końcu planu, po 25. Audyt poniżej opisuje stan przed dopisaniem ticketu;
metoda nadal nie jest zaimplementowana.

## Odpowiedź i rekomendacja

**Tak: najbardziej uzasadnione jest sprawdzenie level set jako etapu
wyznaczania lub poprawiania granic na podstawie cech sieci.** Drugie
zastosowanie to pokrycie/wyspy. Nie ma obecnie dowodu, że dodanie samego
konturu poprawi detekcję naszych domen. Uzasadnienie i ograniczenia opisano
niżej; to wniosek dla projektu, nie wynik pomiaru nowej metody.

Wracamy do kierunku zapisanego już w
[przeglądzie z 2026-10-16](research-domain-detection-level-sets.md).
Nową informacją jest [wynik 17](implementation/interactive-v04/acceptance-17.md):
na regularnej kontroli bariery obrazu rozbiły 63 przypisane molekuły na
7 domen, a po zastąpieniu obrazu płaskim te same centra dały jedną domenę.
Próba skoku fazy nie przeszła. Dlatego warto oddzielić jakość sygnału granicy
od sposobu reprezentowania obrysu; zamiana grafu na level set nie usuwa
automatycznie błędnego sygnału wejściowego.

## Co rzeczywiście proponują źródła

**Osher–Fedkiw** opisują aparat powierzchni niejawnych i level sets;
książka zawiera osobny rozdział o aktywnych konturach i segmentacji.
Nie jest to pojedynczy gotowy detektor domen STM. Zweryfikowano stronę
wydawcy i spis treści, nie pełny tekst książki.
[Osher i Fedkiw, książka, 2003](https://link.springer.com/book/10.1007/b98879).

**Gibou–Fedkiw** przedstawiają hybrydę k-means i level set: inicjalizację
funkcją odległości ze znakiem, ewolucję według prędkości zależnej od danych
oraz okresową reinicjalizację i/lub regularyzację krzywizną. W §3 dopuszczają
prędkość opartą na teksturze i rozszerzenie wielokanałowe. Podstawowe
wyprowadzenie wykorzystuje dwa regiony; nie jest automatycznym odkrywaniem
nieznanej liczby klas struktur. Wartość `K` przy dyfuzji w §2.3 jest progiem
czułości na gradient, a nie liczbą klas. Deklaracji przyspieszenia z tej
pracy nie przenosimy na nasz program bez benchmarku.
[Pełny tekst autorów, §2–3](https://physbam.stanford.edu/papers/stanford2002-08.pdf).
Wykaz autora datuje raport na listopad 2002 i publikację konferencyjną na
2005 r. [Wykaz publikacji Fedkiwa](https://physbam.stanford.edu/).

**Wielokanałowy Chan–Vese** dopasowuje wspólny kontur do kilku kanałów
obrazu, z sumą błędów dopasowania i karą za długość granicy. Daje zatem
podstawę do użycia cech innych niż sama jasność. Dwa regiony modelu mogą
obejmować wiele rozłącznych obiektów; liczba klas modelu i liczba spójnych
domen są różnymi wielkościami.
[Chan, Sandberg i Vese, 2000, s. 130–133](https://www.math.ucla.edu/~lvese/PAPERS/JVCIR2000.pdf).

**Bezpośredni precedens STM:** Bui i współautorzy rozdzielają obraz na
składową gładką i teksturę. Pierwszą segmentują lokalnym wielofazowym
Chan–Vese, drugą przez energie empirycznych filtrów curvelet i grupowanie.
Demonstrują wyniki na monowarstwach cyjankowych na Au{111}; to inny materiał
niż nasze TTMAPP. Nie jest to walidacja hybrydy Gibou–Fedkiw na domenach
naszego projektu.
[Bui i in., 2018, abstrakt oraz §3–5](https://arxiv.org/html/1804.08890v1).
W §5 parametry różnią się między obrazami, a omówienie opiera się na
wynikach obrazowych. Przeczytane sekcje nie dostarczają nam niezależnej
oceny accuracy dla TTMAPP ani testu jego granic fazowych. Automatyczne
wyznaczenie liczby pasm widma w §4 nie jest równoznaczne z odkryciem liczby
domen; §4.4 nadal przewiduje osobny etap grupowania.
[Bui i in., §4.4–5](https://arxiv.org/html/1804.08890v1#S4.SS4).

## Gdzie to może pomóc w STM Domains

Poniższa tabela to **propozycje adaptacji**, nie potwierdzone skuteczności.

| Cel | Proponowane wejście do segmentacji | Ocena i główne ryzyko |
|---|---|---|
| Pokrycie materiałem i wyspy | Sygnał obrazu po przygotowaniu, ewentualnie mapa tekstury | Sensowna osobna próba; kontrast STM nie jest jednoznaczną maską materiału. |
| Granice domen orientacji | Kierunki, rozstaw, wsparcie/jakość pomiaru lub lokalne cechy tekstury | Najbardziej związane z zadaniem; trzeba oddzielić wpływ cech od regularyzacji granicy. |
| Rozdrobnione obrysy przy poprawnych wskazaniach wnętrza domen | Te same cechy i inicjalizacja z obecnych poprawnych przypisań | Może ograniczyć drobne fragmenty; może również usunąć małe domeny lub zamknąć rzeczywistą przerwę. |
| Granica przesunięcia sieci przy tym samym kącie i rozstawie | Sygnał niedopasowania położeń/fazy lub wiarygodne wskazanie granicy | Same kąty i rozstawy nie wystarczają. Level set może wykorzystać taki sygnał, ale go nie tworzy. |
| Odkrywanie nieznanej liczby klas | Oddzielna procedura wyboru/łączenia klas i jawne kryteria | Samo użycie level set nie zapewnia trybu „bez znanego K”. |

W proponowanej adaptacji kąta osiowego z 16 należy użyć np. pary
`(cos(2θ), sin(2θ))`, aby 179° i 1° nie tworzyły sztucznej dużej różnicy.
Dla innej symetrii potrzebny jest odpowiedni okres; nie zakładamy dowolnie
symetrii sześciokrotnej. Dwie rodziny kierunków trzeba dopasowywać wraz
z odpowiadającymi im rozstawami, jak w 17. Brak pomiaru powinien pozostać
brakiem danych, nie zerowym kątem ani dowodem fizycznej granicy.
To wymagania projektowe wynikające z interpretacji
[pomiaru 16](implementation/interactive-v04/geometry-method-v1.md)
i [metody 17](implementation/interactive-v04/experiment-17.md).

**Ograniczenie identyfikowalności:** jeśli przekazane pola cech mają te
same wartości po obu stronach granicy fazowej i nie zawierają sygnału
samej granicy, solver nie uzyska z nich informacji o jej położeniu.
Może narysować granicę wskutek inicjalizacji lub kary geometrycznej,
lecz nie będzie to dowód jej wykrycia. W otoczeniu rzeczywistej granicy
czasem występuje zaburzenie geometrii/tekstury — jego obecność i użyteczność
trzeba sprawdzić, a nie zakładać. Ten argument dotyczy wybranego opisu
danych, nie twierdzenia, że każdy algorytm obrazowy jest niewrażliwy na fazę.

## Czy jest już w kodzie lub planie?

Audyt bieżącego worktree i gałęzi `domains/interactive-v04-ui`, baza
`a5229e4` (potwierdzony odbiór ręczny SD-V4-17). Rozróżniamy aktywne
UI, historyczne prototypy oraz zapisane możliwości dalszych badań.

| Miejsce | Stan potwierdzony w repozytorium |
|---|---|
| Obecna metoda bazowa aplikacji | Grupowanie na grafie, zgodność cech, bariery i maska regionów; nie level set. [Segmentacja](../../stmdomains/analysis/segmentation.py). |
| Obecny SD-V4-17 | Pomiary dwóch kierunków i rozstawów, progi jakości/wsparcia, zgodność całego regionu. Nie używa Gibou–Fedkiwa. [Obliczenia](../../stmdomains/analysis/geometry_domains.py), [łączenie regionów](../../stmdomains/analysis/geometry_regions.py). |
| Wypełnione obszary i obrysy w UI | Maska Voronoia o ograniczonym zasięgu, z barierami i kontrolą spójności; sam fakt rysowania całych domen nie oznacza aktywnych konturów. [Wspólna rasteryzacja](../../stmdomains/analysis/domain_raster.py). |
| Wcześniejsze badania | Level set i Gibou–Fedkiw były opisane w [notatce z 16 października](research-domain-detection-level-sets.md). [Dawny pilotaż pokrycia](coverage-and-scale-pilot.md) oraz [porównanie metod](method-comparison-pilot.md) używały morfologicznego Chan–Vese; oba jawnie wykluczają interpretację jako wykonany test Gibou–Fedkiwa. |
| Historyczna mapa badań | [Dawne issue 10](issues/10-coverage-and-scale.md) dopuszczało rzeczywistą implementację Gibou–Fedkiwa jako przyszłą próbę; [dawne issue 17](issues/17-image-texture-domains.md) rozważało level set po uzyskaniu wiarygodnych cech. To nie są tickety SD-V4-10/17 obecnej aplikacji. |
| Aktualny plan UI | Nie ma osobnego ticketu wdrażającego level set. [SD-V4-18](implementation/interactive-v04/18-compare-freud-environments.md) to `freud.EnvironmentCluster` (`ready-for-agent`); [SD-V4-19](implementation/interactive-v04/19-compare-local-fft-nmf.md) to lokalne FFT/NMF (`deferred`), bez takiej integracji. [Pełna lista](implementation/interactive-v04/README.md#tickety-i-kolejność). |

Przeszukano kod Python `stmdomains/` oraz dokumentację po nazwach Fedkiw,
Gibou, level set, Chan–Vese, active contour i odpowiadających im nazwach
funkcji; sprawdzono także faktyczny przebieg segmentacji i tworzenia masek.
Nie wykonywano dawnych prototypów ponownie. Brak modułu potwierdzamy dla
tej wersji aplikacji, nie dla wszystkich historycznych gałęzi repozytorium.

**freud i Fedkiw to różne kierunki.** `EnvironmentCluster` porównuje lokalne
otoczenia punktów; nie jest implementacją metody aktywnych konturów Fedkiwa.
[Dokumentacja autorów freud](https://freud.readthedocs.io/en/stable/modules/environment.html#freud.environment.EnvironmentCluster).

## Mała próba, która rozstrzygnie przydatność

Rekomendujemy jedną próbę **„te same cechy, inny sposób budowania granic”**.
Nie potrzeba do niej trenować sieci neuronowej. W chwili przeglądu była
propozycją do osobnego wyboru; późniejszą decyzję i ticket 26 podano wyżej.
Porównanie obecnego grafu z level set przy tych samych cechach zmienia też
kryterium podziału i regularyzację, więc ocenia dwa przebiegi analizy.
Nie izoluje samego solvera. Do twierdzenia o korzyści z solvera lub szybkości
Gibou–Fedkiw należałoby utrzymać również tę samą funkcję celu i warunki
zatrzymania.

1. Użyć istniejących kontroli i TTMAPP259–266. Wybrać jedną mapę cech,
   przygotowanie obrazu, inicjalizację i maskę poprawnego pola; zachować je
   identycznie w obu porównywanych wariantach. Jeśli mapy są zbyt rzadkie,
   zgłosić brak wsparcia zamiast bezwarunkowo wypełniać przestrzeń między nimi.
2. Porównać dotychczasowy podział z jednym wariantem aktywnego konturu
   na tych cechach. Oddzielny Chan–Vese na jasności może być kontrolą
   pokazującą, czy wynik śledzi kontrast zamiast domen sieci.
3. Z góry wybrać mały zestaw sił regularyzacji i limit iteracji.
   Zapisać skalę przestrzenną, sposób inicjalizacji i wynik anulowania.
   Nie dopasowywać kolejnych wariantów aż do uzyskania atrakcyjnego obrazka.
4. Obowiązkowo ocenić jedną sieć, różne orientacje, skok fazy, brakujące
   centra, rzeczywistą lukę, małą domenę i artefakt skanu. Sygnały odmowy
   pozostają widoczne. Poprawne scalenie fragmentów jednej domeny nie może
   zasłaniać błędnego sklejenia dwóch rzeczywistych domen.
5. Na kontrolach liczyć błędne scalenia, podziały i pominięcia. Na TTMAPP
   bez ręcznej referencji raportować tylko opis porównania i przypisania.
   Przy referencji oceniać też błąd granic z ustaloną tolerancją; jednostki
   fizyczne stosować dopiero przy wiarygodnej kalibracji. Udział przypisań
   i wygląd maski nie zastępują poprawności.
6. Zakończyć decyzją opartą na ograniczeniach: czy lepiej lokalizuje granice,
   zachowuje małe domeny i luki, oraz ile kosztuje obliczeniowo. Brak poprawy
   lub pogorszenie jest poprawnym wynikiem próby.

Jednostką niezależności dla późniejszej oceny przenoszalności powinna być
akwizycja, nie pojedynczy piksel ani sąsiednia klatka. Obecna seria pozwala
na pilotaż w jej obrębie, bez dowodu działania na innych molekułach/podłożach.
Klatki 259–266 były już oglądane i używane w kolejnych próbach, więc nie są
nowym, nietkniętym zbiorem testowym.
To ograniczenie oceny projektu, opisane również w
[wcześniejszym przeglądzie](research-domain-detection-level-sets.md#minimalny-eksperyment-przed-decyzją).

## Zakres dowodów i źródła proceduralne

Sprawdzono źródła pierwotne: pełny PDF Gibou–Fedkiw, stronę autora z datowaniem,
stronę wydawcy książki Osher–Fedkiw, artykuł Chan–Sandberg–Vese oraz pełny
tekst Bui i in. Dostęp do filmu pod linkiem emload nie był dostępny przez
narzędzie WWW; nie przypisujemy mu zawartości ani nie wykorzystujemy go
jako źródła metodologicznego. Nie wykonywano nowego eksperymentu detekcji.

Ocena rozdziela wykonalność algorytmiczną, dowód z innych obrazów STM oraz
niezweryfikowaną skuteczność na naszym materiale. Nie stosujemy klinicznych
skal GRADE/RoB jako punktowej oceny algorytmów segmentacji.

Przy przygotowaniu oceny użyto procedury `scientific-critical-thinking`
z Scientific Agent Skills: Timothy Kassis, Vinayak Agarwal, Yuhuan He,
Darshil Patel i Aubrey M. Brueckner (2026), *Scientific Agent Skills:
A Library of Procedural Knowledge for Research Agents*.
[Rekord arXiv i bieżąca wersja](https://arxiv.org/abs/2609.00065),
[DOI](https://doi.org/10.48550/arXiv.2609.00065).
Jest to źródło sposobu prowadzenia oceny, nie dowód skuteczności metod STM.
