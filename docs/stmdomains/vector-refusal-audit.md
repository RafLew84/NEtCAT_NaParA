# Audyt odmów: wektory obrazu, geometria molekuł i kryterium zgodności

Data: **2026-10-28**. Kontynuacja [issue 19](issues/19-frozen-feature-domains.md)
na polecenie użytkownika **„zrób audyt”**, po decyzji o pozostaniu przy 19.
Źródła: **`prototype/stmdomains-vector-refusal-audit`, `9c78d8c`**, baza
`89cd738`. Dokumentacja: `domains/vector-refusal-audit`, baza `9b94cac`.
Kod eksperymentu pozostaje poza aplikacją.

**Główne ograniczenie pojawia się w kryterium zgodności obrazu przed
łączeniem domen. Zamiana wektorów ACF na propozycje z centrów molekuł
nie naprawia odmów. Kryterium potrafi też zmienić decyzję przy dwóch
równoważnych bazach tej samej sieci.** Mieszanie obszarów w oknie pogarsza
wynik, lecz nie wystarcza do wyjaśnienia wszystkich odmów. Nie jest to
dowód braku domen ani dowód nieskuteczności wszystkich cech FCN/DINO.

[Podgląd HTML](../../.scratch/vector-refusal-audit/index.html) ·
[wykres PNG](../../.scratch/vector-refusal-audit/audit-comparison.png) ·
[PDF](../../.scratch/vector-refusal-audit/audit-comparison.pdf) ·
[pomiary CSV](../../.scratch/vector-refusal-audit/site-audit.csv) ·
[etapy CSV](../../.scratch/vector-refusal-audit/pipeline.csv) ·
[manifest](vector-refusal-audit-manifest.json).

## Pytanie i zakres

Porównano wektory wybrane z obrazu oraz z dostarczonych centrów molekuł
w **tych samych miejscach i otoczeniach**. Rozdzielono cztery możliwości:
wybór niewłaściwych przesunięć, wymagania zgodności obrazu, mieszanie
obszarów w oknie oraz późniejsze grupowanie/łączenie.

**78 znanych już obrazów**: wszystkie 24 klatki TTMAPP z poprzedniej próby,
12 starszych przypadków × 3 ziarna oraz sześć przypadków rzędów × 3 ziarna.
Kontrole obejmują jedną sieć, defekt, braki oznaczeń, zaburzone pozycje,
orientacje, rozstaw, granicę przesunięcia, rozłączne płaty, pas nieporządku,
losowe punkty, pasy oraz spójne/niezależne, skośne i prostokątne rzędy.
Pełna lista i identyfikacja wejścia są w lokalnych `protocol.json`
i `selection.json`. To diagnoza rozwojowa, **nie nowa niezależna walidacja**.

Nie uczono sieci, nie podawano wzorców domen, symetrii ani liczby grup.
Nie zmieniono progów, cech i podziałów FCN/DINO, reguły przestrzennej
łączności ani minimalnej liczby miejsc w fragmencie. Referencje nie
wybierają miejsc pomiaru i nie sterują predykcją. Odczytano je dopiero
po zapisaniu pomiarów, wyników i ich sum kontrolnych.

Częściowe wnętrza TTMAPP obejmują 18 klatek, **1916 miejsc siatki** i
**1678 oznaczeń molekuł**. To kolejne oznaczenia w klatkach, nie liczba
unikalnych fizycznych molekuł. Pozostała część obrazu jest nieoznaczona,
a nie negatywna. Algorytm nadal analizuje pełne 24 obrazy.

## Co dokładnie podmieniono

Promienie 24 i 48 px odniesienia; regularna siatka oraz dostarczone centra.
Propozycja geometryczna powstaje z wszystkich centrów w kole, minimum 6.
Histogram różnic par punktów: długości 6–24 px, interpolacja dwuliniowa,
wygładzenie sigma 1 px. Wybór dwóch niekolinearnych pików korzysta z tej
samej reguły co ACF: 24 maksima, filtr 5 i sinus kąta ≥.35. Pozycje pików
są całkowitoliczbowe. Nie wymusza to konkretnej symetrii, ale ogranicza
zakres szukanych rozstawów i dokładność propozycji.

