# REG-14 — ręczna próba AKAZE

Status: ready-for-review; odbiór użytkownika jeszcze niewykonany.
[Wyniki i ograniczenia](akaze-results.md), [środowisko](akaze-environment.md),
[testy i przeglądy](reviews/REG-14.md).

Uruchom z katalogu NEtCAT-viewer:

~~~bash
conda activate netcat
python -m stmviewer.main
~~~

Wybierz **AKAZE** w rejestracji filmu, podglądzie pary lub oknie
**Dopasowanie wieloklatkowe…**. Metoda działa na CPU; nie ma pól wag,
ścieżki kodu modelu ani wyboru CUDA. Parametry detektora są stałe,
a opis konfiguracji i diagnostyka są zapisywane z wynikiem.
Przełączenie z Deep/RoMa/LightGlue nie przenosi ich ustawień do AKAZE.

## Wzorzec umożliwiający pełny cykl

1. Otwórz **data/registration-reg14/known.mpp** — osiem klatek 256 × 256.
   Plik jest lokalny; sposób odtworzenia znajduje się w opisie środowiska.
2. Wybierz klatkę 2 i **Porównaj parę…**. Oblicz AKAZE:
   przesunięcie klatki 2 względem 1 powinno wynosić **(+2, −1) px**.
   Dla pary 2→3 oczekuj **(−1, +2) px**.
3. Sprawdź nakładkę, przełączanie obrazów, zoom i gamma. Zmiana prezentacji
   nie zmienia XY ani liczby korespondencji. Hamming nie jest procentową
   pewnością fizycznego dryfu.
4. W głównym oknie kliknij **Rejestruj**. Skumulowane XY względem pierwszej:
   (0,0), (2,−1), (1,1), (−2,0), (3,2), (−1,−2), (0,1), (2,0).
   Wynik pojawia się w aligned; original pozostaje dostępny.
5. Otwórz **Dopasowanie wieloklatkowe…**, wybierz AKAZE i okno 3,
   oblicz kandydata grafu. Oczekuj 18 poprawnie zmierzonych relacji i jednego
   połączonego zbioru ośmiu klatek. Oblicz też wariant Hubera.
6. Kliknij **Zastosuj wynik do filmu**. Samo obliczenie kandydata nie
   zmienia aktywnego aligned. Sprawdź zastosowanie LS i Hubera.
7. Wykonaj ręczną korektę pary o 1 px, zastosuj ją do filmu, obejrzyj dalsze
   klatki i cofnij korektę zgodnie z [instrukcją](manual-movie-corrections-manual.md).

Mały dotychczasowy **tests/stmviewer/fixtures/registration/cpu.mpp** ma za
mało cech dla tego wariantu AKAZE: obie pary dają jedną korespondencję,
przy wymaganym minimum ośmiu. Służy tutaj do sprawdzenia kontrolowanej odmowy,
nie do oczekiwania kompletnego aligned.

## MOVIE_4 i MOVIE_8

Otwórz MOVIE_4 i usuń jego pierwsze dwie klatki przed obliczeniem.
W raporcie i [protokole](manual-protocol.md) numery odnoszą się do pozostałych
362 klatek. MOVIE_8 pozostaw bez usuwania.

Przy obecnych parametrach wszystkie 18 wybranych par daje odmowę, a oba
pełne łańcuchy zatrzymują się na pierwszej parze. Graf okna 3 kończy obliczenia,
ale ma brakujące relacje i rozłączne części — nie można zastosować go do
całego filmu. To spodziewane ograniczenie metody, opisane w raporcie.
Nie trzeba regulować progu Hubera w celu zastąpienia brakujących pomiarów.

Możesz obejrzeć otrzymane relacje i ich ostrzeżenia, porównać tę samą parę
z Deep outdoor/RoMa Turbo oraz otworzyć gotowe sesje:
data/registration-reg14/movie-movie_4/graph-candidate.stmsession
i data/registration-reg14/movie-movie_8/graph-candidate.stmsession.
Nie zawierają automatycznie zastosowanego wyniku.

## Sesja, błędy i eksport

1. Na kompletnym known.mpp zapisz sesję po zastosowaniu i ręcznej korekcie.
   Otwórz ją ponownie: aligned, XY, historia korekty i pochodzenie AKAZE
   mają pozostać. Zapisz także sesję po wybraniu Phase — istniejący wynik
   i niezastosowany kandydat AKAZE nie powinny zniknąć.
2. Zapisz aligned jako MPP wraz z dodatkiem metadanych. Otwórz wynik,
   sprawdź geometrię, brakujące próbki i pochodzenie. Wybór białego
   wypełnienia dotyczy zapisu dla innych czytników; dodatek odtwarza braki.
3. Zapisz AVI w MJPG oraz FFV1, obejrzyj oba w VLC. Film ma pokazywać
   wybrany wygląd aligned; dane pomiarowe pozostają w MPP.
4. Na dłuższym filmie najpierw uzyskaj aligned inną dostępną metodą.
   Włącz ponownie obliczanie grafu AKAZE i kliknij **Anuluj**.
   Wcześniejszy film, korekty i kandydat mają pozostać.
   Odmowa łańcucha AKAZE również nie może zastąpić wcześniejszego aligned.
   Krótki known.mpp może zakończyć się zbyt szybko na ręczne anulowanie.
5. Opcjonalnie sprawdź niedostępność AKAZE bez usuwania OpenCV.
   Zamknij zwykłą aplikację i uruchom w osobnym procesie:

~~~bash
python -c "import cv2; cv2.AKAZE_create = None; from stmviewer.app import main; raise SystemExit(main())"
~~~

Otwórz gotową sesję known.mpp: podgląd i eksport powinny działać.
Nowe obliczenie AKAZE ma wyjaśnić brak detektora; Phase pozostaje dostępne.
Po zamknięciu tego procesu zwykłe uruchomienie przywraca dostępność.

Automatyczne testy Qt, ponowny odczyt sesji i dekodowanie AVI wykonano.
Ręczne GUI, VLC oraz Windows pozostają do odbioru użytkownika.
