# Ocena uwag do propozycji AE/rVAE

2026-11-10. Gałąź `ml_domain`, oceniany stan repozytorium `0e71fb1`.
Źródło uwag: przekazany przez użytkownika plik `Pasted text.txt`, zaczynający
się od „Oceniam ten plan pozytywnie”, załącznik
`f3913d53-025c-4799-bc48-00de77344e4b`.
Przedmiot: [propozycja E1–E7](ml-ae-rvae-experiments.md), nie nowe wyniki.
Poniższe zalecenia nie stanowią jeszcze wyboru ticketów ani zmiany definicji
domen. Pierwotny plan zachowano, żeby oddzielić ocenę od jego aktualizacji.

## Wniosek

Ocena jest w większości trafna. Najważniejsze poprawki to pełny układ
idealnych wejść 2×2, dopuszczenie małego uczonego odczytu mimo słabych
odległości, wcześniejsza referencja rzeczywistych granic i zamrożenie
sprawdzonego dekodera przy dołączaniu enkodera. Te zmiany poprawiają
możliwość rozpoznania przyczyny niepowodzenia bez dużego treningu.

Nie ma podstaw, by z tej oceny wywnioskować skuteczność AE/rVAE na STM.
Nie wszystkie wskazane braki są nowe: testy znanych obrotów, rozróżnienie
przesunięcia całego obrazu i granicy niedopasowania oraz część zasad
walidacji już istnieją. Twierdzenie o wcześniejszej akceptacji domen
dwurzędowych rozdzielonych tarasem nie znalazło potwierdzenia w dokumentacji.

| Propozycja | Ocena | Znaczenie dla następnej próby |
| --- | --- | --- |
| E0: przykłady domen i niepewności | Przyjąć jako krótki audyt celu | Oddzielić cienki fragment sieci, niezależne rzędy i brak danych; nie zmieniać etykiet starych kontroli po wyniku. |
| Idealne relacje × idealna maska, 2×2 | Przyjąć | Błędna maska może ukryć korzyść z poprawnych relacji i odwrotnie. |
| Mała referencja realnych granic wcześniej | Przyjąć przed rozstrzygającą oceną | E1 może ruszyć bez nowych etykiet; mocna ocena granic i uczony odczyt wymagają lepszej referencji. |
| Prosty uczony odczyt mimo słabych dystansów | Przyjąć z walidacją grupową | Słaba odległość nie dowodzi braku informacji w cechach. |
| E5 przed E4 | Preferować dla celu wykrywania domen | Lokalność, centrowanie i skala są bliższe temu celowi; E4 może być osobną krótką diagnostyką rVAE. |
| Zamrożenie skutecznego dekodera | Przyjąć | Pierwszy test enkodera zachowuje już sprawdzoną część modelu. |
| Bazy geometryczne, FFT i skala fizyczna | Przyjąć w ograniczonym zakresie | Sprawdzić, czy cechy AE/rVAE dodają coś ponad geometrię i fotometrię. |

## 1. E0: poprawne pytanie, niepotwierdzony precedens

Zapisana [decyzja o domenach](issues/02-order-types-and-domains.md) wymaga
spójnego obszaru uporządkowania, ale pozostawia minimalną wiarygodność do
prób. Brak dostatecznych danych nie jest dowodem nieporządku. Nie znaleziono
zapisu akceptującego konkretnie „dwie uporządkowane linie rozdzielone tarasem”.
To ograniczenie dostępnej dokumentacji, nie dowód, że użytkownik nigdy tego
nie powiedział. Sama krawędź kontrastu nie potwierdza uskoku tarasu;
[obecne bariery obrazu](implementation/interactive-v04/advanced-settings.md)
nie są uniwersalnym detektorem tarasów.

Kontrola [independent_rows](../../stmdomains/experiments/training/controls.py)
ma regularny odstęp rzędów i osobną losową fazę wzdłuż każdego z nich.
W protokole 21/22 to negatyw dla wspólnej sieci 2D. Nie jest równoważna
dowolnemu wąskiemu fragmentowi prawdziwej domeny. Jednocześnie
[wcześniejsza diagnostyka](fit-quality-diagnosis.md) wykazała, że dwa rzędy
o dowolnej wzajemnej fazie można dopasować do skośnej sieci: taki lokalny
fit nie dowodzi powtarzalności w drugim kierunku.

E0 powinno więc pokazać trzy osobne przypadki: wąski fragment znanej sieci,
wiele niespójnych rzędów oraz dwa rzędy, których lokalnie nie da się
jednoznacznie sklasyfikować. Ostatni może wymagać statusu niepewności.
Dotychczasowe etykiety kontroli zachować; ewentualnie rozszerzony cel
opisać jako nową wersję benchmarku i pokazać wyniki obu wersji.