**Centra są drugim źródłem informacji, nie prawdą referencyjną.** Braki,
błędy i zagęszczenie oznaczeń wpływają na propozycję. Zgodność wektora
z tymi samymi centrami, z których został wyznaczony, nie jest niezależnym
sprawdzeniem jego poprawności. Dwa piki histogramu nie dowodzą domeny.

Zachowano [osiem korelacji różnic obrazu](translation-consistency-trial.md)
(dwa kierunki × cztery części okna), wynik równy ich minimum, preprocessing
i progi `c99`: **.7286339 dla r24**, **.9363692 dla r48**. Próg wyznaczono
wcześniej na negatywnych obrazach przy wektorach ACF. Zastosowanie go do
innej propozycji wektorów jest **podmianą diagnostyczną bez ponownej
kalibracji**, nie gotową metodą. Pozostaje również warunek dodatniego
kandydata ACF. Trzeci wariant, `off_fixed`, odtwarza poprzednią ACF bez
warunku zgodności; jego próg wysokości ACF różni się od wariantów zgodności.

Osiem podziałów FCN/DINO (siatka/centra, HDBSCAN/FH4) i dwa warianty samego
porządku z łącznością × dwa promienie × trzy źródła/reguły = **60 konfiguracji**.
Na obrazach rzędów są tylko 12 wariantów porządku/łączności. Łącznie
**3816 wyników**: 2544 dokładne powtórzenia i 1272 podmiany wektorów.
Ocena z dostępnymi etykietami obejmuje 3456 wyników na 72 obrazach.

Pomocniczo zapisano każdą korelację, średnią, korelację całego okna,
korelację intensywności bez różnic oraz zgodność przesunięć z centrami.
Wskaźniki pomocnicze nie mają nowych progów i nie służą do wyboru detektora.
Korelacja Pearsona toleruje liniową zmianę jasności; badany warunek dotyczy
lokalnej struktury obrazu, nie równości surowych wartości pikseli.

## 1. Wektory różnią się, ale część różnic to wybór bazy

Porównanie uwzględnia zmianę znaków/kolejności wektorów oraz kombinacje
całkowite o współczynnikach −2…2 w obie strony. Tolerancja 2 px służy
opisowi różnic; nie jest regułą akceptacji. Przy tolerancji niezerowej
mówimy o przybliżonej zgodności, nie dowodzie identyczności sieci.

| Otoczenia TTMAPP | Dostępne obie pary | Zgodność bezpośrednia ≤2 px | Zgodność z kombinacjami ≤2 px |
| --- | ---: | ---: | ---: |
| Siatka r24 | 1879/1916 | 605/1879 (32.2%) | 1192/1879 (63.4%) |
| Centra r24 | 1646/1678 | 625/1646 (38.0%) | 1061/1646 (64.5%) |
| Siatka r48 | 1916/1916 | 730/1916 (38.1%) | 1395/1916 (72.8%) |
| Centra r48 | 1678/1678 | 660/1678 (39.3%) | 1265/1678 (75.4%) |

Zatem liczenie każdej różnej pary jako błędu ACF byłoby mylące.
Na siatce r24 mediana udziału centrów zgodnych z przesunięciem w obu
kierunkach wynosi .50 dla wektorów obrazu i .67 dla geometrii
(1822 obliczalne otoczenia; tolerancja 2 px, minimum cztery źródłowe centra).
To poprawa dopasowania do oznaczeń, częściowo oczekiwana z konstrukcji.
Nie przekłada się na wiarygodny detektor domen.

**Konkretny przykład zależności od bazy:** klatka 250, miejsce siatki 113
(indeks od zera), r24, 11 centrów w kole. ACF daje `(-10,5), (-10,-9)`,
geometria `(-10,-9), (0,-14)`. To dokładnie ta sama sieć całkowitych
przesunięć: drugi wektor geometrii jest różnicą wektorów ACF. Mimo to
minimum korelacji zmienia się z **.5285 do .7878**, przekraczając próg .7286.
Sześć z 17 zmian decyzji w znanych wnętrzach r24 dotyczy dokładnie
równoważnych baz. Taką zmianę trudno interpretować jako samo naprawienie
źle znalezionej sieci; zmienia się również kierunek testowania obrazu.
To opis po obliczeniach, bez zmiany reguły lub wyboru najlepszej bazy.

## 2. Kryterium zgodności pozostaje głównym miejscem odmowy

