# Budowa i odbiór szkieletu STM Domains

**Wykonano SD-V4-17 — domeny geometryczne, wybrany Panel A (`25252b2`, poprawki `4c3f3c8`).**
**Analiza → Analiza… → Metoda domen → Geometria**: kąt, rozstaw,
koherencja i wsparcie w bieżącej klatce; bez dopasowania klas.
Przełącznik **Bazowa / Geometria** nad obrazem zachowuje wynik i zoom.
Zapis/eksport obejmuje jeden wybrany wynik, typ pozostaje nieznany.
[Raport i test ręczny](interactive-v04/acceptance-17.md),
[protokół porównania](interactive-v04/experiment-17.md),
[przegląd](interactive-v04/review-17.md).
TTMAPP259–266: geometria bazowa 32–41 przypisań i 1 domena na klatkę;
bez referencji nie oznacza to poprawy. Kontrole wykazały nadmierne
podziały i nierozstrzygnięty skok fazy. Metoda pozostaje eksperymentalna.
**543 testy PASS**, mypy 109 modułów PASS, natywne GUI X11 PASS,
Standards/Spec 0 otwartych uwag; kod maks. 821 linii.
**Odbiór ręczny użytkownika 17 potwierdzony 2026-11-04 dla wersji `b58e69d` („testy manualn ok”).** Następny rekomendowany ticket: **18**;
21 (edycja ręczna) jest również dostępny po swoich zależnościach.
Poniżej historia wcześniejszych etapów.

**Wykonano SD-V4-15 — opis otoczenia i bariery (`1b0c1de`, poprawki `9fe24a6`, `9bf767a`).**
**Analiza → Analiza… → Zaawansowane**: sigma, histogram, zakres par i PCA,
progi/długości/nachylenie/poszerzenie barier oraz pomarańczowy podgląd.
Zmiana opisu wymaga nowego dopasowania; **Użyj istniejących klas** zachowuje
model przy zmianie barier. Projekt i PNG zachowują nową diagnostykę.
[Raport i test ręczny](interactive-v04/acceptance-15.md), [znaczenie parametrów](interactive-v04/advanced-settings.md),
[przegląd](interactive-v04/review-15.md). GUI X11 TTMAPP i kontrola syntetyczna PASS;
przywrócenie bazowych parametrów odtwarza dokładnie katalog, przypisania
oraz maskę. **510 testów PASS**, mypy 92 modułów PASS; maks. 474 linie
w 32 plikach kodu/testów. Standards/Spec: 0 otwartych uwag.
Status `done`; **odbiór ręczny użytkownika 15 potwierdzony 2026-11-03 dla wersji `f129ac2` („testy manualne ok”)**.
Następny rekomendowany ticket: **16 — kierunek, rozstaw i jakość geometrii**.
Poniżej historia wcześniejszych etapów.

**Wykonano SD-V4-14 — eksport PNG i CSV (`a20e14b`, poprawka `361a7d0`).**
**Plik → Eksportuj PNG/CSV…**: wybrany wynik, klatka lub zakres, pełny obraz
albo widoczny wycinek, aktualne Klasy/Domeny, gamma i warstwy. CSV zachowuje
ID, przypisania, powody odmów i mianowniki; brak analizy pozostaje brakiem.
Eksport nie uruchamia obliczeń. Nowy katalog zawiera opis i metadane;
postęp/anulowanie oraz odmowa nadpisania chronią wcześniejsze pliki.
[Raport i test ręczny](interactive-v04/acceptance-14.md), [format eksportu](interactive-v04/export-format-v1.md).
GUI X11 TTMAPP i kontrola wyniku zerowego PASS; kontrola typów 88 plików
PASS, Standards/Spec 0 otwartych uwag; 12 plików kodu/testów do 691 linii.
**499 testów PASS**. Status `done`; **odbiór ręczny użytkownika 14 potwierdzony 2026-11-03 dla wersji `4e9f1d9` („testy manualne ok”)**.
Następny rekomendowany ticket: **15 — opis otoczenia i bariery obrazu**.
Poniżej historia wcześniejszych etapów.

