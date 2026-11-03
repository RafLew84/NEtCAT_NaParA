# REG-13/14: czy jasność powoduje odmowy?

2026-11-02, baza e0cd6b4. Zgłoszenie użytkownika: AKAZE odmawia pierwszej
pary MOVIE_4; możliwy wpływ różnej jasności klatek w REG-13 i REG-14.

**Wniosek:** sposób przygotowania kontrastu ogranicza wykrywanie cech AKAZE,
ale sprawdzone korekty jasności/kontrastu nie usunęły odmowy pierwszej
rzeczywistej pary MOVIE_4 ani w AKAZE, ani w LightGlue. Nie jest to poprawka
programu ani potwierdzenie jednej przyczyny wszystkich niepowodzeń.

## Odtworzenie i hipotezy

Dwa publiczne backendy odtworzyły pierwotne odmowy. MOVIE_4: klatki źródłowe
3→4, czyli 1→2 po usunięciu pierwszych dwóch. AKAZE: jedna korespondencja
przy wymaganych ośmiu. LightGlue: 2/32 zgodne wektory przy minimum czterech.
Powtórny baseline w poniższej próbie dał to samo.

Hipotezy ustalone przed próbą:
1. Niski/nierówny kontrast struktur ogranicza punkty; wzmocnienie kontrastu
   powinno zwiększyć ich liczbę i ewentualnie liczbę zgodnych wektorów.
2. Zmiany struktur/tearing mogą ograniczać zgodność geometrii; samo dodanie
   punktów wtedy nie zapewni wspólnej translacji.
3. Globalna zmiana liniowa jasności powinna być usuwana przez obecną
   normalizację min–max; jej sztuczne dodanie nie powinno zmieniać wyniku.

Próba dotyczy diagnozy, bez zmiany estymatora, progów, UI ani danych źródłowych.
Nie ma podstaw do regresyjnego testu „ta para musi się dopasować”, ponieważ
nie znamy jej niezależnego prawdziwego XY.

## Co trafia do metod

[LightGlue](../../../stmviewer/lightglue_matcher.py) dostaje niezależny
min–max float32 0–1 dla każdej klatki.
[AKAZE](../../../stmviewer/akaze_matcher.py) dostaje analogicznie uint8 0–255.
Dla dodatniego a, bez nasycenia/obcięcia, transformacja a·I+b znosi się w
min–max; numeryczne zaokrąglenia mogą pozostać. Gamma podglądu nie jest wejściem.

Nie oznacza to równości rozkładów jasności ani lokalnego kontrastu.
Dla pierwszej pary surowe percentyle 1 i 99 są identyczne:
−0,230957 i 0,236328. Ekstrema są jednak różne:
A [−0,569336; 1,047363], B [−0,333008; 1,009766].
Po min–max mediany wynoszą około 0,322 i 0,208.
Centralne 98% wartości zajmuje tylko około 29% i 35% pełnej skali.
Nie ustalono, które ekstrema są zakłóceniem, a które strukturą próbki.

## Próba porównawcza

Pięć przypadków × sześć wariantów × dwie metody = **60 prób**:
MOVIE_4 bieżące 1→2, 29→30, 160→161; MOVIE_8 1→2;
oraz kopia pierwszej badanej klatki MOVIE_4 ze znaną translacją.

Warianty ustalono z góry: obecne przygotowanie; wyłącznie B'=2B+20·ptp(B);
rozciągnięcie percentyli 1–99 osobno obu obrazów z obcięciem poza zakresem;
dopasowanie histogramu B do A; kontrolna kwantyzacja uint8;
CLAHE clipLimit=2, tileGridSize=(8,8), osobno obu obrazów, po uint8.
Każdy wariant porównujemy z bazą; kontrola uint8 oddziela wpływ kwantyzacji
od dodatkowej operacji CLAHE. Dane przekształcano tylko w roboczych kopiach.

