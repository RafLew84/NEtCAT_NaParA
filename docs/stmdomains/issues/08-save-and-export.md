# Co zapisujemy i eksportujemy, aby odtworzyć analizę?

ID: 08
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — specyfikacja analizy typów uporządkowania w serii](../map.md)
Blocked by: 01, 05, 06, 07

## Question

Jaki własny zapis wyników STM Domains i eksport są potrzebne do ponownego
otwarcia pracy, odtworzenia obliczeń i porównywania serii poza aplikacją?

Ustalmy rozdzielenie wejściowego zapisu z innego programu od wyników analizy,
identyfikację obrazów i klatek, geometrię, parametry, wzorce orientacji, wersje
metod, wspólną definicję typów, przypisania molekuł, granice i statystyki.
Które elementy są konieczne, a które można bezpiecznie przeliczyć?

Jak zapamiętujemy zaakceptowane korekty i niepewność, jeżeli poprzednia decyzja
je dopuściła? Kiedy zmiana parametrów, geometrii albo danych unieważnia stare
wyniki? Jakie tabele i obrazy użytkownik chce wyeksportować, wraz z jednostkami,
obszarem odniesienia i rozróżnieniem zera od braku danych?

Rozstrzygnięcie to kontrakt trwałości i potrzebne formaty wyników. Przeniesienie
pliku na inny komputer powinno zachować możliwość poprawienia odnośnika do
oryginalnego obrazu. Duże dane i modele pozostają poza Git.

Kontekst: [obecny eksport MolTrack](../../../moltrack/persistence/domain_analysis_export.py)
jest przykładem związanym z M6, nie gotowym kontraktem nowej analizy.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)
- [Jak odkrywać domeny i zachować stałe typy w całej serii?](05-stable-types-across-frames.md)
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](06-frame-statistics.md)
- [Jak przeglądać klatki, domeny i zmiany ilościowe?](07-browsing-and-comparison.md)
