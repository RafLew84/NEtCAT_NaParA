# Issue 19 — diagnoza cech, PCA i grupowania

Data: 2026-10-26. Rozwinięcie [pierwszej próby 19](frozen-feature-domains-trial.md)
wykonane na polecenie użytkownika „wykonaj kolejne badanie”. Status 19
pozostaje `claimed`, do omówienia; nie przyjęto metody do aplikacji.

**Wniosek:** uśrednione cechy FCN i DINO zachowują na kontrolach informację
o obrocie i rozstawie. PCA24 niemal nie zmienia rozróżnialności tych wnętrz.
Pominięcie PCA lub wyzerowanie epsilon nie naprawia jednak wykrywania domen.
Na TTMAPP nadal otrzymujemy jeden klaster wyglądu albo odmowę, a końcowe
przypisania pozostają nieliczne. Nie ma podstaw, by obecny problem
sprowadzić do samego uśredniania cech, PCA albo scalającego epsilon.

Źródła: **`prototype/stmdomains-feature-separation`, `cf88e8a`**, baza
`652ab96`. Nie scalać prototypu do aplikacji. Dokumentacja na
`domains/feature-separation-trial`, baza `1c2eef6`.
[Manifest badania](feature-separation-manifest.json).

Podgląd lokalny, samowystarczalny HTML:
`/home/rlew/projekty/NEtCAT-domains/.scratch/feature-separation/index.html`.
Zakładki: „Obrót i rozstaw”, „Jedna sieć i szum”, „Granica przesunięcia”,
„Pełne TTMAPP”. Lewy obraz pokazuje stary wariant, prawy wybrane odstępstwo.
Można osobno oglądać podobieństwo cech, połączone grupy, kryterium porządku
i końcowych kandydatów. Okręgi oznaczają centra, krzyżyki regularną siatkę.

## Pytanie i protokół

Sprawdzono dwie części hipotezy: czy różnice między wnętrzami domen są
obecne w odległościach cech oraz czy usuwa je PCA lub dodatkowe scalanie
klastrów. Protokół zapisano przed obliczeniem metryk:
`feature_separation_design.json`, SHA-256
`e51c748b3871980adab319ecb0a0a0300dfcdf040033b5f2b5b3d7581264f7e9`.
Ustawień nie zmieniano po obejrzeniu wyników. Nie wybrano zwycięzcy na TTMAPP.

- Te same **24 całe klatki TTMAPP**: 1, 50, 100, 150, 200 i 250–268;
  6730 oznaczeń molekuł. Wszystkie klatki dopasowywane wspólnie.
- **204 kontrole**, 34 przypadki × sześć ziaren 1701–1703 i 2701–2703.
  Każda kontrola ma osobny katalog dopasowywany do całego obrazu.
- FFT, EWT, FCN–ResNet101 i DINOv2; siatka i centra; promień 24 px.
  Sieci: wejście 112 × 112, kontrast percentylowy, dotychczasowe uśrednienie
  map/tokenów. Klasyczne okno ma 49 px szerokości, neuronowe 48 px.
- Ponownie wykorzystano zapisane cechy. Nie wykonywano treningu,
  ekstrakcji na GPU, pobierania modeli ani zmiany wspólnych modułów.
- Referencje TTMAPP odczytano do oceny po zapisaniu predykcji oraz ich
  hashy. Dopasowanie i predykcja nie mają dostępu do ścieżki oceny.
  Decyzja o wykonaniu ograniczonej próby grupowania wynika z uprzednio
  zapisanej przesłanki diagnostycznej na kontrolach, nie z ramek TTMAPP.

**Wszystkie ziarna i ramki były już oglądane.** Jest to diagnoza rozwojowa,
a nie nowy niezależny test. Zachowano podział 1701–1703 / 2701–2703 do
porównania z poprzednią próbą, bez nazywania drugiej części nieznanymi danymi.

## Jak oceniono informację przed grupowaniem

Każdy wektor normalizujemy L2 i zaokrąglamy do ośmiu miejsc jak wcześniej.
Porównujemy pełny wektor i PCA do maksymalnie 24 składowych, solver `full`,
bez wybielania. PCA dopasowujemy na wszystkich miejscach z podparciem
pomiaru ≥50%; referencja nie ogranicza dopasowania.

Dopiero metryka wybiera miejsca, których **całe okno 49 × 49 px** mieści
się w jednym znanym wnętrzu i w obszarze dopuszczonej oceny. To wspólne,
konserwatywne kryterium dla cech klasycznych i sieci. Porównuje niepokrywające
się okna: różnica x albo y wynosi co najmniej 49 px skali odniesienia.
Pary dzielimy na ustalone przedziały odległości przestrzennej szerokości 12 px.