CLAHE lokalnie wyrównuje kontrast z ograniczeniem jego wzmacniania;
nie jest samym przesunięciem średniej jasności.
[Dokumentacja OpenCV](https://docs.opencv.org/4.13.0/d5/daf/tutorial_py_histogram_equalization.html).
Detektor AKAZE ma jawny próg odpowiedzi i pozostałe stałe parametry:
[API OpenCV 4.11](https://docs.opencv.org/4.11.0/d8/d30/classcv_1_1AKAZE.html).
W próbie użyto zainstalowanego OpenCV 4.11.0, czterech wątków CPU i
LightGlue na CUDA z niezmienionymi lokalnymi wagami.

### Pierwsza para MOVIE_4

Ułamki to zgodne wektory / poprawne korespondencje. Przy mniej niż ośmiu
korespondencjach konsensus nie jest uruchamiany; zapisane zero nie oznacza
zmierzonej liczby inlierów.

| Wariant | Punkty AKAZE A/B | AKAZE | LightGlue |
| --- | ---: | --- | --- |
| obecny min–max | 1 / 4 | 1 korespondencja, odmowa | 2/32, odmowa |
| globalna zmiana B | 1 / 4 | 1 korespondencja, odmowa | 2/32, odmowa |
| percentyle 1–99 | 230 / 241 | 1/99, odmowa | 2/13, odmowa |
| histogram B do A | 1 / 2 | 1 korespondencja, odmowa | 2/26, odmowa |
| kontrolne uint8 | 1 / 4 | 1 korespondencja, odmowa | 3/26, odmowa |
| CLAHE | 59 / 148 | 1/34, odmowa | 1/9, odmowa |

Żadna próba nie rozwiązała tej pary. Dopasowanie histogramów wyrównało
prezentację jasności, ale nie dostarczyło zgodnych korespondencji.
W obu metodach wynik globalnej zmiany liniowej pozostał taki sam.
Obraz wejściowy LightGlue był numerycznie identyczny; w AKAZE na jednej
parze maksymalna różnica wyniosła jeden poziom uint8, bez zmiany wyniku.

### Kontrola ze znanym XY

Przesunięto tę samą klatkę metodą np.roll: ruch obrazu (+7,−5), oczekiwane
dopasowanie (−7,+5). To kontrola detektora i przygotowania, bez zmian
kontrastu pomiędzy klatkami, bez tearingu; zawija brzegi.

- AKAZE przy obecnym min–max: tylko 1/1 wykrytych punktów, odmowa.
- AKAZE po percentylach: 214/216 zgodnych, dokładnie (−7,+5).
- AKAZE po CLAHE: 49/49 zgodnych, błąd największej osi około 0,0018 px.
- LightGlue: znane XY odzyskane we wszystkich sześciu wariantach.

To potwierdza, że AKAZE jest ograniczane słabym kontrastem nawet przy
idealnie zachowanej geometrii; nie dowodzi, że taki sam zabieg naprawi
rzeczywiste sąsiednie klatki.

### Pozostałe pary

- MOVIE_4 29→30: wszystkie warianty obu metod nadal odmawiają.
- MOVIE_4 160→161: AKAZE po percentylach zwrócił słabo poparty wynik
  (−3,517; 4,279), 4/108 zgodnych; CLAHE nadal odmawia. LightGlue ma wyniki
  w każdym wariancie, lecz XY zmienia się od (−2,5) do (0,5).
- MOVIE_8 1→2: AKAZE przechodzi z odmowy do wyniku po percentylach
  (13,957; 0,668), 43/422 zgodnych, oraz po CLAHE (13,680; 0,651), 45/391.
  LightGlue daje wyniki w każdym wariancie, około (14–15; 0–1).
  Bez niezależnego XY nie uznajemy samego przekroczenia progu za naprawę.

Poprawa kontrastu pomaga więc w części przypadków, ale może też zmniejszyć
liczbę zgodnych korespondencji lub zmienić ruch. Hipoteza wpływu geometrii,
szumu i tearingu pozostaje możliwa; nie rozdzielono tych przyczyn.

## Artefakty i dalszy krok

Lokalnie: data/registration-brightness-20261102/summary.json,
first-pair-inputs.png oraz brightness-ablation.py.
Manifest zawiera hashe MOVIE_4/MOVIE_8 i wartości klatek, konfigurację,
surowe statystyki, transformacje, wyniki oraz diagnostykę wszystkich prób.

Odtworzenie w netcat, z katalogu Viewera, do nowego katalogu:

~~~bash
PYTHONPATH=. OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 python data/registration-brightness-20261102/brightness-ablation.py data/registration-brightness-repeat
~~~

Ewentualny następny etap: opcjonalne, wersjonowane przygotowanie kontrastu
wyłącznie do estymacji, porównane na wspólnej liście par i wzorcach. Original,
renderowane aligned i dane MPP mają nadal pochodzić z wartości pomiarowych.
To rekomendacja do osobnego zadania, nie dodana funkcja ani automatyczny
wybór wariantu, który akurat przekroczył próg.

Nie zmieniono kodu/progów ani statusu REG-13/14. Nie uruchamiano ponownie
pełnych testów programu dla samej diagnozy i dokumentacji; wykonano
opisane rzeczywiste próby. Nie sprawdzono całych filmów po korekcji
kontrastu ani jakości ręcznej. Windows nie był badany.
