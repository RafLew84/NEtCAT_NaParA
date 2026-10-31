# Plan rozwoju rejestracji trudnych filmów STM

Data: 2026-10-28; rozszerzenie ręcznego dopasowania: 2026-10-30.
Gałąź: `viewer/registration-difficult-movies`.
Baza rozpoznania: `c85aecb`; przegląd metod: `81ff1a0`.
Status: REG-01, REG-01a i REG-02 `done`. Użytkownik potwierdził odbiór REG-02
2026-10-31 i zgłosił brak istotnej poprawy względem Phase na MOVIE_4.
Deep Matcher ocenia najlepiej w obejrzanych pierwszych 100 klatkach.
[Instrukcja REG-02](unnormalized-correlation-manual.md), [wyniki](reviews/REG-02.md).
REG-03 jest odblokowany i czeka na osobne zlecenie. Dalsze próby MOVIE_4
obejmują źródłowe klatki 3–364, zgodnie z [protokołem](manual-protocol.md).
[Instrukcja manualna](manual-alignment-manual.md), [karta sprawdzeń](reviews/REG-01a.md).
Użytkownik wybrał układ C; jest wdrożony z opisowymi kartami wyników i ręcznym
sterowaniem pod obrazem. [Aktualny przegląd i próby](reviews/REG-01a-layout-c.md).
Wcześniejsze A/B w opisach mapy odpowiadają wynikowi zachowanemu/bieżącemu.
Zlecenie użytkownika: małe tickety, ręczna ocena wpływu i jakości po każdym.

## Cel i zakres

Poprawić dopasowanie struktur próbki w MOVIE_4 i MOVIE_8 mimo zakłóceń linii
i tearingu. Pierwsza część nadal wyznacza jedno XY dla całej klatki.
Dowolny kierunek i zmiany kierunku dryfu są dozwolone.
Nie utożsamiamy mniejszego aligned ani gładszej trajektorii z lepszym wynikiem.

Podstawa: [rozpoznanie danych](../registration-difficult-movies.md),
[przegląd metod i źródła](../registration-improvement-options.md).
Nowe zlecenie rozpoczyna etap rozwoju metod odłożony w
[mapie pierwszej wersji](../map.md). Nie zmienia historycznych odbiorów 01–21.
W tej numeracji używamy **REG-01…REG-09** oraz dodanego **REG-01a**, aby uniknąć
kolizji i zachować numery istniejących zadań.

## Kolejność i wynik każdego ticketu

| Ticket | Efekt widoczny w aplikacji | Blocked by |
| --- | --- | --- |
| [REG-01: Porównanie par klatek](issues/01-pair-comparison.md) | Nakładka i przełączanie obrazów przed/po dopasowaniu; porównanie dwóch prób A/B przy jednakowym widoku. | Brak |
| [REG-01a: Ręczne dopasowanie pary](issues/01a-manual-alignment.md) | Ruch klatki dopasowywanej ±1 px w X/Y, nakładka/przełączanie obrazów, start z zera lub korekta próby, zachowanie ręcznego wyniku jako B. | REG-01 |
| [REG-02: Korelacja bez normalizacji](issues/02-unnormalized-correlation.md) | Osobny wariant dostępny dla pary i całej serii, z porównaniem do dotychczasowego Phase. | REG-01a |
| [REG-03: Ręczne maski zakłóceń](issues/03-manual-masks.md) | Zaznaczanie obszarów używanych i pomijanych; rejestracja uwzględnia osobne maski klatek. | REG-02 |
| [REG-04: Dopasowanie wieloskalowe](issues/04-multiscale-translation.md) | Zgrubne XY i doprecyzowanie na pełnym obrazie; jawna ocena niejednoznacznych dopasowań. | REG-03 |
| [REG-05: Zgodność lokalnych fragmentów](issues/05-local-consensus.md) | Wektory dopasowania fragmentów, wskazanie zgodnych/odrzuconych i odporne wyznaczanie globalnego XY. | REG-04 |
| [REG-06: Niezależna kontrola dopasowania](issues/06-independent-validation.md) | Ocena na wydzielonych fragmentach kontrolnych i lista par wymagających obejrzenia. | REG-05 |
| [REG-07: Zapis prób i odbiór pełnych filmów](issues/07-full-movie-comparison.md) | Odtwarzalne porównanie pełnych wyników, zapis/odczyt ustawień i przesunięć, odbiór MOVIE_4/MOVIE_8. | REG-06 |
| [REG-08: Spójność kilku klatek](issues/08-temporal-consistency.md) | Warunkowo: diagnostyka zgodności A→B→C z A→C, bez narzucania trajektorii. | REG-07 + decyzja po odbiorze |
| [REG-09: Rozpoznanie deformacji w pasach](issues/09-scanline-diagnostics.md) | Warunkowo: podgląd lokalnych rozbieżności po globalnym XY i podstawa decyzji o korekcji tearingu. | REG-07 + decyzja po odbiorze |

