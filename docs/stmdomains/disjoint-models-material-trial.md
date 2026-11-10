# Jeden wspólny model czy dwa rozłączne — osobno obecność materiału

Data: **2026-10-28**. Zlecona kontynuacja issue **19**.
**19 pozostaje `claimed`, do omówienia; 20 nadal odłożone.**
[Manifest](disjoint-models-material-manifest.json).

**Wynik:** porównanie dwóch modeli na rozłącznych otoczeniach naprawia prostą
kontrolę granicy przesunięcia 3 px przy próbkowaniu w centrach molekuł.
Odrzuca wszystkie **138/138** połączeń przez granicę, zachowując **89.5%**
przypisanych molekuł i dwa fragmenty w każdej z trzech realizacji. Poprzedni
test fazy pozostawiał 6 połączeń i jeden fragment. Na siatce nadal zostają
po dwa niepewne mostki na obraz; poprawa nie jest niezależna od próbkowania.

Osobna informacja z obrazu odróżnia czystą przerwę 36 px od pasa z samymi
brakami oznaczeń. Nadal zawodzi dla węższej przerwy, lokalnego szumu i słabego
materiału. **TTMAPP nie poprawiono:** żadne porównanie obu stron nie osiąga
ustalonego progu jakości. To ograniczenie metody/kalibracji, nie dowód
braku domen. Nie wybrano rozwiązania do programu.

[Interaktywny podgląd](../../.scratch/disjoint-models-material/index.html)
ma 42 obrazy, wszystkie 96 ustawień, pięć scenariuszy oraz wybór połączenia.
Pokazuje rozłączne strony i bloki dopasowania/oceny, zysk dwóch modeli,
jakość obu stron i oddzielne podparcie sygnałem/oznaczeniami.
[Pełne CSV](../../.scratch/disjoint-models-material/controls.csv),
[CSV podparcia](../../.scratch/disjoint-models-material/material.csv),
[wykres PNG](../../.scratch/disjoint-models-material/comparison.png),
[PDF](../../.scratch/disjoint-models-material/comparison.pdf).

## Wejście i niezależność referencji

- **261 pełnych obrazów:** poprzednie 210 oraz **51 nowych kontroli**
  (17 przypadków × ziarna 8101–8103). W tym 24 TTMAPP; 18 ma częściowe referencje,
  6 pozostaje do oglądania. Nie uruchamiano pełnych 268 klatek.
- Kalibracja: 45 wcześniejszych negatywów dla jakości obu stron i 33 znane
  jednorodne kontrole dla fałszywych rozcięć. Wybrano je według jawnego
  generatora, bez odczytu masek. Progi ustalono przed generowaniem nowych kontroli.
- Nowe przypadki: jitter .6 px jednej sieci, lekkie odkształcenie, skoki 1/3/6 px,
  skok 3 px ukośnie i blisko brzegu, skok 3 px z jitterem lub brakami 30%
  oznaczeń, przerwy 36/18 px, pas samych braków oznaczeń, ciemny materiał,
  zaszumiona pusta przerwa, niezależne rzędy, losowe punkty, odwrócenie kontrastu.
  Obrazy 192×192, okres 12 px. W stałych geometriach ziarna zmieniają szum,
  a nie tworzą trzech niezależnych struktur. Kontrole nie są walidacją STM.
- Zamrożono **25056 wyników** (261×96); oceniono 24480 z 255 obrazów.
  Referencje czytane dopiero po zapisie predykcji. TTMAPP oceniamy we wnętrzach
  częściowych oznaczeń: 1678 molekuł i 1916 miejsc siatki. Poza nimi obszar
  jest nieznany. Nie trenowano modelu na domenach, nie podano ich liczby lub klas.

## Co jest stałe, a co porównujemy

Pozostawiono trzy wcześniejsze oceny porządku r48: zgodność centrów
(`baseline`), miękkie dopasowanie stałej sieci (`fixed2`) i korygowanej
(`refined2`), skala oceny 2 px. Sąsiedztwo i minimum fragmentu pozostały
niezmienione: 4 miejsca siatki albo 8 centrów. **Nowy test krawędzi nie może
odzyskać miejsc odrzuconych wcześniej przez ocenę porządku.**