Rozróżnienie globalnego przesunięcia i rzeczywistej granicy niedopasowania
jest już w [słowniku](GLOSSARY.md) oraz decyzji 02. Generator przesuwa tylko
połowę obrazu w `phase_boundary`; `crop` zachowuje tożsamości domen.
Wystarczy odsyłacz w protokole. Po przesunięciu obrazu maska powinna przesunąć
się razem z nim; porównujemy członkostwo na wspólnym obszarze, nie identyczne
współrzędne pikseli.

## 2. E1: pełny układ idealnych wejść i ograniczenia grafu

Zamiast dwóch osobnych podmian zalecany jest układ:

| Relacje na grafie | Maska dopuszczenia z programu | Maska prawdziwych domen generatora |
| --- | --- | --- |
| Z programu | Punkt odniesienia | Test ograniczenia przez maskę |
| Z prawdy generatora | Test ograniczenia przez relacje | Wspólny test dalszej mechaniki |

To diagnostyka na syntetykach. Zachować ten sam graf, dostępność danych
i pełne wsparcie wycinków. Maska oznacza przynależność do prawdziwych domen,
nie samo istnienie materiału. Tło nie jest jedną wspólną domeną.

Porażka idealnych relacji przy błędnej masce nie obciąża jednoznacznie
podziału grafu. Nawet oba idealne wejścia nie gwarantują wyniku, jeśli
prawdziwa domena nie jest spójna w dostępnym grafie albo usuwa ją minimum
komponentu. [Kod podziału](../../stmdomains/experiments/training/partition.py)
przelicza komponenty po odmowach i domyślnie wymaga czterech węzłów.
Ocena musi oddzielać wynik przed i po tym minimum; naruszenie jawnego
ograniczenia nie oznacza automatycznie błędu implementacji.

Idealne relacje trzeba zakodować zgodnie z solverem. FH operuje odległością
i progiem zależnym od `k`; MWS znakiem i siłą relacji. Binarne odległości
0/1 przy FH `k=4` nie gwarantują zakazu scalania różnych domen. Ten kontrakt
należy sprawdzić na małym grafie o znanym wyniku przed eksperymentem.
To oddzielna kontrola od ośmiu kombinacji bramek opisanych w E1.

## 3. E2 i mały E7: odległość nie jest pełnym testem informacji

