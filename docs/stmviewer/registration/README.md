# Plan rozwoju rejestracji trudnych filmów STM

Data: 2026-10-28; rozszerzenia ręczne: REG-01a 2026-10-30, REG-02a 2026-10-31.
Rozszerzenie o graf dopasowań i nowe modele: 2026-10-31, na zlecenie użytkownika.
Gałąź: `viewer/registration-difficult-movies`.
Baza rozpoznania: `c85aecb`; przegląd metod: `81ff1a0`.

**REG-10 — 2026-11-02: done.** EfficientLoFTR wdrożono dla par,
łańcucha i grafu; [instrukcja](efficient-loftr-manual.md),
[wyniki](efficient-loftr-results.md), [przeglądy](reviews/REG-10.md).
Po [zaakceptowanej poprawce obsługi niepewnych wyników](efficient-loftr-weak-results.md)
graf LS obu filmów jest kompletny, a MOVIE_8 także w łańcuchu.
Użytkownik potwierdził „testy manualne ok” po poprawce.
**REG-11 — 2026-11-02: done.** RoMa v2 działa dla pary, filmu
oraz grafu przez [osobne środowisko](roma-environment.md).
[Instrukcja](roma-manual.md), [wyniki i ograniczenia](roma-results.md),
[przeglądy](reviews/REG-11.md). 761 testów Viewera oraz osobne rzeczywiste
próby CPU/CUDA i Qt offscreen zaliczone. Użytkownik potwierdził
„testy manualne ok”; odbiór REG-11 zamknięty. Bieżący stan REG-12 poniżej.

**REG-12 — 2026-11-02: done.** MatchAnything-ELoFTR działa
w parze, filmie i grafie, z zapisem sesji oraz MPP/AVI.
[Instrukcja ręczna](matchanything-manual.md), [wyniki](matchanything-results.md),
[przeglądy](reviews/REG-12.md). Pełne oba filmy mają łańcuch i LS;
wyniki są przeważnie niepewne. Użytkownik potwierdził „testy manualne ok”;
odbiór REG-12 zamknięty, ograniczenia modelu pozostają zapisane.

Status: REG-01, REG-01a, REG-02, REG-02a, REG-04, REG-05, REG-07, REG-08a, REG-08b, REG-08c, REG-08e, REG-10, REG-11 i REG-12 `done`. Użytkownik potwierdził odbiór REG-02
2026-10-31 i zgłosił brak istotnej poprawy względem Phase na MOVIE_4.
Deep Matcher ocenia najlepiej w obejrzanych pierwszych 100 klatkach.
[Instrukcja REG-02](unnormalized-correlation-manual.md), [wyniki](reviews/REG-02.md).
[REG-02a: ręczne korekty filmu](issues/02a-manual-movie-corrections.md) zamknięto
jako `done` po potwierdzeniu użytkownika „testy manualne ok” 2026-10-31.
[REG-04: Deep Matcher + doprecyzowanie ECC](issues/04-multiscale-translation.md)
ma status `done`: użytkownik potwierdził „testy manualne 04 ok” 2026-10-31.
[Instrukcja REG-04](deep-ecc-manual.md), [karta](reviews/REG-04.md).
[REG-05: zgodność lokalnych fragmentów](issues/05-local-consensus.md) zamknięto
po potwierdzeniu „testy manualne 05 ok” 2026-10-31. REG-06 odłożono na życzenie
użytkownika. REG-07 ma status `done`: użytkownik potwierdził „testy manualne ok”
2026-11-01. Zapis i odczyt sesji zastępują odrzuconą bibliotekę pełnych prób A/B.
[Instrukcja REG-02a](manual-movie-corrections-manual.md), [sprawdzenia](reviews/REG-02a.md).
Dalsze próby MOVIE_4
obejmują źródłowe klatki 3–364, zgodnie z [protokołem](manual-protocol.md).
[Instrukcja manualna](manual-alignment-manual.md), [karta sprawdzeń](reviews/REG-01a.md).
Użytkownik wybrał układ C; jest wdrożony z opisowymi kartami wyników i ręcznym
sterowaniem pod obrazem. [Aktualny przegląd i próby](reviews/REG-01a-layout-c.md).
Wcześniejsze A/B w opisach mapy odpowiadają wynikowi zachowanemu/bieżącemu.
Zlecenie użytkownika: małe tickety, ręczna ocena wpływu i jakości po każdym.

