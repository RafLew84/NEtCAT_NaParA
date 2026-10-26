# Przegląd: ujednolicenie zapisu i białe tło

Baza `7123d1b8bcf20d640d6adb63bc8f313d50be6696`; implementacja `2175cfe`.
Polecenie: `git diff 7123d1b...2175cfe`.
[Specyfikacja](issues/13-white-background.md). Dwóch niezależnych recenzentów,
równoległe przeglądy tylko do odczytu.

## Standards

Bez ustaleń. Zakres pozostaje w Viewerze i jego testach/dokumentacji.
Największy zmieniony plik ma 765 linii. Testy korzystają z zatwierdzonych
publicznych granic zapisu/odczytu i GUI. Instrukcje opisują nowe zachowanie
i rozdzielają odbiór użytkownika od automatycznych sprawdzeń.
Brak przekonujących zapachów kodu: wspólne `draw_frame` odpowiada za
podgląd i miniatury, polityka wypełniania pozostaje w `background_value`.
Źródła: AGENTS.md, stmviewer/AGENTS.md, PARALLEL_DEVELOPMENT.md,
implementation/README.md, GLOSSARY.md i heurystyki skilla code-review.

## Spec

Bez ustaleń. GUI oferuje original/aligned, zapis używa maksimum klatki i V3,
a podgląd i miniatury pokazują białe braki niezależnie od gamma. Pomiary,
rejestracja i geometria bez zmian. Czytnik używa zapisanego `fill_value`,
więc stare V3 z minimum nadal są obsługiwane. API zachowuje parametr
zgodności i dotychczasowy domyślny zapis NaN. Dokumentacja wyjaśnia zależność
wyglądu MPP od palety, kontrastu i stałych klatek. Brak rozszerzenia zakresu.

Standards: 0 ustaleń. Spec: 0 ustaleń. Recenzenci nie ponawiali testów.
