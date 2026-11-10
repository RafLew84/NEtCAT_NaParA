# Orientacja i łączenie sąsiadów — kontynuacja issue 15

Data: 2026-10-23. Polecenie: wykonać badanie zaproponowane po
[próbie powtarzalności](recurrence-criterion-trial.md).
Status: eksperyment wykonany, **issue 15 pozostaje `claimed` do omówienia**.

Lokalna komórka sieci i kontrola zgodności z początkiem obszaru poprawiają
część wyników. Przy 30% brakujących centrów odzyskujemy jedną kontrolną
domenę i 81.9% oznaczeń, zamiast 2–3 fragmentów i 46.7%. Na częściowych
referencjach TTMAPP przypisanie rośnie z 62.5% do 70.7%, bez scaleń
ocenianych par z różnych regionów. Jednocześnie **RED pogarsza się z
28/101 do 14/101 przypisań**, a granica przesunięcia z niedokładnymi
centrami jest prawie całkowicie scalana. To użyteczny punkt odniesienia,
nie gotowa ogólna metoda wykrywania domen.

Podgląd pełnych klatek:
`/home/rlew/projekty/NEtCAT-domains/.scratch/orientation-and-joining/index.html`.
Zacząć od „Braki centrów”, „Granica przesunięcia” i „Pełne TTMAPP”.
Można przełączać wektory komórki, dawną symetrię, odmowy i referencję.
Wykres `orientation-comparison.png` pokazuje przypisania; ich jakość trzeba
oceniać razem z podziałami i scaleniami opisanymi poniżej.

## Zakres porównania

Zamrożono kryterium powtarzalności z poprzedniej próby: R=36 px,
tolerancja 24% lokalnego rozstawu, poprawiony wynik >0.25. Minimum grupy
nadal wynosi 8 centrów. Katalog SOAP/36 nie jest dopasowywany ponownie.

Głównym wynikiem są **obszary zgodnej geometrii bez warunku typu**.
Osobno zapisujemy wynik po dołączeniu dawnego katalogu. Rozdziela to
badanie orientacji/łączenia od znanej luki rozpoznawania typów i rozstawów.
Dlatego główny punkt odniesienia ma 1049/1678 przypisań, a wcześniejszy
wynik z katalogiem 1048/1678; oba zaokrąglają się do 62.5%. Nowe kontrole
nie mają katalogu: ich ocena `typed` jest `null`, nie zerową skutecznością.

Porównano trzy rodziny:

1. **Dawny estymator:** jedna wybrana symetria z pierwszego otoczenia,
   siła ≥0.5, identyczna symetria sąsiadów i różnica kąta ≤12°.
2. **Rozkład kierunków:** zespolone składowe kątowe 2/4/6/8/10/12
   z par punktów w całym lokalnym otoczeniu. Porównanie pełnego opisu
   zachowuje orientację bez przełączania pojedynczej zwycięskiej symetrii.
3. **Lokalna komórka:** zagęszczenia wektorów przesunięć proponują dwie
   nieprawie równoległe translacje. Dopasowanie punktów do ich całkowitych
   kombinacji odrzuca duże reszty i dwukrotnie poprawia bazę oraz początek
   sieci. Porównanie uwzględnia równoważne całkowitoliczbowe zmiany bazy,
   więc zamiana osi lub odwrócenie wektora nie tworzy nowej struktury.

Komórka nie narzuca kwadratowej ani sześciokątnej symetrii, ale zakłada
opis centrów **jedną siecią translacyjną**. Nie jest ogólnym modelem
dowolnego motywu z kilkoma nierównoważnymi molekułami w komórce. Używa
centrów, nie tekstury STM; obrazy służą podglądowi. Błąd reszt, liczba
dopasowanych punktów i konkurencyjne bazy opisują niepewność dopasowania,
lecz nie są skalibrowanym prawdopodobieństwem istnienia domeny.

Dla nowych opisów porównano dwie reguły łączenia: zgodność kolejnych
sąsiadów oraz dodatkowo zgodność każdego dołączanego centrum z opisem
punktu rozpoczynającego obszar. Ten punkt wybieramy według jakości
dopasowania, z remisem rozstrzyganym przez stabilne ID. Nie zadano K.
Zgodność fazy, gdy włączona, dotyczy wyłącznie krawędzi między sąsiadami;
nie zapewnia jednej wspólnej fazy dla całej grupy.

