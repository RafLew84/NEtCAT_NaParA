# E2 — treść rVAE pomaga wybiórczo, nie naprawia detektora

Wykonanie 10/11 listopada 2026, `ml_domain`, baza `6742e13`, środowisko `netcat`.
**E2 zakończone. Następne E3: wpływ jasności, kontrastu i normalizacji.**
Nie potwierdzono ogólnej hipotezy, że wystarczy usunąć kąt z rVAE. Treść
pomaga w części prób orientacji, ale pogarsza relacje na granicy przesunięcia.
Nie uzyskano ustawienia pozwalającego wiarygodnie wykrywać domeny STM.

[Protokół przed próbą](ml-ae-rvae-e2-protocol.md),
[manifest](ml-ae-rvae-e2-manifest.json), [plan](ml-ae-rvae-experiments.md).

## Obrazy i porównania do obejrzenia

Lokalna przeglądarka: `.scratch/ml-e2-20261110/index.html`.
Wykresy: `.scratch/ml-e2-20261110/plots.html`.

```bash
xdg-open .scratch/ml-e2-20261110/index.html
```

105 obrazów; centra molekuł lub jawna siatka, kolory domen, szare odmowy,
wybór odczytu/ziarna/solvera, cech rzeczywistych lub tasowanych. Domyślnie
TTMAPP 259, centra, transdukcja, treść rVAE, ziarno 20261101, FH, **H_M1**.
H_M1 wyłącza miękkie progi ACF/widma, zachowując ważność danych i minimum:
to widok diagnostyczny, nie wybrana konfiguracja detektora. A1S1M1 oznacza
pełną dawną bramkę. Kliknięcie punktu pokazuje także wyłączone przyczyny odmowy.

Miary domen dotyczą całego własnego ocenialnego zbioru. Tabela odległości
obok obrazu korzysta ze **wspólnej dostępności wszystkich 15 odczytów**;
jej mianownik jest inny i podany jawnie. Brak krzywej oznacza brak jednej
klasy par, nie potwierdzenie dobrego rozdzielenia. Kolory nie śledzą domen
między klatkami. Kąt rVAE nie jest tu skalibrowanym kątem fizycznym.

Krótki odbiór ręczny:

1. W ustawieniu domyślnym przełączyć **treść rVAE ↔ treść+kąt ↔ sam kąt**,
   zachowując klatkę, ziarno i FH. Porównać większe fragmenty i drobne podziały.
2. Przełączyć H_M1 → A1S1M1: znane wnętrza centrów pozostają bez przypisań.
   Wyłączyć punkty, obejrzeć sam obraz, następnie kliknąć wybrane centrum.
3. Dla syntetyku `two_orientations` wybrać centra, transfer, H_M1 i porównać
   wszystkie trzy ziarna treści z pełnym rVAE. Zmiana FH→MWS pokazuje, że
   korzystne odległości nie gwarantują tego samego poprawnego podziału.
4. W `phase_boundary` przełączyć na siatkę. Treść nadal scala domeny.
   W grafie centrów tej kontroli nie ma **ocenialnych** par różnych domen;
   krzywa ROC/AP pozostaje niedostępna, choć całe domeny można oceniać.
5. Porównać „Oryginalne cechy” z kontrolą tasowania i otworzyć wykresy.
   Dla `orientation_8deg`, centrów i FFT porównać L2 z adapted.

Odbiór użytkownika pozostaje otwarty. Sprawdzenia techniczne są opisane niżej.

## Co zostało policzone

Jak E1: 24 obrazy STM i 81 syntetyków, skala 48, dwa reżimy, dwa własne grafy
i FH/MWS. Odczyty: AE, pełne rVAE, treść rVAE, sam kąt, FFT, fotometria
oraz geometria ACF. Cztery odczyty modeli mają po trzy ziarna, bazy po jednym:
15 odczytów na reżim, 6300 zestawów obraz–odczyt–sampler.

Fotometria to `[1,mean,std]` tych samych znormalizowanych wejść 64×64.
Geometria opisuje kierunki i długości dwóch kandydatów ACF w sposób
niezależny od ich znaku/kolejności, wraz z ocenami ACF/widma. To miary
diagnostyczne, nie nowy model zwalidowanej sieci. Braki pozostają jawne.

