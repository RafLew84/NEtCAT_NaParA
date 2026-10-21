# Przegląd ticketu 05 — zoom, gamma i brakujące próbki

Data: 2026-10-21. Baza zgodnie z zatwierdzonymi zasadami implementacji:
`4b4f6d478b5c734a196821106e984a6ade865536`.
Commit implementacji: `b2903b8`.
Diff: `git diff 4b4f6d478b5c734a196821106e984a6ade865536...b2903b8`.

Poniższe ustalenia opisują stan w chwili przeglądu. Następnie, 2026-10-21,
użytkownik potwierdził testy manualne („testy manualne ok”);
[ticket 05](issues/05-preview-controls.md) otrzymał status `done`.

Dwie osie sprawdzili równolegle niezależni agenci zgodnie ze skillem
`code-review`. Przegląd tylko do odczytu, bez ponawiania testów przez agentów.
Końcowy raport i status dokumentacji uzupełniono po otrzymaniu obu wyników.

## Standards

**0 naruszeń udokumentowanych zasad; 0 istotnych uwag heurystycznych.**

- Zmiany ograniczają się do `stmviewer/`, `tests/stmviewer/` i `docs/stmviewer/`.
  Nie naruszają granic współpracy ani wspólnych modułów.
- `raster.py` odpowiada za prezentację, `image_preview.py` za stan widoku
  i gesty, `filmstrip.py` za miniatury, a `main_window.py` łączy kontrolki.
  Podział zachowuje zasadę: „Kod aplikacji i jej testy dziel według
  odpowiedzialności” z `stmviewer/AGENTS.md`.
- Testy sprawdzają publiczne akcje i obserwowalne piksele; nie uzależniają
  kontraktu od prywatnych helperów. Próba niezmienności danych korzysta
  z publicznego widgetu i wartości pomiarowych.
- Wzorce mają odtwarzalny generator. Instrukcja ręczna podaje uruchomienie,
  dane, kroki i oczekiwane rezultaty. Dokumentacja odróżnia automatyczne
  Qt offscreen/xcb od oczekującego odbioru użytkownika i Windows.
- Proporcje pikselowe są udokumentowanym doprecyzowaniem zaakceptowanym
  przez użytkownika.

Wspólne `draw_frame()` zapobiega rozchodzeniu się prezentacji braków między
podglądem a miniaturami. `_zoom_at()` współdzieli geometrię kółka i przycisków.
Delegowanie `Filmstrip.set_pixel_proportions()` ukrywa konkretny model przed
oknem; nie wymaga usuwania jako „Middle Man”. Nie wprowadzono abstrakcji
na potrzeby przyszłego aligned ani eksportu.

Źródła standardów: `AGENTS.md`, `stmviewer/AGENTS.md`,
`docs/PARALLEL_DEVELOPMENT.md`, indeks implementacji, słownik i pełny
katalog heurystyk Fowler ze skillu. Nie znaleziono odrębnych
CODING_STANDARDS/CONTRIBUTING. Największy zmieniony plik kodu ma 314 linii.

## Spec

**0 brakujących wymagań, 0 rozszerzeń zakresu, 0 błędów realizacji.**

- „Gamma 0,1–4 […] zmienia wyłącznie prezentację. Miniatury pozostają original
  z gamma 1”: kontrolka, reset i renderowanie realizują ten kontrakt. Korekcja
  używa `u ** (1 / gamma)`; maska braków powstaje osobno, bez modyfikowania
  danych źródłowych.
- „NaN pokazuje szachownica niezależna od gamma”: przezroczyste brakujące
  próbki odsłaniają szachownicę; prawidłowe zera pozostają czarne. Obsłużono
  obraz stały i całkowicie brakujący.
- „Zmiana klatki zachowuje powiększenie i położenie widoku”: zachowywane są
  zoom, przesunięcie, gamma i wybrany sposób proporcji. Nowy poprawny import
  resetuje ustawienia; błąd i anulowanie zachowują wcześniejszy stan.
- Zatwierdzone „Proporcje pikselowe” obejmują obraz i miniatury, zachowując
  metadane źródłowe. Domyślne proporcje korzystają z poprawnej skali X/Y
  albo wymiarów pikselowych.
- Przewijanie prawego panelu jest uzasadnioną poprawką układu chroniącą
  rozmiar podglądu podczas importu.

Play, original/aligned, rejestracja i eksport pozostają zgodnie z planem
w kolejnych ticketach. Dokumentacja udostępnia wzorce i wykonalną próbę
ręczną; nie utożsamia automatycznych prób Qt z odbiorem użytkownika ani Windows.

Źródła: [ticket 05](issues/05-preview-controls.md), [słownik](../GLOSSARY.md),
[decyzja 02](../issues/02-preview-playback.md#answer),
[decyzja 06](../issues/06-acceptance.md#answer), konwencja gamma
z [decyzji 05](../issues/05-avi-export.md#answer) oraz zatwierdzona przez
użytkownika opcja proporcji pikselowych.

Łącznie: Standards — 0 ustaleń; Spec — 0 ustaleń. Brak uwag wymagających poprawki.
