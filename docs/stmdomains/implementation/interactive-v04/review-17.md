# SD-V4-17 — code-review

Baza `7cf0922`, implementacja `25252b2`; `git diff 7cf0922...25252b2`.
Dwa niezależne agenty według skilla `code-review`, po implementacji
zleconej przez `implement`. Spec: ticket 17, Panel A i wspólne kryteria
README. Standards: root/app AGENTS, GLOSSARY, README oraz smell baseline.
Końcowe poprawki `4c3f3c8`; sprawdzone ponownie przez obu recenzentów.

## Standards

Pierwotnie:

- P2: zapis poprawnego wyniku geometrycznego zależał od poprawności
  nieaktywnych pól bazowych (`project_view.capture_draft`). Po ustawieniu
  progu krawędzi 0,8 i średnicy regionu 0,1 użytkownik mógł obliczyć
  geometrię, lecz zapis zgłaszał błąd ukrytego szkicu. Dotyczy zachowania
  funkcji zapisu przy wprowadzeniu drugiej metody.
- Uznaniowy Duplicated Code: rasteryzacja/spójne komponenty/ziarna
  i numeracja były powtórzone w `geometry_regions` i `segmentation`.

Naprawiono w `4c3f3c8`: nieaktywne edycje bazowe mają niezależny zapis
surowych, ograniczonych wartości; walidacja ich zależności jest wymagana
przed obliczeniem tej metody, nie przy zapisie poprawnej geometrii.
Nie zmieniamy po cichu wpisanych progów. Obie metody korzystają ze
wspólnego `domain_raster.rasterize_domains` z jawną skalą X/Y.

Recenzent potwierdził zamknięcie obu uwag i regresję zapisu/otwarcia
z niepoprawnymi progami oraz odwróconym zakresem deskryptora.
**Standards: 0 otwartych uwag, brak nowych ustaleń.**

## Spec

Pierwotnie jedna uwaga P2: zapis geometrii zależny od nieaktywnego szkicu
bazowego, opisany powyżej. Dotyczy integracji Panelu A i zachowania
parametrów wyników. Pozostałe wymagania — niezależność od KMeans,
kontrola całego regionu, przełączanie i jawna porażka fazowa — obecne.
Zapis/eksport oceniony jako uzasadniona integracja wcześniejszych funkcji.

Recenzent sprawdził poprawkę `4c3f3c8`: zapis i walidacja geometrii
przechodzą, wartości nieaktywnego szkicu są zachowane, a powrót do
niepoprawnego szkicu bazowego blokuje jego analizę. Wspólna rasteryzacja
zachowuje bariery, spójność i skalę X/Y.
**Spec: 0 otwartych uwag, brak nowych ustaleń.**

Łącznie: Standards 0 otwartych (2 zamknięte); Spec 0 otwartych
(1 zamknięta, ten sam problem zapisu). Brak nierozwiązanych problemów
w obu osiach. Ograniczenia naukowe i odbiór: [raport 17](acceptance-17.md).
