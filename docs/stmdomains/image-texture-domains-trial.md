# Tekstura obrazu — próba issue 17

Data: 2026-10-23. [Issue 17](issues/17-image-texture-domains.md).
**Próba zakończona, bez wyboru metody produkcyjnej.** Użytkownik zaakceptował
zachowanie porównania i zamknięcie 17. Wynik jest klasycznym punktem
odniesienia dla 19/21/22; odbiór 13 i protokół jakości 04 pozostają otwarte.

Lokalne widmo i EWT działają niezależnie od oznaczeń molekuł. Nie uzyskano
jednak ogólnego wykrywania domen na TTMAPP: wybrane na kontrolach
konfiguracje przypisują 0.3–5.8% centrów we wnętrzach referencji,
bez RED/YELLOW. EWT scala małe różnice orientacji; widmo na siatce
nadmiernie dzieli jedną sieć. Wynik nie przekreśla informacji obrazowej,
ale nie uzasadnia wdrożenia obecnego przetwarzania, grupowania i bramki porządku.

Podgląd całych klatek, pięć scenariuszy, zmiana metody/okna i widoczne odmowy:
`/home/rlew/projekty/NEtCAT-domains/.scratch/image-texture-domains/index.html`.
W tym katalogu znajdują się również `texture-comparison.png`, PDF, CSV,
cechy, parametry, banki filtrów, katalogi i komplet wyników.

Źródła prototypu: gałąź `prototype/stmdomains-texture`, commit `3bb4d36`,
baza `e6d3fbc`. Kod pozostaje osobnym eksperymentem; nie scalać go do aplikacji.
Dokumentacja: `domains/texture-trial`, baza `b292f2f`, docelowo `domains/start`.

## Co rzeczywiście porównano

32 konfiguracje: lokalne widmo Fouriera albo EWT, pomiar na siatce albo
przy centrach, promień 24/36 px, tolerancja HDBSCAN 0.1/0.25 i próg
powtarzalności z kwantyla 0.99/0.999 rozwojowych kontroli negatywnych.
Nie zadawano liczby domen, nie trenowano na ręcznych klasach ani nie
używano ramek do wyboru okien. Parametry określają skalę szukanych struktur;
nie jest to algorytm wolny od założeń o rozstawie.

- Wejście: pełne oryginalne pole obrazu, bez paddingu rejestracji.
  Przeskalowanie techniczne do pikseli odniesienia, odjęcie rozmycia Gaussa
  `σ=3`, podział przez RMS klatki. Nie wyznacza to skali w nm.
- Siatka co 12 px; dodatkowo te same cechy mierzone przy istniejących centrach.
  Okna `(2R+1)²`, odbicie brzegów, minimum 50% rzeczywistego pola okna.
  Odbite piksele nie stają się danymi pomiarowymi.
- Widmo: okno Hanna, 12 częstotliwości od `1/28` do `1/6` cyklu/px,
  18 kierunków modulo π, pierwiastek z unormowanej mocy — 216 cech.
  Częstotliwość i kierunek pozostają rozróżniane; lokalna energia jest osobną
  zapisaną wielkością. Nie redukujemy ich do pojedynczej jasności.
- EWT: oficjalny `pyewt 1.0.0`, curvelet **option 1**, granice radialne
  i kątowe wykrywane niezależnie przez scalespace/Otsu; `Completion=False`.
  Wygładzanie widma Gaussa: długość 9, σ=2. Zmiana `N/curvN` na 37/41
  nie zmieniła granic — te parametry nie wymuszają tu liczby pasm.
- Bank TTMAPP jest wspólny dla całego analizowanego zakresu. Moduł PPFFT
  każdej klatki normalizujemy do sumy 1 i uśredniamy z równą wagą.
  Przed PPFFT stosujemy Tukey α=0.2 oraz minimalne dopełnienie do parzystego
  kwadratu; widma interpolujemy na wspólną siatkę 512×512. Filtracja używa
  odbitego marginesu 36 px. To zapisana polityka, nie wynik optymalizacji
  marginesu na referencjach.
- Lokalne energie EWT: RMS odpowiedzi filtrów, następnie normalizacja
  wektora L2. Zachowano kanał dolnoprzepustowy. Wszystkie 24 klatki mają
  wspólne 12 filtrów; zakres pięciu klatek daje 15. W całej próbie banki
  miały 12–243 kanałów. **Kanał filtra nie jest domeną ani typem sieci.**