**Zmiana zakresu — 2026-10-31:** na życzenie użytkownika usunięto implementację
i etap REG-03 (rejestracja z ręcznymi maskami). Usunięto też wymagania takich
oznaczeń w dalszych etapach. Pozostałe tickety zachowują numery; REG-04
następuje bezpośrednio po odebranym REG-02a.

**Doprecyzowanie REG-04 — 2026-10-31:** użytkownik wybrał eksperyment
Deep Matcher → ECC dla tej samej sąsiedniej pary. ECC dostaje XY Deep jako
start; porównujemy dokładny wynik początkowy z doprecyzowanym. Ten zakres
zastępuje ogólną wieloskalowość, bez zewnętrznej piramidy i bez automatycznego
uznawania wyniku ECC za lepszy. [Instrukcja odbioru](deep-ecc-manual.md)
i [wyniki prób](deep-ecc-results.md) rozdzielają sprawdzenie funkcji od oceny
jakości przez użytkownika.

**Rozszerzenie po przeglądzie — 2026-10-31:** pierwotnie przyjęto kierunek
REG-05 → ocena REG-06 i zapis pracy REG-07 → diagnostyka REG-08 → graf
REG-08a/08b/08c → osobne próby EfficientLoFTR, RoMa v2 i MatchAnything
REG-10/11/12. [Przegląd i źródła](../registration-multiframe-research.md)
uzasadniają te próby, ale nie potwierdzają ich skuteczności na naszych filmach.
W tej wersji planu REG-08 miał być etapem diagnostycznym; został później
wycofany decyzją z 2026-11-01 opisaną poniżej. Dalsze odniesienia
REG-08d i diagnostyka tearingu REG-09 pozostają warunkowe. Rozszerzenie planu
nie jest implementacją ani odbiorem REG-04.

**Odłożenie REG-06 — 2026-10-31:** użytkownik zdecydował „na razie pominiemy 06”.
REG-06 pozostaje w planie ze statusem `planned`, poza bieżącą kolejnością.
Aktualna ścieżka prowadzi z REG-05 bezpośrednio do REG-07, następnie REG-08a
i dalszych etapów. REG-07 oraz kolejne tickety nie przejmują implementacji
kontroli REG-06. Ocena wizualna, poparcie estymatora i diagnostyka spójności
pozostają dostępne zgodnie ze swoimi zakresami; nie nazywamy ich niezależną
walidacją. Wznowienie REG-06 wymaga osobnego zlecenia.

**Zmiana REG-07 — 2026-11-01:** na zlecenie użytkownika usunięto bibliotekę
pełnych prób A/B. REG-07 zapisuje i otwiera jedną sesję `.stmsession`, z obrazami
original i gotowym aligned, zastosowanymi korektami i ustawieniami widoku.
Plik można przenieść bez źródeł i modeli. Porównanie pojedynczej pary pozostaje.
Podgląd kandydata grafu i rozszerzenie zapisu relacji dostarczyły REG-08a/08b.

**Usunięcie REG-08 — 2026-11-01:** użytkownik zrezygnował z osobnej
analizy spójności trójek. Usunięto ticket i jego blokadę; po odebranym REG-07
następuje bezpośrednio REG-08a. Numeracja pozostałych etapów pozostaje.
Spójność relacji będzie oceniana w ramach rozwiązania grafu i jego reszt;
nie dodajemy osobnego panelu ani odbioru diagnostyki trójek. Głównym wynikiem
REG-08a jest podgląd filmu z położeniami wyznaczonymi z wielu dopasowań.

**Rozszerzenie metod — 2026-11-02:** użytkownik zlecił osobny
[REG-08e](issues/08e-multiframe-methods.md): wybór wszystkich istniejących
metod dopasowania par w tym samym oknie wieloklatkowym, z LS/Huberem,
sesją i zastosowaniem do filmu. Status `done`; użytkownik potwierdził
„testy manualne ok” 2026-11-02, po implementacji, testach i przeglądach.
[Instrukcja i sesje](multiframe-methods-manual.md), [karta wykonania](reviews/REG-08e.md).
REG-08e pozostaje po REG-08c, przed próbami nowych modeli.
To osobny zakres od REG-08d, którego implementację wycofano na życzenie
użytkownika commitem `c8e9141` jako nieintuicyjną. Nie przywracamy jej w REG-08e.

