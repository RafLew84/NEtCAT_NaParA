# E7a — te same relacje, inne reguły tworzenia domen

11 listopada 2026, `ml_domain`, baza `f807216`, środowisko `netcat`.
[Protokół](ml-ae-rvae-e7a-protocol.md), [manifest](ml-ae-rvae-e7a-manifest.json),
[plan](ml-ae-rvae-experiments.md), [przeglądarka](../../.scratch/ml-e7a-20261111/index.html).

## Wynik

**E7a wykonane. Reguła tworzenia domen mocno wpływa na wynik, ale jej zmiana
nie dała ogólnego detektora.** Bezpośredni próg relacji odzyskuje przypisania,
jednocześnie zwiększając scalenia i fałszywe domeny na części kontroli.
Nie wybrano nowego progu, modelu lub ustawień produkcyjnej aplikacji.

Najczytelniejszy wynik odczytu **geometria+rVAE, MWS t=0.5, H_M1**:

| Rodzaj syntetycznej kontroli | Pokrycie znanych wnętrz | Błędne scalenia | Błędne podziały |
|---|---:|---:|---:|
| Dwie orientacje | 100% | 0% | 0% |
| Różnica orientacji 8° | 100% | 0% | 0% |
| Granica przesunięcia/fazy | 100% | 100% | 0% |
| Różny okres sieci | 100% | 100% | 0% |

Wszystkie trzy ziarna rVAE dają te wartości, po zsumowaniu trzech realizacji
danego przypadku w każdym ziarnie. To ocena referencyjnych części domen,
nie dowód perfekcyjnego odtworzenia całej fizycznej granicy.
Sama uczona geometria również rozróżnia orientacje, a dodatkowo rozdziela
`different_spacing` bez błędów par i z pełnym pokryciem. Dla fazy scala.
Próba nie potwierdza więc konieczności ani przewagi cech rVAE.

E7 uczyło na 45 lokalnych parach różnych domen, wyłącznie ze zmian
orientacji. Wynik E7a jest zgodny z tak wąskim zakresem nadzoru; nie
izoluje jednak przyczyny błędów do samych etykiet lub samego enkodera.
AP par z E7 pozostaje identyczne: nie zmieniono żadnego wyniku relacji.
Wysokie AP nie obejmowało lokalnych różnych par fazy/okresu, które były
wykluczone przez pas niepewności. W grafie nadal istnieją inne krawędzie
mogące połączyć całe obszary.

## Porównanie na STM

Główny kontrast to ten sam klasyfikator i MWS: kwantyle E7 → jawny próg 0.5.
H_M1 zachowuje twarde warunki i minimum ośmiu molekuł, wyłącza progi ACF/widma.
Pokrycie ma stały mianownik **1354 wspieranych miejsc znanych wnętrz**.
Błędy par są warunkowe na przypisaniu; mianowniki zmieniają się z pokryciem.
Liczniki sumujemy wewnątrz jednego modelu, nie łączymy ziaren.

| Odczyt | Pokrycie: E7 → E7a | Scalenia: E7 → E7a | Podziały: E7 → E7a |
|---|---:|---:|---:|
| Geometria | 79.25 → 89.00% | 67.62 → 95.54% | 11.22 → 0.20% |
| Geometria + fotometria | 47.64 → 77.25% | 10.91 → 9.08% | 61.02 → 42.58% |
| Geometria + AE, 20261101 | 46.90 → 76.96% | 6.63 → 60.59% | 52.46 → 17.34% |
| Geometria + AE, 20261102 | 18.32 → 52.58% | brak → 33.02% | 31.85 → 23.49% |
| Geometria + AE, 20261103 | 55.98 → 84.71% | 22.68 → 87.88% | 41.05 → 5.15% |
| Geometria + rVAE, 20261101 | 78.43 → 91.14% | 59.11 → 93.84% | 19.03 → 0.13% |
| Geometria + rVAE, 20261102 | 40.92 → 60.12% | 12.70 → 17.39% | 50.83 → 37.72% |
| Geometria + rVAE, 20261103 | 21.49 → 57.61% | 33.33 → 7.41% | 49.87 → 41.80% |

