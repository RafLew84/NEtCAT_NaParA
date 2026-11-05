# Przegląd 21 — ręczne domeny, Panel A

2026-11-05. Skill `code-review`, dwa niezależne przeglądy równoległe.
Baza `4d32fbe`, implementacja `a61e1b2`, poprawki `47bafe0`.
Polecenie: `git diff 4d32fbe...HEAD`.
Spec: [21](21-manual-domain-membership.md), zasady ręcznej edycji w indeksie
planu oraz wybór użytkownika: A widoczny wyłącznie podczas edycji.
Standardy: główne i aplikacyjne AGENTS.md oraz docs/PARALLEL_DEVELOPMENT.md.

## Standards

Początkowo: brak twardych naruszeń, dwie uwagi heurystyczne.
Kopiowanie identyfikatorów metod spowodowało literówkę freud i błędną
etykietę „Bazowa”; rekord źródłowego członkostwa budowano w dwóch miejscach.
Poprawiono importem istniejących stałych i wspólnym `_source_metadata()`.

Ponowny przegląd `4d32fbe...47bafe0`: oba ustalenia zamknięte. Nowa historia
sesji i korekta wyłączeń nie wprowadzają dalszych ustaleń. Zmiana testu
obrysu ogranicza tolerancję do jednego piksela rasteryzacji, nadal
sprawdzając widoczność i możliwość wskazania oznaczenia.
**0 twardych naruszeń, 0 otwartych uwag heurystycznych.**

## Spec

Początkowo: trzy ustalenia. Cofnij/Ponów działało jedynie na bieżącej klatce;
wczesna odmowa automatu mogła pozostawić punkt poza polem lub duplikat
jako dostępny do edycji; korekta freud miała błędną etykietę źródła.

Dodano wspólną chronologię operacji z opisem i nawigacją do klatki,
sprawdzanie wyłączeń przestrzennych niezależnie od stanu analizy oraz
stałe metod. Testy potwierdziły wcześniejsze błędy i przeszły po zmianach.
Ponowny przegląd `4d32fbe...47bafe0`: wszystkie trzy ustalenia zamknięte,
bez nowych regresji zgodności i bez dodatkowego rozszerzenia zakresu.
**0 otwartych ustaleń.**

Końcowo: Standards 0, Spec 0. Odbiór ręczny użytkownika pozostaje otwarty;
wykonane testy i GUI opisano w [raporcie odbioru](acceptance-21.md).
