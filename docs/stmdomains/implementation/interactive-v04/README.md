# Interaktywne STM Domains — obliczenia z danych

**Wykonano SD-V4-14 — eksport PNG i CSV (`a20e14b`, poprawka `361a7d0`).**
**Plik → Eksportuj PNG/CSV…**: wybrany wynik, klatka lub zakres, pełny obraz
albo widoczny wycinek, aktualne Klasy/Domeny, gamma i warstwy. CSV zachowuje
ID, przypisania, powody odmów i mianowniki; brak analizy pozostaje brakiem.
Eksport nie uruchamia obliczeń. Nowy katalog zawiera opis i metadane;
postęp/anulowanie oraz odmowa nadpisania chronią wcześniejsze pliki.
[Raport i test ręczny](acceptance-14.md), [format eksportu](export-format-v1.md).
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
[Raport i test ręczny](acceptance-13.md), [format 1](project-format-v1.md).
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
[Raport i test ręczny](acceptance-12.md),
[reguła wyboru](auto-class-count-rule.md).
Sprawdzenia: **476 testów PASS**, mypy 70 plików PASS, GUI X11 PASS;
Standards/Spec: 0 otwartych uwag; maks. zmieniony kod/test 302 linie.
Status `done`; **odbiór ręczny użytkownika 12 potwierdzony 2026-11-03 dla wersji `7edd8de` („testy manualne ok”)**.
Następny rekomendowany ticket: **13 — zapis i otwarcie projektu**.
Plan ma 26 ticketów; 23a pozostaje po 23. Poniżej historia wcześniejszych etapów.

Gałąź implementacji: **`domains/interactive-v04-ui`**, utworzona z
`domains/start` na commicie `b21e0ca`. Worktree:
`/home/rlew/projekty/NEtCAT-domains`.

**Decyzja użytkownika — 2026-11-02:** całkowicie pomijamy wczytywanie
wyników i modeli v0.4. Dostarczony kod służy jako wzór metody, którą
implementujemy w aplikacji i następnie rozszerzamy. Użytkownik otwiera
obrazy z oznaczeniami, wybiera zakres i ustawienia, klika **Analizuj**.
Parametry klas powstają wewnętrznie z wybranych danych, bez pliku modelu.

**Rozszerzenie planu — 2026-11-03:** dodano
[23a — scalanie i dzielenie klas](23a-split-merge-classes.md), po 23.
Zakres obejmuje jawny wybór klatek, podgląd i atomowe Cofnij/Ponów;
scalenie klas zachowuje osobne domeny. 24 i 25 uwzględniają zapis oraz
eksport tych operacji. Status `ready-for-agent`, bez implementacji.

**Wykonano SD-V4-11 — 2026-11-03 (`d18048b`):**
[Wspólne okno analizy](11-unified-analysis-window.md) zastępuje pięć osobnych
formularzy. **Analiza → Analiza…** ma zakładki **Zakres, Klasy, Porządek,
Domeny**. Przycisk przy obrazie otwiera to samo okno dla bieżącej klatki;
**Analizuj** stosuje cały szkic do klatki, zakresu lub serii, także akceptację.
Porównanie i nawigacja zachowują szkic. Jest jawne kopiowanie z wyniku,
bazowe parametry, stany klatek i anulowanie. [Raport i test ręczny](acceptance-11.md).
**456 testów PASS**, GUI X11/mypy PASS, Standards 0 / Spec 0.
Status `done`, **odbiór ręczny użytkownika potwierdzony 2026-11-03 dla wersji `76c8284` („testy manualne 11 ok”)**. Następny **12 — Auto**,
który pozostaje niewykonany i rozszerzy zakładkę Klasy.
Wpisy o menu w starszych etapach poniżej opisują ich historyczny interfejs.

Stan: **26 ticketów w aktualnym planie**. **01–03 są wykonane i odebrane
ręcznie**: [obrazy i suwak](acceptance-01.md), [oznaczenia i geometria](acceptance-02.md),
[miniatury, odtwarzanie i gamma](acceptance-03.md), wraz z poprawkami układu
`0745e4e` i wyjścia `3dd8b47`. **05 jest zaimplementowany (`fb37431`, `done`),
odbiór ręczny użytkownika oczekuje**: [uruchomienie, sprawdzenia i test ręczny](acceptance-05.md).
**Analizuj klatkę · K5** oblicza lokalne klasy i końcowe domeny z MPP
i oznaczeń MolTrack, pokazując kolory, legendę, liczniki i przyczyny odmów.
Obliczenia mają postęp i anulowanie; nie wymagają importu modelu.
Przed 05 kod i testy przywrócono do stanu `24625f2`: po wycofaniu 04
**308 testów PASS**. To wynik historycznego rollbacku.

