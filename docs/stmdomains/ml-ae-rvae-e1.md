# E1 — bramka usuwa domeny, ale podział też wymaga poprawy

2026-11-10, `ml_domain`, baza `bbfa417`, środowisko `netcat`.
**E1 wykonane. Następne E2: diagnostyka odczytu cech i relacji.** Samo
poluzowanie bramki przywraca przypisania, lecz nie daje wiarygodnego detektora.
Nie ma obecnie podstaw do wyboru nowych ustawień produkcyjnych ani do
rozpoczynania kolejnego dużego treningu.

[Protokół zapisany przed próbą](ml-ae-rvae-e1-protocol.md),
[manifest wykonania i pochodzenia](ml-ae-rvae-e1-manifest.json),
[plan dalszych eksperymentów](ml-ae-rvae-experiments.md).

## Obejrzenie wyników

Otwórz `.scratch/ml-e1-20261110/index.html`, np. z katalogu repozytorium:

```bash
xdg-open .scratch/ml-e1-20261110/index.html
```

Przeglądarka działa lokalnie, bez serwera. Pokazuje **105 obrazów** i wszystkie
przebiegi: obraz, rzeczywiste centra molekuł z kolorem domeny, szare odmowy,
przełączniki modelu/ziarna, podziału, wariantu i klatki. Kliknięcie molekuły
pokazuje pomiary i wszystkie flagi, z rozróżnieniem decyzji aktywnych,
wyłączonych i zastąpionych prawdą generatora. Można pokazać obraz bez punktów
lub propozycję przed odmowami. Siatka jest osobnym, wyraźnie nazwanym trybem;
jej etykiety nie są przenoszone na molekuły. Kolory/ID nie śledzą domen w czasie.

Proponowany odbiór ręczny:

1. TTMAPP259, centra, transdukcja, rVAE/20261101, FH. Porównać **A1S1M1**
   z **A1S0M1** i **A0S0M1**. Więcej kolorów nie rozstrzyga poprawności.
2. Kliknąć szare i kolorowe centra. Wyłączenie S ma zmienić status decyzji,
   zachowując zapisany pomiar widma. Przeciągnąć suwak i przejść między klatkami.
3. Wybrać syntetyk `two_orientations`, siatkę, historyczny transfer,
   rVAE/20261101, FH. Porównać cztery warianty R…_M…_M1. Obie idealne
   podmiany dają poprawne członkostwo domen; sama idealna maska scala domeny.
4. Wybrać `phase_boundary`: idealne relacje usuwają błędne scalenie także
   przy masce programu. Wybrać `independent_rows`: pełna bramka nadal dopuszcza
   fałszywe domeny. Sprawdzić również `noise` i `stripes` bez bramek.
5. Włączyć transfer TTMAPP: tylko historyczny pas testowy podlega przypisaniu.
   Pozostałe szare centra oznaczają miejsca poza zakresem, nie nieporządek.

To instrukcja odbioru użytkownika, nie deklaracja, że użytkownik go wykonał.
Techniczne sprawdzenia przeglądarki opisuje końcowa sekcja.

## Co policzono i co pozostało stałe

24 obrazy rzeczywiste oraz 81 syntetyków, skala 48 px, dwa własne grafy
(siatka/centra), dwa solvery (FH k=4/MWS), dwa dawne reżimy. AE i rVAE z32
mają po trzy ziarna; FFT jest pojedynczą bazą w każdym reżimie.
**5880 wyników bazowych × osiem bramek = 47 040 ocen**. Dodatkowo na
syntetykach pełne 2×2 relacje/maska × przed/po minimum: **36 288 ocen**.
Łącznie **83 328**, nie tyle niezależnych obrazów czy eksperymentów fizycznych.

A = próg ACF, S = dodatkowy drugi kierunek widma, M = minimum komponentu.
1 włącza decyzję, 0 ją wyłącza. ACF > **0.37948280732455153**, S ≥ **0.25**,
minimum **4 węzły siatki / 8 centrów**. To doprecyzowanie planu według
faktycznego kodu 21. Wyłączenie minimum ustawia 1; przeliczenie spójności
po usunięciu węzłów pozostaje takie samo. ACF sam wymaga dwóch kierunków.
Wsparcie, skończoność pomiarów, dodatnia energia i dostępność cech są obowiązkowe.

