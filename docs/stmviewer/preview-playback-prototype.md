# Podgląd i odtwarzanie — źródło decyzji

Data: 2026-10-19.
Dotyczy: [Podgląd, gamma i odtwarzanie serii](issues/02-preview-playback.md).

## Artefakt

Prototyp jest zapisany na osobnej lokalnej gałęzi
`prototype/stmviewer-preview-playback`, commit `bf8e849`:

- `stmviewer/ui/preview_playback_prototype.html` — samodzielny plik z obrazem,
  trzema układami i działającymi kontrolkami;
- `stmviewer/ui/preview_playback_prototype.md` — pytanie, warianty, scenariusze,
  proponowane zachowania i ograniczenia.

Gałąź jest źródłem prototypu i nie jest przeznaczona do scalania z kodem
produkcyjnym. Na `viewer/start` pozostaje dokumentacja procesu decyzyjnego.
Wersja HTML służy ocenie przyszłego okna PyQt6; nie zmienia technologii aplikacji.

Lokalną kopię można odtworzyć i otworzyć z katalogu głównego repozytorium:

```bash
mkdir -p .scratch/preview-playback-prototype
git show bf8e849:stmviewer/ui/preview_playback_prototype.html > .scratch/preview-playback-prototype/preview_playback_prototype.html
git show bf8e849:stmviewer/ui/preview_playback_prototype.md > .scratch/preview-playback-prototype/preview_playback_prototype.md
xdg-open .scratch/preview-playback-prototype/preview_playback_prototype.html
```

Plik nie wymaga serwera, instalacji pakietów ani dostępu do sieci. Można otworzyć
go również przez dwuklik. Parametry `?variant=A`, `?variant=B`, `?variant=C`
wybierają układ; dolny pasek przełącza warianty bez resetowania stanu.
Kopia `.scratch/` i zrzuty podglądu pozostają lokalne, poza Git.

## Co porównać

| Wariant | Układ |
| --- | --- |
| A — lista klatek | Lista po lewej, główny obraz pośrodku, ustawienia po prawej, odtwarzanie pod obrazem. |
| B — pasek miniatur | Obraz i ustawienia powyżej poziomego paska miniatur. |
| C — siatka | Miniatury po lewej obok aktywnego obrazu; odtwarzanie nad nimi, ustawienia poniżej. |

Każdy wariant ma jeden główny podgląd i przełącznik original/aligned.
Miniatury pokazują original z gamma 1,0. Oprócz Play/Pause działają tempo,
pętla, suwak i numer klatki, gamma, zoom pod kursorem, przesuwanie, dopasowanie,
odwracanie i usuwanie. Panel „Porównaj zachowania” udostępnia alternatywy
zachowania zoomu, gamma i ręcznej nawigacji podczas Play.

Użytkownik obejrzał prototyp i 2026-10-19 wybrał **wariant B**, potwierdzając
proponowane zasady odtwarzania i podglądu. Wiążąca odpowiedź znajduje się w
[tickecie](issues/02-preview-playback.md#answer). Prototyp zachowuje również
odrzucone warianty i opcje porównawcze jako zapis eksperymentu; nie wszystkie
jego kontrolki są wymaganiami dla aplikacji produkcyjnej.

## Dane i wykonane sprawdzenia

Źródłem jest fixture STP `movie2/34855.STP`. Seria demonstracyjna składa się
z 12 nakładających się wycinków 160 × 160 px, o kontrolowanym przesunięciu.
Aligned ma obszar 182 × 171 px. To symulacja dryfu z jednego obrazu,
nie wynik działania rejestracji ani oryginalny film. Nie przypisano skali
fizycznej ani czasów pomiaru. Obraz ma wspólną normalizację do uint8 wyłącznie
na potrzeby demonstracji; nie jest eksportem danych pomiarowych.

Prototyp uruchomiono w Qt WebEngine. Sprawdzono renderowanie A/B/C i aligned
oraz obejrzano zrzuty w rozdzielczości 1400 × 1000 i zwężonego okna 980 × 850.
Sprawdzono interakcje: Play na ostatniej klatce, ręczne zatrzymanie,
odwrócenie z zachowaniem pochodzenia, usuwanie do pustej serii, ponowne
wczytanie demo oraz Stop na końcu. Nie odnotowano błędów JavaScript.
Przeglądarka systemowa została uruchomiona z gotowym plikiem do oceny użytkownika.

Nie dodawano testów automatycznych prototypu. Nie sprawdzano produkcyjnego
GUI PyQt6, wydajności dużych serii, importu, eksportu ani prawdziwej rejestracji.
Zachowanie przygotowanego aligned po usunięciu lub odwróceniu nie rozstrzyga
[życia wyniku rejestracji](issues/03-registration.md).