## Dane, parametry i wybór

Wejście: **24 pełne klatki TTMAPP i 204 kontrole, razem 228 próbek**.
Do poprzedniego zestawu dodano cztery przypadki, każdy z trzema ziarnami
rozwojowymi i trzema do oceny: różnica orientacji 8°, dwie orientacje
z brakiem 30% centrów, dwie orientacje z błędem centrów σ=0.72 px oraz
granica przesunięcia z takim błędem. Przy zaburzeniu oznaczeń obraz
pozostaje niezmieniony, a centra przesunięte poza pole są odrzucane.

Dotychczasowe kontrole obejmują także losowe skupiska, braki, deformację
i rzędy z niezależnymi przesunięciami. Rzędy nie mają kompletnej prawdy
domen 2D: nie uczestniczą w kalibracji ani metrykach trafności.

Siatka **31 wariantów**:

- jedna dawna reguła;
- rozkład kierunków: odległość kosinusowa ≤0.12/0.25/0.4, dwie reguły
  łączenia; minimalna siła opisu 0.15 — 6 wariantów;
- komórka: ≥65%/80% lokalnych punktów w modelu, różnica bazy
  ≤0.12/0.22 rozstawu, różnica fazy wyłączona lub ≤0.18/0.30 rozstawu,
  dwie reguły łączenia — 24 warianty.

Kandydaci translacji: długości 0.6–2.5 lokalnego rozstawu, szerokość
skupiska 0.22 rozstawu, minimum 3 pary i maksimum 8 różnych propozycji.
Do dopasowania wymagamy 8 punktów, tolerancji reszty 0.24 rozstawu
i pełnego rzędu modelu 2D. Konkurencyjna nierównoważna komórka o podobnym
wsparciu/błędzie oznacza niejednoznaczność. Krawędzie sięgają najwyżej
1.65 mniejszego z lokalnych rozstawów, jak w poprzedniej próbie.

Wybór osobno dla rodzin, **tylko na kontrolach rozwojowych 1701–1703**:
co najmniej 90% przypisań pojedynczej sieci, zero obszarów na czterech
rodzinach losowych, co najmniej 50% przypisań i najwyżej 2% scaleń par
w pięciu kontrolach: dwie orientacje, obrót 8°, różny rozstaw, granica
przesunięcia i rozłączne płaty. Wśród spełniających wymagania maksymalizujemy
średnią po 21 dodatnich przypadkach z wartości
`przypisanie × (1 − podziały) × (1 − scalenia)`, potem najmniejsze
i średnie przypisanie. Jest to jawna miara wyboru, nie pełna ocena domen.

Wybrano **komórkę ≥65%, różnicę bazy ≤0.12, fazę ≤0.30 i zgodność
ze startem obszaru**: `cell-0.65-0.12-0.3-seed`.
Żaden wariant rozkładu kierunków nie spełnił wszystkich wymagań;
`angular-0.4-seed` pokazujemy wyłącznie jako najlepszy wariant diagnostyczny.
Nie rozluźniono warunków, by nadać mu status wybranego rozwiązania.

Predykcje wszystkich wariantów zapisano przed odsłonięciem referencji.
Ocena syntetyczna korzysta z ziaren 2701–2703. Część idealnych geometrii
powtarza się między ziarnami; nowe ziarna nie tworzą niezależnej akwizycji
STM ani nowej rodziny struktur. Ramki TTMAPP były już używane do diagnozy,
więc obecna ocena jest nadal rozwojowa, nie testem generalizacji.

## Dlaczego dawny estymator gubił połączenia

W regularnej kontroli z 30% braków 440/537 pozostałych centrów przechodzi
powtarzalność, ale stary estymator określa orientację tylko dla 279.
**161 punktów odpada przez brak orientacji z najbliższego otoczenia**.
Z 1129 potencjalnych par aż 521 traci krawędź z tego powodu.