**60 adapterów:** 28 historycznych identycznych, 32 nowych na dokładnie
dawnych fit ID. Wszystkie dostępne. Bez inferencji lub treningu enkoderów,
zmiany progów odmowy, etykiet, solverów i krawędzi. **5880 dawnych wyników
odtworzono bitowo identycznie**; niezależnie porównane 6272 agregaty domen
odpowiadają E1 bez różnic. W transdukcji fit od początku obejmował całą
akwizycję, więc nadal jest to ocena opisowa in-sample.

Odległości: native → jednostkowe L2 → PCA i mediana treningowa (adapted).
Pięć wcześniej ustalonych permutacji całych wektorów w obrębie obrazu,
samplera, reżimu i wzorca dostępności. Brak tasowania etykiet, grafów lub
refitu. W każdej z 420 grup wszystkie15 odczytów korzysta z tej samej
permutacji. Pięć tasowań służy relacjom; pierwsze także podziałowi domen.

Powstało **226800 ocen relacji, 100800 ocen domen i 25200 widoków**.
To kombinacje tych samych danych, nie niezależne pomiary. Wszystkie wyniki
zamrożono przed nową oceną etykietami. Pełne dystanse/permutacje zapisano do NPZ.

## Czy usunięcie kąta pomaga?

Na kontroli dwóch orientacji — tak, ale nie wystarcza do ogólnej poprawy.
Poniżej AUC/AP, mediany trzech ziaren **modelu**, przy połączeniu par
z trzech realizacji syntetyku: **transfer, wspólne relacje, adapted**.
Klasa dodatnia to różne domeny; większy dystans powinien wskazywać granicę.

| Kontrola i sampler | Pary tej samej / różnych domen | Pełne rVAE: AUC / AP | Treść: AUC / AP |
| --- | ---: | ---: | ---: |
| Dwie orientacje, siatka | 564 / 66 | 0.505 / 0.112 | **0.617 / 0.181** |
| Dwie orientacje, centra | 1092 / 21 | 0.989 / 0.721 | **0.995 / 0.823** |
| Przesunięcie, siatka | 564 / 66 | **0.545 / 0.218** | 0.426 / 0.088 |
| Różny rozstaw, siatka | 564 / 66 | **0.737 / 0.167** | 0.606 / 0.120 |

Baza AP wynosi 0.1048 dla wierszy siatki i 0.0189 dla dwóch orientacji
centrów. AUC i AP odpowiadają różnym aspektom silnie niezrównoważonych par.
Dla dwóch orientacji treść poprawia AUC pełnego rVAE we wszystkich trzech
ziarnach. AP nie rośnie zawsze: na siatce dla ziarna 20261101 spada
z 0.223 do 0.191. Na siatce każde ziarno treści przewyższa swoje pięć
tasowań pod względem AUC i AP. Przy przesunięciu
pogarsza wynik we wszystkich trzech transferowych ziarnach. Nie odwracaliśmy
kierunku klasyfikacji po zobaczeniu AUC<0.5.

Podział domen pokazuje ograniczenie tego zysku. W centrach dwóch orientacji,
w transferze, treść+FH rozdziela domeny poprawnie w **2/3 ziaren**, pełne rVAE w 0/3.
Treść+MWS nadal scala je we wszystkich ziarnach. Na siatce treść i pełne
rVAE nadal scalają dwie orientacje oraz granicę przesunięcia przy H_M1.
Wysoki ranking odległości nie wystarcza do poprawnych relacji progowych
i całego podziału grafu.

Sam kąt też nie jest zawsze zły: dla centrów różniących się o 8° w transdukcji
ma AUC 0.948, pełne rVAE 0.917, treść 0.882. To zdolność rozróżnienia tej kontroli,
nie walidacja fizycznego pomiaru orientacji przez rVAE.

## Normalizacja, PCA i proste bazy

