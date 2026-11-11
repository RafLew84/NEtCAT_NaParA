# E7 — uczony odczyt: syntetyki → znane STM

11 listopada 2026, `ml_domain`, baza `630f29d`, środowisko `netcat`.
[Protokół](ml-ae-rvae-e7-protocol.md), [manifest](ml-ae-rvae-e7-manifest.json),
[plan](ml-ae-rvae-experiments.md).

## Wynik

**Wykonano wybraną przez użytkownika osobną próbę E7: nadzór syntetyczny
i zastosowanie do znanych obrazów STM. Nie uzyskano stabilnego detektora domen.**
Uczony odczyt rVAE niemal idealnie rozróżnia oceniane pary syntetyczne,
lecz nie daje przewagi domen nad uczoną geometrią we wszystkich miarach.
Na STM wynik silnie zależy od ziarna: część modeli scala różne wnętrza,
inne tracą wiele przypisań. Nie jest to dowód, że AE/rVAE nie zawierają
informacji. To ograniczenie konkretnego nadzoru, odczytu i sposobu
zamiany relacji na domeny.

Najważniejsze nowe ustalenie: **wysoka jakość ocenianych par nie gwarantuje
dobrych domen przy zachowanej regule skali FH i kwantyli MWS**.
Do tego syntetyczny trening zawiera tylko 45 krawędzi różnych domen,
wyłącznie przy zmianie orientacji. Nie reprezentuje pełnego zadania STM.
Pełna bramka nadal daje 0% pokrycia znanych wnętrz na centrach.

Nie wybrano nowych ustawień aplikacji ani zwycięskiego checkpointu.
Nadzorowany E7 na rzeczywistych etykietach STM oraz krzywa ilości danych
pozostają niewykonane. E4/E6 nadal są warunkowe.

## Co obejmowała próba

- 81 nowych syntetyków train i 81 validation: 27 przypadków w każdej
  z trzech grup generatora na rolę. Powiązane warianty pozostają razem.
- 24 pełne klatki TTMAPP z jednej znanej akwizycji rozwojowej. Referencja
  obejmuje 54 częściowe wnętrza na 18 klatkach; sześć pozostałych klatek
  nie dostarcza tej oceny jakości. Brak niezależnego testu STM.
- Sześć zamrożonych enkoderów transferowych issue21: AE32 i pełne rVAE34,
  po trzy ziarna. Enkodery i normalizer były wcześniej uczone na STM;
  **tylko nowy nadzór odczytu pochodzi wyłącznie z syntetyków**.
- Osiem regresji logistycznych: geometria ACF, geometria z fotometrią,
  geometria z AE oraz geometria z rVAE. Identyczne kodowanie par,
  L2/C=1, ważenie klas i grup, bez szukania parametrów.
- Centra molekuł, skala 48, oryginalny graf, FH k=4 i MWS; H_M1 oraz
  pełna bramka A_fixed_M1. Brak ponownego wykrywania molekuł.

Obie części syntetyczne to nowe realizacje tej samej rodziny geometrii,
głównie z innym szumem. Nie są niezależnymi strukturami lub akwizycjami.
Pary, powiązane warianty i kolejne klatki nie są niezależnymi replikami.

Wagi klasyfikatora, scaler, kalibrację oraz wszystkie predykcje zamrożono
przed odczytem referencji walidacyjnej/STM przez ocenę. Fit używa wyłącznie
trzech grup train; kalibracja obejmuje 22 296 wspólnych krawędzi train,
również bez etykiety relacyjnej. Nieoznaczonych miejsc nie uczono jako
negatywów. Wszystkie osiem fitów osiągnęło zbieżność w 36–76 iteracjach.

## Relacje: wysoka miara syntetyczna ma wąski zakres

Train: **18 840 par tej samej domeny i 45 różnych**. Validation:
**18 920 tej samej i 45 różnych**. W każdej grupie jest 15 par różnych:
7 z `two_orientations` i 8 z `orientation_8deg`.
`phase_boundary` i `different_spacing` mają odpowiednio 1095 i 699
ocenianych walidacyjnych par tej samej domeny, **zero lokalnych par różnych**.
Niepewny pas granicy wyklucza je z relacyjnej oceny. Nie oznacza to,
że obrazy nie zawierają granic; jakość całych instancji jest oceniana osobno.