Dla pary sąsiadów próbujemy trzy kierunki normalnej: −45°, 0°, +45° względem
połączenia. Linia przechodzi przez jego środek; badamy koło o promieniu 48 px,
z wykluczeniem pasa ±2 px. Nie dopasowujemy linii do referencji. Każda próba
musi rozdzielać oba końce połączenia. Jest to ograniczona dyskretyzacja kierunków
i położenia granicy, nie pełne przeszukanie wszystkich możliwych konturów.

Każdą stronę dzielimy wzdłuż stycznej na dwa ciągłe bloki punktów; wymagane
minimum to 6 centrów do dopasowania i 6 do oceny po każdej stronie. Bloki
zamieniają się rolami. **Także propozycje baz pochodzą tylko z części uczącej**,
inaczej niż warunkowy podział punktów w poprzedniej próbie.

Model wspólny próbuje bazy zaproponowane przez sumę części uczących oraz
przez każdą stronę; wybór opiera się tylko na błędzie uczącym. Każdy model
osobny dostaje własną propozycję. Zachowano wcześniejsze: histogram przesunięć
6–24 px, kanoniczną bazę, pięć iteracji Hubera ze skalą 2 px i ograniczenie
korekty afinicznej do .15. Nadal jest to lokalny model jednej sieci Bravaisa,
a nie dowolnego wielomolekularnego motywu.

Zysk dwóch modeli to spadek średniej odległości kwadratowej do przewidywanych
węzłów na punktach oceny, z ograniczeniem straty do 16 px². Strony mają równe
wagi; bierzemy gorszy zysk z dwóch zamian bloków. Jakość jest minimum średniej
`exp(-d²/8)` z czterech ocen stron/bloków. Nie jest to wynik dopasowania na
tych samych punktach ani formalny test statystyczny z gwarantowanym poziomem błędu.

Progi ustalone przed nowymi kontrolami:

| Warunek | Próg | Dane kalibracji |
| --- | ---: | --- |
| Jakość obu stron | **> .96688317** | q.99 z 60182 dostępnych prób kierunku na 45 negatywach |
| Zysk dwóch modeli | **> .1 px²** | maksimum z .1 i q.99 najlepszych kwalifikowanych kierunków; 22402 krawędzie z 33 jednorodnych kontroli |

W kalibracji nie wskazano granicy na żadnej z 22402 kwalifikowanych krawędzi
jednorodnych kontroli. Z 41850 krawędzi negatywów 600 kwalifikuje jakość;
486 z nich wskazuje przewagę dwóch modeli. To nie jest samodzielne
rozpoznanie domen: przypadkowe lokalne porządki nadal mogą dawać takie dopasowanie.

Porównano: samo sąsiedztwo, wcześniejszą fazę, dwa modele z zachowaniem
niepewnych połączeń oraz dwa modele z ich usuwaniem. Brak kwalifikowanej
próby jest **brakiem dowodu**, a nie potwierdzoną zgodnością lub granicą.
Zachowane niepewne połączenia również nie dowodzą istnienia jednej domeny.

## Osobna informacja o materiale

Warunek sprawdzamy w miejscach analizy oraz wzdłuż połączeń co najwyżej co 3 px.
Dostępne warianty: brak dodatkowego warunku, oznaczenia, sygnał, oznaczenia
lub sygnał. Każdy punkt odcinka musi mieć wybrane podparcie.

- Oznaczenia: odległość do rzeczywistego centrum ≤12 px. Przewidywane węzły
  dopasowanej sieci **nie są dowodem materiału**.
- Sygnał: RMS w promieniu 12 px z różnicy rozmyć Gaussa σ=.8 i 3 px, przy
  podparciu pomiarem ≥.5. Dzielimy przez globalną ocenę szumu z mediany
  odchyleń mieszanej różnicy sąsiednich pikseli (`MAD/(2×.67448975)`).
  Wymagany iloraz ≥1; parametr ustalony wcześniej, bez dostrajania do ramek.

To prosta ocena lokalnego sygnału, **nie gotowa maska pokrycia**. Słaby sygnał
nie rozstrzyga pomiędzy pustym podłożem, ciemną warstwą i słabym obrazem.
Szum lokalnie silniejszy od globalnej estymaty może dać fałszywe podparcie.

## Wyniki granic

Nowe kontrole, centra molekuł, `refined2`, bez dodatkowego warunku materiału:

