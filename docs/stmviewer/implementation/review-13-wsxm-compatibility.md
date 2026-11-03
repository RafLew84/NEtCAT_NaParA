# Przegląd poprawki WSxM do ticketu 13

Baza `01259e130136a4621f9d12b9d0325c5c1d71bcfd`; implementacja `2343bd6`,
poprawka `e013d73`. Polecenie: `git diff 01259e1...HEAD`.
[Specyfikacja](issues/13-wsxm-compatibility-fix.md),
[kontrakt V3](../mpp-metadata-format.md).
Przeglądy wykonane równolegle przez dwóch niezależnych agentów, tylko do odczytu.

## Standards

Bez ustaleń. Zmiana pozostaje w aplikacji, jej testach i dokumentacji.
Moduł `mpp_missing.py` ma spójną odpowiedzialność. Największy zmieniony plik
kodu ma 766 linii i spełnia limit aplikacji. Testy korzystają z zatwierdzonych
publicznych granic zapisu/odczytu i kontrolek GUI. Dokumentacja rozróżnia
sprawdzenia automatyczne od odbioru użytkownika i Windows oraz opisuje
odtwarzalną próbę. Nie znaleziono naruszeń zasad ani przekonujących ustaleń
z heurystyk zapachów kodu. Status i handoff domknięto po testach.

Źródła standardów: AGENTS.md, stmviewer/AGENTS.md, docs/PARALLEL_DEVELOPMENT.md,
implementation/README.md, GLOSSARY.md; heurystyki skilla code-review.

## Spec

Jedno początkowe ustalenie P3: po przekroczeniu 64 MiB dodatku V3 komunikat
nie proponował wariantu NaN, choć kontrakt to zapowiadał. W `e013d73`
dodano wskazówkę tylko dla eksportu WSxM. Recenzent potwierdził zamknięcie.

Nie znaleziono innych brakujących wymagań, rozszerzenia zakresu ani błędów
poprawności. Odrzucanie całego dodatku, niezmienność skończonych próbek,
odtworzenie maski, wybór GUI i rollback odpowiadają specyfikacji.
Eksperyment recenzenta przez publiczne API potwierdził dokładność bitową
dla sygnalizujących NaN, payloadów NaN, ±Inf, ±0, tablic z ujemnym krokiem,
układem Fortran i big-endian. Przegląd nie ponawiał szerokich testów.

Standards: 0 ustaleń. Spec: 1 P3 poprawione, 0 otwartych ustaleń.
