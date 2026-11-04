# Prototyp układów geometrii — SD-V4-16

Data: **2026-11-04**. Pytanie użytkownika: jak pokazywać informacje
o geometrii przy oglądaniu kolejnych obrazów? Wykorzystano skill `prototype`,
gałąź UI. [Ticket 16](16-inspect-local-geometry.md) został później wykonany;
[raport implementacji](acceptance-16.md).
**Użytkownik wybrał wariant C 2026-11-04 i zlecił implementację ticketu 16.**
Prototyp pozostaje źródłem decyzji; jego demonstracyjne pomiary nie przechodzą do aplikacji.

## Trzy propozycje

| Wariant | Układ | Co sprawdzić |
| --- | --- | --- |
| A — panel boczny | Obraz po lewej, stały panel wybranej molekuły/domeny po prawej. | Czy liczby są czytelne, a obraz dostatecznie duży przy kolejnych kliknięciach? |
| B — tabela pod obrazem | Skan nad tabelą wielu molekuł, wybór wiersza i filtry. | Czy porównywanie pomiarów rekompensuje mniejszą wysokość obrazu? |
| C — karta na obrazie | Cała szerokość dla obrazu, karta pomiaru w narożniku, przenoszenie i zwijanie. | Czy możliwość ukrycia karty jest wygodniejsza niż stały panel i czy karta zasłania istotne miejsca? |

Wspólne: rzeczywiste obrazy i centra klatek 258–260, zapisane domeny 259,
powiększenie, raw/aligned, wybór punktu, miniatury/suwak, warstwy, scenariusze
jednego/dwóch kierunków i nierozstrzygnięcia oraz symulacja postępu/anulowania.
Nakładka kierunków domyślnie obejmuje wybrane sąsiedztwo; można wybrać całą
klatkę. Panel domeny w A/C ilustruje podsumowanie wybranej grupy.

**Wszystkie kąty, rozstawy, zgodności, wsparcie i stabilność geometrii są
demonstracyjne.** Nie stanowią pomiaru TTMAPP. Obraz, centra i kolory domen
są rzeczywiste; wynik 259 pochodzi z lokalnego projektu zapisanego w 13
(105/312, pięć domen). Klatki 258 i 260 mają jawny brak analizy domen.
Prototyp nie zapisuje projektu, nie przelicza modelu i nie wysyła danych.

## Otwieranie i porównanie

Z bieżącego worktree, w środowisku `netcat`:

```bash
python .scratch/stmdomains-geometry-layouts/serve.py
```

Przeglądarka otworzy `http://127.0.0.1:8876/?variant=A`.
Warianty `?variant=B` i `?variant=C` są na tej samej stronie. Przełącznik
na dole oraz klawisze ←/→ zmieniają układ bez utraty wybranego punktu.
Strzałki w polach formularza zachowują zwykłe działanie. „Stan” pokazuje
pełny istotny stan demonstracji. Odświeżenie zachowuje wariant z URL,
pozostały stan wraca do wartości początkowych.

Bez serwera można otworzyć samowystarczalny plik
`.scratch/stmdomains-geometry-layouts/prototype.html` w przeglądarce.
Nie potrzebuje połączenia z Internetem. Opcje launchera: `--no-browser`,
`--port 8877`, `--build-only` (odtworzenie HTML z lokalnych danych).

## Źródło i odtworzenie

Źródło pierwotne: commit **`2a31997`** na gałęzi
**`prototype/stmdomains-geometry-layouts`**, katalog
`stmdomains/ui/prototype_geometry/`. Prototyp powstał z `41cc9e3`.
Kod nie jest częścią gałęzi `domains/interactive-v04-ui` ani punktu startu
aplikacji. Lokalne kopie launchera, HTML i zrzuty są w `.scratch/`.

Jeżeli lokalna kopia zniknie, można ją odtworzyć bez zmiany gałęzi:

```bash
mkdir -p .scratch/stmdomains-geometry-layouts
git archive 2a31997 stmdomains/ui/prototype_geometry | tar -x --strip-components=3 -C .scratch/stmdomains-geometry-layouts
python .scratch/stmdomains-geometry-layouts/serve.py
```

Generator czyta `.scratch/stmdomains-ui-13/real.stmdomains`, jeśli istnieje.
W przeciwnym razie używa MPP/JSON z `data/TTMAPP` i pokazuje brak obliczonych
domen. Nie wymaga paczki v0.4 ani nowych zależności. Duże dane i wygenerowany
HTML pozostają lokalne. Aplikacja jest desktopowa; prototyp HTML odtwarza
kontekst jej obrazu, nawigacji i warstw, bez dodawania routingu do aplikacji Qt.

## Wykonane sprawdzenie i wniosek

Wykonano natywny podgląd X11 przez istniejący QtWebEngine w `netcat`:
wszystkie warianty przy 1440×1000 i 1024×768, bez poziomego przepełnienia.
Obejrzano zrzuty, przeprowadzono wybór punktu/wiersza, zmianę klatki,
raw/aligned i zoom, scenariusz nierozstrzygnięcia (zero rysowanych kierunków),
zwinięcie/przeniesienie karty, anulowanie symulacji, przełącznik klawiatury
i podgląd stanu. Końcowy przebieg: brak błędów JavaScript.
Poprawiono uruchomienie narzędzia podglądu QtWebEngine, sposób symulowania
kliknięć SVG i obsługę syntetycznego zdarzenia klawiatury.

Artefakty: `preview-report.json`, `preview.log`, `layout-{A,B,C}-{1440,1024}.png`
w `.scratch/stmdomains-geometry-layouts/`. Nie pisano testów prototypu i nie
ponawiano testów produkcyjnej aplikacji. Źródła prototypu: sześć plików,
największy plik kodu ma 199 linii, bez wyjątku od limitu 1000/1500.

**Historyczna rekomendacja agenta: A; decyzja użytkownika: C.** W małym oknie B zmniejsza wysokość
pola obrazu do 181 px przy 399 px w A/C; C może zasłaniać część skanu.
To obserwacja układu, nie ocena metody. Wybrany C zapisano w tickecie 16; należy napisać
docelowe UI Qt zgodnie z wymaganiami produkcyjnymi; nie przenosić kodu
demonstracji do aplikacji.
