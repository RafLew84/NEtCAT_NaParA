# STM Domains — wybór wielu molekuł i fragmenty klas

2026-11-09. Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź
`domains/interactive-v04-ui`; baza `648aa4d`, poprawka **`8edc163`**.
Zgłoszenie: każde osobne przypisanie tworzyło kolejną małą domenę tej samej
klasy, a okno klas zasłaniało wybór narzędzia zaznaczania w panelu.

Dodano wspólne narzędzia Kliknięcia/Lasso i tryby Dodaj/Odejmij/Zastąp w
oknie klas oraz podziału klasy. Zaznaczenia można zbierać i przypisać raz.
Opcjonalne, domyślnie wyłączone **Połącz stykające się domeny tej klasy**
łączy obszary docelowej klasy osiągalne od zaznaczenia. Także dla wcześniej
utworzonych fragmentów tej samej klasy. Kryterium jak w 22: 8-sąsiedztwo,
spójny obszar i wsparcie centrów. Nie łączy przez przerwy; zachowuje sumę
masek, oryginał modelu i osobność punktów bez domeny. Atomowe Cofnij/Ponów
oraz zapis projektu z 24 obejmują całe przypisanie i połączenie.

[Obsługa i instrukcja ręczna](implementation/interactive-v04/manual-class-selection.md).
Netcat: **54 testy PASS / 34,44 s**, mypy **124 moduły PASS**. Natywne
Qt/X11: kontrola 2 kliknięć, naprawa 4→3 domen, zapis/odczyt i historia PASS;
TTMAPP268 K5, 3 fragmenty → 1, liczba domen 8→6, suma masek bez zmian PASS.
9 plików Python, maksimum **384 linie**. Bez zależności i zmian wspólnych.
Pełnej regresji nie powtarzano; 645 PASS poniżej dotyczy wersji przed poprawką.
Artefakty lokalne: `.scratch/stmdomains-class-selection/`.

**Odbiór użytkownika tej poprawki i ticketu 24 otwarty.** Przed restartem
zachować bieżące korekty w projekcie Po korektach. Następne 25 → 26;
19–20 odłożone. To poprawa ręcznej obsługi, nie nowa ocena jakości detekcji.

---

# STM Domains — SD-V4-24: trwałe korekty i historia

2026-11-09. Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź
`domains/interactive-v04-ui`; baza `6b5820c`. Commity: implementacja
**`1c1b798`**, poprawki przeglądu **`9b7a19b`**, poprawka Dopasuj/dirty
**`94803e8`**. **Odbiór ręczny użytkownika 24 pozostaje otwarty.**

**Plik → Zapisz projekt…** zapisuje wybrane korekty, automatyczny oryginał
(albo jawny brak analizy), klasy/nazwy/kolory, domeny/geometrię i pełną
historię Cofnij/Ponów z pozycją. Wieloklatkowe operacje pozostają atomowe.
Po otwarciu bez źródeł i obliczeń można wznowić ten sam wariant. Zapisz jako
zachowuje poprzedni plik; nadpisanie samym automatem pozostawia pominięte
korekty jako niezapisane. Zamknięcie/otwarcie: Zapisz/Odrzuć/Anuluj.
Kontener v2 z sumami kontrolnymi i atomową podmianą; v1 bez korekt działa.

[Obsługa, gotowe pliki i test ręczny](implementation/interactive-v04/acceptance-24.md),
[przegląd](implementation/interactive-v04/review-24.md).
Netcat: mypy **124 moduły PASS**; końcowa regresja **645 testów PASS /
292,67 s** dla `94803e8` (`regression.xml`).
Natywne Qt/X11 dla końcowej wersji: kontrola 9/7 po usunięciu jej źródeł,
TTMAPP259–260 K5 (7/5 bazowych domen), dokładne przypisania/rastry,
Cofnij/Ponów, wznowienie wariantu, Zapisz jako, brak analizy i odrzucenie
uszkodzenia bez utraty pracy PASS. To kontrola trwałości i UI, nie jakości
detekcji. Artefakty: `.scratch/stmdomains-ui-24/`.

Standards: 1 P1 poprawiona; Spec: 2 P2 poprawione; recenzenci potwierdzili
zamknięcie uwag. Dodatkowo natywna próba wykryła fałszywe dirty po dopasowaniu
układu okna; poprawka z testem RED/GREEN i powtórzonym GUI.
22 zmienione pliki Python, maksimum **912 linii**, wszystkie poniżej 1000.
Bez nowych zależności i zmian współdzielonych. Szersze mypy całego `tools/`
ma 2 uprzednie błędy w `freud_trial.py:58,63`, odtworzone na bazie;
standardowy zakres oraz zmienione narzędzia przechodzą.

Następne **25 → 26**; 19–20 odłożone. Eksport ręcznych korekt pozostaje
zablokowany do 25. Starsze wpisy poniżej opisują historyczne ograniczenia.

---

# STM Domains — odbiór ręczny SD-V4-23a

**2026-11-09: użytkownik potwierdził „testy manualne ok”.**
Odebrano ticket **23a — scalanie i dzielenie klas**, wraz z poprawką
pustej nazwy nowej klasy (`7db599f`). Testowana wersja: **`eb112f6`**.
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/interactive-v04-ui`.

Zaktualizowano ticket, plan, raport odbioru i dokumentację startową.
To zapis odbioru użytkownika; kod aplikacji nie został zmieniony i testów
nie uruchamiano ponownie. Wcześniejsze wyniki sprawdzeń pozostają w
[raporcie 23a](implementation/interactive-v04/acceptance-23a.md).

Następny ticket: **24 — zapis korekt i wznowienie ręcznej edycji projektu**,
potem **25 → 26**. Implementacji 24 nie rozpoczęto. 19–20 nadal odłożone.

---

# STM Domains — domyślne nazwy pustych klas

2026-11-09. Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź
`domains/interactive-v04-ui`; baza `27a939c`, poprawka **`7db599f`**.
Zgłoszenie: tworzenie przez **Nowa pusta** bez nazwy, później podpis `?1`.
Odtworzono faktyczną sekwencję okna: walidacja odrzucała utworzenie, cel
pozostawał Nieustalona, a późniejsze przypisanie dawało `?1` zamiast C1.

Tworzenie z pustą nazwą lub spacjami nadaje pierwszą wolną literę pełnej
listy (także klas pustych); wspólna reguła 23/23a, podpowiedź w polu nazwy.
Zmiana nazwy istniejącej klasy nadal wymaga niepustej nazwy. `?` pozostaje
nieustaloną klasą; nie naprawiamy istniejących przypisań automatycznie.
[Instrukcja bieżącej naprawy bez restartu i odbioru](implementation/interactive-v04/acceptance-23a.md#poprawka-pustej-nazwy-nowej-klasy--2026-11-09).

Netcat: **48 testów PASS / 22,30 s**, mypy **119 modułów PASS**.
Natywne Qt/X11 TTMAPP268 K5: klasy F/G bez wpisywania nazwy, podpisy F1/G1,
5→7 domen po dwóch częściowych przypisaniach, Cofnij/Ponów PASS.
To kontrola edycji, nie pomiar jakości detekcji. Pełnej regresji nie powtarzano;
624 PASS poniżej dotyczy poprzedniej wersji. Zmieniono 5 plików kodu/testów,
maksimum 268 linii; wyłącznie zakres STM Domains. Bez nowych zależności,
bez potrzebnych zmian współdzielonych. Artefakty lokalne:
`.scratch/stmdomains-class-name-report/`.

**Odbiór ręczny użytkownika 23a wraz z poprawką nazw potwierdzony 2026-11-09 dla wersji `eb112f6` („testy manualne ok”).** Kolejność 24 → 25 → 26;
korekty nadal tylko w pamięci sesji, zapis w 24, eksport w 25.

---

# STM Domains — SD-V4-23a: scalanie i dzielenie klas

2026-11-09. Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź
`domains/interactive-v04-ui`, baza `ee2071d`, implementacja `5ca2e6f`, poprawka `5de0d7f`.
**Odbiór ręczny użytkownika 23a otwarty**; 23 odebrano wcześniej.

## Wynik

W oknie **Klasy ręczne…** są **Scal klasy… / Podziel klasę…**. Niemodalne
okno pokazuje konkretną listę/wersję, wybór źródeł i celu, bieżącą klatkę,
zakres lub całą serię tej listy. Tabela pokazuje konkretne klatki, liczniki
przed/po, warianty i przyczyny pominięcia. Dwuklik nawiguje po podglądzie.
Podział wymaga osobnego zapamiętania wskazań na każdej objętej klatce.

Podgląd jest przygotowywany w tle, zakres i wersje pozostają przypięte;
anulowanie/zmiana kontekstu unieważnia podgląd. Zatwierdzenie i Cofnij/Ponów
obejmuje wszystkie zmienione klatki oraz listę klas jednym krokiem, zgodnie
z globalną kolejnością późniejszych edycji 21–23. Scalenie klas zachowuje
osobne domeny; częściowy podział korzysta z 22/23. Punkty bez domeny
zachowują ten stan. Źródłowe ID, model i K nie zmieniają się.

Gotowy przykład: w netcat `python -m stmdomains.tools.class_operations_demo --open`.
Pliki lokalnie w `.scratch/stmdomains-ui-23a/demo/`; launcher przygotowuje
przez operacje 23 dwa członkostwa A bez domeny w RAM. Sam zapis bazowy nie
przechowuje tych korekt — to zakres 24.
[Instrukcja i próba TTMAPP](implementation/interactive-v04/acceptance-23a.md).

## Weryfikacja i dalsza praca

Netcat/offscreen: pełna regresja **624 PASS / 280,46 s**; testy celowane
**32 PASS / 22,96 s**, po poprawce zakresu **13 PASS / 7,92 s**.
Pierwszy pełny przebieg przerwał SIGTERM bez błędu testu; ponowienie w sesji
terminalowej dało kod 0 i raport `regression.xml`.
[Przegląd](implementation/interactive-v04/review-23a.md): Standards 0; Spec 1 P2 poprawiona, 0 otwartych.
Mypy 119 modułów PASS. Natywne Qt/X11: kontrola 9/7, podziały 5/4 i 1/8,
0 domen bez modelu, anulowanie, nawigacja, historia i TTMAPP259–260 PASS.
TTMAPP K5: początkowo 7/5 domen i 116/104 przypisania; scalenie A+B do
Połączone daje 76/82 członków, wydzielona cała domena ma 50 członków;
maski i K bez zmian. To test edycji, nie ocena skuteczności detektora.

Korekty nadal tylko w sesji. Następny **24 → 25 → 26**, 19–20 `deferred`.
Brak potrzebnych zmian współdzielonych modułów i nowych zależności.
Zmieniono tylko `stmdomains/`, `tests/stmdomains/`, `docs/stmdomains/`.
11 plików kodu/testów, maksimum 891 linii (`ui/session_controller.py`);
wszystkie poniżej celu 1000. Spójność linków, tabeli 27 ticketów i DAG PASS.
Artefakty/przebiegi lokalne: `.scratch/stmdomains-ui-23a/`.

---

# STM Domains — poprawka nazw klas i domen po zgłoszeniu do 23

**Odbiór ręczny 23 wraz z poprawką nazw potwierdzony przez użytkownika
2026-11-09: „testy manualne ok”.** Testowana wersja: `14f39d6`,
kod poprawki: `8d4ec04`. Zaktualizowano statusy w tickecie, planie i raportach.
Ta aktualizacja dotyczy dokumentacji; nie uruchamiano ponownie testów aplikacji.

2026-11-09. Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź
`domains/interactive-v04-ui`, baza `a42ca1c`. Implementacja **`8d4ec04`**.
Użytkownik skorygował znaczenie nazw: klasa D i jej osobne domeny D1, D2…;
w widoku Klasy nadal widział ogólne D1, D2… niezależnie od klasy.

Przyczyna: stały napis `D + domain_local_id` w malowaniu obszaru.
Test rzeczywistego `DomainOverlay.paint` odtworzył `D1, D2` zamiast `A, A`
i po poprawce przechodzi. Wspólna reguła nazw obejmuje obraz, legendę,
panel edycji, podgląd operacji, szczegóły molekuły/pomiaru i eksport PNG.
Automatyczne klasy A…Z, AA… według całego katalogu; puste klasy nie przesuwają
liter. Widok Klasy: D, D; widok Domeny: D1, D2. Własne nazwy pozostają
edytowalne; nieustalona klasa ?, jej domeny ?1, ?2. Nazwy prezentacyjne
nie zmieniają ID, masek, członkostwa ani modelu. Panel pokazuje również ID;
CSV/JSON zachowują oryginalne identyfikatory. Numery domen są lokalne dla
klatki i mogą zmienić się po zmianie składu klas; bez śledzenia w czasie.

[Reguły oraz instrukcja sprawdzenia](implementation/interactive-v04/acceptance-23.md#poprawka-podpisów-po-zgłoszeniu-użytkownika--2026-11-09).
Natywne Qt/X11 w netcat: kontrola D/D ↔ D1/D2, porównanie oraz Cofnij/Ponów
PASS. TTMAPP268, K5 wspólny 259–268: 4 domeny, 119/308; obraz i PNG PASS.
Obejrzano zrzuty. To sprawdzenie autora, nie odbiór użytkownika ani ocena
detekcji. Artefakty i skrypt: `.scratch/stmdomains-class-names/`.

Testy celowane: **40 PASS / 20,59 s**, mypy **115 modułów PASS**.
Pełna regresja po poprawce: **600 PASS / 274,03 s** (netcat/offscreen).
Pierwszy przebieg w sandboxie zakończył się SIGTERM bez raportu błędu testu;
powtórzony poza sandboxem przeszedł w całości. Log w katalogu artefaktów.
16 zmienionych plików kodu/testów, maksimum **341 linii**, wszystkie <1000.
Sprawdzono 546 odnośników w 7 dokumentach, graf 27 ticketów i `git diff --check`.
Nie dodano zależności ani zmian współdzielonych. Diagnostyczne pliki lokalne
pozostają w `.scratch/`; bez instrumentacji w kodzie aplikacji.

**Odbiór użytkownika 23 potwierdzony 2026-11-09 dla wersji `14f39d6` („testy manualne ok”).** Następny 23a → 24 → 25 → 26;
19–20 odłożone. Korekty ręczne nadal tylko w sesji; ta poprawka nie dodaje
zapisu/eksportu korekt planowanych w 24/25.

---

# STM Domains — wykonano SD-V4-23, ręczne klasy

2026-11-09. Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź
`domains/interactive-v04-ui`, baza `09d8001`. Implementacja **`94d5a94`**,
poprawka **`b11d09a`**. Status `done`;
**odbiór ręczny użytkownika 23 potwierdzony 2026-11-09 dla wersji `14f39d6` („testy manualne ok”)**.
[Obsługa, semantyka list i test ręczny](implementation/interactive-v04/acceptance-23.md),
[przegląd](implementation/interactive-v04/review-23.md).

**Edytuj domeny → Klasy ręczne…** otwiera niemodalne okno. Pusta klasa,
nazwa/kolor, przypisanie istniejącej lub utworzenie z przypisaniem,
usunięcie wyłącznie pustej ręcznej klasy. Wybór molekuł lub całych domen;
zmiana klasy części domeny pokazuje podział z 22 w jednym kroku historii.
Klasa punktu bez domeny nie tworzy obszaru; widok Klasy liczy go osobno.
Wspólna klasa kilku domen zachowuje ich ID i geometrię.

Listy mają stabilne UUID, niezmienne wersje i źródło. Metadane wspólne
wyłącznie w swoim katalogu; przypisania bieżącej klatki. Bez analizy
osobna lista bez modelu; lokalne wyniki bez katalogu mają własne listy.
UI pokazuje zakres, wersję, K modelu, klasy ręczne i obecne na klatce.
Nowe dopasowanie nie rozpoznaje ręcznych klas i nie usuwa wcześniejszych
korekt. Model, centroidy, K oraz automatyczne wyniki pozostają bez zmian.
Chronologiczne Cofnij/Ponów obejmuje listę i przypisania. Zapis/eksport
pozostają blokowane dla korekt; 24/25 dodadzą trwałość. Źródła tylko odczytano.

Natywne Qt/X11 w **netcat**, główne okno 1024×768, klasy 620×680:
kontrola K2 (357/405, 17 domen) i TTMAPP259–260 ze wspólnym K5
(259: 116/312, 7 domen) PASS. Wspólna ręczna klasa dwóch domen zachowuje
maskę; częściowe przypisanie tworzy jeden cofany podział; punkt bez domeny
otrzymuje samą klasę. Metadane wspólne, przypisania osobne, porównanie,
Cofnij/Ponów, raw/aligned i osobna lista bez modelu PASS. Obejrzano zrzuty.
To sprawdzenie autora, nie odbiór użytkownika ani ocena detekcji.

Testy celowane po poprawce nawigacji: **16 testów UI PASS / 17,14 s**;
mypy **114 modułów PASS**. Pełna regresja po poprawce `b11d09a`:
**596 testów PASS / 272,59 s**.
Standards: 1 uwaga heurystyczna zamknięta wydzieleniem zapytań o listę;
Spec: niezależnie 0 uwag, root wykrył błąd nadpisania legendy po nawigacji,
potwierdził testem RED i usunął, przygotowując wariant przed publikacją
klatki. Ponowny przegląd `b11d09a`: **0 otwartych uwag w obu osiach**.
11 plików kodu/testów, maksimum **875 linii**, wszystkie <1000.
Sprawdzono 543 odnośniki w 8 dokumentach, graf 27 ticketów i diff.

Artefakty lokalne: `.scratch/stmdomains-ui-23/` (skrypt, zrzuty, raport,
syntetyczne wejścia generatora `class_discovery_demo`). Instrukcja użycia
przykładu znajduje się w raporcie odbioru. Bez nowych zależności,
wspólnych zmian i potrzeb integracyjnych. Następny: **23a — scalanie
i dzielenie klas**, potem 24 → 25 → 26; 19–20 odłożone. Odbiór 22 potwierdzony.

---

# STM Domains — wykonano SD-V4-22, podział i scalanie domen

2026-11-09. Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź
`domains/interactive-v04-ui`, baza `128bcef`. Implementacja **`0910c97`**, poprawka **`62644eb`**.
Status `done`; **odbiór ręczny użytkownika 22 potwierdzony 2026-11-09 dla wersji `f37714f` („testy manualne ok”)**.
[Obsługa, reguła geometrii i test ręczny](implementation/interactive-v04/acceptance-22.md),
[przegląd](implementation/interactive-v04/review-22.md).

W istniejącym Panelu A dodano Podziel domenę i Połącz domeny. Podział
wydziela właściwy podzbiór i zachowuje ID reszty. Scalenie przyjmuje
reprezentantów domen, pokazuje wszystkich członków i wybór ID docelowego.
Podgląd, anulowanie, porównanie automatu i pojedynczy krok Cofnij/Ponów.
Podział zachowuje bieżącą klasę; scalenie różnych klas jawnie daje
nieustaloną. Historia łączy źródłowe/docelowe ID i składy. Kolejna analiza
zachowuje poprawiony wariant; pozostałe domeny i klatki są niezmienione.

Geometria 22 dziedziczy istniejące wsparcie. Podział rozdziela piksele
źródła między najbliższych jego członków, bez wzrostu obszaru. Scalenie
zachowuje dokładną sumę masek i wymaga jednej składowej 8-spójnej oraz
wsparcia każdego centrum we własnej masce. Brak obszaru lub przerwa
daje odmowę; bez mostów i wypełniania dziur. To reguła rastrowa,
nie fizyczny test ciągłości. Podział źródła bez maski pozostaje punktowy.
Korekty nadal tylko w pamięci sesji; zapis/eksport czeka na 24/25.
Ochrona niezapisanej pracy z 21 pozostaje aktywna.

Natywne Qt/X11 w **netcat**, 1024×768: kontrola 3 klatek z lasso,
podglądem/anulowaniem, konfliktem klas i przerwą PASS. TTMAPP259:
105/312, 5 domen; 4 członków z D2→D6 daje 6 domen; D2+D6→D2 odtwarza
dokładnie pierwotną maskę. Cofnij/Ponów, raw/aligned, porównanie i izolacja
260 PASS, brak błędów. Obejrzano zrzuty; podgląd/komunikat/przyciski są
poza przewijaną listą, aby ostrzeżenie było widoczne w małym oknie.
To sprawdzenie autora, nie odbiór użytkownika ani ocena skuteczności detekcji.

W **netcat**: pełna regresja **586 testów PASS / 263,36 s** dla implementacji,
po refaktorze **28 celowanych testów ręcznej edycji PASS / 6,09 s**,
mypy **112 modułów PASS**. Standards: 1 uwaga heurystyczna o powielaniu
podsumowania domen zamknięta wspólną funkcją; Spec: 0 uwag. Ponowny
przegląd `62644eb`: **0 otwartych uwag w obu osiach**. 7 plików kodu/testów,
maksimum **238 linii**, wszystkie <1000. Sprawdzono 531 odnośników
w 8 dokumentach, graf 27 ticketów i diff.
Przykład: `python -m stmdomains.tools.manual_partition_demo` w netcat,
potem otworzyć `.scratch/stmdomains-ui-22/demo/partition-controls.stmdomains`.
To kontrola z zadanymi domenami, nie wynik detektora. Wszystkie lokalne
artefakty 22 znajdują się w `.scratch/stmdomains-ui-22/`.
Bez nowych zależności, wspólnych zmian i potrzeb integracyjnych.
Następny: **23 — ręczne klasy**, potem 23a → 24 → 25 → 26; 19–20 odłożone.
Odbiór 21 i wcześniejszych wykonanych ticketów pozostaje potwierdzony.
Potwierdzenie odbioru 22 zmienia wyłącznie dokumentację; sprawdzono diff
i odnośniki, bez ponawiania testów kodu i GUI.

---

# STM Domains — wykonano SD-V4-21, Panel A

2026-11-05. Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź
`domains/interactive-v04-ui`, baza `4d32fbe`. Implementacja **`a61e1b2`**,
poprawki po przeglądzie **`47bafe0`**. Status `done`;
**Odbiór ręczny użytkownika 21 potwierdzony 2026-11-05 dla wersji `e58393c` („testy manualne ok”)**.
[Raport i test ręczny](implementation/interactive-v04/acceptance-21.md),
[przegląd](implementation/interactive-v04/review-21.md).

Panel A jest widoczny tylko po Edytuj domeny, a Zakończ edycję przywraca
miejsce obrazowi, pozostawiając korekty. Istniejące centra wybiera się
kliknięciami lub lassem. Nowa domena, dodawanie/usuwanie i jawne przenoszenie
mają podgląd oraz Zastosuj. Cofnij/Ponów zachowuje chronologię sesji,
wskazuje klatkę i do niej przechodzi. Automat, korekta i nowsze analizy
pozostają osobnymi wariantami; oryginalna tabela serii jest niezmieniona.
Własne klasy i podział/scalanie nie są częścią 21. Następny: **22**.
19–20 pozostają odłożone. Odbiór 18 pozostaje potwierdzony.

Korekty tylko w pamięci. Zapis/eksport są blokowane przy korektach lub
podglądzie, także w API; zamknięcie/zmiana danych pozwala anulować utratę.
Nie zmieniono formatów. Geometryczny obszar ręczny: ograniczone komórki
najbliższych centrów, 0,8 mediany NN, minimum 3 niewspółliniowych członków;
brak wsparcia pozostawia punkty. To przybliżenie członkostwa, nie test porządku.
Wyłączenia przestrzenne są sprawdzane także po wczesnej odmowie automatu.

Sprawdzenia w **netcat**: **572 testy PASS / 262,28 s**, mypy **110 modułów
PASS**, po poprawkach **17 celowanych testów PASS / 3,85 s**. Pierwsza pełna
regresja wykazała jeden kruchy test obrysu (569 PASS / 1 FAIL); zdiagnozowano
zaokrąglenie współrzędnych o 1 piksel i poprawiono tolerancję testu,
bez zmiany renderera. Dlatego ponowiono pełną regresję po poprawkach.
Natywne Qt/X11 na TTMAPP259–260, 1024×768: 8 kliknięć, 105→113 przypisań,
5→6 domen; lasso 3 centra, podgląd/anulowanie, zastosowanie, Cofnij/Ponów,
porównanie automatu, powrót do klatki, raw/aligned/zoom i anulowanie
zamknięcia PASS. Obejrzano zrzuty. To sprawdzenie autora, nie odbiór
użytkownika ani dowód skuteczności detekcji. Źródła odczytywane, bez ich edycji.

Przegląd Standards: 2 uwagi heurystyczne zamknięte, 0 twardych naruszeń;
Spec: 3 uwagi zamknięte (chronologia między klatkami, wyłączenia po odmowie,
etykieta freud). Ponowny przegląd: **0 otwartych uwag w obu osiach**.
16 zmienionych plików kodu/testów, maksimum **874 linie**, wszystkie <1000.
Raporty, zrzuty i przykłady: `.scratch/stmdomains-ui-21/`.
Bez nowych zależności, wspólnych zmian i nowych potrzeb integracyjnych.
Sprawdzono odnośniki dokumentacji, graf 27 ticketów i diff.
Dokumentacja implementacji: `e58393c`. Potwierdzenie odbioru 2026-11-05
zmienia wyłącznie dokumentację; sprawdzono diff, bez ponawiania testów kodu
i GUI. Następny rekomendowany ticket: **22 — dzielenie i scalanie domen**.

---

# STM Domains — propozycje UI SD-V4-21

2026-11-05, worktree `/home/rlew/projekty/NEtCAT-domains`.
[Podgląd, instrukcja i ograniczenia](implementation/interactive-v04/prototype-21-layouts.md).
A — panel boczny, B — pasek pod obrazem, C — karta na obrazie.
Autor rekomenduje A; **wybór użytkownika pozostaje otwarty**.
21 nadal `ready-for-agent`; odbiór 18 potwierdzony. 19–20 odłożone.

Źródło pierwotne: `prototype/stmdomains-manual-domains-ui`, **`f2db201`**,
baza `65b22f0`, katalog `stmdomains/ui/prototype_manual/`.
Wrócono na `domains/interactive-v04-ui`; tutaj tylko dokumentacja.
Nie scalać demo do aplikacji. Commit dokumentacji podany w odpowiedzi końcowej.

W **netcat**: `python .scratch/stmdomains-manual-ui/serve.py`.
Adres http://127.0.0.1:8879/?variant=A, także B/C; lokalnie również
samowystarczalny `prototype.html`. Rzeczywiste TTMAPP258–260 i centra,
zapisane bazowe przypisania 259 (105/312, 5 domen). Korekty wyłącznie
w pamięci, obszary poglądowe; bez zapisu korekt i nowych obliczeń metod.

Wykonano przejście GUI QtWebEngine/X11/netcat, A/B/C w 1440×1000 i 1024×768.
Obejrzano zrzuty; kliknięcia, lasso, suwak, raw/aligned/zoom, podgląd,
anulowanie, zastosowanie, przenoszenie, usuwanie, Cofnij/Ponów i izolacja
klatek PASS, brak błędów JS. To sprawdzenie autora, nie odbiór użytkownika.
Nie dodawano testów demo i nie powtarzano regresji aplikacji.
Artefakty `.scratch/stmdomains-manual-ui/`; maksymalny plik kodu 663 linie.
Sprawdzono odnośniki dokumentacji i diff. Brak nowych zależności,
wspólnych zmian i potrzeb integracyjnych z tego zadania.
Po wyborze układu zapisać decyzję w 21 i wdrożyć właściwe UI Qt.

---

# STM Domains — SD-V4-18, Panel A

2026-11-04, gałąź `domains/interactive-v04-ui`, poprawny worktree
`/home/rlew/projekty/NEtCAT-domains`, baza zadania `e4fb4aa`.
**Wykonano: `85a90e0`, poprawki `d7ea7b2`; status `done`, odbiór ręczny użytkownika 18 potwierdzony 2026-11-05 dla wersji `f2e0cbc` („testy manualne ok”).**
[Raport i test ręczny](implementation/interactive-v04/acceptance-18.md),
[protokół](implementation/interactive-v04/experiment-18.md).

Rzeczywisty EnvironmentCluster, osobny anulowalny proces, bez K i treningu.
Panel A w Analizie; ustawienia NN, sąsiedzi, obrót; Klasy i Domeny mają różne
mianowniki. Podgląd sąsiadów po kliknięciu, przełączanie trzech zachowanych
wyników, zapis/eksport jednego wyniku i oddzielnego szkicu. Wspólne pomiary
17/18 wydzielone; żadnych nowych modeli lub zmian w paczce v0.4.

Wykonano kontrole 1–9 oraz TTMAPP259–266 z trzema zamrożonymi tolerancjami;
natywne GUI X11/netcat, raw/aligned, okno 1024×768, eksport PNG, zapis/odczyt,
anulowanie i zamknięcie podczas pracy PASS. Źródła pozostały niezmienione.
To automatyzowane sprawdzenie GUI, **nie odbiór ręczny użytkownika**.
Wynik próby: brak wykazanej poprawy; domyślnie 173–196 klas i 0–25 molekuł
w domenach na TTMAPP. Skok fazy, braki i bariery pozostają problemem.
Lokalne artefakty: `.scratch/stmdomains-ui-18/`.

Środowisko **netcat**: dodano `freud-analysis==3.6.1`, `rowan==1.3.2`,
`parsnip-cif==1.0.0`, `more-itertools==11.2.1`; istniejące NumPy/SciPy bez zmiany.
**Potrzeba integracyjna:** odnotować opcjonalne freud-analysis w zarządzaniu
zależnościami STM Domains. Wspólnej konfiguracji tej sesji nie zmieniono.
Brak biblioteki nie blokuje pozostałych metod ani oglądania zapisanego wyniku.
Dalsza dostępna ścieżka: 21 → 22 → 23 → 23a → 24 → 25 → 26; 19–20 odłożone.
Sprawdzenia: **557 testów PASS / 256,20 s** na `85a90e0`, po poprawkach
**28 testów celowanych PASS / 27,84 s**, mypy **105 modułów PASS**.
Natywne GUI po poprawkach na klatce 259 ponownie PASS. Maksymalny plik
862 linie; wszystkie 23 zmienione pliki kodu/testów <1000, brak wyjątków.
[Przegląd](implementation/interactive-v04/review-18.md): doprecyzowano,
że rejestracja 3D freud dopuszcza obrót i **odbicie lustrzane** płaskich
otoczeń; test prawdziwej biblioteki potwierdza to przy progu 0,01.
Wydzielono wspólne pochodzenie wyników 17/18 i poprawiono utrzymanie
podglądu sąsiadów przy zmianie raw/aligned. Domyślne wyniki bez rejestracji
nie zmieniły się. Sprawdzenie linków i grafu 27 ticketów PASS.
Dokumentacja implementacji: `f2e0cbc`. Potwierdzenie odbioru 2026-11-05
zmienia wyłącznie dokumentację; sprawdzono diff, bez ponawiania testów kodu
i GUI. Następny rekomendowany ticket: **21 — ręczne tworzenie domen i zmiana składu**.

---

# STM Domains — propozycje UI SD-V4-18

2026-11-04. Użytkownik zlecił `prototype` dla metody freud.
[Podgląd, zakres i uruchomienie](implementation/interactive-v04/prototype-18-layouts.md).
A — wspólne okno Analiza, B — porównanie obok siebie,
C — stały panel otoczeń. Rekomendacja A; **wybór użytkownika otwarty**.
Ticket 18 nadal `ready-for-agent`, bez implementacji EnvironmentCluster.

Źródło pierwotne na `prototype/stmdomains-freud-ui`: **`d962b7d`**, baza
`97a60bd`, katalog `stmdomains/ui/prototype_freud/`. Po zapisaniu wrócono
na `domains/interactive-v04-ui` w tym samym worktree. Tu zmienia się tylko
dokumentacja; kod demo nie jest częścią aplikacji.

W **netcat**: `python .scratch/stmdomains-freud-ui/serve.py`.
Adres **http://127.0.0.1:8878/?variant=A**, również B/C. Samowystarczalny
HTML i kopia źródeł pozostają w `.scratch/stmdomains-freud-ui/`.
Rzeczywiste obrazy/centra TTMAPP258–260 i zapisane wyniki Bazowej/Geometrii
259. Wszystkie nowe wyniki freud, progi i postęp są demonstracyjne.
Podgląd sąsiadów nie jest obliczeniem freud. Skala parametrów jest propozycją
UI i wymaga weryfikacji przy implementacji 18.

Wykonane: QtWebEngine/X11 w netcat, A/B/C przy 1440×1000 i 1024×768;
zrzuty obejrzano. Przejście szkic → Analizuj, anulowanie, osobne klatki,
Klasy/Domeny, raw/aligned, wybór molekuły, rzeczywiste przeciąganie suwaka,
zoom, odmowy, klawiatura i stan prototypu; bez błędów JS.
Nie pisano testów demo ani nie powtarzano regresji produkcyjnej aplikacji.
Maksymalny plik kodu: 241 linii. Sprawdzono odnośniki i diff.
Brak zmian wspólnych i potrzeb integracyjnych. Dane tylko odczytane;
brak zapisu użytkownika, treningu i wysyłania pomiarów.

Po wyborze zapisać decyzję w 18 i wdrożyć właściwe UI Qt z obliczeniami;
nie scalać kodu prototypu. 17 pozostaje odebrany, 26 na końcu planu.
Commit dokumentacji podany w odpowiedzi końcowej. Poniżej historia.

---

# STM Domains — SD-V4-26 dodany na końcu planu

2026-11-04. Na polecenie użytkownika dodano
[26 — próbę level-set Gibou–Fedkiwa](implementation/interactive-v04/26-compare-fedkiw-level-set.md)
po 25. Status `ready-for-agent`; zależności 17, 13 i 14 są ukończone.
Zakres: jedna metoda na wspólnych cechach z geometrią, parametry w UI,
porównanie przypisań molekuł i obszarów domen, przeglądanie obliczonych
klatek, zapis/eksport oraz jawny test ręczny. Odbiór funkcji jest oddzielony
od wyniku badania; negatywny wynik próby jest dopuszczalny.

Gałąź `domains/interactive-v04-ui`, worktree `/home/rlew/projekty/NEtCAT-domains`,
baza `e3f9922`. Plan ma 27 ticketów; następny rekomendowany pozostaje 18.
Aktualizacja dotyczy wyłącznie dokumentacji, bez implementacji, instalacji
i nowych eksperymentów. Brak potrzebnych zmian wspólnych.
Sprawdzono odnośniki, identyfikatory i zależności planu oraz `git diff --check`.
Nie ponawiano testów programu ani GUI; instrukcja ręczna 26 dotyczy przyszłej
implementacji. Commit dokumentacji podany w odpowiedzi końcowej.

---

# STM Domains — przegląd Fedkiwa po tickecie 17

2026-11-04. Na pytanie użytkownika wykonano `research` i krytyczną ocenę
przydatności metod level set do domen STM.
[Źródła i wnioski](research-fedkiw-after-ticket-17.md).
Stan kodu audytowano na `a5229e4`, w tym samym worktree i gałęzi
`domains/interactive-v04-ui`. Właściwy Gibou–Fedkiw nie jest wdrożony;
historyczne próby pokrycia używały pokrewnego Chan–Vese. Aktywny plan
UI nie zawiera osobnego ticketu level set; 18 jest próbą freud.

To przegląd dokumentacji/kodu i źródeł pierwotnych, bez nowego benchmarku,
zmian aplikacji, zależności lub wspólnych modułów. Sprawdzono linki
lokalnej dokumentacji i diff; nie powtarzano testów programu.
Propozycja próby regularizacji na tych samych cechach nie jest decyzją
wdrożenia. Obowiązują ograniczenia odbioru naukowego z 17.
Użytkownik potwierdził odbiór ręczny 17; następny rekomendowany ticket
pozostaje 18. Poniżej stan implementacji i wcześniejsza historia.

---

# STM Domains — SD-V4-17, Panel A

2026-11-04. Użytkownik wybrał Panel A i zlecił `implement 17`.
Implementacja `25252b2`, poprawki `4c3f3c8`, na `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`; baza `7cf0922`. Status `done`,
**odbiór ręczny użytkownika 17 potwierdzony 2026-11-04 dla wersji `b58e69d`
(„testy manualn ok”)**. Brak potrzebnych zmian wspólnych.

Wspólne **Analiza → Metoda domen → Geometria** oblicza domeny bieżącej
klatki z pomiarów 16. Cztery parametry pomiarowe, odległość, wielkość
regionu i maska oraz istniejące bariery. Kontrola wszystkich par
pomiarów w regionie, osie modulo 180° i wspólne dopasowanie rodzin kąta
z rozstawem. Bez katalogu klas; typ nieznany. Karta C pozostaje dostępna.
Przełącznik nad obrazem zachowuje obie metody w sesji, zoom i klatkę.
Szkic nie zmienia wyniku, anulowanie pozostawia wcześniejsze przypisania.

Projekt/eksport zachowuje **jeden wybrany wynik**, parametry i pomiary
przy molekułach, jak dotychczasowy kontrakt 13/14; nie historię obu metod.
Po otwarciu zapisanego wyniku geometrycznego można obliczyć bazowy
bez utraty wczytanego wyniku geometrii. Źródła i ZIP pozostają niezmienione.

[Raport i manualne kroki](implementation/interactive-v04/acceptance-17.md),
[protokół ustalony przed próbą](implementation/interactive-v04/experiment-17.md),
[Standards/Spec](implementation/interactive-v04/review-17.md).
TTMAPP259–266: geometria 32–41 przypisań do jednej domeny; ścisły wariant
19–30, łagodny bez poprawy. Brak referencji oznacza brak oceny poprawności.
Kontrole: nadmierne podziały regularnej sieci przez bariery obrazu,
odmowy na luce/deformacji, niezaliczony skok fazy. Nie uznajemy tego
za gotowy detektor domen 2D. Wynik zerowy nie zalicza granicy fazy.

Wykonane: mypy 109 modułów; natywne Qt/X11 netcat na kontrolach 1–9 i
TTMAPP259–266, raw/aligned, zoom, karta C, 1024×768, anulowanie,
zapis/otwarcie oraz zamknięcie podczas zadania. SHA256 źródeł bez zmian,
0 odczytów historycznych paczek. Artefakty `.scratch/stmdomains-ui-17/`.
**543 testy PASS** po poprawkach: dwie rozłączne grupy 298 / 134,85 s
oraz 245 / 103,75 s, 78 plików. Przed przeglądem 542 PASS;
powtórzenie po zmianach zapisu i wspólnego rastra. Standards/Spec:
0 otwartych uwag. Kod/testy: 22 pliki poniżej 1000 linii,
maksimum 821 (limit 1500). Linki dokumentacji i graf 26 ticketów PASS.
Nieaktywne niepoprawne pola szkicu bazowego zachowywane niezależnie;
nie blokują zapisu geometrii, a po powrocie blokują tylko bazowe obliczenia.

Środowisko nadal **netcat**; interpreter:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Start: `python -m stmdomains.main`. Kontrole do otwarcia:
`.scratch/stmdomains-ui-17/demo/domain-geometry.moltrack.json`.
Następny rekomendowany ticket 18; ręczna edycja 21 dostępna niezależnie.
Potwierdzenie odbioru zapisano wyłącznie w dokumentacji; bez zmian kodu
i ponownego uruchamiania testów obliczeń. Nie kontynuowano innych ticketów. Poniżej historia.

---

# STM Domains — propozycje UI SD-V4-17

2026-11-04. Użytkownik zlecił `prototype` po omówieniu metody 17.
Trzy warianty: A — wspólne okno Analiza, B — dwa obrazy obok siebie,
C — stały panel parametrów. [Otwieranie i porównanie](implementation/interactive-v04/prototype-17-layouts.md),
[ticket 17](implementation/interactive-v04/17-segment-geometric-tolerances.md).
**Później użytkownik wybrał A i zlecił 17; status powyżej.** Rekomendacja A
nie jest decyzją. Nie rozpoczęto implementacji nowego algorytmu domen.
Pływająca karta C z odebranego 16 pozostaje dostępna w każdym wariancie.

Źródło pierwotne: gałąź `prototype/stmdomains-domain-method-ui`, commit
`621ce71`, baza `e5ba84b`, katalog `stmdomains/ui/prototype_domain_method/`.
Po zapisaniu źródła wrócono do `domains/interactive-v04-ui` w tym samym
worktree `/home/rlew/projekty/NEtCAT-domains`; na gałęzi implementacji
zmienia się tylko dokumentacja. Lokalna kopia i samowystarczalny HTML:
`.scratch/stmdomains-domain-method-ui/`. W netcat:
`python .scratch/stmdomains-domain-method-ui/serve.py`.
Adres `http://127.0.0.1:8877/?variant=A`; B/C na tej samej stronie.