**04 usunięto z planu**, a jego implementację `b6159ac` i `c13b291`
wycofano bez przepisywania historii Git. **Dawny 11 usunięto jako dublujący**:
dopasowanie jednej klatki przejmują 05 (bazowe K5) i 07 (ręczne K i zakres).
Numer 04 pozostaje wycofany. Na wyraźną prośbę użytkownika z 2026-11-03
numer 11 otrzymuje nowy zakres wspólnego okna; nie przywraca dawnego zadania.
Pozostałe ID i ścieżki zachowano. Historia usuniętych ticketów pozostaje w Git.

**Wykonano [05a — obszary i granice domen](05a-domain-regions.md)** (`dfcf392`),
dodany na polecenie użytkownika: wypełnienie, obrysy, numery i krycie
w menu **Obszary…**. [Raport i test ręczny](acceptance-05a.md).
Odbiór ręczny 05a potwierdzony przez użytkownika 2026-11-02 dla `617b006`.

**Wykonano [06 — strojenie i porównanie domen](06-tune-domain-formation.md)**
(`98ca8ff`, poprawka `36aea1f`): menu **Analiza → Tworzenie domen…**,
sześć parametrów, jawne przeliczenie, porównanie poprzedni/nowy i przywracanie
bazowych ustawień przy zachowanych klasach. [Raport i test ręczny](acceptance-06.md).
Odbiór ręczny użytkownika 06 potwierdzony 2026-11-02 dla wersji `a4dcace`
(„testy manualne ok”).

**Wykonano [07 — liczba klas i zakres](07-fit-shared-classes.md)**
(`dedd8b8`, poprawki `65e9d2a`): **Analiza → Klasy i zakres…**, ręczne K1–8,
bieżąca klatka / wybrany zakres / cała seria, wspólny katalog i powrót do
wcześniejszego wyniku z jego katalogiem. Nowe domeny powstają na bieżącej
klatce; pozostałe mają jawny status wcześniejszego katalogu albo braku analizy.
[Raport i test ręczny](acceptance-07.md). 396 testów PASS, mypy PASS,
GUI X11 sprawdzone przez agenta; **odbiór ręczny użytkownika 07 potwierdzony
2026-11-02** dla wersji `7f79362` („testy manualne ok”).

**Wykonano [08 — analiza zakresu/serii](08-analyze-series.md)** — 2026-11-03,
`1c39ae2`, poprawka `46c274f`: menu **Analiza → Analiza serii…** łączy
zakres, źródło wspólnych klas i parametry domen w jednym uruchomieniu.
Każda klatka dostaje wynik/status; można nawigować i anulować z zachowaniem
ukończonych wyników. [Raport i test ręczny](acceptance-08.md).
409 testów PASS, mypy PASS, 268 klatek TTMAPP przeliczonych w rzeczywistym GUI.
**Odbiór ręczny użytkownika 08 potwierdzony 2026-11-03** dla wersji
`a3a5316` („testy manualne ok”). **Następny rekomendowany ticket: 12.**

**Wykonano [09 — akceptacja klasy](09-tune-class-acceptance.md)** — 2026-11-03,
`494ab9d`: menu **Analiza → Akceptacja klasy…**, margines i mnożnik promienia,
przeliczenie przy zachowanym katalogu, porównanie i wartości bazowe.
**Dane oznaczenia…** rozdzielają klasę wstępną, akceptację, porządek i domenę.
K1 ma nieaktywny margines. [Raport i test ręczny](acceptance-09.md).
427 testów PASS, mypy 63 moduły PASS, kod/testy do 544 linii;
GUI X11 sprawdzone, Standards/Spec bez uwag. **Odbiór ręczny użytkownika 09
potwierdzony 2026-11-03** dla wersji `9dd934d` („testy manualne ok”).

