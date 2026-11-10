# Pilotaż porównania metod STM Domains

Data: 2026-10-19. Pytanie:
[Jak porównać metody wykrywania wysp i domen w serii?](issues/05-stable-types-across-frames.md).
To eksploracja wykonana na bezpośrednie polecenie użytkownika przed odbiorem
szkieletu i ustaleniem referencji. Nie wybrano metody do aplikacji.

## Wynik próby

Wspólny katalog dla zaznaczonego zakresu da się obliczyć i porównać w podglądzie.
Proste badane warianty nie spełniają jednak jeszcze uzgodnionej definicji typów
i domen. Obrót zachowuje dominujący typ sąsiedztwa w kontrolnym przykładzie,
lecz rozstaw większy o 25% nie tworzy odrębnego typu. Zwykła sieć bywa dzielona
na kilka komponentów, a zadana granica dwóch domen nie daje poprawnego podziału.
Żaden wynik na TTMAPP nie jest oceną trafności bez niezależnej referencji.

Wyniki uzasadniają dalszą próbę z lepszą kontrolą skali, doborem cech struktury
i wykrywaniem granic niedopasowania. Nie dowodzą nieskuteczności całych rodzin
FFT, analizy grafu czy level set; dotyczą tylko opisanych prostych wariantów.
Po otrzymaniu prototypu i wniosku użytkownik polecił dopisać tickety do dalszej
analizy. Zamknięcie pilotażu dotyczy wskazania luk, nie akceptacji skuteczności.

## Materiał i odtworzenie

Źródła prototypu: osobna gałąź `prototype/stmdomains-method-comparison`;
konkretny commit i ścieżki podaje ticket. Kod nie trafia na gałąź aplikacji.
Pliki `stmdomains/prototypes/method_comparison.py`, odpowiadający szablon HTML
i README zawierają generator, czysty moduł JS oraz instrukcję odtworzenia.

Gotowy lokalny plik, otwierany w przeglądarce bez serwera:
`/home/rlew/projekty/NEtCAT-domains/.scratch/method-comparison/pilot.html`.
Obok są `pilot.json`, `inspection.json` oraz zrzuty ekranu. HTML zawiera obrazy
pomiarowe, więc wraz z pozostałymi dużymi artefaktami pozostaje poza Git.

Z katalogu worktree prototypu, w środowisku `netcat`:

```bash
python stmdomains/prototypes/method_comparison.py \
  --session /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/detection_full.moltrack.json \
  --mpp /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  --out .scratch/method-comparison/pilot.html
```

Wejście jest tym samym zapisem co w [audycie importu](import-geometry-audit.md):

| Materiał | SHA-256 |
| --- | --- |
| MolTrack JSON | `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e` |
| MPP | `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66` |

Wybrano klatki o indeksach od zera: **0, 39, 40, 63, 68, 120, 200, 267**.
To rozpoznawczy wybór obejmujący początek/koniec serii, zanik masek SAM,
brak detekcji i nieliczne detekcje; nie reprezentatywna próba statystyczna.
Maski SAM nie są używane, również jako prawda odniesienia.
Wykorzystane liczby centrów: odpowiednio **288, 224, 158, 0, 3, 265, 61, 308**.

Obrazy 256 × 256 px pochodzą z czytnika NanoTrack obracającego natywny MPP
o 180°. Centra bbox z `expanded_aligned` przeniesiono do oryginału zgodnie
z zapisanymi globalnymi przesunięciami i paddingiem LTRB 224,139,0,13.
Wyniki liczone są w oryginalnym polu, a podgląd aligned przenosi obraz i nakładki
na płótno 480 × 408 px. Jest to translacja podglądu, nie ponowna rejestracja
ani dokładne odtworzenie interpolacji intensywności MolTrack. Większość
zapisanych rejestracji ma niską pewność; nie potwierdzamy poprawności wyrównania.
Wszystkie odległości są w px; brak wiarygodnej kalibracji fizycznej.

## Porównane warianty

| Warstwa | Prosty wariant | Parametry |
| --- | --- | --- |
| Pokrycie z oznaczeń | Suma centrów wygładzona Gaussowsko, próg 20% maksimum | σ = 0,45 albo 0,65 mediany najbliższych odległości w danej klatce |
| Pokrycie z obrazu | Morfologiczny Chan–Vese na wygładzonym obrazie; jaśniejsza faza uznana za materiał | σ = 3 albo 6 px, 45 iteracji, smoothing=2, lambda1=lambda2=1, inicjalizacja powyżej mediany |
| Struktura z oznaczeń | Lokalny rozstaw, liczba sąsiadów, moduły harmonicznych kątów i zmienność odległości | Promień = 1,35 albo 1,65 mediany najbliższych odległości; min. 3 sąsiadów; harmoniczne 2,3,4,6 |
| Struktura z obrazu | Lokalna moc FFT z oknem Hanna, rozstaw dominującej częstotliwości i moduły harmonicznych | Okno 31 albo 47 px, krok siatki 12 px; okresy 6–28 px; harmoniczne 2,4,6 |