Rzeczywiste obrazy i centra TTMAPP 258–260, bazowy zapis 259 z własnego
projektu 13 i pomiary 16. **Nowe przypisania geometryczne, powody decyzji
oraz obliczenia 17 są symulacją UI** — nie oceniać ich jakości naukowej.
Nie zapisuje projektów ani danych, nie trenuje, nie wysyła pomiarów.
Sprawdzono w QtWebEngine/X11 w netcat A/B/C przy 1440×1000 i 1024×768,
przepływ formularza i wyniku, anulowanie, stany klatek, zero/brak wyniku,
wybór molekuły, zoom, raw/aligned, kartę 16, klawiaturę i pełny stan.
Końcowo brak błędów JS; zrzuty obejrzano. Nie pisano testów prototypu
ani nie ponawiano regresji produkcyjnej aplikacji. Maksymalny plik kodu:
814 linii CSS. Sprawdzono odnośniki i `git diff --check`. Brak nowych
zależności, zmian współdzielonych i potrzeb integracyjnych.

Po wyborze zapisać decyzję w 17 i wdrożyć właściwe UI Qt wraz z metodą.
Commit aktualizacji dokumentacji podany w odpowiedzi końcowej.
Poniżej wcześniejszy odbiór 16 i historia etapów.

---

# STM Domains — potwierdzony ręczny odbiór SD-V4-16, karta C

2026-11-04. Baza `901e8d3`, implementacja `c4b6c70`, poprawki `009f38f`, `97988c2`.
Gałąź `domains/interactive-v04-ui`, worktree `/home/rlew/projekty/NEtCAT-domains`.
Użytkownik wybrał C; właściwe pomiary wdrożono w Qt, bez kodu ani
wartości demonstracyjnych z prototypu. Status `done`; **ręczny odbiór
użytkownika 16 potwierdzony 2026-11-04 dla wersji `420f196` („testy manualne ok”)**. Następny rekomendowany 17; 18 dostępny niezależnie.

Zapis potwierdzenia zmienia tylko dokumentację. Nie ponawiano testów
aplikacji ani GUI; poniżej zachowano wyniki weryfikacji implementacji.
Sprawdzono spójność planu, lokalne odnośniki i `git diff --check`.

**Analiza → Geometria… → Pomierz geometrię**. Karta na obrazie, ⇄,
Zwiń/Rozwiń, Molekuła/Domena, przewijanie i niezależne warstwy. Obliczenia
bieżącej klatki w tle, anulowanie, ochrona przed spóźnionym wynikiem.
Normalna/rzędy, 1/f, osobne skale X/Y, stabilność R±10%, osiowe podsumowanie
z rozrzutem i wsparciem. Bez osobnego pomiaru wzdłuż rzędów; brak ≠ 0.
Pomiary nie modyfikują przypisań domen. **Są sesyjne**; format projektu
oraz eksport 13/14 ich nie obejmują, co jest jawne w karcie.

[Raport i kroki ręczne](implementation/interactive-v04/acceptance-16.md),
[zamrożony protokół](implementation/interactive-v04/geometry-method-v1.md),
[przegląd Standards/Spec](implementation/interactive-v04/review-16.md).
Uruchomienie: `conda activate netcat`, `python -m stmdomains.main`.
Gotowe kontrole: `.scratch/stmdomains-ui-16/demo/geometry.moltrack.json`
oraz `anisotropic.moltrack.json`, z README. Generator:
`python -m stmdomains.tools.geometry_demo`. Bez nowych zależności.

**530 testów PASS** w 76 plikach (dwie rozłączne grupy 288/242),
mypy **101 modułów PASS**, wszystkie 18 zmienionych plików kodu/testów
poniżej 1000 linii (maks. 736). Natywne GUI X11 w netcat: dziewięć kontroli,
anizotropia, TTMAPP 259–266, oba widoki, zoom, zwijanie/przenoszenie,
małe okno, przewijanie, anulowanie i zamknięcie. Zrzuty obejrzane.
Wykryte przycięcie opisu poprawione; przełączniki kierunku i otoczenia
rozdzielone po review. Natywne sprawdzenie ujawniło też blokadę skanowania
bibliotek w threadpoolctl; `97988c2` zastępuje małe kontrakcje przez einsum
bez skanowania/pul BLAS. Test regresji i ponowione GUI PASS; matematyka
zweryfikowana w dodatkowym review. Standards/Spec: **0 otwartych uwag**.

TTMAPP259: 40 molekuł z dwoma stabilnymi kierunkami, 29 z jednym,
221 nierozstrzygniętych, 22 ze słabym wsparciem/pominiętych. Bazowe 105/312,
5 domen zachowane. Pozostałe 259–266 również bez zmiany przypisań;
nie jest to ocena poprawy detektora ani accuracy. Skala z nagłówka MPP:
3,90625 nm/px w obu osiach, bez walidacji metrologicznej. Nie wyciągać
wniosku o fizycznym rozmiarze molekuły bez potwierdzenia nagłówka.

Artefakty `.scratch/stmdomains-ui-16/` (report, logi, zrzuty, harnessy)
pozostają lokalne. Źródła MPP/JSON niezmienione, guard odczytów v0.4 czysty.
Brak zmian współdzielonych i potrzeb integracyjnych. Commit końcowej
aktualizacji dokumentacji podany w odpowiedzi końcowej.

---

# STM Domains — propozycje układu ticketu 16

Data **2026-11-04**. Użytkownik zlecił `prototype` dla sposobu pokazywania
pomiarów geometrii. Przygotowano A — panel boczny, B — tabelę pod obrazem,
C — pływającą kartę. [Opis i uruchomienie](implementation/interactive-v04/prototype-16-layouts.md),
[ticket 16](implementation/interactive-v04/16-inspect-local-geometry.md).
Historyczny stan po prototypie: wybór wtedy oczekiwał. Użytkownik później
wybrał C; aktualna implementacja i odbiór opisane powyżej.

Źródło pierwotne prototypu: `prototype/stmdomains-geometry-layouts`, commit
`2a31997`, katalog `stmdomains/ui/prototype_geometry/`, baza `41cc9e3`.
Po zapisaniu prototypu wrócono do `domains/interactive-v04-ui` w tym samym
worktree. Na gałęzi implementacji zmienia się tylko dokumentacja.
Lokalna kopia i samowystarczalny HTML: `.scratch/stmdomains-geometry-layouts/`.
Uruchomienie w `netcat`: `python .scratch/stmdomains-geometry-layouts/serve.py`.
Adres `http://127.0.0.1:8876/?variant=A`, warianty B/C na tej samej stronie.
HTML można też otworzyć bez serwera. Kod nie trafia do produkcyjnego UI.

Rzeczywiste obrazy/centra TTMAPP 258–260 i wynik domen 259 z projektu 13;
wszystkie wartości geometrii są jawnie demonstracyjne. Brak zapisu projektu,
treningu i wysyłania danych. Sprawdzono w QtWebEngine/X11 w `netcat` warianty
1440×1000 i 1024×768, interakcje, nierozstrzygnięcie, nawigację, raw/aligned,
zoom, kartę, przełącznik klawiatury i stan. Końcowy podgląd bez błędów JS;
zrzuty obejrzano. Nie pisano testów jednorazowego prototypu ani nie ponawiano
testów produkcyjnej aplikacji. Maksymalny plik kodu prototypu: 199 linii.
Sprawdzono dokumenty i `git diff --check`. Brak nowych zależności i potrzeb
integracyjnych. Commit aktualizacji dokumentacji podany w odpowiedzi końcowej.
Po wyborze należy zapisać decyzję w 16 i wdrożyć ją jako właściwe UI Qt.
Poniżej historia zakończonych implementacji i ich odbioru.

---

# STM Domains — potwierdzony ręczny odbiór SD-V4-15

Data **2026-11-03**, baza `bc3de1b`, implementacja `1b0c1de`, poprawki
`9fe24a6` i `9bf767a`. Gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. [Ticket 15](implementation/interactive-v04/15-advanced-descriptors-barriers.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-15.md),
[parametry](implementation/interactive-v04/advanced-settings.md),
[przegląd](implementation/interactive-v04/review-15.md).
Status `done`; **odbiór ręczny użytkownika 15 potwierdzony 2026-11-03 dla wersji `f129ac2` („testy manualne ok”)**. Odbiór 14 potwierdzony
w `bc3de1b`. Następny **16 — kierunek, rozstaw i jakość geometrii na obrazie**.

Zapis potwierdzenia zmienia wyłącznie dokumentację. Nie ponawiano testów
aplikacji ani GUI; poniżej zachowano wcześniejsze wyniki weryfikacji 15.
Sprawdzono odnośniki, spójność planu i `git diff --check`.

**Analiza → Analiza… → Zaawansowane** dodaje konfigurację sigma, histogramu,
zakresu par i maksimum PCA oraz sześć parametrów barier. Obliczenia używają
otwartych danych; opis należy do ID katalogu, a bariery do wyniku klatki.
Niezgodny opis przy istniejącym katalogu blokuje analizę. Zmiana barier
przy **Użyj istniejących klas** nie dopasowuje PCA/KMeans. Opcjonalna maska
pomarańczowa pokazuje bariery użyte do tworzenia domen, z poprawną geometrią
raw/aligned, porównaniem i eksportem PNG. Zapis zachowuje maskę i oddzielny
szkic; wcześniejsze projekty otwierają się bez wymyślania brakujących masek.

Wszystkie próby w `netcat`, bez instalacji i zmian wspólnych. TDD obejmuje
analizę, formularz, zapis i PNG. **510 testów PASS** w 71 plikach,
kontrola typów 92 modułów PASS, 32 zmienione pliki kodu/testów do 474 linii.
Pierwsza pełna regresja wykazała 1 błąd przy 509 PASS: zbyt słabą kontrolę
opisu przy odtwarzaniu dawnych decyzji domen. `9bf767a` wiąże kontrolę
z katalogiem; 26 testów obszaru PASS, następnie ponowiono pełny zestaw.
`9fe24a6` naprawił odrzucanie legalnej granicy odległości 0,2–0,3.
Standards/Spec: 0 otwartych uwag po recheckach.

Wykonano natywne GUI X11: TTMAPP klatka 259, K5 dopasowane na 259–268.
Bazowo 105/312, 5 domen, 691 pikseli barier. Sigma 1,7/PCA12: nowy katalog,
113/312, 6 domen. Zmiana barier zachowała katalog, dała 664 piksele barier.
Przywrócenie bazowych ustawień dało identyczne przypisania, ID oraz maskę.
Sprawdzono zapis/otwarcie z innym szkicem, PNG, anulowanie, błędne progi,
nawigację i zamknięcie. Syntetyczny dodatni skok: maska 29 448 → 0 pikseli,
przypisania 0/405 → 389/405 przy tym samym katalogu. To sprawdzenie wpływu
parametrów, nie dowód poprawy jakości. Brak odczytów paczki v0.4;
źródłowe MPP/JSON niezmienione. Artefakty w `.scratch/stmdomains-ui-15/`.

Nie wykonano nowej analizy wszystkich 268 klatek z niestandardowym opisem
ani walidacji naukowej względem referencji. Detektor nadal zakłada prawie
poziome granice jaśniejące w dół obrazu; parametry nie oznaczają kąta molekuły
ani uniwersalnej detekcji tarasów. Format 1 ma opcjonalny raster barier;
starsza aplikacja może odrzucić nowy zapis, bieżąca czyta starsze projekty.
Kontrola 461 lokalnych odnośników/kotwic w 11 dokumentach, 26 ticketów,
zgodności tabeli zależności i braku cykli PASS. `git diff --check` PASS. Brak potrzeb integracyjnych.
Commit dokumentacji podany w odpowiedzi końcowej. Poniżej historia.

---

# STM Domains — potwierdzony ręczny odbiór SD-V4-14

Data **2026-11-03**, baza `0288aa7`, implementacja `a20e14b`, poprawka
`361a7d0`. Gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. [Ticket 14](implementation/interactive-v04/14-export-csv-png.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-14.md),
[format eksportu](implementation/interactive-v04/export-format-v1.md),
[przegląd](implementation/interactive-v04/review-14.md).
Status `done`; **odbiór ręczny użytkownika 14 potwierdzony 2026-11-03 dla wersji `4e9f1d9` („testy manualne ok”)**.
Następny rekomendowany **15 — opis otoczenia i bariery obrazu**.
Plan nadal 26 ticketów; 01–03, 05, 05a, 06–14 wykonane,
15–18 i 21–25/23a gotowe po zależnościach, 19–20 odłożone.

Zapis potwierdzenia zmienia wyłącznie dokumentację. Nie ponawiano testów
aplikacji ani GUI; poniżej zachowano wcześniejsze wyniki weryfikacji 14.
Sprawdzono odnośniki, spójność planu i `git diff --check`.

**Plik → Eksportuj PNG/CSV…**: wyświetlany wynik, ostatni przebieg lub
same oznaczenia wejściowe; bieżąca klatka albo zakres; CSV/PNG niezależnie;
pełny obraz bieżącego widoku lub widoczny wycinek, szerokość obrazu.
Tabele klatek, molekuł, domen i klas zachowują ID, parametry wykonania,
przypisania i odmowy. JSON/README są dołączane automatycznie, manifest
zawiera wersję i SHA-256 części. Nie ma dopasowania ani uzupełniania braków.
Brak wyniku jest pustą wartością z jawnym statusem; obliczone zero pozostaje
zerem. Obszary masek są przybliżone w px², bez fałszywej kalibracji fizycznej.

PNG używa istniejącej sceny/kolorów, zachowuje gammę, raw/wyrównanie,
Klasy/Domeny/Wejściowe i warstwy. Wycięcie nie zmienia tabel ani mianowników.
Podpis i legenda pozostają poza obszarem nakładek. Oddzielna scena eksportu
nie zmienia bieżącego podglądu. IO pracuje w tle; ograniczona kolejka
przekazuje po jednej klatce do renderowania na wątku GUI. Anulowanie
kończy oczekiwanie bez potrzeby obsługi GUI podczas zamykania aplikacji.

Publikacja gotowego nowego podkatalogu po zakończeniu całości, bez nadpisania
istniejącej nazwy. Błąd/anulowanie przed publikacją usuwa tylko katalog
tymczasowy. Pełny projekt nadal zapisuje `.stmdomains`; eksport nie zawiera
źródłowego sygnału ani rastrów do odtworzenia analizy. Eksport przyszłych
ręcznych korekt pozostaje w 25. Brak zmian wspólnych modułów i potrzeb
integracyjnych; duże dane/wyniki pozostają lokalnie.

Środowisko **netcat**, bez instalacji. **499 testów PASS**.
Pierwszy pełny przebieg przerwany SIGTERM (143) po ~180 s, bez raportu
błędu asercji; przyczyna nieustalona. Ponowiono komplet 67 plików w dwóch
rozłącznych grupach: 230 PASS/101,44 s i 269 PASS/102,16 s.
Dziewięć nowych testów eksportu. Mypy w przyjętym zakresie aplikacji
**88 plików PASS**, **12 plików kodu/testów do 691 linii**, poniżej 1000/1500.
Jedno dodatkowe, szersze wywołanie mypy objęło historyczne eksperymenty
oraz wspólne importy i zgłosiło 125 błędów; nie jest zakresem tej implementacji.
Standards **0**; Spec **1 P2 poprawione, recheck 0 otwartych**.
Regresja: po analizie pojedynczej klatki i przejściu do innej domyślny eksport
zachowuje zakres wybranego przebiegu, zamiast eksportować bieżący brak wyniku.

**GUI X11 TTMAPP PASS, agent sterujący widocznym oknem:** K5 dopasowane
z 259–268, wynik 259: 105/312, 5 domen, katalog `9d3b7286`. Zakres 259–260
wyeksportowany w surowych Domenach, wyrównanych Klasach i jako wycinek przy
gammie 1,6. CSV identyczne między widokami, 260 nadal bez wyniku, maski bez
zmian; PCA/KMeans zakazane podczas eksportu. Kontrola zerowego wyniku K4
z minimalną domeną 500, anulowanie i błąd istniejącej nazwy PASS.
Wybrane PNG i dialog obejrzane; eksport dwóch klatek ~0,19–0,28 s,
484 pulsy GUI, największa przerwa ~0,20 s. Źródła MPP/JSON SHA-256 bez zmian.
Natywny recheck po poprawce: otwarty projekt z 13, po przejściu do 260
domyślny eksport ostatniego wyniku zapisuje 259, pozostawiając podgląd 260;
105 przypisań, kompletne metadane, bez dopasowania — PASS.
Dowody `.scratch/stmdomains-ui-14/`, bez dużych plików w Git.

441 lokalnych odnośników/kotwic w 9 dokumentach, zgodność 26 ticketów,
tabeli zależności i brak cykli PASS; `git diff --check` PASS.
Nie oceniano naukowej trafności domen ani eksportu pełnych 268 klatek
czy odporności na odcięcie zasilania. Po odbiorze agenta użytkownik
potwierdził testy manualne wersji `4e9f1d9`. Commit dokumentacji podany
w odpowiedzi końcowej.
Poniżej zachowano historię wcześniejszych przekazań.

---

# STM Domains — potwierdzony ręczny odbiór SD-V4-13

Data **2026-11-03**, baza `5b2ddc8`, implementacja `4f40c28`, poprawki
`1c9c221`. Gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. [Ticket 13](implementation/interactive-v04/13-save-open-project.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-13.md),
[format 1](implementation/interactive-v04/project-format-v1.md),
[przegląd](implementation/interactive-v04/review-13.md).
Status `done`; **odbiór ręczny użytkownika 13 potwierdzony 2026-11-03 dla wersji `21fd906` („testy manualne ok”)**.
Następny rekomendowany **14 — eksport PNG/CSV**. Plan nadal 26 ticketów;
01–03, 05, 05a, 06–13 wykonane, 14–18 i 21–25/23a gotowe po zależnościach,
19–20 odłożone. Ręczna edycja i jej historia pozostają w 21–24.

Zapis potwierdzenia zmienia wyłącznie dokumentację. Nie ponawiano testów
aplikacji ani GUI; poniżej zachowano wcześniejsze wyniki weryfikacji 13.
Sprawdzono odnośniki, spójność planu i `git diff --check`.

**Plik → Zapisz projekt… / Zapisz projekt jako…**, otwieranie `.stmdomains`
przez wspólny przycisk/menu. Samowystarczalny ZIP zawiera pełne bajty MPP,
oznaczenia, geometrię, widok, szkic oraz jeden wybrany przebieg lub brak
analizy. Stary wyświetlany wynik i ostatnia odmowa mogą być zapisane osobno.
Stan katalogu jest zapisany jako bezpieczne liczby/tablice JSON; otwarcie
nie dopasowuje modeli. Zapisany katalog można jawnie wykorzystać ponownie.
Kopia zachowuje ID analizy/katalogu; nowy przebieg otrzymuje nowe ID analizy.

Zapis w tle, postęp/anulowanie, atomowe zastąpienie po `fsync`, SHA-256 części
oraz kontrola niezmienności MPP od importu. Wadliwy projekt nie zastępuje
otwartej pracy. Save As potwierdza nadpisanie końcowej nazwy z rozszerzeniem.
Zamknięcie/otwarcie innej pracy chroni niezapisane zmiany: Zapisz/Odrzuć/Anuluj.
Częściowe wyniki zachowują stany i dostępność, bez zer zamiast braków.
Maski są wczytywane na żądanie, cache trzech wyników; walidacja nagłówków
oraz ID działa blokami bez materializacji całej serii masek. Czytnik MPP
nadal ładuje całą surową serię. Cache dyskowy znika wraz z ostatnim
użytkownikiem danych. Limity: 64 MiB/JSON, 16 GiB zawartości, 50 000 części.

Netcat bez instalacji. Pełny zestaw **490 testów PASS w 189,37 s**,
14 nowych testów projektu; uruchomiony raz na końcu po poprawkach.
Mypy **82 pliki PASS**;
**25 plików kodu/testów, maksimum 661 linii**, poniżej 1000/1500.
Standards **0**; Spec **2 P2 poprawione, recheck 0 otwartych**.

**GUI X11 TTMAPP PASS po poprawkach**: na 259 K5 dopasowane z 259–268,
105/312 i 5 domen, katalog `9d3b7286`. Otwarcie przy zakazie odczytu
oryginalnych MPP/JSON i zakazie PCA/KMeans zachowało dokładne przypisania,
maski, parametry, metadane i piksele; szkic K7, gamma 1,6, warstwy i zoom
wróciły oddzielnie. Kontynuacja z istniejącym katalogiem bez fitu PASS.
Save As, anulowanie zapisu, uszkodzony projekt i zakończenie pracowników PASS.
Zapis ~4,25 s, odczyt ~1,43 s, 142 121 164 B; źródła bez zmian.
Dowody lokalne `.scratch/stmdomains-ui-13/`, bez dużych danych w Git.

Odbiór GUI wykonał agent sterujący widocznym oknem; następnie użytkownik
potwierdził ręczny odbiór wersji `21fd906` słowami „testy manualne ok”. Nie oceniano jakości naukowej, pełnej analizy 268 klatek
ani odporności na odcięcie zasilania. Format zachowuje rzeczywiście dostępne
miary, nie deklaruje pełnego pokrycia/zwalidowanej powierzchni domen.
Kontrola 425 lokalnych odnośników/kotwic w 9 dokumentach, 26 ticketów,
zgodności tabeli zależności i braku cykli PASS; `git diff --check` PASS.
Brak zmian wspólnych modułów i potrzeb integracyjnych. Commit dokumentacji
podany w odpowiedzi końcowej. Poniżej historia wcześniejszych przekazań.

---

# STM Domains — potwierdzony ręczny odbiór SD-V4-12