## Cel i zakres

Poprawić dopasowanie struktur próbki w MOVIE_4 i MOVIE_8 mimo zakłóceń linii
i tearingu. Pierwsza część nadal wyznacza jedno XY dla całej klatki.
Dowolny kierunek i zmiany kierunku dryfu są dozwolone.
Nie utożsamiamy mniejszego aligned ani gładszej trajektorii z lepszym wynikiem.

Podstawa: [rozpoznanie danych](../registration-difficult-movies.md),
[przegląd metod i źródła](../registration-improvement-options.md).
Nowe zlecenie rozpoczyna etap rozwoju metod odłożony w
[mapie pierwszej wersji](../map.md). Nie zmienia historycznych odbiorów 01–21.
Zachowujemy dotychczasowe identyfikatory ticketów, w tym **REG-01a i REG-02a**,
aby uniknąć kolizji i zmian numerów istniejących zadań. Bieżąca ścieżka obejmuje
czternaście etapów podstawowych; REG-06 jest odłożony, REG-08d odłożono
po wycofaniu implementacji, a REG-09 odłożono na życzenie użytkownika 2026-11-02. REG-08e rozszerza
wybór istniejących metod w grafie REG-08a–08c; REG-09 zachowuje swój zakres.

## Kolejność i wynik każdego ticketu

| Ticket | Efekt widoczny w aplikacji | Blocked by |
| --- | --- | --- |
| [REG-01: Porównanie par klatek](issues/01-pair-comparison.md) | Nakładka i przełączanie obrazów przed/po dopasowaniu; porównanie dwóch prób A/B przy jednakowym widoku. | Brak |
| [REG-01a: Ręczne dopasowanie pary](issues/01a-manual-alignment.md) | Ruch klatki dopasowywanej ±1 px w X/Y, nakładka/przełączanie obrazów, start z zera lub korekta próby, zachowanie ręcznego wyniku jako B. | REG-01 |
| [REG-02: Korelacja bez normalizacji](issues/02-unnormalized-correlation.md) | Osobny wariant dostępny dla pary i całej serii, z porównaniem do dotychczasowego Phase. | REG-01a |
| [REG-02a: Ręczne korekty filmu](issues/02a-manual-movie-corrections.md) | Jawne zastosowanie ręcznego XY pary do całego aligned, przeliczenie dalszych klatek, cofnięcie korekty pary i eksport poprawionego MPP/AVI. | REG-02 |
| [REG-04: Deep Matcher + doprecyzowanie ECC](issues/04-multiscale-translation.md) | Początkowe XY z Deep Matcher, doprecyzowanie ECC i porównanie dokładnego startu z wynikiem; wpływ oceniany manualnie. | REG-02a |
| [REG-05: Zgodność lokalnych fragmentów](issues/05-local-consensus.md) | Przestrzenne poparcie XY z różnych części obrazu i konkurujące grupy; porównanie z bazowym Deep, bez obowiązkowego ECC. | REG-04 |
| [REG-06: Niezależna kontrola dopasowania](issues/06-independent-validation.md) | **Odłożony** — zakres zachowany do ewentualnego powrotu. | REG-05 + osobne zlecenie wznowienia |
| [REG-07: Zapis i odczyt sesji](issues/07-session-save-load.md) | Jeden przenośny plik z serią, aktywnym aligned, ręcznymi korektami i widokiem; wznowienie pracy bez rejestracji. | REG-05 |
| [REG-08a: Graf z oknem 3/5 klatek](issues/08a-window-graph.md) | Osobna pełna próba: obecny Deep, wspólne XY przez LS, porównanie z łańcuchem i zapis relacji. | REG-07 |
| [REG-08b: Odporny graf](issues/08b-robust-graph.md) | LS kontra Huber/IRLS na dokładnie tych samych pomiarach; widoczny wpływ odstających relacji. | REG-08a |
| [REG-08c: Zastosowanie grafu do filmu](issues/08c-graph-movie-application.md) | Jawna podmiana aligned, ręczne korekty, MPP/AVI i odtworzenie sesji z zastosowanym grafem. | REG-08b |
| [REG-08e: Metody w dopasowaniu wieloklatkowym](issues/08e-multiframe-methods.md) | Wybór istniejącego algorytmu par (w tym Optical Flow, Phase i ECC), LS/Huber oraz ten sam podgląd, sesja i zastosowanie. | REG-08c |
| [REG-10: EfficientLoFTR](issues/10-efficient-loftr.md) | Nowy model dla par, łańcucha i grafu; porównanie z obecnym Deep przy stałej reszcie obliczeń. | REG-08c |
| [REG-11: RoMa v2](issues/11-roma-v2.md) | Gęste korespondencje jako źródło jednej translacji XY; osobna ocena jakości i zasobów. | REG-10 |
| [REG-12: MatchAnything-ELoFTR](issues/12-matchanything.md) | Kontrola wpływu treningu: porównanie z EfficientLoFTR przy tym samym konsensusie i grafie. | REG-11 |
| [REG-08d: Dalsze klatki odniesienia](issues/08d-long-range-references.md) | Odłożony po wycofaniu implementacji 2026-11-02; nie jest częścią REG-08e. | REG-08c + decyzja po odbiorze |
| [REG-09: Rozpoznanie deformacji w pasach](issues/09-scanline-diagnostics.md) | Odłożony 2026-11-02: podgląd lokalnych rozbieżności po globalnym XY i podstawa decyzji o korekcji tearingu. | REG-07 + decyzja o wznowieniu |