- Każda kontrola syntetyczna stanowi niezależny, jednoklatkowy zakres,
  z osobnym bankiem i grupowaniem. Nie sklejamy kanałów z różnych banków.
- PCA do maksymalnie 24 składowych, bez whitening; HDBSCAN:
  `min_cluster_size=12`, `min_samples=6`, `allow_single_cluster=True`, EOM.
  Grupowanie używa wszystkich próbek z dostatecznym podparciem obrazu,
  przed sprawdzeniem porządku. Zapisano również te wstępne etykiety.
- Osobna bramka porządku: dwa niekolinearne maksima autokorelacji przy
  przesunięciach 6–24 px, sinus kąta ≥0.35 oraz energia drugiego kierunku
  widma ≥25% dominującego. Wynik ACF to mniejsza wysokość wybranej pary
  pików; musi przekraczać próg z kontroli. Energia lokalna musi być dodatnia.
- Po bramce łączymy sąsiednie próbki tego samego klastra. Siatka: połączenie
  do `12√2` px i minimum 4 próbki. Centra: do minimum z 24 px i 1.65 mediany
  najbliższych odległości, minimum 8 elementów. Zgodny typ strukturalny nie
  jest deklarowany: grupy tekstury mogą rozróżniać również orientację.
- Dla porównania ze starszymi metodami wynik siatki przenosimy na najbliższe
  centra, tylko do odległości `12√2/2` px. Oceniono także same próbki siatki,
  w tym obrazy szumu i pasów bez żadnych oznaczeń.