W E2 nie wykazano, że PCA jest główną przyczyną słabości rVAE. Na ocenialnych
syntetykach maksymalna zmiana AUC między L2 a adapted wynosiła około 0.019
dla pełnego rVAE i 0.018 dla treści. Większe, dwukierunkowe zmiany zachodzą
przy normalizacji L2, np. treść na transferowej siatce dwóch orientacji:
**native 0.450 → L2 0.614 → adapted 0.617**; na przesunięciu:
**0.496 → 0.416 → 0.426**. Usuwanie amplitudy nie pomaga uniwersalnie.

Jest konkretny wyjątek dotyczący **FFT**: w centrach przy różnicy 8° wynik
L2 ma AUC/AP=1/1, a po PCA transferowe AUC/AP spada do **0.936/0.131**;
w transdukcji do **0.902/0.094**. To mierzalna strata w tej konfiguracji FFT,
nie powtórzenie ogólnej hipotezy o PCA innych modeli. Do dalszego odczytu
warto zachować FFT bez tej redukcji, ale E2 nie stroi nowego detektora.

Geometria ACF i FFT rozróżniają część syntetycznych relacji lepiej niż
AE/rVAE. Na transferowej siatce przesunięcia: AUC geometrii 0.936, FFT 0.883,
treści rVAE 0.426. Geometria nie jest jednak dostępna wszędzie, a jej podział
nadal fragmentuje część domen. Nominalne/ważne okna fit geometrii:
transfer siatka 96/56, centra 113/62; transdukcja 3456/2382 i 4629/3498.
Miary domen uwzględniają utracone miejsca, a wspólne relacje pokazują
wyłącznie przecięcie dostępności. Nie ukrywamy tej różnicy w mianowniku.

Prosta fotometria osiąga AUC 0.904 na siatce dwóch orientacji, lecz 0.705
na ich centrach. To powód do E3: część sygnału może zależeć od jasności
i kontrastu. Nie dowodzi, że każda różnica wysokości obrazu jest zakłóceniem.

## Rzeczywiste STM: mniej scaleń kosztem pokrycia i fragmentacji

**Centra, transdukcja, FH, H_M1**, mediana ziaren, stały mianownik
1354 centrów w konserwatywnych wnętrzach. Błędy par są warunkowe na
przypisaniu i mają różne mianowniki; nie sumują się do 100%.

| Odczyt | Pokrycie wnętrz | Błędne scalenia par | Błędne podziały par |
| --- | ---: | ---: | ---: |
| AE | 98.74% | 91.20% | 14.53% |
| rVAE treść+kąt | 93.50% | 31.36% | 48.07% |
| rVAE treść | 88.63% | 15.98% | 58.80% |
| rVAE kąt | 86.71% | 49.22% | 32.64% |
| FFT | 97.86% | 84.10% | 19.75% |
| Fotometria | 95.64% | 55.23% | 38.37% |
| Geometria ACF | 83.09% | 24.77% | 53.53% |

Rozrzut treści między ziarnami: pokrycie 87.96–90.62%, błędne scalenia
5.46–25.65%, błędne podziały 56.02–60.65%. Treść zmienia rodzaj błędów,
nie naprawia segmentacji. Dla MWS jej pokrycie
spada z 45.35% pełnego rVAE do 34.56%; niższe błędy dotyczą mniejszej
zachowanej części. **Pełna bramka nadal daje 0% pokrycia znanych wnętrz
centrów dla wszystkich odczytów i obu reżimów**. Na siatce transdukcji
pozostaje 0–4/782, w transferze 0/174. To nie jest procent wykrytych molekuł.

Realna referencja relacji jest zbyt uboga na wybór modelu:

| Zakres | Własne pary rVAE: same / różne | Wspólne wszystkich odczytów |
| --- | ---: | ---: |
| Transfer, siatka | 369 / 1 | 346 / 1 |
| Transfer, centra | 593 / 1 | 509 / 1 |
| Transdukcja, siatka | 2136 / 17 | 1866 / 15 |
| Transdukcja, centra | 3117 / 4 | 2710 / 4 |

Choć na wspólnych centrach transdukcji AUC treści ma medianę 0.757 wobec 0.653
pełnego rVAE, porównanie opiera się na **czterech** krawędziach różnych
wnętrz jednej akwizycji. W transferze na jednej. Nie waliduje to lokalizacji
granic ani generalizacji. Nie dodano odległych par w miejsce brakujących
sąsiadów, nieoznaczone obszary nie zostały negatywami.

