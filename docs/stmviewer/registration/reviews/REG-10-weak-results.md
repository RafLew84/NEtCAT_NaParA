# REG-10: przegląd poprawki niepewnych wyników

Data: 2026-11-02. Baza `93a3126`, implementacja `7e7084c`.
Dwa niezależne przeglądy zakresu `git diff 93a3126...7e7084c`.
Źródło wymagań: [zaakceptowana zmiana i diagnoza](../efficient-loftr-weak-results.md).

## Standards

0 istotnych uwag do kodu lub testów. Zmiana pozostaje w zakresie Viewera,
a największy zmieniony plik Python ma 358 linii. Testy dotyczą publicznych
granic zachowania i trwałości wyników. Próby automatyczne są oddzielone
od ręcznej oceny obrazu (potwierdzonej później przez użytkownika).

## Spec

0 otwartych uwag. Słaby wynik jest dostępny z ostrzeżeniem; rzeczywisty brak
punktów nadal daje odmowę. Status przechodzi przez łańcuch, graf, sesję,
ręczne korekty i MPP, bez sztucznej liczbowej pewności. Starsze diagnozy v1
pozostają odczytywalne. Kompletność filmu nie jest przedstawiana jako
potwierdzenie jakości dryfu.

Jedną uwagę dokumentacyjną poprawiono: LS używa równych wag, natomiast
Huber wyznacza wagi z reszt. Status i score modelu nie są źródłem wag.

## Sprawdzenia

712 testów Viewer passed, 8 skipped; osobno 6 testów rzeczywistych wag
CPU/CUDA passed. Mypy: 90 modułów bez błędów; Ruff i diff-check czyste.
389 odnośników lokalnych sprawdzono bez braków. Pełne próby MOVIE_4/MOVIE_8,
sesje, korekty i eksporty opisuje raport diagnozy. Użytkownik potwierdził
ręczny odbiór poprawki 2026-11-02: „testy manualne ok”; REG-10 ma status `done`.
