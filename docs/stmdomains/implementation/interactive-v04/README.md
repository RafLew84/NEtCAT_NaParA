# Interaktywne STM Domains — obliczenia z danych

Gałąź implementacji: **`domains/interactive-v04-ui`**, utworzona z
`domains/start` na commicie `b21e0ca`. Worktree:
`/home/rlew/projekty/NEtCAT-domains`.

**Decyzja użytkownika — 2026-11-02:** całkowicie pomijamy wczytywanie
wyników i modeli v0.4. Dostarczony kod służy jako wzór metody, którą
implementujemy w aplikacji i następnie rozszerzamy. Użytkownik otwiera
obrazy z oznaczeniami, wybiera zakres i ustawienia, klika **Analizuj**.
Parametry klas powstają wewnętrznie z wybranych danych, bez pliku modelu.

Stan: **19 ticketów w aktualnym planie**. **01–03 są wykonane i odebrane
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
wycofano bez przepisywania historii Git. **11 usunięto jako dublujący**:
dopasowanie jednej klatki przejmują 05 (bazowe K5) i 07 (ręczne K i zakres).
Numerów 04/11 nie wykorzystujemy ponownie; pozostałe ID i ścieżki zachowano.
Historia usuniętych ticketów pozostaje w Git.

**Wykonano [05a — obszary i granice domen](05a-domain-regions.md)** (`dfcf392`),
dodany na polecenie użytkownika: wypełnienie, obrysy, numery i krycie
w menu **Obszary…**. [Raport i test ręczny](acceptance-05a.md).
Odbiór ręczny użytkownika oczekuje. Następny ticket: **06**.
01–03, 05 i 05a mają status `done`.
06–10 oraz 12–18 mają zakres `ready-for-agent`
z opisanymi zależnościami. 19–20 pozostają `deferred`, z jawnym warunkiem
wyboru. Przygotowany zakres nie oznacza ukończenia wymaganych zależności.

## Tickety i kolejność

Identyfikatory **SD-V4-01–20 oraz SD-V4-05a** odróżniają tę serię od dawnych ticketów
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
| [12 — Wybierz liczbę klas automatycznie](12-automatic-class-count.md) | SD-V4-07 | Wybierz Auto dla jednej klatki lub zakresu odkrywania i porównaj z ręcznym K. |
| [13 — Zapisz projekt i otwórz wynik bez ponownych obliczeń](13-save-open-project.md) | SD-V4-05 | Zapisz projekt i otwórz go bez plików źródłowych. |
| [14 — Wyeksportuj przypisania i widok do CSV oraz PNG](14-export-csv-png.md) | SD-V4-05 | Wyeksportuj obliczony wynik i porównaj CSV/PNG z widokiem. |
| [15 — Dostosuj opis otoczenia i bariery obrazu](15-advanced-descriptors-barriers.md) | SD-V4-07 | Zmień opis otoczenia/barier i sprawdź ich wpływ. |
| [16 — Zobacz kierunek, rozstaw i jakość geometrii na obrazie](16-inspect-local-geometry.md) | SD-V4-05 | Kliknij molekułę i zobacz jej pomiary oraz kierunek na obrazie. |
| [17 — Porównaj domeny tworzone według tolerancji geometrycznych](17-segment-geometric-tolerances.md) | SD-V4-06, SD-V4-16 | Zmień tolerancje kąta i rozstawu, porównaj domeny z metodą bazową. |
| [18 — Porównaj otoczenia molekuł metodą freud bez zadawania K](18-compare-freud-environments.md) | SD-V4-06, SD-V4-16 | Przelicz jedną klatkę metodą freud i obejrzyj końcowe przypisania. |
| [19 — Porównaj domeny z lokalnego FFT i NMF obrazu](19-compare-local-fft-nmf.md) | SD-V4-06, SD-V4-16; warunek wyboru | Zmień okno analizy obrazu i porównaj wynik na molekułach. |
| [20 — Zachowaj wspólny katalog typów struktury w serii](20-shared-structural-type-catalogue.md) | SD-V4-08, SD-V4-13, SD-V4-16; warunek wyboru | Sprawdź wspólne typy na kolejnych klatkach i po otwarciu zapisanego projektu. |

Po wykonanych 05 i 05a rekomendowana kolejność: **06 → 07 → 08 → 12**:
strojenie domen → ręczne K i zakres odkrywania
→ analiza serii → Auto. 12 można wykonać już po 07, jeśli Auto ma pierwszeństwo
przed analizą całej serii. Po 05 dostępne są niezależnie 06, 07, 10, 13,
14 i 16; po 07 także 08, 09, 12 i 15. 08 wymaga wspólnego dopasowania
z 07, a 14 eksportuje obliczenia z 05. Nie ma zależności od usuniętych 04/11.

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

## Rozszerzenia

Rozszerzenia wynikają z zaakceptowanej przez użytkownika rekomendacji:
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
Nie dodajemy nowych ręcznych etykiet treningowych; istniejące częściowe
referencje pozostają materiałem oceny, z ich rzeczywistym zakresem.

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

Nie zamykamy nadrzędnych ticketów. W szczególności wdrożenie
eksperymentalnej ścieżki v0.4 nie zamyka naukowego odbioru metody w 13
ani wyboru metody w 04. Szczegóły dotychczasowej implementacji:
[indeks](../README.md).