Data **2026-11-03**, baza **`3297b98`**, implementacja **`274f348`**,
poprawka **`88006c1`**. Gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`.
[Ticket 12](implementation/interactive-v04/12-automatic-class-count.md),
[raport, kontrole i test ręczny](implementation/interactive-v04/acceptance-12.md),
[reguła Auto v1](implementation/interactive-v04/auto-class-count-rule.md).
Status `done`; **odbiór ręczny użytkownika potwierdzony 2026-11-03 dla
wersji `7edd8de`**, słowami „testy manualne ok”. Następny rekomendowany
**13 — zapis i otwarcie projektu**, jeszcze niewykonany.

Zapis potwierdzenia zmienia wyłącznie dokumentację. Nie ponawiano testów
aplikacji ani GUI; poniżej zachowano wcześniejsze wyniki weryfikacji 12.
Sprawdzono odnośniki i spójność planu oraz `git diff --check`.

**Analiza → Analiza… → Klasy**: ręczne K / Auto, maksimum 1–8, ranking i
uzasadnienie. Auto przechodzi przez lokalne/wspólne dopasowanie i segmentację,
z całym szkicem akceptacji, porządku i domen. K1 ma osobną regułę zwartości;
K≥2 wymaga silhouette i kontroli geometrii cech. Brak dopuszczalnego wariantu
jest nierozstrzygnięciem, bez katalogu/K5. Użycie istniejącego katalogu zachowuje
wybrane K i ranking bez ponownego fitu. Wyniki pozostają w pamięci do 13.
Odmowa zachowuje wcześniejszy kompletny wynik i oznacza go jako spoza przebiegu.

Reguła zapisana **przed TTMAPP**, bez późniejszego strojenia progów.
Kontrole: jedna sieć **K1 (117/121 w 1 domenie)**, dwie orientacje **K2
(234/242 w 12 domenach)**; szum/cztery centra/brak oznaczeń: odmowa.
Klas nie utożsamiamy z liczbą domen. TTMAPP **259 i 259–268 nierozstrzygnięte**:
159/312 i 1715/3054 użytecznych, ranking maks. 1200; silhouette maks.
0,368 / 0,335 poniżej progu 0,50, zbyt rozproszone grupy. Nie jest to
wynik 0% wykrywalności ani dowód braku domen. Ręczne K5 dla 259–268 nadal
na 259 daje **105/312, 5 domen**, katalog `9d3b7286`.

Netcat bez instalacji. **20 nowych testów**, kontrole przez obrazy MPP + JSON;
pełny zestaw **476 PASS w 173,61 s** po ponowieniu przerwanego procesu
(SIGTERM 143 bez raportu błędu asercji; przyczyna nieustalona).
Mypy **70 plików PASS**. Rzeczywiste GUI X11 kontrolne i TTMAPP PASS,
ranking/porównanie/nawigacja/anulowanie/zamykanie, brak odczytów dawnych modeli,
SHA-256 źródeł bez zmian; 0 aktywnych pracowników po zamknięciu.
Standards: 0 naruszeń, sugestia duplikacji uwzględniona, recheck 0 otwartych;
Spec: 0 otwartych uwag po poprawieniu jednej zbiorczej listy statusów.
17 plików kodu/testów, maksimum **302 linie**, poniżej 1000/1500.
409 lokalnych odnośników/kotwic w 8 dokumentach PASS, 26 ticketów,
zgodna tabela zależności, bez cykli; `git diff --check` PASS.

Kontrole do otwarcia: `.scratch/stmdomains-ui-12/demo/auto-controls.moltrack.json`;
generator `python -m stmdomains.tools.auto_classes_demo` w netcat.
Dowody lokalne `.scratch/stmdomains-ui-12/`, instrukcja w raporcie.
Nie wykonano oceny naukowej ani Auto dla pełnych 268 klatek TTMAPP;
ścieżka całej serii sprawdzona na kontrolach. Brak zmian współdzielonych
modułów i potrzeb integracyjnych. Commit dokumentacji podany w odpowiedzi
końcowej. Poniżej historia wcześniejszych przekazań.

---

# STM Domains — potwierdzony ręczny odbiór SD-V4-11

Data **2026-11-03**, wersja **`76c8284`**, gałąź `domains/interactive-v04-ui`,
worktree `/home/rlew/projekty/NEtCAT-domains`.
Użytkownik potwierdził: **„testy manualne 11 ok”**.
[Ticket 11](implementation/interactive-v04/11-unified-analysis-window.md)
jest wykonany i odebrany ręcznie; zaktualizowano
[raport odbioru](implementation/interactive-v04/acceptance-11.md), indeks,
mapę, instrukcje startowe i informację o zależności 12.

Następny rekomendowany ticket: **12 — Auto**, nadal niewykonany.
23a pozostaje zaplanowany po 23; plan ma 26 ticketów.
Zmiana wyłącznie dokumentacji; wcześniejsze 456 testów PASS i próby GUI
są zapisane w raporcie. Nie ponawiano testów aplikacji ani GUI.
`git diff --check` PASS. Commit zapisu potwierdzenia podano w odpowiedzi
końcowej. Poniżej historyczne przekazania sprzed tego odbioru.

---

# STM Domains — dodano SD-V4-23a: scalanie i dzielenie klas

Data **2026-11-03**, baza **`25c82bd`**, gałąź `domains/interactive-v04-ui`,
worktree `/home/rlew/projekty/NEtCAT-domains`.
Na polecenie użytkownika dodano [23a](implementation/interactive-v04/23a-split-merge-classes.md),
po 23. Status `ready-for-agent`; **bez implementacji**.

Zakres: Scal klasy do jednej źródłowej lub nowej klasy; Podziel klasę przez
jawne wskazanie członków; bieżąca klatka, zakres lub klatki tego wyniku
ze wspólną listą klas. Podgląd pokazuje wszystkie zmiany i pominięcia.
Scalenie klas zachowuje osobne domeny; podział części domeny używa reguł
22/23 i jest widoczny w podglądzie. Całość, także wieloklatkowa, jest jednym
atomowym krokiem Cofnij/Ponów. Model i bazowy wynik pozostają zachowane.
Brak automatycznego przenoszenia zaznaczeń i utożsamiania różnych katalogów.

Dodano ręczny test z małym przykładem o jawnych licznikach i próbą TTMAPP.
Wymagane netcat i limit 1000/1500 linii. 24 i 25 zależą teraz od 23a
(zamiast samego 23) oraz wymagają zapisu/eksportu scalenia i podziału klas.
25 nadal nie zależy od 24. Uzupełniono indeks, reguły edycji, 23, mapę
oraz instrukcje startowe. Ścieżka ręczna **21 → 22 → 23 → 23a → 24 → 25**.
Plan ma **26 ticketów**. Następny główny ticket pozostaje **12 — Auto**,
niewykonany; odbiór ręczny użytkownika 11 nadal oczekuje.

Zmiana wyłącznie dokumentacji; nie uruchamiano testów aplikacji ani GUI.
Sprawdzono **404 lokalne odnośniki z kotwicami w 9 dokumentach — PASS**,
26 unikalnych ticketów, zgodność zależności z indeksem i brak cykli.
`git diff --check` PASS. Commit tej zmiany podano w odpowiedzi końcowej.
Brak zmian kodu, danych, środowiska i potrzeb integracyjnych poza wcześniej
zapisanymi.

---

# STM Domains — wykonano SD-V4-11: wspólne okno analizy

Data **2026-11-03**, baza **`c60e7fb`**, implementacja **`d18048b`**.
Gałąź `domains/interactive-v04-ui`, worktree `/home/rlew/projekty/NEtCAT-domains`.
[Ticket 11](implementation/interactive-v04/11-unified-analysis-window.md),
[raport, gotowe przykłady i test ręczny](implementation/interactive-v04/acceptance-11.md).
Status `done`; **odbiór ręczny użytkownika oczekuje**. Następny ticket
**12 — Auto pozostaje niewykonany**. Jego zależności 07 i 11 są wdrożone.

**Analiza → Analiza…** i **Analizuj klatkę…** otwierają jedno niemodalne
okno z zakładkami Zakres, Klasy, Porządek i Domeny. Przycisk przy obrazie
wybiera bieżącą klatkę, a **Analizuj** w dialogu uruchamia obliczenia.
Usunięto pięć wcześniejszych formularzy. Jeden szkic przechowuje wszystkie
parametry, także akceptację klas stosowaną teraz do całej serii. Klasy
można dopasować z odrębnego zakresu albo jawnie wybrać istniejący katalog.
Lokalny katalog wymaga zgodnych danych jednej klatki; zakres/seria wymaga
wspólnego. Zmiana testu porządku przebudowuje kalibrację, a przy nowym
odkrywaniu wpływa też na wybór próbek. Samo strojenie istniejących klas
nie wykonuje fitu ani nie zmienia ich ID.

Szkic zostaje podczas nawigacji, zamknięcia dialogu i porównania wyników.
**Z wyświetlanego wyniku** kopiuje progi i wybiera jego katalog, zachowując
zakres analizy. **Przywróć bazowe parametry** zmienia tylko progi; klasy
i zakresy pozostają. Start utrwala niezmienny plan, nawigacja w trakcie
pracy nie przekierowuje obliczeń. Nowa seria resetuje szkic i katalog.
Tabela pokazuje stany klatek, dwuklik nawiguje, anulowanie zachowuje wyniki
ukończone i wcześniejsze; wyniki spoza przebiegu są jawnie opisane.

**Netcat:** `python -m stmdomains.main`. TTMAPP 259, K5 dopasowane na
259–268, margines 0,060, mnożnik 0,80, kwantyl 0,925, promień/sigma 3/(4/3),
minimum domeny 6, łączenie 1,80 × d: **111/312, 8 domen**, akceptacja
219/312, porządek 179/312. Katalog `cfc23500`. Zastosowanie do zakresu
259–268 odtwarza 259 identycznie, również maskę piksel w piksel.
Zmiana okna porządku na 2/1 daje 48/312, 3 domeny; bazowe progi przy
zachowanym katalogu dają 101/312, 5 domen. Liczniki nie są oceną trafności.

**Sprawdzenia agenta:** GUI X11 na rzeczywistych danych i kontrolach PASS;
przegląd `c60e7fb...d18048b`: **Standards 0, Spec 0**. Kontrole regularna,
losowa, rzędy i cztery centra: odpowiednio 117/121 (1 domena), 0/98,
0/94, 0/4. K1, brak oznaczeń, porównanie, raw/wyrównany, gamma, nawigacja,
anulowanie podczas dopasowania/serii i zamknięcie podczas pracy sprawdzone.
Końcowy układ: okno główne 900×650 oraz 1250×850; dialog 660×650 i 620×574,
z przewijaniem pól. Obejrzano zrzuty. Wszystkie trzy pule po zamknięciu puste.
Dopasowanie + klatka około 7,06 s, zakres 10 klatek około 6,80 s,
RSS około 698 MiB, największa przerwa timera 0,231 s. 0 odczytów starych
zasobów v0.4; hashe wejściowych MPP/JSON bez zmian. Pierwsza próba X11
w piaskownicy nie miała dostępu do ekranu; próba z dostępem do X11 PASS.

**456 testów PASS**, bez pominięć, 153,60 s; mypy 67 modułów PASS.
22 nowe/zmienione pliki kodu/testów, maksimum **575 linii**. Pierwszy pełny
przebieg: 455 PASS i 1 nieaktualny test warstw domen, oczekujący obliczeń
bezpośrednio po przycisku przy obrazie. Zaktualizowano go do nowej obsługi
okna; celowany test PASS, potem pełny zestaw PASS. Kod aplikacji nie
wymagał poprawki. Zachowano oba logi, recenzent potwierdził zmianę testu.
**393 lokalne odnośniki z kotwicami w 8 dokumentach PASS**, 25 ticketów,
zgodne zależności i brak cykli; `git diff --check` PASS. Jawne kopiowanie
ustawień z wyniku sprawdzono kontrolkami Qt offscreen; nie było osobnej
próby tej operacji w X11.

Artefakty poza Git: `.scratch/stmdomains-ui-11/` — logi, zrzuty, sondy GUI,
`demo/order-controls.moltrack.json` i `class-demo/pair_b.moltrack.json` z MPP.
Raport opisuje dokładne kroki i oczekiwane wyniki. Wyniki i szkic tylko
w pamięci; zapis 13, eksport 14 i ręczna edycja 21–25 pozostają do wykonania.
Plan ma 25 ticketów: 01–03, 05, 05a i 06–11 `done`, 12–18 i 21–25
`ready-for-agent`, 19–20 `deferred`. Odbiory naukowe pozostają odrębne.
Nie instalowano zależności, nie zmieniano danych ani modułów wspólnych;
dawne potrzeby integracyjne pozostają aktualne. Commit dokumentacji
odbioru podano w odpowiedzi końcowej.

---

# STM Domains — zaplanowano SD-V4-11: wspólne okno analizy

Data **2026-11-03**, baza **`3267207`**, gałąź `domains/interactive-v04-ui`,
worktree `/home/rlew/projekty/NEtCAT-domains`.
Na polecenie użytkownika dodano [ticket 11](implementation/interactive-v04/11-unified-analysis-window.md).
**12 — Auto nie jest wykonany**, zgodnie ze sprostowaniem użytkownika.
Nowa kolejność: **11 → 12**. Plan ma **25 ticketów**; 11 `ready-for-agent`,
po ukończonych 06, 08, 09 i 10. 12 wymaga teraz 07 i nowego 11.

11 dostarcza jedno niemodalne okno Analiza z zakładkami Zakres, Klasy,
Porządek i Domeny, jednym szkicem ustawień i przyciskiem Analizuj.
Zakres odkrywania klas jest oddzielny od zakresu obliczania domen.
Wszystkie ustawienia, w tym akceptacja klas, trafiają zarówno do klatki,
jak i serii. Użycie istniejącego katalogu pozostaje bez ponownego fitu;
nowe odkrywanie używa wybranych parametrów porządku. Jest postęp,
anulowanie, statusy klatek, porównanie i jawne kopiowanie ustawień z wyniku.
Przycisk przy obrazie otwiera to samo okno, zamiast uruchamiać odrębną
konfigurację. Po 11 przyszłe Auto z 12 pojawi się w zakładce Klasy.

Ticket opisuje zachowanie szkicu podczas nawigacji, porównania i zmiany
serii, ochronę wcześniejszych wyników oraz ręczny test klatka/seria
z konkretnym wspólnym zestawem parametrów. Wymaga netcat i limitu
1000/1500 linii. Nie wprowadza nowej metody, zapisu projektu, presetów,
eksportu ani ręcznej edycji. **Implementacji nie rozpoczęto**.

Poprzedni 11 był usunięty jako duplikat dopasowania z 05/07. Ponowne
użycie numeru dla nowego zakresu jest jawną decyzją użytkownika z tej sesji;
nie przywracamy starego zadania. Zaktualizowano indeks, zależności i zakres
12 oraz wskazania aktualnego planu. Statusy odebranych zadań i badań
pozostają zachowane. Brak zmian kodu, danych, środowiska i wspólnych modułów.
Sprawdzenia dokumentacji: **386 lokalnych odnośników z kotwicami w 7 dokumentach
PASS**, 25 unikalnych ticketów, zgodne zależności w plikach i indeksie oraz
brak cykli. `git diff --check` PASS. Testów aplikacji ani GUI nie uruchamiano
(zmiana wyłącznie dokumentacji). Commit planu podano w odpowiedzi końcowej.

---

# STM Domains — wykonano SD-V4-10: regulacja testu porządku

Data **2026-11-03**, baza **`3c09c0b`**, implementacja **`aa7e039`**.
Gałąź `domains/interactive-v04-ui`, worktree `/home/rlew/projekty/NEtCAT-domains`.
[Ticket](implementation/interactive-v04/10-tune-order-test.md),
[raport, przykłady i test ręczny](implementation/interactive-v04/acceptance-10.md).
Status `done`; **odbiór ręczny użytkownika 10 potwierdzony 2026-11-03**
dla wersji **`4b55727`** słowami „testy manualne ok”. Zapis potwierdzenia
zmienia wyłącznie dokumentację; `git diff --check` PASS, bez ponawiania
testów aplikacji. Commit zapisu podano w odpowiedzi końcowej.
Następny rekomendowany ticket: **12 — Auto**.

Menu **Analiza → Test porządku…** udostępnia kwantyl kontroli, minimum
punktów lokalnych i efektywnych, promień i sigmę w jednostkach odstępu
molekuł d. Jawny przycisk kalibruje kontrole dla aktualnych ustawień
w tle i przelicza klatkę przy zachowanych klasach, akceptacji i domenowych
ustawieniach. Jest porównanie poprzedni/nowy, przywracanie bazowych pól,
postęp i anulowanie. Dane oznaczenia wyjaśniają wsparcie, koherencję i próg.

Ponowne odkrywanie klas używa zastosowanego porządku do doboru próbek.
Przy starcie analizy serii ustawienia pochodzą z wyświetlanego wyniku
(lub są bazowe przy jego braku) i są jawnie opisane w oknie. Wynik zapisuje
konfigurację, ziarno, kontrolne liczności, kalibrację, skalę i źródło.
Brak cache progów: pełna analiza generuje kontrole ponownie; samo strojenie
domen zachowuje oceny porządku. Strojenie nie zmienia tożsamości katalogu.
Nowo dopasowane katalogi mogą mieć inne ID niż w 09 z powodu rozdzielenia
parametrów stosowania modelu od pochodzenia doboru próbek.

Uruchomienie w **netcat**: `python -m stmdomains.main`. Dla TTMAPP 259,
**lokalnego K5 z bieżącej klatki** i bazowych domen/akceptacji:

| Kwantyl | Promień / sigma [× d] | Porządek | Przypisania do domen |
| --- | --- | --- | --- |
| 0,950 | 3 / 4⁄3 | 159/312 | 120/312, 6 domen |
| 0,925 | 3 / 4⁄3 | 179/312 | 134/312, 7 domen |
| 0,925 | 2 / 1 | 77/312 | 47/312, 2 domeny |

Powrót do bazowych ustawień odtwarza przypisania i mapę piksel w piksel.
Akceptacja klas w trzech wariantach pozostaje 274/312. To test regulacji,
nie potwierdzenie lepszej trafności domen.

**Sprawdzenia:** 22 nowe przypadki PASS i 58 celowanych regresji PASS;
TDD na obliczeniach, doborze próbek, UI i przekazaniu konfiguracji do serii.
Mypy **67 modułów PASS**, **22 pliki kodu/testów, maksimum 566 linii**.
Code-review `3c09c0b...aa7e039`: **Standards 0, Spec 0**, brak otwartych uwag.
Po review rozsunięto cztery centra przykładu, aby były osobno widoczne;
celowana próba GUI PASS. Pełny zestaw po review: **449 passed, bez pominięć,
139,80 s**. Pierwsza próba przerwana sygnałem (kod 143), bez błędu testu;
przyczyny sygnału nie ustalono. Kompletny ponowiony przebieg PASS;
oba logi zachowane. **376 lokalnych odnośników z kotwicami w 7 dokumentach
PASS**, 24 tickety, `git diff --check` PASS.

Rzeczywiste **GUI X11 PASS**: TTMAPP, porównanie, szczegóły, raw/wyrównany,
gamma, okna 900×650 i 1250×850, anulowanie, nawigacja, kontrolne serie
regularna/losowa/rzędy/cztery centra, wyjście podczas pracy. Obejrzano
zrzuty okna parametrów, szczegółów i obrazów. Przeliczanie około 0,4–0,7 s,
RSS około 621 MiB, największa przerwa timera 0,235 s; trzy pule kończą
z 0 aktywnych zadań. Blokada fit PCA/KMeans nie została wyzwolona.
0 odczytów historycznych zasobów v0.4; MPP/JSON niezmienione według SHA-256.

Artefakty poza Git: `.scratch/stmdomains-ui-10/`, w tym logi i PNG oraz
gotowe `demo/order-controls.moltrack.json` z MPP. Generator:
`python -m stmdomains.tools.order_demo --output .scratch/stmdomains-ui-10/demo`.
Instrukcja opisuje K1 dopasowane na pierwszej kontroli i ocenę wszystkich
czterech klatek. Rzędy mogą przejść test periodyczności bez dowodu sieci 2D.
Zerowe domeny na losowej kontroli/rzędach obejmują też odmowę klasy, więc
nie są samodzielnym sprawdzianem poprawności testu porządku.

Ograniczenia: metoda zachowuje bazowe kotwice efektywnego wsparcia i stałą
rodzinę kontroli, z interpolacją i progiem skrajnym poza kotwicami. Kwantyl
nie jest prawdopodobieństwem poprawności domeny. Przy braku kontroli
kalibracja zgłasza błąd i zachowuje poprzedni wynik. Brak nowych zależności,
zmian wspólnego kodu, danych i środowiska. Dawne potrzeby integracyjne
pozostają aktualne. Wyniki są w pamięci; zapis 13 i eksport 14 nadal
przed nami. Plan ma 24 tickety: 01–03, 05, 05a i 06–10 `done`,
12–18 i 21–25 gotowe po zależnościach, 19–20 odroczone. Odbiór naukowy
metody i historyczne badawcze 04/13 pozostają odrębne.

---

# STM Domains — wykonano SD-V4-09: akceptacja klasy i przyczyny odmowy

Data **2026-11-03**, baza **`b34e862`**, implementacja **`494ab9d`**.
Gałąź `domains/interactive-v04-ui`, worktree `/home/rlew/projekty/NEtCAT-domains`.
[Ticket](implementation/interactive-v04/09-tune-class-acceptance.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-09.md).
Status `done`; **odbiór ręczny użytkownika 09 potwierdzony 2026-11-03**
dla wersji **`9dd934d`** słowami „testy manualne ok”. Commit zapisu
potwierdzenia podano w odpowiedzi końcowej. Następny rekomendowany ticket
pozostaje **12 — Auto**.

Po odbiorze użytkownik zgłosił `inotify_add_watch(...) failed: (No space
left on device)` i potwierdził, że program zamknął się normalnie.
Minimalna próba systemowego `inotify_add_watch`, bez STM Domains, odtwarza
`ENOSPC` dla IBus, `/tmp` i repozytorium. Limit użytkownika wynosi 65 536;
trzy procesy `code` mają łącznie 64 600 wpisów obserwacji. Dysk ma około
2,3 TB wolnego miejsca, i-węzły i pamięć są dostępne. To problem limitu
systemowego, nie odtworzony crash aplikacji. [Szczegóły i zalecenie](implementation/interactive-v04/acceptance-09.md#komunikat-inotify-po-odbiorze).
Nie zmieniano limitów, nie kończono procesów ani nie instalowano pakietów;
usunięcie komunikatu po zwiększeniu limitu pozostaje do sprawdzenia.
Ta aktualizacja obejmuje wyłącznie dokumentację: `git diff --check` PASS,
bez ponawiania testów aplikacji. Lokalna sonda w
`.scratch/stmdomains-inotify-diagnosis/probe.py` pozostaje poza Git.

Menu **Analiza → Akceptacja klasy…** ma dwa progi: minimalny margines
(bazowo 0,075) i mnożnik promienia (1,10). Przeliczenie bieżącej klatki
zachowuje wyświetlany katalog i parametry domen. Działa poprzedni/nowy,
przywrócenie pól bazowych, anulowanie i zachowanie wyniku przy błędzie.
K1 używa promienia i dostępności opisu, bez marginesu drugiej klasy.
**Dane oznaczenia…** pokazują najpierw czytelny opis klasy wstępnej,
akceptacji, testu porządku i domeny, a niżej dotychczasowe metadane.

Uruchomienie w **netcat**: `python -m stmdomains.main`. Na TTMAPP 259
przy K5 z zakresu 259–268, bazowych domenach i progach: **272/312**
zaakceptowane klasy, **105 molekuł w 5 domenach**. Margines 0,06:
**281/312** i nadal **105/312, 5 domen**. Margines 0,06 / mnożnik 0,80:
**236/312** oraz **81/312, 4 domeny**. Powrót do 0,075 / 1,10 odtwarza
bazowe przypisania i mapę piksel w piksel. To kontrola sterowania,
nie ocena trafności detekcji.

**Sprawdzenia:**

- 18 nowych przypadków PASS i celowane regresje; TDD dla obliczeń,
  kontrolki UI, szczegółów i zachowania progów przy ponownej analizie.
- Pełny zestaw raz na koniec po review: **427 passed, bez pominięć, 111,88 s**.
- Mypy **63 moduły PASS**, **15 plików kodu/testów, maksimum 544 linii**.
- Code-review `b34e862...494ab9d`: **Standards 0, Spec 0**, brak otwartych uwag.
- Rzeczywiste **GUI X11/xcb PASS**: TTMAPP 259, K1, porównanie, szczegóły,
  raw/aligned, gamma, stabilny układ w 900×650 i 1250×850, anulowanie,
  nawigacja, brak danych oraz zamknięcie podczas pracy. Obejrzano sześć PNG.
- Przeliczenie TTMAPP około **0,70–0,71 s**, K1 **0,58 s**. RSS **631,90 MiB**,
  największa przerwa timera **0,228 s**; trzy pule zakończone przy wyjściu.
- Podczas strojenia wymuszona odmowa wywołań fit PCA/KMeans nie została
  wyzwolona. **0 odczytów historycznych paczek/modeli**, MPP/JSON niezmienione
  według SHA-256. Hashe i polecenia są w raporcie.
- **365 lokalnych odnośników z kotwicami w 7 dokumentach PASS**;
  24 tickety, zgodne zależności i brak cykli. `git diff --check` PASS.

Artefakty `.scratch/stmdomains-ui-09/` poza Git: demo, GUI, log pełnych testów
i zrzuty. Pierwsza próba X11 w piaskownicy nie miała dostępu do ekranu;
ten sam test przeszedł po udostępnieniu lokalnego DISPLAY. Nie instalowano
pakietów. Bez zmian wspólnych, danych i środowiska; dotychczasowe zgłoszenia
zależności do integratora pozostają aktualne.

Ograniczenia: 09 stroi jedną klatkę. Strojenie domen i Analizuj klatkę
zachowują zastosowane progi; jawne odkrywanie nowego katalogu w 07 i nowa
analiza serii w 08 używają bazowej akceptacji. Progi nie są częścią tożsamości
dopasowania; nowe katalogi mogą mieć inny hash niż w 08 przy tych samych
klasach bazowych, ale strojenie go nie zmienia. Wyniki są tylko w pamięci,
do dwóch wersji na klatkę; zapis 13 i eksport 14 pozostają do wykonania.
09 nie dodaje Auto, ręcznej edycji ani potwierdzenia fizycznych typów.
Plan nadal ma 24 tickety; 01–03, 05, 05a i 06–09 `done`, 19–20 odroczone.
Historyczne badawcze 04/13 i odbiór naukowy metody pozostają odrębne.

---

# STM Domains — plan ręcznej edycji klas i domen: SD-V4-21–25

Data **2026-11-03**, baza **`02a54d4`**, gałąź `domains/interactive-v04-ui`,
worktree `/home/rlew/projekty/NEtCAT-domains`. Na polecenie użytkownika
dopisano pięć osobnych zadań do [aktualnego planu](implementation/interactive-v04/README.md#edycja-ręczna-klas-i-domen):

- [21 — tworzenie i rozszerzanie domen](implementation/interactive-v04/21-manual-domain-membership.md),
  z selekcją kliknięciami/lassem, usuwaniem członków i Cofnij/Ponów;
- [22 — podział i łączenie domen](implementation/interactive-v04/22-split-merge-domains.md);
- [23 — własne klasy i ręczne przypisania](implementation/interactive-v04/23-manual-classes.md);
- [24 — zapis korekt i historii w projekcie](implementation/interactive-v04/24-save-manual-corrections.md);
- [25 — eksport poprawionego wyniku](implementation/interactive-v04/25-export-manual-corrections.md).

Każdy ticket ma kryteria akceptacji i scenariusz ręcznego testu w działającej
aplikacji. Statusy `ready-for-agent` oznaczają przygotowany zakres, nie
ukończone zależności. **Żadnej nowej funkcji nie implementowano.** Plan ma
**24 tickety**; 01–03, 05, 05a i 06–08 pozostają `done`, 19–20 `deferred`.
Główna rekomendacja po odebranym 08 pozostaje **12 — Auto**. Edycję można
zacząć od 21 po wykonanym 05a; dalej 22 → 23, z wykonanym 07 wymaganym
dla klas. 24 wymaga również 13, a 25 również 14; 25 nie jest blokowany przez 24.

Korekty dotyczą istniejących oznaczeń jednej klatki i konkretnego wyniku.
Można pracować bez wyniku automatycznego; jego brak pozostaje jawny.
Klasa może obejmować kilka domen, a ręczne klasy nie zmieniają dopasowanego
modelu ani nie propagują się automatycznie na serię. Ręczny wariant,
oryginalny automat i historia są rozróżnione; ponowna analiza nie nadpisuje
poprawionej pracy. 24 rozszerza trwałość z 13, 25 eksport z 14. Wspólny
indeks określa zachowanie zapisu/eksportu, gdy edytor jest wdrożony wcześniej.
Do czasu 24 korekty są tylko w sesji, z ochroną przed ich nieświadomą utratą.

Nowy zakres rozszerza dawne ograniczenie do rozstrzygania konfliktów;
historycznych ticketów badawczych i ich statusów nie zmieniano. Nie obejmuje
nowych detekcji molekuł, swobodnego malowania granic, śledzenia ani uczenia
z przykładów. Limity kodu/testów 1000/1500 linii i środowisko **netcat**
obowiązują w każdym zadaniu. Nie zmieniono kodu, danych ani środowiska;
brak nowych potrzeb integracyjnych.

Weryfikacja w netcat: **379 lokalnych odnośników wraz z kotwicami w 12
zmienionych dokumentach PASS**; **24 unikalne tickety**, zgodność zależności
w plikach i tabeli oraz brak cykli PASS. Pięć nowych zadań ma kryteria
akceptacji, test ręczny, netcat i limit 1000/1500. `git diff --check` PASS.
Nie uruchamiano testów aplikacji ani GUI: zmieniono wyłącznie dokumentację.
Commit przekazania podano w odpowiedzi końcowej.

---

# STM Domains — wykonano SD-V4-08: domeny na zakresie lub całej serii

Ukończono **2026-11-03**. Baza **`e51b612`**, implementacja **`1c39ae2`**,
poprawka **`46c274f`**, gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. [Ticket](implementation/interactive-v04/08-analyze-series.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-08.md).
Status `done`; **odbiór ręczny użytkownika 08 potwierdzony 2026-11-03**
dla wersji **`a3a5316`** słowami „testy manualne ok”. Zapis potwierdzenia
zmienia wyłącznie dokumentację; `git diff --check` PASS, bez ponawiania
testów kodu. Commit zapisu podano w odpowiedzi końcowej.
Następny rekomendowany ticket: **12 — automatyczny wybór liczby klas**.

Menu **Analiza → Analiza serii…** otwiera niemodalne okno z zakładkami
**Zakres i klasy** oraz **Tworzenie domen**. Jeden przycisk stosuje oba
zestawy ustawień: dopasowuje wspólny katalog i oblicza domeny wszystkich
wybranych klatek. Można wskazać osobny zakres dopasowania lub użyć aktywnego
wspólnego katalogu z 07 bez ponownego fitu. Pola nieaktywnego zakresu
pokazują faktyczne dane dopasowania. Osobne strojenie 06 pozostaje dostępne.

Tabela pokazuje postęp, wyniki, brak oznaczeń, odmowę, błąd albo niewykonane
klatki; dwuklik przechodzi do obrazu. Podczas pracy można nawigować.
Anulowanie dopasowania zachowuje wcześniejszy katalog; anulowanie analizy
pozostawia ukończone wyniki. Stare wyniki niewykonanych klatek nie są
uznawane za nowe: stopka pokazuje, że pochodzą spoza przebiegu.
Wyniki mają wspólne klasy i lokalne numery domen; bez śledzenia w czasie.

Uruchomienie w **netcat**: `python -m stmdomains.main`. Otwórz
`data/TTMAPP/detection_full.moltrack.json`, wybierz w oknie serii **259–268,
K5, Ten sam zakres co analiza**, bazowe domeny. Wynik 259: **105/312,
5 domen**; 268: **119/308, 4**. Dla **250–268, K8, minimum 6, łączenie 1,80**
wynik 268 to **131/308, 6 domen**. Oznaczenia są dostępne na każdej klatce
przebiegu. Parametry domen można skopiować z zastosowanego wyniku lub
ustawić bezpośrednio w oknie serii; szkic drugiego okna nie jest przejmowany.

**Wykonane sprawdzenia:**

- 13 nowych przypadków oraz celowane regresje PASS. Pełny zestaw uruchomiony
  raz po przeglądzie/poprawce: **409 passed, bez pominięć, 95,15 s**.
- Mypy **59 modułów PASS**. Kod/testy: **14 plików, maksimum 527 linii**.
- `git diff --check` i **341 lokalnych ścieżek odnośników w 7 dokumentach PASS**.
- Code-review `e51b612...1c39ae2`: **Standards 1 P2**, poprawiona w `46c274f`
  i potwierdzona przez recenzenta; **Spec 0 uwag**, 0 otwartych. Indywidualne
  strojenie usuwa teraz z nowego wyniku znacznik przynależności do przebiegu,
  zachowując oryginalny wynik/tabelę i prawidłową stopkę przy porównaniu.
- Rzeczywiste GUI **X11/xcb sterowane Qt PASS**: 259–268 K5 (**13,00 s**),
  250–268 K8 z minimum 6 i łączeniem 1,80 (**24,73 s**), niezależny zakres
  dopasowania, zastosowanie istniejącego katalogu do **268/268 klatek
  bez błędów — 167,67 s**. Zgodność z pojedynczą analizą potwierdzona.
- Anulowanie zachowało **2 ukończone klatki**, nawigacja nie pomieszała
  wyników. Gamma/raw/aligned i układ 900×650 PASS. Ponowne otwarcie serii
  czyści stan. Zamknięcie podczas fitu: kod 0 i **trzy pule zakończone**.
- Demo w GUI: pozytywny wynik i brak oznaczeń; odmowa K8 sprawdzona
  testem kontrolera Qt offscreen. Końcowa próba GUI
  sprawdziła pola zakresu, dwuklik w tabeli i indywidualne strojenie
  **357 → 231** przypisań przy zachowanym wyniku serii. Obejrzano zrzuty.
- Źródłowe JSON/MPP niezmienione (SHA-256 przed/po), **0 odczytów paczek
  lub dawnych modeli/wyników**. Szczyt RSS **866 MiB**, przerwa timera
  **0,237 s**, cache obrazów przy przejściach **2350080 B** (limit 32 MiB).

Artefakty `.scratch/stmdomains-ui-08/` poza Git, w tym pełny log pytest,
raporty GUI i demo. Nie instalowano pakietów; użyto wskazanego **netcat**.
Bez nowych zmian wspólnych — zależności zgłoszone w 05 nadal aktualne.
Wyniki i modele są tylko w pamięci: do dwóch wersji/klatkę i tabela
ostatniego przebiegu. Jeden katalog/metadane są współdzielone, kolejka
przetwarza po jednym wyniku. Limity i zastrzeżenia metody z 07 pozostają;
liczniki nie są pomiarem trafności detektora. Zapis projektu to 13, eksport 14.

**Plan nadal ma 19 ticketów; 01–03, 05, 05a i 06–08 done. Następny: 12 — Auto.**
12 nie rozpoczęto. 19–20 pozostają odroczone; historyczne badawcze 04/13
i odbiór metody są odrębne. Poniżej historia wcześniejszych etapów.

---

# STM Domains — wykonano SD-V4-07: liczba klas i zakres dopasowania

Data **2026-11-02**, baza **`eebbfbd`**, implementacja **`dedd8b8`**, poprawki
**`65e9d2a`**. Gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. [Ticket](implementation/interactive-v04/07-fit-shared-classes.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-07.md).
Status `done`; **odbiór ręczny użytkownika 07 potwierdzony 2026-11-02**
dla wersji **`7f79362`** słowami „testy manualne ok”. Zapis potwierdzenia
zmienia wyłącznie dokumentację; `git diff --check` PASS, bez ponawiania
testów kodu. Commit zapisu podano w odpowiedzi końcowej.
Następny ticket: **08 — analiza zakresu lub całej serii**.

Menu **Analiza → Klasy i zakres…** otwiera małe niemodalne okno K1–8,
bieżącej klatki / zakresu / całej serii i przycisku dopasowania. Pola
zmieniają szkic; obliczenie tworzy katalog i wynik domen bieżącej klatki.
Pozostałe klatki mają jawny status wcześniejszego katalogu lub braku analizy.
Porównanie **Poprzedni / Nowy** przywraca także katalog wybranego wyniku.
Górne **Analizuj klatkę** stosuje aktywny wspólny katalog bez dopasowania;
przy lokalnym dopasowuje klasy bieżącej klatki z wybranym K. Strojenie 06
zachowuje katalog wyświetlanego wyniku. Stare klasy nie są przemianowywane.

Uruchomienie w **netcat**: `python -m stmdomains.main`. Otwórz
`data/TTMAPP/detection_full.moltrack.json`, wybierz **259**, menu klas.
Przy bazowych domenach: lokalne K5 **120/312, 6 domen**, K4 **132/312, 6**,
K5 z 259–268 **105/312, 5**, K5 z całej serii **111/312, 4**.
Wspólny katalog 259–268 zastosowany na 268: **119/308, 4**.
To sprawdzenie działania, nie pomiar poprawy trafności.

Dopasowanie wspólne odwiedza wszystkie wskazane klatki i wybiera najwyżej
6000 próbek, po `floor(6000/liczba klatek)` z każdej. W metadanych zapisuje
faktyczne próbki, SHA-256 wejścia, indeksy, skalę i powody braków.
259–268: wszystkie 1715 próbek, około 6,44 s. Cała seria 268 klatek:
4497 z 20071 użytecznych próbek, limit 22/klatkę, około 159,13 s.
Wersja katalogu jest skrótem treści; identyczny fit ma ten sam identyfikator.
K1 pomija margines do drugiego centroidu, zachowuje promień. Mała/stała
próba zachowuje przestrzeń deskryptora zamiast zdegenerowanego PCA.

**Wykonane sprawdzenia:**

- 23 nowe przypadki i celowane regresje PASS. Pełny zestaw uruchomiony
  raz po przeglądzie/poprawce: **396 passed, bez pominięć, 65,41 s**.
- Mypy **54 moduły PASS**. Kod/testy: **23 pliki, maksimum 469 linii**.
- `git diff --check` i **333 lokalne ścieżki odnośników w 7 dokumentach PASS**.
- Code-review `eebbfbd...dedd8b8`: **Standards 1 P2**, poprawiona
  w `65e9d2a` i potwierdzona przez recenzenta; **Spec 0 uwag**.
  Górny przycisk po nawigacji i odmowie zbyt dużego K zachowuje teraz
  obie wcześniejsze poprawne wersje. **0 otwartych uwag**.
- Rzeczywiste GUI **X11/xcb sterowane Qt PASS**: K5/K4, zakres, cała seria,
  porównanie i użycie katalogu, walidacja, anulowanie/nawigacja/ponowne
  otwarcie, raw/aligned, gamma, stabilny układ 900×650. Obejrzano zrzuty.
  Zamknięcie podczas dopasowania: kod 0, obie pule workerów zakończone.
- Demo `python -m stmdomains.tools.class_discovery_demo`: K1 **12/16,
  1 domena**, odmowa K8, brak danych, para różniąca się niewybranymi
  klatkami — identyczne lokalne K5 **357/405, 17 domen**. Poprawiono
  czytelność małej kontrolki do 128×128 i sprawdzono końcowy dialog w GUI.
- Źródłowe JSON/MPP niezmienione (SHA-256 przed/po), **0 odczytów ZIP
  lub historycznych modeli/wyników**. Artefakty `.scratch/stmdomains-ui-07/`
  poza Git. Szczyt RSS około **666 MiB**, przerwa timera **0,232 s**.

Nie instalowano pakietów; wszystkie próby w **netcat**. Bez nowych wspólnych
zmian — zależności zgłoszone w 05 nadal aktualne. Wyniki i katalogi są tylko
w pamięci bieżącej serii, do dwóch ukończonych wersji/klatkę. Deskryptor
nadal zależy od orientacji; klasy nie są potwierdzonymi fazami fizycznymi.
Raport zawiera dokładne kroki i komendy ręcznego testu.

**Plan nadal ma 19 ticketów; 01–03, 05, 05a, 06 i 07 done. Dalej 08 → 12.**
08 nie rozpoczęto; 19–20 pozostają odroczone. Historyczne badawcze 04/13
i odbiór całej metody są odrębne. Poniżej historia wcześniejszych etapów.

---

# STM Domains — wykonano SD-V4-06: strojenie i porównanie domen

Data **2026-11-02**, baza **`8caa8a7`**, implementacja **`98ca8ff`**, poprawka
**`36aea1f`**. Gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. [Ticket](implementation/interactive-v04/06-tune-domain-formation.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-06.md).
Status `done`; **odbiór ręczny użytkownika 06 potwierdzony 2026-11-02**
dla wersji **`a4dcace`** słowami „testy manualne ok”. Zapis potwierdzenia
zmienia wyłącznie dokumentację; `git diff --check` PASS, bez ponawiania
testów kodu. Commit zapisu podano w odpowiedzi końcowej.
Następny ticket: **07 — ręczne K i zakres**.

Zgodnie z życzeniem użytkownika menu **Analiza → Tworzenie domen…** otwiera
małe, niemodalne okno. Dostępne: minimum molekuł, odległość łączenia,
kontrola geometrii, próg krawędzi, średnica regionu i zasięg maski. Edycja
i **Przywróć bazowe** zmieniają tylko szkic; **Przelicz domeny** uruchamia
obliczenia. **Poprzedni / Nowy** pokazuje dwa ostatnie ukończone wyniki
na tej samej klatce, bez zmiany zoomu i przesunięcia obrazu. W stopce
głównego okna pozostaje informacja o wybranej wersji także po zamknięciu
dialogu. Nie dodano kolejnego wiersza do głównego układu.

Przeliczanie zachowuje słownik klas, dopasowany model i decyzje porządku.
Przed użyciem poprzednich przypisań sprawdza SHA-256 danych, serię, indeksy
i parametry wcześniejszych etapów. Deskryptory i bariery są wyliczane
ponownie; bez dużego cache pośrednich tablic. Oba minima domen i metadane
korzystają z jednej konfiguracji `DomainSettings`. Zmiana serii usuwa
wyniki; anulowanie/błąd nie zastępują ukończonej pary. Przy braku modelu
przeliczenie wykonuje pełną analizę i zachowuje właściwy powód odmowy.

Uruchomienie w **netcat**: `python -m stmdomains.main`. Otwórz
`data/TTMAPP/detection_full.moltrack.json`, wybierz **259**, analizuj,
a następnie otwórz menu ustawień. Bazowo **120/312, 6 domen**. Średnice
0,50/0,55/0,60 dają tu ten sam wynik; minimum 6 daje **127/312, 7 domen**,
a osobno łączenie 1,80 daje **129/312, 7 domen**. Przywrócenie bazowych
ustawień i przeliczenie odtwarzają identyczne przypisania oraz mapę pikseli.
Więcej przypisań nie oznacza potwierdzonej poprawy trafności.

**Wykonane sprawdzenia:**

- 25 nowych testów oraz celowane regresje PASS. Pełny zestaw uruchomiony
  raz po przeglądzie/poprawce: **373 passed, bez pominięć, 41,51 s**.
- Mypy **45 modułów PASS**. Kod/testy: **12 plików, maksimum 424 linie**.
- Code-review `8caa8a7...98ca8ff`: **Standards 0 uwag**; **Spec 1 P3**,
  poprawiony w `36aea1f`, potwierdzony przez recenzenta, **0 otwartych**.
  Dotyczył błędnego komunikatu przy ponowieniu po przekroczeniu limitu
  pikseli/oznaczeń; dodano dwie regresje.
- Rzeczywiste GUI **X11/xcb sterowane Qt PASS** dla `98ca8ff`: menu myszą,
  sześć parametrów, walidacja, porównanie, odtworzenie wyniku, raw/aligned,
  gamma, układ 900×650, anulowanie/nawigacja/ponowne otwarcie serii.
  Demo: dodatni wynik, zero, brak oznaczeń, brak danych do K5.
  Zamknięcie podczas kalibracji: kod 0, obie pule workerów zakończone.
  Zrzuty okna i dialogu obejrzano. To odbiór agenta, odrębny od potwierdzonego
  powyżej testu ręcznego użytkownika 06.
- SHA-256 wejściowych JSON/MPP identyczne przed i po, 0 odczytów ZIP lub
  dawnych modeli/wyników. Model klas identyczny we wszystkich próbach.
- `git diff --check` i lokalne odnośniki dokumentacji PASS. Artefakty
  `.scratch/stmdomains-ui-06/` poza Git, w tym pełny log pytest i raport GUI.

Nie instalowano pakietów; użyto wskazanego **netcat**. Bez nowych wspólnych
zmian — zależności zgłoszone w 05 nadal aktualne. Wyniki są w pamięci,
nie w projekcie na dysku: najwyżej dwie wersje/klatkę; 512 KiB map/klatkę
TTMAPP, do 32 MiB przy największym dopuszczonym obrazie, plus model
i przypisania. Szczyt RSS próby GUI około 1462 MiB, przerwa timera 0,179 s.

**Plan nadal ma 19 ticketów; 01–03, 05, 05a i 06 done. Dalej 07 → 08 → 12.**
07 nie rozpoczęto. 19–20 pozostają odroczone; historyczne badawcze 04/13
i odbiór całej metody są odrębne. Poniżej historia wcześniejszych etapów.

---

# STM Domains — wykonano SD-V4-05a: obszary i granice domen

Data: **2026-11-02**. Użytkownik polecił dopisać 05a do planu i od razu
go wykonać. [Ticket](implementation/interactive-v04/05a-domain-regions.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-05a.md).
Baza **`319c156`**, implementacja **`dfcf392`**, gałąź
`domains/interactive-v04-ui`, worktree `/home/rlew/projekty/NEtCAT-domains`.
Status `done`; **ręczny odbiór użytkownika 05a potwierdzony 2026-11-02**
dla wersji **`617b006`** słowami „testy manualn ok”. Zapis potwierdzenia
zmienia wyłącznie dokumentację; `git diff --check` PASS, bez ponawiania
testów kodu. Commit zapisu podano w odpowiedzi końcowej. Następny ticket: **06**.

Po analizie widoczne są półprzezroczyste obszary domen z obrysami i numerami
D1, D2… Przycisk **Obszary…** przy legendzie udostępnia niezależne warstwy
i krycie 0–100% (domyślnie 35%). Centra i ramki można wyłączyć. Numer
domeny pozostaje czytelny przy zoomie, a kolory odpowiadają wybranemu
trybowi Domeny/Klasy. Wejściowe ukrywa obszary. Górne **Maski molekuł**
(dawniej Maski / obrysy) dotyczą wyłącznie segmentacji MolTrack: na 259
nie są dostępne, lecz obliczone obszary domen działają.

Uruchomienie w **netcat**: `python -m stmdomains.main`. Otwórz
`data/TTMAPP/detection_full.moltrack.json`, wybierz **259**, kliknij analizę,
wyłącz Centra i Ramki. Powinno być **120/312, 6 domen** i obszary D1–D6.
Sprawdź menu Obszary…, oba tryby kolorowania, raw/aligned, gamma/zoom,
nawigację i anulowanie. Kontrole zera/braków:
`python -m stmdomains.tools.analysis_demo`; szczegóły w raporcie.

**Wykonane sprawdzenia:**

- 8 nowych testów mapy/widoku/kontrolek oraz 25 celowanych regresji PASS.
  Pełny zestaw po przeglądach: **348 passed, bez pominięć, 30,10 s**;
  uruchomiony raz na koniec, komenda w raporcie.
- Mypy **41 modułów PASS**. Kod/testy: **13 plików, maksimum 405 linii**.
- 325 lokalnych odnośników w 8 dokumentach PASS, graf 19 ticketów bez cykli;
  `git diff --check` PASS.
- Code-review `319c156...dfcf392`: **Standards 0 uwag, Spec 0 uwag**.
  Obaj recenzenci niezależnie potwierdzili 8 nowych testów.
- Na TTMAPP 7/120/259/268 porównano z kodem 05: **identyczne przypisania
  każdej molekuły, statusy, przyczyny odmów i model**, również identyczne
  liczniki 245/317 (12 domen), 67/248 (3), 120/312 (6), 145/308 (5).
  Mapa pikseli jest zgodna z końcowymi ID po podziale i renumeracji.
- Rzeczywiste GUI **X11/xcb sterowane Qt PASS**: wszystkie cztery klatki
  raw/aligned, menu i przełączniki myszą, krycie, klasy/domeny, gamma/zoom,
  nieanalizowana klatka, powrót, anulowanie oraz demo zera i braków.
  Stabilny układ 900×650; obejrzano zrzuty także maksymalizacji i popupu.
  Zamknięcie podczas kalibracji: kod 0, obie pule workerów zakończone.
  Sprawdzenie agenta jest odrębne od potwierdzonego powyżej odbioru użytkownika.

Wejściowe JSON/MPP niezmienione (SHA-256 przed/po), **0 odczytów ZIP lub
dawnych artefaktów**. Artefakty `.scratch/stmdomains-ui-05a/` poza Git.
Szczyt RSS GUI około 1462 MiB, maksymalna przerwa testowego timera 0,233 s.
Mapa TTMAPP zajmuje 256 KiB/wynik; największy dopuszczony obraz to 16 MiB
mapy. Kolorowy raster i obrysy są przechowywane tylko dla aktualnego wyniku.
Na TTMAPP budowa ścieżek około 0,8–2,7 ms; kontrola 2048² około 22 ms.

Obszar jest przybliżeniem wspartym centrami i barierami. Zmiana prezentacji
nie stanowi nowego pomiaru granic ani poprawy trafności metody. Ograniczenia
K5/porządku/barier i fragmentacja z 05 pozostają. Brak trwałego zapisu
wyników; przyszłe 13/14 powinny zachować/eksportować także tę końcową mapę.
Bez instalacji i nowych wspólnych zmian; zależności zgłoszone w 05 nadal
aktualne. Badawcze 04/13 i odbiór całej metody pozostają odrębne.

**Plan: 19 ticketów; 01–03, 05 i 05a done. Następny: 06 — strojenie
tworzenia domen.** Nie rozpoczęto go w tym zleceniu. Pozostałe statusy
i zależności zachowane. Poniżej historia poprzednich etapów.

---

# STM Domains — wykonano SD-V4-05: własne obliczenia klatki

Data: **2026-11-02**. Na polecenie `implement 05` wykonano
[SD-V4-05](implementation/interactive-v04/05-analyze-current-frame.md),
status `done`; **ręczny odbiór użytkownika oczekuje**. Baza **`2d01c5e`**,
implementacja **`fb37431`** na `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. Commit dokumentacji podano w odpowiedzi.

Przycisk **Analizuj klatkę · K5** oblicza z oryginalnego obrazu i oznaczeń
bieżącej klatki skalę, opisy otoczeń, ocenę porządku i jej kalibrację,
PCA/KMeans, bariery oraz domeny. Parametry modelu powstają wewnętrznie,
bez dostępu do paczek, modeli, etykiet lub kalibracji v0.4. Wynik po ID
molekuły obejmuje końcową klasę/domenę i przyczynę odmowy. UI pokazuje
**Domeny / Klasy / Wejściowe**, legendę i liczniki; duplikaty są osobnym
stanem poza mianownikiem. Przyciski danych udostępniają użyte parametry,
kalibrację, model i identyfikację wejścia. Obliczenia działają w tle;
zmiana klatki, anulowanie i nowa seria odrzucają spóźnione wyniki.

**[Instrukcja odbioru i raport](implementation/interactive-v04/acceptance-05.md).**
Uruchom w **netcat**: `python -m stmdomains.main`, otwórz
`data/TTMAPP/detection_full.moltrack.json`, wybierz 259 i kliknij analizę.
Sprawdź kolory Domeny/Klasy, odmowę po kliknięciu szarej molekuły,
gamma/zoom/raw/aligned, powrót do wyników i anulowanie. Generator
`python -m stmdomains.tools.analysis_demo` udostępnia w tym samym UI
kontrole poprawnego wyniku, zera domen, braku oznaczeń i zbyt małej próby.

**Wykonane sprawdzenia w netcat, bez instalacji:**

- Pełny zestaw **340 testów PASS, bez pominięć, 26,92 s**, w tym 32 nowe;
  uruchomiony raz po poprawkach i przeglądach. Mypy **38 modułów PASS**.
- Długości kodu/testów: **20 plików, maksimum 394 linie**. Wspólnego kodu,
  konfiguracji i pozostałych aplikacji nie zmieniano.
- **316 lokalnych odnośników w 9 dokumentach PASS**, `git diff --check` PASS.
- Code-review `2d01c5e...fb37431`: Spec bez niezgodności; Standards bez
  naruszeń/usterek blokujących. Uwaga o powtórzonych stałych trafiła do 06:
  ustawienia obliczeń i raportu mają korzystać ze wspólnej konfiguracji.
- Próby TTMAPP, każda powtórzona z identycznym członkostwem: 7 **245/317,
  12 domen**; 120 **67/248, 3 domeny**; 259 **120/312, 6 domen**;
  268 **145/308, 5 domen**. Zero odczytów dawnych paczek/artefaktów,
  identyczne SHA-256 wejściowych MPP i JSON przed/po.
- Rzeczywiste GUI X11/xcb sterowane Qt: analiza, wszystkie tryby wyników,
  odmowy, raw/aligned, gamma/zoom, nawigacja/anulowanie, kontrole i jedna
  klatka. Układ okna 900×650 stabilny; obejrzano zrzuty także maksymalizacji.
  Zamknięcie w trakcie kalibracji: kod 0, obie pule workerów zakończone.
  To sprawdzenie agenta, oddzielne od oczekiwanego odbioru użytkownika.

Lokalne artefakty `.scratch/stmdomains-ui-05/` pozostają poza Git.
Na sprawdzonych danych samo obliczenie około 0,66–0,72 s/klatkę;
259 bez ustawiania zmiennych liczby wątków 0,704 s. GUI szczyt RSS około
1288 MiB; dotychczasowe ograniczenia wczytywania JSON/MPP pozostają.
Początkowe limity analizy: 3000 oznaczeń i 4 194 304 piksele.

**Ograniczenia:** model i kolory klas są lokalne dla klatki, bez śledzenia
w czasie. Wyniki pozostają w pamięci, po jednym na klatkę; zapis należy
do 13. K5 jest jawnym wariantem bazowym, nie oszacowaniem liczby faz.
Ocena porządku wykrywa pojedynczy kierunek okresowości, bariery zakładają
bliskie poziomym jasne przejścia. Kontrola pięciu pól sieci daje 17 domen,
więc fragmentacja pozostaje widoczna. Liczniki przypisań nie dowodzą
trafności detekcji; badawcze 04/13 i odbiór całej metody nadal otwarte.

**Następny ticket: 06 — strojenie tworzenia domen**, bez jego implementacji
w tym zleceniu. 07 doda ręczne K i zakres dopasowania, 08 wspólną analizę
serii, 12 Auto. **01–03 oraz 05 done**, 06–10 i 12–18 ready po zależnościach,
19–20 deferred. 04/11 pozostają wycofane. Odbiór użytkownika 01–03 zachowany.