**Wykonano SD-V4-13 — zapis projektu (`4f40c28`, poprawki `1c9c221`).**
**Plik → Zapisz projekt… / Zapisz projekt jako…** zapisuje jeden plik
`.stmdomains`: cały MPP, oznaczenia, geometria, widok, szkic i jeden wybrany
przebieg lub brak analizy. Otwieranie odtwarza wynik bez źródeł i obliczeń.
Obsługiwane są wyniki częściowe, osobny wybór ostatniej odmowy i poprzedniego
wyniku, kontrola integralności, anulowanie oraz ochrona niezapisanej pracy.
[Raport i test ręczny](interactive-v04/acceptance-13.md), [format 1](interactive-v04/project-format-v1.md).
GUI X11 na TTMAPP: identyczne 105/312 i 5 domen po odtworzeniu, także dalsza
analiza z zapisanym katalogiem bez dopasowania. **490 testów PASS**, mypy
82 pliki PASS, Standards/Spec 0 otwartych uwag; maks. 661 linii. Status `done`;
**odbiór ręczny użytkownika 13 potwierdzony 2026-11-03 dla wersji `21fd906` („testy manualne ok”)**. Następny rekomendowany ticket:
**14 — eksport PNG i CSV**. Poniżej zachowano historię wcześniejszych etapów.

**Wykonano SD-V4-12 — Auto (`274f348`, poprawka `88006c1`).**
**Analiza → Analiza… → Klasy**: ręczne K albo Auto, maksimum 1–8,
jawne uzasadnienie i ranking bieżących danych. Jedna klatka, zakres lub
seria używa pełnego szkicu parametrów. Odmowa nie zastępuje wcześniejszego
kompletnego wyniku; istniejący katalog zachowuje decyzję Auto.
Kontrole: K1 dla jednej sieci, K2 dla dwóch orientacji, odmowa dla szumu
oraz słabych/pustych danych. TTMAPP 259 i 259–268: **nierozstrzygnięte**
według reguły zapisanej przed próbą, bez zastępowania ręcznym K5.
[Raport i test ręczny](interactive-v04/acceptance-12.md),
[reguła wyboru](interactive-v04/auto-class-count-rule.md).
Sprawdzenia: **476 testów PASS**, mypy 70 plików PASS, GUI X11 PASS;
Standards/Spec: 0 otwartych uwag; maks. zmieniony kod/test 302 linie.
Status `done`; **odbiór ręczny użytkownika 12 potwierdzony 2026-11-03 dla wersji `7edd8de` („testy manualne ok”)**.
Następny rekomendowany ticket: **13 — zapis i otwarcie projektu**.
Plan ma 26 ticketów; 23a pozostaje po 23. Poniżej historia wcześniejszych etapów.

**Dodano SD-V4-23a — 2026-11-03:**
[Scalaj i dziel klasy ręcznie](interactive-v04/23a-split-merge-classes.md),
po 23, z wyborem zakresu, podglądem i Cofnij/Ponów. 24 i 25 wymagają
23a i obejmą zapis/eksport nowych operacji. Plan ma 26 ticketów;
23a `ready-for-agent`, implementacji nie rozpoczęto. Główna kolejność
pozostaje bez zmian: następny 12, odbiór ręczny 11 jest potwierdzony.

**Wykonano SD-V4-11 — 2026-11-03 (`d18048b`):**
**Analiza → Analiza…** łączy zakres, klasy i akceptację, porządek oraz domeny.
Szkic pozostaje podczas nawigacji/porównania; **Analizuj** uruchamia jeden
kompletny przebieg dla klatki, zakresu lub serii. Pięć wcześniejszych
formularzy zastąpiono tym oknem. [Raport i test ręczny](interactive-v04/acceptance-11.md).
**456 testów PASS**, GUI X11/mypy PASS, Standards 0 / Spec 0;
status `done`, **odbiór ręczny użytkownika potwierdzony 2026-11-03 dla wersji `76c8284` („testy manualne 11 ok”)**.
Następny **12 — Auto**, nadal niewykonany. Plan ma **26 ticketów**.
Opisy menu starszych etapów poniżej zachowują historię interfejsu.

