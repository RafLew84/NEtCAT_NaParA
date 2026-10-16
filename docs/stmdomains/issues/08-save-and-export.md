# Co zapisujemy i eksportujemy po próbach metod?

ID: 08
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 01, 05, 06, 07

## Question

Jaki własny zapis wyników STM Domains i eksport są potrzebne po próbach metod
do ponownego otwarcia pracy, odtworzenia obliczeń i porównywania serii?

Ustalmy rozdzielenie wejściowego zapisu z innego programu od wyników analizy,
identyfikację obrazów i klatek, geometrię, parametry i wersje metod, maski
pokrycia i wysp, orientacje sieci, wspólną definicję typów, przypisania molekuł,
granice i statystyki.
Które elementy są konieczne, a które można bezpiecznie przeliczyć?

Jak zapamiętujemy niepewność i ewentualne zaakceptowane korekty, jeśli próby
ujawnią taką potrzebę? Kiedy zmiana parametrów, geometrii albo danych unieważnia stare
wyniki? Jakie tabele i obrazy użytkownik chce wyeksportować, wraz z jednostkami,
obszarem odniesienia i rozróżnieniem zera od braku danych?

Rozstrzygnięcie to kontrakt trwałości i potrzebne formaty wyników. Przeniesienie
pliku na inny komputer powinno zachować możliwość poprawienia odnośnika do
oryginalnego obrazu. Duże dane i modele pozostają poza Git.

Ustalmy również sposób ponownego pokazania zapisanych warstw, wyboru typu
i powiązania tabeli lub wykresu z klatką. Zapisywanie oraz porównywanie wyników
rozwija etap 2 i nie jest warunkiem odbioru podstawowej przeglądarki.

Kontekst: [obecny eksport MolTrack](../../../moltrack/persistence/domain_analysis_export.py)
jest przykładem związanym z M6, nie gotowym kontraktem nowej analizy.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md)
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](06-frame-statistics.md)
- [Jak przeglądać obrazy i oznaczenia w szkielecie?](07-browsing-and-comparison.md)