Na syntetycznych centrach przesunięcia i różnego rozstawu jest odpowiednio
1095/0 i 699/0 ocenialnych par same/różne; ROC/AP=null. Negatywy, np.
niezależne rzędy, nie mają dodatnich domen do takiego ROC. Oceniamy je
osobno przez fałszywe przypisania: treść przy pełnej bramce nadal przypisuje
około 74.5–78.6% miejsc siatki niezależnych rzędów w transferze i 55.0% centrów.
Brak wspartych centrów na szumie nie jest udanym odrzuceniem szumu.
W całej macierzy syntetycznej obie klasy par występują tylko w 4/27
rodzajów kontroli siatki i 2/27 centrów. Pozostałe miary ROC/AP pozostają
niedostępne; nie zastępowano ich zerem.

## Decyzja i następny krok

**E3 pozostaje następnym krokiem, bez nowego treningu.** Sprawdzić na tych
samych wycinkach wpływ niewielkich zmian jasności/kontrastu/gradientu na
cechy i relacje. Zachować treść rVAE jako osobny wariant, ale również pełny
odczyt, AE, FFT i proste bazy. Nie wyłączać globalnie kąta ani bramki.

E2 wykazało lokalny użyteczny sygnał, szczególnie dla orientacji w centrach,
oraz problem przejścia od odległości do domen. Nie wykazało braku informacji
w enkoderach. Mały uczony odczyt E7 nadal ma sens po przejrzeniu relacji
i rozdzieleniu grup. Do mocnych wniosków o rzeczywistych granicach potrzebna
jest referencja z E0; znane klatki nadal są materiałem rozwojowym.
Nie zmieniono metody aplikacji, modeli źródłowych ani ustawień produkcyjnych.

## Odtworzenie i weryfikacja

```bash
conda activate netcat
python -m stmdomains.experiments.e2_run --out .scratch/ml-e2-nowy-przebieg
python -m stmdomains.experiments.e2_readout .scratch/ml-e2-nowy-przebieg
python -m stmdomains.experiments.e2_plots .scratch/ml-e2-nowy-przebieg
python -m stmdomains.experiments.e2_check_gallery .scratch/ml-e2-nowy-przebieg/index.html --out .scratch/ml-e2-nowy-przebieg/browser-check --check-plots
```

Nowy katalog chroni wcześniejsze przebiegi. `edge-metrics.csv` i
`domain-metrics.csv` zawierają pełne agregaty, osobne ziarna/warunki.
Szczegóły każdego obrazu są w gzip, pełne dystanse w 6300 NPZ. Protokół,
kod, źródła, adaptery i wyniki mają hashe. Ponowne sprawdzenie źródeł i E1
potwierdziło brak zmian. Liczebności relacji sprawdzono także niezależnie.

Obliczenia: **222.56 s wall, 222.94 s CPU, 927.7 MiB szczytowego RSS**,
około 986 MiB początkowych artefaktów, poniżej limitu 60 min CPU / 8 GiB.
25 nowych testów E2 PASS; niezależna zgodność ROC/AP ze scikit-learn na 400
zadaniach, błąd ≤ 2.22e−16. Nie znaleziono liczbowego AUC/AP przy brakującej
klasie w żadnym z 60480 agregatów. QtWebEngine: **303 sprawdzenia PASS,
105/105 obrazów, 112/112 figur, 0 błędów JS**. Zapisano siedem zrzutów;
obejrzano m.in. rzeczywiste centra, syntetyki i wykresy. Figury są dostępne
w PNG i SVG, z osobnym manifestem pochodzenia. Odbiór ręczny użytkownika otwarty.
Bez instalacji, pełnej regresji aplikacji i zmian wspólnych; nowe moduły <1000 linii.

Procedury: `experimental-design`, `scientific-critical-thinking`, `matplotlib`.
Źródło procedur: Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M.
(2026), *Scientific Agent Skills: A Library of Procedural Knowledge for Research
Agents*, [doi:10.48550/arXiv.2609.00065](https://doi.org/10.48550/arXiv.2609.00065).
Metadane zweryfikowano w arXiv podczas E2. Nie jest to dowód skuteczności metod STM.