REG-01 ma status `done` po odbiorze użytkownika 2026-10-29:
[instrukcja próby](pair-comparison-manual.md),
[karta odbioru](reviews/REG-01.md). REG-01a ma status `done` po odbiorze
użytkownika 2026-10-31. REG-02 i REG-02a również odebrano 2026-10-31 (`done`).
REG-04 i REG-05 mają status `done` po odbiorze użytkownika 2026-10-31.
REG-07 ma status `done` po odbiorze 2026-11-01. REG-08a ma status `done` po potwierdzeniu „testy manualne ok” 2026-11-01; REG-08b ma status `done` po potwierdzeniu „testy manualne ok” 2026-11-01; REG-08c ma status `done` po potwierdzeniu „testy manualne ok” 2026-11-01; REG-10 ma status `done` po potwierdzeniu „testy manualne ok” 2026-11-02; REG-11 ma status `done` po potwierdzeniu „testy manualne ok” 2026-11-02.
REG-12 ma status `done` po potwierdzeniu „testy manualne ok” 2026-11-02.
REG-06 ma status
`planned` jako odłożony; nie blokuje bieżącej ścieżki i nie jest odebrany.
REG-08d ma status `planned` jako odłożony po wycofaniu implementacji; REG-09
pozostaje `planned` jako odłożony na życzenie użytkownika 2026-11-02. Nie blokuje REG-10. REG-08e ma status
`done`: użytkownik potwierdził „testy manualne ok” 2026-11-02.
Żadnego z tych etapów nie uruchamiamy automatycznie.

Kolejność podstawowa: REG-01 → REG-01a → REG-02 → REG-02a → REG-04 → REG-05
→ REG-07 → REG-08a → REG-08b → REG-08c → REG-08e → REG-10 → REG-11
→ REG-12. To także kolejność ręcznych odbiorów, nawet gdy część kodu można
technicznie napisać niezależnie. Zależność między REG-10/11/12 porządkuje
eksperymenty; RoMa nie wymaga uruchamiania EfficientLoFTR, a MatchAnything nie
wymaga działającego RoMa. REG-08e poprzedza nowe modele w planie, ale nie
dodaje technicznej blokady REG-10; jego zależność od REG-08c pozostaje.
Wspólną bazą porównań pozostaje obecny Deep.

