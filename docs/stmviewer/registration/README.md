# Plan rozwoju rejestracji trudnych filmów STM

Data: 2026-10-28; rozszerzenia ręczne: REG-01a 2026-10-30, REG-02a 2026-10-31.
Rozszerzenie o graf dopasowań i nowe modele: 2026-10-31, na zlecenie użytkownika.
Gałąź: `viewer/registration-difficult-movies`.
Baza rozpoznania: `c85aecb`; przegląd metod: `81ff1a0`.
Status: REG-01, REG-01a, REG-02, REG-02a, REG-04 i REG-05 `done`. Użytkownik potwierdził odbiór REG-02
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
użytkownika; REG-07 jest w realizacji.
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
REG-05 → ocena i zapis prób REG-06/07 → diagnostyka REG-08 → graf
REG-08a/08b/08c → osobne próby EfficientLoFTR, RoMa v2 i MatchAnything
REG-10/11/12. [Przegląd i źródła](../registration-multiframe-research.md)
uzasadniają te próby, ale nie potwierdzają ich skuteczności na naszych filmach.
REG-08 przestaje być warunkowy; nadal sam nie zmienia XY. Dalsze odniesienia
REG-08d i diagnostyka tearingu REG-09 pozostają warunkowe. Rozszerzenie planu
nie jest implementacją ani odbiorem REG-04.

**Odłożenie REG-06 — 2026-10-31:** użytkownik zdecydował „na razie pominiemy 06”.
REG-06 pozostaje w planie ze statusem `planned`, poza bieżącą kolejnością.
Aktualna ścieżka prowadzi z REG-05 bezpośrednio do REG-07, następnie REG-08
i dalszych etapów. REG-07 oraz kolejne tickety nie przejmują implementacji
kontroli REG-06. Ocena wizualna, poparcie estymatora i diagnostyka spójności
pozostają dostępne zgodnie ze swoimi zakresami; nie nazywamy ich niezależną
walidacją. Wznowienie REG-06 wymaga osobnego zlecenia.

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
czternaście etapów podstawowych; REG-06 jest odłożony, a dwa etapy pozostają
warunkowe. Sufiksy REG-08a–08d rozwijają pracę
na wielu klatkach; REG-09 zachowuje dotychczasowy zakres.

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
| [REG-07: Zapis prób i odbiór pełnych filmów](issues/07-full-movie-comparison.md) | Odtwarzalne porównanie pełnych wyników, zapis/odczyt ustawień i przesunięć, odbiór MOVIE_4/MOVIE_8. | REG-05 |
| [REG-08: Spójność kilku klatek](issues/08-temporal-consistency.md) | Diagnostyka zgodności A→B→C z A→C i porównanie również niesąsiednich par; jeszcze bez zmiany XY. | REG-07 |
| [REG-08a: Graf z oknem 3/5 klatek](issues/08a-window-graph.md) | Osobna pełna próba: obecny Deep, wspólne XY przez LS, porównanie z łańcuchem i zapis relacji. | REG-08 |
| [REG-08b: Odporny graf](issues/08b-robust-graph.md) | LS kontra Huber/IRLS na dokładnie tych samych pomiarach; widoczny wpływ odstających relacji. | REG-08a |
| [REG-08c: Zastosowanie grafu do filmu](issues/08c-graph-movie-application.md) | Jawna podmiana aligned, ręczne korekty, MPP/AVI i odtworzenie zapisanej próby. | REG-08b |
| [REG-10: EfficientLoFTR](issues/10-efficient-loftr.md) | Nowy model dla par, łańcucha i grafu; porównanie z obecnym Deep przy stałej reszcie obliczeń. | REG-08c |
| [REG-11: RoMa v2](issues/11-roma-v2.md) | Gęste korespondencje jako źródło jednej translacji XY; osobna ocena jakości i zasobów. | REG-10 |
| [REG-12: MatchAnything-ELoFTR](issues/12-matchanything.md) | Kontrola wpływu treningu: porównanie z EfficientLoFTR przy tym samym konsensusie i grafie. | REG-11 |
| [REG-08d: Dalsze klatki odniesienia](issues/08d-long-range-references.md) | Warunkowo: uzupełnienie odebranego okna o jawne dalsze odniesienia, bez zmiany modelu pary. | REG-08c + decyzja po odbiorze |
| [REG-09: Rozpoznanie deformacji w pasach](issues/09-scanline-diagnostics.md) | Warunkowo: podgląd lokalnych rozbieżności po globalnym XY i podstawa decyzji o korekcji tearingu. | REG-07 + decyzja po odbiorze |