**Wykonano SD-V4-10 — 2026-11-03 (`aa7e039`):**
**Analiza → Test porządku…** — kwantyl, minima punktów, promień i sigma,
nowa kalibracja, zachowany katalog i porównanie poprzedni/nowy.
Zastosowane ustawienia przechodzą do ponownego odkrywania klas i serii.
[Raport, kontrole i ręczny test](interactive-v04/acceptance-10.md).
**449 testów PASS**, GUI X11 PASS, mypy 67 modułów PASS, maksimum 566 linii; Standards 0 / Spec 0.
**Odbiór ręczny użytkownika 10 potwierdzony 2026-11-03** dla wersji
`4b55727` („testy manualne ok”). Następny rekomendowany **11 → 12**.

**Wykonano SD-V4-09 — 2026-11-03 (`494ab9d`):**
**Analiza → Akceptacja klasy…**, progi marginesu i promienia, przeliczenie
z zachowanym katalogiem i porównanie wyników. Szczegóły molekuły rozdzielają
klasę, akceptację, porządek i domenę; K1 ma jawny brak marginesu.
[Raport i test ręczny](interactive-v04/acceptance-09.md).
427 testów PASS, mypy 63 moduły PASS, 15 plików kodu/testów do 544 linii;
rzeczywiste GUI PASS, oba przeglądy bez uwag. **Odbiór ręczny użytkownika
09 potwierdzony 2026-11-03** dla wersji `9dd934d` („testy manualne ok”).
Kolejny rekomendowany ticket pozostaje **12 — Auto**.