| TTMAPP | Przechodzące miejsca: wektory obrazu | Wektory centrów | Końcowe przypisania molekuł, oba warianty |
| --- | ---: | ---: | ---: |
| Siatka r24 | 0/1916 | 17/1916 | 0/1678 |
| Centra r24 | 0/1678 | 0/1678 | 0/1678 |
| Siatka r48 | 0/1916 | 0/1916 | 0/1678 |
| Centra r48 | 0/1678 | 0/1678 | 0/1678 |

Na siatce r24 wszystkie 1916 miejsc mają podparcie i kandydata. Po
podmianie 17 przechodzi również grupowanie FCN, lecz tworzą składowe
liczące **1–3 miejsca**, przy minimum czterech. Sprawdzono składowe
całych klatek, nie tylko ich przecięcie z referencją. Dlatego łączenie
usuwa te resztki; nie jest pierwotną przyczyną masowych odmów.

Mediana minimum ośmiu korelacji na siatce r24: **−.022 → −.009**.
Mediana średniej z ośmiu: **.419 → .434**, dla obliczalnych zestawów.
Nawet w 1192 otoczeniach o przybliżonej zgodności baz mediana minimum
wynosi tylko **.058 → .065**. Nie wystarcza wyjaśnienie, że zawsze
wybierano zupełnie inny układ przesunięć.

Minimum mocno zależy od najsłabszej części obrazu. Samo zastąpienie go
średnią nie jest uzasadnioną naprawą: średnia może zamaskować granicę,
niezależne rzędy lub brak struktury w części okna. Musiałaby otrzymać
osobną kalibrację i kontrolę takich błędów. Wartości −1 oznaczają też
nieobliczalną korelację/stały sygnał; statystyki średniej i całego okna
podano warunkowo, z liczebnościami w tabelach maszynowych.

Istnieje również niezależny problem dalszego etapu: zachowany wariant
**DINO/centra/HDBSCAN odmawia grupowania wszystkim 1678 oznaczeniom**.
Usunięcie bariery porządku nie naprawiłoby tego wariantu. FCN i pozostałe
podziały przyjmują większość lub wszystkie miejsca na etapie wyglądu.
Audyt nie rozgrzesza więc całego późniejszego grupowania.

## 3. Mieszane okna nie wyjaśniają całości

Po zamrożeniu wyników wyróżniono otoczenia, których koło w co najmniej
80% należy do tego samego znanego wnętrza. Pozostała część może być
nieoznaczona; nie utożsamiamy jej z inną domeną.

| Otoczenia | Liczba | Mediana minimum: obraz → geometria | Próg |
| --- | ---: | ---: | ---: |
| Siatka r24 | 847 | .101 → .125 | .729 |
| Centra r24 | 786 | .103 → .106 | .729 |
| Siatka r48 | 332 | .157 → .169 | .936 |
| Centra r48 | 299 | .166 → .169 | .936 |

Wyniki są lepsze niż w całym zbiorze, nadal daleko od progów. Wszystkie
17 miejsc przepuszczonych przez geometrię r24 mieści się w tej grupie;
pozostałe kombinacje nadal nie przepuszczają żadnego. To przemawia
przeciw wyjaśnieniu wszystkich odmów wyłącznie granicami w oknach.
Nie wyklucza jednak mieszania: ramki są przybliżone, a przesunięte próbki
korelacji wychodzą poza koło nawet o 18 px. Nie sprawdzano tu dokładnej
referencji całego faktycznego obszaru odczytu.

## 4. Geometria nie daje uniwersalnej poprawy na kontrolach

Siatka r24, sam porządek i łączność, trzy zachowane ziarna:

| Kontrola | Wektory obrazu | Wektory centrów |
| --- | ---: | ---: |
| Jedna sieć: przypisane molekuły | 79.7% | 79.7% |
| Brak 30% samych oznaczeń | 79.5% | 71.7% |
| Lokalne braki samych oznaczeń | 78.4% | 78.4% |
| Słabsze spójne rzędy | 79.7% | 68.0% |
| Prostokątna sieć 13° | 78.2% | 77.6% |
| Losowe fazy rzędów: błędne miejsca | 24/768 | 14/768 |