REG-01 ma status `done` po odbiorze użytkownika 2026-10-29:
[instrukcja próby](pair-comparison-manual.md),
[karta odbioru](reviews/REG-01.md). REG-01a ma status `done` po odbiorze
użytkownika 2026-10-31. REG-02 również odebrano 2026-10-31 (`done`). REG-03–07 mają
status `ready-for-agent`:
zakres jest przygotowany, ale start
wymaga zlecenia użytkownika i zakończenia blokujących ticketów. REG-08/09 mają
status `planned`; nie uruchamiamy ich automatycznie. Nie zależą od siebie.
Kolejność REG-01 → REG-01a → REG-02–07 jest również kolejnością ręcznych
odbiorów: chcemy ocenić pojedynczą zmianę przed dołożeniem następnej, nawet jeśli część kodu można
technicznie napisać niezależnie.

## Stałe kontrakty

- REG-01a ustawia XY jednej pary ręcznie, w pikselach original (+X w prawo,
  +Y w dół). Klatka odniesienia pozostaje nieruchoma. A/B to próby; obrazy
  nazywamy odniesieniem i dopasowywaną klatką. Szkic ręczny jest odrębny od
  zatwierdzonych prób. Zastosowanie tworzy B z jawnym pochodzeniem ręcznym
  i bez automatycznego wskaźnika pewności. Pełny aligned i eksport zachowują
  dotychczasowy wynik; ręczne składanie całego filmu wymaga osobnego zakresu.
- Próby ręczne można rozpocząć od zera lub kopii istniejącego wyniku tej pary.
  Podgląd zawsze powstaje z oryginałów i całkowitego XY. REG-07 zachowuje
  początkowe XY, pochodzenie, korektę i wynik ręczny. Ocena wzrokowa operatora
  nie staje się automatycznie niezależną kontrolą z REG-06.

- Każda metoda dodawana w REG-02–05 działa od razu na parze i na całej serii,
  przez ten sam estymator. REG-07 nie odkłada podstawowej integracji z GUI.
- Dotychczasowe metody pozostają dostępne. Nowe warianty są jawnie wybierane,
  bez automatycznej zmiany domyślnej metody ani cichego zastępowania po błędzie.
- Pomocnicze filtrowanie/maski służą wyznaczaniu przesunięcia. Aligned powstaje
  z oryginalnych wartości, z jedną interpolacją końcową. Gamma nie wpływa na XY.
- Nowa maska obliczeń jest odrębna od maski ważności aligned. Zaznaczenie
  zakłócenia nie usuwa ani nie wypełnia jego pikseli w zapisanym obrazie.
- Współrzędne masek i fragmentów odnoszą się do original i pochodzenia klatki.
  Wspólny układ porównania zakotwiczamy w źródłowej klatce odniesienia;
  różny padding wyników nie może przesuwać podglądu A/B.
- Porównanie przechowuje ustawienia, przesunięcia i potrzebne metadane,
  renderując oglądane klatki na żądanie. Nie utrzymuje dwóch dodatkowych
  pełnych filmów float64. Zwykły wynik aligned działa jak dotychczas.
- Brak wiarygodnego dopasowania nie oznacza (0,0). Wynik liczbowy z małym
  poparciem może być widoczny jako niepewny; brak wyniku lub błąd przerwie
  próbę całej serii, zachowując poprzedni kompletny aligned.
- Postęp, anulowanie, ochrona poprzedniego wyniku i blokady edycji serii
  podczas obliczeń obowiązują również nowe metody i podgląd par.
- Usuwanie klatek zachowuje gotową geometrię pozostałych. Nowe obliczenie
  korzysta z oryginałów bieżącej serii. Nie dodajemy odwracania kolejności.
- Każdy wariant ma jednoznaczną nazwę i wersję ustawień. MPP/AVI korzystają
  z aktywnego kompletnego aligned, a nie z dowolnego eksperymentu pary A/B.
  Szczegółowy zapis próby z REG-07 jest osobnym dokumentem, nie zmianą
  istniejącego formatu metadanych MPP.

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

Otwarte zadania pierwszej wersji 19–21 zachowują swoje statusy. Problem długiego
nagłówka MPP nie blokuje pracy na tych dwóch filmach, ale pozostaje osobnym
warunkiem odbioru dużych eksportów. Próby na Ubuntu nie oznaczają odbioru Windows.

## Poza bieżącą implementacją

Automatyczne maskowanie zakłóceń, swobodna deformacja obrazu, prostowanie do
założonej sieci molekuł, trening/pobieranie modeli, zastępowanie brakujących
danych oraz wygładzanie trajektorii dryfu nie należą do REG-01–07.
REG-08 nie optymalizuje jeszcze trajektorii; REG-09 nie deformuje pikseli.
Wdrożenie rzeczywistej korekcji tearingu wymaga po REG-09 osobnego planu:
modelu deformacji, zachowania rzeczywistego ruchu, geometrii, ważności próbek
i metadanych eksportu. Obecne metadane pojedynczego XY nie opiszą takiej korekcji.