Bez treningu, nowej inferencji enkodera, dopasowania adapterów, kalibracji
progów lub nowych etykiet. Odtworzono jedynie brakujące składowe tekstury
z oryginalnych okien 48 px. Wszystkie **420 masek bramki** są identyczne
ze starymi, a największa różnica ACF/FFT wyniosła **0**. Wariant 111 odtworzył
**5880/5880 dawnych podziałów bitowo identycznie**. W transferze rzeczywistym
zachowano zapisane grafy heldout, także ich własne sąsiedztwo centrów.

## Bramka: oba wymagania przepuszczają różne miejsca

Poniżej liczby miejsc z pełnym wsparciem w zakresie danej oceny, ze wszystkich
24 klatek. Nie mnożymy ich przez modele, ziarna ani solvery.

| Zakres | Pełne wsparcie i warunki stałe | Przechodzi A | Przechodzi S | Przechodzi A i S |
| --- | ---: | ---: | ---: | ---: |
| Transfer, siatka | 912 | 80 | 809 | **6** |
| Transfer, centra | 1245 | 147 | 1051 | **9** |
| Transdukcja, siatka | 3456 | 391 | 2934 | **50** |
| Transdukcja, centra | 4629 | 739 | 3667 | **74** |

Na rzeczywistych obrazach nie odrzuca ich brak dodatniej energii czy finite:
warunki stałe przechodzą wszystkie miejsca z pełnym wsparciem w zakresie.
ACF usuwa najwięcej miejsc ogółem, ale dodatkowy filtr widma odrzuca
**665 z 739 centrów**, które przeszły ACF w transdukcji. Obie składowe
działają silnie łącznie. Z pozostałych 74 centrów minimum i fragmentacja
usuwają końcowe przypisania w znanych wnętrzach. Nie można nazwać tego
wyłącznie problemem jednego progu ani wyłącznie minimum.

## Rzeczywiste molekuły: przypisania wracają, jakość pozostaje słaba

Główny liczbowy przykład dla użytkownika: **centra, transdukcja, FH**.
Pokrycie to przypisane centra w znanych konserwatywnych wnętrzach, ze stałego
mianownika **1354**; to nie procent wykrytych molekuł ani IoU domen.
W tabeli mediany trzech ziaren AE/rVAE, FFT bez powielania.

| Model | Pełna bramka 111 | Bez S, A1S0M1 | Bez A i S, A0S0M1 | Błędne scalenia par bez A/S | Błędne podziały par bez A/S |
| --- | ---: | ---: | ---: | ---: | ---: |
| AE | 0% | 35.67% | 98.74% | 91.20% | 14.53% |
| rVAE | 0% | 26.96% | 93.50% | 31.36% | 48.07% |
| FFT | 0% | 35.45% | 97.86% | 84.10% | 19.75% |

Błędy par są **warunkowe na przypisaniu**, z różnymi mianownikami dla scaleń
i podziałów; nie sumują się do 100%. Dla rVAE bez A/S scalenia między ziarnami
wynoszą 17.19–43.38%, podziały 43.18–49.76%. Nie ma stabilnej, kompletnej
segmentacji po samym zniesieniu odmów.

Wyłączenie S też nie przywraca wszystkich rodzajów domen. Przykład rVAE
20261101, A1S0M1: **374/1156** centrów w grupie BLACK, **0/18** RED,
**0/180** YELLOW. Brak ocenialnych par między zachowanymi różnymi domenami
daje `null` błędu scalenia, a nie dowód bezbłędnego rozdzielania.
Nazwy kolorów oznaczają dawne grupy referencji, nie potwierdzone typy fizyczne.

MWS nie rozwiązuje problemu: dla centrów rVAE bez A/S zachowuje medianę
45.35% referencji, przy 12.00% scaleń i 45.20% podziałów. Na głównej siatce
transdukcji FH bez A/S pokrycie rVAE rośnie do 98.59%, ale scalenia/podziały
pozostają odpowiednio 38.55%/31.93%. Historyczny transfer ma znacznie uboższą
referencję: **174 miejsca siatki / 302 centra**, z prawie samą grupą BLACK.
Nie daje mocnego testu wszystkich rzeczywistych granic.