W każdym przedziale AUC opisuje prawdopodobieństwo, że odległość cech
dwóch różnych domen będzie większa od odległości cech tej samej domeny;
remis dostaje 1/2 punktu. Średnia przedziałów ma wagę mniejszej z liczby
par tej samej i różnych domen. Zapisano także AUC bez dopasowania
odległości, mediany dystansów, liczebności i wartości każdego ziarna.

To **nie trafność detektora domen**. AUC wykorzystuje znane wnętrza
wyłącznie do diagnozy; algorytm nie dostaje tych wnętrz. Pary są zależne,
więc nie podajemy pozornie precyzyjnych przedziałów ufności z liczby par.
Brak dwóch regionów lub par oznacza null, a nie wynik zerowy.

Umowna przesłanka: AUC ≥0.75 w każdym z sześciu ziaren dla choć jednego
głównego przypadku pozwala przejść do zaplanowanego badania grupowania.
Warunek został spełniony również przez oba modele sieci dla orientacji
i rozstawu. Nie uruchamiano warunkowego porównania przestrzennych map
z uśrednianiem: na tych kontrolach informacja w uśrednieniu nie zniknęła.
Nie rozstrzyga to przydatności innych poolingów na rzeczywistych obrazach.

## Wynik cech i PCA

Średnia dopasowanego przestrzennie AUC z sześciu ziaren; liczby zaokrąglone.
Pełne zakresy w `distances.csv` i `distance-diagnosis.png` / `.pdf`.

| Cecha / miejsca | Obrót 27°: pełne / PCA | Obrót 8°: pełne / PCA | Rozstaw 12→16 px: pełne / PCA | Przesunięcie: pełne / PCA |
| --- | ---: | ---: | ---: | ---: |
| FFT / siatka | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 0.751 / 0.755 |
| FFT / centra | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 0.530 / 0.536 |
| EWT / siatka | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 0.595 / 0.596 |
| EWT / centra | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 0.606 / 0.607 |
| FCN / siatka | 1.000 / 1.000 | 0.994 / 0.994 | 1.000 / 1.000 | 1.000 / 1.000 |
| FCN / centra | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 0.501 / 0.498 |
| DINO / siatka | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| DINO / centra | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 0.455 / 0.448 |

Dla głównych prób obrotu/rozstawu największa bezwzględna zmiana AUC po
PCA wynosi **0.000486** (zaokrąglenie w górę). Nie znaleziono tu utraty
informacji wyjaśniającej scalenie domen. Spośród wszystkich 432 porównań
z dostępną metryką dwa spadły o ≥0.05: FFT/siatka dla pasa nieporządku
(ziarno 1703, spadek 0.0911) i rozłącznych płatów (1701, 0.0788).
W obu przypadkach oceniamy rozdział obszarów, niekoniecznie różne struktury.

Na główną kontrolę siatki przypada po 96 bezpiecznych miejsc w każdym
ziarnie; łącznie 5376 par tej samej i 13824 różnych domen. Dla centrów
liczebności zależą od przypadku: 360–468 miejsc łącznie w sześciu ziarnach.
Nie są to wyniki obliczone z kilku zachodzących na siebie wycinków.

**Granica przesunięcia wymaga ostrożności.** Oba modele odróżniają wnętrza
na stałej siatce, lecz przy centrach molekuł AUC jest bliskie losowemu.
Wyrównanie okna do molekuły usuwa różnicę translacji wnętrza regularnej
sieci; siatka może reagować na położenie wzoru względem okna. To zgodna
z wynikiem interpretacja, nie dowód wykrywania samej linii niedopasowania.
Nie wykonywano dodatkowego testu przesuwania początku siatki.

## Cztery warianty grupowania

Budżet **32 konfiguracje**: osiem kombinacji cecha/miejsca × pełne/PCA
× dotychczasowe/zerowe epsilon. Pozostałe parametry stałe:
HDBSCAN `min_cluster_size=12`, `min_samples=6`, `allow_single_cluster=True`,
EOM, odległość euklidesowa. Dystanse dzielimy przez medianę dodatniej
odległości szóstego innego sąsiada, osobno w każdej reprezentacji.
Dotychczasowe epsilon to 1.5, a DINO/centra 0.5. Nie zadano liczby grup.

Kryterium ACF, jego progi, podparcie, odległości łączenia i minimalny
fragment są identyczne z wybraną poprzednio konfiguracją danej rodziny.
Nie porównujemy tu nowych wariantów ACF. Grupy wyglądu, ich połączone
fragmenty bez sprawdzenia porządku i końcowi kandydaci są osobnymi etapami.