| Przypadek | Zachowaj brak dowodu: przypisania / wynik | Usuń brak dowodu: przypisania / wynik |
| --- | --- | --- |
| Prosta granica 3 px | **89.5%; 2 fragmenty**, zero scaleń, wszystkie 138 połączeń przez granicę odrzucone | 52.0%; 2 fragmenty, znacznie mniej przypisań |
| Granica ukośna 3 px | 88.0%; nadal scalona, pozostaje 30/36 połączeń między znanymi wnętrzami | 54.0%; 2 fragmenty przez szerokie odrzucanie niepewności |
| Granica 3 px blisko brzegu | 86.3%; 2 fragmenty | 58.6%; **zostaje jeden fragment**, nie oceniaj tego jako poprawnego rozdzielenia |
| Granica 3 px, brak 30% centrów | 70.8%; 94.6% ocenianych par różnych domen nadal scalone | 21.4%; 3, 1 i 2 fragmenty, duża utrata wyniku |
| Pojedyncza sieć, jitter .6 px | 75.2%; jedna domena jak wcześniej | **0%; całość odrzucona** |
| Pojedyncza sieć, małe odkształcenie | 92.5%; jeden fragment | 92.5%; jeden fragment |

Przy prostej granicy 3 px poprawa dotyczy centrów: na regularnej siatce
pozostają dwa niepewne połączenia na obraz i wynik jest scalony. Przy ukośnej
granicy oraz brakujących oznaczeniach pozostałe połączenia przez rzeczywistą
linię należą do stanu niepewnego. Kierunek/propozycja modelu, liczba punktów
oraz wymaganie bardzo wysokiej jakości ograniczają metodę.

Skok 1 px nadal pozostaje scalony. Audyt pełnej linii, także w wyłączonym
pasie oceny, pokazuje po 25 zachowanych połączeń centrów na obraz: mają
kwalifikowane dopasowanie, lecz zysk nie przekracza progu. Skok 6 px był
rozdzielony już przez wcześniejszą odmowę porządku przy styku; nie przypisujemy
tego sukcesu nowemu testowi. Metryka bezpośrednich połączeń między znanymi
wnętrzami nie obejmuje wszystkich dróg przez nieoznaczony pas — dlatego
raportujemy także końcowe scalenia i `raw-boundary-audit.json`.

## Wyniki podparcia materiału

Siatka, `refined2`, porównanie modeli z zachowaniem braku dowodu:

| Kontrola | Bez podparcia | Tylko oznaczenia | Tylko sygnał | Oznaczenia lub sygnał |
| --- | --- | --- | --- | --- |
| Czysta przerwa 36 px | 96/96 fałszywych miejsc, płaty scalone | **0/96, dwa płaty** | **0/96, dwa płaty** | **0/96, dwa płaty** |
| Przerwa 18 px | 48/48, scalone | 48/48, scalone | 48/48, scalone | 48/48, scalone |
| Pas brakujących oznaczeń, pełny obraz | jeden fragment | **błędnie dwa** | **jeden fragment** | **jeden fragment** |
| Ciemny pas rzeczywistego materiału | jeden fragment, 91.0% przypisań | jeden, 91.0% | **błędnie dwa, 77.3%** | jeden, 91.0% |
| Silny szum w pustej przerwie 36 px | 96/96, scalone | **0/96, dwa płaty** | **96/96, scalone** | **96/96, scalone** |

Rozróżnienie przerwy i samych braków oznaczeń jest rzeczywistą korzyścią:
kontrole mają te same centra po usunięciu środkowego pasa, lecz inny obraz.
Samo zwiększenie promienia szukania centrów tego nie rozstrzyga. Jednocześnie
wariant „oznaczenia lub sygnał” nie rozwiązuje lokalnie zaszumionego podłoża.
Brakuje niezależnego, lokalnego rozpoznania szumu i wiarygodności sygnału.

Na niezależnych rzędach pozostaje 36/768 fałszywych miejsc siatki dla omawianych
wariantów; losowe punkty dają 0/768. Odwrócenie kontrastu połowy obrazu nie
rozszczepia poprawnej sieci. To wyniki tych kontroli, nie ogólna walidacja materiału.

## TTMAPP: rozdzielenie przyczyn odmowy

W 24 pełnych klatkach, dla poprzedniej geometrycznej oceny porządku na siatce:
**987** dopuszczonych krawędzi, **931** z dostępnym porównaniem, **0**
kwalifikowanych jakościowo. Mediana najlepszej jakości kierunku .680,
maksimum .916, wobec progu .967. Zatem podstawowym problemem nie jest tu
sam brak liczby punktów. Także pozostałe oceny porządku i próbkowanie w
centrach nie dają kwalifikowanej krawędzi.