Pełne osiem kombinacji, przed/po i osobne ziarna:
`.scratch/ml-e1-20261110/measurement.csv`; wszystkie kontrole:
`.scratch/ml-e1-20261110/summary.csv`. `null`/puste pole oznacza brak mianownika.

## Idealne wejścia: mechanika działa, ograniczenia zależą od przypadku

Podstawienie prawdy generatora jest diagnostyką uprzywilejowaną. Nie jest
modelem, którego można użyć do nieoznaczonego obrazu. Idealne relacje FH
mają odległości 0/5, MWS siły 1 i jawne odpychanie różnych domen/tła.
Prawdziwa maska oznacza dodatnie domeny, nie całe pole materiału.

Przykład: **rVAE 20261101, transfer, siatka, FH, po minimum**, trzy syntetyki
danego rodzaju. W każdej komórce: pokrycie / błąd scaleń / boundary F1.

| Przypadek | Program/program | Relacje programu + maska idealna | Relacje idealne + maska programu | Oba idealne |
| --- | --- | --- | --- | --- |
| Dwie orientacje | 85.42% / 0% / 0 | 100% / 100% / 0 | 85.42% / 0% / 0 | **100% / 0% / 0.8** |
| Granica przesunięcia | 100% / 100% / 0 | 100% / 100% / 0 | **100% / 0% / 0.8** | **100% / 0% / 0.8** |
| Pusta przerwa | 66.67% / 0% / n/d | **100% / 0% / n/d** | 66.67% / 0% / n/d | **100% / 0% / n/d** |

Dwie orientacje: maska wycina pas i pozornie rozdziela złą propozycję;
przywrócenie całej prawdziwej domeny ujawnia scalenie. Potrzebne są obie
składowe. Granica przesunięcia: maska już przepuszcza miejsca, błędne są
relacje. Przerwa: utrata pokrycia pochodzi z maski; relacje nie wymagają
podmiany w tym przykładzie. Nie ma jednej uniwersalnej przyczyny wszystkich porażek.

**4536/4536** wyników z obiema idealnymi składowymi przed minimum odpowiada
niezależnie policzonym komponentom prawdy na niezmienionym grafie.
To 162 kombinacje obrazu i samplera powtórzone dla zestawów cech/solverów,
nie 4536 niezależnych doświadczeń.
Na siatce pełny oracle zachowuje 100% ocenialnych dodatnich miejsc bez
scaleń/podziałów. F1=0.8 dla granic kontaktowych wynika z odczytu osiowych
krawędzi, wsparcia i pełnego rastra referencji; nie dowodzi usterki solvera.
F1 konturu nie jest przedstawiane dla nieregularnego grafu centrów.

Graf centrów ma rzeczywiste ograniczenia po usunięciu części centrów
w kontrolach `missing_*`:

- `missing_30`: mały fragment dwóch centrów odrzuca minimum 8;
  końcowe pokrycie pełnego oracle 99.22%.
- `missing_50`: rozłączność i małe fragmenty; pokrycie 94.76%, podziały 8.15%.
- `missing_band`: jedna prawdziwa domena staje się dwoma rozłącznymi zbiorami
  po 44 centra; pokrycie 100%, podziały 50.57%. Nie dodawaliśmy krawędzi,
  aby ukryć ten problem.
- `insufficient_field`: brak pełnego wsparcia, więc brak oceny, nie negatyw.

To rozdziela błąd relacji, bramki, ograniczenia grafu i polityki minimum.
Nie ma dowodu, że implementacja FH/MWS sama uniemożliwia odtworzenie domen.

## Negatywy: wyłączenie bramki ma koszt

Przykład rVAE 20261101, transfer, siatka, FH; po minimum. Każdy wiersz
obejmuje trzy obrazy, **192 ocenialne miejsca** znanego negatywu.