REG-01 ma status `done` po odbiorze użytkownika 2026-10-29:
[instrukcja próby](pair-comparison-manual.md),
[karta odbioru](reviews/REG-01.md). REG-01a ma status `done` po odbiorze
użytkownika 2026-10-31. REG-02 i REG-02a również odebrano 2026-10-31 (`done`).
REG-04 i REG-05 mają status `done` po odbiorze użytkownika 2026-10-31.
REG-07 ma status `in-progress`. REG-08, REG-08a/08b/08c i REG-10–12 mają status `ready-for-agent`: zakres jest przygotowany, ale start wymaga
zlecenia użytkownika i zakończenia blokujących ticketów. REG-06 ma status
`planned` jako odłożony; nie blokuje bieżącej ścieżki i nie jest odebrany.
REG-08d i REG-09 również mają status `planned` jako warunkowe osobne odnogi.
Żadnego z tych etapów nie uruchamiamy automatycznie.

Kolejność podstawowa: REG-01 → REG-01a → REG-02 → REG-02a → REG-04 → REG-05
→ REG-07 → REG-08 → REG-08a → REG-08b → REG-08c → REG-10 → REG-11
→ REG-12. To także kolejność ręcznych odbiorów, nawet gdy część kodu można
technicznie napisać niezależnie. Zależność między REG-10/11/12 porządkuje
eksperymenty; RoMa nie wymaga uruchamiania EfficientLoFTR, a MatchAnything nie
wymaga działającego RoMa. Wspólną bazą porównań pozostaje obecny Deep.

Trwa realizacja [REG-07 — zapis prób i odbiór pełnych filmów](issues/07-full-movie-comparison.md).
Zależność od REG-05 jest spełniona. [Instrukcja odbioru](full-trial-manual.md)
i [raport prób](full-trial-results.md) opisują nowy zapis i porównanie A/B.
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
  początkowe XY, pochodzenie, korektę i wynik ręczny. Ocena wzrokowa operatora
  nie staje się automatycznie niezależną kontrolą z REG-06.

- REG-02a wymaga kompletnej rejestracji bazowej. Ręczne XY zastępuje przesunięcie
  pary; różnica zmienia skumulowane XY tej i kolejnych klatek. Powtórzenie nie
  dubluje zmiany, cofnięcie dotyczy jednej pary. Film powstaje z oryginałów;
  błąd/anulowanie zachowują wcześniejszy wynik i korekty. Po usunięciu klatki
  dotychczasowy aligned/eksport zostaje, lecz dalsza edycja wymaga nowej rejestracji.
  Eksport poprawionego filmu i ręcznego pochodzenia należy już do REG-02a;
  zapis edytowalnych prób przy oryginalnych źródłach pozostaje w REG-07.
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
- Porównanie przechowuje ustawienia, przesunięcia i potrzebne metadane,
  renderując oglądane klatki na żądanie. Nie utrzymuje dwóch dodatkowych
  pełnych filmów float64. Zwykły wynik aligned działa jak dotychczas.
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
  Szczegółowy zapis próby z REG-07 jest osobnym dokumentem, nie zmianą
  istniejącego formatu metadanych MPP.

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
- REG-08a/08b tworzą próbę do oglądania i zapisu w GUI, bez podmiany aktywnego
  aligned. REG-08c dodaje **Zastosuj wynik do filmu** oraz eksport. To celowy
  podział na etapy możliwe do ręcznej oceny; szczegółowy wyjątek eksportowy
  znajduje się w protokole. Pełne klatki próby renderujemy na żądanie.
- REG-08c zamraża globalne XY grafu jako bazę dla REG-02a. Ręczne nadpisanie
  zastępuje różnicę XY sąsiadów tej bazy i przesuwa dalsze klatki, bez ponownego
  uruchamiania solvera. Surowa krawędź modelu, wynik grafu i ręczna korekta są
  osobnymi danymi. Nowa optymalizacja tworzy osobną próbę; przed jej zastosowaniem
  UI pokazuje, które ręczne korekty aktywnego wyniku zostaną zastąpione.
- Dokument próby przechowuje krawędzie i ich źródła, konfigurację grafu,
  bazowe/końcowe XY oraz ręczne nadpisania. Rozszerzenia tego dokumentu i
  metadanych MPP należą do wprowadzającego je ticketu i zachowują odczyt starszych
  wersji. Sam aligned MPP nadal nie zawiera oryginałów sprzed interpolacji.
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
REG-08 nie zmienia XY; REG-08a/08b wyznaczają wspólne przesunięcia w próbie,
REG-08c stosuje je do filmu. REG-09 nie deformuje pikseli.
LightGlue + ALIKED i TartanMatch pozostają na liście obserwacyjnej w przeglądzie,
bez osobnych ticketów przed oceną trzech wybranych modeli. Wszystkie pary filmu,
szablon uśredniony i optymalizacja grafu z ręcznymi twardymi ograniczeniami
wymagają osobnego uzasadnienia; nie rozszerzamy o nie pierwszego eksperymentu.
Wdrożenie rzeczywistej korekcji tearingu wymaga po REG-09 osobnego planu:
modelu deformacji, zachowania rzeczywistego ruchu, geometrii, ważności próbek
i metadanych eksportu. Obecne metadane pojedynczego XY nie opiszą takiej korekcji.