To **adaptacja**, a nie reprodukcja wyników publikacji Bui. Publikacja
używa innego rozdzielenia obrazu na teksturę, innego skalowania energii,
zmodyfikowanej transformacji kierunkowej i grupowania z liczbą klas podaną
przez użytkownika. Nasze odjęcie Gaussa, wspólny bank zakresu, normalizacja,
HDBSCAN bez K i osobna bramka wymagają własnej oceny. Wariant 1 wybrano
po audycie ograniczeń API wariantu 3; nie poprawiano samej biblioteki.
[Audyt źródeł i API](research-image-texture-adaptation-audit.md),
[Bui i in.](https://arxiv.org/pdf/1804.08890),
[oficjalny pyewt](https://github.com/jegilles/pyewt).

## Wejście i rozdzielenie doboru od oceny

To ten sam zestaw co w końcowym porównaniu 15 i próbie 16: **24 pełne
klatki TTMAPP, 6730 oznaczeń oraz 204 kontrole — 34 przypadki × 6 ziaren**.
Źródło lokalne: `.scratch/orientation-and-joining/input`. SHA-256 manifestów
oraz źródeł zapisano w `provenance.json`; manifesty wejścia zachowują
identyfikację pierwotnego MPP/MolTrack i geometrię.

Ziarna 1701/1702/1703 służyły do doboru, a 2701/2702/2703 do oceny.
Progi ACF z 18 negatywnych kontroli rozwojowych:

| R | q=0.99 | q=0.999 |
| --- | ---: | ---: |
| 24 | 0.32224349 | 0.36077697 |
| 36 | 0.26640445 | 0.31284048 |

Ranking zamrożono przed odczytem wyników: liczba niespełnionych warunków,
potem średnia `przypisanie × (1−podziały) × (1−scalenia)` na 24 dodatnich
przypadkach. Warunki obejmowały ≥90% przypisań jednej sieci, zero fałszywych
próbek w sześciu rodzinach negatywnych i ≥50% przypisań z ≤2% scaleń
w sześciu przypadkach rozdzielenia. Doboru dokonywano wyłącznie na kontroli
rozwojowej; nie zmieniano go po obejrzeniu TTMAPP.

**Ograniczenie tego filtra doboru:** nie miał twardego warunku liczby domen
ani podziałów dla pojedynczej sieci. Dlatego FFT/siatka przechodzi filtr,
ale dzieli jedną sieć na trzy. To jawny brak kryterium, nie sukces wykrycia
jednej domeny. Nie poprawialiśmy rankingu po wynikach, aby wybrać korzystny
wariant. Dalsze porównanie powinno uwzględnić także ten warunek.

| Rodzina | Wybrany wariant diagnostyczny | Niespełnione warunki rozwojowe |
| --- | --- | --- |
| Widmo, siatka | R24 / ε0.1 / q0.999 | Brak w ograniczonym filtrze; nadmierne podziały jednej sieci pozostają |
| Widmo, centra | R24 / ε0.25 / q0.99 | Brak w filtrze; później błąd małej orientacji na odłożonym ziarnie |
| EWT, siatka | R24 / ε0.25 / q0.999 | Mała orientacja i obie granice przesunięcia |
| EWT, centra | R24 / ε0.1 / q0.99 | Mała orientacja |

Parametry i ranking są w `settings.json`. Zmiana techniczna przed wyborem
zastąpiła pośredni import listy kontroli identyczną listą, usuwając zbędną
zależność od MatID; nie zmieniła reguł. Potwierdzenie zapisano osobno.

## Odłożone kontrole: przypisanie nie wystarcza

Procenty poniżej dotyczą centrów, aby porównanie z 15/16 miało ten sam
mianownik. Błędy par liczymy tylko wśród przypisanych elementów; odmowy
pozostają widoczne w kolumnie przypisania. Liczby obszarów dla trzech ziaren
są w CSV i podglądzie.

| Przypadek | Widmo/siatka | Widmo/centra | EWT/siatka | EWT/centra |
| --- | --- | --- | --- | --- |
| Jedna sieć | 95.3%; **3 obszary**, 28.9% podziałów | 96.9%; 1 obszar | 95.3%; 1 obszar | 96.6%; 1 obszar |
| Braki 30% | 95.2%; 3 obszary | 96.5%; 1 obszar | 95.2%; 1 obszar | 95.5%; 1 obszar |
| Braki 50% | 95.1%; 3 obszary | 93.5%; 2/1/1 obszary | 95.1%; 1 obszar | 92.4%; 2/1/1 obszary |
| Dwie orientacje 27° | 79.8%; 18.9% podziałów | 91.1%; 2 obszary | 84.2%; 2 obszary | 89.3%; 12.3% podziałów |
| Mała różnica 8° | 79.9%; 18.97% podziałów, 0 scaleń | 92.2%; **32.9% scaleń** | 87.8%; **100% scaleń** | 92.8%; **100% scaleń** |
| Inny rozstaw | 78.2%; 28.1% podziałów | 86.2%; 2 obszary | 85.1%; 2 obszary | 79.4%; 19.9% podziałów |
| Granica przesunięcia | 85.8%; **4 obszary**, 27.9% podziałów | 87.9%; 2 obszary | 93.3%; **100% scaleń** | 88.1%; 2 obszary |
| Granica + błąd centrów | 86.9%; 4 obszary | 90.6%; 2 obszary | 92.1%; **100% scaleń** | 91.9%; 2 obszary |
| Rozłączne płaty | 80.1%; 3 obszary | 96.6%; 2 obszary | 84.6%; 2 obszary | 96.0%; 2 obszary |
| Rzadszy wzór | 83.3%; 3/1/2 obszary | 81.9%; 1 obszar | 83.3%; 1 obszar | 78.9%; 1 obszar |

Wszystkie cztery wybrane warianty: **0/3195 fałszywych przypisań** w czterech
rodzinach losowych punktów. Również zero fałszywych próbek na szumie i pasach.
To sprawdzenie przydatnej odmowy, ale nie równoważy odmowy na rzeczywistych
domenach. Niezależne rzędy pozostają kontrolą diagnostyczną bez kompletnej
prawdy domen 2D; nie służyły do wyboru ani liczenia trafności.

Braki i błędy centrów zmieniają oznaczenia, **nie obraz**. Wariant obrazowy
powinien wtedy zachować wynik i to sprawdzono. Sukces przy błędzie centrów
nie jest dowodem odporności na rozmycie, deformację lub szum samego obrazu.
Rozdzielenie idealnej granicy przez lokalne widmo może wynikać ze zmiany
okien na styku oraz reguły łączenia; nie jest dowodem odzyskania fazy sieci
z modułu widma. EWT na siatce właśnie tę granicę scala.

## TTMAPP: większość danych odrzucona

Ocena obejmuje **18 częściowych referencji, 1678 centrów** w ich wnętrzach:
BLACK 1303, RED 101, YELLOW 274. Regiony oznaczają głównie orientacje tej
samej sieci. Błędy par wykorzystują osobne regiony w klatce, nie samo
powtarzanie koloru. Poza referencjami nie zakładamy braku domen.

| Metoda | Przypisane centra | Podziały przypisanych par tego samego regionu | Scalenia przypisanych par różnych regionów |
| --- | ---: | ---: | ---: |
| Widmo/siatka | 5/1678 = **0.3%** | 0/10 | Brak par do oceny |
| Widmo/centra | 54/1678 = **3.2%** | 0/298 | Brak par do oceny |
| EWT/siatka | 98/1678 = **5.8%** | 275/635 = **43.3%** | Brak par do oceny |
| EWT/centra | 54/1678 = **3.2%** | 0/298 | Brak par do oceny |
| Komórka, issue 15 | 1187/1678 = 70.7% | 1001/35733 = 2.8% | 0/3801 |
| SBC, issue 16 | 1065/1678 = 63.5% | 1843/31227 = 5.9% | 232/4189 = 5.5% |

Wszystkie przypisania wybranych wariantów obrazowych są w BLACK.
RED: **0/101**, YELLOW: **0/274**. Brak ocenianych par z różnych regionów
nie oznacza zerowego błędu scalenia — wykres i tabela pokazują brak mianownika.
Odrzucenie prawie wszystkiego nie kwalifikuje metody.

Diagnoza etapów, w tym samym zbiorze 1678 centrów (siatka przez najbliższą
próbkę):

| Wariant | Przechodzi bramkę porządku | Ma klaster przed bramką | Spełnia oba | Zostaje po łączeniu |
| --- | ---: | ---: | ---: | ---: |
| Widmo/siatka | 154 | 199 | 31 | 5 |
| Widmo/centra | 212 | 1493 | 208 | 54 |
| EWT/siatka | 154 | 1678 | 154 | 98 |
| EWT/centra | 212 | 1678 | 212 | 54 |

EWT grupuje praktycznie całe TTMAPP w **jeden klaster tekstury** przed bramką;
różne końcowe obszary powstają głównie przez przerwy w akceptacji i łączność.
Nie jest to rozróżnienie domen orientacyjnych. Widmo na siatce odrzuca już
większość cech jako szum HDBSCAN. Bramka ACF dobrana na prostej syntezie
przepuszcza jedynie 9.2%/12.6% ocenianych miejsc (siatka/centra), a następnie
małe składowe usuwają dalsze elementy. Zmiana cech przy zachowaniu tej samej
bramki może więc pozostać ograniczona przez bramkę.

Pozostałych konfiguracji nie ukryto. Największe przypisanie wśród 32 to
EWT/siatka R36/q0.99: **370/1678 = 22.1%**, ale 48.7% podziałów i 16.9%
scaleń warunkowych par. Większe okno samo nie naprawia wyniku. Nie wybierano
tego wariantu po referencji; pełne wartości są w `diagnostics.json` i CSV.

## Stabilność, niezależność i ograniczenia

- Pełna ponowna ekstrakcja ze **wszystkich 228 obrazów**, po fizycznym
  usunięciu oznaczeń z plików wejściowych i bez drzewa referencji:
  identyczne cechy siatki, 205 banków i wyniki obu wybranych metod siatkowych.
  To kontrola niezależności od anotacji i referencji, nie tylko ich ukrycie w UI.
- Braki 10/30/50%, lokalny brak i odwrócenie kontrastu: **60 dokładnych
  porównań** (5 przypadków × 6 ziaren × 2 metody), bez zmiany przypisań
  ani relacji par na siatce.
- Zmiana kontrastu i techniczne przeskalowanie: kolejne 24 porównania.
  EWT/siatka bez zmian. FFT/siatka: przy kontraście zmiana jednej próbki
  w 3/6 ziaren, przy skali w 2/6; każda zmienia 13 relacji par z unii 19292.
  Nie deklarujemy z tego pełnej niezmienniczości dowolnego kontrastu/skali.
- Zakres 250–254 kontra pełne 24 klatki: ponownie dopasowano **bank i
  grupowanie**. EWT zmienia bank 15 → 12 filtrów, ale w obu zakresach
  zostaje jeden klaster. FFT zmienia członkostwo katalogu w 3/5 klatek
  na siatce (łącznie 20 próbek) i 5/5 przy centrach (376 elementów).
  Końcowe domeny są puste w obu zakresach na tych pięciu klatkach:
  ich zgodność nie dowodzi stabilności poprawnego wyniku.
- Nie testowano uogólnienia na inne akwizycje, pełnych 268 klatek, marginesów
  o innych rozmiarach ani automatycznego wyboru skal poza 24/36 px i lagami
  6–24 px. Prototyp zakłada w pełni zmierzone, skończone obrazy takie jak
  wejście 14. Płaskie/degenerujące widmo i dowolne maski braków pomiaru
  nie są zwalidowane; biblioteka ma niepełną obsługę pustych granic pasm.
- Nie określano masek pokrycia, powierzchni wysp, skal nm ani dokładności
  granic pikselowych. Nie zbudowano rozpoznanego katalogu typów sieci.

## Odtworzenie, koszt i sprawdzenia

Instrukcja oraz jedno polecenie odtworzenia są w `README-texture.md` na
gałęzi prototypu. Runner: `stmdomains/prototypes/run_texture_trial.sh`,
argumenty: artefakt `orientation-and-joining`, artefakt `sbc-matid-domains`
i nowy katalog wynikowy. Wszystkie etapy wykonano; później złożono runner.
Nie uruchamiano ponownie całej próby przez sam wrapper Bash.

CPU, po jednym wątku BLAS/OpenMP, bez GPU i treningu:

| Etap | Czas | Szczyt RSS procesu |
| --- | ---: | ---: |
| Cechy, 228 obrazów / oba warianty próbkowania | 842.47 s | 803324 KiB, ok. 785 MiB |
| Predykcja 32 konfiguracji | 25.85 s | 499428 KiB, ok. 488 MiB |
| Ocena z oboma wcześniejszymi kandydatami | 3.64 s | Nie mierzono osobno |
| Pełna ekstrakcja bez oznaczeń / referencji | 785.32 s | 786744 KiB, ok. 768 MiB |

To czasy lokalnej próby, nie benchmark produkcji; część weryfikacji biegła
równolegle. Same cechy zajmują 257917431 B. Cały skopiowany artefakt:
3455 plików, 891338928 B, zgodność kopii sprawdzona SHA-256 każdego pliku.

Zależności: Python z lokalnego `netcat`, NumPy 2.2.5, SciPy 1.15.2,
scikit-learn 1.6.1, Pillow 11.2.1, matplotlib 3.10.1; pełne wersje i hashe
w `provenance.json`. `pyewt 1.0.0` oraz wymagany import
`connected-components-3d 3.26.1` zainstalowano wyłącznie do
`/tmp/stmdomains-issue17-deps`. Środowisko netcat i główna konfiguracja
pozostały bez zmian. Brak zmian modułów współdzielonych.

Weryfikacja: 1824 wyniki zgodne ze schematem, 228 identycznie odtworzonych
wejść bez anotacji, zgodność hashy kodu ekstrakcji i predykcji, pełny replay
opisany wyżej. Optymalizacja pętli ACF przed końcowym obliczeniem:
12 porównań cech bitowo identycznych; następnie przeliczono całość.
QtWebEngine offscreen: **42 kontrole** scenariuszy, widoków, konfiguracji
oraz referencji, bez błędów JS i poziomego przepełnienia. Obejrzano zrzut
podglądu i wykres. Sprawdzono składnię Python/Bash i diff. Nie wykonywano
testów produkcyjnej aplikacji ani natywnego GUI.

`features/` przechowuje opisy, pozycje, energię, autokorelację, podparcie
okna, wektory translacji i banki. `predictions/` zawiera etykiety przed/po
bramce, przypisania centrów i katalogi. `assignments/` rozróżnia przez
`sampling_kind` próbki siatki od molekuł. `evaluation/`, `controls.csv`,
`diagnostics.json` i `verification.json` zapisują ocenę i ograniczenia.
Wszystkie duże dane pozostają lokalne, poza Git.

## Decyzja i następne porównanie

Użytkownik: **„Tak — zachowaj porównanie i zamknij 17”**. Issue 17 ma status
`resolved` jako eksperyment; żadna konfiguracja nie została przyjęta do programu.

Kolejny krok mapy to przygotowanie gotowych cech w 18, następnie ich
porównanie w 19 z zapisanymi wynikami tej próby. Przygotowanie własnego
treningu 20 jest niezależną ścieżką. Nie uruchomiono ich w ramach 17.
Dalsze porównanie musi oddzielać jakość cech od odmowy bramki porządku,
uwzględniać podziały pojedynczej sieci i odłożone małe różnice orientacji.
Nie wystarczy obniżyć progu, wymusić trzy grupy lub wygładzić kontur level set:
te operacje nie dowodzą istnienia domen ani poprawnego rozpoznania struktury.
