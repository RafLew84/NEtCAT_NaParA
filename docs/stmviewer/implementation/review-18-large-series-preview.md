# Code review — ticket 18

Baza: `08c1f3c4495a9d15b6632811fe4a99fc76b511fa`.
Implementacja: `fb6b4e4`, poprawki: `ae06831`.
Dwóch niezależnych recenzentów skilla `code-review` oceniło zakres
`git diff 08c1f3c...ae06831`, w tym ponownie poprawki.

Specyfikacja: [ticket 18](issues/18-large-series-preview.md) i
[kryteria odbioru](../issues/06-acceptance.md#answer).
Standardy: główny i aplikacyjny AGENTS.md, zasady współpracy i implementacji,
słownik, granice TDD i heurystyki skilla. Brak osobnych plików CONTRIBUTING
lub CODING_STANDARDS. Produkcji nie zmieniano; to etap pomiaru i odbioru
istniejącego kontraktu, bez produkcyjnej poprawki red → green.

## Standards

**0 otwartych ustaleń.**

Początkowa opcjonalna uwaga Duplicated Code dotyczyła osobnego sumowania RSS
w samplerze i odczycie chwilowym. Poprawka sprawia, że `_sample()` korzysta
z `snapshot()`, więc obliczanie RSS ma jedno źródło. Wspólne `source_identity()`
ujednolica identyfikację wejścia w obu narzędziach, a dokumentacja opisuje
moment obliczania sumy kontrolnej. Nie stwierdzono nowych naruszeń reguł
ani uwag heurystycznych.

## Spec

**0 otwartych ustaleń.**

Pierwotne P2: raport rzeczywistego TTMAPP nie zawierał rozmiaru ani SHA-256,
wbrew wymaganiu manifestu wybranych plików. Uzupełniono oba wejścia w raporcie
oraz lokalnym manifeście; oba narzędzia zapisują identyfikację w kolejnych
raportach. Recenzent niezależnie potwierdził 140 518 099 bajtów i hash TTMAPP.
Nie stwierdzono nowych braków ani rozszerzenia zakresu.

Pomiar obejmuje faktyczne piksele, 30 s Play obu widoków, 400 prób reakcji,
powiększone aligned, anulowanie, ponawianie i rozróżnienie RSS od żywych
buforów. Ograniczenia stanowiska i otwarty odbiór ręczny są jawne.
Niezależnie powtórzone małe testy: **4 passed**.

Wynik końcowy: Standards **0 ustaleń**, Spec **0 ustaleń**.