Na wspólnych parach validation AP dla różnych domen wynosi:
geometria 0.99394, geometria+fotometria 0.99544, AE 0.94236–0.98691,
rVAE 1.0 dla trzech ziaren. Przy stałym progu 0.5 wszystkie modele
rozpoznają 45/45 różnych par. Błędnie rozcinają odpowiednio 11, 10,
6–15 i 1–5 spośród 18 920 par tej samej domeny.
To udana separacja tych przykładów, **nie 100% wykrywania domen**.

Na STM wszystkie osiem modeli oceniło te same **2722 pary tej samej domeny
i tylko 4 pary różnych domen**. Przy progu 0.5:

| Uczony odczyt | Trafione różne / 4 | Błędnie uznane za różne / 2722 |
|---|---:|---:|
| Geometria | 0 | 134 |
| Geometria + fotometria | 1 | 666 |
| Geometria + AE, 20261101 | 3 | 618 |
| Geometria + AE, 20261102 | 4 | 1246 |
| Geometria + AE, 20261103 | 4 | 338 |
| Geometria + rVAE, 20261101 | 0 | 142 |
| Geometria + rVAE, 20261102 | 0 | 1105 |
| Geometria + rVAE, 20261103 | 3 | 1153 |

Nawet trafienie 4/4 granicznych par może współistnieć z dużą liczbą
fałszywych cięć. Tak mała i zależna referencja nie pozwala wybrać
modelu ani ocenić generalizacji na STM. `p_same` jest wynikiem ważonego
klasyfikatora, nie zweryfikowanym prawdopodobieństwem populacyjnym.

## Domeny na STM

Poniżej FH i H_M1. To sumy liczników wewnątrz klatek, osobno dla każdego
modelu, bez łączenia ziaren. Pokrycie ma stały mianownik **1354 miejsc
znanych wnętrz z fizycznym wsparciem**. Scalenia/podziały dotyczą par
przypisanych po odmowach, więc ich mianowniki zmieniają się z wynikiem.
Nie są tym samym co cztery lokalne krawędzie powyżej.

| Uczony odczyt | Pokrycie ↑ | Błędne scalenia ↓ | Błędne podziały ↓ |
|---|---:|---:|---:|
| Geometria | 85.82% | 99.30% | 0.00% |
| Geometria + fotometria | 82.27% | 19.03% | 12.28% |
| Geometria + AE, 20261101 | 74.67% | 82.09% | 6.21% |
| Geometria + AE, 20261102 | 37.00% | 23.33% | 31.23% |
| Geometria + AE, 20261103 | 85.38% | 87.54% | 2.80% |
| Geometria + rVAE, 20261101 | 90.47% | 96.57% | 0.09% |
| Geometria + rVAE, 20261102 | 65.21% | 32.50% | 33.95% |
| Geometria + rVAE, 20261103 | 42.47% | 9.96% | 23.71% |

Fotometria jest istotnym punktem odniesienia: poprawa względem samej
geometrii nie stanowi dowodu wartości cech sieci. rVAE/20261101 przypisuje
1225/1354 miejsc, ale scala 10038/10395 przypisanych par różnych wnętrz.
rVAE/20261103 scala mniej, 234/2350, lecz zachowuje tylko 575/1354 miejsc.
Nie porównywać samych procentów scalenia bez tego kosztu.

W porównaniu z historycznym odczytem rVAE/20261101 pokrycie rośnie
84.27→90.47%, ale scalenia 36.19→96.57%. Dla 20261103 scalenia maleją
13.49→9.96%, a pokrycie 83.90→42.47%. To porównanie całych reguł:
nowy model ma dodatkowe cechy geometrii i inny sposób dopasowania;
nie izoluje samego wpływu klasyfikatora.

MWS również nie rozstrzyga próby: dla rVAE pokrycie STM wynosi
21.49–78.43%, błędy podziału 19.03–50.83%. Pełna bramka A_fixed_M1 daje
**0% pokrycia znanej referencji we wszystkich modelach i obu solverach**.
Nie jest to odsetek wykrytych molekuł.

