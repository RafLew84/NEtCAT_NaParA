# SBC / MatID — próba domen z centrów molekuł

Data: 2026-10-23. Issue [16](issues/16-sbc-matid-domains.md).
**Obliczenia zakończone; wynik do omówienia. Nie wybrano metody do programu.**

SBC wnosi przydatną odporność na braki centrów i łagodne odkształcenie
sieci. W tej próbie rozdziela też granicę przesunięcia z błędami pozycji
lepiej niż poprzednia lokalna komórka. Nie spełnia jednak podstawowego
warunku samodzielnego wykrywania: zwraca obszary na losowych punktach,
scala różnicę orientacji 8°, a wynik zależy od losowego początku wyszukiwania.
Żadna z sześciu konfiguracji i trzech polityk wyniku nie przeszła wszystkich
warunków na kontrolach rozwojowych.

Proponowany następny krok to [17 — tekstura obrazu](issues/17-image-texture-domains.md).
SBC pozostaje niezależnym punktem odniesienia. Ewentualny dalszy wariant
powinien odpowiadać na konkretną lukę: wiarygodność powtarzania ponad przypadek,
scalanie zgodnych komórek i stabilność między początkami wyszukiwania.
Sam większy minimalny klaster ani wybór ładniejszego losowania nie jest
rozwiązaniem tych problemów. Nie uruchomiono 17 ani nowego treningu.

## Materiały i odtworzenie

- Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/sbc-matid-domains/index.html`.
  Jeden samowystarczalny HTML: pięć przykładów, wszystkie 228 próbek,
  surowy wynik, dwie adaptacje, poprzednia komórka, odmowy, prototypy komórek
  oraz osobno włączana referencja.
- W tym samym katalogu: `sbc-comparison.png` i `.pdf`, `controls.csv`,
  `cells.csv`, `settings.json`, `evaluation/`, `verification.json`,
  `cleanup-diagnostics.json`, `provenance.json`, `assignments/` i `predictions/`.
- Źródła: gałąź `prototype/stmdomains-sbc`, commit
  `e6d3fbc12f0b87b3a84d707a8e178289731ea2b3`, baza `2b70d0d`.
  Instrukcja `stmdomains/prototypes/README-sbc.md`; nie scalać prototypu
  do aplikacji. Dokumentacja jest na `domains/sbc-trial`, baza `9f2b127`.
- [Audyt źródeł i API](research-sbc-adaptation-audit.md) wyjaśnia różnicę
  między biblioteką atomistyczną a modelem naszych punktów.

Po utworzeniu worktree źródeł i przygotowaniu opisanych w README zależności:

```bash
bash stmdomains/prototypes/run_sbc_trial.sh \
  /home/rlew/projekty/NEtCAT-domains/.scratch/orientation-and-joining \
  /tmp/sbc-reproduction