**Wykonano [10 — test porządku](10-tune-order-test.md)** — 2026-11-03,
`aa7e039`: **Analiza → Test porządku…**, kwantyl kontroli, minima wsparcia,
promień i sigma, kalibracja dla bieżącego otoczenia, zachowane klasy,
porównanie i anulowanie. Jawne odkrywanie klas i analiza serii używają
zastosowanych parametrów wyświetlanego wyniku; przy jego braku bazowych.
[Raport, gotowe przykłady i test ręczny](acceptance-10.md). **449 testów PASS**, GUI X11 PASS,
mypy 67 modułów PASS, maksimum 566 linii; Standards 0 / Spec 0.
**Ręczny odbiór użytkownika 10 potwierdzony 2026-11-03** dla wersji
`4b55727` („testy manualne ok”). Później wykonano 11–14; obecnie następny **15**.

01–03, 05, 05a i 06–14 mają status `done`.
15–18, 21–25 oraz 23a mają zakres `ready-for-agent`
z opisanymi zależnościami. 19–20 pozostają `deferred`, z jawnym warunkiem
wyboru. Przygotowany zakres nie oznacza ukończenia wymaganych zależności.

**Rozszerzenie na polecenie użytkownika — 2026-11-03:** dodano
**21–25 — ręczną edycję domen i klas, zapis historii oraz eksport korekt**.
Zakres i kolejność opisuje [edycja ręczna](#edycja-ręczna-klas-i-domen).
To plan przyszłych funkcji; implementacji nie rozpoczęto. Następny
rekomendowany etap głównej ścieżki to teraz **15 — opis otoczenia i bariery obrazu**; 21 można
wybrać niezależnie już po wykonanym 05a.

## Tickety i kolejność

Identyfikatory **SD-V4-01–25, SD-V4-05a oraz SD-V4-23a** odróżniają tę serię od dawnych ticketów
badawczych 01–26 i implementacyjnych SD-IMPL. Każdy plik zawiera zakres,
zależności, kryteria akceptacji i instrukcję testu ręcznego.

| Ticket | Wymagane wcześniej | Co można sprawdzić w uruchomionej aplikacji |
| --- | --- | --- |
| [01 — Otwórz zapis i przeglądaj obrazy](01-open-images.md) | brak | Otwórz MPP z zapisem MolTrack i przejdź po klatkach. |
| [02 — Pokaż molekuły i poprawną geometrię obrazu](02-molecules-and-geometry.md) | SD-V4-01 | Włącz oznaczenia i sprawdź, czy leżą na molekułach. |
| [03 — Przeglądaj serię przez miniatury i odtwarzanie](03-filmstrip-and-playback.md) | SD-V4-01 | Wybierz miniaturę, odtwórz serię i zatrzymaj. |
| [05 — Oblicz klasy i domeny bieżącej klatki z danych](05-analyze-current-frame.md) | SD-V4-02 | Kliknij Analizuj klatkę; klasy K5 i domeny powstają z jej danych, bez pliku modelu. |
| [05a — Obszary i granice domen](05a-domain-regions.md) | SD-V4-05 | Wyłącz centra i oglądaj wypełnienie, obrysy i numery domen; reguluj krycie. |
| [06 — Strojenie tworzenia domen i porównanie wyniku](06-tune-domain-formation.md) | SD-V4-05 | Zmień progi domen i porównaj poprzedni/nowy wynik. |
| [07 — Wybierz liczbę klas i zakres ich odkrywania](07-fit-shared-classes.md) | SD-V4-05 | Wpisz K1–8, wybierz jedną klatkę lub wspólny zakres i obejrzyj nowy wynik. |
| [08 — Przelicz zakres lub całą serię](08-analyze-series.md) | SD-V4-07 | Dopasuj wspólne klasy i przelicz zakres; przeglądaj wyniki i anuluj pozostałe. |
| [09 — Reguluj akceptację klasy i zobacz przyczynę odmowy](09-tune-class-acceptance.md) | SD-V4-07 | Zmień progi akceptacji i sprawdź powody odmowy, także dla K1. |
| [10 — Reguluj test porządku z prawidłową kalibracją](10-tune-order-test.md) | SD-V4-05 | Zmień test porządku i obejrzyj wynik po kalibracji. |
| [11 — Ustaw i uruchom pełną analizę w jednym oknie](11-unified-analysis-window.md) | SD-V4-06, SD-V4-08, SD-V4-09, SD-V4-10 | Ustaw zakres, klasy, akceptację, porządek i domeny; jednym przyciskiem przelicz klatkę lub serię. |
| [12 — Wybierz liczbę klas automatycznie](12-automatic-class-count.md) | SD-V4-07, SD-V4-11 | Wybierz Auto we wspólnym oknie analizy i porównaj z ręcznym K dla klatki oraz serii. |
| [13 — Zapisz projekt i otwórz wynik bez ponownych obliczeń](13-save-open-project.md) | SD-V4-05 | Zapisz projekt i otwórz go bez plików źródłowych. |
| [14 — Wyeksportuj przypisania i widok do CSV oraz PNG](14-export-csv-png.md) | SD-V4-05 | Wyeksportuj obliczony wynik i porównaj CSV/PNG z widokiem. |
| [15 — Dostosuj opis otoczenia i bariery obrazu](15-advanced-descriptors-barriers.md) | SD-V4-07 | Zmień opis otoczenia/barier i sprawdź ich wpływ. |
| [16 — Zobacz kierunek, rozstaw i jakość geometrii na obrazie](16-inspect-local-geometry.md) | SD-V4-05 | Kliknij molekułę i zobacz jej pomiary oraz kierunek na obrazie. |
| [17 — Porównaj domeny tworzone według tolerancji geometrycznych](17-segment-geometric-tolerances.md) | SD-V4-06, SD-V4-16 | Zmień tolerancje kąta i rozstawu, porównaj domeny z metodą bazową. |
| [18 — Porównaj otoczenia molekuł metodą freud bez zadawania K](18-compare-freud-environments.md) | SD-V4-06, SD-V4-16 | Przelicz jedną klatkę metodą freud i obejrzyj końcowe przypisania. |
| [19 — Porównaj domeny z lokalnego FFT i NMF obrazu](19-compare-local-fft-nmf.md) | SD-V4-06, SD-V4-16; warunek wyboru | Zmień okno analizy obrazu i porównaj wynik na molekułach. |
| [20 — Zachowaj wspólny katalog typów struktury w serii](20-shared-structural-type-catalogue.md) | SD-V4-08, SD-V4-13, SD-V4-16; warunek wyboru | Sprawdź wspólne typy na kolejnych klatkach i po otwarciu zapisanego projektu. |
| [21 — Twórz domeny ręcznie i zmieniaj ich skład](21-manual-domain-membership.md) | SD-V4-05a | Zaznacz molekuły, utwórz/rozszerz domenę, usuń członka i cofnij zmianę. |
| [22 — Dziel i łącz domeny na obrazie](22-split-merge-domains.md) | SD-V4-21 | Wydziel część domeny lub połącz sąsiadujące domeny; porównaj i cofnij. |
| [23 — Twórz klasy ręcznie i poprawiaj ich przypisania](23-manual-classes.md) | SD-V4-07, SD-V4-22 | Dodaj własną klasę, nazwę/kolor oraz przypisz molekuły lub domeny. |
| [23a — Scalaj i dziel klasy ręcznie](23a-split-merge-classes.md) | SD-V4-23 | Scal klasy lub wydziel wskazanych członków w jawnym zakresie; sprawdź podgląd i Cofnij/Ponów. |
| [24 — Zapisz korekty i wznów ręczną edycję projektu](24-save-manual-corrections.md) | SD-V4-13, SD-V4-23a | Otwórz zapisane korekty bez źródeł i kontynuuj Cofnij/Ponów. |
| [25 — Eksportuj poprawione klasy i domeny do CSV oraz PNG](25-export-manual-corrections.md) | SD-V4-14, SD-V4-23a | Porównaj CSV/PNG po korektach z obrazem oraz bazowym automatem. |

Po wykonanych 05, 05a i 06–14 następny rekomendowany ticket to
**15 — opis otoczenia i bariery obrazu**. Odbiór użytkownika 13 jest potwierdzony;
Odbiór użytkownika 14 potwierdzono dla `4e9f1d9`. 13/14 wykonano po 05;
16 jest niezależnie dostępny po 05, a 15 po 07. 08 korzysta
z dopasowania z 07, a 14 eksportuje obliczenia z 05. Nie ma zależności
od usuniętego 04 ani historycznego, wchłoniętego zakresu 11.

Rozszerzenia można zacząć od **16 po 05**, bez czekania na wszystkie 01–15.
Po 06 i 16 dostępne są niezależne 17 oraz 18. Jako pierwszą próbę nowej
biblioteki wybieramy 18; 19 pozostaje dalszym wariantem po jej ocenie,
jeśli wskażemy informację, którą może wnieść obraz. 20 czeka na stabilny
opis struktur oraz analizę serii i zapis projektu. Numeracja nie wymusza
ukończenia wszystkich wcześniejszych numerów.

Nie tworzymy osobnych etapów „sam backend” lub „sam refaktor”. Potrzebne
wydzielenie operacji metody na wzór v0.4 należy do pierwszego ticketu,
który z nich korzysta. Aplikacja nie uruchamia zewnętrznych skryptów paczki.
Każdy ukończony ticket pozostawia uruchamialny program i zachowuje wcześniejsze
funkcje. Wykonawca wybiera ticket o uzgodnionym zakresie, którego wszystkie
zależności są ukończone. `ready-for-agent` oznacza przygotowany zakres,
a nie ukończenie zależności. `deferred` oznacza zachowany dalszy pomysł;
warunek jego wyboru jest opisany w pliku. `in_progress` i `done` opisują
wykonanie, przy czym odbiór programu i pozytywny wynik eksperymentu są odrębne.

## Edycja ręczna klas i domen

Użytkownik zlecił dodanie tego zakresu **2026-11-03**, po ręcznym odbiorze 08.
Każdy z sześciu ticketów kończy się działającą funkcją z testem w GUI.
Rekomendowana kolejność w tej ścieżce: **21 → 22 → 23 → 23a → 24 → 25**.
Przed 24 potrzebny jest **13 — zapis projektu**, przed 25 **14 — eksport**;
można je wykonać wcześniej niezależnie. 24 i 25 wymagają teraz 23a,
aby zachować także scalenia/podziały klas. 25 nie jest blokowany przez 24.
07 i 05a są ukończone. Nie trzeba czekać na Auto, pomiary ani odłożony 20.

Wspólny zakres i zasady:

- Edytujemy członkostwo istniejących oznaczeń MolTrack: kliknięcia/lasso,
  nowa domena, dodawanie i usuwanie członków, podział/scalenie domen
  oraz klas (23a).
  Po zmianie aktualizują się obszary, obrysy, kolory i liczniki. Nie jest to
  dorysowywanie molekuł ani swobodne malowanie granicy pikselowej.
- Ręczna praca jest możliwa także bez analizy lub przy zerowej detekcji
  domen. Brak modelu i bazowego wyniku pozostaje jawny; ręczne wskazania
  nie uzyskują fikcyjnych wyników testu porządku ani ufności modelu.
- Klasa grupuje wskazania; kilka osobnych domen może mieć tę samą klasę.
  Przypisanie klasy nieprzypisanej molekule nie tworzy samo domeny.
  Zmiana klasy części domeny wymaga jawnego podziału z 22, realizowanego
  razem ze zmianą przypisania w 23. Klasa ręczna nie jest typem struktury
  zwalidowanym w 20 ani dodatkowym klastrem dopasowanego modelu.
  Scalenie klas z 23a zachowuje osobne ID i geometrię domen. Podział klasy
  obejmujący część domeny pokazuje również jej podział w podglądzie.
- Korekty odnoszą się do konkretnego źródła, wyniku, klatki i ID oznaczeń.
  Wynik automatyczny pozostaje dostępny, a poprawiony ma własną rewizję.
  Nowa analiza nie dziedziczy korekt po numerach domen i nie nadpisuje
  poprawionej pracy. Edycja nie zwiększa liczników oryginalnego przebiegu 08.
- Cofnij/Ponów działa od 21. Historia wybranego poprawionego wyniku zachowuje
  kolejność operacji także między klatkami; UI wskazuje, którą klatkę lub
  wspólną listę klas zmieni cofnięcie. Dzięki temu nie usuwa się klasy użytej
  w późniejszej, jeszcze niecofniętej operacji. Zapis i odtworzenie historii
  po ponownym uruchomieniu należą do 24.
- Do wykonania 24/25 zapis/eksport z 13/14 nie może sugerować zachowania
  korekt, których jeszcze nie obsługuje. UI jawnie wskazuje ograniczenie;
  ewentualny zapis samego bazowego automatu wymaga świadomego wyboru.
  Po 24/25 późniejsze prace nad zapisem i eksportem muszą zachować obsługę
  korekt. Zamknięcie programu nie może bez ostrzeżenia utracić edycji.
- Ręczna korekta nie trenuje modelu ani nie przenosi przypisań automatycznie
  na inne klatki. W 23a użytkownik może jawnie objąć operacją wiele klatek
  korzystających z tej samej listy klas; zakres i zmiany widzi w podglądzie.
  Nowa klasa, jej członkowie i pochodzenie są zapisywane oddzielnie od
  niezmienionego dopasowania. Uczenie z przykładów wymaga przyszłego
  osobnego zlecenia; nie jest częścią ticketów 21–25 ani 23a.

Zakres rozszerza wcześniejszy, ograniczony wybór jednej z propozycji przy
konflikcie domen. Historyczne kontrakty zachowujemy jako zapis tamtych
decyzji; dla nowych operacji obowiązują 21–25 oraz 23a. Nie oznacza to odbioru
naukowego metody ani uznania ręcznych korekt za niezależną referencję.

## Rozszerzenia

Rozszerzenia metod w 16–20 wynikają z zaakceptowanej przez użytkownika rekomendacji:
najpierw czytelne pomiary geometrii i możliwość strojenia, potem ograniczona
próba porównania otoczeń. FFT/NMF oraz trwały katalog typów są dalszymi
krokami. Dla pierwszych prób wystarczą obecne obrazy i oznaczenia TTMAPP.

**Co jest nowe:** 16 pokazuje pomiary w aplikacji; 17 wprowadza jeden
alternatywny sposób tworzenia domen według tolerancji o czytelnych jednostkach;
18 sprawdza konkretnie EnvironmentCluster; 19 sprawdza jeden przebieg FFT/NMF;
20 nadaje stabilne znaczenie typom w serii i zapisuje katalog w projekcie.
Nie wystarczy dopisać kontrolki bez wpływu na obliczenia albo dostarczyć
raport bez wyniku widocznego w aplikacji.

**Co już istnieje:** v0.4 ma koherencję Fouriera i kontrolę podobieństwa
całego regionu. Geometrię, dopasowanie sieci i lokalną fazę badano wcześniej.
Każda próba opisuje różnicę względem tych punktów odniesienia;
zmiana biblioteki sama nie dowodzi poprawy. Zobacz
[przegląd v0.4](../../new-code-v04-review.md),
[próbę fazy](../../phase-boundaries-trial.md) i
[syntezę badań](../../research-after-training-pilot.md).

**Wspólny sprawdzian:** jedna sieć, dwie orientacje, granica przesunięcia
przy jednakowym kącie i rozstawie, brakujące centra, rzeczywista przerwa,
szum oraz rzędy bez potwierdzonej sieci 2D. Dla 17 dochodzi stopniowa zmiana
orientacji, sprawdzająca zgodność całego regionu. Wykonawca dostarcza małe
przykłady do otwarcia w tym samym UI, z opisanym oczekiwanym wynikiem.
Na TTMAPP punktem porównania są klatki 259–266 przy identycznych wejściach.
W próbach metod 16–20 nie dodajemy nowych ręcznych etykiet treningowych;
istniejące częściowe referencje pozostają materiałem oceny, z ich
rzeczywistym zakresem.

**Ocena próby:** przed oceną zapisać ograniczony zestaw ustawień, zakres
dopasowania i warunki odtwarzania. Raportować błędne scalenia, rozdrobnienie,
granice oraz odmowy, a udział przypisań osobno. Metryki granic mają znaczenie
tam, gdzie jest odpowiednia referencja; ocena wzrokowa nie staje się accuracy.
Negatywna ocena metody może zakończyć poprawnie wykonany ticket eksperymentalny,
lecz nie uprawnia do przyjęcia detektora. Porażka granicy przesunięcia pozostaje
porażką; nie znika przez nazwanie dwóch obszarów jedną klasą.

**Znaczenie wyniku:** typ struktury jest niezależny od obrotu; orientacja
i konkretna domena są osobnymi informacjami. Jeden kierunek periodyczności
nie potwierdza sieci 2D. Dla nowych metod wymagane są końcowe przypisania
na rzeczywistych molekułach, szare odmowy i możliwość powrotu do bazowej
metody aplikacji przy porównywalnym wejściu. „Metoda bazowa” oznacza
obliczenia wdrożone w 05 na wzór v0.4, z klasami dopasowanymi z danych.
Nie oznacza importu starego modelu lub gotowych przypisań.
Pomiary i diagnostyka są opcjonalne, żeby zachować prosty widok podstawowy.

Gwyddion może pomagać w kontrolnym pomiarze kilku fragmentów, bez osobnego
ticketu integracyjnego. PyGPA, integracje Atomap/OVITO, symulacje ASE/GPAW
i kolejne treningi rVAE pozostają poza tym rozszerzeniem planu.
Dokumentacja kandydatów:
[freud — porównanie otoczeń](https://freud.readthedocs.io/en/stable/modules/environment.html),
[AtomAI — lokalne FFT/NMF](https://atomai.readthedocs.io/en/latest/multivar.html),
[Gwyddion — pomiar sieci](https://gwyddion.net/documentation/user-guide-en/feature-measurement.html).

## Wspólne kryteria odbioru

- **Uruchamialna aplikacja:** te same drzwi wejściowe do STM Domains
  (`python -m stmdomains.main` w środowisku **`netcat`**, używanym także
  do testów i prób zgodnie z [instrukcją uruchomienia](../README.md#uruchomienie-i-środowisko)).
  Przekazanie ticketu podaje dokładną komendę, potrzebne dane, kroki w UI
  i oczekiwany rezultat; użytkownik nie musi sam tworzyć plików testowych.
- **Ręczny test każdego ticketu:** instrukcja z jego pliku jest częścią
  odbioru. Wykonawca dostarcza małe, niesprzeczne przykłady potrzebne
  do przypadków jednej klatki, błędu, braku danych i kontroli syntetycznych.
  Oddziela faktycznie wykonany test w GUI od testów automatycznych,
  sprawdzeń bez ekranu i sprawdzeń pozostających do wykonania przez użytkownika.
- **Rozmiar kodu:** obowiązuje [instrukcja aplikacji](../../../../stmdomains/AGENTS.md):
  cel do **1000 fizycznych linii na plik**, twardy limit **1500**, również
  dla testów, z komentarzami i pustymi liniami. Zakres 1001–1500 wymaga
  uzasadnienia w przekazaniu. Ticket 01 wprowadza lokalną kontrolę,
  a każde zadanie raportuje długości nowego i zmienionego kodu.
  Odpowiedzialności dzielimy na moduły; nie skracamy formatowania dla limitu.
- **Testy odpowiadają zachowaniu:** małe testy syntetyczne i integracyjne
  sprawdzają geometrię, import, przetwarzanie, zależności ustawień lub zapis,
  zgodnie ze zmianą. Przynajmniej wymagany w tickecie przypadek na rzeczywistym
  TTMAPP ma oddzielny wynik. Brak danych lub pominięty test nie oznacza PASS.
- **Responsywność i spójność:** długie operacje mają postęp i anulowanie.
  Obraz, oznaczenia, wynik oraz zakres należą do tej samej klatki i wersji
  danych. Spóźniony wynik nie podmienia nowej pracy. Zmiana suwaka nie
  przemalowuje starego wyniku przed ponownym obliczeniem.
- **Pochodzenie wyniku:** wynik zachowuje faktycznie użyte parametry,
  źródło, zakres i model. Nowe dopasowanie nie przemianowuje starych klas.
  Pliki źródłowe oraz wcześniejsze własne wyniki pozostają bez nadpisywania.
- **Samodzielne obliczenia:** aplikacja oblicza cechy, klasy i domeny z wejścia.
  Próbę odbioru wykonuje się także bez dostępu do dostarczonych paczek i ich
  modeli/wyników. Zapisane własne projekty z 13 są osobną funkcją; nie są
  warunkiem rozpoczęcia analizy. Modele robocze są szczegółem obliczeń,
  a podstawowy przepływ nie wymaga szukania ani ładowania pliku modelu.
- **Czytelny widok:** podstawą są rzeczywiste molekuły na obrazie,
  kolor konkretnej domeny i szare nieprzypisane oznaczenia. 05a dodaje
  niezależnie wypełnienie, obrysy i numery końcowych obszarów. Klasa,
  domena, brak analizy i wynik z zerem domen są rozróżnione. Diagnostyka
  jest dostępna osobno; kolor domeny nie oznacza śledzenia jej w czasie.
- **Zamknięcie zadania:** przekazanie zawiera uruchomienie, wynik sprawdzeń,
  ograniczenia i długości kodu. Zmiany są wersjonowane w Git. Dane pomiarowe,
  modele, środowiska i duże wyniki pozostają lokalne.

## Założenia i punkty odniesienia

Plan realizuje [ocenę wykonalności](../../v04-interactive-ui-feasibility.md)
oraz [wymagania przeglądarki](../../trial-result-browser.md).
Punktem odniesienia jest [przegląd v0.4](../../new-code-v04-review.md).

- Wejście to istniejące obrazy MPP i oznaczenia MolTrack. Te zadania
  nie tworzą nowego detektora molekuł ani importera STP.
- K oznacza liczbę roboczych klas opisu, nie liczbę domen. Wspólny model
  serii i niezależne odkrywanie klas jednej klatki to dwa jawne tryby.
- Auto wybiera liczbę klas w ograniczonym zakresie; potrzebuje obsługi
  jednej klasy i niewystarczających danych. Nie gwarantuje liczby faz fizycznych.
- Najpierw implementujemy metodę wzorowaną na kodzie v0.4 i obliczamy nowy
  wynik, potem umożliwiamy eksperymenty z jej parametrami i rozszerzeniami.
  Nowe dopasowanie nie musi odtwarzać historycznych etykiet lub liczników.
  Metoda v0.4 dopuszcza jeden kierunek periodyczności.
  Wzrost liczby przypisań nie stanowi sam w sobie walidacji domen 2D.
- Nie przenosimy skryptów paczki w postaci jednego dużego pliku GUI.
  Ustawienia mają trafiać do wykonywanych obliczeń, bez ukrytych
  zależności od pierwszych dziesięciu klatek lub katalogu agenta.

Lokalne dane do odbioru:

- MPP: `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`.
- Oznaczenia: `data/TTMAPP/detection_full.moltrack.json`.

Materiały dla implementatora: archiwa w `data/new_code/` i rozpakowane kopie
w `.scratch/new-code-v04-review/`, opisane w przeglądzie v0.4. Służą analizie
kodu metody; aplikacja nie wymaga ich podczas uruchomienia. Dane, modele
i lokalne artefakty z wcześniejszych prób pozostają na dysku bez zmian.

Odbiór odróżnia klatkę jeszcze nieanalizowaną, poprawnie obliczone zero domen
i niemożliwe dopasowanie. Nie przejmujemy listy 56 klatek ani zer z dawnego
eksportu jako własnego wyniku. Przypadki importu obejmują brak masek i oznaczeń.

## Relacja do wcześniejszej mapy

Dotychczasowe tickety i ich statusy pozostają zachowane. Ten podział
opisuje nowe przekroje prac, a nie deklarację ukończenia starych zadań.

| Wcześniejszy zakres | Pokrycie w nowym planie |
| --- | --- |
| SD-IMPL-01 — import | 01–02: otwarcie i geometria danych |
| SD-IMPL-02 — przeglądanie | 01–03: obraz, oznaczenia, miniatury i odtwarzanie |
| SD-IMPL-03 — odbiór szkieletu | Sprawdzenia 01–03; całościowy odbiór wymaga osobnego potwierdzenia |
| Kontrakt 08 — projekt i eksport | 13: samowystarczalny projekt; 14: CSV/PNG |
| Nowy zakres ręcznych korekt — 2026-11-03 | 21–23: edycja z Cofnij/Ponów; 24: trwałość; 25: CSV/PNG po korektach |

Nie zamykamy nadrzędnych ticketów. W szczególności wdrożenie
eksperymentalnej ścieżki v0.4 nie zamyka naukowego odbioru metody w 13
ani wyboru metody w 04. Szczegóły dotychczasowej implementacji:
[indeks](../README.md).