Fotometria i rVAE/20261103 poprawiają wszystkie trzy obserwowane miary
agregatu STM. To korzyść lokalna, nie wybór detektora. Przykładowo ostatni
wariant zwiększa przypisania 291→780 z 1354 miejsc; błąd scalenia zmienia
się z **4/12** na **276/3723** par. Mniejszy procent nie oznacza mniejszej
liczby błędnie połączonych par ani niezależnej walidacji.
Odczyt rVAE/20261101 przypisuje 1234/1354 miejsc, ale scala 9883/10532
przypisanych par różnych wnętrz. Zależność od ziarna nadal jest duża.

Pełna bramka A_fixed_M1 pozostaje przy **0% pokrycia znanych wnętrz STM**
we wszystkich sześciu regułach i ośmiu odczytach. Część przypisań poza
referencją może pozostać. Nie jest to odsetek wykrytych molekuł.

## Koszt odzyskania przypisań

Na walidacyjnych syntetykach geometria+rVAE/MWS t=0.5 zwiększa pokrycie
z 24.18–27.63% do 99.77–99.80%, lecz ma 33.04–40.17% błędnych scaleń.
Fałszywe przypisania znanych zer rosną z 6.33–17.71% do 43.25–54.52%.
Kontrola `independent_rows` daje 96.86–100% fałszywych przypisań,
wobec 25.36–45.65% dla bazy E7 MWS. To szczególnie ważne: podział grafu
nie rozwiązał problemu rozpoznawania obecności domeny 2D.

Żaden z ośmiu odczytów nie spełnia warunku poprawy bez kosztu w agregacie
syntetycznym głównego kontrastu. Dodatkowe progi 0.25 i 0.75 nie ustanawiają
stabilnej poprawy: dla rVAE na STM ziarno 20261101 nadal scala około 93.8%
par, a ziarna 20261102/03 zmieniają kompromis pokrycia i błędów.
Wyniki wszystkich progów, przypadków i grup są zachowane w CSV;
nie dobierano progu według STM ani nie wybierano najlepszego ziarna.

FH bez dzielenia przez medianę, z zachowanym k=4, również zwiększa
przypisania. Na syntetykach rVAE ma wtedy około 99.80% pokrycia i
44.23–60.07% błędnych scaleń. To zmiana efektywnej regularyzacji.
Kontrola z odpowiednio przeskalowanym k odtwarza stare FH dokładnie:
wynik nie jest skutkiem błędu jednostek lub nowej implementacji solvera.

## Zakres i sprawdzenia

Te same 105 obrazów, 840 zapisanych wektorów relacji, sześć reguł,
osiem odczytów, niezmienione współrzędne, grafy, maski i bramki E7.
Bez treningu, inferencji enkoderów, refitu lub nowych etykiet.
MWS t=0.5 jest głównym porównaniem; 0.25/0.75 to ustalona z góry
wrażliwość. Siła relacji rośnie liniowo z odległością od progu do końca
przedziału [0,1]. Wynik ważonego klasyfikatora nie jest zweryfikowanym
prawdopodobieństwem. Zmiana mapowania obejmuje znak, siłę i brak dawnego
pasa neutralności; nie izoluje samego progu od tych elementów.

Odtworzono dokładnie **5040 tablic podziałów E7**, 840 kontroli skali FH
i 3360 zapisów bazowych miar jakości. Predykcje zamrożono przed oceną
referencją. Hashami sprawdzono 1588 plików źródłowych E7, 32 artefakty
wersjonowanego manifestu i sześć checkpointów przed i po próbie.

**13 testów PASS** w netcat. Osobny audyt numeryczny ponownie wyliczył
10 080 ocen przez jawne wyliczenie par, sprawdził spójność i minimum
komponentów po odmowach oraz 109 440 pól liczników w 10 944 agregatach.
Wszystkie 840 wektorów wyników relacji i 5040 tablic grafów/masek są
identyczne ze źródłem. To kontrole innym sposobem liczenia, nie osobny
recenzent ani niezależny eksperyment.

