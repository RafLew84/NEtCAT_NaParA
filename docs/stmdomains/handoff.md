# STM Domains — zadania przygotowania i porównania ML

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
