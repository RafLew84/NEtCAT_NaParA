# Co zapisujemy i eksportujemy po próbach metod?

ID: 08
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 01, 06, 07, 13

## Question

Jaki własny zapis wyników STM Domains i eksport są potrzebne po próbach metod
do ponownego otwarcia pracy, odtworzenia obliczeń i porównywania serii?

Zakończony pilotaż wskazał braki i nie wybrał metody. Kontrakt zapisu opieramy
na odbiorze dalszych prób, nie na numerach klastrów z prototypu.

[Uzgodnione statystyki klatek](06-frame-statistics.md#answer--2026-10-19)
wymagają zachowania obu mianowników powierzchni, liczby wszystkich poprawnych
oznaczeń ze środkiem w polu, jednostek i dostępności poszczególnych miar.
Wynik częściowy, zero i brak pomiaru pozostają rozróżnialne. Zapis nie może
gubić przyczyn nieprzypisania, ucięć brzegiem ani wersji wspólnego katalogu.

Użytkownik dopuścił ręczne rozstrzygnięcie konkretnego nakładania domen przez
wybór jednej z propozycji. Ustalmy sposób zachowania obszaru konfliktu,
automatycznych propozycji i decyzji użytkownika, aby odtworzyć geometrię oraz
przeliczyć statystyki bez udawania automatycznego wyniku. Korekta odnosi się
do konkretnej analizy; nie przechodzi po numerze domeny na nowy katalog.
Nie rozszerza to zakresu do pełnego edytora granic ani tworzenia oznaczeń.

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
- [Które metody i warunki odmowy wyniku przyjmujemy po próbach?](13-method-acceptance.md)
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](06-frame-statistics.md)
- [Jak przeglądać obrazy i oznaczenia w szkielecie?](07-browsing-and-comparison.md)