```

Duże dane i wyniki pozostają lokalne. Zapisaliśmy parametry, wersje,
komórki/propozycje przed scalaniem, po scalaniu, przed czyszczeniem oraz
wynik biblioteki. Każda próbka przechowuje identyfikatory i sumę wejścia.

## Wejście i rozdzielenie analizy od oceny

Użyto niezmienionego zestawu z [próby orientacji i łączenia](orientation-and-joining-trial.md):
24 pełne klatki TTMAPP, 6730 centrów oraz 204 kontrole syntetyczne
(34 przypadki × 6 ziaren). 102 kontrole z ziarnami 1701–1703 służą do
wyboru ustawień; 102 z ziarnami 2701–2703 do późniejszego porównania.
Kontrole obejmują zero/jedną/wiele sieci, rozłączne płaty, różnice rozstawu,
sieć ukośną, braki, błędy pozycji, deformacje, granice przesunięcia,
różnice orientacji i cztery rodziny losowych punktów.

18 częściowych referencji TTMAPP zawiera 1678 centrów we wnętrzach:
BLACK 1303, RED 101, YELLOW 274. Kolory oznaczają przede wszystkim
orientacje tej samej sieci. Pary domen oceniamy według `region_instances`,
nie według samego koloru. Nieoznaczone miejsce nie jest przykładem tła.
Te referencje były wcześniej oglądane; nie stanowią niezależnej walidacji
na nowej akwizycji. Odłożone ziarna syntezy także nie dowodzą transferu
na nowe rzeczywiste materiały.

Predykcja dostaje tylko `input/analysis`; nie odczytuje referencji ani obrazu
jako cechy. Ustawienia zamrożono po ocenie kontroli rozwojowych, przed oceną
odłożonych kontroli i TTMAPP. Pełne predykcje zapisano przed otwarciem
referencji w ocenie. Wstępne cztery sprawdzenia API obejmowały też klatkę
250, bez oceny ramek i bez strojenia do niej. Korekta progu nakładania
wynikała z nieprawidłowego odrzucenia idealnej kontrolnej sieci przez API.

SHA-256 manifestu analizy:
`4b038d7ac488ba47f3b97bab7eab714263690de65608a80448a0ae552647be23`.
Manifest oceny:
`b2f496fc3100ea3cf038840e2cd48bbcb1e14a5caa09fb325bc65e2993119719`.
Pozostałe identyfikatory, w tym źródła MatID i poprzednich predykcji,
są w `provenance.json`.

## Biblioteka i jawna adaptacja

Zbudowano MatID z dokładnie przypiętego commita
`5aa27776df0277e2b75af8680bd0faf760cf924a` (wersja pakietu 2.2.0).
Publikacja SBC dotyczy rozpoznawania okresowych struktur atomistycznych;
nie potwierdza skuteczności na wykrytych centrach molekuł STM.
[Artykuł autorów](https://www.nature.com/articles/s41524-024-01498-x).

Każdy punkt jest jedną kategorią w płaszczyźnie, bez periodycznych brzegów.
Współrzędne pomnożono przez techniczny `pixel_spacing_xy` i podzielono przez
12 px. To jawna wspólna jednostka numeryczna, nie Å i nie oszacowany
rozstaw każdej domeny. Zachowujemy różnice rzeczywistego rozstawu w px.
Własne promienie wynoszą zero. Próg połączenia 1.65 odpowiada 19.8 px;
`merge_radius=1.65`, `merge_threshold=0.5`, `angle_tol=20`, `seed=7`.
`angle_tol` jest parametrem budowy bazy, nie limitem różnicy orientacji domen.

Sprawdzono `pos_tol=0.08/0.15/0.24` (0.96/1.8/2.88 px) i
`max_cell_size=2.5/3.5` (30/42 px). `overlap_threshold=0` nie narzuca
minimalnej fizycznej odległości między punktami w adaptacji. Próba API
pokazała, że dodatni próg 0.5 w wersji surowej odrzuca idealny rozstaw 1
przez wewnętrzne promienie H; nie użyto go w pełnym porównaniu.

Trzy polityki dla każdego ustawienia:

| Wynik | Znaczenie |
| --- | --- |
| `raw` | Oryginalne `SBC.get_clusters`, z podanymi wyżej parametrami i zewnętrznymi zerowymi promieniami. Wewnętrzna walidacja prototypu nadal używa promieni atomowych kategorii H. Zachowuje natywne scalanie, rozstrzyganie nakładania i tylko największy komponent. Bez naszego minimum 8. |
| `points-merged` | Zerowe promienie także wewnątrz `get_distances` i `get_dimensionality`. Zostawia biblioteczne scalanie propozycji. Następnie wszystkie punkty należące do wielu pozostałych propozycji otrzymują odmowę; zachowuje każdy połączony komponent ≥8 punktów. |
| `points-unmerged` | Ten sam model punktowy, ale korzysta z propozycji sprzed scalania. Usuwa tylko dokładne duplikaty zbiorów punktów, potem odmawia konfliktom i zachowuje komponenty ≥8. To diagnostyka kosztu braku scalania, nie gotowy algorytm rozpoznawania zgodnych propozycji. |

Warianty adaptacji nie rozstrzygają niepewnych nakładań według kolejności
ani liczby sąsiadów. Jednak `points-merged` nadal dziedziczy wcześniejsze
scalanie biblioteki, które może połączyć różne struktury. `raw` pozostaje
punktem odniesienia, nie poprawnym modelem molekuł. Różnica raw/adapter
obejmuje kilka zmian naraz; nie przypisujemy całego efektu minimum 8.

MatID scala według wspólnych punktów, bez porównania komórek; zachowuje
prototyp większej propozycji i może zmieniać komórkę podczas wzrostu.
Dlatego zapisana baza nie jest globalnym fitem wszystkich członków.
W obecnym kodzie wyłączono też jeden z testów stopnia grafu powtarzalności
opisanego w publikacji. Szczegóły i odnośniki do konkretnych źródeł są
w [audycie](research-sbc-adaptation-audit.md).

## Wybór konfiguracji

Warunki ustalono przed oceną wyników: ≥90% przypisań pojedynczej sieci,
zero przypisań w czterech kontrolach losowych oraz ≥50% przypisań i ≤2%
scaleń w sześciu kontrolach rozdzielenia: dwie orientacje, różnica 8°,
różny rozstaw, rozłączne płaty, granica przesunięcia i ta granica z błędem
centrów. W przeciwieństwie do poprzedniej próby trudna granica jest tu
osobnym warunkiem koniecznym.

Ranking: najmniej niespełnionych warunków, potem najwyższa średnia
`przypisanie × (1−podziały) × (1−scalenia)` w 24 dodatnich przypadkach,
na końcu identyfikator konfiguracji. Brak mianownika par nie wprowadza
kary, ale zerowe przypisanie daje wynik zero. Niezależne rzędy nie mają
pełnej prawdy domen 2D i nie uczestniczą w wyborze.

Żaden z 18 wariantów nie spełnił kompletu. Do podglądu i głównego
porównania wybrano **diagnostycznie** `t0.15-c3.5/points-merged`:
tolerancja 1.8 px, maksymalny wektor 42 px. Nie przeszły warunki losowego
porządku i małej różnicy orientacji. Wszystkie pozostałe wyniki zachowano;
nie wybrano ustawienia według referencji TTMAPP.

## Odłożone kontrole

Tabela dotyczy trzech ziaren każdej kontroli. Liczności dotyczą propozycji
całego pola. Podziały/scalenia są warunkowe wśród przypisanych par;
przypisanie i fałszywe punkty pokazujemy osobno.

| Kontrola | SBC punkty 2D: liczba obszarów | Przypisanie | Podziały / scalenia par | Poprzednia komórka |
| --- | --- | --- | --- | --- |
| Jedna sieć | 1 / 1 / 1 | 100% | 0% / — | 98.4%, jedna domena |
| Braki 30% | 1 / 1 / 1 | 99.8% | 0% / — | 81.9%, jedna domena |
| Braki 50% | 2 / 1 / 1 | 73.2% | 2.4% / — | 53.6%, 31.8% podziałów |
| Błąd centrów 1.2 px | 3 / 2 / 0 | 18.4% | 33.9% / — | 76.8%, bez podziałów |
| Dwie orientacje, 27° | 2 / 2 / 2 | 99.6% | 0% / 0% | 96.4%, bez błędów par |
| Różnica orientacji 8° | 1 / 1 / 1 | 100% | 0% / **100%** | 97.6%, dwie domeny, bez błędów par |
| Granica przesunięcia | 2 / 2 / 2 | 100% | 0% / 0% | 92.9%, bez błędów par |
| Granica + błąd 0.72 px | 2 / 2 / 3 | 52.2% | 1.9% / 0.2% | 92.8%, **98.1% scaleń** |
| Rozłączne identyczne płaty | 2 / 2 / 2 | 100% | 0% / 0% | 96.2%, bez błędów par |
| Gładkie odkształcenie | 1 / 1 / 1 | 100% | 0% / — | 95.5%, 51.0% podziałów |
| Różne rozstawy | 2 / 2 / 2 | 100% | 0% / 0% | 88.3%, bez błędów par |
| Sieć ukośna | 1 / 1 / 1 | 100% | 0% / — | 96.9%, bez błędów par |

W trudnej granicy wynik raw ma 93.4% przypisań i 0.6% scaleń;
konserwatywne wyłączenie wspólnych punktów w adaptacji poprawia wynik par
kosztem dużej liczby odmów. Bez scalania propozycji zostaje tylko 1.3%
przypisań tej kontroli. Nie wolno uznać tego ostatniego za poprawną granicę.

W czterech rodzinach losowych, łącznie 3195 punktów:

| Metoda | Punkty w fałszywych propozycjach |
| --- | --- |
| Raw | 246 / 3195 = 7.7% |
| Punkty 2D, ze scalaniem | 355 / 3195 = 11.1% |
| Punkty 2D, bez scalania | 355 / 3195 = 11.1% |
| Poprzednia komórka z kryterium powtarzalności | 0 / 3195 |

To błąd dyskwalifikujący aktualną konfigurację jako samodzielny detektor.
Wariant punktowy ma więcej fałszywych wskazań niż raw mimo minimum 8:
usunięcie atomowych ograniczeń zmienia również zbiór propozycji. Losowe
skupiska mają 181/891 fałszywie przypisanych centrów. Nie stroiliśmy teraz
dodatkowego filtra według tych odłożonych danych.

SBC odkrywa komórki, nie tylko etykiety: w kontroli kwadratowej baza ma
12 × 12 px, w ukośnej 12 i 12.71 px z odpowiednim skosem. Dwa rozstawy
dają komórki 12 i 16 px; wybrana baza pierwszego obszaru może zawierać
przekątną 16.97 px, więc same długości wektorów bez uwzględnienia
równoważnych baz nie definiują typu. Dwie orientacje 27° zachowują rozstaw.
Losowe dane również potrafią dać prototypy z 1–4 punktami w motywie.
Samo istnienie odtworzonej komórki nie dowodzi rzeczywistej domeny.

## TTMAPP — wyłącznie częściowa ocena

| Metoda przy zamrożonych ustawieniach | Przypisane centra / 1678 | Podziały par wewnątrz regionów | Scalenia par różnych regionów |
| --- | --- | --- | --- |
| Raw | 1307 = 77.9% | 2895/38722 = 7.5% | 373/9599 = 3.9% |
| Punkty 2D, ze scalaniem | 1065 = 63.5% | 1843/31227 = 5.9% | 232/4189 = 5.5% |
| Punkty 2D, bez scalania | 164 = 9.8% | 196/1075 = 18.2% | 29/413 = 7.0% |
| Poprzednia komórka | 1187 = 70.7% | 1001/35733 = 2.8% | 0/3801 = 0% |

| Grupa referencji | Raw | Punkty 2D | Poprzednia komórka |
| --- | --- | --- | --- |
| BLACK | 1160/1303 = 89.0% | 990/1303 = 76.0% | 1125/1303 = 86.3% |
| RED | 40/101 = 39.6% | 17/101 = 16.8% | 14/101 = 13.9% |
| YELLOW | 107/274 = 39.1% | 58/274 = 21.2% | 48/274 = 17.5% |

Poprawa RED/YELLOW w adaptacji jest mała, a całościowo przypisanie spada
i pojawiają się scalenia. Raw ma więcej przypisań, lecz także wiele małych
regionów i zależność od domyślnych promieni. Bez scalania większość
przesłanek tego samego obszaru konkuruje ze sobą i powoduje odmowy.
To nie uzasadnia ani dowolnego łączenia, ani bezwarunkowego odrzucenia
wszystkich nakładań jako docelowej metody.

Parametry silnie zmieniają wynik: w adaptacji ze scalaniem przypisanie
w referencjach wynosi 35.5–76.4%, a warunkowe scalenia 0–39.4%.
Niższy błąd przy odmowie większości danych nie oznacza przewagi.
Nie oceniono dokładności pozostałych obszarów, granic pikselowych,
powierzchni warstwy ani stabilnego katalogu typów. `type_id` i pojedynczy
kąt pozostają nieustalone; zapisane są pełne bazy/motywy propozycji.

## Czyszczenie, niejednoznaczność i stabilność

Kontrola dwóch rozłącznych płatów daje oba płaty także w raw: podejrzewana
utrata drugiego płata nie wystąpiła w tym konkretnym wyszukiwaniu.
Osobna kontrola cyklu biblioteki podała do czyszczenia jedną propozycję
obejmującą dwa płaty po 9 punktów. Raw zachowało 9 punktów, adaptacja
18 w dwóch komponentach. To potwierdza zachowanie funkcji, nie dowodzi
błędu detekcji w każdej naturalnej sytuacji.

W całym zestawie czyszczenie raw usunęło 1091 punktów w 82 próbkach,
w tym 317 punktów w 24 klatkach TTMAPP. Nie oznacza to automatycznie
1091 błędów: część może być poprawnie usuwanymi luźnymi punktami.
Ślady etapów pozwalają odróżnić brak znalezienia od odrzucenia na końcu.

Sprawdzenia odtwarzalności i odporności:

- Powtórzono pełną analizę wybranego ustawienia w osobnym drzewie bez
  referencji, ze zmianą kolejności punktów i odwróceniem kolejności klatek.
  **228/228 wyników i pełnych śladów identycznych**, poza czasem wykonania.
  Wejście jest kanonizowane po stałych identyfikatorach obiektów.
- Kontrast, inwersja i techniczne powiększenie ×2: po 6 par, wszystkie
  trzy polityki dają identyczne przypisania. To oczekiwane dla metody
  punktowej; nie jest dowodem odporności algorytmu obrazowego.
- Obrót 37°: identyczne relacje par i przypisania wszystkich trzech
  polityk w 10 sprawdzonych próbkach, w tym TTMAPP 250 i 268.
- Zmiana umownej kategorii H na C zmienia raw w 10/10 próbek; adaptacje
  zachowują wynik w 10/10. Potwierdza to usunięcie zależności atomowej
  we wskazanych wywołaniach adaptera.
- Zmiana ziarna 7 na 19 lub 43 zmienia wynik adaptacji ze scalaniem
  w 5/10 próbek. W TTMAPP 250 status przypisania zmienia odpowiednio
  70 i 60 centrów; w 268 — 61 i 81. To znaczna niestabilność.
- Odwrócenie wejścia bez kanonizacji również zmienia tę adaptację
  w 5/10 próbek. Sortowanie stabilizuje konkretne uruchomienie, ale nie
  usuwa zależności naukowego wyniku od początku wyszukiwania ani od
  nadania nowych identyfikatorów.

Zapisano 684 poprawne koperty wyników i 1460 opisów komórek wybranego
ustawienia. Wszystkie wyniki mają rozłączne przypisania albo jawne odmowy;
surowe propozycje są oznaczone jako eksperymentalne, bez zatwierdzenia.
QtWebEngine offscreen: 35 sprawdzeń wszystkich kroków scenariuszy,
trybów, metod i przełącznika referencji; bez błędów JS i poziomego
przepełnienia. Obejrzano zrzut HTML i osobny wykres PNG. Sprawdzono
składnię Pythona/Bash i `git diff --check`. Nie testowano natywnego GUI
ani kodu produkcyjnego, który nie został zmieniony.

Jedna próbka (`control-0045`, losowa kontrola rozwojowa) wydała ostrzeżenia
numeryczne `invalid value encountered in cast/divide`; zachowano je w
wyniku. Nie wystąpił wyjątek przerywający przebieg ani niefinitywny zapis
wyniku. Biblioteka sama przechwytuje wyjątki czyszczenia; ślady zapisują
stan przed i po, ale nie zmienialiśmy jej obsługi wyjątków.

## Koszt i środowisko

Python z lokalnego `netcat`; MatID 2.2.0 i spglib 2.6.0 w osobnym
`/tmp/stmdomains-issue16-deps`, bez instalacji do środowiska użytkownika.
NumPy 2.2.5, SciPy 1.15.2, ASE 3.25.0, NetworkX 3.4.2,
scikit-learn 1.6.1. CPU, jeden wątek BLAS/OpenMP, bez GPU i treningu.

- 102 kontrole rozwojowe × 6 ustawień, każdorazowo raw i punktowe SBC:
  91.05 s, maksymalny RSS 222824 KiB.
- Wszystkie 228 próbek × 6 ustawień: 224.07 s, RSS 223844 KiB (~219 MiB).
- Pełne powtórzenie wybranego ustawienia: około 41 s; dodatkowe próby
  ziaren, obrotu i kategorii dotyczą osobnej dziesiątki próbek.

RSS to szczyt całego procesu, nie samej biblioteki. Czasy nie obejmują
pobrania/kompilacji pakietu. Nie wykonano benchmarku całych 268 klatek ani
prób wielkoskalowych. Nie potrzeba obecnie GPU do tej implementacji SBC.

## Stan decyzji

Użytkownik polecił przejść od 15 do 16. Issue 15 kończymy jako trzy
udokumentowane eksperymenty, z komórką jako punktem odniesienia;
nie jako przyjęcie algorytmu. Próba 16 jest wykonana i pozostaje
`claimed` do omówienia wyniku. Odbiór 13 i protokół jakości 04 nadal
pozostają otwarte. Kolejny proponowany eksperyment to 17, bez zmiany
warunku braku zadanej liczby domen lub treningu na kolorowych ramkach.
