# REG-14 — środowisko i odtworzenie prób AKAZE

AKAZE używa istniejącego OpenCV w środowisku netcat. Nie instalowano pakietów,
nie pobierano kodu ani wag. W wykonanych próbach: Python 3.12, opencv-python
4.11.0.86 (cv2 4.11.0), NumPy 2.2.5. Metoda działa na CPU, bez Torch,
CUDA i osobnego procesu modelu. Zapisane wyniki można otworzyć bez dostępnego
detektora; nowa rejestracja sprawdza dostępność OpenCV.

## Stała konfiguracja

Adapter: akaze-mldb-crosscheck-v1. AKAZE: MLDB, descriptor_size=0,
descriptor_channels=3, threshold=0.001, nOctaves=4, nOctaveLayers=4,
diffusivity=DIFF_PM_G2, max_points=−1. Deskryptory binarne porównuje
BFMatcher z NORM_HAMMING i crossCheck=True. Wszystkie wzajemne pary
trafiają do konsensusu; bez dodatkowego progu odległości i ważenia score.

Dokumentacja pierwotna: [AKAZE w OpenCV 4.11](https://docs.opencv.org/4.11.0/d8/d30/classcv_1_1AKAZE.html)
oraz [BFMatcher](https://docs.opencv.org/4.11.0/d3/da1/classcv_1_1BFMatcher.html).
Użyta dystrybucja OpenCV jest objęta Apache 2.0:
[warunki OpenCV](https://opencv.org/license/).
Korzystamy z zainstalowanego API, bez kopiowania obcego kodu do repozytorium.
Nie dodano SPMUtil ani kodu sterowania mikroskopem.

Przygotowanie: natywny rozmiar, skala XY=(1,1), bez paddingu.
Skończone wartości są niezależnie dla każdego obrazu mapowane min/max na
uint8 0–255 z zaokrągleniem do najbliższej liczby (np.rint).
Stałe obrazy i pojedynczy wiersz/kolumna nie mają użytecznych cech;
otrzymują lokalną odmowę. NaN/Inf nie są zamieniane w sztuczną teksturę.
Zoom, gamma i kolory podglądu nie są wejściem algorytmu.

Konsensus translation-consensus-v2 jest niezmieniony względem RoMa/LightGlue.
Minimum: 8 poprawnych korespondencji i 4 zgodne wektory, promień 2 px.
Słabe poparcie przestrzenne daje ostrzeżenie; brak minimum daje odmowę.
Sesja zapisuje wersję adaptera, OpenCV i hash jego kompilacji, konfigurację,
zakresy wartości i mapowanie współrzędnych. Schemat sesji/grafu v9 oraz
dodatku MPP v12 odróżnia AKAZE; bez AKAZE zapis zachowuje wcześniejsze wersje.

## Odtworzenie

Z katalogu NEtCAT-viewer, po conda activate netcat:

~~~bash
export PYTHONPATH=.:tests/stmviewer
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
python tests/stmviewer/diagnostics/akaze_trial.py --mode verify
python tests/stmviewer/diagnostics/akaze_trial.py --mode pairs
python tests/stmviewer/diagnostics/akaze_trial.py --mode patterns
python tests/stmviewer/diagnostics/akaze_trial.py --mode known
python tests/stmviewer/diagnostics/akaze_trial.py --mode movie --source data/MOVIE_4.mpp --drop-first 2
python tests/stmviewer/diagnostics/akaze_trial.py --mode movie --source data/MOVIE_8.mpp
python tests/stmviewer/diagnostics/akaze_trial.py --mode visuals
~~~

Harness używa czterech wątków OpenCV wyłącznie w swoim procesie.
Aplikacja nie przestawia globalnej liczby wątków. Powyższe polecenia są dla
Linuksa; nie zweryfikowano wykonania Windows. Na powtórną próbę podaj nowy
katalog przez --output, aby zachować wcześniejsze sesje filmu.
Tryb known sam generuje ośmioklatkowy wzorzec; nie potrzebuje pomiarów STM
ani poprzednich modeli. Dla verify/patterns/visuals potrzebne są lokalne
artefakty REG-13 i oryginalne MOVIE_4/MOVIE_8. Bez tych danych nie można
odtworzyć porównania samym klonem repozytorium.

[Harness](../../../tests/stmviewer/diagnostics/akaze_trial.py) zapisuje
wyniki w data/registration-reg14. Pliki pomiarów, sesje i filmy pozostają
lokalne, poza Git. Raport baseline-verification.json zawiera sumy poprzednich
raportów, potwierdzenie identyczności wartości wszystkich wejściowych par
oraz sumy niezmienionego kodu dotychczasowych estymatorów.
[Wyniki](akaze-results.md) oddzielają czasy bieżących prób CPU od historycznych
prób CUDA — nie są to pomiary przyspieszenia na tym samym urządzeniu.
