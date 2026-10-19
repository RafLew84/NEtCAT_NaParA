# STM Domains — przekazanie kontraktu importu

Data: 2026-10-19.
Gałąź zadania: `domains/import-contract`, baza `61d010e`.
Docelowa gałąź aplikacji: `domains/start`.
Commit przypisania ticketu: `295ccad`; commit rozstrzygnięcia podany w końcowej
wiadomości sesji. Przygotowanie w `/tmp/netcat-stmdomains-import-contract`,
przeniesienie do worktree Domains przez scalenie commitów.

## Zakres i wynik

Rozstrzygnięto ticket `01`:
[Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](issues/01-import-and-geometry.md).
Status `resolved` wynika z dwóch rund odpowiedzi użytkownika oraz audytu kodu
i rzeczywistych danych. Pełny kontrakt jest w `Answer` ticketu; mapa zawiera
odnośnik do wyniku. Zaktualizowano słownik i README.

Uzgodniono MolTrack z jednym MPP, automatyczne/ręczne odnajdywanie źródła,
odtwarzanie słabej rejestracji z informacją o jakości, częściowy podgląd przy
uszkodzonych dodatkach oraz potwierdzane użycie zgodnego źródła o zmienionym mtime.
Kontrakt ustala też mapę klatek, oba układy obrazu, padding, dostępność oznaczeń
i kryteria odbioru. Nie zmieniono kodu aplikacji ani wspólnych modułów.

## Wykonane sprawdzenia

- [Audyt importu i geometrii](import-geometry-audit.md): pełny odczyt MPP,
  odtworzenie zapisanych translacji, kontrola wszystkich bboxów i dekodowanie
  masek pojedynczo. Ogląd statycznych nakładek klatek 0, 39 i 267 w obu widokach.
- Istniejące testy `tests/moltrack/test_registered_coordinates.py` oraz
  `tests/nanotrack/test_mpp_loader.py` w conda netcat: **6 passed**.
- Kontrola lokalnych odnośników, statusów i zależności mapy oraz `git diff --check`.

Nie wykonano odbioru nowego importera ani GUI STM Domains: funkcje te nie są
jeszcze wdrożone. Nie uruchamiano detekcji, ponownej rejestracji ani analizy domen.
Wersje wejścia 2/3 i pozostałe kodowania masek mają dostać fixture'y odbioru
przy implementacji; realny przebadany zapis ma schema 1. Ogląd nakładek nie
jest naukową walidacją jakości detekcji.

## Następny krok

Odblokowane jest
[Jak przeglądać obrazy i oznaczenia w szkielecie?](issues/07-browsing-and-comparison.md).
Przy szkicu trzeba uwzględnić wyniki importu i dostępność poszczególnych warstw.
Następnie pozostaje przekazanie szkieletu do implementacji. Druga mapa zaczyna
się dopiero po implementacji i odbiorze szkieletu, zgodnie z podziałem `61d010e`.

## Ograniczenia i integracja

Istniejący pełny loader sesji MolTrack nie realizuje tego kontraktu. Dla realnego
MPP data różni się o 7200 s, mimo zgodności hasha z poprzednim audytem; loader
odrzuca źródło. Ładuje też analizy poza zakresem i wszystkie maski — same dwa
zestawy rastrów bool przykładowej serii to około 4,70 GB. Importer STM Domains
powinien mieć lokalny adapter, korzystający z czytnika MPP i sprawdzonej geometrii,
oraz odczytywać maski w miarę potrzeby. Wydzielenie wspólnego lekkiego parsera,
jeśli okaże się potrzebne, należy do sesji integracyjnej.

Do sesji integracyjnej przekazujemy potwierdzone obserwacje o obecnym MolTrack:

- `restore_moltrack_image_series_from_session` wybiera obrazy po źródłowych ID,
  ale nie wybiera odpowiadających im `metadata.frame_times_s`.
- Parser cicho nadpisuje duplikaty wyników rejestracji i przyjmuje powtórzone
  ID detekcji. Dekoder nie wiąże shape maski z geometrią obrazu.
- Dotychczasowe wymaganie zgodności mtime nie obsługuje potwierdzonego przez
  użytkownika przypadku przeniesienia pliku. Zmiana tego zachowania w MolTrack
  wymaga oddzielnej decyzji integracyjnej; nie została tutaj wykonana.

Lokalny adapter może kontynuować pracę bez zmiany współdzielonego kodu.
Zachowujemy wcześniejsze zgłoszenie o podwójnym odwracaniu serii wielu STP/S94
w NanoTrack (przekazanie w `61d010e`); ten wariant jest poza zakresem importera
STM Domains z jednym MPP. Nie modyfikowano roboczych zmian STM Viewer.