Epsilon nie jest wyłącznie przełącznikiem scalania. Inspekcja lokalnego
oficjalnego kodu sklearn 1.6.1 (`_hdbscan/_tree.pyx`, linie 440–507)
potwierdza, że przy wyborze jednego korzenia i `allow_single_cluster`
zmienia również próg uznania punktu za członka tego klastra. Dlatego po
wyzerowaniu może zmienić się zakres odmów bez utworzenia nowych grup.
Hash źródła i zakres inspekcji zapisano w `provenance.json`.

**Żadna z 32 konfiguracji nie spełniła wszystkich poprzednich warunków
rozwojowych.** Rozróżnialne odległości wnętrz nie gwarantują, że EOM
wybierze odpowiadające im klastry wśród wszystkich okien całego obrazu.
Przykłady z poprzednio odłożonych, obecnie już znanych ziaren 2701–2703:

- FCN nadal scala obrót 8° we wszystkich czterech wariantach i obu
  sposobach próbkowania: 100% błędnie scalonych przypisanych par różnych domen.
- Jedna sieć nadal daje 2/2/2 fragmenty dla FCN/siatka i 4/4/4 dla
  FCN/centra. DINO/siatka daje 2/3/3; usunięcie PCA zmienia DINO/centra
  z 5/2/2 na 2/2/2, ale nadal nie daje jednej domeny.
- Są lokalne poprawy: FCN/siatka z pełnymi cechami rozdziela rozstaw
  na dokładnie dwie domeny przy 93.1% przypisania, bez błędów par;
  PCA daje 4/3/2 fragmenty. Nie poprawia to innych wymaganych przypadków.
- Są też pogorszenia: DINO/centra, pełne cechy i epsilon=0, scala
  orientację 27°, orientację 8° i granicę przesunięcia w jedną domenę.
  Odpowiednio około 79.6%, 82.1% i 82.6% przypisania nie jest sukcesem,
  bo błędy scalenia przypisanych par wynoszą 100%.
- Na sześciu rodzajach negatywnych kontroli w sześciu ziarnach wszystkie
  warianty mają zero końcowych fałszywych przypisań: 0/9216 miejsc siatki
  lub 0/6394 centrów. Brak centrów w szumie/pasach nie dowodzi odporności
  wariantu centrowego na te tekstury; służy temu ocena siatki.

## TTMAPP

W całym wspólnym zakresie **30 z 32 konfiguracji** wybiera jeden klaster
wyglądu. Dwa warianty DINO/centra z dotychczasowym epsilon odmawiają
wszystkim. Żadna konfiguracja nie znajduje kilku grup wyglądu, które
mogłyby rozróżniać orientacje. Wyzerowanie epsilon przede wszystkim
zmienia liczbę przyjętych miejsc, nie rozwiązuje podziału.

Końcowe przypisane molekuły w częściowych wnętrzach, mianownik **1678**.
Pełne cechy i PCA dają tu taką samą liczbę przypisań dla danego epsilon.

| Cecha / miejsca | Dotychczasowe epsilon | Epsilon = 0 |
| --- | ---: | ---: |
| FFT / siatka | 98 (5.84%) | 98 (5.84%) |
| FFT / centra | 34 (2.03%) | 34 (2.03%) |
| EWT / siatka | 86 (5.13%) | 70 (4.17%) |
| EWT / centra | 34 (2.03%) | 27 (1.61%) |
| FCN / siatka | 86 (5.13%) | 86 (5.13%) |
| FCN / centra | 34 (2.03%) | 34 (2.03%) |
| DINO / siatka | 86 (5.13%) | 86 (5.13%) |
| DINO / centra | 0 | 46 (2.74%) |

We wszystkich wariantach przypisania dotyczą tylko BLACK. RED: 0/101,
YELLOW: 0/274. DINO/centra odzyskuje niewielkie fragmenty dzięki zmianie
odmów klastra, nie dzięki rozdzieleniu orientacji. Brak przypisanych par
między różnymi regionami oznacza null dla scalenia, nie bezbłędną detekcję.
To ocena znanych wnętrz 18 klatek, bez globalnej oceny pozostałego obrazu.

Wcześniej rozpoznane ograniczenie ACF pozostaje: większość miejsc nie
przechodzi dowodu porządku. Jednocześnie etap przed ACF także nie daje
podziału wyglądu. Samo obniżenie progu porządku nie zapewni więc domen.
Nie wyznaczono typów strukturalnych, powierzchni ani dokładnych konturów.

## Sprawdzenia, koszt i odtworzenie