Przy błędzie centrów σ=0.72 px tej samej sieci stary wybór symetrii
rozrzuca wyniki między 4, 5, 7, 8, 9, 10, 11 i 12. Z 2294 potencjalnych
par 283 odpada przez różne wybrane symetrie, 59 przez brak orientacji,
a tylko 2 przez sam limit kąta. Większe otoczenie i opis bez twardego
wyboru jednej symetrii odpowiadają więc na rzeczywiste ograniczenie kodu.
Nie wynika z tego, że każda odmowa TTMAPP ma tę samą przyczynę.

## Wyniki na kontrolach odłożonych do oceny

Wartości przypisania dotyczą poprawnie oznaczonych obszarów kontrolnych.
Liczby obszarów podano dla trzech ziaren; błędy par są warunkowe względem
przypisania obu punktów. W tej tabeli porównujemy główne obszary bez typu.

| Kontrola | Dawna reguła | Komórka + zgodność ze startem |
| --- | --- | --- |
| Jedna sieć | 1/1/1; 98.4% przypisań | 1/1/1; 98.4% |
| Brak 30% centrów | 2/2/3; 46.7%, 33.8% podziałów par | **1/1/1; 81.9%, bez podziałów** |
| Brak 50% | 1/0/0; 2.9% | 2/1/2; 53.6%, nadal 31.8% podziałów |
| Błąd centrów 0.72 px | 1/1/1; 85.7% | 1/1/1; 95.5% |
| Błąd centrów 1.2 px | 3/2/2; 49.2% | 1/1/1; 76.8% |
| Błąd 0.72 px + brak 30% | 2/2/3; 30.2% | **1/1/1; 74.8%** |
| Dwie orientacje | 2/2/2; 89.5% | 2/2/2; 96.4%, bez podziałów/scaleń |
| Różnica orientacji 8° | 1/1/1; 100% scaleń par różnych domen | **2/2/2; 97.6%, bez podziałów/scaleń** |
| Dwie orientacje + brak 30% | 4/5/2; 45.9% | 2/2/2; 78.0%, bez podziałów/scaleń |
| Idealna granica przesunięcia | 3/3/3; 97.9%, 11.3% podziałów | **2/2/2; 92.9%, bez podziałów/scaleń** |
| Granica przesunięcia + błąd 0.72 px | 1/1/2; 78.7%, 68.5% scaleń | **2/1/1; 92.8%, 98.1% scaleń** |
| Łagodnie wygięta sieć | 3/3/3; 88.0%, 43.0% podziałów | 3/3/3; 95.5%, **51.0% podziałów** |

Na czterech rodzinach losowych żaden z trzech głównych wariantów nie
tworzy obszaru: **0/3195 punktów tła w obszarach**. Stały warunek
powtarzalności nadal przepuszcza 2 punkty, ale nie stają się domenami.
W pasie nieuporządkowanym komórka przypisuje do obszaru 1/119 punktów
negatywnych (dawniej 0), opis kierunków 3/119. Nie jest to idealne
rozpoznanie granicy nieuporządkowanego materiału.

Rzędy o niezależnych przesunięciach dają 7/6/6 obszarów dla komórki,
9/11/5 dla dawnej reguły i 2/3/2 dla kierunków. Bez pełnej prawdy domen
nie traktujemy tych liczb jako trafności; nadal pokazują, że lokalny model
może składać pozornie spójne fragmenty struktur skorelowanych.

**Ważne ograniczenie wyboru:** granica z błędem centrów uczestniczyła
w średniej jakości, ale nie miała osobnego twardego limitu scaleń.
Wybrany wariant spełnia zatem zapisane wąskie warunki, a nie komplet
potrzeb programu. Kolejne porównania powinny zachować ten trudny przypadek
jako osobny warunek, bez poprawiania rankingu po obejrzeniu TTMAPP.

## TTMAPP — poprawa nie jest równomierna

Ocena obejmuje 1678 obserwacji centrów w 18 częściowych referencjach,
nie 1678 niezależnych molekuł. Poza oznaczonymi wnętrzami nie znamy
trafności; nieoznaczonych miejsc nie uznajemy za tło.

| Główny wariant | Przypisania | Podziały par w regionie | Scalenia par z różnych regionów |
| --- | --- | --- | --- |
| Dawna reguła | 1049/1678 = 62.5% | 203/28638 = 0.71% | 708/2329 = 30.4% |
| Kierunki, diagnostyczny | 1457/1678 = 86.8% | 1372/43225 = 3.17% | 2822/16422 = 17.2% |
| Komórka + tylko sąsiedzi | 1198/1678 = 71.4% | 1049/36125 = 2.90% | 1443/4154 = 34.7% |
| **Komórka + zgodność ze startem** | **1187/1678 = 70.7%** | 1001/35733 = 2.80% | **0/3801 = 0%** |

