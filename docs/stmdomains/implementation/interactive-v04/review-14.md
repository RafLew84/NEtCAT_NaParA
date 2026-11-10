# Przegląd SD-V4-14

Baza `0288aa7`; implementacja `a20e14b`, poprawka `361a7d0`.
Dwa niezależne przeglądy skilla `code-review`: osobno Standards i Spec.
Specyfikacja: [ticket 14](14-export-csv-png.md), wspólne kryteria planu
i [kontrakt CSV/PNG](../../issues/08-save-and-export.md).
Zasady: główny `AGENTS.md`, `stmdomains/AGENTS.md`, instrukcje współpracy
oraz wspólne kryteria. Nie znaleziono dodatkowych CONTRIBUTING/CODING_STANDARDS.
Pełna regresja i końcowa dokumentacja są opisane w [raporcie](acceptance-14.md).

## Standards

**0 naruszeń, 0 istotnych uwag** dla `0288aa7...a20e14b`.
Zmiany zachowują zakres aplikacji i podział odpowiedzialności: opcje
w core, tabele i zapis w IO, renderowanie i okno w UI. Renderer używa
istniejącej sceny i reguł kolorowania. Nie wskazano zapachu kodu
uzasadniającego refaktor.

Obsługa zadań zachowuje sygnały do zakończenia pracownika, ignoruje
spóźnione komunikaty anulowanego eksportu i ogranicza oczekujące
renderowanie do jednej klatki. Oczekiwanie sprawdza anulowanie,
więc zamknięcie nie wymaga dalszej obsługi GUI.

Recheck `a20e14b..361a7d0`: **0 nowych uwag**. Regresja sprawdza
działanie okna i zapis CSV, nie powtarza implementacji warunku.
Przeczytano również robocze dokumenty odbioru i formatu; końcowe
wyniki kontroli uzupełnił agent główny.

## Spec

Pierwszy przegląd wskazał **1 P2**: przy wyniku klatki 1 i przejściu do
nieanalizowanej 2 wybór ostatniego przebiegu nadal domyślnie eksportował
bieżącą 2. Kontrakt wymaga domyślnego zakresu wybranego wyniku.
Poprawka `361a7d0` wybiera bieżącą klatkę tylko gdy jest ona całym zakresem
analizy; pojedynczy wynik innej klatki dostaje zakres tej klatki.
Test był czerwony dla błędnego wyboru, po zmianie potwierdził właściwy CSV
i niezmieniony bieżący widok. Trzy testy okna PASS.

Recheck: **P2 zamknięte, 0 otwartych uwag**. Pozostały sprawdzony zakres:
rozdzielenie przebiegów, braki versus zera, faktyczne parametry versus szkic,
kolory/warstwy/gamma i wycinek PNG, niezmienność przypisań oraz błędy,
anulowanie i zamykanie — bez dodatkowych uwag. Nie stwierdzono rozszerzenia
poza zakres. Raport i format poprawnie rozdzielają sprawdzenia agenta
od przyszłego odbioru użytkownika.

Stan końcowy: Standards 0 otwartych ustaleń; Spec 1 P2 zamknięte,
0 otwartych ustaleń.