- **1824/1824** odtworzeń ośmiu dotychczasowych konfiguracji jest dokładnych:
  228 obrazów × osiem wariantów, po pięć tablic (grupy, bramka, fragmenty
  z bramką i bez, przypisania molekuł). To kontrola izolacji zmienionych etapów.
- Obliczenie AUC porównano z bezpośrednim wyliczeniem wszystkich par,
  także z remisami; różnica 5.56e-17. Odległości po PCA w diagnozie
  nie przekroczyły odległości pełnych cech.
- Predykcje zamrożono przed oceną TTMAPP; hash pliku blokady nie zmienił
  się podczas oceny. Kod dopasowania czyta wyłącznie analizę i cechy.
  Niezależność samej ekstrakcji od oznaczeń była sprawdzona w 18/19;
  tutaj nie powtarzano ekstrakcji ani nie deklaruje się nowego takiego testu.
- **68 sprawdzeń QtWebEngine**: scenariusze, obie geometrie, rodziny,
  warianty, etapy i referencje; bez błędów JS i poziomego przepełnienia.
  Obejrzano zrzut podglądu i wykres. To nie testy natywnego GUI aplikacji.
- Składnia Python/Bash, hashe, lokalne linki i `git diff --check`.
  Bez nowych testów jednostkowych prototypu i bez zmian produkcyjnego kodu.

Lokalne netcat: Python 3.12.12, NumPy 2.2.5, SciPy 1.15.2, sklearn 1.6.1.
Jeden wątek BLAS/OpenMP, **bez GPU**. Przygotowanie transformacji 16.16 s,
metryki odległości 7.19 s, wszystkie grupowania 457.59 s. Szczyt RSS
przygotowania 589056 KiB (ok. 575 MiB), grupowania 536784 KiB (ok. 524 MiB).
Nie mierzymy tu kosztu ekstrakcji sieci ani wydajności pełnych 268 klatek.

Artefakty obejmują pełne metryki JSON, `distances.csv`, `clustering.csv`,
parametry, PCA, predykcje, ich hashe, HTML i wykres PNG/PDF. Własne dane
wynikowe zajmują około 262 MB. Cechy i obrazy są powiązane względnymi
symlinkami z zachowanym artefaktem pierwszej próby; ten katalog jest
potrzebny do odtworzenia obliczeń. Sam HTML zawiera wszystko do podglądu.
Kopia do `.scratch/feature-separation/` została zweryfikowana SHA-256.

Runner i opis: `stmdomains/prototypes/run_feature_separation.sh` oraz
`README-feature-separation.md` na gałęzi prototypu. Etapy wykonano osobno;
wrapper sprawdzono składniowo, bez ponownego pełnego przebiegu.

## Kolejny krok do omówienia

Aktualizacja 2026-10-26: zaproponowaną niżej próbę lokalnego podziału
wykonano w [osobnym badaniu grafu i początku siatki](local-feature-graph-trial.md).
Zmniejsza część scaleń, ale nadmiernie dzieli jedną sieć i pozostaje
zależna od próbkowania. Osobna próba skali/podparcia ACF nadal przed nami.
Poniższy plan zachowuje uzasadnienie kolejnego eksperymentu.

Najbardziej uzasadniona kolejna próba w obrębie 19 to **lokalny podział
przestrzenny na podstawie różnic cech**, porównany z obecnym globalnym
grupowaniem gęstościowym. Trzeba sprawdzić, czy punkty przejściowe lub
wpływ brzegu okna łączą rozróżnialne wnętrza i czy da się rozdzielić je
bez narzucania K, przykładów domen lub rozcinania jednej sieci.
To hipoteza wynikająca z tej diagnozy, jeszcze niezweryfikowana metoda.

Osobnym, jawnie ograniczonym porównaniem powinno być kryterium porządku
i jego skala: nawet poprawny podział wyglądu nie odzyska miejsc odrzuconych
przez obecną ACF. Nie zmieniać jednocześnie cech, grafu i bramki bez
wariantów pozwalających rozpoznać źródło poprawy. Zachować kontrole jednej
sieci, małego obrotu, szumu i braków oraz sprawdzić przesunięcie siatki.

Nie ma obecnie uzasadnienia, żeby samą wymianę PCA na pełne cechy uznać
za rozwiązanie albo zwiększać model na podstawie tej próby. Nie wyklucza
ona treningu zaplanowanego w 20–23, lecz go nie uruchamia. Użyteczność
cech na trudnych rzeczywistych strukturach pozostaje otwarta; wysokie
AUC idealnych wnętrz nie jest dowodem uogólnienia na STM.