Mianowniki metryk par są różne. Zero scaleń dotyczy tych 3801 ocenianych
par przypisanych punktów; nie dowodzi braku błędów we wszystkich domenach
ani na nieoznaczonym otoczeniu. Suma przypisań jest silnie zdominowana
przez BLACK.

| Referencja | Dawna reguła | Kierunki | Komórka + zgodność ze startem |
| --- | --- | --- | --- |
| BLACK, 1303 | 1008 = 77.4% | 1225 = 94.0% | 1125 = 86.3% |
| RED, 101 | 28 = 27.7% | 69 = 68.3% | **14 = 13.9%** |
| YELLOW, 274 | 13 = 4.7% | 163 = 59.5% | 48 = 17.5% |

Po dołączeniu zamrożonego katalogu wyniki zmieniają się tylko o jeden
punkt BLACK: 1048/1456/1186 przypisań dla starego/kierunków/komórki.
Nie naprawiono w ten sposób typów ani rozstawów. Kolory referencji
oznaczają głównie różne orientacje tej samej sieci, nie różne typy.

Dla komórki w RED pozostaje 20 odrzuceń przez powtarzalność, 12 słabych
dopasowań, 8 konkurencyjnych komórek i **47 punktów w zbyt małych grupach**.
W YELLOW odpowiednio 76, 36, 8 i **106**. Zwiększenie ogólnego odsetka
przypisań nie rozwiązuje więc słabego rozpoznania tych obszarów.

## Co rzeczywiście poprawiło łączenie

Przy tej samej komórce przejście od zgodnych par sąsiadów do dodatkowej
zgodności ze startem zmniejsza scalenia TTMAPP z 1443/4154 do 0/3801,
przy podobnym przypisaniu 71.4% → 70.7%. Na różnicy orientacji 8°
usuwa całkowite scalenie. Pokazuje to problem łańcucha: kolejne małe
różnice potrafią połączyć dwa niezgodne końce obszaru.

Cena jest widoczna na płynnie wygiętej sieci: same sąsiedztwa tworzą
jedną grupę, a zgodność ze stałym początkiem trzy. Nie ustalono jeszcze
reguły rozróżniającej dozwoloną deformację od rzeczywistej granicy.

W porównanych wariantach faza wyłączona, limit 0.18 i limit 0.30 dają
takie same metryki na TTMAPP oraz na idealnej i zaburzonej granicy
przesunięcia. **Sukcesu na idealnej granicy nie można przypisać kontroli
fazy.** Wynika z lokalnego dopasowania/łączenia w tym przykładzie;
nie jest ogólnym detektorem granic przesunięcia. Po dodaniu błędu centrów
32502/33144 = 98.1% par różnych domen zostaje scalonych. Dalsze rozwijanie
tej rodziny wymagałoby wspólnego modelu fazy i odporności na niepewność
położeń, a nie samej korekty progu kąta.

## Sprawdzenia i odtwarzalność

- Dokładne odtworzenie głównego wyniku i wariantu z katalogiem poprzedniej
  próby na wszystkich 204 wcześniejszych próbkach; bramka także identyczna.
- Walidacja **1368 wyników** dla sześciu wariantów podglądu. W nowych
  kontrolach brak typowania jest jawny; obszary główne mają `ordered_untyped`.
- Po sześć par kontrastu, odwrócenia kontrastu i technicznego powiększenia
  ×2 daje identyczne obszary, kwalifikacje i bramkę dla wszystkich wariantów.
- Obrót 37° i przesunięcie czterech kontroli: identyczne przypisane pary
  wszystkich 31 wariantów, brak zmian frakcji dopasowania i niejednoznaczności;
  błąd transformacji opisu kątowego <6e-15. Bramka i katalog są zamrożone.
- Przed oceną referencji naprawiono remisy numeryczne w rzutowaniu na
  liczby całkowite i kolejności startów. Zaokrąglenia 10/8 miejsc oraz
  epsilon 1e-7 na granicach; ponowiono całą ekstrakcję i kalibrację.