W znanych wnętrzach 18 klatek zachowanie niepewnych połączeń utrzymuje
**279/1678** przypisań poprzedniej oceny na siatce i **102/1678** po korygowanej
sieci τ2. Stała sieć pozostaje na zerze. Są to te same przypisania co przed
nowym testem; tylko BLACK, bez RED/YELLOW. Usuwanie braku dowodu sprowadza
wszystkie warianty do zera. Tego nie można uznać za skuteczne wykrywanie granic.

Próg .967 wymaga niemal idealnego przewidywania każdej strony i bloku.
Chroni przed częścią przypadkowych układów, lecz wyklucza także prostą sieć
z jitterem .6 px. Nie obniżano go po obejrzeniu TTMAPP. Model jednej lokalnej
sieci i sposób kalibracji jakości wymagają dalszej oceny; referencje nie
wystarczają do przyjęcia dowolnego łagodniejszego progu.

## Decyzja i dalsza praca

Zachowujemy **porównanie jednego i dwóch modeli jako mechanizm do dalszych prób**,
z dowodem działania na prostej granicy przy centrach. Osobne podparcie sygnałem
pomaga odróżnić puste miejsce od brakujących oznaczeń. Żaden z tych mechanizmów
nie został przyjęty do produkcji ani jako ogólny detektor domen.

Następne pytania w 19 dotyczą przede wszystkim wiarygodności dopasowania:
jak uwzględnić błąd pozycji i niepewność modelu bez wymagania niemal idealnej
sieci oraz jak dobrać kierunek/położenie granicy przy skończonej liczbie centrów.
Osobno potrzebna jest ocena lokalnego szumu, aby jego wzrost nie udawał materiału.
Niepewność powinna pozostać jawnym stanem, a nie automatycznym rozcięciem
lub potwierdzeniem jednej domeny. Następnej próby nie uruchomiono; 20 odłożone.

## Odtworzenie i sprawdzenia

Źródła **`prototype/stmdomains-disjoint-models-material`, `946cfb4`**, baza
`c7ed021`. Kod prototypu pozostaje poza aplikacją. Z tego checkoutu:
`bash stmdomains/prototypes/run-disjoint-models-material.sh /tmp/nowa-proba`.
Wymagane lokalne poprzednie artefakty i środowisko netcat.

- 16 sprawdzeń niezmienności względem przesunięcia/kolejności centrów,
  wzmocnienia, przesunięcia i znaku obrazu, niezależności sygnału od oznaczeń
  oraz dostępu wyłącznie do części uczących przy proponowaniu/dopasowaniu.
  Cztery proste przypadki analityczne skoków 0/1/3/6 px zachowano w JSON.
- **1566 wcześniejszych wyników po 4 tablice** odtworzone dokładnie.
  51 deterministycznych odtworzeń generatora nowych kontroli.
- **261 nowych pomiarów i 261 predykcji / 25056 wyników** odtworzone identycznie
  z blokadą odczytów referencji. Wcześniejsze bramki porządku pozostają zapisanym
  wejściem tego sprawdzianu; nie twierdzimy, że odtworzono od zera cały historyczny ciąg.
- **212 kontroli QtWebEngine**, bez błędów JS; 42 obrazy w obu trybach, 96 ustawień,
  scenariusze, wybór połączenia, kierunku i procenty. Podgląd oraz wykres obejrzane.
  Python/Bash sprawdzone składniowo, wrapper wykonany etapami. Nie testowano
  produkcyjnego GUI, nie dodawano testów aplikacji lub nowych zależności.

CPU, 4 procesy po 1 wątku: nowe bramki bazowe **52.53 s**, porównania
**316.14 + 107.94 s**, predykcje **1.82 s**, ocena **5.89 s**, odtworzenie
**424.46 s**. Maksymalny RSS procesu **205740 KiB**; łącznego szczytu nie mierzono.
Bez GPU. Czasy końcowych etapów, bez budowy podglądu. Kopia **758 plików /
200239951 B**, wszystkie SHA-256 zgodne; następnie dopisano potwierdzenie kopii.
Link `previous` prowadzi do `../tolerant-fit-phase`. HTML/CSV/wykresy są
samodzielne; ponowienie obliczeń wymaga poprzednich artefaktów. Dokumentacja
w Git, dane i duże wyniki w `.scratch/`. Brak potrzeb zmian wspólnych modułów.
