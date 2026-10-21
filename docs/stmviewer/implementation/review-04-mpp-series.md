# Przegląd ticketu 04 — MPP z czasami i pochodzeniem

Data: 2026-10-21. Baza zgodnie z zatwierdzonymi zasadami implementacji:
`8aa12416d6225d63d1378b535e140b2063b65bf6`.
Commit implementacji: `03f4917`.
Diff: `git diff 8aa12416d6225d63d1378b535e140b2063b65bf6...03f4917`.

Dwie osie sprawdzili równolegle niezależni agenci zgodnie ze skillem
`code-review`. Przegląd tylko do odczytu, bez ponawiania testów przez agentów.

## Standards

**0 naruszeń udokumentowanych zasad; 1 drobna sugestia projektowa.**

Zmiany pozostają w zakresie `stmviewer/`, `tests/stmviewer/` i `docs/stmviewer/`,
zgodnie z `AGENTS.md` i `stmviewer/AGENTS.md`. Adapter MPP pozostaje lokalny,
a potrzebne zmiany wspólnego czytnika opisano w `handoff.md`. Wydzielenie
`quantities.py` usuwa powielanie parsowania jednostek pomiędzy formatami.
Instrukcja GUI zawiera wzorce, generator i oczekiwane wyniki; odróżnia
sprawdzenia automatyczne od niewykonanego odbioru ręcznego, zgodnie z
`implementation/README.md`.

Sugestia **Duplicated Code** — heurystyka, nie naruszenie standardu:
`stmviewer/ui/main_window.py` i `stmviewer/ui/filmstrip.py` identycznie
formatują pochodzenie klatki:

```python
source = str(frame.source)
if frame.source_frame_index is not None:
    source += f"\nKlatka źródłowa MPP: {frame.source_frame_index + 1}"
```

Wspólny formatter w warstwie UI pozwoliłby utrzymywać zgodny opis panelu
i tooltipu w jednym miejscu. Przy obecnych trzech liniach jest to sugestia
niskiego priorytetu, bez wpływu na akceptację implementacji.

Decyzja po przeglądzie: pozostawiono te trzy linie w obu kontrolkach.
Wspólny formatter warto wydzielić, gdy opis pochodzenia stanie się bardziej
złożony. Obecny test GUI sprawdza zgodność numeru w panelu i tooltipie.
Nie ma usterek wymagających poprawki przed próbą użytkownika.

Źródła standardów: `AGENTS.md`, `stmviewer/AGENTS.md`,
`docs/PARALLEL_DEVELOPMENT.md`, indeks implementacji, słownik i pełny
katalog heurystyk Fowler ze skillu. Nie znaleziono odrębnych
CODING_STANDARDS/CONTRIBUTING. Końcowe wyniki i commit uzupełniono w przekazaniu.

## Spec

**0 usterek, 0 brakujących wymagań implementacji, 0 rozszerzeń zakresu.**

- „Jeden MPP zastępuje serię po pełnym sukcesie” — wybór kilku MPP lub
  mieszanki z STP/S94 jest odrzucany. Wynik trafia do GUI po odczycie wszystkich
  klatek i przygotowaniu miniatur. Błąd i anulowanie zachowują poprzednią serię.
- „Klatki zachowują kolejność z filmu, orientację, wartości, metadane i źródłowy
  numer” — dekodowanie `<f8` nie skaluje próbek; pojedynczy obrót odpowiada
  istniejącemu loaderowi NanoTrack. Metadane źródłowe pozostają dostępne,
  numer źródłowy jest odrębny od pozycji w serii.
- „Znane czasy są poprawnie interpretowane z jednostką, a częściowe braki nie
  usuwają pozostałych czasów” — każdy wpis jest interpretowany niezależnie.
  Nieznana jednostka i brak nie wpływają na pozostałe klatki; zapis źródłowy
  jest zachowany. FPS nie generuje czasu.
- „Nagłówek z ponad 1000 liniami i film o 1000 klatkach” — parser nie ogranicza
  liczby linii ani klatek; limit długości pojedynczej linii nie ogranicza tego
  scenariusza.
- Testy obejmują rzeczywiste dekodowanie, częściowe czasy, orientację, postęp,
  wybór klatki 1000, błędy oraz anulowanie po odczytanej klatce. Zachowano
  wcześniejsze ścieżki STP/S94.

Eksport, metadane towarzyszące, Play, gamma i rejestracja pozostają poza zmianą,
zgodnie z zakresem etapu. Ręczny odbiór użytkownika oraz Windows pozostają
jawnie niewykonane.

Źródła: [ticket 04](issues/04-mpp-series.md), [słownik](../GLOSSARY.md),
[decyzja 01](../issues/01-frame-series.md#answer),
[decyzja 04](../issues/04-mpp-export.md#answer),
[decyzja 06](../issues/06-acceptance.md#answer).

Łącznie: Standards — 1 drobna sugestia, bez naruszeń zasad; Spec — 0 ustaleń.