## Dlaczego dobre pary nie dają dobrych domen

Na syntetykach FH/H_M1 z geometrią daje pokrycie 92.15%, scalenia 0.18%
i podziały 3.77%. Z rVAE: pokrycie 88.84–94.93%, scalenia 0–2.79%,
podziały 5.37–6.84%. Każde z trzech ziaren rVAE pogarsza podziały
względem geometrii mimo AP=1.0. MWS zachowuje jedynie 24.18–33.49%
znanych syntetycznych wnętrz w ośmiu uczonych wariantach.

Kalibracja korzysta z historycznej reguły mediany i kwantyli,
wyliczonych na nowych treningowych wartościach `1-p_same`.
FH używa odległości podzielonej przez medianę i k=4; q25/q75 sterują MWS.
Mediany są bardzo małe: około 1.14×10⁻⁶–2.79×10⁻⁴. W geometrii MWS
uznaje krawędź za odpychającą już przy `p_same < 0.999585`, a przyciągającą
przy `p_same > 0.999759`. **Nie stosuje progu 0.5 ocenianego w tabeli par.**
Wartość będąca bardzo mocnym wskazaniem tej samej domeny według
klasyfikatora może więc prowadzić do cięcia grafu. Brak degeneracji
lub użycia dolnego limitu mediany; to skutek zachowanej reguły.

To uzasadnia osobną przyszłą diagnozę sposobu zamiany uczonych relacji
na graf. Wynik domen zależy także od innych krawędzi, masek i odmów;
nie przypisujemy całego pogorszenia kwantylom. Nie dowodzi to, że zmiana
progu sama naprawi STM; nie stroiliśmy solvera po obejrzeniu wyników.

Klasyfikator relacji nie uczył się obecności domeny 2D. Kontrola
`independent_rows` nadal ma fałszywe przypisania: geometria 40.58%,
AE 27.29–54.11%, rVAE 32.37–54.35% (FH/H_M1). Nie wolno uznać
tych uporządkowanych kolorów za dowód poprawnej detekcji.

## Przeglądarka i test ręczny

Otworzyć [przeglądarkę](../../.scratch/ml-e7-20261111/index.html):

```bash
xdg-open .scratch/ml-e7-20261111/index.html
```

1. Domyślnie TTMAPP259, geometria+rVAE/20261101, FH, H_M1. Lewy panel
   pokazuje uczoną geometrię, prawy wybrany odczyt. W obu panelach są
   oryginalne centra i przynależność do instancji domeny.
2. Przełączać ziarna 20261101–03 i klatki przyciskami lub suwakiem.
   Kolory zależą od członkostwa, nie oznaczają klas fizycznych i nie śledzą
   tożsamości domen w czasie.
3. Jako lewy panel wybrać historyczną odległość; obejrzeć koszt pokrycia
   i zmiany scalenia. Wybranie uczonej geometrii po obu stronach ma dać
   identyczny wynik.
4. Przełączyć MWS, pełną bramkę i „Propozycje przed odmowami”. Pełna
   bramka na STM usuwa wszystkie przypisania w znanych wnętrzach referencji;
   poza nimi część przypisań pozostaje. Braki wejścia/cechy i odmowy
   pozostają widoczne; nie są dodatkowymi domenami.
5. Kliknąć molekułę: sprawdzić źródłowe ID, współrzędne, bramki i wyniki
   relacji na jej krawędziach. Obejrzeć również `two_orientations`,
   `phase_boundary`, `independent_rows` i `resample_2x`.

UI rozróżnia 312 źródłowych centrów, 211 z pełnym wejściem i 161 ze wspólnymi
poprawnymi cechami na TTMAPP259. Brak cech nie usuwa miejsca z mianownika
pokrycia referencji. Licznik przypisań nad obrazem dotyczy pełnego obrazu,
a procenty jakości pod nim wyłącznie częściowej referencji.

**Odbiór ręczny użytkownika pozostaje otwarty.** Galeria jest osobnym
artefaktem badawczym; produkcyjna aplikacja nie dostała nowej metody.

## Sprawdzenia i pochodzenie

