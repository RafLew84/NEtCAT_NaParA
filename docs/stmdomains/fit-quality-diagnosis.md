# Diagnostyka jakości dopasowania — issue 19

Data: **2026-10-31**. Wykonana na polecenie użytkownika kontynuacja
[rozłącznych modeli](disjoint-models-material-trial.md).

**Samo złagodzenie progu ani uwzględnienie liczby punktów nie rozwiązuje
problemu.** Wykazano błąd wyboru okresu sieci po podziale danych oraz
niewystarczającą liczbę niezależnych rzędów w części wcześniejszych kontroli.
Na TTMAPP dopasowania we wnętrzach referencji są lepsze niż w otoczeniach
mieszanych, ale nowa ocena nie daje ogólnej poprawy. Nie rozstrzygnięto,
czy rzeczywiste dane wymagają wielomolekułowego motywu. Próbę zakończono;
**19 pozostaje `claimed`, do omówienia; 20 nadal odłożone.**

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/fit-quality-diagnosis/index.html`.
Pokazuje obrazy, rzeczywiste centra, części dopasowania i oceny, przewidywane
węzły oraz błędy pozycji. Kwadraty oznaczają miejsca sprawdzania otoczeń,
nie molekuły ani wykryte domeny. CSV oraz wykres PNG/PDF są obok podglądu.
[Manifest](fit-quality-diagnosis-manifest.json) identyfikuje wejście i wyniki.

## Skąd pochodził poprzedni wysoki próg

Audyt zachowanych wyników, bez zmiany poprzedniej kalibracji:

- Wszystkie **600 kierunków** ponad progiem `.966883` pochodzą z kontroli
  niezależnych poziomych rzędów. Losowe punkty nie wymusiły tego progu.
- W każdej z 1200 stron tych porównań były tylko **2–3 rzędy**: 321 stron
  miało dwa, 879 trzy. Każdy testowy rząd występował również w części
  uczącej. Oceniano dalsze punkty tych samych rzędów, a nie nową fazę rzędów.
- Bazy nie były zdegenerowane: pole komórki 142.1–145.9 px², mediana 144,
  współczynnik uwarunkowania 1.12–1.67. Dwa rzędy z dowolną wzajemną fazą
  można opisać skośną siecią; samo dobre dopasowanie takiego wycinka
  nie dowodzi powtarzalności w dwóch kierunkach.
- Różne warianty wyglądu powtarzały geometrię. **45 obrazów to 19 unikalnych
  geometrii, w tym 18 niepustych.** Audytowy q99 po deduplikacji wynosi
  `.921621`, zamiast `.966883`; dla samych losowych rozkładów `.313622`.
  To diagnoza wrażliwości kalibracji, nie zgoda na obniżenie starego progu.

Dane audytu: `independent-audit/negative-audit.json`, `row-audit.json`
i `geometry-deduplication.json`. Nowa próba deduplikuje geometrie przed
kalibracją. Liczne nakładające się okna nadal nie są niezależnymi obserwacjami.

## Wejście i zamrożony protokół

**97 obrazów, 68184 oceny otoczeń, po cztery miary**: 19 geometrii kalibracji,
24 pełne klatki TTMAPP i 54 nowe syntetyki (18 przypadków × 3 ziarna
9101–9103). TTMAPP ma 18 częściowych referencji i 6 klatek bez nich.
Nie analizowano pełnych 268 klatek. Ramki nie wybierają miejsc obliczeń,
baz, parametrów ani liczby domen. Nie uruchamiano treningu.

Próbkowanie całego obrazu co 24 px, od `(12,12)`, promienie 24/36/48 px.
Każde otoczenie dzielimy na dwa rozłączne zbiory i zamieniamy ich role:

- naprzemiennie po uporządkowaniu współrzędnych;
- blok lewy/prawy;
- blok górny/dolny.

Minimum 6 punktów na dopasowanie i 6 na ocenę. Propozycja bazy pochodzi
wyłącznie z części uczącej: wcześniejszy histogram przesunięć 6–24 px,
kanoniczna baza, pięć iteracji Huber z tolerancją 2 px i limitem korekty
afinicznej 15%. Podział blokowy nie zawsze rozdziela całe rzędy dowolnie
obróconej sieci; wyniki zawierają udział nowych poziomów indeksów obu osi.

Porównanie:

1. **Q**: mniejsza z dwóch średnich `exp(−d²/8)` na punktach testowych.
2. **Z** dla z góry zadanych σ=.6/1.2/2 px: zgodność po uwzględnieniu
   tolerancji pozycji, geometrii dopasowania i liczby punktów, odniesiona
   do równomiernej losowej fazy w komórce dopasowanej sieci.

W Z tolerancja punktu wynosi `σ√(1+h)`, gdzie `h` pochodzi z macierzy
indeksów części uczącej. To przybliżenie niepewności ekstrapolacji,
warunkowe względem wybranej bazy i indeksów; rzeczywisty fit stosuje Huber
i ograniczenie korekty, więc nie jest zwykłym modelem OLS. **σ nie jest
wyliczana z błędów dopasowania ani zmierzona na TTMAPP.** Nie rozlicza
błędu wyboru bazy, nieznanego motywu czy fizycznego odkształcenia.

Średnią i wariancję oceny losowej fazy całkujemy na siatce 16×16 wewnątrz
komórki. Z jest standaryzowaną różnicą sum ocen, **nie p-value ani
prawdopodobieństwem domeny**. Przy średniej ocenie losowej fazy ≥.75 wynik
Z jest niedostępny. Zależności pomiędzy punktami ograniczają interpretację.

Progi q99 na starych negatywach, osobno dla promienia, podziału, miary
i liczby testowych punktów 6–11/12–19/20+. Minimum 100 dostępnych okien
w komórce kalibracji; w przeciwnym razie **brak progu**, nie odrzucenie
porządku. Z 108 komórek kalibracji 48 nie ma wystarczających danych. Liczba okien nie zastępuje liczby niezależnych obrazów. Progi
zamrożono przed wygenerowaniem nowych kontroli; nie wybierano najlepszego
wariantu według TTMAPP. Nowe Q to minimum dwóch ocen całego okna;
poprzednie minimum czterech ocen stron granicy ma inny rozkład.

Kontrole mają rozstaw 12 px, warianty 10/14 px, błędy pozycji .6/1.2/2 px,
braki 30/60%, dwupunktowy motyw, różnice orientacji 8°/30°, przesunięcie
wzoru, niezależne rzędy, losowe punkty i pustą przerwę. Rozstaw i liczebność
dobrano orientacyjnie do nieoznaczonych danych wejściowych: TTMAPP mediana
najbliższego sąsiada 12.15 px; liczebność r48 ma percentyle 18/32/42.
Nie oznacza to, że znamy prawdziwe braki lub błąd oznaczeń TTMAPP.
W kontrolach ziarno zmienia położenie/obrót, szum i odpowiednie zaburzenia;
porównywane warianty współdzielą ziarna, więc nie są niezależnymi seriami.

## Kontrole ujawniają problem propozycji, nie tylko oceny

Przy r48, w idealnej sieci i podziale naprzemiennym, **83/184** dostępne
okna mają Q<.5 mimo Q>.9 po rozpoczęciu dopasowania od prawdziwej bazy.
Dla braków 30% jest to **97/187**. Mediana pola proponowanej komórki w
pierwszym przypadku wynosi około 1.9–2.0 prawdziwej komórki: część ucząca
zawierająca co drugi punkt sugeruje podwojony okres. To konkretna utrata
informacji przez sposób proponowania modelu i podział danych.

W podziale góra/dół takie porażki spadają odpowiednio do **0/192 i 9/190**.
Nie oznacza to uniwersalnej przewagi osi pionowej: dla inaczej obróconej
struktury kierunek rozdzielający niezależne powtórzenia będzie inny.

Diagnostyka prawdziwej **bazy startowej** jest wyłącznie oceną na syntetykach:
model nadal dopasowuje bazę i fazę, a nie dostaje prawdziwych węzłów.
Nie jest sufitem osiągalności algorytmów ani konfiguracją do użycia na STM.
Przykładowo przy r48 i podziale naprzemiennym:

| Kontrola | Mediana Q, propozycja | Prawdziwa baza startowa |
| --- | ---: | ---: |
| Błąd pozycji 1.2 px | .207 | .669 |
| Błąd 1.2 px i brak 30% | .157 | .652 |
| Dwupunktowy motyw | .194 | .241 |

Dwupunktowy motyw jest dokładnie periodyczny, ale model jednego punktu
w komórce nie umie go opisać nawet po podaniu właściwej bazy startowej.
Prawdziwy model z oboma położeniami motywu ma błąd numerycznie zerowy.
To potwierdza ograniczenie klasy modelu na tej kontroli; **nie dowodzi,
że właśnie taki motyw występuje w TTMAPP**.

Nowa statystyka nie daje ogólnej poprawy. Przykład r48, podział góra/dół,
liczba okien ponad progiem, na 192 okna każdego przypadku:

| Kontrola | Q | Z przy σ1.2 | Okna z progiem Q/Z |
| --- | ---: | ---: | ---: |
| Idealna sieć | 176 | 176 | 176 |
| Błąd .6 px | 154 | 133 | 177 |
| Błąd 1.2 px | 0 | 0 | 178 |
| Brak 30% | 112 | 112 | 117 |
| Błąd 1.2 px i brak 30% | 0 | 0 | 118 |
| Dwupunktowy motyw | 46 | 46 | 129 |
| Niezależne rzędy | 0 | 0 | 179 |
| Losowe punkty | 0 | 0 | 171 |

To wyniki otoczeń, nie przypisania molekuł, powierzchnie lub liczby domen.
Brak kalibracji jest oddzielony od niespełnienia kryterium. W innych
podziałach niezależne rzędy nadal potrafią przejść sprawdzian — przy r48
i podziale lewo/prawo Q dopuszcza 2/192, Zσ1.2 1/192. Wszystkie promienie,
podziały i σ są w CSV; tabela nie jest wyborem wariantu do aplikacji.
Kontrola pustej przerwy nadal może przechodzić ocenę sieci: nie jest to
sprawdzian obecności materiału i nie zastępuje osobnego wątku pokrycia.

## TTMAPP: co da się rozstrzygnąć

Po zamrożeniu pomiarów określono położenie okien względem częściowych
referencji. „Jedno wnętrze” oznacza ≥80% wszystkich centrów okna w jednym
znanym obszarze; „mieszane” — ≥20% w każdym z co najmniej dwóch obszarów.
Na dokładnej granicy 80/20 pierwszeństwo ma pierwsza kategoria. Pozostałe
okna mają **brak rozstrzygnięcia**, nie etykietę nieporządku. Spośród 26136
ocen TTMAPP 2157 należy do pierwszej kategorii, 501 do drugiej; te liczby
liczą osobno trzy podziały tych samych geometrycznych otoczeń.

W r48, podział góra/dół: mediana RMSE w jednym znanym wnętrzu **2.29 px**,
w otoczeniach mieszanych **4.24 px**, w nierozstrzygniętych **4.72 px**.
Mieszanie struktur ma znaczenie, ale błąd pozostaje także we wnętrzach.
Kategoria „jedno wnętrze” nie gwarantuje idealnej jednorodności ani
dokładnej granicy referencji; porównanie jest opisowe, nie przyczynowe.

Mniejsze otoczenia mają mniej błędu, ale często za mało centrów. Dla
podziału góra/dół i jednego znanego wnętrza:

| Promień | Dostępne dopasowania / okna | Mediana RMSE dostępnych | Ponad próg Q / Zσ1.2 |
| --- | ---: | ---: | ---: |
| 24 px | 72/333 | 1.40 px | 0 / 2 |
| 36 px | 203/234 | 1.93 px | 76 / 74 |
| 48 px | 147/152 | 2.29 px | 37 / 35 |

Nie wybieramy promienia 36 na tej podstawie: zbiory okien i progi różnią
się, a dostępność selekcjonuje łatwiejsze przypadki. Pełna ocena wymaga
nowego zamrożonego protokołu. Nowe wyniki otoczeń nie są porównywalne
z wcześniejszymi 279/1678 przypisaniami molekuł lub zerem krawędzi.

Sprawdzono także niezależne od sieci lokalne ekstrema pasmowego sygnału
obrazu w promieniu 3 px od oznaczeń. To diagnostyka wyglądu, **nie pomiar
rzeczywistej niepewności centrów**. Na kontroli celowo przesuniętych
oznaczeń taki ruch zmniejsza medianę błędu względem zachowanego modelu
o .59 px (r48, góra/dół); na identycznych centrach z fizycznie przesuniętymi
molekułami nie daje poprawy. W znanych wnętrzach TTMAPP pogarsza ją
o .83 px. Nie wspiera to prostej korekty „przesuń do ekstremum”. Nie
wyklucza błędu bboxów: wygląd molekuły może mieć kilka ekstremów, a sam
dopasowany model może być błędny. Oryginalnych oznaczeń nie zmieniono.

## Wniosek i następna próba

Kolejny krok w 19 powinien zbadać **proponowanie kilku możliwych baz oraz
sprawdzenie ich na rzeczywiście nowych powtórzeniach w dwóch kierunkach**.
Należy odróżniać prawdziwy okres od jego wielokrotności, zachować osobną
część oceny po wyborze kandydata i kontrolować liczbę niezależnych rzędów,
nie samą liczbę punktów. Można porównać model jednopunktowy z małym motywem
wielopunktowym, ale jego złożoność też musi być oceniana poza dopasowaniem.

Najpierw trzeba wykazać poprawę na czystej sieci, jitterze, brakach i
motywie oraz utrzymanie odmowy na niezależnych rzędach i losowych punktach.
Dopiero wtedy wrócić do porównania jednego i dwóch modeli granicy. Pusty
pas, ciemny materiał i lokalny szum pozostają osobną próbą sygnału.
Nie potrzeba teraz nowych ramek domen do naprawy ujawnionego problemu
syntetycznego. Referencje nadal służą ocenie, bez narzucania klas lub K.
Następnej próby nie rozpoczęto; nie wybrano metody do programu.

## Odtworzenie i sprawdzenia

Źródła na `prototype/stmdomains-fit-quality`, **`481194a`**;
baza `946cfb4`. Polecenie: `bash stmdomains/prototypes/run-fit-quality.sh
/tmp/nowa-diagnoza` (w jednym wierszu). Wymagane lokalne poprzednie artefakty
i środowisko netcat. HTML, CSV i wykresy są samodzielne.

- 23 sprawdzenia liczbowe: idealna sieć przy prawdziwej bazie startowej,
  przesunięcia i permutacje, propozycje/dopasowanie tylko z części uczącej,
  minimum punktów oraz pełne pole generatora obrotu.
- 54 deterministyczne odtworzenia generatora; niezależny audyt wykrył
  brakujące punkty w kontroli 30°, poprawiono zasięg siatki i ponowiono
  pomiary nowych kontroli bez zmiany kalibracji. Ocena końcowa dotyczy poprawki.
- **97 obrazów, 68184 ocen i 272736 decyzji** odtworzone dokładnie z blokadą
  odczytów referencji. Nie odtwarzano całego wcześniejszego łańcucha metod.
- Niezależny przegląd: 30000 porównań najbliższego węzła z szerszym
  przeszukiwaniem, 24 inwarianty; zagęszczenie całkowania 16×16→64×64
  na 218 oknach nie zmienia żadnej decyzji. To kontrola wycinka, nie wszystkich okien.
- Podgląd QtWebEngine: 42 obrazy, scenariusze, kryteria i rozdzielenie
  dopasowania/oceny; **108 kontroli**, bez błędów JS (`browser-verification.json`).
  Zrzut i wykres obejrzano. Składnia Python/Bash sprawdzona, wrapper
  wykonany etapami. Nie testowano produkcyjnego GUI, nie dodano zależności.

CPU, cztery procesy po jednym wątku. Końcowe etapy pomiarów: kalibracja
4.24 s, TTMAPP 7.18 s, syntetyki 10.21 s; odtworzenie 20.74 s. Maksymalny
RSS procesu 118808 KiB, nie łączny szczyt. Czasy nie obejmują generowania,
oceny referencyjnej i podglądu. Bez GPU. W Git dokumentacja i źródła prototypu
na osobnych gałęziach; dane, obrazy i duże wyniki lokalnie w `.scratch/`.
Brak wymaganych zmian wspólnych modułów.

Kopia lokalna: **247 plików / 108012599 B**, wszystkie sumy SHA-256
zgodne; następnie dopisano `copy-verification.json`. Link `previous`
prowadzi względnie do `../disjoint-models-material`.