QtWebEngine: **430 kontroli PASS, zero błędów JS**, wczytano wszystkie
105 obrazów, osiem modeli, sześć reguł, oba porównania i bramki;
sprawdzono niezmienność wyniku relacji po zmianie reguły. Indeks ma
5040 zestawów; nie otwierano każdego osobno. Cztery zrzuty obejrzane:
STM, dane punktu, resample2x i obraz bez centrów. Bez usterek.
Pierwszy start Qt został zatrzymany przez ograniczenie procesu Chromium
w piaskownicy przed odczytem galerii; ten sam checker przeszedł po
uruchomieniu na hoście. Zachowano oba logi. Nie zmieniano obliczeń lub UI.

Przebieg główny: **30.37 s wall / 30.37 s CPU**, szczyt RSS około **0.99 GiB**,
199 MB przed postprocessingiem. Budżet 10 min CPU / 8 GiB RSS / 2 GiB
artefaktów zachowany. Bez pełnej regresji aplikacji; zmiany wyłącznie
w izolowanych modułach eksperymentu. Wszystkie nowe pliki kodu/testów <1000 linii.

## Przeglądarka i odbiór ręczny

```bash
xdg-open .scratch/ml-e7a-20261111/index.html
```

1. Domyślnie TTMAPP259, geometria+rVAE/20261101, H_M1. Po lewej E7 MWS,
   po prawej MWS z progiem 0.5. Na pełnym obrazie przypisania zmieniają
   się 133→156, a liczba domen 4→2; nie oznacza to poprawnego rozdzielenia
   znanych wnętrz, których scalenia na tej klatce wynoszą 100% w obu panelach.
2. Zmienić ziarno, regułę i klatkę przyciskami lub suwakiem. Lewy panel
   zawsze dotyczy tego samego wybranego odczytu co prawy. Można przełączyć
   bazę na E7 FH. Wybranie tej samej bazy po obu stronach daje identyczne domeny.
3. Kliknąć molekułę i przełączać reguły. Źródłowe ID, współrzędne oraz
   wynik relacji pozostają te same; zmienia się przynależność do domeny.
4. Obejrzeć propozycje przed odmowami, H_M1 i pełną bramkę. Braki cech,
   niedostępne wejścia oraz odmowy pozostają widoczne.
5. Porównać `two_orientations`, `orientation_8deg`, `phase_boundary`,
   `different_spacing` i `independent_rows`. Kolory oznaczają instancje
   na danym obrazie, nie fizyczne klasy ani śledzenie w czasie.

Odbiór użytkownika pozostaje otwarty. Pełne pliki NPZ, grafy i galeria
są lokalne w `.scratch/ml-e7a-20261111`. `readout-domains.csv` zachowuje
liczniki i grupy, `readout-contrasts.csv` koszt każdego porównania.
Późniejsze odczyty i audyt mają osobne hashe; nie zmieniają zamrożonych predykcji.

## Co dalej

Najbardziej uzasadnione jest teraz przygotowanie E7b: przejrzanych relacji
rzeczywistych wnętrz i różnych rodzajów granic oraz przypadków bez domeny.
Punktem wyjścia jest 10 ROI E0; trzeba sprawdzić ich zawartość i podział
fizycznych miejsc. Same ROI jednej akwizycji nie tworzą niezależnego testu.
Następny trening powinien odpowiadać na te braki, zamiast powielać więcej
szumu tego samego generatora. Nie uruchomiono E7b, E4 ani E6.

Projekt porównania wspierał skill `experimental-design`. Źródło procedur:
Kassis T., Agarwal V., He Y., Patel D., Brueckner A. M. (2026),
*Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*,
[DOI](https://doi.org/10.48550/arXiv.2609.00065). Nie jest to źródło wyników E7a.