**Dla integratora:** deklaracja zależności STM Domains wymaga teraz także
scikit-learn i threadpoolctl, obok wcześniej zgłoszonych NumPy/SciPy oraz
pytest-qt do testów. Wszystkie są dostępne w istniejącym netcat; wspólnych
requirements nie zmieniano. Poniżej historia, której wskazania kolejnego
zadania nie zastępują aktualnego planu.

---

# STM Domains — wycofanie 04, plan własnych obliczeń

Data: **2026-11-02**. Użytkownik polecił całkowicie pominąć wczytywanie
modeli/wyników v0.4, usunąć poprzedni ticket i zmodyfikować plan. Kod v0.4
ma być wzorem metody, którą implementujemy i następnie rozszerzamy.

**Wykonano rollback SD-V4-04:** odwrócono `c13b291` oraz `b6159ac`,
zachowując historię Git. Kod `stmdomains/` i testy `tests/stmdomains/`
są identyczne z **`24625f2`**, czyli odebranym 03 po poprawkach układu
`0745e4e` i wyjścia `3dd8b47`. Usunięto przycisk/importer wyników v0.4,
model podglądu i testy dodane w 04 oraz jego ticket/raport odbioru.
Lokalne dane, ZIP, modele i artefakty badawcze pozostały bez zmian.
Nie usuwano historii commitów ani nie zmieniano innych worktree.

**[Aktualny plan](implementation/interactive-v04/README.md):**

- **05**: obrazy i oznaczenia → opisy otoczeń → klasy PCA/KMeans (bazowe K5)
  → domeny na jednej klatce → kolory, legenda i odmowy w UI. Model powstaje
  wewnętrznie; nie ma importu paczki ani ręcznego wyboru pliku modelu.
- **06**: strojenie tworzenia domen i porównanie własnego wyniku bazowego.
- **07**: ręczne K1–8 i zakres odkrywania, jedna klatka lub wspólny zakres.
- **08**: wspólne klasy i analiza domen zakresu/serii; wymaga 07.
- **12**: Auto na danych jednej klatki lub zakresu; wymaga 07, może poprzedzić 08.

Usunięto dawny **11** jako dublujący nowe 05/07. Numery 04/11 pozostają
historycznie zarezerwowane, pozostałe ID bez zmian. **18 aktywnych ticketów**:
01–03 done, 05–10 i 12–18 ready-for-agent po zależnościach, 19–20 deferred.
09 wymaga 07 (K1), 14 wymaga 05. Uaktualniono także zapis projektu, eksport
oraz rozszerzenia 15–20: punktem porównania są obliczenia metody bazowej
naszej aplikacji. Własny projekt z 13 pozostaje dozwolony i opcjonalny.

Nie wolno zastąpić ręcznego importu automatycznym kopiowaniem dawnego modelu.
Przenoszona metoda musi działać bez dawnych modeli, etykiet, cech, katalogu
pierwszych dziesięciu klatek, plików kalibracji i stałego rozstawu TTMAPP.
Pochodzenie skali, kontrola porządku i zakres dopasowania są jawne. Nowe
wyniki nie muszą odtwarzać etykiet/liczników starego eksportu. Samo grupowanie
K5 ani wzrost przypisań nie potwierdzają domen fizycznych. Każdy ticket ma
ręczny scenariusz w uruchamialnym UI; limit kodu 1000/1500 linii zachowany.

**Sprawdzenia w istniejącym netcat:**

- `git diff 24625f2 -- stmdomains tests/stmdomains`: pusta różnica.
- Pełny zestaw STM Domains: **308 passed, bez pominięć, 16,31 s**.
  Komenda: `QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains`.
- Mypy core/io/ui/tools: **27 plików PASS**. Sprawdzenie nie obejmuje
  historycznego katalogu experiments z wcześniejszymi błędami typowania.
- Kontrola rozmiaru przywróconego kodu/testów: **7 plików, maksimum 341 linii**.
- Niezależny przegląd planu bez otwartych uwag po doprecyzowaniu słownika w 07.
  **347 lokalnych odnośników PASS**, graf 18 ticketów bez cykli i zależności
  od usuniętych 04/11; każdy ticket ma test ręczny. `git diff --check` PASS.
  Nie ponawiano ręcznego odbioru GUI:
  przywrócono dokładnie kod już zaakceptowany przez użytkownika w 03.

Uruchomienie: `conda activate netcat`, następnie `python -m stmdomains.main`.
Ręczna kontrola zakresu rollbacku: otwórz MPP/JSON, przełączaj klatki suwakiem
lub miniaturami, odtwórz, zmień gamma i zamknij aplikację. Powinny działać
funkcje 01–03, bez przycisku Otwórz wynik v0.4. Ta instrukcja nie oznacza
wykonania nowego testu ręcznego. Własna analiza pozostaje do zaimplementowania.

**Następne zadanie: SD-V4-05 — oblicz klasy i domeny bieżącej klatki z danych.**
Nie rozpoczęto go tym zleceniem. Odbiór 01–03 jest zachowany; badawcze 04/13
oraz historyczny odbiór całego szkieletu pozostają odrębne, otwarte.
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/interactive-v04-ui`.
Commit rollbacku i aktualizacji planu podano w odpowiedzi końcowej.
Bez instalacji ani nowych wspólnych zmian; wcześniejsze zgłoszenie
NumPy/SciPy/pytest-qt integratorowi pozostaje aktualne. Poniżej historia
poprzednich etapów — ich wskazania kolejnego ticketu nie zastępują tego planu.

---

# STM Domains — wykonano SD-V4-03: miniatury i odtwarzanie

**Odbiór poprawki wyjścia — 2026-11-02:** użytkownik potwierdził „testy
manualne ok” dla **`3dd8b47`**. **SD-V4-03 wraz z poprawkami układu i wyjścia
jest odebrany ręcznie.** Zapis potwierdzenia zmienia wyłącznie dokumentację;
`git diff --check` PASS, bez ponawiania testów kodu. Commit zapisu w odpowiedzi
końcowej. Następny ticket: **SD-V4-04 — otwarcie wyniku v0.4 i przynależność
molekuł**. Historyczny odbiór szkieletu i badawcze 04/13 pozostają odrębne.

**Odbiór ręczny i poprawka wyjścia — 2026-11-02:** użytkownik potwierdził
„testy manualne ok” dla 03 wraz z poprawką układu **`0745e4e`**, po czym
zgłosił crash przy wyjściu: `TaskSignals has been deleted` w `finished.emit`.
Odtworzono dokładny traceback w osobnym procesie. Qt usuwało obiekty sygnałów
przed końcem workerów. `aboutToQuit` zatrzymuje teraz obie pule i czeka na
ich zakończenie przy żywych obiektach Qt; działa dla zamknięcia okna i app.quit.
Nie przerywa siłowo odczytu, więc zakończenie procesu może chwilę potrwać.

W `netcat`: **25 celowanych testów PASS**, w tym 4 nowe regresje procesów;
te same **4 przypadki X11/xcb PASS**, mypy **27 plików PASS**. Kontrola
5 plików kodu/testów, maksimum **341 linii**. Pierwotna reprodukcja kończy
się kodem 0. **3/3 dodatkowe próby TTMAPP na X11 PASS**: wyjście w trakcie
importu, miniatur i play; kod 0, pusty stderr, obie pule zakończone.
Przegląd poprawki bez uwag. Pełnego zestawu nie powtarzano.
[Raport i sprawdzenie wyjścia](implementation/interactive-v04/acceptance-03.md#poprawka-wyjścia-z-programu).
**Ręczny odbiór poprawki wyjścia potwierdzony przez użytkownika.** Artefakty:
`.scratch/stmdomains-ui-03/shutdown-debug/`. Baza `0745e4e`, poprawka `3dd8b47`.
Zmiany tylko w aplikacji, testach i dokumentacji;
bez instalacji. Następny ticket nadal SD-V4-04.

**Poprawka po odbiorze użytkownika — 2026-11-02, baza `c5deb59`:**
zgłoszony skok przy ładowaniu klatki został odtworzony i usunięty. Pokazywanie
paska postępu i przycisku Anuluj zwiększało dolny wiersz o 8 px; układ
zachowuje teraz ich miejsce także w stanie ukrytym. W `netcat`: **13 testów
okna PASS**, w tym 4 nowe regresje, mypy **27 plików PASS**, kod/test 331/71
linii. Rzeczywiste GUI X11: 12 przejść TTMAPP w 1100×760 i 900×650 bez zmian
geometrii przy ładowaniu i publikacji, także przy różnych komunikatach.
Artefakty `.scratch/stmdomains-ui-03/layout-debug/`. Pełnego zestawu 300
testów nie powtarzano. [Scenariusz ponownego sprawdzenia](implementation/interactive-v04/acceptance-03.md#poprawka-po-zgłoszeniu-użytkownika--stabilny-układ-okna).
Użytkownik potwierdził ręczny odbiór funkcji 03 i tej poprawki (`0745e4e`).
Zmiany tylko w aplikacji, testach i dokumentacji, bez instalacji.
Poniżej pierwotny raport 03.

Data: **2026-11-02**. Na polecenie `implement 03` wykonano
[SD-V4-03](implementation/interactive-v04/03-filmstrip-and-playback.md), `done`.
Działa pasek miniatur pod obrazem, play/pauza, od początku, maksymalne tempa
1/2/5/10/20 kl./s oraz gamma 0,2–5 z resetem do 1. Każdy krok publikuje
kompletny obraz i oznaczenia; wolne przygotowanie spowalnia odtwarzanie
bez pomijania klatek. Pauza odrzuca oczekujący krok. Zapisany tryb widoku
jest przywracany przy otwarciu, jeżeli geometria na to pozwala: TTMAPP
otwiera klatkę 268 wyrównaną, inaczej niż początkowy oryginał w 02.

[Raport i dokładny test ręczny](implementation/interactive-v04/acceptance-03.md).
Uruchomienie w **netcat**: `python -m stmdomains.main`. Przykłady 8 klatek,
niepoprawnych próbek, stałej klatki i jednej klatki:
`python -m stmdomains.tools.browsing_demo`. **Odbiór ręczny użytkownika 03
potwierdzono dla `0745e4e`.** Potwierdzenia 01 i 02 pozostają zachowane.

Sprawdzenia: **300 testów STM Domains PASS, bez pominięć, 13,58 s**, w tym
21 nowych; mypy **27 plików PASS**; kontrola **12 plików, maksimum 327 linii**.
Pełny zestaw uruchomiono raz po poprawkach i przeglądzie. Standards znalazł
błąd zaznaczenia po prawym kliknięciu: naprawiony i sprawdzony regresyjnie.
Końcowa kontrola wykryła spóźniony krok przy ręcznej nawigacji → Play → Pauza:
również naprawiony, recenzent Spec potwierdził poprawkę. **0 otwartych uwag**.

Rzeczywiste GUI X11 sterowane Qt: pełne **268 klatek TTMAPP**, wszystkie
tempa, pauza/wznowienie, restart/koniec, miniatury, gamma, zoom, dialog
i kontrolne braki danych. Obejrzano zrzuty. Po poprawkach dodatkowo
**9 testów GUI/kontrolera PASS na X11**. SHA-256 JSON i MPP przed/po identyczne.
Sprawdzono linki dokumentacji i `git diff --check`. Lokalne artefakty:
`.scratch/stmdomains-ui-03/`, poza Git.

Cache miniatur: do **64 rastrów/1,5 MiB** plus obiekty Qt; przygotowanie
pojedynczo dla widocznego fragmentu i sąsiadów. Cache obrazów 3/32 MiB,
masek 2/64 MiB. JSON i MPP nadal w pamięci w całości, lokalny szczyt RSS
około **1132 MiB**. Otwarcie około 0,83 s, 267 przejść przy limicie
20 kl./s około 17,62 s. Anulowanie odrzuca wynik bez przerywania wątku.
Tempo podglądu nie jest czasem pomiaru; ograniczenia kalibracji pozostają.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/interactive-v04-ui`,
baza **`d862333`**, implementacja **`93701af`**, poprawki i raport **`c5deb59`**.
Zmiany tylko w aplikacji, testach
i dokumentacji; bez nowych zależności lub instalacji. Wcześniejsze zgłoszenie
NumPy/SciPy/pytest-qt do integratora nadal aktualne, wspólny kod i CI bez zmian.
**Następny ticket: SD-V4-04**, otwarcie wyników v0.4 i przynależność molekuł.
Historyczny odbiór szkieletu oraz badawcze 04/13 pozostają osobnymi zadaniami.

---

# STM Domains — wykonano SD-V4-02: oznaczenia i geometria

Data: **2026-11-02**. Na polecenie `implement 02` wykonano
[SD-V4-02](implementation/interactive-v04/02-molecules-and-geometry.md), `done`.
Działają centra/ramki/maski/obrysy, krycie, ID i metadane po kliknięciu,
widoki oryginał/wyrównany z zapisaną rejestracją oraz jawna dostępność danych.
Ułamkowe przesunięcia, globalny padding i pole pomiarowe korzystają z jednego
modelu geometrii; błędna maska pozostawia poprawne ramki/obrysy.

[Raport i dokładny scenariusz ręczny](implementation/interactive-v04/acceptance-02.md).
Uruchomienie w **netcat**: `python -m stmdomains.main`. Kontrole braków:
`python -m stmdomains.tools.annotation_demo`. **2026-11-02 użytkownik potwierdził
pomyślny ręczny odbiór 02** słowami „testy manualne ok”. Odbiór obejmuje wersję
`3572b6d` (implementacja `df5c48b`); 01 i suwak również mają jego potwierdzenie.

Sprawdzenia: **279 testów STM Domains PASS**, w tym 49 nowych, bez pominięć;
mypy **23 pliki PASS**; kontrola **17 plików kodu/testów, maksimum 274 linie**.
Code-review `152146a...df5c48b`: Standards **0 uwag**, Spec **0 uwag**.
Pełny zestaw uruchomiono raz po przeglądzie. Rzeczywiste GUI X11 sterowane
Qt: 14 par klatka/widok na TTMAPP (1/40/41/64/68/69/268) i 5 plików kontrolnych;
obejrzano zrzuty. SHA-256 JSON i MPP przed/po identyczne. Linki dokumentacji
i `git diff --check` sprawdzone. Artefakty `.scratch/stmdomains-ui-02/` poza Git.

Maski dekodowane na potrzebę klatki: cache do 2 wpisów/64 MiB, obrazy
podglądu do 3 wpisów/32 MiB. Aktualny wynik i bufory mają dodatkowy koszt.
MPP/JSON nadal w pamięci w całości; lokalny szczyt RSS około 1121 MiB.
Anulowanie odrzuca wynik bez siłowego przerywania wątku. Czas/kalibracja
TTMAPP pozostają niepotwierdzone; 267 rejestracji ma niską pewność.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/interactive-v04-ui`,
baza **`152146a`**, implementacja **`df5c48b`**, raport **`3572b6d`**.
Zapis potwierdzenia odbioru zmienia tylko dokumentację; `git diff --check` PASS,
bez ponawiania testów kodu. Commit tego zapisu w odpowiedzi końcowej.
Zmiany tylko w aplikacji, testach i dokumentacji. Integrator powinien dodać
używane teraz **SciPy** do wcześniejszego zgłoszenia NumPy/pytest-qt;
lokalny `netcat` zawiera pakiety, nic nie instalowano. Wspólny kod i CI bez zmian.
Następny ticket w kolejności to 03; 04 jest również dostępny po 02.

---

# STM Domains — odbiór 01 i suwak klatek

Data: **2026-11-02**. Użytkownik potwierdził pomyślne testy ręczne pierwotnego
SD-V4-01 (`808f3b7`) i zlecił dodanie suwaka pod obrazem. Suwak działa podczas
przeciągania i podąża za zmianami numeru/przycisków. Bez serii i dla jednej
klatki jest nieaktywny. Wykorzystuje istniejącą obsługę pracy w tle i odrzucania
starszych wyników; anulowanie przywraca pozycję wyświetlanej klatki.

**Odbiór suwaka (`ee54638`) potwierdzony przez użytkownika 2026-11-02:**
„testy manualne ok”. SD-V4-01 wraz z dodatkiem został odebrany ręcznie.

W `netcat`: **9 testów widoku/nawigacji PASS**, mypy **14 plików PASS**,
kontrola długości zmienionego kodu/testów **162/204 linie**, przegląd drugiego
agenta bez uwag. Rzeczywiste GUI X11: przeciąganie na TTMAPP 268 klatek,
sprawdzenie obrazu i numeru przed puszczeniem uchwytu; zrzut lokalny
`.scratch/stmdomains-ui-01/slider.png`. GUI sterowano przez Qt i obejrzano zrzut.
Pełnego zestawu 230 testów z poprzedniego odbioru nie powtarzano.

[Scenariusz ręczny suwaka](implementation/interactive-v04/acceptance-01.md#ręczne-sprawdzenie-nowego-suwaka)
zachowano jako instrukcję ponownego sprawdzenia. Uruchomienie w `netcat`:
`python -m stmdomains.main`. Kolejny ticket pozostaje 02.
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/interactive-v04-ui`,
baza **`808f3b7`**, commit dodatku **`ee54638`**. Potwierdzenie odbioru zmienia
tylko dokumentację; sprawdzono `git diff --check`, bez ponawiania testów kodu.
Commit zapisu odbioru w odpowiedzi końcowej. Brak nowych potrzeb
integracyjnych, instalacji i zmian wspólnych modułów.

---

# STM Domains — wykonano SD-V4-01: otwarcie danych i przeglądanie obrazów

Data: **2026-11-02**. Na polecenie `implement 01` wykonano
[SD-V4-01](implementation/interactive-v04/01-open-images.md), status `done`.
Działa otwarcie MolTrack schema 1/2/3 z jednym MPP, relokacja źródła,
potwierdzenie zmienionego mtime, podgląd oryginałów, nawigacja, numer klatki,
zoom/pan/dopasowanie oraz anulowanie importu w tle. Atomowa aktywacja
i tokeny żądań zachowują poprzednią serię po błędzie lub anulowaniu.

[Raport i gotowy scenariusz ręczny](implementation/interactive-v04/acceptance-01.md)
zawierają uruchomienie przez `python -m stmdomains.main` w **netcat** oraz
generator małych przykładów. Oznaczenia i raw/aligned należą do następnego
02; stare zadania odbioru całego szkieletu i naukowe 04/13 pozostają otwarte.

Sprawdzenia: **230 testów aplikacji PASS**, w tym 35 nowych; mypy **14 plików
PASS**; kontrola **16 plików kodu/testów, maksymalnie 209 linii**; wejście
modułowe aplikacji; rzeczywiste GUI xcb na TTMAPP 268×256×256, dziewięć
wybranych klatek, zoom/dopasowanie, rzeczywiste potwierdzenie źródła i jedna
klatka. GUI sterowano automatycznie i obejrzano zrzuty. Ręczny odbiór przez
użytkownika pozostaje do wykonania; nie deklarujemy jego przeprowadzenia.
Sprawdzono też lokalne linki dokumentacji i `git diff --check`.

Code-review od bazy `4c4825f`: Standards — brak twardych naruszeń, jedna
uwaga czytelności poprawiona i ponownie sprawdzona; Spec — brak niezgodności.
Pełne raporty obu osi są w raporcie odbioru. Nie instalowano zależności.
Czytnik materializuje cały MPP; lokalny pomiar dał około 0,72 s otwarcia
oraz szczyt RSS około 1051 MiB. To ograniczenie przy większych plikach;
anulowanie odrzuca wynik, lecz nie przerywa siłowo trwającego odczytu.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/interactive-v04-ui`.
Implementacja `347a2b5`, po bazie **`4c4825f`**; commit końcowych poprawek
i dokumentacji w odpowiedzi końcowej. Zmiany tylko w aplikacji, jej testach
i dokumentacji. Integrator powinien uzupełnić główne zależności szkieletów
o NumPy dla tej funkcji oraz pytest-qt w testach; przyszłe wyrównanie będzie
potrzebowało SciPy. Lokalny netcat już zawiera te pakiety. Nie zmieniano
wspólnego czytnika, konfiguracji głównej ani CI.

---

# STM Domains — środowisko uruchomienia i testów

Data: **2026-11-02**. Użytkownik wskazał istniejące środowisko Conda
**`netcat`** jako środowisko do uruchamiania programu, testów i prób.
Zapisano tę zasadę w instrukcji aplikacji oraz powiązano ją z instrukcją
uruchomienia i wspólnymi kryteriami ticketów.

Sprawdzono aktywne `CONDA_DEFAULT_ENV=netcat` oraz zgodność `CONDA_PREFIX`
z `sys.prefix`. Działający interpreter:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Próba `conda run -n netcat` w piaskownicy zwróciła `NoWritableEnvsDirError`;
Python już aktywnego środowiska działa poprawnie. Można również wskazać
zweryfikowany interpreter bezpośrednio. Nie zmieniano ani nie instalowano
środowiska; nie uruchamiano aplikacji lub testów funkcjonalnych.

Sprawdzenia dokumentacji: lokalne odnośniki i `git diff --check`.
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź
`domains/interactive-v04-ui`, baza **`d317329`**; commit w odpowiedzi końcowej.
Statusy ticketów pozostają bez zmian; brak potrzebnych zmian wspólnych.

---

# STM Domains — gałąź implementacji interaktywnego UI

Data: **2026-11-02**. Na polecenie użytkownika utworzono i wybrano lokalną
gałąź **`domains/interactive-v04-ui`** w istniejącym worktree
`/home/rlew/projekty/NEtCAT-domains`. Punktem startowym jest `b21e0ca`
z `domains/start`, zawierający [plan SD-V4-01–20](implementation/interactive-v04/README.md).

Gałąź jest przeznaczona do przyszłej implementacji. Nie rozpoczęto żadnego
ticketu i nie zmieniono ich statusów. Nie tworzono kolejnego worktree ani
nie publikowano gałęzi zdalnie. Sprawdzono bieżącą gałąź, stan katalogu,
przypisanie worktree i poprawność różnic dokumentacji. Testy programu i GUI
nie dotyczą tej operacji. Commit aktualizacji przekazania podano w odpowiedzi
końcowej; brak potrzebnych zmian wspólnych.

---

# STM Domains — rozszerzenia planu interaktywnego UI

Data: **2026-11-02**. Użytkownik polecił dopisać omówione rozszerzenia jako
osobne tickety. Dodano [SD-V4-16–20](implementation/interactive-v04/README.md#rozszerzenia):

- 16: pomiary kierunku, rozstawu i jakości bezpośrednio na obrazie;
- 17: eksperymentalne tworzenie domen według tolerancji geometrycznych;
- 18: ograniczona próba freud.EnvironmentCluster bez zadawania K;
- 19: lokalne FFT/NMF jako dalsza, warunkowa próba porównawcza;
- 20: wspólny katalog typów w serii i zapis w projekcie, po ocenie stabilności opisu.

16–18 mają status `ready-for-agent`, przy nieukończonych zależnościach;
19–20 `deferred` z jawnym warunkiem wyboru. Użytkownik zlecił dodanie
omówionych rozszerzeń, więc nie wymagano ponownego potwierdzenia tego
zapisu. Podstawowych 01–15 nie zmieniano: pozostają `draft`.
Każdy nowy ticket zawiera kryteria, test ręczny z oczekiwanym zachowaniem
i obowiązek kontroli 1000/1500 linii kodu oraz testów. Najkrótsza droga
do pomiarów to 01 → 02 → 04 → 05 → 16; 17 i 18 wymagają dodatkowo 06.

Porównania zachowują v0.4 oraz sprawdzają jedną sieć, dwie orientacje,
granicę przesunięcia, braki detekcji i rzeczywistą przerwę. Doprecyzowano
rozróżnienie typu, orientacji, domeny i porządku 1D/2D, nieokresowe brzegi
obrazu dla freud oraz brak niezależności statystycznej obrazu i jego detekcji.
Nie dodano integracji Gwyddion/Atomap/OVITO, GPA, symulacji ani nowego treningu.

Sprawdzenia: przegląd zależności i zakresu przez drugiego agenta, kompletność
20 ticketów, acykliczność zależności, kroki testów ręcznych, lokalne odnośniki
i `git diff --check`. Nie uruchamiano aplikacji, testów GUI ani eksperymentów;
zmiany obejmują wyłącznie plan. Nie instalowano bibliotek. Statusy odbioru
naukowego i historycznych ticketów pozostają bez zmian.
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`,
baza **`5c78b66`**; commit w odpowiedzi końcowej. Ewentualne wspólne zmiany
zależności przy realizacji prób należy przekazać integratorowi; obecnie
brak zmian wspólnych do wykonania.

---

# STM Domains — tickety interaktywnego UI v0.4

Data: **2026-11-02**. Na prośbę użytkownika przygotowano
[15 osobnych ticketów SD-V4](implementation/interactive-v04/README.md)
z zależnościami, kryteriami akceptacji i krokami ręcznego testu po każdym
zadaniu. Pierwszy daje otwarcie pliku i przeglądanie obrazów, kolejne
oznaczenia molekuł, wynik v0.4, obliczenia oraz regulację parametrów.
Dalszy zakres obejmuje analizę serii, ręczne K, niezależną klatkę, Auto,
samowystarczalny projekt i eksport.

Status wszystkich nowych ticketów: **draft**. Podział czeka na zatwierdzenie
użytkownika zgodnie z wywołanym `to-tickets`; dopiero wtedy status
`ready-for-agent`. Stare tickety i ich statusy pozostają bez zmian.
Nie rozpoczęto implementacji ani nowych badań. W instrukcji aplikacji
zapisano wymaganie użytkownika: cel do 1000, twardy limit 1500 fizycznych
linii na plik kodu i testów, z kontrolą w każdym zadaniu.

Sprawdzenia dokumentacji: lokalne odnośniki nowych i zmienionych plików,
kompletność 15 ticketów, zależności bez cykli, scenariusz ręczny każdego
ticketu oraz `git diff --check`. Nie uruchamiano aplikacji ani testów GUI:
zmieniono plan i instrukcję, a scenariusze dotyczą przyszłej implementacji.
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`,
baza **`5224554`**; commit w odpowiedzi końcowej. Zmiany dotyczą wyłącznie
dokumentacji STM Domains i jego instrukcji. Brak potrzebnych teraz zmian
wspólnych; ewentualne zależności środowiska podczas implementacji należy
przekazać integratorowi.

---

# STM Domains — wykonalność interaktywnego UI v0.4

Data: **2026-11-02**. Użytkownik opisał program do zmiany parametrów,
uruchamiania analizy serii lub jednej klatki i oglądania wyniku, z ręcznym K
oraz bez znajomości K. Przeczytano dostarczoną notatkę strojenia i sprawdzono
kod. [Ocena wykonalności](v04-interactive-ui-feasibility.md): v0.4 jest
odpowiednią bazą po wydzieleniu obliczeń i ujednoliceniu konfiguracji.

Istotne ustalenie: `discover_classes.py` już wybiera K według silhouette,
ale runner zawsze przekazuje K z konfiguracji. Auto wymaga podłączenia
całej ścieżki oraz obsługi K1 i braku danych; obecny ranking preferuje K2,
nie ręcznie wybrane K5. Dla jednej klatki trzeba rozdzielić użycie słownika
serii od odkrywania nowego słownika. Runner nadal wymaga pierwszych 10 klatek.
Pierwsze wejście to obrazy z istniejącymi oznaczeniami MolTrack.

Zapisano proponowane zachowanie UI i zakres zmian, bez implementacji,
nowych treningów, instalacji, uruchamiania kodu paczki lub nowych ticketów.
Nie przyjęto detektora; 04/13 pozostają otwarte. Domyślne wyniki v0.4
pozostają punktem odniesienia, a łagodniejsze progi z notatki nie są sprawdzone.

Sprawdzenia: statyczna analiza skryptów, konfiguracji i obecnego szkieletu
PyQt6, dodatkowy przegląd wykonalności, lokalne odnośniki dokumentacji
i `git diff --check`. Bez testów programu lub GUI, ponieważ zmieniono
wyłącznie dokumentację. Worktree `/home/rlew/projekty/NEtCAT-domains`,
gałąź `domains/start`, baza **`5d4d430`**; commit w odpowiedzi końcowej.
Brak bieżących zmian wspólnych; ewentualne zależności aplikacji podczas
budowy wymagają przekazania do integratora zgodnie z podziałem prac.

---

# STM Domains — przegląd paczek v0.4

Data: **2026-11-02**. Na polecenie użytkownika przejrzano dwa archiwa
`data/new_code/stm_domains_source_v04.zip` i `stm_domains_prototype_v04.zip`.
[Podsumowanie](new-code-v04-review.md) opisuje zawartość, metodę, wyniki,
przeglądarkę i ograniczenia ponownego użycia. Kopie rozpakowane są w
`.scratch/new-code-v04-review/source/` i `prototype/`, poza Git.

Wspólna treść kodu jest identyczna. Pełna paczka zawiera 56 klatek naszego
TTMAPP, 9695 aktywnych pozycji, 4190 końcowych przypisań i 122 domeny.
Metoda korzysta z geometrii centrów, PCA/KMeans K5 i ograniczeń podobieństwa
wewnątrz regionu. Dopuszcza jeden kierunek periodyczności; liczby nie są
bezpośrednio porównywalne z kryterium sieci 2D i mianownikami 21–26.
K i parametry wybrano na tej samej serii; nie ma niezależnej oceny trafności.

Gotowy HTML pokazuje maski i klasy geometrii. Końcowe przypisania molekuł
w CSV mogą zasilić uzgodniony prosty widok, którego paczka jeszcze nie ma.
Wynik pozostaje częściowy, z opisanymi w paczce brakami i scaleniami A/B.
Nie scalono kodu, nie zmieniono metod ani protokołu, nie uruchomiono nowych
analiz lub treningów. 04 i 13 pozostają otwarte, bez nowych ticketów.

Sprawdzenia: odczyt wszystkich ZIP/CRC, zgodność 35/299 wpisów manifestów
z SHA-256 i rozmiarami, porównanie obu paczek, składnia 27 plików Python,
zgodność źródeł MPP/JSON, ID i geometrii 9697 rekordów, liczniki CSV,
porównanie zapisanych wariantów i inspekcja PNG. Przejrzano kod i zakres
dołączonych audytów. Nie odtwarzano pipeline'u ani testów autora; dołączony
test HTML używał imitacji DOM, nie pełnego odbioru przeglądarki.
Sprawdzono lokalne odnośniki dokumentacji i `git diff --check`.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`,
baza **`126b9eb`**. Commit przeglądu podany w odpowiedzi końcowej.
Wersjonowano tylko dokumentację; oryginalne paczki, kod i dane pozostają
lokalne. Brak potrzebnych zmian wspólnych; integracja po stronie koordynatora.

---

# STM Domains — prosty podgląd wyników przyszłych prób

Data: **2026-11-02**. Użytkownik uznał dotychczasowe raporty za nieczytelne
i wskazał potrzebę przeglądarki kolejnych obrazów z oznaczonymi molekułami
oraz przynależnością do domen. Zapisano [wymaganie prezentacji](trial-result-browser.md)
i połączono je z README, mapą metod oraz odbiorem 13.

Podstawowy widok: jeden obraz, nawigacja po klatkach, oznaczenia w centrach
molekuł, kolor domeny i szary brak przypisania. Diagnostyka pozostaje osobno.
Przypisania muszą wynikać z zapisanego wyniku metody; istniejące diagnostyczne
mapowanie najbliższego punktu siatki z 25/26 nie staje się końcowym wynikiem.
Kolory nie oznaczają tożsamości domen między klatkami. Zero i brak analizy
pozostają odrębne; szczegóły zgodne z wcześniejszymi regułami statystyk.

Zakres bieżącej pracy to wyłącznie dokumentacja przyszłych prób, bez nowego
GUI, treningu, przeliczania wyników, zmiany metody lub historycznych galerii.
13 i 04 pozostają otwarte. Przeglądarka zostanie wykonana przy przyszłych
próbach zgodnie z tym wymaganiem; obecny wpis nie potwierdza jej implementacji.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`,
baza **`bdce82a`**; commit podany w odpowiedzi końcowej. Sprawdzono zgodność
z kontraktem przypisań i precedensem 15/16, lokalne odnośniki zmienionych
dokumentów i `git diff --check`. Nie uruchamiano testów programu lub GUI.
Brak potrzebnych zmian wspólnych; integracja pozostaje zadaniem koordynatora.

---

# STM Domains — wnioski po 21–26 i przegląd dalszych kierunków

Data: **2026-11-01**. Na prośbę użytkownika przygotowano
[syntezę wyników i przegląd źródeł pierwotnych](research-after-training-pilot.md)
z użyciem skilla `research`. Użytkownik poprosił o porównanie obu wariantów:
bez etykiet treningowych oraz z niewielkimi ręcznymi wskazaniami relacji/granic.

Wniosek: dotychczasowe treningi nie dały przyjętego detektora. Lepsza
rekonstrukcja i zmiana cech nie wystarczyły do rozdzielenia domen.
Rekomendowany następny kierunek to ograniczona diagnoza przestrzennego
odczytu przy granicach, a warunkowo mały model uczony bezpośrednio relacji.
Przegląd uwzględnia już wykonane próby 12/19, żeby nie przedstawiać ich
powtórzeń jako nowych metod. Propozycje fizyczne i nowe gotowe modele
mają jawnie opisane ograniczenia oraz różnicę wobec wcześniejszych prób.

To materiał do decyzji, bez nowych ticketów, treningów, instalacji, modeli
lub importu danych. Nie zmieniono protokołów, wyników ani statusów 21–26.
Nie przyjęto detektora; 04 i 13 pozostają otwarte. Ręczne wskazania do
treningu wymagałyby osobnego wyboru tej ścieżki; dotychczasowe referencje
pozostają wyłącznie oceną. Dodatkowe MPP/STP nadal odłożone.

Zakres: nowa notatka oraz nawigacja README, mapa metod i to przekazanie.
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`,
baza **`a1fb554`**; commit dokumentacji podany w odpowiedzi końcowej.
Sprawdzenia: przegląd raportów i źródeł pierwotnych, lokalne odnośniki
zmienionych dokumentów oraz `git diff --check`. Nie uruchamiano testów
programu ani GUI — zmiana obejmuje wyłącznie dokumentację.
Brak potrzebnych zmian wspólnych; integracja pozostaje zadaniem koordynatora.

---

# STM Domains — wykonano adaptację DINOv2, 26

Data: **2026-11-01**. Na polecenie „wykonaj 26” zakończono
[ticket 26](issues/26-pretrained-self-supervised-adaptation.md),
**`resolved` jako eksperyment**. [Raport](pretrained-self-supervised-trial.md),
[protokół](pretrained-self-supervised-protocol.md),
[manifest](pretrained-self-supervised-manifest.json).
**Brak wymaganej poprawy domen względem oryginalnego DINOv2.**
Nie przyjęto detektora; 13 i 04 pozostają otwarte, dodatkowe dane odłożone.

6/6 fitów po 1000 kroków, trzy ziarna i transfer/transdukcja. Adaptowano
ostatni blok i normę DINOv2 ViT-S/14, lokalna samodestylacja z nauczycielem
EMA. Główny odczyt: `mean384` z kroku 1000, bez wyboru na walidacji. Oryginalne
wagi i FFT są bazami. Model zmienia cechy, bez stałej reprezentacji, ale F1
czterech głównych granic = 0 przed i po odmowach. Oba osobne werdykty
(reprezentacja przed, cały detektor po odmowach) są negatywne.

TTMAPP po odmowach: **transfer 0/174, transdukcja FH 4/782, MWS 0/782**.
To zakres częściowych referencji, nie czułość wykrywania molekuł.
Przed odmowami transfer/MWS zmniejsza fragmentację względem FFT:
mediana 27,73% wobec 77,55%, ale oryginalny DINO miał już 28,59%.
Zysk adaptacji względem niego nie przekracza progu i nie przechodzi
kontroli syntetycznych. Zachowany limit bramki nie wyjaśnia błędów granic
przed odmowami. Nie rozszerzono budżetu ani nie zastępowano ziaren.

Wyniki lokalne `.scratch/pretrained-ssl-26/`, galeria `index.html`:
117 obrazów, 10 reprezentacji, 2340 widoków grid48 i dwie figury.
14 040 pełnych predykcji + 1440 osobnych archiwów transferu (300 pustych
poza testem). Ocena: 14 520 rekordów, w tym 480 diagnostycznych mapowań.
Punkty w galerii to środki okien siatki, nie wykryte molekuły.
QtWebEngine: 55 sprawdzeń, 0 błędów JS; 5 zrzutów i obie figury obejrzane.

Sprawdzenia: 8 testów mechaniki; preflight 36 technicznych kroków i bitowe
wznowienie na 3 ziarnach, odrzucone wagi. Audyt 66 checkpointów, dokładnie 45
kluczy/kształtów/dtype, optymalizator/RNG/EMA i nienaruszona baza.
Audyt eksportów: 3 104 460 wierszy i 8 952 420 relacji. Zachowano bitowo 2592
plików FFT z 21, 432 pliki cache i 12 adapterów. Niezależny audyt potwierdził
2340 głównych wyników / 4680 etapów, 5616 porównań, 640 agregatów,
544 warunki korzyści, 8 werdyktów.
96 pomiarowych rekordów metryk FFT zgodnych z 21. Pierwsza próba niezależnego
audytu zatrzymała się przed odczytem referencji na błędnym liczniku; jawna korekta dodała
480 mapowań diagnostycznych. Obie próby i ich koszty zachowane, bez zmiany
predykcji, metryk, progów lub zamrożonych źródeł. Skorygowany audyt PASS.

