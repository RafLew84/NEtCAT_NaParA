# Issue 19 — skala i podparcie kryterium porządku ACF

Data: 2026-10-26. Kontynuacja [próby lokalnego grafu](local-feature-graph-trial.md)
na polecenie „wykonaj kolejne badanie”. **Badanie wykonane; issue 19
pozostaje `claimed`, do omówienia. Nie przyjęto metody do aplikacji.**

**Wniosek:** większe okno odzyskuje część pomijanych fragmentów TTMAPP,
także w RED/YELLOW, ale może łączyć rozłączne płaty przez pustą przerwę.
Samo usunięcie odbicia brzegu nie rozwiązuje problemu. Przy dotychczasowym
oknie około połowę miejsc w znanych wnętrzach odrzuca warunek drugiego
kierunku widma. Pozostają również błędy zachowanych podziałów wyglądu.

Źródła: **`prototype/stmdomains-acf-scale-support`, `2ccf9ad`**, baza
`1ae0706`. Nie scalać prototypu do aplikacji. Dokumentacja:
`domains/acf-scale-support-trial`, baza `e095bc4`.
[Manifest](acf-scale-support-manifest.json).

Samowystarczalny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/acf-scale-support/index.html`.
Zakładki: „Jedna sieć i rozmiar okna”, „Szum i pasy”, „Granice i ucięcie”,
„Pełne TTMAPP”. Kliknięcie miejsca pokazuje okno, podparcie, wynik ACF,
próg oraz powody odmowy. Okręgi oznaczają centra, krzyżyki próbki siatki.
Podgląd zawiera wszystkie 24 klatki TTMAPP i wszystkie 34 kontrole
z uprzednio ustalonego ziarna 2701; obliczenia obejmują wszystkie 228 obrazów.

## Protokół przed oceną

- **24 całe klatki TTMAPP i 204 kontrole**, 34 przypadki × sześć ziaren.
  Wszystkie te dane były już oglądane; to diagnoza rozwojowa,
  bez niezależnej walidacji na nowym zbiorze.
- **32 warianty bramki**: promień 16/24/36/48 px × cztery oceny ACF
  × wymagane zmierzone podparcie okna 50/80%.
- Dla każdego wariantu zachowano osiem baz cech/miejsc
  (FFT/EWT/FCN/DINO × siatka/centra), każdą z zapisanym HDBSCAN
  oraz grafem skali 4. Graf 4 to wcześniej ilustrowana stała próba,
  nie ustawienie wybrane na podstawie nowego wyniku.
- Razem **512 nowych konfiguracji detektora**, 64 kontrole maksymalnego
  zakresu bramki i 16 zachowanych wyników początkowych: **592 konfiguracje**.
  Kontrola zakresu daje wszystkim miejscom jedną grupę wyglądu i stosuje
  samą bramkę oraz łączność. Nie jest detektorem domen.
- Cechy, PCA, etykiety wyglądu, podparcie tych cech i reguły przestrzenne
  pozostają stałe: minimum cztery miejsca siatki albo osiem centrów.
  Nie wykonywano treningu, ponownego grupowania ani zadawania liczby domen.
- Przetwarzano całe obrazy. Progi i wszystkie predykcje zapisano
  i zahashowano przed odczytem masek oceny.

Ramki użytkownika służą tylko ocenie gotowych wyników. W ich wnętrzach
jest **1678 centrów**: BLACK 1303, RED 101, YELLOW 274; odpowiada im
1916 miejsc siatki. Poza ramkami nie znamy prawdy referencyjnej.
Kolory oznaczają głównie różne orientacje jednej sieci, nie zadane klasy.

## Co zmieniono i co pozostało stałe

| Wariant ACF | Zasada |
| --- | --- |
| `windowed` | Dotychczasowa autokorelacja z oknem Hanninga i odbiciem poza brzegiem obrazu |
| `overlap` | Dotychczasowa korelacja Pearsona z lokalnym odjęciem średniej na nakładających się częściach; nadal odbity brzeg |
| `measured35` | Pearson wyłącznie z par rzeczywiście zmierzonych pikseli; przesunięcie wymaga co najmniej 35% nominalnej powierzchni okna w parach |
| `measured65` | Ta sama reguła, ale co najmniej 65% nominalnej powierzchni okna w parach |

Nowy Pearson używa liniowych korelacji FFT z maską pomiaru oraz sumami,
średnimi i wariancjami obliczanymi osobno dla każdego przesunięcia.
Konwencję korelacji opisuje [dokumentacja SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlate.html).
Implementację sprawdzono także bezpośrednim sumowaniem par pikseli.

Zachowano filtr obrazu sigma 3, przedział przesunięć 6–24 px, lokalne
maksima, wymaganie dwóch niekolinearnych wektorów (sinus kąta ≥0.35),
energię >1e-12 oraz **widmowy wskaźnik drugiego kierunku ≥0.25**.
Energia i widmowy wskaźnik nadal pochodzą z dotychczasowego, odbitego
okna o badanym promieniu. Nowy wariant zmienia wyłącznie dowód Pearsonowski;
nie deklarujemy, że cały tor przestał używać odbicia.

Każdy próg to kwantyl 0.999, według tej samej reguły, na siatce tych samych
18 znanych kontroli negatywnych z ziaren 1701–1703, po sprawdzeniu podparcia
i drugiego kierunku. Jeden próg obowiązuje oba sposoby próbkowania
i wszystkie rodzaje cech. Nie dobierano go na dodatnich kontrolach
ani TTMAPP. **Zmiana skali obejmuje ponowną kalibrację tą stałą regułą**,
nie porównanie przy tej samej liczbowej wartości progu: przykładowo
`windowed`, podparcie 50%, daje 0.3608 przy r24 i 0.2481 przy r48.

## TTMAPP: dostępność wyniku rośnie, poprawność nie nadąża

Kontrola maksymalnego zakresu, `windowed`, podparcie ≥50%:

| Promień | Siatka: molekuły / 1678 | BLACK / RED / YELLOW | Centra: molekuły / 1678 | BLACK / RED / YELLOW |
| --- | ---: | --- | ---: | --- |
| 24 px | 98 (5.8%) | 98 / 0 / 0 | 34 (2.0%) | 34 / 0 / 0 |
| 36 px | 210 (12.5%) | 190 / 2 / 18 | 97 (5.8%) | 97 / 0 / 0 |
| 48 px | 430 (25.6%) | 301 / 11 / 118 | 320 (19.1%) | 245 / 7 / 68 |

To pokazuje ograniczenie skali dotychczasowej bramki, ale nie dowodzi
odnalezienia całych domen. Liczby dotyczą przypisanych oznaczeń,
nie powierzchni materiału. Przejście r24 → r36 → r48 opisuje jeden
ustalony rodzaj ACF, bez podmieniania cech lub wybierania innego modelu.

Przy zapisanym **FCN/siatka/HDBSCAN**, r48 `windowed` daje te same
430 przypisań, lecz błędnie rozdziela **45.7%** par tej samej referencji
i scala **38.8%** par różnych referencji. Z grafem 4 zostaje 414 przypisań,
z błędami odpowiednio **45.8% / 38.2%**. Te metryki są warunkowe względem
przypisanych par. Wcześniejsze zerowe mianowniki dla różnych referencji
oznaczały brak pomiaru scalenia, a nie poprawny podział.

Największa liczba przypisań w całym przeglądzie to **522/1678 (31.1%)**
przy r48 `measured65`, podparcie 50%. To opis maksimum po ocenie,
**nie wybór ustawienia**: wariant traci dużą część poprawnej jednej sieci,
przepuszcza fragmenty losowych skupisk i scala granice. Dla FCN/HDBSCAN
na siatce ma 70.3% błędnie scalonych par różnych referencji.

## Kontrole ujawniają koszt większego okna

Wyniki jednej sieci poniżej używają znanych ziaren 2701–2703.
Kontrola maksymalnego zakresu oddziela bramkę od zapisanych błędów wyglądu.

- `windowed`, siatka, r24/r36/r48: **95.3/96.1/91.0%** przypisanych
  molekuł i po jednej części na obraz. Na sześciu całkowicie negatywnych
  rodzajach kontroli, wszystkich sześciu ziarnach, brak końcowych
  fałszywych przypisań tych trzech wariantów.
- Mimo tego **r48 łączy dwa rozłączne płaty przez pustą przerwę**:
  na siatce przypisuje 96/96 ocenianych miejsc przerwy w trzech ziarnach,
  daje jedną część i 100% scaleń. r24 i r36 zachowują dwie części,
  0/96 fałszywych miejsc i zero scaleń. Całkowicie negatywny obraz
  oraz puste miejsce obok uporządkowanego materiału to różne kontrole.
- `measured65`, r48: jedna sieć zachowuje tylko **54.3%** molekuł
  na siatce i **47.3%** przy centrach. Na siatce pojawia się osiem
  fałszywych miejsc w losowych skupiskach (dwa obrazy po cztery),
  a w nieuporządkowanym pasie między domenami 72/96 miejsc z trzech ziaren.
- Wynik zależy też od miejsca pobrania okna: małe r16 `windowed`
  daje 95.3% jednej sieci na siatce, lecz **0% przy centrach molekuł**.
  To ograniczenie lokalnej oceny i jej kalibracji, nie brak molekuł w danych.
- Zapisany FCN/siatka/HDBSCAN z r48 `windowed` nadal dzieli pojedynczą
  sieć na 2/2/2 części; graf 4 daje 6/5/5. Lepsza dostępność bramki
  nie naprawia zachowanego podziału wyglądu.

**Żadna z 512 nowych konfiguracji detektora nie spełnia wszystkich
dotychczasowych warunków rozwojowych.** Nie ma kwalifikacji do odbioru
ani benchmarku całych 268 klatek.

Osobny, słabszy warunek dla samej bramki — zero fałszywych końcowych
przypisań na sześciu całkowicie negatywnych przypadkach oraz ≥90%
pokrycia jednej sieci w każdej z dwóch grup ziaren — spełnia 17/64
kombinacji bramka/miejsca. Nie obejmuje on rozdzielania granic i nie jest
odbiorem metody. Żaden wariant wymagający 80% podparcia okna go nie spełnia;
wykluczenie brzegu zabiera zbyt wiele miejsc w tych kontrolach.

## Dlaczego miejsca są odrzucane

Pierwszy niespełniony warunek, w kolejności: podparcie, energia,
drugi kierunek, ACF. Przyczyny mogą współwystępować; pełne liczniki
każdego warunku i ich maski są zapisane osobno.

| Miejsca i wariant | Mianownik | Mało pomiaru | Energia | Drugi kierunek | ACF po pozostałych warunkach | Przechodzi ACF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Siatka, r24 `windowed` | 1916 | 0 | 0 | 953 | 798 | 165 |
| Siatka, r48 `windowed` | 1916 | 27 | 0 | 977 | 402 | 510 |
| Centra, r24 `windowed` | 1678 | 0 | 0 | 835 | 692 | 151 |
| Centra, r48 `windowed` | 1678 | 8 | 0 | 877 | 325 | 468 |

To ocena miejsc we wnętrzach częściowych referencji przed ograniczeniami
cech wyglądu, łącznością i minimalną wielkością fragmentu. Dlatego np.
151 przejść ACF nie oznacza 151 końcowych przypisań molekuł.

Przy r24 próg 50% podparcia nie odrzuca żadnego z tych miejsc.
Usunięcie odbicia brzegu z Pearsona nie daje zatem prostego rozwiązania
odmów. Większa skala zmniejsza część odmów ACF, ale około połowy miejsc
nadal nie przechodzi wymagania drugiego kierunku. **To wskazanie konkretnej
hipotezy do sprawdzenia**, nie dowód, że cały ten warunek można usunąć:
dotąd chronił także przed pasami skanowania.

## Sprawdzenia, koszt i odtworzenie

- **5836** bezpośrednich kontroli przesunięć: maski z dziurami, narożnik,
  pełne okno i stały sygnał. Maksymalny błąd Pearsona **6.42e-13**,
  liczby par zgodne dokładnie.
- **912/912** odtworzeń dotychczasowych wyników r24/r36 dokładnych;
  cztery stare progi kalibracji odtworzone dokładnie.
- **3648/3648** zachowanych wyników początkowych zgodnych w trzech
  tablicach; 228 starych i 228 nowych plików predykcji zgodnych z hashami.
  Nie przeliczano modeli, PCA, HDBSCAN ani grafu.
- **864** porównania tablic ACF siatki oraz **7104** porównania wyników
  siatki identyczne po usunięciu samych oznaczeń molekuł.
- Progi, kod analizy i predykcje zgodne z zapisanym stanem po ocenie.
  **92 kontrole QtWebEngine**, bez błędów JavaScript i przepełnienia
  poziomego. Obejrzano podgląd i wykres PNG.
- Składnia Python/Bash, linki, manifesty oraz `git diff --check`.
  To sprawdzenia eksperymentu; nie testy produkcji lub natywnego GUI.

CPU, bez GPU i nowych pakietów: cztery procesy, po jednym wątku BLAS/OpenMP.
Przygotowanie ACF **429.29 s**, predykcje **18.37 s**, ocena **30.57 s**.
Największy zanotowany RSS pojedynczego procesu przygotowania 125004 KiB
(około 122 MiB); nie zmierzono łącznego szczytu wszystkich procesów.
W trakcie przygotowania poprawiono reprezentację pustych list centrów;
12 takich rekordów odtworzono przed kalibracją/oceną, dodatkowe **12.11 s**.
Nie zmieniono protokołu, parametrów lub metody po obejrzeniu wyników.

Artefakt: **479 plików / 425534929 B**, kopia zweryfikowana SHA-256.
Zawiera pełne tablice ACF/predykcji, powody odmów, `controls.csv`,
metryki JSON, protokół, kalibrację, HTML, PNG/PDF i weryfikację.
Względne symlinki wymagają zachowania wcześniejszego katalogu
`.scratch/local-feature-graph/` i jego zależności. Sam HTML jest samowystarczalny.

Runner: `stmdomains/prototypes/run_acf_scale_support.sh` i opis
`README-acf-scale-support.md` na gałęzi prototypu. Etapy wykonano osobno,
wrapper sprawdzono składniowo. Dane i wyniki pozostają poza Git.

## Następny krok

Najbliższe ograniczone badanie powinno dotyczyć **warunku drugiego
kierunku**: kiedy uporządkowane rzędy molekuł mają jeden dominujący
kierunek widma i jak odróżnić je od samych pasów skanowania lub rzędów
bez wzajemnego uporządkowania. Potrzebna jest jawna ablacja tego warunku
i kontrolowane zmiany kontrastu między rzędami, przy stałej reszcie toru.
Nie wystarczy usunąć próg po obejrzeniu TTMAPP.

Zachować kontrole pustej przerwy i nieuporządkowanego pasa: dowód porządku
w sąsiedztwie nie może automatycznie oznaczać porządku w jego środku.
Duże okno samo tego nie zapewnia. Nawet lepsza bramka nie rozwiązuje
podziału wyglądu ani zależności grafu od początku siatki z poprzedniej próby.

Opisaną próbę wykonano następnie: [warunek drugiego kierunku](second-direction-trial.md).
Odzyskanie rzędów po wyłączeniu warunku wiąże się z przyjmowaniem rzędów
o losowych fazach; nie wybrano metody. Treningu 20–23 nie rozpoczęto.
**19 pozostaje `claimed`**; zapisane wyniki służą dalszemu omówieniu.
