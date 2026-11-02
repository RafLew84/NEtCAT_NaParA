# STM Domains — odbiór 01 i suwak klatek

Data: **2026-11-02**. Użytkownik potwierdził pomyślne testy ręczne pierwotnego
SD-V4-01 (`808f3b7`) i zlecił dodanie suwaka pod obrazem. Suwak działa podczas
przeciągania i podąża za zmianami numeru/przycisków. Bez serii i dla jednej
klatki jest nieaktywny. Wykorzystuje istniejącą obsługę pracy w tle i odrzucania
starszych wyników; anulowanie przywraca pozycję wyświetlanej klatki.

W `netcat`: **9 testów widoku/nawigacji PASS**, mypy **14 plików PASS**,
kontrola długości zmienionego kodu/testów **162/204 linie**, przegląd drugiego
agenta bez uwag. Rzeczywiste GUI X11: przeciąganie na TTMAPP 268 klatek,
sprawdzenie obrazu i numeru przed puszczeniem uchwytu; zrzut lokalny
`.scratch/stmdomains-ui-01/slider.png`. GUI sterowano przez Qt i obejrzano zrzut.
Pełnego zestawu 230 testów z poprzedniego odbioru nie powtarzano.

[Scenariusz ręczny suwaka](implementation/interactive-v04/acceptance-01.md#ręczne-sprawdzenie-nowego-suwaka)
jest gotowy do osobnego odbioru użytkownika. Uruchomienie w `netcat`:
`python -m stmdomains.main`. Kolejny ticket pozostaje 02.
Worktree `/home/rlew/projekty/NEtCAT-domains`, gałąź `domains/interactive-v04-ui`,
baza **`808f3b7`**, commit dodatku w odpowiedzi końcowej. Brak nowych potrzeb
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