[REG-07 — zapis i odczyt sesji](issues/07-session-save-load.md) odebrano
2026-11-01. [REG-08a — graf dopasowań z oknem
3 lub 5 klatek](issues/08a-window-graph.md), implementacja `ae32f1d` + `665a1ed`,
również odebrano 2026-11-01: użytkownik potwierdził **„testy manualne ok”**.
[Instrukcja](window-graph-manual.md), [wyniki](window-graph-results.md),
[karta przeglądu](reviews/REG-08a.md).
[REG-08b — odporny graf](issues/08b-robust-graph.md), zlecony 2026-11-01,
ma implementację `2802837` + `417c107` i status **done** po potwierdzeniu
użytkownika „testy manualne ok” 2026-11-01. Dodaje warianty
Hubera na tych samych pomiarach, porównanie LS/Huber i zapis diagnostyki w sesji.
[Instrukcja](robust-graph-manual.md), [wyniki](robust-graph-results.md),
[karta przeglądu](reviews/REG-08b.md). Zastosowanie grafu do aligned i eksportu
realizuje [REG-08c](issues/08c-graph-movie-application.md), implementacja
`140136e` + `73bbc44`, status **done** po potwierdzeniu „testy manualne ok”
2026-11-01. Odebrano jawne zastosowanie LS/Hubera, ręczne korekty, sesję
i przywrócenie poprzednika. Na życzenie użytkownika dodano dialog po obliczeniu
niekompletnego Hubera; nowe powiadomienie nie było objęte wcześniejszą próbą manualną.
[Instrukcja](graph-application-manual.md), [wyniki](graph-application-results.md),
[karta przeglądu](reviews/REG-08c.md). REG-10 później wdrożono na osobne
zlecenie; jego stan i odbiór są opisane na początku tego planu.
[Instrukcja odbioru](session-manual.md), [wyniki](session-results.md),
[przegląd](reviews/REG-07-session.md).
REG-06 jest odłożony i pozostaje niewdrożony.
REG-05 zamknięto jako odebrany wariant eksperymentalny: [instrukcja](local-consensus-manual.md),
[próby rzeczywiste](local-consensus-results.md), [karta](reviews/REG-05.md).
Zachowujemy ograniczenia 2/14 lokalnych wyników i odmowy obu pełnych filmów,
bez deklaracji przewagi nad Deep. W osobnym [porównaniu checkpointów](checkpoint-comparison-results.md)
użytkownik ocenił Outdoor jako znacznie lepszy; pozostaje bazą dalszych prób.

## Stałe kontrakty

- REG-01a ustawia XY jednej pary ręcznie, w pikselach original (+X w prawo,
  +Y w dół). Klatka odniesienia pozostaje nieruchoma. A/B to próby; obrazy
  nazywamy odniesieniem i dopasowywaną klatką. Szkic ręczny jest odrębny od
  zatwierdzonych prób. Zastosowanie tworzy B z jawnym pochodzeniem ręcznym
  i bez automatycznego wskaźnika pewności. Pełny aligned i eksport zachowują
  dotychczasowy wynik po „Zakończ korektę”. REG-02a dodaje osobne
  „Zastosuj do filmu”, które jawnie podmienia aktywny pełny wynik.
- Próby ręczne można rozpocząć od zera lub kopii istniejącego wyniku tej pary.
  Podgląd zawsze powstaje z oryginałów i całkowitego XY. REG-07 zachowuje
  korekty zastosowane do aktywnego filmu wraz z bazą i pochodzeniem;
  diagnostyczne próby par i niezastosowane szkice nie należą do zapisu sesji.
  Ocena wzrokowa operatora
  nie staje się automatycznie niezależną kontrolą z REG-06.

- REG-02a wymaga kompletnej rejestracji bazowej. Ręczne XY zastępuje przesunięcie
  pary; różnica zmienia skumulowane XY tej i kolejnych klatek. Powtórzenie nie
  dubluje zmiany, cofnięcie dotyczy jednej pary. Film powstaje z oryginałów;
  błąd/anulowanie zachowują wcześniejszy wynik i korekty. Po usunięciu klatki
  dotychczasowy aligned/eksport zostaje, lecz dalsza edycja wymaga nowej rejestracji.
  Eksport poprawionego filmu i ręcznego pochodzenia należy już do REG-02a;
  zapis sesji z oryginałami, gotowym aligned i stanem ręcznej edycji należy do REG-07.