19 testów E7 PASS w netcat; testy obejmują grupy, jednostki resample2x,
brak przecieku referencji, ważenie, symetrię par, odmowy i zachowanie
fizycznego mianownika oraz porównania na wspólnych parach.
QtWebEngine: **167 kontroli PASS, zero błędów JS**, otwarto wszystkie
105 obrazów i obejrzano cztery zrzuty. Indeks ma 1680 zestawów; nie każdy
otwierano osobno. Sprawdzono wszystkie osiem modeli i sterowanie porównaniami.

Niezależny audyt pochodzenia: 1588 zamrożonych artefaktów, 81 modułów,
18 482 pliki źródłowe i sześć checkpointów zgodne; 192 bloki cech STM
bitowo zgodne z cache. Odtworzono 840 wyników klasyfikatora/odległości
i osiem kalibracji bez refitu. Osobny audyt jakości: 2520 ocen relacji,
7296 agregatów domen oraz 112 128 kontroli ilorazów zgodne. Wspólne maski
par identyczne w ośmiu odczytach na 105 obrazach. Raporty lokalne:
`provenance-audit.json`, `independent-audit.json`, `browser-check/`.
Największy nowy moduł ma 292 linie; wszystkie pliki kodu/testów <1000.
Bez pełnej regresji aplikacji; zmiana izolowana w eksperymencie.

Przebieg: **32.92 s wall / 32.91 s CPU**, szczyt RSS około **1.00 GiB**,
222.3 MB artefaktów przed późniejszym odczytem/audytami. Osiem fitów,
840 plików predykcji, 6720 ocen domen i 2520 ocen par; nie są to liczby
niezależnych pomiarów. Budżet 30 min CPU / 8 GiB RSS / 8 GiB danych zachowany.

Pierwszy preflight zakończył się przed utworzeniem danych i fitami:
indeks E2 ma hash w zamrożonym manifeście predykcji, a nie bezpośrednio
w skróconym manifeście repo. Poprawiono odwołanie, zachowując łańcuch
repo → freeze → index. Nie oglądano wtedy wyników E7. Nieudany snapshot
i log pozostają w `.scratch/ml-e7-20261111-preflight-failed*`.
Udany przebieg nie wymagał zmian obliczeń po ocenie.

Pełne artefakty: `.scratch/ml-e7-20261111/`. `probes/` zawiera jawne
współczynniki ośmiu modeli i skalery JSON. `prediction-freeze.json`
kotwiczy dane i predykcje; `readout-manifest.json` późniejsze tabele.
`training-census.csv`, `pair-summary.csv` i `domain-summary.csv`
zachowują przypadki, grupy i mianowniki. Wartość `regime=transductive`
w historycznej funkcji oceny oznacza tu pełną klatkę, nie trening enkodera
E7 w transdukcji ani niezależny test. Historyczne pola `qualified`
dotyczą dawnych kryteriów częściowej referencji, nie wyboru detektora.

## Dalszy kierunek

Przed zwiększaniem sieci warto przygotować mały, przejrzany zestaw
rzeczywistych relacji na granicach orientacji, przesunięcia i okresu oraz
wnętrz i przypadków bez domeny. Całe miejsca/akwizycje muszą pozostać
w osobnych rolach; nie mnożyć danych przez sąsiednie klatki.

Drugim uzasadnionym kierunkiem jest ograniczony kontrast podziału grafu
korzystającego z uczonych relacji zamiast dotychczasowej skali FH/progów MWS. Wymaga osobnego
protokołu i walidacji; nie uruchomiono go w E7. Dopiero wynik tych kroków
może uzasadnić E6 lub zmianę reprezentacji. E4 nadal odpowiada na osobne
pytanie o zdolność dekodera do rekonstrukcji, nie o skuteczność domen.

Do projektu i oceny użyto skilli `experimental-design`,
`scientific-critical-thinking`, `scikit-learn`, z istniejącą biblioteką
scikit-learn 1.6.1. Źródło procedur: Kassis T., Agarwal V., He Y., Patel D.,
Brueckner A. M. (2026), *Scientific Agent Skills: A Library of Procedural
Knowledge for Research Agents*, [arXiv](https://doi.org/10.48550/arXiv.2609.00065).
To źródło procedur, nie dowód skuteczności niniejszego detektora.
