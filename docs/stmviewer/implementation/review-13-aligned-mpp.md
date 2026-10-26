# Przegląd ticketu 13 — aligned MPP

Data: 2026-10-26. Baza `6ab0837abb5b4e6ba356a1ff6121779302e3585a`.
Pierwszy diff: `git diff 6ab0837...ec21f6a`.
Commity: `ec21f6a` (implementacja), `35858f1` (poprawki).
Ponowny przegląd: `git diff ec21f6a..35858f1`.
Dwie osie wykonali równolegle niezależni agenci skillu `code-review`.
Końcowy raport/status dopisano po sprawdzeniu poprawek.

## Standards

Brak naruszeń udokumentowanych standardów. Zmiany pozostają w zakresie
Viewera, rozdzielają historię od bieżącego wyniku rejestracji i zawierają
odtwarzalną instrukcję ręcznej próby. Kod i testy spełniają limit plików.

Jedna uwaga heurystyczna, nie błąd blokujący: **możliwy Duplicated Code**.
`alignment_metadata.py` powielał walidację pochodzenia z `mpp_metadata.py`:
`{'source', 'source_frame_index'}`, kontrolę pustego tekstu/NUL oraz
`type(index) is not int or index < 0`. Według kontraktu obie struktury mają
identyczne reguły. Zalecenie: wspólny dekoder zwracający `FrameProvenance`.

Ponowny przegląd `35858f1`: uwaga zamknięta. Oba miejsca używają
`source_provenance`, zachowując reguły walidacji. Zmiana porównania skali
jest mała i spójna; test sprawdza publiczny zapis i odczyt.

Źródła: AGENTS.md, stmviewer/AGENTS.md, docs/PARALLEL_DEVELOPMENT.md,
indeks implementacji, słownik, kontrakt metadanych i heurystyki Fowlera
ze skillu. Nie znaleziono osobnych CODING_STANDARDS/CONTRIBUTING.

**Standards: początkowo 0 naruszeń i 1 drobna heurystyka; 0 otwartych uwag.**

## Spec

Nie stwierdzono brakujących wymagań ani rozszerzenia zakresu.
Odbiór ręczny i Windows są jawnie oczekujące.

Jedno ustalenie **P2**: kompletny wynik własnej rejestracji mógł nie dać
się zapisać przy minimalnie różniących się skalach. Przykład:
`size_x_nm = [1, 1.0000000009, 1.0000000018]`, `size_y_nm = 1`.
Rejestracja kończyła się sukcesem, ale eksport odrzucał skalę źródła.

Przyczyna: `_common_pixel_size` porównywał sąsiednie wartości, przesuwając
punkt odniesienia; walidator eksportu porównywał wszystkie klatki ze skalą
ostatniej. Różnica mogła narosnąć ponad tolerancję.
Naruszony zapis [specyfikacji MPP](../issues/04-mpp-export.md#answer):
„Różne skale, kanały lub jednostki **nie blokują zapisu**”.

Poprawka `35858f1`: porównanie do jednej stałej skali pierwszej klatki,
przy braku zgodności użycie pikseli i zachowanie indywidualnych parametrów.
Test publicznego `register_series → save_aligned_mpp → open_frame_series`
odtworzył błąd przed poprawką i przeszedł po niej. Recenzent ponownie
sprawdził kod i niezależnie uruchomił regresję: **1 passed**.

**Spec: początkowo 1 ustalenie P2; 0 otwartych uwag.**

Wyniki automatyki i granice odbioru: [ticket 13](issues/13-aligned-mpp.md)
i [handoff](../handoff.md). Standards: 0 otwartych; Spec: 0 otwartych.
