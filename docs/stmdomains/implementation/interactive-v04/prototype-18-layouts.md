# Propozycje UI freud — SD-V4-18

2026-11-04, skill `prototype`, wariant UI. Pytanie: **gdzie ustawiać
porównanie lokalnych otoczeń i jak oglądać klasy oraz domeny obok
dotychczasowego wyniku?** Trzy układy osadzono w kontekście przeglądarki
STM, z obrazem, oznaczeniami, suwakiem klatek i istniejącymi metodami.

**Użytkownik wybrał Panel A i zlecił implementację 2026-11-04.**
[Właściwe UI Qt i wyniki obliczeń](acceptance-18.md). Poniższy prototyp
pozostaje historyczną demonstracją, jego kod i symulacje nie zostały scalone.

## Uruchomienie

Adres: **http://127.0.0.1:8878/?variant=A**; również `?variant=B` i
`?variant=C` na tej samej stronie. Dolny pasek oraz klawisze ←/→ przełączają
układ. Strzałki w polach edycji zachowują własne działanie. Wybór jest
zapisany w URL, pozostały stan żyje wyłącznie w pamięci strony.

Z bieżącej gałęzi aplikacji, w środowisku **netcat**:

```bash
python .scratch/stmdomains-freud-ui/serve.py
```

Bez serwera można otworzyć `.scratch/stmdomains-freud-ui/prototype.html`.
`--build-only` odtwarza samowystarczalny HTML, `--no-browser` uruchamia
serwer bez otwierania przeglądarki. Nie ma nowych zależności.

Źródło pierwotne: gałąź **`prototype/stmdomains-freud-ui`**, commit
**`d962b7d`**, baza `97a60bd`, katalog `stmdomains/ui/prototype_freud/`.
Na tej gałęzi: `python stmdomains/ui/prototype_freud/serve.py`.
Lokalna kopia w `.scratch/stmdomains-freud-ui/` pozwala uruchamiać podgląd
po powrocie do `domains/interactive-v04-ui`. Nie scalać kodu prototypu
jako implementacji; po wyborze napisać właściwe UI Qt i obliczenia.

## Warianty

| Wariant | Sposób pracy | Co ocenić |
| --- | --- | --- |
| A — wspólne okno Analiza | W istniejącym wyborze metody dodane freud; parametry w oknie. Po Analizuj jeden obraz i przełącznik Bazowa / Geometria / freud. | Spójność z 17 i miejsce na obraz; do kolejnej zmiany parametrów trzeba otworzyć okno. |
| B — porównanie obok siebie | Po lewej Bazowa albo Geometria, po prawej freud. Parametry pod obrazami, wspólny zoom i wybór molekuły. | Bezpośrednie porównanie; w małym oknie oba obrazy są wyraźnie mniejsze. |
| C — stały panel otoczeń | Jeden obraz i przełącznik wyników; ustawienia oraz Analizuj stale po prawej. | Szybkie strojenie; panel zajmuje szerokość, a w małym oknie ustawienia się przewijają. |

W każdym wariancie: tolerancja podobieństwa, liczba sąsiadów, maksymalny
zasięg i sposób traktowania obrotu. **Bez pola K.** Przełącznik Klasy/Domeny
pokazuje różnicę między podobnymi otoczeniami a spójnym obszarem. Kliknięcie
molekuły otwiera opis przypisania oraz podgląd jej sąsiadów.

## Co jest rzeczywiste, a co symulowane

- Obrazy i centra: rzeczywiste TTMAPP258–260. Zapis Bazowej na klatce 259
  pochodzi z `.scratch/stmdomains-ui-13/real.stmdomains` (105/312, 5 domen),
  a Geometrii z `.scratch/stmdomains-ui-17/geometry.stmdomains` (32/312,
  1 domena). Na 258/260 brak tych zapisów jest jawny.
- **Wszystkie przypisania freud, klasy, obrysy, odmowy i postęp są
  demonstracyjne.** Nie uruchamiano EnvironmentCluster. Obrysy fixture
  nie są docelową rasteryzacją ani wynikiem wykrywania granic.
- Zasięg w px, względna skala tolerancji, wartości i zakresy pól to
  propozycja UI. Nie ustalają poprawnej konfiguracji metody 18; jej
  jednostki, normalizację i reguły sąsiedztwa trzeba zweryfikować w próbie.
- Podgląd sąsiadów wybiera najbliższe rzeczywiste centra w zasięgu szkicu;
  nie przedstawia dopasowania ani wyniku freud. Różnica orientacji nadal
  ma znaczenie przy tworzeniu domen, nawet przy dopasowaniu obrotu klas.

Scenariusze UI: zwykły wynik, zero domen z powodu niepełnych otoczeń oraz
nierozdzielona granica przesunięcia. To przykłady komunikatów, nie ocena
widocznej klatki. Edycja parametrów zachowuje wcześniejszy wynik; Analizuj
tworzy nowy, anulowanie go nie nadpisuje. Klatki mają osobne wyniki.
„Stan prototypu” ujawnia szkic, użyte parametry, wyniki, zaznaczenie, widok,
pochodzenie i oczekujące zadanie; stan trafia też do konsoli po zmianie wariantu.

## Wykonane sprawdzenia

W **netcat**, rzeczywisty QtWebEngine na X11: A/B/C przy 1440×1000 oraz
1024×768; obejrzano zrzuty, brak przewijania całej strony w tych rozmiarach.
Poprawiono wysokość panelu parametrów B, aby pozostawić więcej miejsca
na obrazy. Panel C ma przewijaną treść i stale dostępny przycisk Analizuj.

Przebieg interakcji sprawdził szkic bez zmiany wyniku, Analizuj, anulowanie,
zachowanie zoomu, Klasy/Domeny, raw/aligned, istniejącą Geometrię,
oddzielne stany klatek, brak spóźnionego wyniku po zmianie klatki,
zero domen, komunikat granicy fazy, klawiaturę i pełny stan.
Rzeczywiste kliknięcie molekuły oraz przeciąganie suwaka klatek również
zadziałały. Końcowy podgląd: **brak błędów JavaScript**.

To oglądanie i automatyzowany przebieg interakcji, nie odbiór użytkownika
ani test skuteczności metody. Nie pisano testów jednorazowego prototypu
i nie ponawiano regresji aplikacji. Maksymalny plik kodu ma **241 linii**;
sprawdzono odnośniki dokumentacji i `git diff --check`.

Kod prototypu nie jest częścią `python -m stmdomains.main`. Dane wejściowe
są tylko odczytywane, stan użytkownika nie jest zapisywany ani wysyłany.
Wygenerowany HTML, raport podglądu i zrzuty pozostają lokalne w
`.scratch/stmdomains-freud-ui/`. Brak zmian wspólnych i potrzeb integracyjnych.
