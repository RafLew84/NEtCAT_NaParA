# Odbiór NanoTrack w działającym GUI

Wykonuj z katalogu repo przez wspólny launcher UTF-8 w środowisku `netcat`.
Domyślnie uruchamia się widoczne okno Windows. Runner używa prawdziwych
kontrolek, bibliotek oraz publicznych metod Save/Open; zapisuje zrzuty, które
wykonawca ogląda po próbie. To automatyczny odbiór GUI, nie ręczny test człowieka.

## Tryby

Geometrię Original ↔ Aligned sprawdza tryb `aligned`. Tworzy plik MPP i sesję
`S1-aligned.nanotrack` (6 klatek 96×64, skala X=2/Y=1 nm/px), znane całkowite
i subpikselowe dx/dy, maskę braków oraz klatki bez własnej korekty. Sprawdza
wartości float64, położenie konturów, edycję uchwytów ROI/polilinii, rzeczywisty
klik myszy i Save/Open. Nie uruchamia estymacji ani modeli ML:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -ScriptPath scripts/run_nanotrack_acceptance.py aligned
```

Gotowa sesja otwiera się na klatce 2 z włączonym `Show Aligned`. Przełączanie
tej opcji zachowuje zaznaczony obiekt. Klatka 3 pokazuje czarny obszar braków
i puste brzegi; klatki 5–6 pokazują „Brak własnego dx/dy — bez przesunięcia”.
Plik `S1-truth.json` podaje niezależnie znane wartości i przesunięcia.
Kontrolny wynik preprocessingu w tej próbce to jawny syntetyczny offset +0,25;
nie jest wynikiem BM3D ani oceną skuteczności rejestracji.

Podgląd Original/Aligned materializuje pojedyncze klatki float64, z cache
ograniczonym do 32 MiB. Próbka biliniowa wymaga ważności wszystkich wkładów
z niezerową wagą. Braki pozostają NaN w danych; czarne tło jest osobną warstwą
wyświetlania. Tę samą ścieżkę danych stosuje Expanded.

Odbiór Expanded tworzy dwie gotowe sesje S1, sprawdza wspólne płótno,
zmianę skrajnego dx/dy, wybór źródła, edycję i Save/Open:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -ScriptPath scripts/run_nanotrack_acceptance.py expanded
```

`S1-expanded.nanotrack` ma płótno **102 × 70 px**, początek **(-2,-3)**
i skalę **2 / 1 nm/px**. `S1-expanded-extreme.nanotrack` zmienia przesunięcie
klatki 3 na **(-7.5,6.25)**: płótno ma **108 × 74 px**, początek **(-8,-3)**.
`Apply Registration` włącza domyślne Expanded; `Show Aligned` wybiera rozmiar
źródła. Wyłączenie `Apply Registration` wraca do obrazu bez wyrównania.
Wspólny plan obejmuje wszystkie klatki sekwencji, z identity dla brakujących
wyników. Nie materializuje całego filmu. Odmowa zbyt dużego płótna następuje
przed alokacją, przy szacunku buforów ponad 512 MiB, bez zmniejszania obrazu.
Wejścia trackerów pozostają osobnym zadaniem wdrożeniowym.

Krótka próba generuje S1 o znanej skali, z klatką stałą, NaN i dużym offsetem.
Sprawdza naprawę, rzeczywisty BM3D, precyzję, przełączanie źródła i Save/Open:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -ScriptPath scripts/run_nanotrack_acceptance.py quick
```

Pełny przebieg obejmuje wszystkie klatki wskazanego MPP: ECC, jawny testowy
znacznik trwałości, naprawę, BM3D, zachowanie raw/dxdy/adnotacji, Save/Open
i widoki Original/Processed/Aligned:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -ScriptPath scripts/run_nanotrack_acceptance.py full --input data/nanotrack_registration/dobre/MOVIE_2.MPP
```

Sprawdzenie istniejącej sesji otwiera ją, zapisuje nową kopię do katalogu
odbioru, ponownie ją otwiera i porównuje cały publiczny snapshot. Nie liczy
ponownie BM3D ani rejestracji i nie nadpisuje wejściowej sesji:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python_utf8.ps1 -ScriptPath scripts/run_nanotrack_acceptance.py session --input .scratch/nanotrack-registration-export/acceptance/runs/ticket-02/MOVIE_2-repair-bm3d-registered-v2.nanotrack
```

Limity czasu: `quick`, `session`, `aligned` i `expanded` 180 s, `full` 7200 s. Nadpisanie:
`--timeout 300`. Przekroczenie czasu kończy własny proces roboczy, zapisuje
`timeout` i zwraca kod 1. Awaria procesu bez raportu też jest błędem — runner
sprawdza zakończenie procesu, nie czeka na pojawienie się pliku sygnalizacyjnego.
Ctrl+C kończy własny proces i zapisuje `cancelled`.

`--headless` służy diagnostyce bez pulpitu. Raport jawnie oznacza `offscreen`;
taka próba nie zastępuje wymaganego widocznego odbioru. Brak BM3D w trybach
`quick/full` jest błędem. Tryb `session` nie wymaga ponownego filtrowania.

## Postęp i wyniki

Każde uruchomienie dostaje nowy katalog `.scratch/nanotrack-acceptance/<id>`.
Można wskazać nowy lub pusty katalog przez `--report-dir`; zajęty katalog
zostanie odrzucony, aby zachować wcześniejsze dowody.

- `status.html`: jeden odświeżany widok postępu do otwarcia w przeglądarce.
- `status.json`: ten sam status do krótkiego odczytu narzędziowego.
- `report.json`: końcowy PASS/FAIL, wyniki etapów, czas, kod wyjścia procesu,
  środowisko, identyfikacja wejścia SHA-256 i lista artefaktów.
- `worker-report.json`: szczegóły etapów aktualizowane w trakcie.
- `worker.log`: stdout/stderr, także przy awarii natywnej biblioteki.
- `result.nanotrack`, próbka MPP i zrzuty: gotowe dane do ręcznego odbioru.

Runner wypisuje ścieżkę postępu i wynik końcowy. Licznik klatek pozostaje
w oknie aplikacji i aktualizowanym statusie, zamiast dopisywać kolejne linie
do rozmowy lub logu. W komunikacji z użytkownikiem podawaj zmianę etapu,
problem lub istotną zmianę szacowanego czasu, zgodnie z nadrzędnymi instrukcjami.

PASS wymaga pomyślnego zakończenia procesu i wszystkich rozpoczętych etapów.
Odbiór nie ocenia naukowej skuteczności filtru ani jakości rejestracji na
nieznanym filmie. Save/Open porównuje zapisane wartości i dtype dokładnie.
Nie wymaga bitowo identycznego wyniku dwóch niezależnych uruchomień BM3D.

## Dodawanie następnych scenariuszy

Rozszerzaj `scripts/nanotrack_acceptance/scenarios.py` przez publiczne operacje
aplikacji i etapy `AcceptanceReport.stage`. Wspólny proces nadzorujący obsługuje
limit czasu, log, końcowy raport i awarie. Dane wejściowe pozostają tylko do
odczytu; nowe sesje i zrzuty trafiają do katalogu danego uruchomienia.
