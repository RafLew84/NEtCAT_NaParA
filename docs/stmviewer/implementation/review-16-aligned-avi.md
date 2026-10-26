# Code review — ticket 16

Baza: `903d00b6e21c9cbe2609ca151d09480c2551c754`.
Implementacja: `ecc8663`; poprawka po przeglądzie: `883b3ae`.
Przegląd skilla `code-review` przez dwóch niezależnych recenzentów;
oba przeglądy objęły finalny diff `git diff 903d00b...883b3ae`.

Specyfikacja: [ticket 16](issues/16-aligned-avi.md),
[AVI](../issues/05-avi-export.md#answer),
[rejestracja](../issues/03-registration.md#answer).
Standardy: główny i aplikacyjny AGENTS.md, zasady implementacji i współpracy,
słownik oraz reguły TDD publicznych granic; dodatkowo heurystyki skilla.

## Standards

**0 naruszeń, 0 uwag heurystycznych po poprawce.**

Pierwotna opcjonalna uwaga Feature Envy dotyczyła sprawdzania zgodności
wyniku rejestracji z serią w konstruktorze okna AVI. Została rozwiązana:
`avi_sources.py` skupia przygotowanie danych dla eksportu, a okno udostępnia
otrzymany wariant. Osobny adapter jest uzasadniony różnicą między kalibracją
eksportowanego zakresu a skalą podglądu.

Nowe testy pozostają na zatwierdzonych granicach: publiczne kontrolki GUI →
widoczny wynik oraz eksport → rzeczywiście odczytany film. Sprawdzają konkretne
wymiary, proporcje i zachowanie podglądu bez mockowania własnych modułów.
Nie stwierdzono nowych problemów względem udokumentowanych zasad.

## Spec

**0 otwartych uwag po poprawce.**

Pierwotne P2: zakres aligned z jednolicie skalibrowanych klatek pierwotnie
mieszanej serii pozostawał w proporcjach pikselowych. Wymaganie dotyczy wspólnej
skali eksportowanych klatek, a nie koniecznie wszystkich klatek rejestracji.
`aligned_movie_frames` zachowuje tablice próbek i pełny obszar, przekazując
kalibrację poszczególnych oryginałów do planowania eksportu.

Niezależne sprawdzenie recenzenta potwierdziło:

- cała mieszana seria: 54 × 34, proporcje pikselowe;
- jednolicie skalibrowany zakres oraz seria po usunięciu odstającej klatki:
  106 × 34, proporcje fizyczne;
- niezmienione próbki, obszar 53 × 34 i metadane podglądu.

Nowe testy GUI obejmują oba scenariusze, a instrukcja ręczna odzwierciedla
poprawione zachowanie. Nie znaleziono dalszych braków, błędów względem
specyfikacji ani rozszerzenia zakresu.

Wynik końcowy: Standards **0 otwartych uwag**, Spec **0 otwartych uwag**.