Zdanie w pierwotnym E2, że brak sygnału w relacjach uzasadnia zmianę
reprezentacji, wymaga osłabienia. Wynik dotyczy sprawdzonego sposobu
porównania cech. Prosty klasyfikator może wykorzystać ich nierówną wagę
lub kombinację, której zwykła odległość nie ujawnia. Niezależnie uczone
proste odczyty są znaną diagnostyką reprezentacji:
[Alain i Bengio, linear classifier probes](https://arxiv.org/abs/1610.01644).

Zalecany jeden ograniczony kontrast: ta sama regularizowana rodzina
klasyfikatora relacji dla geometrii, geometrii+AE i geometrii+rVAE, przy
zamrożonych enkoderach, tym samym grafie i budżecie doboru parametrów.
Zachować bazę jasności/kontrastu: korzyść AE może pochodzić z fotometrii.

Dobry wynik poza grupami treningowymi uzasadnia rozwój odczytu, ale jeszcze
nie gwarantuje poprawnego podziału całego obrazu. Słabe dystanse i słaby
mały klasyfikator oznaczają brak użytecznego odczytu w sprawdzonym zakresie,
nie dowód matematycznej nieobecności informacji. To praktyczny argument
za zmianą reprezentacji zamiast nieograniczonego strojenia klasyfikatorów.

## 4. Realna referencja i jednostka oceny

[Synteza dotychczasowych prób](research-after-training-pilot.md) opisuje
28 par między różnymi referencjami, ale tylko **jedną lokalną krawędź**
między nimi w transferze. To nie 28 niezależnych granic. Mały zestaw
przejrzanych wnętrz, styków i niepewnych obszarów powinien poprzedzić
mocne wnioski z E2/E5 oraz uczenie relacji; nie musi blokować E1.

Nie potrzeba od razu pełnych masek całej serii. Potrzebne są rzeczywiste
przykłady „ta sama / inna domena” przy sąsiedztwach oraz kontrola jakości
tych oznaczeń. Brak oznaczenia nie oznacza negatywu. Odcinki granic nie
uprawniają do raportowania globalnego IoU. Liczbę ROI ustalić po inwentaryzacji
rodzajów granic; liczba wygenerowanych par nie zastępuje różnorodności pól.

Rozdzielać role danych **przed tworzeniem par**. Wspólne molekuły,
nakładające się wycinki i kolejne widoki tego samego miejsca nie mogą
swobodnie trafiać do treningu i walidacji. Walidacja grupowa zachowuje całe
zależne grupy poza treningiem:
[dokumentacja scikit-learn](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data).
Na jednej akwizycji można prowadzić eksplorację z blokami przestrzennymi
i buforem dla wycinków, ale nie wykazać transferu na inne materiały.
Znane trudne klatki pozostają materiałem rozwojowym również po anotacji.

Wspólny procent pokrycia nie zapewnia wspólnej trudności ocenianych par.
Raportować jakość i odmowy na całym ocenialnym zbiorze, wynik na wspólnej
części, liczebności oraz błędne scalenia osobno. Progów nie dobierać do
referencji testowej, aby uzyskać atrakcyjne pokrycie.

## 5. E5, E4 i fizyczne interpretacje

Przy celu wykrywania domen preferuję E5 przed pełnym E4: lokalne cechy,
centrowanie i łączenie skal bez nowego treningu bezpośrednio badają relacje
przy granicach. [Praca Valleti i in.](https://arxiv.org/abs/2101.06892)
uzasadnia wycinki centrowane na jednostkach atomowych w swoim zadaniu STEM.
Jest inspiracją do kontroli centrowania, nie dowodem skuteczności na STM.
Porównanie całej siatki i grafu molekuł już wykonano w 21; nowa próba
powinna izolować centrowanie przy zachowanym grafie, zgodnie z E5.

E4 pozostaje wartościową, osobną diagnostyką zdolności rVAE do odtworzenia
16 wejść. Gdy decoder-only zadziała, zachować jego wagi i **najpierw je
zamrozić**, ucząc tylko enkoder przez rekonstrukcję przy stałej pozie.
Późniejsze wspólne dostrajanie byłoby oddzielnym kontrastem. Porażka tego
testu wskazuje trudność wyznaczenia kodu dla danego dekodera i budżetu,
nie dowodzi sama braku informacji wejściowej ani zbyt małego enkodera.

Testy znanych obrotów już są w [raporcie 21a](rvae-decoder-kl-trial.md):
różnice 27° i 8° oraz obroty ±90° bez interpolacji nie potwierdziły
wiarygodnego kąta. Wrócić do nich jako bazowych wyników; nowe obliczenia
uzasadnia zmiana modelu lub nowy kontrast. Nie zastępować automatycznie
`sin θ, cos θ` przez `sin 2θ, cos 2θ`: trzeba ustalić, czy chodzi o oś
rzędów, orientację molekuły czy pełną sieć i jej rzeczywistą symetrię.

W bazach fizycznych wystarczą na początek istniejące miary kierunku,
rozstawu i pewności okresowości. Zapisywać nm/piksel, rozmiar wycinka
w jednostkach fizycznych i liczbę widocznych okresów; brak skali oznaczać
jawnie. Nie jest to powód do otwierania osobnego dużego projektu geometrii.

## Zalecana kolejność i zakres tej oceny

1. Krótkie E0: przypadki celu, niepewność i przegląd dostępnej referencji.
2. E1: odmowy oraz pełny układ idealnych wejść; możliwe na obecnych danych.
3. E2/E3: odczyt cech i wpływ warunków obrazowania; równolegle małe ROI.
4. E5: lokalność, skala i izolowane centrowanie.
5. Mały E7: prosty uczony odczyt, dopuszczony również po słabych dystansach,
   gdy jest odpowiednia referencja i rozdział danych.
6. Warunkowo E4 i dopiero uzasadniony wynikami kontrast treningowy E6.
   E4 można wcześniej wydzielić, jeśli priorytetem jest diagnoza samego rVAE.

Wynik każdej próby nadal pokazywać na obrazie z rzeczywistymi molekułami,
domenami i nieprzypisanymi miejscami. Więcej pokolorowanych punktów samo
w sobie nie jest poprawą. Przy obecnych danych celem jest rozpoznanie
ograniczenia i wybór następnego kroku, nie deklaracja ogólnej skuteczności.

Ocena wykorzystuje `scientific-critical-thinking` i `experimental-design`:
konkurencyjne wyjaśnienia, kontrolę współdziałających czynników, zależność
próbek i ograniczenia wnioskowania. Wykonano dwa niezależne przeglądy
semantyki domen oraz projektu eksperymentów. Sprawdzono wskazane fragmenty
kodu, raportów i źródła pierwotne. Bez nowych obliczeń naukowych, treningu,
testów aplikacji lub GUI. Nie zmieniono kodu, planu E1–E7 ani ticketów.

Źródło wykorzystanych procedur: Kassis, T., Agarwal, V., He, Y., Patel, D.,
& Brueckner, A. M. (2026), *Scientific Agent Skills: A Library of Procedural
Knowledge for Research Agents*,
[arXiv:2609.00065](https://doi.org/10.48550/arXiv.2609.00065).
Metadane sprawdzono 2026-11-10. To uznanie pochodzenia procedur, nie dowód
trafności niniejszej oceny ani skuteczności modeli.