- Każda metoda dodawana w REG-02, REG-04 i REG-05 działa od razu na parze i na całej serii,
  przez ten sam estymator. REG-07 nie odkłada podstawowej integracji z GUI.
- Dotychczasowe metody pozostają dostępne. Nowe warianty są jawnie wybierane,
  bez automatycznej zmiany domyślnej metody ani cichego zastępowania po błędzie.
- Pomocnicze filtrowanie służy wyznaczaniu przesunięcia. Aligned powstaje
  z oryginalnych wartości, z jedną interpolacją końcową. Gamma nie wpływa na XY.
- Maska ważności aligned nadal opisuje faktycznie dostępne próbki. Brakujące
  dane i padding nie uczestniczą w ocenie dopasowania jako struktury obrazu.
- Współrzędne fragmentów odnoszą się do original i pochodzenia klatki.
  Wspólny układ porównania zakotwiczamy w źródłowej klatce odniesienia;
  różny padding wyników nie może przesuwać podglądu A/B.
- REG-08e dodaje wybór wszystkich ośmiu istniejących metod par, zachowując
  okna 3/5 oraz obecne LS/Huber. Poprawne XY bez oceny pewności pozostaje
  pomiarem, a lokalna odmowa pozostaje brakiem. Dane różnych metod nie
  współdzielą pamięci pomiarów; CPU nie wymaga wag Deep. Rozszerzenie sesji
  zachowuje odczyt dotychczasowych grafów Deep. Funkcję odebrano ręcznie 2026-11-02.
- Podgląd kandydatów grafu, dostarczony w REG-08a i rozszerzony w REG-08b, przechowuje ustawienia,
  przesunięcia i metadane, renderując oglądane klatki na żądanie. Nie utrzymuje
  dwóch dodatkowych pełnych filmów float64. Ten interfejs dostarczył REG-08a,
  a REG-07 zapewnia zapis bieżącej pracy, bez biblioteki prób.
- Brak wiarygodnego dopasowania nie oznacza (0,0). Wynik liczbowy z małym
  poparciem może być widoczny jako niepewny; brak wyniku lub błąd przerwie
  dotychczasową próbę łańcuchową, zachowując poprzedni kompletny aligned.
  Nowa, jawnie wybrana metoda grafowa ma osobną politykę brakujących relacji
  opisaną poniżej; nie zmienia zachowania dotychczasowych metod.
- Postęp, anulowanie, ochrona poprzedniego wyniku i blokady edycji serii
  podczas obliczeń obowiązują również nowe metody i podgląd par.
- Usuwanie klatek zachowuje gotową geometrię pozostałych. Nowe obliczenie
  korzysta z oryginałów bieżącej serii. Nie dodajemy odwracania kolejności.
- Każdy wariant ma jednoznaczną nazwę i wersję ustawień. MPP/AVI korzystają
  z aktywnego kompletnego aligned, a nie z dowolnego eksperymentu pary A/B.
  Sesja REG-07 jest osobnym plikiem, bez zmiany istniejących formatów MPP/AVI.
  Otwiera całą zapisaną pracę wraz z aktywnym aligned; nie wymaga źródeł ani wag.

## Kontrakty rozszerzenia wieloklatkowego

- Oddzielamy **algorytm pary**, **wyznaczanie wspólnych XY** i **zastosowanie
  wyniku**. Pierwszy graf używa obecnego Deep bez ECC i bez zmiany jego ustawień.
  REG-05 jest osobnym porównaniem przestrzennego poparcia, a nie ukrytą nową
  wersją bazowego Deep. REG-10 ustala wspólną agregację korespondencji nowych
  modeli; REG-11/12 zachowują ją i zmieniają model. Lokalna metoda wycinków
  REG-05 pozostaje osobnym wariantem, bez ukrytego dołączania do nowych matcherów.
- `d_ij` przesuwa oryginalną klatkę j na i, `p_i` przesuwa i do wspólnego
  układu: `p_j - p_i = d_ij`, kotwica `p_0=(0,0)`. Okno obejmuje jedną relację
  każdej pary `0 < |i-j| ≤ k`. Wybór aktualnej klatki podglądu nie zmienia kotwicy.
  Nie uśredniamy surowych wektorów mających różne odniesienia.
