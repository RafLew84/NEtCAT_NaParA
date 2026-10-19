# Co zapisujemy i eksportujemy po próbach metod?

ID: 08
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: claimed
Assignee: Codex — domains/save-export-contract
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

## Discussion — 2026-10-19

### Pierwsza runda — przyjęte przez użytkownika

- Jeden samowystarczalny plik zawiera także obrazy MPP. Odrzucono propozycję
  przechowywania obrazu jako zewnętrznego odnośnika. Ponowne otwarcie nie
  wymaga ani źródłowego MPP obok pliku, ani pierwotnego zapisu MolTrack.
- Jeden wybrany wynik analizy w pliku. Warianty parametrów można zachować
  w osobnych plikach przez „Zapisz jako”; bez historii wielu prób w projekcie.
- Podstawowy eksport: tabele CSV i obrazy PNG z nakładkami; wykresy również PNG.

Pozostałe zachowania są ustalane w kolejnych rundach. To nie jest jeszcze
pełne rozstrzygnięcie ticketu ani implementacja formatu.

### Fakty z audytu lokalnego kodu

Audyt był tylko do odczytu; nie uruchamiano starych testów ani eksportera.

- [Eksporter Domain Analysis](../../../moltrack/persistence/domain_analysis_export.py)
  zapisuje manifest i CSV w katalogu i wymaga opublikowanego wyniku M6.
  [Nagłówki tabel](../../../moltrack/persistence/domain_analysis_export_schema.py)
  nie realizują definicji powierzchni, jednostek i stanów STM Domains.
- [UI eksportera](../../../moltrack/ui/domain_analysis_runtime.py) przekazuje
  jako tożsamość źródła jego nazwę i ścieżkę. Hash takiego słownika nie jest
  sumą kontrolną danych obrazu. [Sesja MolTrack](../../../moltrack/persistence/session_store.py)
  sprawdza wielkość i datę źródła; nie wystarcza to do mocnej identyfikacji.
- [Eksport z korektami](../../../moltrack/persistence/correction_aware_export.py)
  pokazuje rozdzielenie automatu i wyniku po decyzjach użytkownika. Jego
  mechanizm rewizji/rebase i znaczenia orientacyjne nie przechodzą automatycznie
  do niewielkiego STM Domains.
- [Sesja NanoTrack](../../../nanotrack/persistence/session_store.py) jest
  przykładem jednego archiwum ZIP z JSON i tablicami NPZ. Wciąż doczytuje obraz
  ze źródła zewnętrznego; dołączenie MPP jest nowym wymaganiem STM Domains.
- [Zapis atomowy JSON](../../../moltrack/persistence/atomic_json.py) i
  [publikowanie pakietu](../../../moltrack/persistence/package_io.py) pokazują
  zapis tymczasowy przed zastąpieniem celu oraz strumieniowe sumy SHA-256.
  To wzorce do oceny, nie zadanie zmiany wspólnych modułów.

## Comments

### 2026-10-19 — podjęcie na bezpośrednie polecenie użytkownika

Rozmowę o zapisie rozpoczynamy przed odbiorem metod, jako wskazany przez
użytkownika wyjątek od kolejności mapy. Ustalamy kontrakt wspólny dla metod,
a szczegóły zależne od wyników prób pozostają do weryfikacji podczas ich
odbioru. Nie oznacza to wyboru ani zatwierdzenia algorytmu i nie rozszerza
pierwszego etapu o implementację zapisu.
