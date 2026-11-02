# REG-11: RoMa v2 — wyniki implementacji i prób

Data: 2026-11-02. Baza: `3a3a684`; implementacja: `cfc1547`.
Status użytkowy: **done** — użytkownik potwierdził „testy manualne ok”
2026-11-02. [Instrukcja odbioru](roma-manual.md).
Poparcie korespondencji i kompletność grafu nie stanowią potwierdzenia
poprawnego dryfu STM. Potwierdzenie odbioru nie zmienia wyników
automatycznych prób ani odnotowanych ograniczeń modelu.

## Zaimplementowany przebieg

RoMa v2 można wybrać dla pary, sąsiednich klatek filmu oraz grafu LS/Hubera.
Wszystkie trzy drogi wykorzystują ten sam estymator pary i istniejący
`translation-consensus-v2`. Obrazy nadal otrzymują tylko globalną translację;
gęste pole nie deformuje danych pomiarowych, nie ma dodatkowego ECC.

Proces GUI i reszta aplikacji działają w `netcat`. Inny interpreter obsługuje
wyłącznie model i próbkowanie. Jeden proces ładuje model raz na całe zadanie;
po sukcesie, błędzie lub anulowaniu jest zakończony, a pliki pary usunięte.
Transport ma wersjonowany JSON i ograniczone tablice NumPy bez pickle.
Błędy procesu, wersji protokołu, EOF i OOM nie zastępują wcześniejszego aligned.

Przed obliczeniami sprawdzane są lokalne wagi, kod RoMa i DINOv3 przez SHA-256.
Nie ma pobierania, automatycznej zmiany urządzenia ani zmiany rozdzielczości
po błędzie. Otwarcie sesji i zmiana metody nie uruchamiają interpretera.
Środowisko, wersje i licencje: [przygotowanie](roma-environment.md).

Domyślne ustawienia to Turbo, 1000 punktów, seed 20261102. Szarość jest
normalizowana osobno min/max i powielana do RGB; model jawnie skaluje oba
wejścia. Znormalizowane punkty wracają do pikseli obu oryginałów, a skalowanie,
kanały i brak paddingu pozostają w diagnostyce. Po próbkowaniu modelu limit
`ceil(limit_punktów / 64)` na komórkę siatki 8 × 8 w każdym obrazie ogranicza
nadreprezentację jednego obszaru. Ziarno i wersja tego kroku są zapisywane.
Nie usuwa to wpływu zakłóceń na kontekstowe cechy DINOv3.

GUI pokazuje liczbę punktów, przestrzenne poparcie, słabe wyniki i odmowy.
Zapisane sesje, graf, korekty ręczne oraz MPP zachowują pochodzenie RoMa.
Dawne wersje sesji i metadanych pozostają odczytywalne. Wyeksportowane AVI
zawiera obraz aktywnego filmu, bez diagnostyki modelu.

## Rzeczywisty model i GUI automatyczne

Publiczne próby pary CPU/CUDA odtwarzają znane XY (−7, +5) px z błędem
poniżej 0,2 px. Próba trzyklatkowego filmu zachowuje oryginały i skumulowane
położenia; graf używa identycznego pomiaru pary, LS/Hubera i renderera.
Testy są jawnie włączane przez `STMVIEWER_TEST_ROMA=1`.

Dodatkowe **2 testy Qt offscreen z rzeczywistym modelem** wykonały
„Sprawdź model” i „Rejestruj” na CPU i CUDA, na `cpu.mpp`.
Dla drugiej klatki uzyskano CPU (1,99785; −1,00478), CUDA
(1,99890; −1,00321) px przy znanych (2; −1) px.
Anulowanie ładowania modelu oraz checkpoint o poprawnym rozmiarze,
lecz błędnym SHA-256 zachowały wcześniejszy opis i identyczne piksele aligned.
Zrzuty okien 1024 × 768 obejrzano; kontrolki są osiągalne przez przewijanie.
To automatyczne sprawdzenia GUI, nie odbiór manualny.

Artefakty: `/tmp/stmviewer-reg11-gui/`.

## Wzorce i porównanie modeli

[Skrypt](../../../tests/stmviewer/diagnostics/roma_patterns.py) porównuje na CPU
te same 9 par: RoMa Turbo, EfficientLoFTR ze wspólnym konsensusem v2
oraz historyczny Deep outdoor. Nie zmienia progów zależnie od filmu.

| Maksymalny błąd osi względem znanego XY | RoMa Turbo | EfficientLoFTR | Deep outdoor |
| --- | ---: | ---: | ---: |
| `cpu.mpp` | 0,009 px | 0,017 px | 0,299 px |
| Ruch subpikselowy | 0,022 px | 0,336 px | 0,056 px |
| Silny szum | 0,191 px | 0,025 px | 0,350 px |