Koszt: 297,31 s procesów treningowych (289,91 s wewnętrznych fitów, nie dodawać),
270,46 s CPU. Maksimum GPU 573 MB, RSS 2,09 GB, checkpointy 1,96 GB. Wszystko w limitach.
Istniejące środowisko netcat i zasoby 18 wystarczyły bez instalowania.
Ledger CPU etapów poza fitami oraz reszty wait4 zapisane bez podwójnego liczenia;
manifest jest migawką ukończonych procesów przed zamknięciem summarize.
Końcowy audyt integralności: 57 730 bieżących plików i 192 872 pliki
poprzedniej próby 25 bez zmian; 445 odnośników, 28 ticketów bez cykli.
Po tym audycie koszt etapów poza fitami wynosi 605,83 s CPU / limit 7200 s.
Pierwszy start audytu integralności wymagał poprawienia PYTHONPATH;
źródła nie zmienione, obie próby zachowane. Raport i ledger są osobne.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`.
Start **`9232eb5`**, podjęcie **`25caf81`**, źródła przed fitami **`77bc6a2`**;
commit zakończenia w odpowiedzi końcowej. Prototyp zachowany na
`prototype/stmdomains-pretrained-self-supervised`.
[Odtworzenie](../../stmdomains/experiments/training/pretrained_ssl/README.md).
Dane/modele/wyniki poza Git; kod i raporty w zakresie Domains.
Bez zmian wspólnych, innych worktree, natywnego GUI lub publikacji.
Integracja pozostaje zadaniem koordynatora.

---

# STM Domains — wykonano maskowane odtwarzanie 25

Data: **2026-11-01**. Na polecenie „wykonaj 25” zakończono
[ticket 25](issues/25-masked-autoencoder-domains.md), **`resolved` jako eksperyment**.
[Raport](masked-autoencoder-trial.md), [protokół](masked-autoencoder-protocol.md),
[manifest](masked-autoencoder-manifest.json). **Lepsza rekonstrukcja nie dała
poprawy końcowych domen.** Odbiór 13 i jakość 04 pozostają otwarte;
26 i przygotowanie dodatkowych MPP/STP nadal niewybrane/odłożone.

12/12 fitów, 19 800 kroków, suma zapisanych czasów **349,86 s na RTX 5090**.
Mały AE32 identyczny z 21, maski blokowe 25/50%, trzy ziarna,
transfer/transdukcja. Te same dane 20, 24 znane klatki TTMAPP, 93 nowe
realizacje znanych kontroli. Bez instalacji. Główny kandydat mask50/grid48;
mask25, inne skale i centra pozostają diagnostyką.

Przy identycznej masce 50% mediana sparowanych redukcji błędu zakrytych
pikseli względem AE21 wynosi **58,80%**. To walidacja
wybierająca checkpoint, bez nowego dowodu generalizacji. TTMAPP po odmowach:
**transfer 0/174**, transdukcja **FH 4/782, MWS 0/782**. Cztery główne granice
syntetyczne mają F1 0 także przed odmowami. Częściowy zbiorczy zysk par
względem AE dotyczy mniejszej fragmentacji, bez kwalifikacji całej metody.
Transdukcyjny AE21 miał 600 kroków, nowe maskowane modele 1300; porównanie
nie izoluje maskowania przy identycznej liczbie aktualizacji.

Wyniki: `.scratch/masked-ae-25/`, galeria `index.html`. **44 928 predykcji**
i osobne 4608 archiwów transferu, w tym 960 pustych poza testem. Nakładki
pokazują środki okien siatki, nie wykryte molekuły. Samowystarczalny HTML
obejmuje 32 reprezentacje, 117 obrazów, siedem scenariuszy i dwie figury.
QtWebEngine: 143 sprawdzenia, zero błędów JS; pięć zrzutów obejrzanych.

Sprawdzenia: sześć testów maskowania; pełny stan i bitowo identyczne wznowienie
na trzech ziarnach; niezależne odtworzenie wejść i zgodność 15 600 wspólnych
kroków z AE21. Audyt eksportów sprawdził 9 934 272 wiersze; 18 144 pliki
predykcji baz, cache, cechy i adaptery zachowane bitowo. Zamrożono wyniki
przed oceną. Niezależny audyt: 7488 głównych rekordów, 14 976 etapów,
22 464 porównania, 672 rekordy baz zgodne z 21/22. Wszystkie audyty przeszły.
Nie uruchamiano ponownie dawnych treningów/testów ani natywnej aplikacji.

Pierwszy proces oceny w sandboxie przerwał SIGTERM (kod 143) po około
29 tys. rekordów. Przyczyna niepotwierdzona; zachowano zapis i obciążenie
budżetu 900 s CPU jako konserwatywną rezerwę, nie pomiar. Tę samą ocenę
ukończono poza sandboxem bez zmian numeryki, fitów lub predykcji:
177,05 s CPU, 4,28 GB RSS. Manifest oddziela zmierzone koszty od rezerwy
awarii; limit postprocessingu 7200 s pozostaje zachowany.
Zmierzone etapy poza fitami: 2002,12 s CPU; z rezerwą 2902,12 s.
Pomiar nie obejmuje w pełni procesów pomocniczych QtWebEngine.
Końcowo przeszło 192 872 hashów, 429 odnośników, graf 28 ticketów bez cykli
i `git diff --check`; pełne lokalne podsumowanie pozostało bitowo niezmienione.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`.
Start `0347455`, podjęcie `36d5cb1`, przypięte źródła/protokół **`b8fdc9a`**;
commit zakończenia w odpowiedzi końcowej. Prototyp zachowuje
`prototype/stmdomains-masked-autoencoder`. Instrukcja odtworzenia:
[README](../../stmdomains/experiments/training/masked_ae/README.md).
Dane, modele i duże wyniki lokalnie poza Git. Zakres wyłącznie Domains;
brak potrzebnych zmian wspólnych, publikacji i zmian innych worktree.
Integracja pozostaje zadaniem koordynatora.

---

# STM Domains — wykonano diagnozę kontekstu 24a

Data: **2026-11-01**. Na polecenie „wykonaj proponowaną próbę” zakończono
[24a](issues/24a-graph-context-boundaries.md), `resolved` jako eksperyment.
[Raport](graph-context-boundary-trial.md), [protokół](graph-context-boundary-protocol.md),
[manifest](graph-context-boundary-manifest.json). **Artefakt jednej sieci usunięty;
prawdziwe granice nadal błędne.** Nie przyjęto detektora, 13 i 04 pozostają otwarte.
25/26, dalsze treningi i dodatkowe MPP/STP nadal niewybrane/odłożone.

93 znane kontrole 24, 19 reprezentacji, FH/MWS, **3534 wyniki**, stałe 8350
centrów S24. Zamrożone modele SCE+scale transfer i własne inicjalizacje,
trzy ziarna; 0 nowych fitów, 0 kroków optymalizacji i 0 refitów adapterów.
Porównano oryginalne closed72, półotwarte halfopen72 i ablację root_only;
root57 pozostaje wspólną bazą. Nie przeliczano TTMAPP ani transdukcji.

Kryterium A: halfopen72 oraz root_only dają jedną domenę i **121/121**
przed/po odmowach we wszystkich ziarnach, solverach i stanach wag.
Kryterium B prawdziwych granic: niezaliczone wszędzie. C: zmienione wyuczone
modele mają regresje. Czysta faza FH poprawia medianę F1 0,327 → 0,399,
lecz błąd podziałów nadal 57,1% (wymagane ≤10%). Jitter fazy nie zyskuje
na halfopen; niezależne rzędy nadal fałszywie przypisane 300/300.
To diagnoza na znanych kontrolach, bez dowodu generalizacji lub przewagi uczenia.

Galeria `.scratch/graph-context-24a/index.html`: zapisany closed72 po lewej,
wybrana zmiana po prawej, te same wagi/ziarno/solver i mianowniki. Rzeczywiste
centra oznaczeń, przełącznik przed/po odmowach, wybór centrum z obrysem 72.
40 sprawdzeń QtWebEngine, zero błędów JS, trzy zrzuty obejrzane wizualnie.

Audyt techniczny: 3534 archiwa, 745 902 wiersze, niezmienione S24 i adaptery;
1302 bazowe archiwa predykcji i 651 cech bitowo zgodne z 24. Niezależny audyt
metryk: 3534 rekordy, 7068 etapów, 14 136 etapów porównań, 1178 agregatów,
14 kryteriów; wszystkie 1302 bazowe metryki zgodne z 24. Zamrożone źródła
numeryczne i artefakty 24 zachowane. Nie uruchamiano natywnej aplikacji ani
ponownie dawnych treningów/testów. Koszt etapów i ograniczenia pomiaru
CPU/RSS zapisano w manifeście i raporcie.
Suma zmierzonych etapów: 114,60 s CPU, szczyt 1,57 GiB RSS. Końcowe
sprawdzenie 21 883 hashów, 409 odnośników, grafu 28 ticketów bez cykli,
kompilacji modułów i `git diff --check` przeszło.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`.
Podjęcie `959fde3`, implementacja/protokół `ee73c83`; commit zamknięcia
w odpowiedzi końcowej. Prototyp zachowuje
`prototype/stmdomains-graph-context-boundaries`. Instrukcja odtworzenia:
`stmdomains/experiments/training/graph_context/README.md`. Wyniki lokalne poza Git.
Zakres wyłącznie Domains; brak zmian wspólnych, publikacji i zmian innych worktree.
Integracja pozostaje zadaniem koordynatora.

---

# STM Domains — wykonano grafowy eksperyment 24

Data: **2026-11-01**. Na bezpośrednie polecenie użytkownika wykonano
[24 — grafy otoczeń molekuł](issues/24-graph-self-supervised-domains.md),
status **`resolved`** jako zakończony eksperyment. [Raport](graph-self-supervised-trial.md),
[protokół](graph-self-supervised-protocol.md), [manifest](graph-self-supervised-manifest.json).
Nie wybrano detektora. 13 ma wynik 24, lecz pozostaje otwarty; 04 także.
25/26 i dodatkowe MPP/STP pozostają niewybrane/odłożone.

**9/9 fitów, 17 400 kroków, 122,86 s na RTX 5090**, bez nowych instalacji.
24 klatki TTMAPP i 93 świeże kontrole; wejściem są oznaczenia molekuł,
72 × 72 px kontekstu i geometryczna bramka 15. Transfer ma tylko 76 grafów
train i 27 validation; osobny test zawiera 204 centra z częściową referencją.
Transdukcja ma mianownik 1175. Te liczby nie są wykrywalnością molekuł
ani mianownikami poprzedniej siatki 21/22.

Nie wykazano przewagi nad geometrią i własną inicjalizacją. Główny FH
w transferze zachowuje **178–183/204**, ale scala wszystkie oceniane pary
różnych referencji; MWS po odmowach **0/204**. Transdukcja: FH 1070–1093/1175
ze znacznymi scaleniami, MWS 517–632/1175 wobec 815/1175 geometrii.
Są częściowe zyski na pojedynczych kontrolach, bez zaliczenia całej próby.
Brzegowe otoczenia grafu powodują fałszywy podział pełnej sieci także
bez uczenia. Pary przerwa materiału/brak oznaczeń mają identyczną geometrię
oraz wyniki. Typ, orientacja fizyczna i powierzchnia pozostają nieokreślone.

Galeria `.scratch/graph-ssl-24/index.html`: rzeczywiste centra, wybór modelu,
ziarna/podziału, osobny graf testowy i klikalne okno kontekstu. 117 obrazów,
19 wariantów, 6 scenariuszy; **78 interakcji QtWebEngine, zero błędów JS,
5 zrzutów obejrzanych wizualnie**. Duże wyniki i modele pozostają lokalne.

Sprawdzenia: zgodność cache 117 próbek, izolacja kontekstu i splitów,
174 checkpointy oraz 6000 par batchy, bitowo zgodne wznowienie. Zamrożono
4212 wyników przed referencjami. Audyt 4212+504 eksportów obejmuje 1 090 254
wiersze; niezależny audyt metryk odtwarza 4212 rekordów, 8424 etapów par,
6696 ocen granic i 792 warunki przewagi. Nie zmieniano wyników po ocenie.
Zmierzony koszt pozostałych etapów wynosi 241,25 s CPU; CPU/RSS pierwszego
przygotowania nie był mierzony, a jego identyczny replay opisano osobno.
Przed pierwszym fitem poprawiono techniczny błąd typu ścieżki kontroli hashów,
bez zmiany modelu lub parametrów; wcześniejszy plan i dowód zachowano.
395 lokalnych odnośników, 27 ticketów i graf bez cykli, kompilacja modułów
oraz `git diff --check` przeszły. Nie uruchamiano natywnej aplikacji ani
ponownie starych treningów/testów.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`.
Podjęcie **05d32f2**, implementacja i protokół **f53611b**; commit raportu
w odpowiedzi końcowej. Prototyp zachowuje
`prototype/stmdomains-graph-self-supervised`. Zakres wyłącznie Domains,
bez potrzebnych zmian wspólnych. Integracja przez koordynatora;
nie scalano, nie publikowano ani nie zmieniano innych worktree.

---

# STM Domains — decyzja 23 zakończona

Data: **2026-11-01**. Użytkownik zaakceptował rekomendację i zakończenie
obecnego pilota. [Ticket 23](issues/23-training-comparison-and-next-step.md)
ma status **`resolved`**: porównanie i decyzja wykonane, bez wyboru detektora.
[Raport](training-comparison-and-next-step.md) oraz manifest i audyt
z commita **`f5d9b56`** pozostają podstawą rozstrzygnięcia.

24–26 pozostają `open`, **niewybrane i warunkowe**. Samo zakończenie 23
nie włącza ich do kolejki ani zależności 13. Dodatkowe MPP/STP są odłożone;
nie wybrano nowej próby, budżetu lub większego sprzętu. 04 i 13 pozostają
otwarte. Zachowujemy częściowe korzyści i wskazane luki porządku/granic;
nie przyjęto metody klasycznej przez brak zwycięzcy uczenia.

Zaktualizowano datowaną odpowiedź, raport, mapę i indeks, warunki 24–26,
README, stan odbioru 13 oraz notatki o eksperymentach i danych.
Sprawdzenia obecnej zmiany: lokalne odnośniki, statusy i graf zależności,
wykluczenie niewybranych rozszerzeń z kolejki oraz `git diff --check`.
Nie ponawiano treningów, agregacji, testów kodu ani GUI; ta zmiana zapisuje
zaakceptowaną decyzję. Audyty analizy są opisane w poprzednim przekazaniu.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`, baza
`f5d9b56`; commit zamknięcia w odpowiedzi końcowej. Zapis roboczy działa.
Brak zmian wspólnych, kodu i artefaktów eksperymentów. Zapis metadanych Git
wymaga dostępu poza sandboxem; integracja przez koordynatora.

---

# STM Domains — porównanie 23 przygotowane do decyzji

Data: **2026-11-01**. Na polecenie użytkownika podjęto
[23 — porównanie i następny krok](issues/23-training-comparison-and-next-step.md).
Status **`claimed`**: analiza jest wykonana, końcowa decyzja użytkownika
pozostaje do omówienia zgodnie z trybem HITL i warunkiem zakończenia ticketu.
[Raport](training-comparison-and-next-step.md),
[manifest](training-comparison-manifest.json). Rekomendacja: zakończyć
obecny pilot bez detektora i pozostawić 24–26 niewybrane. Nie aktywowano
nowych fitów, danych lub budżetu. 04 i 13 pozostają otwarte.

Główna wspólna ocena 21/22: transfer 0/174, transdukcja najwyżej 4/782.
Zachowana bramka ze spójnością narzuca właśnie takie maksimum niezależnie
od cech; osobną luką są granice przed odmowami, w tym F1=0 dla SSL z32.
Zachowano częściowy zysk AE/FH przed odmowami: mediana poprawy błędu par
7,57 pp w transferze, wszystkie trzy ziarna dodatnie. rVAE/FH transdukcyjny
poprawia medianę o 7,21 pp, lecz tylko 2/3 ziaren i kosztem rozdrobnienia.
Żadna uczona konfiguracja nie spełnia całych kryteriów kontynuacji.
21a i wcześniejsze 15–19 pozostają oddzielne z powodu różnych kontroli,
przygotowania i mianowników; nie tworzymy pozornego rankingu procentów.

Nowy moduł `stmdomains/experiments/training/comparison.py` czyta zapisane
oceny. `.scratch/training-comparison-23/` zawiera pełne `tables.md`, JSON,
10 CSV i audyt wejścia. Nie zmieniono zamrożonych źródeł, modeli, progów,
predykcji ani galerii 21/21a/22. Punkty siatki opisano jako środki okien,
a procent przypisań jako udział ocenialnych miejsc, nie wykrywalność molekuł.

Sprawdzenia: 56/61/74 przypięte pliki prób, 112 identycznych agregatów FFT,
14 zgodnych baz TTMAPP, 83 grupy mianowników; wszystkie 14 artefaktów
porównania odtworzone bajt w bajt w osobnym katalogu. Kompilacja modułu,
lokalne linki, 27 ticketów i graf bez cykli oraz `git diff --check` przeszły.
Niezależne przeglądy historii i interpretacji uwzględnione. Nie ponawiano
treningów, testów aplikacji ani GUI; korzystamy z wcześniejszych odbiorów.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`, baza
`865bfbc`, podjęcie `b215616`; commit zestawienia w odpowiedzi końcowej.
Zapis roboczy sprawdzony. Zakres wyłącznie Domains, bez potrzebnych zmian
wspólnych. Zapis metadanych Git wymaga wykonania poza sandboxem; integracja
przez koordynatora. Duże wyniki i modele pozostają lokalne.

---

# STM Domains — wykonano lokalny SSL, ticket 22

Data: **2026-10-31**. Na polecenie użytkownika wykonano
[22 — lokalny SSL](issues/22-local-self-supervised-domains.md), status
**`resolved`** jako zakończony eksperyment, bez przyjęcia detektora.
[Raport](local-self-supervised-trial.md), [manifest dowodów](local-self-supervised-manifest.json).
Następny jest **23** — wspólne zestawienie i decyzja. 04 i 13 pozostają
otwarte; 24–26 oraz dodatkowe MPP/STP nadal wymagają osobnej decyzji.

**9/9 fitów, 18 000 kroków, 452,04 s**, bez restartów i instalacji.
Sześć fitów transferowych z16/z32 oraz trzy transdukcyjne z32; własne
zapisane inicjalizacje są kontrolą bez uczenia. Razem 21/22 wykorzystały
27/27 pierwotnych fitów; 21a ma oddzielny budżet. Zachowano parametry
20, bramkę i bazę FFT oraz trzy skale i diagnostykę centrów.

SSL zmienia cechy: główny z32 ma efektywny rząd około 114–120 wobec
26–62 dla inicjalizacji i słabszą korelację z jasnością. **Nie poprawia
końcowych domen**: transfer 0/174 dla FH/MWS i wszystkich ziaren;
transdukcja FH 4/782 (0,51%), MWS 0/782, bez przewagi nad FFT.
Przed odmowami SSL z32 scala różne referencje transferu i ma F1=0
na czterech kontrolach granic. Żadna uczona konfiguracja nie spełnia
kryteriów kontynuacji. Niezależne rzędy nadal tworzą fałszywe domeny.

Osobna diagnoza zapisanej bramki i minimum czterech połączonych miejsc
wykazała maksimum **0/174 w transferze i 4/782 w transdukcji niezależnie
od cech**. To analiza ograniczenia istniejącego wyniku, bez zmiany progów,
nowego detektora lub powrotu do strojenia 19. Do 23 przekazujemy dwie
luki: granice przed odmowami oraz geometryczny limit końcowych przypisań.

21 420 predykcji, 22 236 ocen z diagnostyką mapowania na centra.
Przed oceną zamrożono 84 595 lokalnych i 115 zewnętrznych artefaktów.
Sprawdzono wszystkie 100 299 hashy 21 i dokładną zgodność 2808 archiwów
FFT we wszystkich skalach/reżimach. 189 checkpointów, 6000 par batchy,
wspólne inicjalizacje i wybór walidacyjny przeszły audyt. Wszystkie
1530 sprawdzeń niezmienności siatki przy brakach centrów zaliczono.

**181 testów**, składnia wrappera i wszystkie jego etapy wykonane osobno.
Galeria `.scratch/local-ssl-22/index.html`: 105 obrazów, 17 wariantów;
**89 interakcji, zero błędów JS**, pięć obejrzanych zrzutów i trzy PNG.
Nie wykonano odbioru natywnego GUI. Pomierzone etapy 22: 1031,08 s CPU;
łącznie 21+22: **2088,67 / 7200 s CPU**. Artefakty około 7,19 GiB poza Git.
Kontrole były już oglądane w 21, a TTMAPP jest jedną skorelowaną akwizycją;
to ocena rozwojowa częściowych referencji, nie globalna trafność obrazu.

Kod: `stmdomains/experiments/training/local_ssl/`;
[odtworzenie](../../stmdomains/experiments/training/local_ssl/README.md).
Źródło na `prototype/stmdomains-local-self-supervised`. Zmiany wyłącznie
w zakresie Domains; stare źródła 21/21a i współdzielone moduły zachowane.
Integracja przez koordynatora, bez publikacji modeli lub wyników.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`,
baza `5755316`, podjęcie `8920f71`. Commit wykonania podany w odpowiedzi
końcowej. Dostęp do zapisu sprawdzono; GPU, QtWebEngine i zapis metadanych
Git wykonano z wymaganym dostępem poza sandboxem.

---

# STM Domains — wykonano próbę 21a

Data: **2026-10-31**. Na polecenie użytkownika wykonano
[21a — dekoder i regularyzacja rVAE](issues/21a-rvae-decoder-and-kl.md),
status **`resolved`** jako zakończony eksperyment, bez przyjęcia detektora.
[Raport](rvae-decoder-kl-trial.md), [manifest dowodów](rvae-decoder-kl-manifest.json).
Następne jest **22**, potem **23**; dziewięć fitów SSL pozostaje dostępne.

Ukończono 2/2 runy diagnostyczne i 9/9 pełnych fitów transferowych z32:
22 000 kroków, 336,34 s treningu, bez restartów lub dodatkowych instalacji.
Macierz dekoder × KL zachowuje oryginalne modele 21 jako punkt odniesienia.
Słabsze KL obniża medianę MSE walidacji o około 14%, lecz rekonstrukcje
pozostają wygładzone, a kąt nie odtwarza znanych orientacji. Nawet bez KL
mała próba zapamiętania nie odtworzyła szczegółów molekularnych w tym budżecie.
Żaden nowy wariant z FH/MWS nie spełnia kryteriów kontynuacji; końcowe
TTMAPP nadal **0/174** przypisań. Odmowy i fałszywe domeny kontroli
pozostają problemem; poprawa rekonstrukcji jest wynikiem częściowym.

Ocena obejmuje główną siatkę 48 px, 81 nowych realizacji kontroli oraz
znane TTMAPP; to ocena rozwojowa jednej akwizycji. 3360 predykcji zamrożono
przed oceną: 14 370 lokalnych i 50 zewnętrznych artefaktów. Wszystkie
100 299 hashy pierwotnej próby 21 sprawdzono przed rozpoczęciem; 672 tablice
wyników bazowych na TTMAPP są dokładnie identyczne. Bramka, podział danych,
źródła i artefakty 21 pozostały niezmienione. Nie rozpoczęto 22 ani nowych
prób bramki; dodatkowe MPP/STP pozostają odłożone.

Sprawdzenia: **161 testów**, 220 checkpointów, identyczne inicjalizacje
wspólnych warstw/batche, właściwy wybór walidacyjny i niezależność wejścia
od referencji. Galeria: **112 interakcji, zero błędów JS**, pięć obejrzanych
zrzutów; obejrzano też PNG rekonstrukcji i diagnostyki. Koszt pomierzonych
etapów przygotowania, oceny i galerii: **150,53 s CPU** wobec limitu 7200 s.
Wrapper sprawdzono składniowo; wszystkie jego etapy wykonano osobno,
bez ponawiania 11 treningów. Nie wykonywano odbioru natywnego GUI.

Kod badawczy: `stmdomains/experiments/training/rvae_followup/`;
[odtworzenie](../../stmdomains/experiments/training/rvae_followup/README.md).
Wyniki lokalne: `.scratch/rvae-21a/index.html`, `evaluation/`, `figures/`,
checkpointy i diagnostyka; całość około 1,27 GiB poza Git. Źródło zachowuje
gałąź `prototype/stmdomains-rvae-decoder-kl`. Zmiany wyłącznie w Domains,
bez potrzeb wspólnych modułów; integracja przez koordynatora.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`,
baza `773ff5f`, podjęcie zadania `526c61c`. Commit wykonania podany
w odpowiedzi końcowej. GPU, QtWebEngine i zapis metadanych Git wymagały
uruchomienia poza sandboxem; żadne modele ani wyniki nie były publikowane.

---

# STM Domains — dodano osobną próbę 21a

Data: **2026-10-31**. Na polecenie użytkownika dodano
[21a — dekoder i regularyzacja rVAE](issues/21a-rvae-decoder-and-kl.md),
status **`open`**, bez rozpoczęcia treningów. Jeden ticket obejmuje krótką
diagnostykę odtwarzania wycinków oraz ograniczoną macierz dekoder × KL.
Aktualna kolejność to **21a → 22 → 23**; negatywny wynik 21a również
pozwala przejść do 22. 19, 20 i 21 pozostają `resolved`.

21a ma osobny budżet: najwyżej dwa krótkie runy diagnostyczne i dziewięć
nowych fitów transferowych z32 (trzy nowe konfiguracje × trzy ziarna).
Punktem odniesienia są zachowane modele 21. Dla 22 pozostaje dziewięć
fitów z pierwotnego budżetu 27; dodatek nie zmienia planu SSL, protokołu
20 ani artefaktów 21. Nowe kontrole syntetyczne oceniać po zamrożeniu
wariantów, TTMAPP traktować jako już oglądaną ocenę rozwojową. Bez strojenia
bramki, dodatkowych MPP/STP i nowych instalacji. Poprawa reprezentacji
przed odmowami nie oznacza poprawy końcowego detektora.

Zaktualizowano indeks, diagram zależności, mapę metod, README oraz linki
w 21/22/23. W poleceniu wyboru ticketów uwzględniono identyfikatory z literą.
Sprawdzenia: lokalne odnośniki, spójność ID/statusów/zależności i diagramu,
brak cykli oraz `git diff --check`. Bez testów kodu, GUI lub nowych fitów:
zmiana dotyczy wyłącznie dokumentacji i planu. Nie zgłoszono potrzeb
wspólnych modułów; integracja przez koordynatora.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`,
baza `9d729b1`. Commit tej aktualizacji podany w odpowiedzi końcowej.

---

# STM Domains — wykonana próba AE/rVAE, issue 21

Data: **2026-10-31**. Na polecenie użytkownika wykonano zamkniętą próbę
[21](issues/21-autoencoder-domains.md), status **`resolved`** jako zakończony
eksperyment, bez przyjęcia detektora. [Raport](autoencoder-domains-trial.md),
[manifest dowodów](autoencoder-domains-manifest.json).
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`, baza
`77126f2`. Commit w odpowiedzi końcowej; kopia źródła prototypu na
`prototype/stmdomains-autoencoder-domains`. Integracja przez koordynatora.

18/18 fitów, 29 700 kroków, 469,09 s treningu; bez restartów lub instalacji.
12 transferowych fitów AE/rVAE z16/z32 i sześć transdukcyjnych z32.
25 200 predykcji, 26 160 ocen z pomocniczym mapowaniem centrów. Właściwe
modele, FFT/ACF, train-only PCA, FH/MWS, odmowy, ocena i galeria są
w `stmdomains/experiments/training/`; nie rozpoczęto lokalnego SSL.

**Wynik negatywny:** żaden główny z32 nie spełnia kryteriów kontynuacji.
Końcowe TTMAPP: transfer 0/174, transdukcja najwyżej 4/782 (0,51%),
bez dostępnego porównania błędów po odmowach. Wspólna bramka przepuszcza
tylko około 1,5% pełnych okien TTMAPP, a zarazem tworzy fałszywe domeny
na niezależnych rzędach. Przed odmowami pozostają scalenia i rozdrobnienie.
rVAE koduje głównie jasność, bez wiarygodnego kąta sieci. Dokładne wartości,
kontrole granic, trzy ziarna i mianowniki są w raporcie oraz lokalnych CSV.

Sprawdzenia: **143 testy przeszły**, bitowo identyczne wznowienie AE/rVAE,
297 checkpointów i wybór walidacyjny sprawdzone. Audyt eksportu zachował
tablice/relacje/przypisania. 100 299 hashy zweryfikowano przed odczytem
referencji. 1800/1800 zgodnych porównań siatki przy brakach centrów.
Galeria: 15 interakcji, zero błędów JS; obejrzano finalne screenshoty/PNG.
Brak odbioru natywnego GUI. Dane, wagi i duże wyniki poza Git.

Lokalnie `.scratch/autoencoder-21/`: `index.html`, `evaluation/`,
`feature-diagnostics.json`, `figures/`, checkpointy i zamrożony manifest.
Odtworzenie opisuje [AUTOENCODER.md](../../stmdomains/experiments/training/AUTOENCODER.md).
Zmiany tylko w zakresie Domains; brak potrzebnych wspólnych zmian.
GPU i zapis metadanych Git wymagają wykonania poza sandboxem.

Następne **22**, potem **23**; 24–26 warunkowe. Zachować wspólny protokół,
bez strojenia na kontrolach ujawnionych w 21. Dla 22 pozostaje dziewięć
fitów ze wspólnego budżetu 27; uwzględnić koszt/checkpointy 21, w tym
1056,61 s zmierzonego CPU przygotowania, inferencji, podziału i oceny.
Porównanie SSL przed odmowami może ocenić relacje, ale ta sama bramka
nadal ogranicza końcowe coverage. Dodatkowe MPP/STP pozostają odłożone.
Jedna akwizycja, niepewna rejestracja i częściowe referencje nie rozstrzygają
generalizacji na inne materiały. Nie otwieramy ponownie 19.

---

# STM Domains — najpierw pilot na obecnych danych

Data: **2026-10-31**. Użytkownik zdecydował, aby najpierw wykonać 21/22
na obecnym TTMAPP i kontrolach przygotowanych w 20. Dodatkowe MPP/STP
przygotuje później, jeśli wyniki będą interesujące. Audyt archiwum nie
blokuje obecnych prób. W 23 oceniamy korzyść według zamrożonych kryteriów
oraz potrzebny zakres ewentualnego rozszerzenia danych. Wynik obecnego
pilota nie rozstrzyga przenoszenia na inne molekuły/podłoża.

Uaktualniono README, mapę metod, notatkę o danych i ticket 23.
Protokół 20 i statusy pozostają bez zmian: 19/20 `resolved`, 21/22/23 `open`.
Ta aktualizacja zapisuje kolejność prac; nie uruchomiono nowych treningów.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`, baza
`b7ca02a`. Commit dokumentacji w odpowiedzi końcowej; integracja przez
koordynatora. Sprawdzenia: lokalne odnośniki zmienionych dokumentów oraz
`git diff --check`. Bez testów kodu lub GUI; zmiana dotyczy tylko dokumentacji.
Brak potrzebnych zmian wspólnych i nowych instalacji.

---

# STM Domains — wymagania dla dodatkowych danych MPP/STP

Data: **2026-10-31**. Na pytanie użytkownika przygotowano
[zalecenia dotyczące zbioru](research-training-data-requirements.md),
z użyciem skilla `research` i źródeł pierwotnych. Użytkownik potwierdził,
że archiwum obejmuje różne molekuły/podłoża, a rozmiary skanów znajdują się
w metadanych. Nowych plików nie udostępniono ani nie audytowano.

Pojedyncze STP mogą być niezależnymi obrazami treningowymi bez kolejności
czasowej i etykiet domen. Potrzebne są skala obrazu, identyfikacja układu,
kanału oraz grup powiązanych akwizycji/pól. Liczby 20–50 pól do audytu
oraz 100–300 do szerszego pilota są roboczymi celami organizacyjnymi,
nie empirycznie ustalonym minimum. Ostateczną ilość należy ocenić na
odłożonych akwizycjach; wycinki jednego pola nie są niezależnymi pomiarami.

Kod ma czytniki MPP/STP, lecz obecny adapter eksperymentu20 jest celowo
ograniczony do audytowanego TTMAPP. Zbiór heterogenicznych skanów wymaga
osobnego adaptera z metadanymi każdego obrazu, sprawdzenia orientacji/skali
i nowego manifestu. Nie wolno udawać jednej serii z metadanymi pierwszego
obrazu. Nie zmieniono kodu, wspólnych modułów ani zatwierdzonego protokołu.

Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`, baza
`0ab27c6`. Commit dokumentacji w odpowiedzi końcowej; integracja przez
koordynatora. Statusy pozostają: 19/20 `resolved`, 21/22 `open`.
Sprawdzono źródła, czytniki, lokalne odnośniki i `git diff --check`.
Bez nowych eksperymentów, instalacji, testów kodu lub GUI.

---

# STM Domains — przygotowanie treningu, issue 20

Data: **2026-10-31**. Na polecenie użytkownika wykonano
[20](issues/20-self-supervised-training-preparation.md), status **`resolved`**.
[Raport](self-supervised-training-preparation.md),
[protokół](self-supervised-training-protocol.md),
[manifest](self-supervised-training-manifest.json).
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/start`, baza
`fab9877`. Commit kodu/dokumentacji podany w odpowiedzi końcowej;
do integracji przez koordynatora na `stm-next`. Zachowano poprzednie przekazania.

Przygotowano odtwarzalny moduł badawczy `stmdomains/experiments/training`:
24 pełne raw klatki, 38 622 rekordy siatki/centrów w trzech skalach,
25 530 wycinków z pełnym wsparciem. Transfer ma rozdzielone bloki czasu
oraz pasy przestrzenne po zapisanej rejestracji; transdukcja osobny fit.
Zarezerwowano 81 nowych kontroli syntetycznych. Zamknięto protokół relacji,
wyjść, porównania 2 × 2, kryteriów oraz budżetu 27 przyszłych fitów w 21/22.
Nie uruchomiono właściwych modeli ani porównań domen tych ticketów.

Na RTX 5090 w `netcat` wykonano krótki test obliczeń i checkpointów:
trzy ziarna, sześć kroków vs trzy + zapis + nowy proces + trzy,
bitowo identyczne wagi, Adam/scheduler, RNG, batch IDs i straty.
Próba obejmowała 99 technicznych kroków małego AE. Sprawdzono też
reparametryzację, lokalną wariancję/kowariancję i obrót współrzędnych
przed MLP. Ścisły deterministyczny CUDA backward `grid_sample` nie działa;
plan rVAE przewiduje dekoder współrzędnych. Właściwy rVAE/SSL nadal wymaga
własnego krótkiego sprawdzenia w 21/22.

Sprawdzenia: **78 testów STM Domains przeszło**; odtworzenie tablic i geometrii
24 klatek z MPP/sesji, 25 530 hashy wycinków, 18 432 identyczne rekordy
siatki po usunięciu centrów. Pełne przygotowanie i manifest są identyczne
przy blokadzie referencji. Wrapper wykonany od początku do końca, obejrzano
rysunek geometrii. Końcowy GPU probe: 13,16 s; batch64 3,13–3,18 ms/krok,
91 MiB tensorów / 96 MiB rezerwy. To proxy, nie prognoza kosztu pełnych modeli.
Sprawdzenia dokumentacji obejmują linki, statusy, manifest i `git diff --check`.
Bez testów natywnego GUI oraz oceny skuteczności detektora.

Artefakty lokalne: `.scratch/training-20/`, około 118 MB z kopią weryfikacyjną;
`evidence.json`, `geometry.png`, wejścia, kontrole i checkpointy. Polecenie
odtworzenia w raporcie oraz README modułu. W Git wyłącznie kod, testy,
protokół i mały manifest. Nie instalowano pakietów lub wag. GPU i operacje
zapisu Git wymagają w tej sesji wykonania poza sandboxem; pliki tego worktree
pozostają zapisywalne. Nie zgłoszono zmian wspólnych ani wymagań aplikacji.

Ograniczenia: tylko 96 okien siatki48 train, nakładające się skale/okna,
jedna akwizycja, słaba rejestracja; bufor8px nie jest skalibrowanym błędem
położenia. Nie wolno ogłaszać niezależnej generalizacji lub traktować braku
referencji w części transferu jako błędu0. Następne: **21 i 22 niezależnie,
potem 23**. 19 pozostaje zakończony; 04/13 oraz implementacja szkieletu
pozostają otwarte. Viewer i współdzielone moduły bez zmian.

---

# STM Domains — przyjęcie usprawnień planu 20–23

Data: **2026-10-31**. Użytkownik zatwierdził rekomendacje
[badania](research-domain-plan-improvements.md) i polecił dodać je do planu.
Uzupełniono aktywną treść 20–23: protokół relacji i wyników, pilot granic
w 21/22, ograniczone porównanie 2 × 2 oraz kryteria kontynuacji i odmów.
Mały AE pozostaje punktem odniesienia, rVAE bada obrót, lokalne SSL — cechy
użyteczne przy granicach. MWS jest kandydatem do ograniczonego porównania,
a wariant przewidywalności inspirowany INPAINTAFF pozostaje opcjonalny.

Zaktualizowano mapę, README, indeks/diagram, wcześniejszy plan-odnośnik,
adnotację przyjęcia badania i przekazanie do odbioru 13. Kolejność to
**20 → 21 i 22 → 23**, potem wyłącznie wybrane rozszerzenia 24–26.
Nie powstało zadanie 20a. Statusy i zależności nie zmieniły się: 19
`resolved`, 20–23 `open`, nierozpoczęte. Nie uruchomiono eksperymentu.

Własny worktree `/tmp/netcat-stmdomains-domain-training-plan`, gałąź
`domains/domain-training-plan`, baza `06b1772`. Commit planu w odpowiedzi
końcowej; przekazanie do `domains/start`, integracja przez koordynatora.
Zachowano historię tego pliku. Bez zmian wspólnych, aplikacji lub Viewer.

Sprawdzenia: spójność zakresu z zatwierdzonym badaniem, lokalne odnośniki
i kotwice, zgodność statusów/zależności z bazą oraz `git diff --check`.
Bez testów kodu lub GUI — zmiana dotyczy dokumentacji planu, nie oceny
skuteczności nowej metody. Wartości kryteriów i budżet ustali wykonanie 20.

---

# STM Domains — badanie usprawnień planu

Data: **2026-10-31**. Na polecenie użytkownika wykonano przegląd według
skilla `research`: [raport](research-domain-plan-improvements.md).
Źródła pierwotne: podział grafu MWS/multicut, rozdzielenie klastrów
i instancji SEM, cechy STM/SSL, INPAINTAFF i ocena błędów/odmów.
Oddzielono dowody z innych rodzajów mikroskopii od hipotez dla TTMAPP.

Główna rekomendacja: ukierunkować 21/22 na lokalne relacje i granice;
oddzielnie oceniać wpływ cech, podziału przestrzennego i odmów, z małym
porównaniem 2 × 2. 19 już obejmowało graf FH i krawędzie — nie powtarzać
tej serii jako rzekomo nowego pomysłu. MWS jest kandydatem do ograniczonej
próby relacji przyciągających/odpychających, nie gotowym detektorem STM.
Katalog typów, materiał i wiarygodność pozostają osobnymi informacjami.
Raport proponuje doprecyzowanie 20–23; nie zmieniono ticketów, zależności
ani statusów. 19 nadal `resolved`, 20 nierozpoczęte, 24–26 warunkowe.

Własny worktree `/tmp/netcat-stmdomains-domain-plan-research`, gałąź
`domains/domain-plan-research`, baza `f444b2a`. Commit dokumentacji
w odpowiedzi końcowej; przekazanie do `domains/start`, integracja przez
koordynatora. Historia tego pliku zachowana, bez zmian wspólnych/Viewer.

Sprawdzenia: lektura publikacji/kodu i istniejących raportów, osobny audyt
zgodności zaleceń z historią oraz kontrola lokalnych linków i `git diff --check`.
Nie wykonywano eksperymentu, treningu, instalacji, testów programu ani GUI.
Żadna rekomendacja nie jest wynikiem potwierdzonej poprawy na STM.

---

# STM Domains — galeria zapisanych propozycji domen

Data: **2026-10-31**. Na prośbę użytkownika wyeksportowano istniejące wyniki
15/16 do `.scratch/domain-examples/index.html` w worktree Domains.
[Opis, liczebności i pochodzenie](saved-domain-examples.md). Trzy klatki
TTMAPP (250, 259, 268), kontrola dwóch orientacji, porównania i osobne PNG,
CSV oraz oryginalne JSON przypisań. To propozycje grup molekuł, bez konturów
i powierzchni. Nie zmieniano parametrów i nie uruchamiano nowych metod.
19 pozostaje `resolved`, 20 nierozpoczęte; aplikacja bez zmian.

Własny worktree `/tmp/netcat-stmdomains-domain-examples`, gałąź
`domains/domain-examples`, baza `022a518`. Commit dokumentacji w odpowiedzi
końcowej; przekazanie do `domains/start`, integracja przez koordynatora.
Galeria, eksportujący skrypt i manifest z hashami pozostają lokalne poza Git.
Zachowano wcześniejszą historię tego pliku. Nie są potrzebne zmiany wspólne.

Sprawdzono 2344 przypisania według ID/pozycji, zgodność z pierwotnymi
predykcjami, 24 rekordy źródłowe i osiem identycznych kopii JSON. Osobny audyt
potwierdził eksport, geometrię i liczniki. Obejrzano PNG, sprawdzono hashe
publikacji lokalnej, odnośniki i `git diff --check`. Bez nowych obliczeń metod,
treningu, testów aplikacji ani odbioru GUI. Wyniki nie dowodzą ogólnej
skuteczności segmentacji TTMAPP.

---

# STM Domains — zamknięcie serii analiz 19

Data: **2026-10-31**. Na wyraźne polecenie użytkownika podsumowano ustalenia
w [tickecie 19](issues/19-frozen-feature-domains.md) i zmieniono jego status
na **`resolved`**. Gałąź `domains/close-issue-19`, baza `c7cda73`, worktree
`/tmp/netcat-stmdomains-close-19`. Commit dokumentacji w odpowiedzi końcowej;
do `domains/start`, następnie integracja przez koordynatora.

Zakończono serię badań FCN/DINO i dalszej diagnostyki, bez przyjęcia detektora.
Zachowano wnioski o reprezentacji, porządku, bazie/okresie, tolerancji,
fazie/granicach, kompletności oznaczeń, motywie oraz obecności materiału.
Sprawdzone składniki i kontrole pozostają punktami odniesienia; nie dowodzą
ogólnego wykrywania domen TTMAPP ani nieskuteczności całego ML.

Zaktualizowano bieżący stan README, mapy, indeksu, przekazanie do 20 i odbioru
13 oraz adnotację zamknięcia w ostatnim raporcie. Wcześniejsze raporty,
manifesty i wpisy historyczne zachowano; stare statusy opisują chwilę próby.
20 pozostaje `open`, nierozpoczęte, do osobnego podjęcia. Jakość 04,
odbiór 13 i druga mapa pozostają otwarte. Nie uruchomiono kolejnych prób,
treningu ani zmian aplikacji. Źródła ostatniej próby: `25b270e`, dokumentacja
wyników: `c7cda73`; nie przenoszono kodu prototypu do programu.

Sprawdzenia tej zmiany: zgodność podsumowania z raportami i niezależny
przegląd wniosków, statusy/decyzje, lokalne odnośniki oraz `git diff --check`.
Nie powtarzano obliczeń, testów kodu ani GUI: zmiana dotyczy wyłącznie
zamknięcia dokumentacyjnego. Wyniki wcześniejszych sprawdzeń pozostają
w raportach prób. Nie są potrzebne zmiany wspólne; Viewer pozostaje
w zakresie osobnej sesji.

---

# STM Domains — motyw i kompletność oznaczeń, issue 19

Data: **2026-10-31**. Dokumentacja `domains/motif-completeness`, baza
`559daaf`, worktree `/tmp/netcat-stmdomains-motif`. Źródła:
**`prototype/stmdomains-motif-completeness`, `25b270e`**, baza `b450c4f`.
Prototyp pozostaje osobno; nie scalać go do aplikacji. Dokumentacja do
`domains/start`; końcowy commit w odpowiedzi użytkownika. Integrację do
`stm-next` prowadzi koordynator. Nie zmieniono Viewer ani wspólnych modułów.

Wykonano [próbę motywu i kompletności](motif-completeness-trial.md),
[manifest](motif-completeness-manifest.json). Podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/motif-completeness/index.html`.
103 obrazy: 19 geometrii kalibracji, 24 pełne TTMAPP i 60 nowych kontroli;
7960 otoczeń, 581305 dopasowań, 47760 decyzji. Trzy warianty: dotychczasowe
F jednej pozycji, nowa ocena pozycji jednej sieci oraz wybór 1–3 pozycji.
Osobne dane do dopasowania, wyboru i końcowego testu, progi przed nowymi
kontrolami, referencje wyłącznie po zamrożeniu wyników.