- REG-08a używa równych wag ważnych pomiarów i zwykłego LS. REG-08b porównuje
  na tych samych krawędziach blokowy Huber/IRLS: jedna waga dla całej reszty XY.
  Nie dokładamy gładkości trajektorii, stałego kierunku, przyciągania do zera
  ani automatycznie wyższej wagi wyniku ECC. Próg Hubera zapisujemy w pikselach.
- Nieudana estymacja pary to brak krawędzi z przyczyną. Inne połączenia mogą
  ją ominąć. Nieobliczona wskutek anulowania para nie jest odmową estymatora:
  anulowanie przerywa próbę. Awaria zasobów/modelu/solvera również nie udaje
  serii zwykłych braków dopasowania.
- Rozłączny graf nie daje jednego pełnego wyniku; pozostaje diagnostyką.
  Mosty i brak nadmiarowych połączeń są widocznymi ograniczeniami. Mała reszta,
  zgodny cykl lub duża liczba krawędzi nie gwarantują poprawności fizycznej:
  błędy mogą być powiązane, okresowe albo wynikać ze wspólnego zakłócenia.
- REG-08a/08b dodają własny podgląd kandydata grafu i porównanie z bazą oraz
  rozszerzają sesję o relacje, wyniki i diagnozy. REG-07 nie dostarcza biblioteki
  pełnych prób. Samo obliczenie/oglądanie kandydata nie podmienia aktywnego
  aligned. REG-08c dodaje **Zastosuj wynik do filmu** oraz eksport. To celowy
  podział na etapy możliwe do ręcznej oceny; szczegółowy wyjątek eksportowy
  znajduje się w protokole. Pełne klatki próby renderujemy na żądanie.
- REG-08c zamraża globalne XY grafu jako bazę dla REG-02a. Ręczne nadpisanie
  zastępuje różnicę XY sąsiadów tej bazy i przesuwa dalsze klatki, bez ponownego
  uruchamiania solvera. Surowa krawędź modelu, wynik grafu i ręczna korekta są
  osobnymi danymi. Nowa optymalizacja tworzy osobną próbę; przed jej zastosowaniem
  UI pokazuje, które ręczne korekty aktywnego wyniku zostaną zastąpione.
- Rozszerzenia sesji przechowują krawędzie i ich źródła, konfigurację grafu,
  bazowe/końcowe XY oraz ręczne nadpisania. Należą do wprowadzającego je ticketu,
  tak jak potrzebne rozszerzenia metadanych MPP, i zachowują odczyt starszych sesji.
  Otwarcie całej sesji odtwarza zapisany aktywny wynik. Zachowany kandydat grafu,
  którego wcześniej nie zastosowano, nadal czeka na jawne zastosowanie.
  Sam aligned MPP nadal nie zawiera oryginałów sprzed interpolacji.
- REG-06 jest odłożony: obecna ścieżka nie wymaga jego interfejsu ani wyników
  kontroli. Po ewentualnym wznowieniu kontrola nie będzie ustalać wag, progów
  ani wyboru krawędzi tej samej próby. Jeśli model widział dane kontrolne
  (także przez globalne cechy obrazu), ocena jest zależna. Brak kontroli oznacza
  brak oceny, a zmiana roli danych nową próbę, nie pozorną niezależność.
- Modele są opcjonalne, z lokalnymi wagami, jawną wersją i sumą kontrolną.
  Brak zależności/wag/pamięci ma przyczynę w UI, bez pobierania i podmiany metody.
  Zapisane wyniki można obejrzeć bez ponownej inferencji. Nowy model nie zmienia
  domyślnego algorytmu ani nie deformuje lokalnie pikseli.

## Odbiór i statusy

Obowiązuje [wspólny protokół manualny](manual-protocol.md) oraz kroki ticketu.
Po implementacji agent zostawia `ready-for-review`, podaje commit, uruchomienie,
dane i oczekiwane zachowanie. **Nie rozpoczyna następnego ticketu przed ręcznym
odbiorem użytkownika.** Automatyczne Qt offscreen nie zastępuje tego odbioru.

