# Przegląd 22 — dzielenie i scalanie domen

2026-11-09. Skill `code-review`, dwa niezależne przeglądy równoległe.
Baza `128bcef`, implementacja `0910c97`, poprawka `62644eb`.
Polecenie: `git diff 128bcef...HEAD`.
Spec: [22](22-split-merge-domains.md), wspólne kryteria oraz zasady
ręcznej edycji w [planie](README.md#edycja-ręczna-klas-i-domen).
Standardy: główne i aplikacyjne AGENTS.md oraz docs/PARALLEL_DEVELOPMENT.md.

## Standards

Nie stwierdzono naruszeń udokumentowanych standardów. Zmiany pozostają
w zakresie STM Domains, rozdzielają geometrię, operacje i UI;
dokumentują netcat, test ręczny oraz ograniczenia. Raport odróżnia
sprawdzenie autora od odbioru użytkownika i skuteczności detekcji.

Jedna uwaga heurystyczna: **możliwy Duplicated Code, niski priorytet**.
`ManualDomains._domain_record` i `ManualPanel.refresh` niezależnie
wyznaczają posortowany skład oraz wspólną klasę domeny. Wyniki są zgodne,
ale zmiana reguł może rozjechać listę w panelu i metadane operacji.
Zalecenie: wspólne podsumowanie domeny, formatowanie tekstu pozostaje w UI.
To sugestia utrzymaniowa, nie błąd działania ani twarde naruszenie.

**Zamknięta w `62644eb`**: historia i panel korzystają z jednej funkcji
`domain_record`; formatowanie pozostało w UI, reguła klasy nie zmieniła się.
Ponowny przegląd poprawki i całości względem `128bcef`: **0 twardych
naruszeń, 0 otwartych uwag heurystycznych**.

## Spec

**0 uwag** dla `git diff 128bcef...0910c97`.

Podział wymaga właściwego podzbioru jednej domeny; zachowuje ID reszty
i bieżącą klasę źródła. Scalenie obejmuje wszystkich członków wskazanych
domen, pozwala wybrać ID celu i jawnie sygnalizuje konflikt klas.
Obszary pozostają rozłączne, zachowują istniejące wsparcie i dziury.
Udokumentowana reguła 8-spójności odmawia łączenia przez przerwę.
Podgląd, anulowanie, porównanie oryginału, izolacja klatek i pojedyncze
Cofnij/Ponów korzystają z mechanizmów 21; historia zapisuje źródła i cele.
Nie stwierdzono rozszerzenia poza zakres zadania.

Dodatkowa próba recenzenta w netcat/Qt offscreen: podział kontrolnej D7
na 48 domen i podgląd ich scalenia w oknie 1024×768 — PASS;
komunikat i zatwierdzanie pozostają w oknie.

Ponowny przegląd `git diff 0910c97...62644eb`: **0 uwag, brak regresji
zgodności**. Wydzielenie `domain_record` zachowuje członków, klasy,
powiązania historii i informacje panelu. Reguły geometrii są niezmienione.

Końcowo: **Standards 0, Spec 0 — brak otwartych uwag w obu osiach**.
Odbiór ręczny użytkownika pozostaje otwarty.
Wykonane testy i GUI opisano w [raporcie odbioru](acceptance-22.md).