Oddzielna ocena pozycji pomaga przy brakach oznaczeń: pojedyncza sieć
z nominalnie 60% braków daje 100/192 lokalnych akceptacji wobec 1/192 dla
F, przy 104 dostępnych modelach. Model par poprawia medianę zgodności pełnych
pozycji z .754 do .968. Jednocześnie dodaje fałszywe akceptacje niezależnych
rzędów: 9/192 i 16/192 po obrocie. Kontrola K3 jest bliska drobniejszej
sieci w tolerancji; nie potwierdza rozpoznawania trzech odrębnych składników.

TTMAPP: jedna pozycja i rozszerzony motyw oceniane przez S dają te same
7 akceptacji pierścienia i 5 nowych rzędów, przy wspólnym progu. W znanych
wnętrzach po jednej; wszystkie zaakceptowane modele rozszerzonego wariantu
mają K1. Nie wyznaczono domen, granic ani powierzchni. Brak nowych rzędów
jest osobnym wynikiem; dostępność zależy także od komórki. Pusta przerwa
i same braki oznaczeń dają identyczną geometrię, więc materiał wymaga obrazu.

**19 nadal `claimed`, do omówienia; 20 odłożone.** Zachowujemy użyteczne
składniki badawcze, bez przyjęcia detektora. Propozycja po omówieniu:
zakończyć tę serię diagnostyki i przejść do przygotowania treningu bez
etykiet. Treningu ani implementacji metody w aplikacji nie uruchomiono.

Sprawdzenia: 60 deterministycznych odtworzeń generatora i 33 kontrole par;
103 wejścia zgodne z hashami pełnych tablic. Niezależnie sprawdzono
1440 przypisań, 60 modeli gęstości, równoważne opisy, permutacje i brak
przecieku między dopasowaniem, wyborem i testem. Audyt wyników obejmuje
23880 wierszy/wyborów, 47760 decyzji, 3213 pól agregacji, 5661 pól CSV
i 94 niezależne oceny przewidywań. 103 pomiary i **47760 decyzji** identyczne po pełnym odtworzeniu
  z blokadą referencji; trzy ukończone partie. Pierwszy proces odtwarzania
  przerwano (kod 143); wszystkie partie obliczono ponownie od początku.
84 kontrole QtWebEngine, zero błędów JS, 399 kontroli agregatów podglądu
i 83778 kontroli eksportowanych wartości/modeli. Zrzut oraz wykres obejrzane.
Python/Bash sprawdzone, wrapper wykonany etapami. To sprawdzenia
eksperymentu, nie produkcyjnego GUI ani skuteczności detektora domen.

CPU, 4 procesy po jednym wątku BLAS. Kalibracja 45.82 s, syntetyki
109.39 s, TTMAPP 91.48 s; maksimum RSS procesu 120760 KiB, nie sumaryczny
szczyt. Bez GPU i nowych zależności. Artefakty są lokalne, poza Git;
źródła prototypu i dokumentacja wersjonowane na osobnych gałęziach.

Nie są potrzebne zmiany wspólne. Nadal otwarte: jakość 04, odbiór metod 13,
decyzja o dalszym zakresie 19 i wykonanie natywnego szkieletu. Uzgodniony
zapis/statystyki nie zostały przez ten eksperyment zaimplementowane.

Kopię 258 plików wynikowych wskazanych w manifeście (149895313 bajtów)
zweryfikowano SHA-256 w docelowym katalogu; poprzednie dane pozostają
pod wskazanym w manifeście lokalnym odsyłaczem.

---

# STM Domains — kandydaci baz i nowe powtórzenia, issue 19

Data: **2026-10-31**. Dokumentacja `domains/basis-candidates`, baza
`1a63188`, worktree `/tmp/netcat-stmdomains-basis-candidates`. Źródła:
**`prototype/stmdomains-basis-candidates`, `b450c4f`**, baza `481194a`.
Prototyp pozostaje osobno, nie scalać go do aplikacji. Dokumentacja
do `domains/start`; końcowy commit w odpowiedzi użytkownika. Integrację
do `stm-next` prowadzi koordynator. Nie zmieniono Viewer ani wspólnych modułów.

Wykonano [porównanie kandydatów baz i nowych rzędów](basis-candidates-trial.md),
[manifest](basis-candidates-manifest.json). Podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/basis-candidates/index.html`.
97 obrazów: 19 geometrii kalibracji, 24 pełne TTMAPP, 54 nowe syntetyki;
15152 otoczenia, 512272 dopasowania, 90912 decyzji. Osobne dane do
dopasowania, wyboru i końcowego sprawdzenia, bez ponownego dopasowania
po wyborze. Referencje wyłącznie do późniejszej oceny.

Dzielniki baz odzyskują prawidłowy okres w **9/9 celowanych kontrolach
R64**, z końcowym wynikiem 1; pojedyncza baza i same dodatkowe piki 0/9.
Przy R48 obszar wyboru nie zawiera informacji rozróżniającej okresy.
Na TTMAPP przy wspólnym progu R48 to samo jedno otoczenie w każdej
puli, R64 zero. Trzy wyniki przy własnym progu dzielników są skutkiem
łagodniejszej kalibracji, a nie zmiany wybranego modelu. Niezależne rzędy
nadal czasem przechodzą sprawdzian. Brak nowych rzędów pozostaje brakiem
oceny; sieć nie dowodzi obecności materiału. Nie wybrano metody do programu.

**19 nadal `claimed`, do omówienia; 20 odłożone.** Następna propozycja:
oddzielić zgodność motywu od kompletności oznaczeń, porównać jedno-
i wielopunktowy motyw z oceną złożoności poza dopasowaniem i wyborem.
Nie rozpoczęto kolejnej próby, treningu ani implementacji w aplikacji.

Sprawdzenia: 48 kontroli liczbowych, 54 odtworzenia generatora. Naprawiono
lokalnie niestabilne remisy indeksów/fazy/histogramu; powtórzono kalibrację
i pomiary. Niezależnie: 928 redukcji baz, 140 kontroli węzłów i Hungarian,
72 inwarianty, 1008 punktów porównania Python/JS, 1566 kontroli agregacji.
**97 pomiarów i 90912 decyzji** identycznych po odtworzeniu z blokadą
referencji. **86 kontroli QtWebEngine**, bez błędów JS; zrzut i wykres
obejrzane. Python/Bash sprawdzone, wrapper uruchomiony etapami. To odbiór
raportu badawczego, nie produkcyjnego GUI. Snapshot źródła pomiarów
i końcowe źródło mają identyczne drzewo składni — różnica tylko w komentarzu.

CPU, 4 procesy po 1 wątku: kalibracja 14.95 s, syntetyki 44.42 s, TTMAPP 31.22 s,
odtworzenie 86.52 s. Maksymalny RSS procesu 115652 KiB, nie łączny szczyt.
Bez GPU i nowych zależności. Ograniczenia: pojedynczy punkt w komórce,
stała tolerancja, braki oznaczeń obniżające wynik, mało niezależnych
geometrii, nakładające się okna. Regularne braki kolumn nierozróżnialne
od większego okresu na samych centrach. Źródła i dokumentacja w osobnych
gałęziach; dane lokalne. Kopia sprawdzona w `copy-verification.json`,
HTML/CSV/wykresy samodzielne; obliczenia wymagają poprzednich artefaktów.
Brak potrzeb zmian wspólnych modułów lub konfiguracji głównej.

---

## Poprzednie przekazanie — diagnostyka jakości

Data: **2026-10-31**. Dokumentacja `domains/fit-quality-diagnosis`, baza
`2a962df`, worktree `/tmp/netcat-stmdomains-fit-quality`. Źródła:
**`prototype/stmdomains-fit-quality`, `481194a`**, baza `946cfb4`. Prototyp
pozostaje osobno, nie scalać go do aplikacji. Dokumentacja do `domains/start`;
końcowy commit w odpowiedzi użytkownika. Integrację do `stm-next` prowadzi
koordynator. Nie zmieniono Viewer, produkcji lub wspólnych modułów.

Na polecenie użytkownika wykonano [diagnozę jakości](fit-quality-diagnosis.md),
[manifest](fit-quality-diagnosis-manifest.json). Podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/fit-quality-diagnosis/index.html`.
97 obrazów: 19 unikalnych geometrii negatywnych, 24 pełne TTMAPP, 54 nowe
syntetyki; 68184 oceny otoczeń i cztery kryteria. Ramki tylko do późniejszej
oceny. Tolerancje zadane przed próbą, nie estymowane z błędów modelu.

Wykazano dwie przyczyny: poprzedni wysoki próg wynikał z 2–3 niezależnych
rzędów wspólnych dla treningu i testu; naprzemienny podział proponuje czasem
podwojony okres. W idealnej sieci r48 dotyczy 83/184 dostępnych okien
z Q<.5, które mają Q>.9 po podaniu prawdziwej bazy startowej. Dwupunktowy
motyw ujawnia osobne ograniczenie pojedynczej sieci. Nowa statystyka
uwzględniająca tolerancję/liczebność nie daje ogólnej poprawy. TTMAPP
pozostaje nierozstrzygnięte; prosty ruch do ekstremum nie poprawia błędu
względem zachowanego modelu. Nie wybrano metody do aplikacji.

**19 nadal `claimed`, do omówienia; 20 odłożone.** Następna propozycja:
kilka kandydatów bazy, odróżnianie okresu od wielokrotności, ocena na nowych
powtórzeniach obu kierunków; osobne sprawdzenie złożoności motywu. Materiał
i szum pozostają osobnym wątkiem. Następnej próby ani treningu nie rozpoczęto.

Sprawdzenia: 23 kontrole liczbowe, 54 odtworzenia generatora; niezależny
audyt wykrył niezamierzoną przerwę w syntetyku 30°, poprawiono generator
i powtórzono świeże pomiary bez zmiany progów. **97 pomiarów / 68184 ocen /
272736 decyzji** identycznych w odtworzeniu z blokadą referencji.
Niezależnie: 30000 porównań najbliższego węzła, 24 inwarianty, całkowanie
16²→64² na 218 oknach bez zmiany decyzji. **108 kontroli QtWebEngine**,
42 obrazy, bez błędów JS; screenshot i wykres obejrzane. Python/Bash
sprawdzone składniowo, wrapper wykonany etapami. To kontrola raportu
badawczego, nie odbiór produkcyjnego GUI.

CPU, 4 procesy po 1 wątku: kalibracja 4.24 s, TTMAPP 7.18 s, syntetyki 10.21 s,
odtworzenie 20.74 s. Maksymalny RSS procesu 118808 KiB, nie łączny szczyt.
Bez GPU lub nowych zależności. Mała liczba niezależnych geometrii i 48/108
brakujących komórek kalibracji ograniczają wnioski. Okna się nakładają;
Z nie jest p-value, sigma nie jest zmierzoną niepewnością TTMAPP. Nie
porównywać odsetków okien z poprzednimi przypisaniami molekuł. Lokalny
HTML/CSV/wykresy samodzielne; odtworzenie wymaga poprzednich artefaktów.
Kopia zweryfikowana w `copy-verification.json`. Brak potrzeb zmian wspólnych.

---

## Poprzednie przekazanie — rozłączne modele i materiał

Data: **2026-10-28**. Dokumentacja `domains/disjoint-models-material`, baza
`49badd7`, worktree `/tmp/netcat-stmdomains-disjoint-models-material`.
Źródła: **`prototype/stmdomains-disjoint-models-material`, `946cfb4`**, baza
`c7ed021`. Prototyp pozostaje osobno; nie scalać go do aplikacji.
Dokumentacja do `domains/start`; końcowy commit w wiadomości użytkownika.
Integrację do `stm-next` prowadzi koordynator.

Na polecenie użytkownika porównano jeden wspólny model z dwoma modelami
na rozłącznych otoczeniach po stronach granicy oraz osobną informację o materiale:
[raport](disjoint-models-material-trial.md), [manifest](disjoint-models-material-manifest.json),
podgląd `/home/rlew/projekty/NEtCAT-domains/.scratch/disjoint-models-material/index.html`.
261 obrazów, 96 wariantów, 51 nowych syntetyków. Progi na 45 starych negatywach
i 33 jednorodnych kontrolach przed nowymi obrazami. 25056 prognoz, 24480 ocen
(brak referencji 6 z 24 TTMAPP). Bez wzorców domen, K, treningu i strojenia na
referencjach. Propozycje i dopasowania krawędzi wyłącznie z części uczących;
wcześniejsze oceny porządku pozostają zachowanym wejściem.

Prosta granica 3 px przy centrach: **138/138 połączeń przez granicę odrzuconych**,
dwa fragmenty, zachowane 89.5% przypisań. Na siatce nadal dwa niepewne mostki
na obraz. Osobny sygnał rozróżnia czystą przerwę 36 px od braków samych oznaczeń.
Węższa przerwa, lokalny szum i słaby materiał ujawniają ograniczenia podparcia.
Granice ukośne i niepełne centra nadal problematyczne. TTMAPP: zero porównań
kwalifikowanych jakościowo. Zachowaj niepewność = stare przypisania; usuń
niepewność = brak wyniku. Brak poprawy STM, nie wybrano metody do programu.

**19 pozostaje `claimed`, do omówienia; 20 odłożone.** Następne pytania:
wiarygodność dopasowania przy błędach pozycji, kierunek/położenie granicy,
lokalny szum. Nie uruchomiono kolejnej próby, treningu lub pełnych 268 klatek.
Nie zmieniono kodu produkcyjnego ani konfiguracji wspólnej.

Sprawdzenia: 16 kontroli inwariantów/dostępu wyłącznie do części uczących,
cztery przypadki analityczne; 1566 bazowych wyników po 4 tablice identyczne;
51 deterministycznych odtworzeń generatora. **261 nowych pomiarów i 261 plików /
25056 wyników** identycznych po odtworzeniu z blokadą referencji (wcześniejsze
bramki porządku pozostają wejściem). **212 kontroli QtWebEngine**, bez błędów JS;
42 obrazy, 96 ustawień, scenariusze, wybór połączenia/kierunku i procenty;
podgląd oraz wykres obejrzane. Python/Bash sprawdzone składniowo, wrapper
wykonany etapami. Nie testowano aplikacyjnego GUI lub produkcji.

CPU: 4 procesy po 1 wątku. Nowe bramki bazowe 52.53 s, pomiary 316.14+107.94 s,
prognozy 1.82 s, ocena 5.89 s, odtworzenie 424.46 s. Maksymalny RSS procesu
205740 KiB; łącznego szczytu nie mierzono. Bez GPU, nowych wag i zależności.
Kopia **758 plików / 200239951 B**, wszystkie SHA-256 zgodne; następnie
potwierdzenie kopii. Względny link do tolerant-fit-phase; HTML/CSV/wykresy
samodzielne, powtórzenie obliczeń wymaga poprzednich lokalnych artefaktów.
Brak potrzeb zmian wspólnych modułów, głównej konfiguracji, Viewer lub GUI.

---

## Poprzednie przekazanie — tolerancja pozycji i osobna zgodność fazy


Data: **2026-10-28**. Dokumentacja `domains/tolerant-fit-phase`, baza
`5e5557b`, worktree `/tmp/netcat-stmdomains-tolerant-fit-phase`.
Źródła: **`prototype/stmdomains-tolerant-fit-phase`, `c7ed021`**, baza
`d6ae09a`. Prototyp pozostaje osobno; nie scalać go do aplikacji.
Dokumentacja do `domains/start`; końcowy commit w wiadomości użytkownika.
Integrację do `stm-next` prowadzi koordynator.

Na polecenie użytkownika zbadano lokalne dopasowanie jednej sieci z tolerancją
błędów pozycji oraz osobny test fazy sąsiednich otoczeń:
[raport](tolerant-fit-phase-trial.md), [manifest](tolerant-fit-phase-manifest.json),
podgląd `/home/rlew/projekty/NEtCAT-domains/.scratch/tolerant-fit-phase/index.html`.
210 obrazów: 24 TTMAPP oraz 186 kontroli, w tym 45 nowych syntetyków.
84 warianty; 45 wcześniejszych negatywów do kalibracji przed nowymi obrazami.
17640 prognoz, 17136 ocen z powodu braku referencji 6 TTMAPP. Pełne obrazy,
bez wzorców klas, K, treningu lub strojenia na referencjach. Ocena dopasowania
na części punktów jest warunkowa względem propozycji bazy z wszystkich centrów.

Stała sieć poprawia mały jitter i brak oznaczeń; korekta pomaga przy lekkim
odkształceniu, ale pochłania skok 3 px. Faza małego otoczenia odcina 132/138
połączeń przez granicę, lecz dwa pozostawione mostki na obraz nadal scalają
domeny. Dopasowanie wypełnia pusty pas na siatce; ograniczenie dostępności
małego otoczenia usuwa go, ale także rozcina kontrolę braków oznaczeń.
TTMAPP najwyżej **125/1678 (7.4%)**, tylko BLACK, wobec poprzednich 279/1678
w tym samym geometrycznym wariancie siatki. RED/YELLOW nadal nieprzypisane.
Model jednej sieci Bravaisa nie jest ogólnym modelem dowolnych motywów.

**19 pozostaje `claimed`, do omówienia; 20 nadal odłożone.** Następna
propozycja: porównanie jednego/dwóch modeli na rozłącznych otoczeniach
po stronach granicy, ocena ciągłości rozcięcia i osobne podparcie materiału.
Nie uruchomiono następnej próby, treningu ani pełnych 268 klatek.
Nie przyjęto metody do programu i nie zmieniono produkcyjnego kodu.

Sprawdzenia: **1225 kontroli liczbowych**, 660 wcześniejszych wyników po
3 tablice dokładne; 45 deterministycznych odtworzeń syntetyków. **210 pomiarów
oraz 210 plików / 17640 wyników** odtworzone identycznie bez dostępu do
referencji. **217 kontroli QtWebEngine**, bez błędów JS; oba tryby, 53 obrazy,
84 ustawienia, scenariusze i procenty; podgląd i wykres obejrzane. Poprawki
serializacji bool/wskaźników dotyczyły HTML, bez zmian wyników analizy.
Python/Bash sprawdzone składniowo; wrapper wykonany etapami.
Nie testowano aplikacyjnego GUI ani produkcji. Nie jest to odbiór skuteczności.

CPU: 4 procesy po 1 wątku, pomiary 42.13+29.80 s, prognozy 18.28 s,
ocena 4.18 s, odtworzenie 91.85 s. Maksymalny RSS procesu 118712 KiB;
łącznego szczytu nie mierzono. Bez GPU, nowych wag lub zależności.
Kopia: **537 plików / 109045271 B**, wszystkie SHA-256 zgodne; następnie
potwierdzenie kopii. Względny link do translation-family. HTML/CSV/wykresy
samodzielne, powtórzenie analizy wymaga starszych lokalnych artefaktów.
Brak potrzeb zmian modułów wspólnych, głównej konfiguracji, Viewer lub GUI.

---

## Poprzednie przekazanie — rodzina zgodnych przesunięć


Data: **2026-10-28**. Dokumentacja `domains/translation-family`, baza
`e5e6100`, worktree `/tmp/netcat-stmdomains-translation-family`.
Źródła: **`prototype/stmdomains-translation-family`, `d6ae09a`**, baza
`9c78d8c`. Prototyp pozostaje osobno; nie scalać go do aplikacji.
Dokumentacja do `domains/start`; końcowy commit w wiadomości użytkownika.
Integrację do `stm-next` prowadzi koordynator.

Na polecenie użytkownika zbadano rodzinę zgodnych przesunięć:
[raport](translation-family-trial.md), [manifest](translation-family-manifest.json),
podgląd `/home/rlew/projekty/NEtCAT-domains/.scratch/translation-family/index.html`.
165 obrazów: 24 pełne TTMAPP, pozostałe znane obrazy audytu i 45 negatywów
kalibracji (łącznie 123), następnie 42 nowe syntetyki. Pięć kryteriów,
dwa promienie/źródła, osobna kalibracja kwantylem .99; bez treningu,
K, wzorców domen i strojenia na referencjach. Cechy/podziały zachowane.
260 konfiguracji na starszych obrazach spoza rzędów, 52 na rzędach/nowych.

Kanoniczna rodzina daje identyczne oceny równoważnych baz; sprawdzono
56818 takich otoczeń. Agregacje obrazu nadal **0/1678 przypisań TTMAPP**.
Zgodność centrów r48 daje do **296/1678 (17.6%)**, tylko BLACK, przy
scalaniu granicy przesunięcia i fałszywych miejscach niezależnych rzędów.
Na małym oknie próg zgodności centrów wynosi 1, więc nie przechodzi nawet
poprawna sieć. Mediany obrazu r48 tworzą też pozorny fragment w pustej
przerwie (84/96 lub 78/96 miejsc). Zmienna amplituda pojedynczych molekuł,
szum i niewielki jitter nadal silnie obniżają wyniki obrazu.

**19 pozostaje `claimed`, do omówienia; 20 nadal odłożone.** Następna
propozycja: lokalna zgodność struktury z tolerancją pozycji i oddzielna
spójność fazy między sąsiednimi otoczeniami. Kontrole niezależnych rzędów,
przerw i granicy przesunięcia muszą pozostać. Nie uruchomiono tej próby,
treningu ani pełnych 268 klatek. Nie przyjęto metody do programu.

Sprawdzenia: 24 rodziny, 96 niezmiennych ocen, 864 porównania korelacji
(błąd ≤1.39e-16), 804 odtworzenia pojedynczych par (≤1.12e-15), 3816
bazowych wyników dokładnych. **165 pomiarów i 165 plików / 24804 wyniki**
odtworzone identycznie z blokadą odczytów referencji. 132 pary tablic obrazu
niezmienione przy brakach oznaczeń; 227272 identyczne oceny wspólnych rodzin.
42 deterministyczne odtworzenia nowych obrazów. Przed oceną poprawiono
zapis pól/manifestu; 165 ponowionych obrazów zachowało wszystkie oceny
oraz progi. **343 kontrole QtWebEngine**, bez błędów JS, podgląd/wykres
obejrzane. Python/Bash sprawdzone składniowo; wrapper wykonany etapami.
Nie testowano natywnego GUI, produkcji ani pełnego odbioru skuteczności.

CPU: 4 procesy po 1 wątku. Pomiary 153.98+64.41 s, predykcje 4.17 s,
ocena 7.05 s, ponowienie 232.03 s. Maksymalny RSS procesu 138200 KiB;
łącznego szczytu nie mierzono. Czasy końcowych etapów, bez poprawek/UI.
Bez GPU, nowych wag i zależności. Kopia **444 pliki / 158992656 B**,
wszystkie SHA-256 zgodne; następnie dopisano potwierdzenie kopii.
Względne linki do audytu, translation-consistency i grafu. HTML/CSV/wykresy
samowystarczalne, odtworzenie obliczeń wymaga poprzednich artefaktów.
Do aplikacji tylko dokumentacja i manifest. Brak potrzeb zmian wspólnego
kodu, głównej konfiguracji, Viewer lub produkcyjnego GUI.

---

## Poprzednie przekazanie — audyt wektorów i odmów, issue 19

Data: **2026-10-28**. Dokumentacja `domains/vector-refusal-audit`, baza
`9b94cac`, worktree `/tmp/netcat-stmdomains-vector-refusal-audit`.
Źródła: **`prototype/stmdomains-vector-refusal-audit`, `9c78d8c`**,
baza `89cd738`. Kod prototypu pozostaje osobno; nie scalać go do aplikacji.
Dokumentacja do `domains/start`, końcowy commit w wiadomości użytkownika.
Integrację do `stm-next` prowadzi koordynator.

Użytkownik wybrał pozostanie przy 19 i polecił audyt. **19 nadal `claimed`;
20 odłożone.** Wykonano [audyt odmów](vector-refusal-audit.md),
[manifest](vector-refusal-audit-manifest.json), podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/vector-refusal-audit/index.html`.
78 znanych obrazów: 24 pełne TTMAPP, 36 starszych kontroli i 18 rzędów.
W tych samych otoczeniach porównano przesunięcia obrazu i centrów, zachowując
progi, cechy, podziały i łączność. Bez treningu, K, wzorców domen i strojenia
na referencjach. Podmiana przy starym progu jest diagnostyką bez rekalibracji.

Kryterium zgodności odrzuca miejsca przed łączeniem. Geometria przepuszcza
17/1916 znanych miejsc siatki r24, ale składowe mają tylko 1–3 miejsca,
więc nadal **0/1678 przypisań TTMAPP**. Przy centrach i przy r48 zero miejsc.
Sześć zmian decyzji występuje przy dokładnie równoważnych bazach tej samej
sieci. Okna w ≥80% w jednym znanym wnętrzu nadal zwykle daleko od progu;
mieszanie obszarów nie tłumaczy całości, ale nie zostało całkiem wykluczone.
DINO/centra/HDBSCAN ma także niezależną całkowitą odmowę grupowania wyglądu.
Geometria pozostawia fałszywe fragmenty losowych rzędów i pogarsza braki
centrów/słabsze rzędy. Centra nie są prawdą referencyjną.

Kolejna propozycja **w 19**, jeszcze niewykonana: kryterium rodziny zgodnych
przesunięć, odporność na wybór bazy i zmienny wygląd molekuł. Kontrole
odkształceń, niezależnych rzędów, przerw i granic, z kalibracją bez ramek.
Nie wybierać po prostu najlepszego przesunięcia bez kontroli fałszywych
akceptacji. Nie wdrożono metody i nie uruchomiono treningów.

Sprawdzenia: 128 permutacji, trzy bazy, sześć braków podstaw, przypadek
analityczny. **312 dokładnych odtworzeń** tablic zgodności, **2544 wyników
bazowych**. Wszystkie 78 pomiarów i 78 plików / **3816 wyników** odtworzone
identycznie przy blokadzie odczytów referencji; hashe 372 poprzednich plików,
progów/protokołu/kodu zgodne. 72 pary tablic obrazowych niezmienione przy
brakach oznaczeń; 12 geometrycznych zmienionych zgodnie z oczekiwaniem.
**125 kontroli QtWebEngine**, brak błędów JS, obejrzano HTML/wykres.
Składnia Python/Bash sprawdzona, wrapper uruchamiany etapami. To weryfikacja
obliczeń i podglądu, nie test natywnego GUI ani odbiór skuteczności.

CPU, cztery procesy, po jednym wątku: pomiary 41.57 s, predykcje 1.05 s,
ocena 52.01 s, ponowienie 43.68 s. Maksymalny RSS procesu 110492 KiB;
łącznego szczytu nie mierzono. Bez GPU, nowych wag i zależności.
Kopia **179 plików / 92488878 B**, wszystkie SHA-256 zgodne, potem dopisano
potwierdzenie. Względne linki do translation-consistency/local-feature-graph.
HTML/CSV/wykresy samowystarczalne; pełne odtworzenie wymaga dawnych artefaktów.
Do aplikacji tylko raport, manifest i statusy mapy. Brak potrzeb zmian
wspólnego kodu, konfiguracji, Viewer lub produkcyjnego GUI.

---

## Poprzednie przekazanie — zgodność przesunięć i lokalny sygnał, issue 19

Data: **2026-10-28**. Dokumentacja `domains/translation-consistency-trial`,
baza `1868426`, worktree `/tmp/netcat-stmdomains-translation-consistency`.
Źródła: **`prototype/stmdomains-translation-consistency`, `89cd738`**,
baza `f648afe`. Prototyp pozostaje osobno; nie scalać kodu do aplikacji.
Dokumentacja do `domains/start`, commit końcowy w wiadomości użytkownika.
Integrację do `stm-next` prowadzi koordynator.

Wykonano dwa badania: zgodność różnic obrazu po przesunięciach między
rzędami oraz lokalny wskaźnik sygnału. [Raport](translation-consistency-trial.md),
[manifest](translation-consistency-manifest.json), podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/translation-consistency/index.html`.
372 obrazy: 24 TTMAPP, 204 kontrole, 63 znane obrazy rzędów i 81 nowych
realizacji, także skośnych/prostokątnych sieci. Nowe dane nie kalibrują
progów. Bez K, wzorców domen, treningu i ponownego grupowania cech.
360 konfiguracji starego zestawu, w tym 256 zmienionych detektorów;
na obrazach rzędów tylko 40 wariantów porządku i łączności.

Zgodność przy r24/kwantylu .99 zachowuje **79.7%** słabszej syntetycznej
sieci, ograniczając przypisania losowych faz rzędów 0° z **756 do 24/768**
względem wariantu bez drugiego kierunku. Wszystkie kryteria zgodności
odrzucają jednak wnętrza TTMAPP. Mały lokalny pomiar usuwa błąd pustej
przerwy, lecz również poprawne płaty na siatce; przy centrach kontrola
pozostaje rozpoznana. To zależność od położenia w komórce sieci, nie
gotowa maska materiału. **0/256 zmienionych konfiguracji** spełnia cały
zestaw warunków. Wynik poza częściowymi referencjami pozostaje nieznany.

**19 pozostaje `claimed`, do omówienia.** Proponowane następne: 20,
potem 21/22, z oceną reprezentacji/podziału przed bramką oraz osobno
odmów. W 20/22 zapisano wnioski, bez uruchomienia tych zadań i bez
wyboru modelu. Nowe syntetyki nie są niezależną walidacją realnego STM.

Sprawdzenia: 128 porównań Pearsona, 400 interpolacji (błędy ≤4.45e-16),
400 masek i cztery przypadki analityczne/braku podstaw; 81 odtworzeń
generatora. 4656 tablic zgodnych do 1e-12, 16920 wyników początkowych
dokładnych. 456 tablic i 4320 par wyników siatki niezmienionych przy
brakach oznaczeń. **372 pliki / 87840 wyników** ponowiono identycznie
przy blokadzie odczytów referencji; 372 nowe i 291 starych plików zgodnych
z hashami. Parametry/protokół/kod analizy niezmienione po ocenie.
Pomocniczy audyt przyczyn odmów dodano po zamrożeniu, bez strojenia.
**187 kontroli QtWebEngine**, brak błędów JS, obejrzano HTML i wykresy.
Składnia Python/Bash, linki, manifest i diff sprawdzone. Nie testowano
produkcji, natywnego GUI, przesunięć początku siatki ani pełnych 268 klatek.

CPU: cztery procesy, po jednym wątku BLAS/OpenMP. Pomiary 174.26 s,
predykcje 15.61 s, ocena 17.18 s, ponowienie bez referencji 13.91 s.
Maksymalny RSS jednego procesu przygotowania 120468 KiB (~118 MiB);
łącznego szczytu nie mierzono. Bez GPU, instalacji i nowych wag.
Etapy wykonano osobno, wrapper sprawdzono składniowo.

Kopia **931 plików / 293617956 B**, wszystkie SHA-256 zgodne; potem
dopisano potwierdzenie kopii. Względne linki do wcześniejszych katalogów
second-direction/grafu i ich zależności. HTML/PNG/PDF/CSV samowystarczalne.
Do aplikacji tylko dokumentacja i manifest. Brak potrzeb zmian wspólnego
kodu, konfiguracji głównej, Viewer lub produkcyjnego GUI.

---

## Poprzednie przekazanie — drugi kierunek i rzędy molekuł, issue 19

Data: 2026-10-26. Dokumentacja `domains/second-direction-trial`, baza
`4241af9`, worktree `/tmp/netcat-stmdomains-second-direction`.
Źródła: **`prototype/stmdomains-second-direction`, `f648afe`**, baza
`2ccf9ad`. Prototyp pozostaje na osobnej gałęzi; nie scalać do aplikacji.
Dokumentacja do `domains/start`; commit końcowy w wiadomości do użytkownika.
Integrację ze `stm-next` prowadzi koordynator.

Wykonano zaproponowane badanie: [raport](second-direction-trial.md),
[manifest](second-direction-manifest.json), podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/second-direction/index.html`.
24 pełne klatki TTMAPP, 204 stare kontrole i 63 nowe obrazy syntetyczne.
30 kryteriów × 18 zachowanych podziałów/limitów = 540 konfiguracji:
108 powtórzonych, 384 zmienione detektory, 48 zmienionych limitów.
Nowe obrazy sprawdzają tylko 60 wariantów porządku/łączności. Bez wzorców
domen, K, treningu i ponownego grupowania; progi bez nowych obrazów/ramek.

Usunięcie drugiego kierunku przy r24/`windowed` zwiększa limit przypisań
z **98 do 636/1678**, nadal wyłącznie BLACK. Odzyskuje słabsze regularne
rzędy, ale przyjmuje **756/768 miejsc** rzędów z losową fazą jako jedną
sieć. Krzywizna ACF odmawia słabszym rzędom i TTMAPP; przy obrocie nadal
przepuszcza fragmenty niezależnych rzędów. R48 dalej łączy płaty przez
przerwę. **0/384 zmienionych konfiguracji detektora** spełnia komplet
warunków. Nie utożsamiać liczby przypisań z jakością wykrywania domen.

**19 pozostaje `claimed`, do omówienia.** Kolejna hipoteza: zgodność
przesunięć między rzędami i lokalne potwierdzenie sygnału. Kontrole
obejmą słabe spójne rzędy, losowe fazy, pasy i puste przerwy. Tej próby,
treningu 20–23 ani odbioru 13 nie uruchomiono. Nowe ziarna syntetyczne
nie stanowią niezależnej walidacji rzeczywistych pomiarów STM.

Sprawdzenia: 130 obliczeń analitycznych krzywizny (błąd ≤6.67e-16),
63 odtworzenia obrazów, 2736 dokładnych odtworzeń ACF, 24624 poprzednich
wyników zgodnych. 528 tablic siatki i 6480 par wyników identycznych przy
brakach samych oznaczeń. Wszystkie **291 plików / 126900 wyników**
ponowiono przy blokadzie odczytów referencji: zgodne hashe zawartości.
291 nowych i 228 poprzednich plików predykcji sprawdzonych SHA-256;
protokół/progi/kod niezmienione po ocenie. **170 kontroli QtWebEngine**,
bez błędów JS, obejrzano podgląd i wykres. Sprawdzono składnię, linki,
manifest i diff. Nie testowano produkcji, natywnego GUI ani pełnych
268 klatek; nie powtarzano przesunięcia siatki i ekstrakcji modeli.

CPU, cztery procesy, po jednym wątku BLAS/OpenMP; ACF/krzywizna 440.43 s,
predykcje 14.87 s, ocena 24.87 s, ponowienie bez referencji 15.42 s.
Maksymalny RSS jednego procesu przygotowania 115892 KiB (~113 MiB),
bez pomiaru łącznego szczytu. Bez GPU, instalacji i nowych wag.
Etapy uruchomiono osobno; wrapper sprawdzono składniowo.

Kopia **732 pliki / 414795835 B**, wszystkie SHA-256 zgodne; później
dopisano potwierdzenie kopii. Wymaga wcześniejszych katalogów ACF/grafu
i ich zależności; HTML, wykresy i CSV są samowystarczalne.
Do aplikacji trafia wyłącznie dokumentacja i mały manifest. Brak potrzeb
zmian wspólnego kodu, konfiguracji głównej lub Viewer.

---

## Poprzednie przekazanie — skala i podparcie ACF, issue 19

Data: 2026-10-26. Dokumentacja `domains/acf-scale-support-trial`, baza
`e095bc4`, worktree `/tmp/netcat-stmdomains-acf-scale-support`.
Źródła prototypu: **`prototype/stmdomains-acf-scale-support`, `2ccf9ad`**,
baza `1ae0706`. Nie scalać prototypu do aplikacji. Dokumentacja przeznaczona
do `domains/start`; integrację do `stm-next` prowadzi koordynator.

Wykonano kolejne badanie issue 19: [raport](acf-scale-support-trial.md),
[manifest](acf-scale-support-manifest.json), samowystarczalny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/acf-scale-support/index.html`.
24 całe klatki TTMAPP, 204 kontrole; 32 warianty ACF/skali/podparcia,
512 konfiguracji ze stałymi podziałami, 64 kontrole limitu bramki
i 16 zachowanych wyników początkowych. Bez treningu, K, wzorców domen,
przeliczania cech/PCA/HDBSCAN/grafu lub strojenia do referencji.