Zapisujemy oddzielnie działanie funkcji i jakość rejestracji. Test algorytmu
nie jest zaliczony wyłącznie dlatego, że program zakończył obliczenia.
Wynik „gorzej” lub „niejednoznacznie” wymaga decyzji: poprawić etap, odrzucić
wariant lub zachować go jako eksperymentalny. Nie promujemy go automatycznie.
Można zamknąć świadomie odebrany eksperyment z negatywnym wynikiem naukowym,
jeżeli spełnia kontrakt funkcji, a decyzja i ograniczenia są zapisane.

`done` wymaga spełnionych kryteriów, sprawdzeń, przeglądu, commita, przekazania
i jawnego ręcznego odbioru. Przy odpowiedzi „testy manualne ok” aktualizujemy
status, jeśli nie ma innych niespełnionych warunków; nie zostawiamy wówczas
ticketu bez powodu w `ready-for-review`. Otwarte zależności integracji opisujemy.

## Realizacja i granice testów

Stosujemy [zasady implementacji i przeglądu](../implementation/README.md#praca-ze-skillem-implement):
zapis HEAD przed zmianami, TDD na publicznych zachowaniach, typecheck,
odpowiednie testy, pełny zestaw repo raz na końcu ticketu, przegląd Standards/Spec,
commit i [handoff](../handoff.md). Historyczne wyłączenie rozwoju algorytmów
w pierwszej wersji nie dotyczy tego nowego planu.

W ticketach zapisano proponowane publiczne granice TDD, bez narzucania nazw
klas i prywatnych helperów. Ich zakres należy uwzględnić przy zleceniu ticketu;
nie opisujemy ich jako wcześniej zatwierdzonych w zestawie 21 zadań.
Wzorce syntetyczne obejmują znane przesunięcia w obu osiach, szum linii,
niejednoznaczny wzór okresowy i niedopasowanie modelu jednego XY.
Badania na lokalnych filmach są oddzielnym dowodem od testów syntetycznych.

Cel wielkości pliku kodu: do 1000 linii; twardy limit: **1500 fizycznych linii**,
zgodnie z [instrukcją aplikacji](../../../stmviewer/AGENTS.md).
Podział na moduły i konieczne porządkowanie wykonujemy wewnątrz odpowiedniego
etapu, bez osobnego ticketu kończącego się samym refaktorem.

Nowy kod specyficzny dla Viewera, jego testy i dokumentacja należą do tej sesji.
Istniejące publiczne backendy można wykorzystywać bez zmian. Jeśli potrzebna
jest zmiana wspólnego kodu lub konfiguracji głównej, opisujemy wymagany kontrakt
w handoff i kierujemy go do `stm-next`, zgodnie z
[regułami współpracy](../../PARALLEL_DEVELOPMENT.md). Nie edytujemy innych worktree.

Zadania pierwszej wersji 19–21 zachowują swoje statusy. Problem długiego
nagłówka MPP nie blokuje pracy na tych dwóch filmach, ale pozostaje osobnym
warunkiem odbioru dużych eksportów. Próby na Ubuntu nie oznaczają odbioru Windows.

## Poza bieżącą implementacją

Swobodna deformacja obrazu, prostowanie do założonej sieci molekuł,
trening modeli, automatyczne pobieranie przez aplikację, zastępowanie brakujących
danych oraz wygładzanie trajektorii dryfu nie należą do tego planu.
REG-10–12 obejmują instrukcje przygotowania lokalnych wag i sprawdzenie warunków
ich wybranych wersji; sam plan niczego nie instaluje ani nie pobiera.
REG-08a/08b wyznaczają wspólne przesunięcia w próbie,
REG-08c stosuje je do filmu. REG-09 nie deformuje pikseli.
LightGlue + ALIKED i TartanMatch pozostają na liście obserwacyjnej w przeglądzie,
bez osobnych ticketów przed oceną trzech wybranych modeli. Wszystkie pary filmu,
szablon uśredniony i optymalizacja grafu z ręcznymi twardymi ograniczeniami
wymagają osobnego uzasadnienia; nie rozszerzamy o nie pierwszego eksperymentu.
Wdrożenie rzeczywistej korekcji tearingu wymaga po REG-09 osobnego planu:
modelu deformacji, zachowania rzeczywistego ruchu, geometrii, ważności próbek
i metadanych eksportu. Obecne metadane pojedynczego XY nie opiszą takiej korekcji.