- Pełna ponowna ekstrakcja i predykcja bez katalogu referencji, z losową
  kolejnością próbek oraz oznaczeń: **228/228 plików cech i 228/228 plików
  predykcji identycznych bajtowo**, każdy wynik zawiera 31 wariantów.
  Kanonizacja po ID i zamrożona kalibracja są częścią tego sprawdzenia.
- QtWebEngine offscreen: 14 kontroli scenariuszy/widoków/referencji,
  bez błędów JavaScript i poziomego przepełnienia. Obejrzano zrzut i wykres.
  To nie test natywnego GUI aplikacji ani wszystkich kombinacji podglądu.

Końcowe obliczenia CPU, jeden wątek BLAS/OpenMP: ekstrakcja **205.11 s**,
wybór **40.47 s**, predykcja 31 wariantów **186.77 s**, ocena **2.80 s**.
Największy procesowy RSS 264000 KiB (~258 MiB), w kalibracji. Pomiar
Linux `ru_maxrss`, bez GPU/treningu i bez pomiaru VRAM. Nie dopasowywano
ponownie SOAP; nie wykonano benchmarku całych 268 klatek.

Środowisko `netcat`: NumPy 2.2.5, SciPy 1.15.2, scikit-learn 1.6.1,
Matplotlib 3.10.1, PyQt6 6.9.1 / WebEngine 6.9.0. Istniejące dodatkowe
DScribe 2.1.2/sparse 0.19.2 pozostają w `/tmp/stmdomains-issue15-deps`;
bez instalacji lub zmian wspólnej konfiguracji. Nie zmieniono aplikacji
ani nie uruchamiano jej testów produkcyjnych.

Źródło: **`prototype/stmdomains-orientation`, commit `2b70d0d`**, baza
`bc3763e`, worktree `/tmp/netcat-stmdomains-orientation-prototype`.
Nie scalać kodu prototypu do aplikacji. README i skrypt odtworzenia:
`stmdomains/prototypes/README-orientation.md` i `run_orientation_trial.sh`.
Z katalogu głównego tej gałęzi:

```bash
bash stmdomains/prototypes/run_orientation_trial.sh \
  /home/rlew/projekty/NEtCAT-domains/.scratch/recurrence-criterion \
  /tmp/stmdomains-orientation-new
```

Końcowy katalog musi być nowy. README podaje także kontrolę obrotu
i pełne powtórzenie bez referencji. SHA-256 głównego skryptu:
`58c036297563bbe8d3b5321a85ab357170e70cf4d33310535da7379a3a5cf8de`.
Pakiet lokalny `.scratch/orientation-and-joining/` zawiera plan,
228 wejść, cechy, 31 wariantów predykcji, ocenę i diagnozę odmów,
wyniki JSON/CSV, podgląd, wykres, wersje i hashe. Duże dane są poza Git.

## Następny krok

Zachować komórkę z kontrolą zgodności obszaru jako **geometryczny punkt
odniesienia**, a opis kierunków jako wariant pokazujący kompromis między
przypisaniem a scalaniem. Obecne wyniki odpowiadają na pytanie o przyczynę
części odmów, lecz nie uzasadniają wdrożenia detektora.

Proponowany kolejny krok po omówieniu issue 15 to
[porównanie SBC/MatID w issue 16](issues/16-sbc-matid-domains.md) na tym
samym wejściu i rozszerzonych kontrolach. Osobno oceniać granicę
przesunięcia z błędem centrów, małą różnicę orientacji, braki i wyniki
RED/YELLOW; poprawa samej sumy przypisań nie wystarczy. Zachować też
porównanie z teksturą w issue 17, ponieważ ta próba w ogóle nie używa
informacji obrazowej. Nie uruchomiono tych zadań w obecnej sesji.

Jeżeli później wrócimy do komórki, potrzebne będzie odporne dopasowanie
wspólnej geometrii i fazy obszaru, z rozróżnieniem deformacji i granicy
oraz możliwością bardziej złożonego motywu. Nie zmieniamy teraz parametrów
pod RED/YELLOW. Issue 15 nadal `claimed`; odbiór 13 i jakość 04 pozostają
otwarte, bez wyboru metody produkcyjnej.