| Kontrola | Pełna bramka: fałszywie przypisane | Bez A/S: fałszywie przypisane | Bez A/S: suma domen |
| --- | ---: | ---: | ---: |
| Szum | 0/192 | **192/192** | 3 |
| Pasy | 0/192 | **192/192** | 15 |
| Niezależne rzędy | **151/192** | **192/192** | 3 |

Dla grafu centrów `noise` i `stripes` nie mają miejsc z pełnym wsparciem;
brak przypisań w tych dwóch konfiguracjach nie ocenia skuteczności odmowy.

Przy idealnych relacjach i masce programu niezależne rzędy nadal mają
151/192 przypisań **przed minimum**, jako singletony. Minimum usuwa je
wszystkie. Nie przypisujemy tego sukcesu samej masce ani nie ukrywamy jej
fałszywych akceptacji przez oglądanie wyłącznie końcowego obrazu.

## Decyzja i ograniczenia

**Przejść do E2, następnie E3; nie wybierać jeszcze nowego detektora.**
W E2 rozdzielić treść rVAE od kąta oraz sprawdzić rzeczywiste dystanse
i sposób ich zamiany na relacje grafu, obok AE/FFT i prostej fotometrii.
E1 potwierdza sens diagnostyki bramki, ale nie uzasadnia globalnego wyłączenia
S lub A. E3 sprawdzi zależność tych pomiarów od normalizacji/kontrastu.
Nowy trening pozostaje warunkowy; E7 nadal wymaga przejrzanych relacji i grup.

Wszystkie rzeczywiste obrazy pochodzą z jednej znanej akwizycji rozwojowej.
Nieoznaczone miejsca nie są negatywami. Referencja obejmuje konserwatywne
wnętrza, bez dokładnych konturów ani globalnego IoU. Syntetyki są idealizowane,
a ich ziarna/klatki/okna nie tworzą tysięcy niezależnych doświadczeń.
Wyniki jednej skali 48 px nie rozstrzygają problemu skali fizycznej.
Nie zmieniono metody ani parametrów aplikacji produkcyjnej.

## Odtworzenie i sprawdzenia

```bash
conda activate netcat
python -m stmdomains.experiments.e1_run --out .scratch/ml-e1-nowy-przebieg
python -m stmdomains.experiments.e1_readout .scratch/ml-e1-nowy-przebieg
python -m stmdomains.experiments.e1_check_gallery .scratch/ml-e1-nowy-przebieg/index.html --out .scratch/ml-e1-nowy-przebieg/browser-check
```

Runner wymaga nowego katalogu. Zachowuje snapshot protokołu/kodu, hashe
źródeł, deskryptory, zamrożone warianty bramek, osobne wyniki oracle, metryki
i grafową granicę możliwości. Po obliczeniach ponownie zweryfikowano hashe
użytych źródeł. Modele, wejścia i referencje pozostały bez zmian.
Przebieg: **105.27 s czasu ściennego, 106.07 s CPU, 602 MiB szczytowego RSS**,
około 293 MiB początkowych artefaktów. W granicach ustalonego budżetu.

Testy netcat: **68 różnych przypadków PASS** (20 E1, 14 podział, 24 ocena,
10 tekstura): odtwarzanie natywnych okien, freeze bez prawdy, niezależna
kontrola komponentów i istniejąca regresja. Przeglądarka QtWebEngine:
**162 sprawdzenia PASS, 105/105 obrazów, 0 błędów JS**, trzy zrzuty obejrzane.
Renderer doprecyzowano po próbie numerycznej; osobny `gallery-render.json`
przypina finalny HTML/kod/sprawdzenia, bez zmiany wyników obliczeń.
Kontrole i końcowy bilans są również zapisane w manifeście.
Nowe moduły mają poniżej 1000 linii. Bez instalacji, bez pełnej regresji GUI
aplikacji i bez odbioru ręcznego użytkownika.

Procedury oceny: `experimental-design`, `scientific-critical-thinking`.
Źródło procedur: Kassis i in. (2026), *Scientific Agent Skills: A Library of
Procedural Knowledge for Research Agents*,
[doi:10.48550/arXiv.2609.00065](https://doi.org/10.48550/arXiv.2609.00065).