Geometria zmniejsza jeden błąd, ale nie usuwa go, a przy niepełnych
oznaczeniach i słabszych rzędach odbiera część poprawnych przypisań.
Wariant centrów r24 z brakującymi 30% oznaczeń dodatkowo dzieli pojedynczą
sieć na dwa fragmenty w dwóch z trzech realizacji. Przy r48 geometria
odrzuca wszystkie słabsze spójne rzędy 0°, więc mniejsza liczba fałszywych
wyników nie dowodzi przewagi. Nie przeprowadzano nowego wyboru konfiguracji.

## Weryfikacja i odtworzenie

- 128 niezmiennych propozycji po permutacji centrów; trzy równoważne bazy,
  sześć przypadków braku wystarczającej liczby centrów i kontrola analityczna.
- **312 dokładnych odtworzeń** dotychczasowych tablic zgodności; błąd 0.
  **2544 dokładne odtworzenia** wariantów bazowych (bramka, domeny, przypisania).
- **78 plików pomiarów i 78 predykcji / 3816 wyników** ponowiono z blokadą
  odczytów referencji: identyczne hashe zawartości. Sprawdzono także hashe
  372 poprzednich predykcji, protokołu, progów i kodu obliczeń.
- 72 pary tablic obrazowych nie zmieniły się po usunięciu samych oznaczeń.
  Wszystkie 12 porównań tablic geometrycznych zmieniło się — oczekiwany
  wpływ danych wejściowych, a nie wymagana niezmienniczość.
- **125 kontroli QtWebEngine**, bez błędów JS; obejrzano HTML i wykres.
  Sprawdzono składnię Python/Bash. To kontrola eksperymentu i podglądu,
  nie odbiór skuteczności ani test aplikacji produkcyjnej.

CPU, cztery procesy po jednym wątku BLAS/OpenMP: pomiary **41.57 s**,
predykcje **1.05 s**, ocena **52.01 s**, pełne ponowienie **43.68 s**.
Maksymalny RSS jednego procesu przygotowania **110492 KiB (~108 MiB)**;
nie zmierzono łącznego szczytu. Bez GPU, nowych wag i instalowania zależności.
Kopia lokalna: **179 plików / 92488878 B**, zgodne SHA-256, następnie
dopisano potwierdzenie kopii. Dane i poprzednie artefakty pozostają lokalne.

Odtworzenie ze wskazanej gałęzi prototypu:
`bash stmdomains/prototypes/run-vector-refusal-audit.sh`.
Etapy wykonano indywidualnie; wrapper sprawdzono składniowo.
HTML zawiera 24 klatki TTMAPP i po jednym ziarnie każdego z 18 przypadków
kontrolnych. Kliknięcie wybiera rzeczywiste miejsce pomiaru. Kwadraty
siatki i centra molekuł są wyraźnie rozróżnione; ramki są opcjonalną
nakładką oceny i niczego nie przeliczają.

## Wniosek i następny krok w 19

**Nie zamykamy 19; 20 pozostaje odłożone zgodnie z decyzją użytkownika.**
Najpierw należy zbadać kryterium powtarzalności odporne na wybór
równoważnej bazy oraz zmienność wyglądu molekuł wewnątrz tego samego układu.
Obecna zgodność intensywności, jej minimum i kalibracja z syntetycznych
negatywów razem nie przenoszą się wystarczająco na TTMAPP.

Proponowana kolejna próba: porównać aktualną parę z oceną **rodziny
zgodnych przesunięć**, z osobnym pomiarem zgodności położeń i struktury
obrazu. Dodać kontrole tej samej sieci ze zmiennym wyglądem molekuł,
szumem i niewielkim odkształceniem, obok niezależnych rzędów, przerw
i granic przesunięcia. Dobór wielu przesunięć wymaga własnej kontroli
fałszywych akceptacji — samo wybranie maksimum korelacji nie wystarczy.
Kalibracja na kontrolach, zamrożenie przed ponowną oceną TTMAPP;
bez narzucania domen, ich liczby i bez uczenia z ramek.

To jeszcze **niewykonany eksperyment**, nie gotowa recepta. Nie należy
teraz obniżać progu tylko po to, żeby odzyskać znane ramki, ani zmniejszać
minimalnego fragmentu do pojedynczego miejsca. Nie wybrano metody do
programu, nie uruchomiono treningu ani całych 268 klatek.