Normalizacja obrazu używa percentyli 2–98. Gamma zmienia tylko wyświetlanie.
Chan–Vese jest wariantem odniesienia dla segmentacji regionowej;
**nie jest implementacją hybrydy Gibou–Fedkiwa**. Nie porównano więc tych dwóch
konkretnych algorytmów i nie rozstrzygnięto przewagi Fedkiwa.

Katalog jest dopasowany **wspólnie do wszystkich zaznaczonych klatek**, osobno
dla cech sąsiedztwa i FFT, zgodnie z odpowiedzią użytkownika. Wykorzystuje
deterministyczne k-means z inicjalizacją najdalszymi punktami; każdy punkt ma
jednakową wagę. Standaryzacja cech ma dolne ograniczenie skali 1 px dla rozstawu
i 0,15 dla pozostałych cech. Podstawowa próba: maksymalnie 3 klastry, próg
regularności 0,45, tolerancja orientacji 15°, minimum 5 punktów komponentu.
Dodatkowo sprawdzono 2 klastry oraz większą skalę.

Punkty odległe od klastra bardziej niż jego 95. percentyl odległości pozostają
bez typu; promień ma minimum 0,25 w przestrzeni standaryzowanej. Mała różnica
odległości do dwóch klastrów daje niejednoznaczność. To robocze reguły próby,
nie skalibrowane prawdopodobieństwa ani walidator nowych typów.
Osobno pokazano brak danych i niespełnienie progu regularności. Żadnego z tych
stanów nie nazwano automatycznie fizycznym nieporządkiem.

Komponenty łączą punkty tego samego klastra i okresu symetrii, o podobnej
orientacji; promień łączenia to promień sąsiedztwa albo 17,1 px na siatce FFT.
Nie mierzą fazy wzoru ani granic powierzchni domen. Pokrycie jest odrębną
warstwą, nie bramkuje FFT: cechy podłoża też mogą wejść do katalogu.
Kierunku cechy FFT nie utożsamiamy jeszcze z fizyczną osią sieci.

Zmiana zestawu lub parametrów wymaga nowej wersji katalogu. G1/F1 to odrębne
katalogi metod; numery nie mają zapewnionej tożsamości między próbami.
Rzadki wzór może zniknąć wśród liczniejszych punktów. Nie wykazano rozpoznawania
rzadkich/nowych typów, a wspólnie analizowane dane nie są niezależnym testem.

## Kontrole syntetyczne

Wszystkie cztery kontrole to 121 punktów sieci kwadratowej, rozmytych σ=2,2 px,
na obrazie 256 × 256 px: baza o odstępie 16 px, obrót 25°, odstęp 20 px oraz
przesunięcie prawej połowy o 8 px. Oczekiwane liczby domen: **1, 1, 1, 2**.
Umowna referencja pokrycia kończy się pół odstępu poza skrajnymi punktami;
biały kontur i czerwona granica domen są dostępne w prototypie.

| Kontrola | Komponenty sąsiedztwa: K=3 / K=2 | Komponenty FFT: K=3 / K=2 |
| --- | --- | --- |
| Baza | 5 / 1 | 1 / 1 |
| Obrót 25° | 5 / 1 | 4 / 4 |
| Rozstaw +25% | 5 / 1 | 0 / 0 |
| Granica przesunięcia | 5 / 3 | 3 / 3 |

Tabela dotyczy mniejszej skali i progu 0,45. Nie wystarczy zgodna liczba
komponentów: FFT nie przypisało typu w żadnym z 64 punktów centralnego pola
`|x−128|<50, |y−128|<50` w tych kontrolach, a jego komponenty pojawiają się
głównie przy brzegu płata. Cechy obrazu reagują więc tu na obwiednię i okno.

Dla K=3 dominujący typ sąsiedztwa w środku bazy, obrotu i zwiększonego rozstawu
jest ten sam (G3). Dla K=2 także pozostaje wspólny (G2). Obrót jest zachowany,
lecz rozstaw nie został rozdzielony. Brzegi i linia niedopasowania potrafią
utworzyć osobne klastry, zużywając dostępną liczbę typów. Przy większej skali
i niezmienionym progu wszystkie 121 punktów każdej kontroli sąsiedztwa wypada
poniżej progu: promień obejmuje kolejną powłokę i zmienia cechy kątowe.

IoU maski pokrycia względem umownej obwiedni:

| Kontrola | Gęstość: mniejsza / większa skala | Chan–Vese: mniejsza / większa skala |
| --- | --- | --- |
| Baza | 0,914 / 0,859 | 0,934 / 0,987 |
| Obrót | 0,918 / 0,856 | 0,941 / 0,984 |
| Większy rozstaw | 0,915 / 0,846 | 0,389 / 0,965 |
| Granica przesunięcia | 0,913 / 0,858 | 0,932 / 0,984 |

Zmiana skali silnie wpływa na wynik. Są to łatwe, sztuczne obrazy i umowne
maski kontrolne, nie dowód skuteczności na STM. Nie sprawdzono jeszcze osobno
defektów, pasów nieuporządkowanych, małych wysp, ucięć ani rzadkich typów.

## Obserwacje TTMAPP

Nie ma referencji pokrycia ani domen. Raportujemy propozycje i czułość,
bez precision/recall, trafności czy zatwierdzonych liczebności fizycznych domen.

- Klatka 0: pokrycie z centrów **80,2% → 87,5%** przy zwiększeniu skali,
  jedna wyspa; Chan–Vese **48,6% → 51,3%**, liczba komponentów **31 → 11**.
  Rozbieżność wymaga oceny względem ręcznej granicy warstwy.
- Klatka 63: brak oznaczeń daje **brak propozycji** z centrów, nie zerowe
  pokrycie. FFT i segmentacja obrazu nadal działają.
- Klatka 68: z trzech centrów estymowany rozstaw wynosi ok. 90 px.
  Maska gęstości obejmuje **45,5% → 78,8%** obrazu. To demonstracja zawodności
  automatycznej skali przy nielicznych danych; w UI widnieje ostrzeżenie.
- Dla K=3 i mniejszej skali klatka 0 ma **12** komponentów sąsiedztwa i **2** FFT;
  większa skala daje odpowiednio **4** i **12**. Bez referencji nie wskazuje to
  lepszego wariantu, tylko znaczną wrażliwość.

## Koszt, powtarzalność i kontrola działania

Lokalne środowisko: Python 3.12.12, NumPy 2.2.5, SciPy 1.15.2,
scikit-image 0.25.2, Pillow 11.2.1; inspekcja HTML w QtWebEngine/Qt 6.9.0.

- Generator: około **5,54 s**, szczyt RSS **596,5 MiB**, HTML około **3,4 MiB**.
  RSS obejmuje wczytanie całego MPP i JSON; nie jest pamięcią samego algorytmu.
- W tej próbie na klatkę: cechy sąsiedztwa zwykle 1–10 ms, FFT 15–24 ms,
  gęstość 1–11 ms, Chan–Vese 150–180 ms. To pojedyncze lokalne pomiary,
  nie benchmark; pierwszy przebieg może być wolniejszy.
- Interaktywny katalog i komponenty dla ośmiu klatek: **51,0 ms**;
  powtórzenie **48,2 ms**, identyczne przypisania i komponenty.
- Anulowanie między klatkami zachowało poprzedni przyjęty wynik i numer wersji;
  wynik częściowy nie zastąpił katalogu. Nie oceniono anulowania przygotowania
  cech, opóźnienia najdłuższego etapu ani pracy na całych 268 klatkach.
- Zmiana zakresu na dwie klatki utworzyła nowy katalog; pusty wybór nie uruchamia
  próby. Sprawdzono również widok raw/aligned, gamma, brak oznaczeń, syntetyczne
  nakładki, scenariusze prowadzone i brak komunikatów błędów JavaScript.

Inspekcja interaktywnego prototypu i zrzutów nie zastępuje testów aplikacji.
Nie dodawano zestawu testów ani nie uruchamiano testów produkcyjnego GUI.
Nie zmierzono pamięci przeglądarki, długich serii, innych akwizycji ani pracy
na innym sprzęcie. Zestaw 12 obrazów pozwala wykryć luki, nie przyjąć metody.

## Konkretna luka do dalszej próby

Potrzebne są niezależne oznaczenia płata i domen w TTMAPP oraz ocena ich
niepewności w [pytaniu o referencje i jakość](issues/04-reference-and-quality.md).
Należy osobno sprawdzić stabilny dobór pierwszego sąsiedztwa, cechy rozstawu
odporne na brzeg/defekt, skalę okna FFT obejmującą wystarczającą liczbę okresów
i informację pozwalającą rozpoznać granicę niedopasowania. Ponadto potrzebna
jest kontrola rzadkich typów i powtarzalność po zmianach składu katalogu.
Samo regulowanie K, progu lub wygładzania do uzyskania oczekiwanej liczby domen
na tych samych kontrolach nie byłoby niezależną walidacją.