**Rozszerzenie planu — 2026-11-03:** dodano
[SD-V4-21–25 — ręczną edycję klas i domen](interactive-v04/README.md#edycja-ręczna-klas-i-domen).
21 tworzy i rozszerza domeny z Cofnij/Ponów, 22 dzieli/łączy, 23 dodaje
własne klasy, 24 zapisuje korekty i historię, 25 eksportuje poprawiony wynik.
Każdy etap jest osobno testowalny w aplikacji. Nowe zadania są
`ready-for-agent` po zależnościach; implementacji nie rozpoczęto.
Plan ma **24 tickety**. Następny rekomendowany pozostaje **12 — Auto**;
21 jest niezależnie dostępny po ukończonym 05a.

**Wykonano SD-V4-08 — 2026-11-03 (`1c39ae2`, poprawka `46c274f`):**
menu **Analiza → Analiza serii…**, wspólne klasy i ustawienia domen,
wynik każdej klatki, postęp/statusy i anulowanie zachowujące ukończone
wyniki. [Raport i test ręczny](interactive-v04/acceptance-08.md).
409 testów PASS, mypy 59 modułów PASS; rzeczywiste GUI sprawdzone także
na całych 268 klatkach TTMAPP. **Odbiór ręczny użytkownika 08 potwierdzony
2026-11-03** dla wersji `a3a5316` („testy manualne ok”).
Następny rekomendowany ticket **12 — Auto**.

**Wykonano SD-V4-07 — 2026-11-02 (`dedd8b8`, poprawki `65e9d2a`):**
**Analiza → Klasy i zakres…**, ręczne K1–8, zakres dopasowania i wspólny
katalog. Przelicza bieżącą klatkę; poprzednie wyniki zachowują własny katalog.
[Raport i test ręczny](interactive-v04/acceptance-07.md). 396 testów PASS,
mypy 54 moduły PASS, GUI X11 sprawdzone przez agenta.
**Ręczny odbiór użytkownika 07 potwierdzony 2026-11-02** dla wersji
`7f79362` („testy manualne ok”). Kolejny etap 08 opisano powyżej.

**Wykonano SD-V4-06 — 2026-11-02 (`98ca8ff`, poprawka `36aea1f`):**
parametry domen w menu **Analiza → Tworzenie domen…**, przeliczenie,
porównanie i przywracanie bazowych ustawień bez ponownego dopasowania klas.
[Raport i test ręczny](interactive-v04/acceptance-06.md). Odbiór ręczny
użytkownika potwierdzony 2026-11-02 dla wersji `a4dcace`
(„testy manualne ok”). Kolejny etap 07 opisano powyżej.

**Wykonano SD-V4-05a — 2026-11-02 (`dfcf392`):** wypełnienie, obrysy,
numery domen i krycie w menu **Obszary…**; centra i ramki można wyłączyć.
Dotychczasowe „Maski / obrysy” nazwano **Maski molekuł**, zgodnie ze źródłem
MolTrack. [Raport i test ręczny](interactive-v04/acceptance-05a.md).
Przypisania i metoda 05 są zachowane. Ręczny odbiór 05a potwierdzony przez
użytkownika 2026-11-02 dla wersji `617b006`.

**Wykonano SD-V4-05 — 2026-11-02 (`fb37431`):** **Analizuj klatkę · K5**
oblicza lokalne klasy i końcowe domeny z bieżącego obrazu MPP i oznaczeń
MolTrack, z kolorami, legendą, odmowami, postępem i anulowaniem.
[Uruchomienie, sprawdzenia i test ręczny](interactive-v04/acceptance-05.md).
Ręczny odbiór użytkownika 05 oczekuje. Aktualny plan ma 26 ticketów:
01–03, 05, 05a i 06–15 `done`,
16–18, 21–25 oraz 23a `ready-for-agent` po zależnościach, 19–20 `deferred`.

**Wcześniejsza zmiana kierunku — 2026-11-02:** na polecenie użytkownika wycofano
SD-V4-04 i import jego wyników. Stan aplikacji wrócił wtedy do odebranego 03,
z zachowaniem poprawek układu i wyjścia. **308 testów PASS**, mypy 27 plików
PASS. [Zmieniony plan](interactive-v04/README.md) prowadzi do własnych
obliczeń na wzór metody v0.4, bez ładowania zewnętrznych modeli/wyników.
Ręczne K i zakres dodaje 07, serię 08, Auto 12. Dawny 11 wchłonięto
w 05/07. Obliczenia jednej klatki wdrożono w 05, zgodnie z aktualizacją
powyżej. Poniżej historia poprzednich etapów.

**Wykonano SD-V4-03 — 2026-11-02:** miniatury, odtwarzanie bez pomijania
klatek, pauza/restart i gamma. [Uruchomienie i test ręczny](interactive-v04/acceptance-03.md).
300 testów PASS, mypy 27 plików PASS; pełne 268 klatek TTMAPP sprawdzone
w GUI. Ręczny odbiór 03 wraz z poprawką układu `0745e4e` potwierdzono;
późniejsza [poprawka wyjścia](interactive-v04/acceptance-03.md#poprawka-wyjścia-z-programu)
`3dd8b47` również odebrana ręcznie 2026-11-02. Historyczny odbiór całego
szkieletu pozostaje otwarty; aktualną kolejność nowego planu podano powyżej.

**Wykonano SD-V4-02 — 2026-11-02:** działają zapisane oznaczenia, maski,
metadane po kliknięciu i geometria raw/aligned. [Uruchomienie i test ręczny](interactive-v04/acceptance-02.md).
279 testów PASS; ręczny odbiór 02 potwierdzony przez użytkownika (`3572b6d`).
Miniatury, gamma i odtwarzanie dodano następnie w 03.

**Wykonano SD-V4-01 — 2026-11-02:** działa otwieranie zapisów MolTrack/MPP
i przeglądanie obrazów oryginalnych w PyQt6. [Uruchomienie, test ręczny i raport](interactive-v04/acceptance-01.md).
To pierwszy działający przekrój nowego planu; historyczne zadania poniżej
nadal obejmują szerszy zakres oznaczeń, geometrii i pełnego odbioru szkieletu.

**Rozszerzenie planu — 2026-11-02:** [SD-V4-16–20](interactive-v04/README.md#rozszerzenia)
obejmuje pomiary geometrii, tolerancje domen i próbę freud (`ready-for-agent`
po zależnościach) oraz późniejsze FFT/NMF i katalog typów (`deferred`).
Każdy ticket kończy się funkcją do ręcznego sprawdzenia w aplikacji.

**Nowy podział do uzgodnienia — 2026-11-02:**
[15 ticketów interaktywnego UI v0.4](interactive-v04/README.md), status
`draft`, rozpisuje uruchamialne funkcje z testem ręcznym po każdym zadaniu.
Indeks opisuje zależności i pokrycie historycznych zakresów poniżej.
Dotychczasowe tickety i ich statusy pozostają zachowane.

Specyfikacja: [przekazanie do implementacji](../issues/09-implementation-handoff.md).
Pierwsza mapa decyzji jest zakończona. **Poniższe historyczne zadania mają
status `todo`; ich zakres jest wdrażany przez nowy podział SD-V4.**
Aktualne wykonanie 01–03 i 05 opisano powyżej; nie oznacza ono odbioru całego szkieletu.

To zadania wykonawcze, poza rejestrem pytań `wayfinder`. Nie wybierają ponownie
metod ani zakresu. Obowiązują [import](../issues/01-import-and-geometry.md),
[podgląd C](../issues/07-browsing-and-comparison.md) i doprecyzowania przekazania.

| Zadanie | Zależności | Rezultat |
| --- | --- | --- |
| [Import, model serii i geometria](01-import-model.md) | Przyjęta specyfikacja | Zwalidowana seria i poprawny widok danych jednej klatki, bez Qt. |
| [Natywny podgląd i nawigacja](02-browsing-window.md) | Import, model serii i geometria | Działające otwieranie MolTrack i podgląd C w PyQt6. |
| [Odbiór szkieletu](03-acceptance.md) | Oba zadania implementacji | Sprawdzenia automatyczne, pełne dane, GUI i raport ograniczeń. |

Praca obejmuje `stmdomains/`, `tests/stmdomains/` i `docs/stmdomains/` na gałęzi
`domains/*`. Zmiany wspólne i konfiguracja główna trafiają do integratora,
zgodnie z [zasadami współpracy](../../PARALLEL_DEVELOPMENT.md). Każde zadanie
kończy się commitem i aktualizacją [przekazania](../handoff.md).

Statusy wykonawcze: `todo`, `in_progress`, `done`. Rozpoczynając zadanie,
przypisz prowadzącego i ustaw `in_progress`; `done` wymaga spełnienia jego
kryteriów. Nie przenoś wyników sprawdzeń prototypu HTML jako testów natywnej
aplikacji. Raport odbioru wskazuje konkretny commit, środowisko oraz dane.

Kolejność nie blokuje pracy nad niezależnymi testami lub fragmentem UI, ale
odbiór końcowy wymaga spójnego importu i podglądu na tej samej wersji kodu.
Po zakończeniu wszystkich trzech zadań oraz odbiorze przez użytkownika można
kontynuować zwykły tok [drugiej mapy](../map-methods-and-save.md).
Wcześniej rozstrzygnięte pytania o definicje/statystyki/zapis nadal obowiązują.

## Uruchomienie i środowisko

Do uruchamiania STM Domains, testów oraz prób używamy istniejącego środowiska
Conda **`netcat`**, zgodnie z [instrukcją aplikacji](../../../stmdomains/AGENTS.md).
Z katalogu głównego worktree, przy aktywnym `netcat`, sprawdź interpreter,
a następnie uruchom potrzebne polecenie:

```bash
python -c 'import sys; print(sys.executable); print(sys.prefix)'
python -m stmdomains.main
python -m pytest -q tests/stmdomains
```

Na tym komputerze zweryfikowano interpreter
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Można wywołać go bezpośrednio zamiast `python`, gdy powłoka nie aktywowała
środowiska albo `conda run -n netcat` nie działa w piaskownicy. Przy aktywacji
porównaj `CONDA_PREFIX` z `sys.prefix`; przy bezpośrednim wywołaniu sprawdź,
czy `sys.executable` i `sys.prefix` należą do wskazanego `netcat`.

Testy wymagające Qt na maszynie bez ekranu uruchamia się z
`QT_QPA_PLATFORM=offscreen`. Scenariusze pełnych danych i GUI mają być
uruchamiane jawnie i raportowane oddzielnie. Pusty zbiór testów nie jest sukcesem.
Minimalna ścieżka produkcyjna: PyQt6 + NumPy + SciPy + scikit-learn +
threadpoolctl. Dla testów: pytest, pytest-qt. Wszystkie te pakiety są
dostępne w istniejącym `netcat`. Środowisko, modele i dane nie trafiają do Git.

Główny `requirements/stm-apps.txt` obsługuje na razie puste okno. Potrzebę
uzupełnienia NumPy/SciPy, scikit-learn/threadpoolctl oraz właściwego zakresu
CI przekazuje się integratorowi.
Przed deklaracją instalacji z tego pliku trzeba sprawdzić jego aktualizację.