Na wzorcu **stationary-artifact** RoMa zwróciło około (0; −0,20) zamiast
znanych (7; −5) px, mimo statusu `manual_review`. EfficientLoFTR v2 uzyskało
około (6,98; −5,00) z ostrzeżeniem, a Deep również podążyło za pasem.
RoMa zwróciło też niejednoznaczny wynik na teksturze okresowej.
Limit punktów komórki pomaga przy gęstym lokalnym skupisku, ale nie gwarantuje
poprawności, gdy artefakt wpływa na dopasowania w większej części obrazu.

RoMa na CPU: około 0,80–0,85 s/parę, szczyt RAM procesu około 2962 MiB.
Raport: `/tmp/stmviewer-reg11-patterns/report.json`; identyczne wejścia
z manifestem pozostają w `/tmp/reg10-patterns-v2/`.

Sprawdzono również wszystkie cztery presety na CUDA na `cpu.mpp`
i `stationary-artifact`: Turbo, Fast, Base i Precise ładowały się i odzyskały
znane XY pierwszego wzorca. **Żaden z nich nie naprawił dopasowania pasa**.
Szczyt alokacji Torch wyniósł odpowiednio około 1173, 1352, 1526 i 3013 MiB.
To nie całkowite użycie GPU ani próba na sprzęcie 8 GB.
Raport: `/tmp/stmviewer-reg11-presets.json`.

## Pełne filmy

[Skrypt prób](../../../tests/stmviewer/diagnostics/roma_trial.py) uruchomiono
z main `netcat` i osobnym procesem RoMa CUDA na RTX 5090. Turbo, 1000 punktów,
seed 20261102, graf z oknem 3; ta sama lista par co w poprzednich porównaniach.
MOVIE_4 po usunięciu źródłowych 1 i 2: 362 klatki 256 × 256;
MOVIE_8: 84 klatki 512 × 512. SHA-256 źródeł zapisano w raportach.

| Pomiar | MOVIE_4 | MOVIE_8 |
| --- | ---: | ---: |
| Sąsiednia seria, pełny wynik | tak | tak |
| Cały czas serii z ładowaniem i renderem | 15,62 s | 7,32 s |
| Pary grafu | 1080 | 246 |
| Czas grafu z ładowaniem i LS | 37,64 s | 11,93 s |
| Kompletne pozycje LS | tak | tak |
| Pary grafu o słabym poparciu | 197 | 77 |
| Odmowy par grafu | 0 | 1 |
| Czas solvera LS | 0,010 s | 0,003 s |
| Render zastosowanego LS | 0,71 s | 0,82 s |
| Próbkowany szczyt RAM drzewa procesu podczas grafu | 3626 MiB | 3208 MiB |
| Próbkowane użycie VRAM według sterownika | 1984 MiB | 1984 MiB |

W MOVIE_8 odmowa dotyczy pary 32–35: tylko 3 zgodne przesunięcia przy
wymaganych 4; pozostałe krawędzie nadal łączą cały graf.
**Huber osiągnął limit 200 iteracji w obu filmach** i nie dostarczył nowego
kompletnego wariantu. Nie stosowano niezakończonego wyniku. LS pozostaje
dostępny do obejrzenia i zastosowania.

Statystyki klatek serii dziedziczą niepewność wcześniejszych par, dlatego
nie są liczbą słabych pojedynczych pomiarów. Wysoka kompletność nie przesądza
o jakości pierwszych 150 klatek MOVIE_4 ani dalszej części filmu.

W obu próbach zapis/odczyt kandydata grafu zachował brak aktywnego aligned.
Zastosowany LS, ręczna korekta +1 px Y, sesja i mały MPP z metadanymi
przeszły ponowny odczyt z zachowaniem pikseli, XY i pochodzenia.
Utworzono AVI MJPG oraz FFV1. Testowa „manual correction” oznacza wywołanie
publicznej funkcji korekty przez skrypt, nie ręczne klikanie w GUI.
W procesie nadrzędnym nie zaimportowano Torch, RoMa ani DINOv3.

Gotowe lokalne sesje i filmy:

- `/tmp/stmviewer-reg11-movie4/` — `chain.stmsession`,
  `graph-candidate.stmsession`, `ls-corrected.stmsession`, małe MPP i oba AVI.
- `/tmp/stmviewer-reg11-movie8/` — ten sam zestaw.
- `report.json` w każdym katalogu zawiera czasy, zasoby, odmowy i konfigurację.

Próbkowanie zasobów co sekundę może pominąć krótkie maksimum; pomiar na
RTX 5090 nie zastępuje odbioru na karcie 8 GB. Nie wykonano próby Windows,
niezależnej oceny fizycznego dryfu ani ręcznego odtwarzania nowych AVI w VLC.

## Weryfikacja kodu

Przebiegi red→green obejmowały współrzędne, gęste błędne skupisko, granicę
procesu, protokół/EOF/OOM/anulowanie, sprzątanie, ścieżki względne oraz
trwałość konfiguracji i wyników. Szczegółowe wyniki końcowe i przeglądy
są zapisane w [raporcie przeglądu](reviews/REG-11.md).
