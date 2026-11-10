# Przegląd 23 — ręczne klasy i przypisania

2026-11-09. Skill `code-review`, dwa niezależne przeglądy równoległe.
Baza `09d8001`, implementacja `94d5a94`, poprawka `b11d09a`.
Polecenie: `git diff 09d8001...HEAD`.
Spec: [23](23-manual-classes.md), wspólne kryteria i zasady
[ręcznej edycji](README.md#edycja-ręczna-klas-i-domen).
Standardy: główne i aplikacyjne AGENTS.md oraz docs/PARALLEL_DEVELOPMENT.md.

## Standards

**0 naruszeń udokumentowanych standardów.** Zmiany pozostają w zakresie
STM Domains. Kod rozdziela listy klas, operacje i UI; dokumentacja opisuje
netcat, test ręczny, ograniczenia oraz odróżnia sprawdzenie autora od
odbioru użytkownika i oceny detekcji.

Jedna uwaga heurystyczna: **możliwy Feature Envy, niski priorytet**.
`ManualClassDialog.refresh` sam szukał pierwotnej wersji w kolekcji rewizji
i przechodził po wariantach, aby wyznaczyć zakres wspólnej listy. UI znało
szczegóły przechowywania historii i powiązań; zalecenie: zapytania w
`ManualClassLists`/`ManualController`, formatowanie w dialogu.

**Zamknięta w `b11d09a`**: wybór pierwotnej wersji i powiązanych klatek
przeniesiono do warstwy list/kontrolera. Przygotowanie wariantu przed
publikacją klatki, test legendy i dopasowanie wysokości dialogu nie
wprowadzają nowych uwag. **0 twardych naruszeń, 0 otwartych heurystyk.**

## Spec

Pierwotny niezależny przegląd `09d8001...94d5a94`: **0 uwag**.
Stabilne ID i wersje list, pochodzenie, ograniczenie usuwania do pustych
klas ręcznych; lokalne przypisania i podział części domeny; wspólne
metadane w konkretnym katalogu; niezmienny model; podgląd, porównanie
oraz historia spełniają zakres ticketu. Bez rozszerzenia zakresu.

Dodatkowa próba recenzenta w netcat/Qt offscreen: 50 kolejnych zmian klasy
po podziale i cofnięcie całej sekwencji — PASS. Zachowano liczebność oraz
geometrię, wrócono do oryginału; lista bez modelu pozostała odizolowana.

Sesja nadrzędna wykryła dodatkowy błąd rzeczywistego widoku: po przejściu
na klatkę nowo podłączoną do listy przy zamkniętym panelu zagnieżdżony
sygnał `frame_changed` mógł nadpisać poprawioną legendę starszym widokiem.
Test publicznego okna potwierdził błąd przed poprawką. `b11d09a` przygotowuje
wariant przed publikacją klatki; test teraz przechodzi, sprawdzając też
niezmienność przypisań. Ponowny przegląd `94d5a94...b11d09a` potwierdził
zamknięcie błędu i **0 nowych uwag, brak regresji zgodności**.

Końcowo: **Standards 0, Spec 0 — brak otwartych uwag w obu osiach**.
Odbiór ręczny użytkownika potwierdzony 2026-11-09 dla wersji `14f39d6` („testy manualne ok”). Testy i wykonane GUI:
[raport odbioru](acceptance-23.md).
