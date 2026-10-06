# Walidacja lokalnych planów Wayfinder

Z katalogu repozytorium:

```powershell
python scripts/check_wayfinder_plan.py .scratch/nanotrack-registration-export
```

Argument to katalog zawierający `map.md` i `issues/NN-slug.md`. Może być względny
albo absolutny. Skrypt wymaga Pythona 3.10 lub nowszego, bez dodatkowych pakietów.
Można używać interpretera ze środowiska `netcat`.

Poprawny plan daje komunikat `OK: <katalog>: <liczba> tickets` i kod 0.
Pierwszy błąd daje pojedynczy komunikat `ERROR: <plik>: <przyczyna>` na stderr
i kod 1. Błędne argumenty wywołania dają kod 2. Walidator niczego nie zapisuje
ani nie poprawia automatycznie.

## Sprawdzany format

- Numery plików są dodatnie i unikalne: `01`, `02`, ..., `100`. Wymagany jest
  niepusty slug; `1-zadanie.md`, `00-zadanie.md` i `001-zadanie.md` są błędne.
  Luki po usunięciu zadania są dozwolone.
- Mapa ma dokładnie jeden `Status: open` albo `Status: resolved`.
  Zadanie ma dokładnie jeden `Status: open`, `claimed` albo `resolved`.
  Metadane znajdują się przed pierwszą sekcją `##`; historyczne wzmianki
  w komentarzach nie zmieniają statusu.
- Każde zadanie ma `Blocked by: none` albo listę numerów, np. `Blocked by: 01, 03`.
  Numery muszą istnieć, nie mogą się powtarzać ani tworzyć cykli, również
  zależności zadania od samego siebie. Rozstrzygnięte zadanie nie może mieć
  nierozstrzygniętych zależności.
- Każde zadanie `resolved` ma dokładnie jedną sekcję `## Answer` z treścią.
  Podsekcje należą do odpowiedzi; sama sekcja `## Comments`, puste nagłówki
  lub komentarze HTML nie zastępują treści odpowiedzi.
- Mapa ma po jednej sekcji `## Decisions so far` i `## Out of scope`.
  Wszystkie rozstrzygnięte zadania muszą być podlinkowane w jednej z nich.
  Odrzucone poza zakres zadanie może być tylko w `Out of scope`.
  Odnośniki do `open`/`claimed` w tych indeksach i powtórzenia tego samego
  zadania w jednej sekcji są błędami. Powtórne odwołanie do decyzji przy
  opisywaniu granic zakresu w drugiej sekcji jest dozwolone.
- Mapa `resolved` nie może mieć żadnych zadań `open` ani `claimed`.

Nie są to reguły planów implementacyjnych z `Status: pending/completed`.
Takie plany mają osobny format i odrębne kontrole.

## Odnośniki i granice kontroli

Sprawdzane są odnośniki w mapie, wszystkich zadaniach, istniejącym `spec.md`
oraz dokumentach Markdown osiągalnych przez ich lokalne odnośniki wewnątrz
katalogu planu. Walidator nie skanuje niepowiązanych archiwów ani kopii repo
w `worktrees/`. Link poza katalog planu musi istnieć, ale treść zewnętrznego
dokumentu nie jest dalej przeglądana.

Obsługiwane są zwykłe odnośniki Markdown i obrazki, odnośniki referencyjne,
lokalne URI `file:`, katalogi, kodowanie `%20`, ścieżki w `<...>`, fragmenty
`#...`, parametry `?...` oraz odnośniki edytora `plik.py:123[:kolumna]`.
Na Windows działają też bezwzględne ścieżki dyskowe i zapis `/C:/...`.
Ścieżka dyskowa Windows na innym systemie daje jawny błąd, zamiast pozornego
potwierdzenia istnienia pliku.

Sprawdzane jest istnienie celu, nie istnienie nagłówka `#...`, numeru linii
ani zgodność zawartości pliku. Linki sieciowe nie są pobierane. Surowy HTML,
same ścieżki bez odnośnika, kod w backtickach i blokach fenced code oraz
komentarze HTML nie są traktowane jako odnośniki do sprawdzenia.
Walidator sprawdza strukturę planu, nie sens decyzji, faktyczną akceptację
użytkownika ani wykonanie opisanych prac.

## Testy i CI

```powershell
python -m unittest discover -s tests/wayfinder -p "test_*.py" -v
```

`tests/wayfinder/fixtures/` zawiera małe plany: zamknięty, w toku i celowo
błędny z cyklem. Testy używają ich bez prywatnych plików. Dodatkowe uszkodzenia
tworzą w katalogach tymczasowych, aby sprawdzać komunikaty i kody zakończenia.

`.github/workflows/wayfinder-plan.yml` wykonuje tę samą komendę po zmianie
walidatora, jego testów, przykładów, dokumentacji lub workflow. Używa zwykłego
Pythona na runnerze GitHub z Linuxem; nie wymaga Condy ani bibliotek GUI.
Python jest przygotowywany przez [oficjalny setup-python](https://github.com/actions/setup-python).

Rzeczywisty plan NanoTrack pozostaje ignorowany w `.scratch` i jest sprawdzany
lokalnie. Workflow nie zakłada, że ten plan istnieje w checkoutcie CI.