Większe okno odzyskuje fragmenty RED/YELLOW: limit `windowed` na siatce
rośnie z 98/1678 przy r24 do 430/1678 przy r48. Jednak r48 łączy dwa
rozłączne płaty przez pustą przerwę, a zachowane podziały nadal dzielą
jedną sieć lub scalają różne obszary. **0/512 nowych konfiguracji**
spełnia komplet warunków. W r24 brak podparcia 50% nie odrzuca znanych
wnętrz; widmowy warunek drugiego kierunku odrzuca około połowy miejsc.

**19 nadal `claimed`**, do omówienia. Kolejna hipoteza: drugi kierunek
widma przy różnym kontraście rzędów molekuł wobec pasów skanowania
i rzędów bez wzajemnego porządku. Potrzebna osobna ablacja i zachowanie
kontroli przerw. Nie rozpoczęto tej próby, treningu 20–23 ani odbioru 13.
Wszystkie użyte ziarna i referencje były znane; bez niezależnej walidacji.

Sprawdzenia: 5836 przesunięć Pearsona kontra bezpośredni rachunek
(błąd do 6.42e-13, liczby par dokładne), 912 dokładnych odtworzeń ACF,
cztery progi i 3648 wyników początkowych zgodne. 864 tablice ACF siatki
i 7104 wyniki siatki identyczne przy brakach samych oznaczeń.
228 starych i 228 nowych plików predykcji zgodnych z hashami, progi stałe
po ocenie. **92 kontrole QtWebEngine**, bez błędów; obejrzano podgląd
i wykres. Składnia Python/Bash, linki, manifest i diff sprawdzone.
Nie testowano produkcji, natywnego GUI ani pełnych 268 klatek.

CPU bez GPU/instalacji: cztery procesy, po jednym wątku BLAS/OpenMP.
ACF 429.29 s, dodatkowe odtworzenie 12 rekordów z pustymi centrami po
poprawce ich pustych tablic 12.11 s (przed oceną), predykcje 18.37 s,
ocena 30.57 s. Największy RSS pojedynczego procesu przygotowania
125004 KiB; łącznego szczytu nie mierzono. Etapy wykonano osobno;
wrapper składniowo. Protokół i parametry nie zmieniały się po ocenie.

Kopia: **479 plików / 425534929 B**, wszystkie SHA-256 zgodne.
Względne linki wymagają zachowania `.scratch/local-feature-graph/`
i jego zależności; sam HTML jest samowystarczalny. Do gałęzi aplikacji
trafia wyłącznie dokumentacja i mały manifest. Bez zmian wspólnego kodu,
konfiguracji głównej, produkcyjnego GUI lub Viewer.

---

## Poprzednie przekazanie — lokalny graf cech i położenie siatki, issue 19

Data: 2026-10-26. Dokumentacja `domains/local-feature-graph-trial`, baza
`e7b6ae0`, worktree `/tmp/netcat-stmdomains-local-feature-graph`.
Źródła prototypu: **`prototype/stmdomains-local-feature-graph`, `1ae0706`**,
baza `cf88e8a`. Nie scalać prototypu do aplikacji. Dokumentacja przeznaczona
do `domains/start`; integrację do `stm-next` prowadzi koordynator.

Na polecenie „wykonaj kolejne badanie” ukończono zaproponowaną próbę
lokalnego podziału. [Raport](local-feature-graph-trial.md),
[manifest](local-feature-graph-manifest.json), samowystarczalny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/local-feature-graph/index.html`.

24 całe klatki TTMAPP, 204 kontrole; osiem baz cech/miejsc, cztery skale
grafu, osiem zachowanych wyników HDBSCAN i osiem kontroli limitu bramki.
Własna adaptacja grafu Felzenszwalba–Huttenlochera, z niezmienionymi
cechami, PCA i oceną porządku. Bez liczby domen K, wzorców domen i treningu.
Znane już dane oznaczają diagnozę rozwojową, bez niezależnej walidacji.

Graf zmniejsza część scaleń orientacji, ale rozcina jedną sieć;
**0/32 konfiguracji** spełnia komplet warunków. Przykład FCN/siatka,
skala 4: scalenia obrotu 8° ze 100% do 1.9%, lecz jedna sieć ma
7/5/5 fragmentów. ACF nadal ogranicza końcowe przypisania TTMAPP
do 2.0–5.8% molekuł we wnętrzach referencji, bez RED/YELLOW.
Podział bez bramki także scala różne obszary wyglądu.

Świeża ekstrakcja na 53 obrazach i czterech początkach siatki:
424 zestawy cech, 1696 wyników grafu. Zależność od siatki pozostaje
po wykluczeniu brzegu — jedna sieć zmienia wynik w 69/144 powiązanych
porównań. Pomocniczy audyt wnętrza dodano po zamrożeniu predykcji;
nie zmieniano parametrów. Nie powstały typy strukturalne ani dokładne kontury.

**19 nadal `claimed`**, do omówienia. Kolejny kierunek to osobne badanie
skali/podparcia kryterium porządku ACF przy stałych cechach i podziałach,
z kontrolami szumu i pasów. Nie rozpoczęto tego badania, treningu 20–23
ani odbioru 13. Sama poprawa bramki nie rozwiąże problemów granic.

Sprawdzenia: 7296 permutacji grafu, 7296 ograniczeń zakresu przez bramkę,
128 małych grafów zgodnych z niezależną implementacją; 384 porównania
braków samych oznaczeń bez zmiany siatki. 106 świeżych zestawów cech
bitowo zgodnych z cache, 424 zgodne grafy zerowego przesunięcia, stałe
wagi/bufory modeli i hashe predykcji. **107 kontroli QtWebEngine**,
bez błędów JS; obejrzano podgląd i wykres. Składnia Python/Bash,
linki, manifesty i diff sprawdzone. Nie testowano produkcji ani natywnego GUI.

Koszt: krawędzie 3.91 s CPU, grafy podstawowe z permutacjami 26.95 s,
ekstrakcja przesuniętej siatki i ACF 55.02 s (ACF 33.33 s), grafy
przesunięte 4.17 s. Szczyt RSS ekstrakcji ok. 1.41 GiB, tensory CUDA
155.6 MiB; nie jest to pełna pamięć procesu GPU. RTX 5090, lokalne netcat,
bez instalacji lub pobierania wag. Etapy wykonano osobno, wrapper
sprawdzono składniowo. Bez kwalifikacji do benchmarku całych 268 klatek.

Artefakt **1555 plików / 367553595 B**, kopia zweryfikowana SHA-256.
Względne symlinki wymagają zachowania `.scratch/frozen-feature-domains/`
i `.scratch/feature-separation/`; sam HTML jest samowystarczalny.
Do aplikacji trafia wyłącznie dokumentacja i mały manifest. Brak zmian
wspólnych modułów, konfiguracji głównej, produkcyjnego GUI lub Viewer.

---

## Poprzednie przekazanie — diagnoza cech, PCA i grupowania, issue 19

Data: 2026-10-26. Dokumentacja `domains/feature-separation-trial`, baza
`1c2eef6`, worktree `/tmp/netcat-stmdomains-feature-separation`.
Źródła prototypu: **`prototype/stmdomains-feature-separation`, `cf88e8a`**,
baza `652ab96`. Nie scalać prototypu do aplikacji. Docelowo dokumentacja
na `domains/start`; commit dokumentacji w wiadomości końcowej.

Na polecenie „wykonaj kolejne badanie” ukończono diagnozę zaproponowaną
w pierwszej próbie 19. [Raport](feature-separation-trial.md),
[manifest](feature-separation-manifest.json), interaktywny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/feature-separation/index.html`.

24 całe klatki TTMAPP i 204 kontrole, osiem kombinacji cecha/miejsca;
pełne cechy/PCA × dotychczasowe/zerowe epsilon daje 32 konfiguracje.
Protokół zapisany przed oceną, bez treningu, K i dopasowania do ramek.
Wszystkie ziarna były już znane: to diagnoza, nie niezależna walidacja.

Cechy obu modeli zachowują rozróżnienie orientacji 8°/27° i rozstawu
na kontrolach; największa zmiana AUC po PCA to 0.000486. Same zmiany
PCA/epsilon nie naprawiają domen: na TTMAPP 30 wariantów daje jeden
klaster wyglądu, dwa odmawiają. DINO/centra po epsilon=0 odzyskuje
46/1678 oznaczeń, nadal tylko BLACK. Żaden wariant nie spełnia kompletu
warunków. Nie wyznaczono typów, powierzchni ani dokładnych granic.

**19 nadal `claimed`**, do omówienia. Dalszy kierunek: lokalne granice
różnic cech i osobna ocena kryterium porządku. Nie rozpoczęto tego
następnego eksperymentu, treningu 20 ani odbioru 13. Nie ma potrzeby
uruchamiania warunkowej próby przestrzennego poolingu dla wyjaśnienia
utraty obrotu/rozstawu na tych kontrolach; nie oznacza to odrzucenia
innych poolingów dla rzeczywistych STM.

Sprawdzenia: **1824/1824** dokładne odtworzenia starego wariantu (pięć
tablic na wynik), AUC kontra bezpośrednie liczenie z remisami (5.56e-17),
odległości PCA nie większe od pełnych, niezmienione hashe predykcji
podczas oceny. **68 kontroli QtWebEngine**, bez błędów JS; obejrzano
podgląd oraz wykres. Składnia Python/Bash, linki i diff sprawdzone.
Nie powtarzano ekstrakcji, testów modeli ani natywnego GUI; korzystano
z cech i ich wcześniejszej weryfikacji.

Koszt CPU, jeden wątek: PCA 16.16 s, metryki 7.19 s, grupowanie 457.59 s;
szczyt RSS do 589056 KiB (ok. 575 MiB), bez GPU i instalacji pakietów.
Kopia: **2078 plików / 261856765 B**, wszystkie SHA-256 zgodne.
Względne symlinki wskazują zachowany artefakt pierwszej próby 19;
sam HTML jest samowystarczalny. Dane i modele pozostają poza Git.
Runner na gałęzi prototypu; etapy wykonano osobno, wrapper składniowo.

Do aplikacji trafia tylko dokumentacja i manifest. Bez zmian wspólnych
modułów, konfiguracji głównej, produkcyjnego GUI lub Viewer. Integrację
do `stm-next` prowadzi koordynator.

---

## Poprzednie przekazanie — porównanie gotowych cech, issue 19

Data: 2026-10-26. Dokumentacja `domains/frozen-domain-trial`, baza `ad584eb`,
worktree `/tmp/netcat-stmdomains-frozen-domain-trial`, docelowo `domains/start`.
Źródło prototypu: **`prototype/stmdomains-frozen-domains`, `652ab96`**,
baza `ad584eb`. Nie scalać prototypu do aplikacji. Commit dokumentacji
w wiadomości końcowej.

Wykonano issue 19: FCN–ResNet101 i DINOv2, widmo i EWT, siatka i centra,
24 pełne klatki TTMAPP i 204 kontrole. 64 konfiguracje podstawowe ze
wspólnym budżetem oraz 96 dodatkowych wariantów rozdzielczości/normalizacji.
Bez wzorców domen, zadanego K i treningu. Nowe wspólne grupowanie:
L2/PCA, epsilon w jednostkach mediany dystansu sąsiada; dwa kryteria ACF,
w tym nowa korelacja na nakładających się częściach okna. Wagi sieci stałe.

[Raport](frozen-feature-domains-trial.md),
[manifest](frozen-feature-domains-manifest.json),
[audyt grupowania](research-frozen-domain-clustering-audit.md), podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/frozen-feature-domains/index.html`.
Wybrane FCN/DINO przypisują 0–5.1% centrów we wnętrzach TTMAPP, bez
RED/YELLOW. Siedem wariantów ma jeden katalogowy klaster wyglądu;
DINO/centra odmawia wszystkim. Ocena porządku usuwa większość danych.
Pozostają nadmierne podziały pojedynczej sieci i błędy małych orientacji
oraz granic. Żaden ze 160 wariantów nie spełnia wszystkich warunków.
Nie wyznaczono typów strukturalnych, powierzchni ani dokładnych konturów.

Użytkownik: **„Najpierw omówmy lub rozwińmy tę próbę”**. Issue 19 pozostaje
**`claimed`**, bez zamknięcia i bez wyboru metody. Zachowano pełne wyniki;
proponowane rozwinięcie powinno rozdzielić utratę informacji w uśrednieniu,
PCA i grupowaniu. Jest jeszcze niewykonane. Nie uruchomiono treningu 20;
odbiór 13 i jakość 04 nadal otwarte. Nie przypisywać wyniku wyłącznie
modelom ani proponować samego obniżenia progu jako rozwiązania.

Sprawdzenia: 912 świeżych zestawów cech sieci siatki identycznych bez
oznaczeń; 228 identycznych zestawów klasycznych (FFT/EWT z niezależnego
powtórzenia 17, nowa ACF przeliczona); 1824 identyczne wyniki pełnego
powtórnego grupowania wybranych konfiguracji bez referencji. Wariant
centrowy sprawdzony przy odwróceniu kolejności wejścia. 1824 wyniki
zgodne z kontraktem; bez zmian źródeł i ustawień po odczycie referencji.
96 par braków detekcji identycznych na siatce; kontrast/skala zmieniają
wynik. Zakres 5 → 24 zmienia katalog wyglądu w 21/40 porównań; zgodne puste
końcowe wyniki nie dowodzą stabilności detekcji. Bezpośrednia kontrola
numeryczna nowej ACF: błąd do 3.33e-16. QtWebEngine: **46 kontroli**,
bez błędów JS, obejrzano podgląd i wykres. Składnia Python/Bash i diff
sprawdzone. Nie testowano produkcji ani natywnego GUI.

Koszt: sieci 566.52 s na RTX 5090, nowa ACF/audyt 319.95 s CPU,
grupowanie 319.16 s CPU, ocena 11.73 s. Szczyt RSS ekstrakcji ok. 1.48 GiB;
alokowane tensory CUDA 324 MiB FCN / 268 MiB DINO. Same tablice sieci ok. 3.3 GB.
Cały artefakt 35319 plików / 6642599215 B, kopia do Domains zweryfikowana
SHA-256, symlinki względne. Netcat bez instalacji nowych pakietów,
wagi z 18. Etapy runnera wykonano osobno, nie powtarzano całości wrapperem.
Nie kwalifikowano żadnej konfiguracji do benchmarku 268 klatek.

Brak zmian wspólnych modułów, wymagań, aplikacji lub Viewer. Do Domains
trafia tylko dokumentacja i mały manifest; prototyp jest na osobnej gałęzi,
dane pozostają lokalne. Integrację do `stm-next` prowadzi koordynator.

---

## Poprzednie przekazanie — przygotowanie gotowych cech, issue 18

Data: 2026-10-26. Gałąź `domains/frozen-features`, baza `9346d1a`,
worktree `/tmp/netcat-stmdomains-frozen-features`, docelowo `domains/start`.
Kod, testy, audyt źródeł i manifest: **`e6e7248`**. Commit końcowej
dokumentacji w wiadomości końcowej. Zmiany obejmują wyłącznie katalogi
STM Domains; kod służy eksperymentom i nie zmienia uruchamiania aplikacji.

Issue 18 **`resolved`**: działają oba zamrożone ekstraktory, FCN–ResNet101
z `layer1/layer2` i DINOv2 ViT-S/14 z końcowymi patch tokens. Oficjalne
wagi i przypięty kod sprawdzane SHA-256. Wykonano 16 konfiguracji na
12 obrazach (5 TTMAPP i 7 kontroli), na siatce i przy wszystkich centrach:
384 wpisy, 368 unikalnych cache. Zachowane oryginalne współrzędne, maski
pomiaru, okna i podparcie brzegu. Nie wykonywano treningu ani grupowania.

[Raport](frozen-feature-preparation.md),
[manifest](frozen-feature-preparation-manifest.json),
[audyt źródeł](research-frozen-feature-extraction-audit.md),
[instrukcja odtworzenia](../../stmdomains/experiments/frozen/README.md).
Lokalny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/frozen-features/index.html`.
Krzyżyki siatki, okręgi molekuł i wybrane okno oznaczają miejsca pobierania
cech. To podgląd geometrii, nie wynik wykrywania domen.

Wykonane sprawdzenia: **41 testów pytest**; **192/192** zestawy cech
siatki bitowo identyczne w świeżym powtórzeniu bez centrów, po zmianie
danych referencyjnych; 384 kontrole geometrii/cache; niezmienione hashe
parametrów i buforów modeli przed/po. Osiem kontroli partii i kolejności:
DINO przy zmianie partii 5 → 1 różni się do 4.20e-5; zapisano niepowodzenie
pierwotnej tolerancji i osobną tolerancję 1e-4 dla tego porównania.
Zwykłe powtórzenie jest dokładne. QtWebEngine offscreen: **19 kontroli**,
bez błędów JS; obejrzano podgląd. Składnia Python/Bash i diff sprawdzone.
Nie testowano natywnego GUI, skuteczności domen ani pełnych 268 klatek.
Etapy odtworzenia wykonano osobno, bez powtarzania całości samym wrapperem.

Sprzęt/środowisko: RTX 5090, torch 2.9.1+cu128, torchvision 0.24.1+cu128,
Python 3.12.12 w lokalnym netcat; bez instalacji dodatkowych pakietów.
Ekstrakcja 37.01 s; maksimum alokatora CUDA ok. 324 MiB (FCN), 268 MiB
(DINO), maksimum RSS procesu ok. 1.34 GiB. To koszt pilotażu, bez
przyszłego grupowania. Wyniki lokalne: 1126 plików / 394049728 B;
modele i źródła: 222 pliki / 312982757 B w `.scratch/frozen-feature-assets/`.
Kopie do Domains zweryfikowano SHA-256; duże pliki pozostają poza Git.

**Następne: 19**, gotowe zależności, jeszcze nieuruchomione. Rozszerzyć
zakres wejścia i porównać cechy z klasyczną teksturą; uwzględnić pooling,
normalizację, okna 48/72 wobec 49/73 w 17 i odmowy bramki porządku.
Gotowość techniczna nie dowodzi rozróżniania orientacji, rozstawów ani
granic. Opcjonalnego DINOv3 nie uruchamiano. Trening 20, odbiór 13
i jakość 04 pozostają otwarte. Brak potrzeb zmian wspólnego kodu,
głównych wymagań lub Viewer; integrację do `stm-next` prowadzi koordynator.

---

## Poprzednie przekazanie — tekstura obrazu, issue 17

Data: 2026-10-23. Dokumentacja `domains/texture-trial`, baza `b292f2f`,
worktree `/tmp/netcat-stmdomains-texture`, docelowo `domains/start`.
Źródła: `prototype/stmdomains-texture`, commit `3bb4d36`, baza `e6d3fbc`.
Nie scalać prototypu do aplikacji. Commit dokumentacji w wiadomości końcowej.

Issue 16 zamknięto wcześniej po zatwierdzeniu użytkownika. Następnie wykonano
issue 17: lokalne widmo/autokorelacja i EWT, siatka/centra, 32 konfiguracje,
24 pełne klatki i 204 kontrole. Parametry wybrano na kontrolach rozwojowych;
częściowe referencje i odłożone ziarna oceniono później. Adaptacja EWT jest
jawnie odróżniona od publikacji STM z zadanym K. Nie trenowano modelu.

[Raport](image-texture-domains-trial.md),
[audyt API i publikacji](research-image-texture-adaptation-audit.md), podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/image-texture-domains/index.html`.
Wybrane warianty przypisują 0.3–5.8% centrów w referencjach, wyłącznie BLACK;
RED/YELLOW pominięte. Bramka przepuszcza 9.2–12.6% ocenianych miejsc.
EWT wcześniej tworzy jeden klaster całego zakresu. Na kontrolach scala małe
orientacje; widmo na siatce dzieli pojedynczą sieć. Zero fałszywych przypisań
na losowych punktach nie rekompensuje odmowy na TTMAPP. Filtr doboru nie
miał twardego warunku podziałów pojedynczej sieci; ujawniono brak, bez
zmiany rankingu po wynikach. Większe okno również nie rozwiązuje problemu.

Użytkownik zatwierdził: **„Tak — zachowaj porównanie i zamknij 17”**.
Issue 17 `resolved` jako badanie, bez wyboru metody produkcyjnej. Cechy,
przypisania i reguły zachowano dla 19/21/22. Następne 18 → 19 i niezależne
20 nie są uruchomione. Odbiór 13 i jakość 04 pozostają otwarte. W 19 i 13
zapisano konieczność rozdzielenia jakości cech od odmów bramki oraz oceny
podziałów jednej sieci. Nie mierzono pokrycia ani granic powierzchni.

Sprawdzenia: pełna ponowna ekstrakcja 228 obrazów bez wszystkich anotacji
i bez drzewa referencji — identyczne cechy siatki, 205 banków oraz wyniki
obu wybranych metod obrazowych. 60 dokładnych porównań braków/inwersji;
24 porównania kontrastu/skali z jawnymi drobnymi zmianami FFT. Zakres 5 → 24:
ponowne dopasowanie banku i katalogu; puste wyniki końcowe nie dowodzą
stabilności. 1824 wyniki zgodne z kontraktem, 228 odtworzonych wejść bez
anotacji, zgodność hashy kodu. QtWebEngine offscreen: 42 kontrole bez
błędów JS; obejrzano podgląd i wykres. Sprawdzono składnię Python/Bash
i diff. Etapy wykonano osobno; nie powtarzano całego przebiegu wrapperem.
Nie testowano produkcyjnej aplikacji, natywnego GUI ani pełnych 268 klatek.

CPU, po jednym wątku BLAS/OpenMP: ekstrakcja 842.47 s, predykcja 25.85 s,
ocena 3.64 s, pełna ekstrakcja bez anotacji 785.32 s. Maksymalny RSS
803324 KiB (~785 MiB). `pyewt 1.0.0` i `connected-components-3d 3.26.1`
wyłącznie w izolowanym `/tmp/stmdomains-issue17-deps`; netcat bez zmian.
Artefakty lokalne: 3455 plików, 891338928 B, kopia SHA-256 zgodna.
Brak potrzeb zmian wspólnego kodu lub konfiguracji. Dokumentacja trafia
wyłącznie do Domains; Viewer oraz gałąź integracyjna bez zmian tej sesji.

---

## Poprzednie przekazanie — SBC / MatID, issue 16

Data: 2026-10-23. Dokumentacja `domains/sbc-trial`, baza `9f2b127`,
worktree `/tmp/netcat-stmdomains-sbc`, docelowo `domains/start`.
Źródła: `prototype/stmdomains-sbc`, commit `e6d3fbc`, baza `2b70d0d`.
Nie scalać prototypu do aplikacji. Commit dokumentacji w wiadomości końcowej.

Na polecenie użytkownika przejścia do 16 zakończono issue 15 jako trzy
porównania, bez przyjęcia metody. Wykonano SBC/MatID: 228 próbek,
6 ustawień, surowa biblioteka i dwie jawne adaptacje punktowe. Kalibracja
na 102 kontrolach rozwojowych; pozostałe kontrole i TTMAPP ocenione później.
Żadna konfiguracja nie spełniła kompletu warunków. Wybrany diagnostycznie
wariant: tolerancja 1.8 px, maksymalny wektor komórki 42 px, połączenie
19.8 px, zerowe promienie także wewnątrz walidacji prototypu, zachowanie
wszystkich komponentów ≥8 i odmowa nakładającym się propozycjom.

[Raport](sbc-matid-domains-trial.md), [audyt API](research-sbc-adaptation-audit.md)
i podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/sbc-matid-domains/index.html`.
SBC poprawia 30% braków (99.8% przypisań), deformację i granicę przesunięcia
z błędami centrów (0.2% scaleń przy 52.2% przypisań). Jednak scala różnicę
orientacji 8° i tworzy pozorne obszary z 355/3195 losowych punktów.
TTMAPP: 63.5% przypisań, 5.9% podziałów i 5.5% scaleń warunkowych par,
wobec 70.7% / 2.8% / 0% poprzedniej komórki. Zmiana ziarna powoduje
znaczne zmiany wyniku. Komórka biblioteki jest prototypem, nie globalnym fitem.

Issue 16 **`resolved`**: użytkownik zatwierdził zachowanie porównania
i przejście następnie do tekstury 17. Zakończenie próby nie wybiera
metody produkcyjnej. Odbiór 13 i jakość 04 pozostają otwarte. Nie wybrano metody
produkcyjnej, nie mierzono powierzchni ani nie tworzono katalogu typów.

Sprawdzenia: 228/228 identycznych ponownych wyników i śladów etapów bez
referencji, po przestawieniu punktów i odwróceniu kolejności klatek;
684 wyniki zgodne z kontraktem. Kontrast/inwersja/skala: po 6 par;
obrót 37°: identyczne przypisania na 10 próbkach. Zmiana kategorii H/C
zmienia raw, lecz nie adaptację. Sprawdzono także 2 dodatkowe ziarna,
wejście bez kanonizacji i bezpośrednie zachowanie czyszczenia. 35 kontroli
lokalnego HTML w QtWebEngine bez błędów JS; obejrzano zrzut i wykres.
Sprawdzono składnię Python/Bash i diff. Nie testowano natywnego GUI ani
produkcji, nie wykonano pełnego benchmarku 268 klatek. Ostrzeżenia
numeryczne jednej kontroli zapisano w artefaktach; nie było przerwania próby.

CPU, jeden wątek BLAS/OpenMP: 91.05 s kalibracyjnych predykcji,
224.07 s dla 228 próbek × 6 ustawień; RSS 223844 KiB (~219 MiB).
Zbudowano MatID 2.2.0 z commita `5aa27776` i spglib 2.6.0 w izolowanym
`/tmp/stmdomains-issue16-deps`. Środowisko netcat, kod wspólny i główna
konfiguracja bez zmian. Dane/duże wyniki pozostają lokalne (3594 pliki,
564478701 B; kopia zweryfikowana SHA-256). Dokumentacja trafia wyłącznie
do Domains; Viewer i integracja bez zmian.

---

## Poprzednie przekazanie — orientacja i łączenie, issue 15


Data: 2026-10-23. Dokumentacja: `domains/orientation-trial`, baza `8065aea`,
worktree `/tmp/netcat-stmdomains-orientation`, docelowo `domains/start`.
Źródła: `prototype/stmdomains-orientation`, commit `2b70d0d`, baza `bc3763e`.
Nie scalać prototypu do aplikacji. Commit dokumentacji w wiadomości końcowej.

Wykonano proponowane badanie orientacji oraz łączenia sąsiadów: 31
wariantów, 24 pełne klatki i 204 kontrole. Zamrożono powtarzalność,
minimum 8 elementów i dawny katalog. Główny wynik ocenia obszary bez
warunku typu; katalog stanowi osobne porównanie. Wybrany na kontrolach
wariant komórki wymaga ≥65% dopasowanych punktów, różnicy bazy ≤0.12,
fazy ≤0.30 rozstawu i zgodności z punktem rozpoczynającym obszar.

[Raport](orientation-and-joining-trial.md) i podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/orientation-and-joining/index.html`.
Przy 30% braków: jedna domena, 81.9% przypisań zamiast 2–3 fragmentów
z 46.7%. TTMAPP: 70.7% zamiast 62.5%, scalenia 0/3801 ocenianych par
różnych regionów zamiast 708/2329. RED jednak spada z 28/101 do 14/101;
YELLOW nadal tylko 48/274. Granica przesunięcia z błędem centrów ma 98.1%
scaleń, a łagodna deformacja 51.0% podziałów. Same krawędzie tworzą
łańcuchy łączące różne orientacje; zgodność ze startem ogranicza to kosztem
deformacji. Sprawdzanie fazy na krawędziach nie naprawia trudnej granicy.

Stan **`claimed` do omówienia**. Komórka jest punktem odniesienia, bez
wyboru metody produkcyjnej. Proponowany następny krok: porównanie 16
na rozszerzonych kontrolach, osobno oceniając zaburzoną granicę przesunięcia,
małe różnice orientacji i RED/YELLOW. Nie uruchomiono 16/17 ani treningu;
odbiór 13 i jakość 04 pozostają otwarte. Opis kierunków to wariant
diagnostyczny: żaden nie spełnił wszystkich zapisanych warunków wyboru.

Sprawdzenia: dokładne odtworzenie 204 wcześniejszych wyników głównych
oraz z katalogiem; 1368 wyników zgodnych z kontraktem; kontrast/skala;
obrót 37° czterech kontroli daje identyczne przypisane pary wszystkich
31 wariantów. Przed oceną referencji naprawiono remisy numeryczne i
ponowiono obliczenia. Pełna ponowna ekstrakcja/predykcja bez referencji,
ze zmianą kolejności: 228 identycznych plików cech i 228 wyników.
QtWebEngine offscreen: 14 kontroli bez błędów JS; obejrzano zrzut i wykres.
Nie wykonano testów produkcyjnej aplikacji, natywnego GUI ani benchmarku
268 klatek. Nie oceniano granic pikselowych lub pokrycia warstwy.

CPU, jeden wątek BLAS/OpenMP. Ekstrakcja 205.11 s, wybór 40.47 s,
predykcja 186.77 s, ocena 2.80 s; szczyt procesowego RSS 264000 KiB
(~258 MiB), bez GPU/treningu. Bez instalacji pakietów i zmian wspólnych
modułów, środowiska lub konfiguracji. Artefakty lokalne poza Git.
Dokumentację przenosimy tylko do Domains; Viewer i integracja bez zmian.

---

## Poprzednie przekazanie — kryterium powtarzalności, kontynuacja issue 15

Data: 2026-10-23. Gałąź dokumentacji `domains/recurrence-trial`, baza
`12f3652`, worktree `/tmp/netcat-stmdomains-recurrence`, docelowo `domains/start`.
Źródła prototypu: `prototype/stmdomains-recurrence`, commit `bc3763e`,
baza `1f25b45`. Nie scalać kodu prototypu do aplikacji. Commit dokumentacji
w wiadomości końcowej; duże wyniki pozostają lokalne.

Na polecenie „zbadaj kryterium powtarzalności” wykonano kontrolowane
porównanie 38 wariantów na 24 pełnych klatkach i 180 kontrolach. Zamrożono
katalog SOAP/36 i reguły przestrzenne. Usunięto gwarantowane trafienie
środka przy przesunięciu, porównano promienie, tolerancje i progi
kalibrowane wyłącznie na kontrolach rozwojowych. Wybrany wariant:
R=36 px, tolerancja 24% lokalnego rozstawu, wynik >0.25.

[Raport](recurrence-criterion-trial.md) i podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/recurrence-criterion/index.html`.
Warunek przechodzi 90.9% zamiast 34.0% oznaczeń we wnętrzach referencji;
domenę otrzymuje 62.5% zamiast 31.0%. To nie dokładność: 708/2329 = 30.4%
przypisanych par z różnych regionów scalono w jedną domenę. W YELLOW
nadal tylko 13/274 centrów ma domenę; wiele pozostałych odpada na zbyt
małych składowych zgodnych orientacyjnie. Losowe kontrole: 2/3195 akceptacji,
zero składowych. Przy błędzie centrów 0.72 px akceptacja regularnej sieci
rośnie z 13.3% do 95.5%, lecz duże braki nadal powodują podziały/odmowy.
Rzędy z niezależną fazą pokazują, że lokalna powtarzalność nie wystarcza
jako dowód spójnej domeny 2D; nie mają kompletnej prawdy domen.

**Issue 15 nadal `claimed`**: użytkownik wcześniej wybrał rozwinięcie próby,
a obecne zlecenie dotyczyło tego kryterium, nie zamknięcia całego pytania.
Nie uruchomiono 16 ani treningu. Następny proponowany eksperyment:
estymacja orientacji i lokalnej komórki oraz łączenie sąsiadów, z kontrolą
scaleń, braków i skorelowanych struktur. Katalog rozstawów pozostaje osobną
luką. Bez wyboru metody produkcyjnej; odbiór 13 i protokół 04 nadal otwarte.

Sprawdzenia wykonane: dokładne odtworzenie starego warunku i domen na
156 próbkach, monotoniczność wyniku na 204, obrót/kolejność/kontrast/skala,
walidacja 1020 wyników. Dwa pełne powtórzenia bez referencji, jedno także
z losową kolejnością: po 204 identyczne pliki NPZ z 38 wariantami.
Ponowne przygotowanie wejścia końcowym kodem: identyczne 205 plików analizy
oraz 199 oceny. QtWebEngine offscreen: 13 kontroli bez błędów JS;
obejrzano zrzut i wykres. Nie wykonano testów produkcyjnej aplikacji,
natywnego GUI ani pomiaru 268 klatek. Nowe kontrole bez dopasowanego
katalogu oceniono tylko dla warunku/składowych bez typu; patrz raport.

CPU, jeden wątek BLAS/OpenMP. Ekstrakcja 29.61 s, wybór 3.71 s,
predykcja wszystkich wariantów 24.98 s, ocena 3.10 s; szczyt procesowego
RSS 217 780 KiB (~213 MiB), bez GPU/treningu. Brak instalacji pakietów,
zmian środowiska, wspólnych modułów lub głównej konfiguracji. Artefakty
~230 MB poza Git. Przekazanie ogranicza się do dokumentacji Domains;
nie aktualizowano gałęzi Viewer ani integracyjnej.

---

## Poprzednie przekazanie — pierwsza próba otoczeń molekuł, issue 15

Data: 2026-10-23. Gałąź dokumentacji `domains/local-neighborhood-trial`,
baza `76dd4a3`, worktree `/tmp/netcat-stmdomains-neighborhoods`.
Źródła prototypu: osobna gałąź `prototype/stmdomains-neighborhoods`,
commit `1f25b45`. Nie scalać prototypu do aplikacji.

Wykonano porównanie prostego opisu odległości/kątów i SOAP, promieni
24/36 px, wspólnego HDBSCAN bez K, oceny powtarzalności i przestrzennych
składowych. 24 pełne klatki TTMAPP + 132 kontrole, 624 kompletne wyniki.
[Raport](local-neighborhood-domains-trial.md) zawiera parametry, tabele,
odmowy, stabilność, koszty i ograniczenia. Podgląd lokalny:
`/home/rlew/projekty/NEtCAT-domains/.scratch/local-neighborhood-domains/index.html`.

Stan **`claimed`**, nie `resolved`: użytkownik po przedstawieniu wyniku
wybrał „Najpierw omówmy lub rozwińmy tę próbę”. Nie uruchomiono 16.
SOAP/36 przypisuje 31.0% centrów w referencjach, tylko BLACK; RED/YELLOW
odpadają na kryterium powtarzalności mimo przeważnie wystarczającej liczby
sąsiadów. Proponowana kolejna próba w 15 ma zbadać ten warunek i tolerancję
położeń z kontrolą fałszywego porządku. Nie została jeszcze uruchomiona.
Pozostają też nadmierne podziały prostego opisu i scalenia typów SOAP.

Wykonane sprawdzenia: walidacja 624 wyników, rotacja/kontrast/skala/braki,
rzadki układ, rozszerzenie 5 → 24. Powtórna ekstrakcja/predykcja bez
referencji: 624 pliki identyczne bajtowo. Losowa kolejność oznaczeń/klatek:
624 identyczne zestawy przypisań po sortowaniu ID. QtWebEngine offscreen:
15 kontroli scenariuszy/widoków/referencji, bez błędów JS; obejrzano zrzut.
Naprawiono błąd numeryczny granicy promienia i powtórzono całość przed
końcowym raportem. Nie testowano aplikacyjnego GUI, nie uruchamiano
testów produkcyjnych ani pomiaru 268 klatek. Brak zmian produkcyjnych.

Ekstrakcja 12.24 s, dopasowanie/predykcja/zapis 42.31 s, szczyt RSS
330 636 KiB, CPU, bez GPU. Zależności dodatkowe DScribe 2.1.2 i sparse
0.19.2 wyłącznie w `/tmp/stmdomains-issue15-deps`; `netcat` bez zmian.
Nie ma nowych potrzeb zmian wspólnego kodu ani konfiguracji. Dane,
cechy, duże wyniki i podgląd pozostają lokalne. Mapa i indeks zachowują
otwartą dyskusję; odbiór 13 i jakość 04 nadal otwarte.

---

## Poprzednie przekazanie — przygotowanie wspólnego wejścia, issue 14

Data: 2026-10-23. Gałąź `domains/unsupervised-input`, baza `d134439`.
Worktree `/tmp/netcat-stmdomains-input`, docelowo `domains/start`.
Commit kodu, testów i dokumentacji w wiadomości końcowej.

Wykonano issue 14: `stmdomains.experiments` przygotowuje audytowane obrazy
MPP i bieżące oznaczenia w raw, 132 kontrole syntetyczne oraz osobny pakiet
oceny z 18 referencjami/54 wnętrzami. Pilot ma 24 pełne klatki i 6730
oznaczeń, włącznie z klatką 255. Generator nie uruchamia detektora ani treningu.

[Raport](unsupervised-input-preparation.md) zawiera polecenie odtworzenia;
[protokół](experiment-input-protocol.md) definiuje schematy wejścia/wyniku,
miary z odmowami i warunki porównania. Lokalny artefakt:
`/home/rlew/projekty/NEtCAT-domains/.scratch/unsupervised-input/index.html`.
Dane, obrazy, maski i duże manifesty pozostają poza Git.

Sprawdzenia: 35 testów pytest w `netcat`, oba źródłowe SHA-256, geometria
6730 bboxów (roundtrip 0 px), dokładne odtworzenie 18 PNG i zgodność masek
z poprzednim audytem. Wszystkie 156 próbek przechodzą walidację. Wszystkie
157 plików analizy są identyczne po ponownym przygotowaniu bez referencji.
Obejrzano statyczny arkusz podglądów i sprawdzono składnię JS w QJSEngine;
interakcji DOM w przeglądarce oraz natywnego GUI aplikacji nie testowano.
Przygotowanie końcowe: 5,89 s, RSS 445 916 KiB; bez GPU.

