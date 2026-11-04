# Propozycje UI metod domen — SD-V4-17

2026-11-04, skill `prototype`, wariant UI. Pytanie: **gdzie wybierać metodę,
ustawiać tolerancje i porównywać konkretne molekuły/domeny?**
Przygotowano trzy strukturalnie różne układy w kontekście przeglądarki STM,
z nawigacją klatek, molekułami, obszarami i istniejącą kartą pomiaru 16.
[Ticket 17](17-segment-geometric-tolerances.md) nadal `ready-for-agent`.
**Wyboru użytkownika jeszcze nie ma; metoda 17 nie została wdrożona.**

## Otwieranie

Lokalny serwer: **http://127.0.0.1:8877/?variant=A**.
Warianty `?variant=B` i `?variant=C` na tej samej stronie. Dolny pasek
oraz klawisze ←/→ przełączają propozycje; strzałki w polach edycji nie
przełączają układu. URL zachowuje wybór po odświeżeniu.

Z bieżącej gałęzi implementacji, w środowisku `netcat`:

```bash
python .scratch/stmdomains-domain-method-ui/serve.py
```

Samowystarczalny HTML bez serwera:
`.scratch/stmdomains-domain-method-ui/prototype.html`.
`--build-only` odtwarza HTML, `--no-browser` pomija uruchamianie przeglądarki.
Nie ma nowych pakietów. Źródło pierwotne:

- gałąź `prototype/stmdomains-domain-method-ui`, commit **`621ce71`**;
- katalog `stmdomains/ui/prototype_domain_method/`, baza `e5ba84b`;
- na tej gałęzi komenda `python stmdomains/ui/prototype_domain_method/serve.py`;
- lokalna kopia źródła w `.scratch/stmdomains-domain-method-ui/` pozwala
  oglądać warianty po powrocie do `domains/interactive-v04-ui`.

Kod prototypu nie jest częścią `python -m stmdomains.main`. Nie należy
scalać go jako implementacji ticketu; po wyborze trzeba napisać właściwe
UI Qt z rzeczywistymi obliczeniami.

## Propozycje

| Wariant | Układ i przebieg | Co ocenić |
| --- | --- | --- |
| A — wspólne okno Analiza | W znanym oknie wybór Bazowa/Geometria i parametry. Obliczenie zamyka okno; nad jednym obrazem przełącznik wyników. | Jedno miejsce konfiguracji, więcej miejsca na obraz po obliczeniu; zmiana parametrów wymaga ponownego otwarcia okna. |
| B — porównanie obok siebie | Bazowa po lewej, Geometria po prawej. Ustawienia pod obrazami, wspólny zoom, przesunięcie i wybrana molekuła. | Bezpośrednia ocena obu wyników; w małym oknie obrazy wyraźnie mniejsze. |
| C — stały panel ustawień | Jeden obraz z przełącznikiem wyniku, formularz po prawej. Oblicz stale widoczne; pola przewijane w małym oknie. | Szybkie kolejne próby; formularz stale zajmuje część obszaru roboczego. |

**Rekomendacja autora: A** — zgodność z wcześniejszym wyborem wspólnego
okna Analiza, jeden punkt ustawień i pełniejszy obraz po obliczeniu.
B jest najbardziej bezpośrednim widokiem porównawczym na dużym ekranie;
C ułatwia częste strojenie. Rekomendacja nie oznacza wyboru przez użytkownika.
Litery dotyczą układu **17**. Wybrana wcześniej **karta C z 16 pozostaje
w każdym wariancie**, pod przyciskiem „Pomiary · 16”.

## Zakres demonstracji

Rzeczywiste: obrazy i centra TTMAPP 258–260, zapisany wynik bazowy 259
z własnego projektu 13 (105/312, pięć domen) oraz pomiary liczone przez 16.
Klatki 258/260 mają jawny brak zapisanego wyniku bazowego. Źródłem bazowego
podglądu jest `.scratch/stmdomains-ui-13/real.stmdomains`, a przy jego braku
surowy MolTrack z `data/TTMAPP/` bez udawania brakujących wyników.
Skala pomiaru 16 pochodzi z nagłówka, bez walidacji metrologicznej.

**Wszystkie nowe przypisania „Geometria”, powody decyzji oraz postęp są
symulacją UI.** Reguły fixture nie realizują algorytmu 17. Parametry
modyfikują szkic; dopiero Oblicz aktualizuje przykładowy wynik, pokazując
użyte wartości. Anulowanie zachowuje poprzedni. Zero domen i brak wyniku
mają różne stany. Kolor D1 obu metod nie oznacza tego samego obszaru.

Scenariusze „brak wiarygodnych pomiarów” i „nierozdzielona granica
przesunięcia” są przykładami komunikatów, nie oceną widocznej klatki.
„Stan prototypu” ujawnia pełny istotny stan: szkic, użyte ustawienia,
wyniki osobnych klatek, metodę, zoom, zaznaczenie i pochodzenie danych.
Przełączenie wariantu wypisuje stan również w konsoli przeglądarki.

Brak zapisu projektu, trwałych ustawień, treningu i zmian danych wejściowych.
Brak wysyłania pomiarów; lokalny serwer zwraca wyłącznie stronę prototypu.
Wygenerowany HTML i zrzuty zawierają dane lokalne i pozostają poza Git.

## Wykonane oglądanie i sprawdzenia

W `netcat`, QtWebEngine na X11: A/B/C przy 1440×1000 i 1024×768.
Zrzuty obejrzano; brak przewijania całej strony w poziomie/pionie w tych
rozmiarach. Sprawdzono formularz przed/po Oblicz, anulowanie, osobne stany
klatek, wynik zerowy, komunikat nierozdzielonej granicy, wybór molekuły,
powiększenie i zachowanie zoomu, raw/aligned, kartę 16, pasek wariantów,
klawiaturę oraz ujawnienie stanu. Poprawiono obsługę zdarzenia klawiatury
na dokumencie i dostępność przycisku Oblicz w małym wariancie C.
Końcowy podgląd: brak błędów JavaScript.

Nie pisano testów jednorazowego prototypu ani nie ponawiano testów
produkcyjnej aplikacji. To oglądanie i automatyzowany przebieg interakcji
w przeglądarce, nie odbiór metody 17. Przesuwanie obrazu jest przygotowane
w UI; szczegółowy odbiór jego ergonomii należy do wyboru wariantu.
Największy plik kodu: CSS 814 linii; wszystkie pliki poniżej 1000/1500.
Sprawdzono odnośniki dokumentacji oraz `git diff --check`.

Lokalne artefakty `.scratch/stmdomains-domain-method-ui/`: `prototype.html`,
`preview.py`, `preview-report.json`, `preview.log`, `layout-A/B/C-1440.png`,
`layout-A/B/C-1024.png`, `applied-A.png`, `measurement-card.png`,
`phase-failure.png`. Brak zmian wspólnych i potrzeb integracyjnych.