Issue 14 ma status `resolved`. Mapa i indeks wskazują 15 jako następny
zalecany eksperyment; odblokowane także 16, 17, 18 i 20. 04 i 13 pozostają
otwarte. Ograniczenia: adapter tylko dla audytowanego TTMAPP, częściowe
używane już referencje, brak rzeczywistej kalibracji i niezależnej akwizycji.
Nie wykonano nowego algorytmu, pełnego eksportu 268 klatek ani pomiaru pokrycia.

Wykorzystano istniejący czytnik MPP bez zmian. Ekstrakcję referencji
przeniesiono z audytowanego prototypu `4e7a757` do lokalnego modułu oceny.
Brak nowych potrzeb zmian wspólnego kodu, konfiguracji i środowiska.

---

## Poprzednie przekazanie — mapa prób treningu bez etykiet

Data: 2026-10-21. Gałąź `domains/self-supervised-training-map`, baza `63c5d0b`.
Worktree `/tmp/netcat-stmdomains-training-map`, docelowo `domains/start`.
Commit dokumentacji w wiadomości końcowej.

Na polecenie użytkownika rozwinięto ostatnie badanie w
[siedem ticketów 20–26](issues/README.md#trening-bez-etykiet-domen):
przygotowanie treningu, porównanie AE/rVAE, lokalne SSL, decyzję po pierwszych
próbach oraz warunkowe grafy, maskowany AE i adaptację gotowego modelu.
Wszystkie mają status `open`; żadnego modelu nie wytrenowano.

Przygotowanie 20 zależy od wspólnego wejścia 14. Próby 21 i 22 zależą od
20 oraz wyniku tekstury 17, mogą być prowadzone niezależnie. Zestawienie 23
czeka na 19, 21 i 22. Odbiór 13 uzupełniono o 23. Rozszerzenia 24–26 są
warunkowe i nie blokują odbioru, dopóki nie wybierzemy ich w 23; wtedy
należy dodać odpowiednie zależności 13 i krawędzie diagramu. Tracker wyklucza
niewybrane rozszerzenia z frontier mimo spełnienia samych zależności.

Zakres zachowuje pełne pola pomiarowe, brak etykiet domen i zadanej liczby
grup, osobne typ/orientację, kontrolę rozstawu oraz granic. Protokół oddziela
opis obecnej serii od oceny przenoszenia, z podziałem przed wycinaniem okien,
kontrolą przecieku, budżetem, powtórzeniami i odtwarzalnymi checkpointami.
Pierwszy sprzęt to RTX 5090; 96 GB i Colab są opcjami uzasadnianymi pomiarem.

Zaktualizowano mapę, indeks z diagramem, odnośniki ze wcześniejszego planu,
README i badania oraz wspólne wejście 14. Zakres 18–19 pozostaje zamrożony,
statusy zakończonych prób 10–12 i mapa szkieletu bez zmian. Następny krok
badawczy nadal to 14. Nie zmieniono kodu ani współdzielonych zależności.

Sprawdzenia dokumentacji: lokalne linki, unikatowe ID, zgodność `Blocked by`
z `Dependencies` i diagramem, brak cykli oraz `git diff --check`.
Nie uruchamiano testów aplikacji, GUI, modeli ani nowych pomiarów sprzętu.
Brak nowych potrzeb zmian współdzielonych modułów.

---

## Poprzednie przekazanie — trening bez etykiet do odkrywania domen

Data: 2026-10-21. Gałąź `domains/self-supervised-training-research`, baza `a298c1d`.
Worktree `/tmp/netcat-stmdomains-training-research`, docelowo `domains/start`.
Commit dokumentacji w wiadomości końcowej.

Na polecenie użytkownika, z użyciem `research`, przygotowano
[przegląd metod uczonych bez etykiet](research-self-supervised-domain-learning.md).
Użytkownik dopuścił własny trening i wskazał RTX 5090 32 GB VRAM / 128 GB RAM,
a przy dobrych wynikach drugi komputer z Blackwell Max-Q 96 GB VRAM lub Colab.
Zgoda na trening nie zmienia zakazu uczenia klas z ręcznie wskazanych domen
ani wymagań zero/jedna/wiele domen i rozdzielenia typu od orientacji.

Raport rozróżnia bezpośrednie precedensy STM/AFM/PFM od adaptacji ogólnego
uczenia reprezentacji. Zaleca najpierw ciągły rVAE i lokalne uczenie cech,
następnie rozważenie grafu molekuł lub maskowanego autoenkodera. Zawiera
ograniczenia narzuconej liczby kategorii, utraty orientacji/fazy, przecieku
danych i kosztu. Potrzebne są osobne oceny obecnej serii oraz uogólnienia.

Mapę, README i plan uzupełniono o nowy zakres. We wspólnym wejściu usunięto
ogólne wykluczenie treningu; dotychczasowe tickety przygotowania i porównania
gotowych cech nadal dotyczą modeli zamrożonych. Nie dodano ani nie zamknięto
ticketów treningowych przez samo badanie źródeł.

Sprawdzenia: publikacje i repozytoria autorów, lokalne odnośniki, zachowanie
metadanych ticketów i `git diff --check`. Odczytano GPU/sterownik przez
`nvidia-smi` poza piaskownicą oraz metadane lokalnego `netcat`; brak pomiarów
wydajności treningu i pełnego sprawdzenia zgodności bibliotek. Nie uruchamiano
modeli, nie instalowano zależności, nie pobierano wag ani nie przenoszono
danych na drugi komputer lub do Colab. Bez zmian kodu i testów aplikacji.
Brak nowych potrzeb zmian współdzielonych modułów.

---

## Poprzednie przekazanie — zadania przygotowania i porównania ML

Data: 2026-10-21. Gałąź `domains/training-free-ml-map`, baza `abf7869`.
Worktree `/tmp/netcat-stmdomains-ml-map`, docelowo `domains/start`.
Commit aktualizacji dokumentacji w wiadomości końcowej.

Na polecenie użytkownika rozwinięto wnioski przeglądu ML w dwa otwarte
tickety istniejącej mapy `wayfinder`:

- [Przygotowanie gotowych cech bez własnego treningu](issues/18-frozen-feature-preparation.md)
  — task / AFK, po wspólnym wejściu. Modele, geometria cech, zapis
  konfiguracji i sprawdzenie odtwarzalności; bez oceny skuteczności domen.
- [Porównanie domen z gotowych cech](issues/19-frozen-feature-domains.md)
  — prototype / HITL, po przygotowaniu cech i wyniku klasycznej tekstury.
  FCN–ResNet101 i DINOv2, opcjonalnie DINOv3, bez uczenia na ramkach
  i bez treningu wag. Grupowanie nienadzorowane jest dozwolone.

Próba tekstury zachowuje autokorelację/EWT; jej wynik jest punktem
odniesienia dla ML, nawet jeśli nie wykrywa domen poprawnie. Geometria
otoczenia molekuł pozostaje niezależnym porównaniem. Wspólne wejście
uzupełniono o metadane modeli i kontrolę skalowania; nie czeka na wagi.
Odbiór metod zależy również od wyniku porównania ML. DINOv3 i własny trening
sieci nie są nowymi obowiązkowymi etapami. Zaktualizowano mapę, indeks,
diagram zależności, README oraz odnośniki w planie i raporcie badawczym.

Sprawdzenia: lokalne odnośniki, kompletność metadanych i indeksu, zgodność
zależności z linkami i diagramem, brak cykli oraz `git diff --check`.
Bez uruchamiania eksperymentów, instalacji, pobierania wag, testów aplikacji
i odbioru GUI. Wszystkie nowe zadania pozostają `open`, bez prowadzącego.
Nie zmieniono danych, kodu ani konfiguracji wspólnych modułów.

---

## Poprzednie przekazanie — ML bez własnego treningu do odkrywania domen

Data: 2026-10-21. Gałąź `domains/training-free-ml-research`, baza `2a35377`.
Worktree `/tmp/netcat-stmdomains-ml-research`, docelowo `domains/start`.
Commit aktualizacji dokumentacji w wiadomości końcowej.

Na polecenie użytkownika, z użyciem `research`, przygotowano
[przegląd ML i gotowych sieci](research-training-free-ml-domain-discovery.md)
na podstawie publikacji, kodu i kart modeli autorów. Odróżniono grupowanie
nienadzorowane, użycie zamrożonego modelu i własny trening bez etykiet.
Pierwsze dwa kierunki pozwalają wykonać próby bez uczenia na zaznaczonych
domenach użytkownika; nie potwierdzono gotowego rozwiązania całego zakresu.

Do [kroku 17](issues/17-image-texture-domains.md) dodano propozycję
porównania autokorelacji/EWT z wczesnymi cechami FCN–ResNet101 oraz DINOv2,
opcjonalnie DINOv3. Gotowe cechy obrazowe można próbkować na siatce i przy
istniejących centrach. Krok 15 zachowuje niezależną bazę geometryczną.
Mapę i README uzupełniono o raport; numeracja, zależności i statusy ticketów
pozostają aktualne. Następny krok badawczy to nadal przygotowanie wejścia
14, potem próby 15–17 i odbiór 13 z protokołem jakości 04.

Sprawdzenia: źródła pierwotne, lokalne odnośniki, zachowanie metadanych
ticketów i `git diff --check`. Bez uruchamiania modeli, pobierania wag,
instalacji zależności, testów aplikacji i odbioru GUI. Wydajność oraz
skuteczność na TTMAPP wymagają dopiero eksperymentu. Brak zmian danych,
kodu produkcyjnego i nowych potrzeb wspólnych modułów.

---

## Poprzednie przekazanie — nowe tickety prób samodzielnego wykrywania domen

Data: 2026-10-21. Gałąź `domains/unsupervised-experiment-map`, baza `5a7209c`.
Worktree `/tmp/netcat-stmdomains-experiment-map`, docelowo `domains/start`.
Commit aktualizacji dokumentacji w wiadomości końcowej.

Na polecenie użytkownika przeniesiono plan eksperymentów do istniejącej
[mapy metod i zapisu](map-methods-and-save.md), zgodnie z lokalnym trackerem
`wayfinder`. Dodano cztery otwarte zadania/pytania:

- [Wspólne wejście i kontrole](issues/14-unsupervised-input-and-controls.md) — task / AFK.
- [Otoczenie zaznaczonych molekuł](issues/15-local-neighborhood-domains.md) — prototype / HITL.
- [SBC/MatID z niepełnych centrów](issues/16-sbc-matid-domains.md) — prototype / HITL.
- [Lokalna tekstura STM](issues/17-image-texture-domains.md) — prototype / HITL.

Przygotowanie wejścia zależy od rozstrzygniętych kontraktów importu i pojęć;
trzy niezależne próby zależą od tego przygotowania. Rozszerzono zależności
[odbioru metod](issues/13-method-acceptance.md) o wyniki trzech prób.
[Pełny protokół jakości](issues/04-reference-and-quality.md) nadal jest
wymagany do odbioru, ale nie blokuje wstępnego porównania na obecnych danych.
Zakończonych badań pokrycia, typów i granic nie otwarto ponownie.

Następny krok w tym cyklu badawczym to przygotowanie wspólnego wejścia;
pierwszą zalecaną próbą jest otoczenie molekuł. Analiza obejmuje pełne pola
klatek bez dostępu do ramek referencji, z przypadkami zero/jedna/wiele domen.
Zaktualizowano rejestr, diagram i README; mapa jest indeksem, a dawny plan
prowadzi do ticketów przechowujących szczegóły. Nie rozwiązano nowych pytań
ani nie uruchomiono eksperymentów przez tę aktualizację.

Sprawdzenia dokumentacji: lokalne odnośniki, kompletność metadanych,
zgodność zależności z linkami i diagramem, brak cykli oraz `git diff --check`.
Bez testów aplikacji, analizy danych, instalacji zależności i odbioru GUI.
Brak zmian produkcyjnych lub nowych potrzeb wspólnych modułów. Wcześniejsze
wyniki i ustalenia integracyjne poniżej pozostają aktualne.

---

## Poprzednie przekazanie — samodzielne wyszukiwanie domen w STM/AFM

Data: 2026-10-21. Gałąź `domains/stm-afm-unsupervised-research`,
baza `53e5fb4`. Worktree `/tmp/netcat-stmdomains-stm-afm-research`,
docelowo `domains/start`. Commit dokumentacji w wiadomości końcowej.

Na bezpośrednie polecenie użytkownika, z użyciem `research`, przygotowano
[przegląd STM/AFM](research-stm-afm-unsupervised-domain-discovery.md)
i [plan kolejnych eksperymentów](unsupervised-domain-experiments.md).
Publikacje dostarczają nienadzorowanych sposobów analizy, lecz w sprawdzonych
źródłach nie potwierdzono jednego gotowego rozwiązania całego zakresu.
Sprawdzono szczególnie narzucaną liczbę grup, wybór wzorców oraz różnicę
między odtworzeniem komórki, grupowaniem cech i domeną przestrzenną.

Doprecyzowanie użytkownika: gotowe oznaczenia molekuł są wejściem; nie
zakładamy istnienia domen i nie trenujemy klasyfikatora na wybranych domenach.
Plan obejmuje analizę pełnych pól klatek, bez masek referencji na wejściu,
oraz kontrole zero/jedna/wiele domen. Ramki służą wyłącznie późniejszej,
częściowej ocenie. To rozszerzenie zakresu następnej próby względem lokalnych
badań wnętrz w krokach 10–12, nie zmiana dawnych wyników. Nieoznaczone
obszary nie stają się negatywnymi przykładami.

Kolejność planu: wspólne kontrole i opis otoczenia centrów, potem SBC/MatID
oraz lokalna tekstura obrazu na tym samym wejściu. Porządek, podobieństwo,
spójność przestrzenna i powierzchnie materiału pozostają rozdzielone.
Plan nie został wykonany, metody nie wybrano. Kroki 10–12 nadal `resolved`
jako zakończone badania; protokół 04 i odbiór 13 pozostają otwarte.

Sprawdzenia: źródła pierwotne, teksty metod i wskazane repozytoria autorów;
kontrola lokalnych odnośników nowych/zmienionych dokumentów oraz
`git diff --check`. Bez instalacji zależności, nowego przetwarzania TTMAPP,
testów aplikacji i odbioru GUI. Nie zmieniono danych ani kodu produkcyjnego.
Brak nowych potrzeb wspólnych modułów; wcześniejsze ustalenia poniżej.

---

## Poprzednie przekazanie — badanie metod domen i klastrowania obiektów

Data: 2026-10-21. Gałąź `domains/general-domain-clustering-research`,
baza `035bc11`. Worktree `/tmp/netcat-stmdomains-general-research`,
docelowo `domains/start`. Commit dokumentacji w wiadomości końcowej.

Na polecenie użytkownika i z użyciem umiejętności `research` przygotowano
[przegląd źródeł pierwotnych](research-domain-discovery-and-object-clustering.md).
Obejmuje grupowanie centrów, opis otoczenia obiektów, SBC/MatID, teksturę
obrazu oraz łączenie przestrzenne z użyciem grafów. Rozróżnia wyniki publikacji,
właściwości dostępnego kodu i nasze propozycje transferu do STM Domains.

Rekomendowane porównanie obejmuje trzy kierunki: cechy otoczenia i grupowanie,
SBC dla periodycznych punktów oraz teksturę obrazu. MolTrack pozostaje
porównaniem. Nie wybrano metody, nie wykonano nowego eksperymentu i nie
zmieniono statusów 10–13. Nie rozszerzono produkcyjnego zakresu aplikacji.

Wykonano przegląd publikacji, dokumentacji i wskazanych fragmentów kodu,
kontrolę lokalnych odnośników i `git diff --check`. Odczytano wersje pakietów
z metadanych `netcat`; nie instalowano zależności ani nie uruchamiano metod,
testów aplikacji czy GUI. Wydajność i jakość kandydatów na TTMAPP pozostają
do sprawdzenia. Brak nowych potrzeb zmian wspólnych modułów; wcześniejsze
ustalenia integracyjne zachowano poniżej.

---

## Poprzednie przekazanie — audyt MolTrack

Data: 2026-10-21. Gałąź `domains/moltrack-method-audit`, baza `2e0c8d1`.
Worktree `/tmp/netcat-stmdomains-moltrack-audit`, docelowo `domains/start`.
Commit dokumentacji podany w wiadomości końcowej.

[Audyt](moltrack-method-audit.md) opisuje rzeczywiste ścieżki M6, M3/M6,
teksturę A/B/C oraz ograniczenie klasyfikatora do wcześniej wyznaczonych
domen. Rozróżnia przybliżenie powierzchni wokół centrów od sumy masek/bboxów;
żadne nie jest automatycznie powierzchnią całego płata.

Użytkownik wskazał potrzebę ogólnego znajdowania domen poza wariantami
znanego układu. Zapisano propozycję próby lokalnego wzoru obrazu w kilku
skalach, z osobnym typem i orientacją. MolTrack jest materiałem porównawczym.
Nie zatwierdzono nowego algorytmu ani wymagania pracy całkowicie bez oznaczeń.
Kroki 10–12 pozostają `resolved`; odbiór 13 i protokół jakości 04 są otwarte.

Wykonano audyt kodu i odnośników oraz `git diff --check`. Nie uruchamiano
algorytmów, testów aplikacji ani GUI. Brak zmian produkcyjnych, nowych danych
i nowych potrzeb wspólnych modułów. Dotychczasowe potrzeby integracyjne
opisane niżej pozostają aktualne.

---

## Poprzednie przekazanie — krok 12

Data: 2026-10-21. Gałąź dokumentacji: `domains/phase-boundaries`.
Baza `a103f99`, claim `2cd4e02`; commit raportu podany w wiadomości końcowej.
Worktree `/tmp/netcat-stmdomains-boundaries`, docelowo `domains/start`.
Źródła: **`prototype/stmdomains-boundaries`, `c33cc5b` — nie scalać do aplikacji.**

[Krok 12](issues/12-phase-boundaries.md) zakończono jako eksperyment (`resolved`).
[Raport](phase-boundaries-trial.md) obejmuje 7 wariantów, 19 kontroli
syntetycznych i 18 klatek / 54 wnętrza TTMAPP. Wynik gotowy do oceny użytkownika;
nie deklarujemy zatwierdzenia metody ani parametrów.

Niedopasowanie wektorów między centrami rozdziela proste domeny kontrolne
przy przesunięciu 4/8 px bez dzielenia przez pojedynczy defekt. Nie wykrywa
1 px, zależy od centrów i wiarygodnej sieci. Dwa piki przyjęto tylko w 7/54
wnętrz TTMAPP. Prosta faza obrazu daje nadmierne cięcia i myli odwrócenie
kontrastu z granicą. Komponenty grafu nie są powierzchniami domen; rozłączenie
przez brak danych nie oznacza wyznaczonej linii. Dokładność granic realnych
nie jest dostępna z obecnych przybliżonych ramek orientacyjnych.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/phase-boundaries-trial/index.html`.
Obok pełny JSON, CSV, inspekcje i zrzuty. Parametry, hashe, metryki i polecenie
odtworzenia są w raporcie i README prototypu. Poza wnętrzami nie pobierano
pikseli do obliczeń; dane źródłowe i maski pozostały niezmienione.

Wykonane sprawdzenia: tożsamość wejścia i geometria, 95 389 węzłów we wnętrzach,
6854 środków cięć, 87 365 pełnych okien fazy; 76 niezależnych kontroli miar par;
6 niezmienionych wyników fazowych po usunięciu samych centrów i niezależność
od otoczenia referencji na kontroli oraz TTMAPP 258. QtWebEngine: 37 przypadków,
7 metod, 24 kroki, wybory/nakładki/gamma/nawigacja/tabela/reset/brak wyniku;
bez błędów JS, obejrzano zrzuty. Generator 3,91 s przed końcowym JSON/CSV,
588,59 MiB RSS; HTML 4 500 199 B. Sprawdzono linki i `git diff --check`.
Nie uruchamiano testów aplikacji ani nie wykonywano odbioru użytkownika.

Próby 10–12 są zakończone. Ograniczenia przekazano do otwartego odbioru 13;
04 opisuje konkretną przyszłą potrzebę referencji granicy przesunięcia.
Nowych anotacji nie żądano przed zakończeniem eksperymentu. Brak zmian
wspólnych i produkcyjnych. Wcześniejsze ustalenia integracyjne poniżej.

---

## Poprzednie przekazanie — krok 11

Data: 2026-10-21. Gałąź dokumentacji: `domains/structural-type-catalogue`.
Baza `8b16b8c`, claim `d8cdd77`; commit raportu i przekazania podany w wiadomości
końcowej. Worktree `/tmp/netcat-stmdomains-types`, docelowo `domains/start`.
Źródła: **`prototype/stmdomains-types`, `f2608c7` — nie scalać do aplikacji.**

[Krok 11](issues/11-structural-type-catalogue.md) zakończono jako eksperyment
(`resolved`). [Raport](structural-type-catalogue-trial.md) obejmuje 9 wariantów,
18 klatek / 54 wnętrza TTMAPP oraz 19 kontroli syntetycznych. Użytkownik
wyjaśnił, że kolory oznaczają głównie różne orientacje tej samej sieci.
Wynik przygotowano do obejrzenia; nie deklarujemy zatwierdzenia algorytmu.

Cechy rozstawu i różnic odległości pozwalają rozdzielić proste struktury
kontrolne bez zmiany typu po obrocie. Cecha rozwijana na tych kontrolach nie
ma niezależnej walidacji. Na TTMAPP tworzy 34 grupy kandydatów; zmiana zakresu
zmienia 11,29% relacji par. Ubytki centrów, defekty, rozmiar okna i fałszywy
porządek w szumie pozostają problemem. Wąski RED często nie mieści pełnego
pomiaru; taki brak danych nie oznacza nieporządku. Nie wybrano metody.
Luki przekazano do otwartego odbioru 13; krok 12 osobno bada granice.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/type-catalogue-trial/index.html`.
Obok JSON, CSV dostępności/cech/przypisań, zestawienie i raporty inspekcji.
Źródła, parametry, hashe i polecenie odtworzenia opisują raport oraz README
prototypu. Pełny obszar każdej cechy mieści się w referencji i fizycznym polu.

Wykonane sprawdzenia: tożsamość wejścia i geometria, 7014 pomiarów z poprawnym
wsparciem, 349 średnic grup i 81 okien niezależnych od otoczenia. FFT pozostaje
identyczne po usunięciu samych centrów. QtWebEngine: 37 przypadków, 9 wariantów,
26 kroków scenariuszy, wybory/nakładki/gamma/nawigacja/reset/brak wyniku;
bez błędów JS. Obejrzano zrzuty. Generator: 7,10 s przed CSV / 618,43 MiB RSS;
HTML 16 068 171 B. Sprawdzono linki dokumentacji i `git diff --check`.
To inspekcja eksperymentu; nie uruchamiano testów aplikacji ani nie wykonano
odbioru użytkownika. Kod produkcyjny, dane i maski źródłowe pozostały bez zmian.

Brak nowych potrzeb wspólnych modułów. Wcześniejsze ustalenia integracyjne
pozostają w przekazaniach poniżej. Duże wyniki lokalne, bez publikacji.

---

## Poprzednie przekazanie — zakończenie kroku 10

Data: 2026-10-21. Gałąź dokumentacji: `domains/coverage-and-scale`.
Raport próby: `25c6aba`; obecna zmiana zamyka status po omówieniu wniosków.
Worktree: `/tmp/netcat-stmdomains-coverage`; docelowo `domains/start`.
Commit dokumentacji podany w wiadomości końcowej. Źródła prototypu:
**`prototype/stmdomains-coverage`, `e67ca93` — nie scalać do aplikacji.**

[Próba zadania 10](coverage-partial-reference-trial.md): wykonano 10 wariantów
na 18 klatkach / 54 wnętrzach częściowej referencji. Dodano cztery ubytki
centrów klatki 250 oraz kontrolę całego pola. Parametrów nie dostrajano.
Dane i maski referencji pozostały niezmienione; nie oceniano obszarów poza nimi.

Mediana zachowania znanego materiału: fixed45 97,71%, fixed65 99,51%, bright3
45,00%, texture3 23,87%. Ubytek do 25% centrów w klatce 250 obniża fixed45
z 97,63% do 26,30%; przy trzech centrach auto65 obejmuje całe pole. Wyniki
uzasadniają ograniczenia tych kandydatów, nie wybór gotowej metody.

Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/coverage-partial-trial/index.html`.
Obok `results.json`, CSV klatek/regionów, 22 NPZ masek, zestawienia PNG i raporty
inspekcji. Polecenie odtworzenia, parametry i hashe są w raporcie i README prototypu.

Wykonano kontrolę hashy wejścia, geometrii raw/PNG, wyłączenia kreski/paddingu,
zgodności metryk 238 masek i 10 masek klatki 268 z pierwszą próbą. Metody
obrazowe są niezmienne przy ubytkach centrów. QtWebEngine: 22 przypadki,
15 kroków scenariuszy, wybory i nakładki, gamma, nawigacja, reset, brak wyniku;
bez błędów JS. Obejrzano zrzut i zestawienia wszystkich klatek dla dwóch metod.
Generator: 28,49 s / 590,40 MiB RSS, HTML 3 839 863 B. Sprawdzono linki dokumentacji
oraz `git diff --check`. Nie uruchamiano testów ani nie zmieniano kodu aplikacji.

Próba wykonana i omówiona; [ticket 10](issues/10-coverage-and-scale.md) ma status
`resolved` jako zakończony eksperyment, bez zatwierdzenia metody pomiarowej.
Nie czeka na krok 11. Odbiór metod nadal obejmuje nierozstrzygnięte granice,
nadmiar maski i warunki odmowy; zmiana statusu nie zalicza tych sprawdzeń.
Brak nowych referencji nie blokował
próby; nie poproszono o dodatkowe dane. Pełna ocena nadmiaru maski poza ramkami
pozostaje niedostępna. Można kontynuować lokalne porównania na obecnych danych.
Nie zgłoszono nowych zmian wspólnych; wcześniejsze potrzeby integracyjne
pozostają w zachowanym przekazaniu poniżej.

Przy zmianie statusu sprawdzono spójność odwołań i `git diff --check`.
Nie uruchamiano ponownie eksperymentów ani testów aplikacji. Krok 11 nie został
rozpoczęty tą zmianą dokumentacji.

---

## Poprzednie przekazanie — wstępna próba pokrycia i skali

Data: 2026-10-21. Gałąź dokumentacji: `domains/coverage-and-scale`, baza `c80d9e9`.
Worktree: `/tmp/netcat-stmdomains-coverage`; docelowo `domains/start`.
Claim: `fd0c119`; commit niniejszego przekazania podany w wiadomości końcowej.
Źródła prototypu: `prototype/stmdomains-coverage`, commit `3f2dee6`.
**Nie scalać gałęzi prototypu do aplikacji.**

[Pokrycie i skala](issues/10-coverage-and-scale.md): wykonano i omówiono
porównanie wstępne; pytanie nadal `claimed`. Użytkownik potwierdził dalszą próbę
z referencjami. Następnie dostarczył częściowe oznaczenia domen opisane
w uzupełnieniu poniżej i zaakceptował ich użycie na najbliższe próby.
Nie zwalidowano metody; pełny odbiór nadal wymaga protokołu jakości.

[Raport](coverage-and-scale-pilot.md): 25 obrazów, 10 wariantów, oddzielny wpływ
skali, braków oznaczeń, kontrastu i wygładzania. Na kontrolach wykazano błędne
scalenia/podziały i fałszywy materiał na samym szumie. Wspólna skala usuwa
rozrost maski z trzech centrów, lecz nie dostarcza pełnej granicy warstwy.
Metryki TTMAPP bez referencji pozostają niedostępne.

Doprecyzowanie użytkownika: pokrycie obejmuje materiał na dowolnym widocznym
poziomie warstwy. Ciemne miejsca bez rozpoznawalnych molekuł i innych
wystarczających przesłanek pozostają nierozstrzygnięte, nie są automatycznie
podłożem ani potwierdzoną niższą warstwą. Zaktualizowano słownik, kontekst
referencji oraz zastosowanie dotychczasowych reguł statystyk częściowych.
Nie zmieniono liczebności oznaczeń ani ich mianownika.

Artefakt lokalny:
`/home/rlew/projekty/NEtCAT-domains/.scratch/coverage-and-scale/index.html`.
Obok są metryki, inspekcja, porównanie powtarzalności i podglądy ośmiu klatek
bez nakładek w `reference-candidates/`. To kandydaci do referencji, nie ich maski.
Odtworzenie jednym poleceniem opisuje raport i README na gałęzi prototypu.

Wykonano: kontrolę hashy wejścia i liczby centrów, powtórzenie 230 pierwotnych
wariantów z identycznymi maskami/metrykami, inspekcję scenariuszy HTML,
przełączników, gamma i braków wyniku w QtWebEngine oraz oglądanie zrzutów.
Ostateczny generator: 28,91 s, 589,81 MiB RSS (pełny odczyt i generowanie),
HTML 2,38 MiB. Kontrola lokalnych linków, statusów, grafu i `git diff --check`
przed commitem. Nie dodawano testów prototypu ani nie uruchamiano testów
produkcyjnej aplikacji; kod produkcyjny pozostaje bez zmian.

Następny krok badawczy: wykorzystać obecne oznaczone wnętrza do lokalnego
porównania. Dodatkowe referencje pozyskiwać dopiero po wykazaniu konkretnej
potrzeby; nie są warunkiem rozpoczęcia tej próby. Nie utworzono duplikatu ticketu.
Budowa szkieletu z pierwszej mapy może przebiegać niezależnie. Do integratora nie
zgłoszono nowych zmian wspólnych; wcześniejsze potrzeby środowiska i importu
pozostają poniżej.

## Uzupełnienie: częściowe referencje domen

Użytkownik dostarczył `data/ttmapp_frames_250_268_domain_review` i wyjaśnił,
że ramki są przybliżonymi granicami wybranych domen, a podobne skupiska mogą
występować poza nimi. [Audyt i zasady użycia](partial-domain-reference-audit.md)
ograniczają ocenę do zaznaczonych obszarów; reszta nie jest podłożem ani
fałszywą detekcją. Kolory są etykietami referencji, nie wyborem typów sieci.

18 par PNG, brak klatki 255; dla wszystkich zgodność rekonstrukcji z MPP
piksel w piksel. Przygotowano 54 robocze wnętrza regionów, maski raw/PNG,
manifest z hashami i galerię; obejrzano wnętrza oraz źródłowe ramki.
Kod przygotowania: `prototype/stmdomains-coverage`, commit `4e7a757`.
Lokalny HTML: `/home/rlew/projekty/NEtCAT-domains/.scratch/partial-domain-reference/index.html`.
Nie scalać kodu prototypu do aplikacji. Dane i duże artefakty są poza Git.

Nie przeliczono klasyfikatorów ani nie oceniono skuteczności pokrycia na tych
referencjach; nie uruchamiano testów aplikacji. Ramki są przybliżone, margines
wnętrz nie jest skalibrowaną tolerancją. Do pełnej walidacji nadal brakuje
negatywnych przykładów podłoża, niepewności i niezależnej próby. Nie zgłoszono
nowych potrzeb wspólnych. Dokumentacja i stan ticketu zostały uzupełnione.

Uzupełnienie po akceptacji zbioru przez użytkownika: dokumentacja dopuszcza
lokalne próby na tej referencji mimo otwartego pytania 04. Commit bazowy audytu:
`c0cc0f4`; commit tej decyzji podany w wiadomości końcowej. Obecna zmiana
obejmuje tylko dokumentację: sprawdzono lokalne linki i `git diff --check`.
Nie uruchamiano ponownie eksperymentów ani testów aplikacji.

---

## Poprzednie przekazanie — specyfikacja szkieletu gotowa do implementacji

Data: 2026-10-19.
Gałąź: `domains/implementation-handoff`, baza `7378c21`.
Worktree: `/tmp/netcat-stmdomains-implementation-handoff`.
Gałąź docelowa: `domains/start`. Claim: `52b5139`.
Commit rozstrzygnięcia podany w wiadomości końcowej. Przeniesienie dokumentacji
przez fast-forward po kontroli gałęzi, HEAD i czystości worktree.

## Wynik

[Przekazanie do implementacji](issues/09-implementation-handoff.md) ma status
`resolved`. Zakończono [pierwszą mapę decyzji](map.md); nie oznacza to wykonania
aplikacji. Kod produkcyjny nadal zawiera startowe okno PyQt6.

Użytkownik potwierdził dwa pozostałe zachowania: pełną kolejność klatek
podczas play, ze spowolnieniem w razie potrzeby, oraz automatyczny kontrast
każdej klatki. Raw/aligned tej samej klatki używają wspólnej skali jasności.

Przygotowano [trzy zadania wykonawcze](implementation/README.md), wszystkie `todo`:

1. Import MolTrack, lokalny model serii, kodek masek i geometria.
2. Natywny podgląd C, otwieranie, zadania w tle i nawigacja.
3. Automatyczne sprawdzenia, pełny TTMAPP oraz odbiór GUI i raport.

Zadania nie są nowymi pytaniami `wayfinder`. Kolejny krok to
[import, model serii i geometria](implementation/01-import-model.md).
Dopiero wykonanie zadań i potwierdzony odbiór programu otwierają zwykły tok
etapu 2. Wcześniejsze decyzje na bezpośrednie polecenia użytkownika są zachowane.

## Kierunek implementacji

Publiczny czytnik `nanotrack.io.mpp_loader.load_mpp_sequence` za lokalnym
adapterem; własne rekordy zachowujące braki i kodowane maski. Jeden układ
geometrii z całej zapisanej rejestracji, obraz/oznaczenia pojedynczej klatki
przygotowywane razem. Nie kopiować pełnego loadera sesji MolTrack ani jego
modeli wymagających pełnych masek lub domyślnego confidence/jakości.

Mały lokalny widok PyQt6 zamiast dziedziczenia całych widgetów NanoTrack/MolTrack.
Odrębne tło paddingu, jednostki px, scene coordinates zgodne z krawędziami
pikseli i bboxów. Kontrast percentylami 2–98 finite próbek oryginału, gamma
wyłącznie podglądu. Cache masek i wyrównania jest ograniczony; nie budować
całego wyrównanego stosu ani wszystkich masek przy otwarciu.

Lokalny kontroler importu i nawigacji odrzuca spóźnione odpowiedzi workerów,
zachowuje poprzednią serię do zatwierdzenia nowej i nie miesza obrazu/oznaczeń.
Wątki GUI i pracy są oddzielone; pauza nie publikuje dodatkowego kroku.
Przyszła analiza dostanie model serii; nie tworzyć teraz ogólnego systemu metod.

## Wykonane sprawdzenia

- Audyt istniejącego okna, czytników, modeli, kodeków, geometrii, widgetów,
  zależności i testów. Nie zmieniano ich kodu.
- Małe próby importów modułów bez danych w `netcat`. Pełne `session_store`
  załadowało 171 modułów `moltrack.analysis`; lekki czytnik MPP nie ładuje ich.
  To kontrola sprzężeń, nie benchmark przyszłej aplikacji.
- Próba starego ViewerWidget w Qt/offscreen: bez ustawienia row-major obraz
  `(2,4)` dostał wymiary 2×4 zamiast 4×2; osie pozostawały nm bez kalibracji;
  NaN w podglądzie były zastępowane medianą. Uzasadnia to lokalny prosty widok.
- Kontrola lokalnych linków, statusów i grafów zależności, kompletności zadań,
  zgodności zakończonej mapy z jej decyzjami oraz `git diff --check` przed commitem.

Nie uruchamiano ponownie dawnych sześciu testów importu, pełnego TTMAPP ani
nowej aplikacji. Prototyp HTML i wcześniejsze testy nie zastępują odbioru
natywnego programu. Przyszłe sprawdzenia opisuje
[zadanie odbioru](implementation/03-acceptance.md); wszystkie pozostają do wykonania.

## Potrzeby integracyjne i środowisko

Produkcja według tego planu: PyQt6 + NumPy + SciPy. Testy: pytest i pytest-qt.
Lokalne `netcat` ma potrzebne zależności. Nie potrzeba modeli, Torch,
QtWebEngine, pyqtgraph ani skimage w produkcyjnej ścieżce szkieletu.

Do integratora: uzupełnienie `requirements/stm-apps.txt` (obecnie tylko PyQt6)
o NumPy/SciPy i objęcie nowych testów właściwym CI. Root requirements/workflow
nie były zmieniane w tej sesji. Dotychczasowy plik nie jest jeszcze podstawą
do deklaracji kompletnej nowej instalacji programu.

Wydzielenie wspólnego lekkiego kodeka masek lub renderera pojedynczej klatki
może być późniejszym refaktorem integracyjnym; lokalna implementacja zgodnego
podzbioru nie musi na to czekać. Stare problemy importu opisane niżej nie są
rozwiązywane przez bezwarunkowe przejęcie pełnego loadera MolTrack.

## Zachowany kontekst poprzednich prac

[Kontrakt importu](issues/01-import-and-geometry.md),
[audyt geometrii](import-geometry-audit.md) i
[definicje wysp/typów/domen](issues/02-order-types-and-domains.md) pozostają aktualne.
Przekazania wcześniejszych zadań są w commitach `3c7c680`, `af7888e`, `ed5da11` i `1a81bc7`.
[Definicje statystyk](issues/06-frame-statistics.md) pozostają aktualne;
ręczne rozstrzyganie konfliktów domen należy do późniejszego UI analizy,
bez rozszerzania podglądu pierwszego etapu.

[Pilotaż metod](method-comparison-pilot.md) nie wybrał algorytmu do aplikacji.
Jego źródła pozostają na `prototype/stmdomains-method-comparison`, commit
`f9ea1d602a8c2bcd1bc5eb410765706d2ae43fca`; nie scalać tej gałęzi do aplikacji.
Lokalny HTML: `/home/rlew/projekty/NEtCAT-domains/.scratch/method-comparison/pilot.html`.
Wynik inspekcji prototypu oraz sześciu dawnych testów importu dotyczy poprzednich
zadań; nie przedstawiamy ich jako sprawdzeń obecnej zmiany.

Zgłoszenia integracyjne pozostają aktualne: dobór czasów do wybranych klatek
MolTrack, walidacja duplikatów i shape masek, zachowanie przy zmienionym mtime
oraz koszt pełnej materializacji masek. Adapter STM Domains może powstać bez
czekania na wspólne poprawki. Dawne zgłoszenie odwracania STP/S94 w NanoTrack
jest poza zakresem importera z jednym MPP. Zmiany tych wspólnych modułów nie blokują lokalnego importera.
Aktualne wymaganie dotyczące środowiska opisano powyżej.

Wybór podglądu jest zakończony: [jeden obraz i pasek miniatur](issues/07-browsing-and-comparison.md),
commit dokumentacji `92e589d`. Źródła jego prototypu pozostają na
`prototype/stmdomains-browsing`, commit `cb51fbf04802620637dd7d10acc19863717de083`;
nie scalać do aplikacji. Lokalny HTML:
`/home/rlew/projekty/NEtCAT-domains/.scratch/browsing-prototype/index.html`.

[Kontrakt zapisu i eksportu](issues/08-save-and-export.md) rozstrzygnięto
w `7378c21`: samowystarczalny `.stmdomains`, opcjonalnie jeden wynik,
odtwarzanie bez przeliczania oraz CSV/PNG. Zapis pozostaje w etapie 2,
także wariant pracy przed analizą. Nie powstał jeszcze serializer.
