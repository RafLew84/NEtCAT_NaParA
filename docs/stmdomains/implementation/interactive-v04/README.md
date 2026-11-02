# Interaktywne STM Domains na bazie v0.4

Gałąź implementacji: **`domains/interactive-v04-ui`**, utworzona z
`domains/start` na commicie `b21e0ca`. Worktree:
`/home/rlew/projekty/NEtCAT-domains`.

Stan: **20 osobnych ticketów**, 2026-11-02. **01 wykonano (`done`)**:
działa otwieranie MolTrack/MPP, podgląd oryginałów i nawigacja;
[uruchomienie i raport odbioru](acceptance-01.md). 02–15 zachowują
status `draft`. Na polecenie użytkownika dodano omówione rozszerzenia:
16–18 mają status `ready-for-agent` i wymagają ukończenia zależności,
a dalsze 19–20 status `deferred` z jawnym warunkiem wyboru.
Pozostałe funkcje są planem implementacji. Oznaczenia molekuł, wyrównanie
i analiza nie są częścią ukończonego 01; ręczny odbiór przez użytkownika
jest opisany osobno od wykonanych testów technicznych.

## Tickety i kolejność

Identyfikatory **SD-V4-01–20** odróżniają tę serię od dawnych ticketów
badawczych 01–26 i implementacyjnych SD-IMPL. Każdy plik zawiera zakres,
zależności, kryteria akceptacji i instrukcję testu ręcznego.

| Ticket | Wymagane wcześniej | Co można sprawdzić w uruchomionej aplikacji |
| --- | --- | --- |
| [01 — Otwórz zapis i przeglądaj obrazy](01-open-images.md) | brak | Otwórz MPP z zapisem MolTrack i przejdź po klatkach. |
| [02 — Pokaż molekuły i poprawną geometrię obrazu](02-molecules-and-geometry.md) | SD-V4-01 | Włącz oznaczenia i sprawdź, czy leżą na molekułach. |
| [03 — Przeglądaj serię przez miniatury i odtwarzanie](03-filmstrip-and-playback.md) | SD-V4-01 | Wybierz miniaturę, odtwórz serię i zatrzymaj. |
| [04 — Otwórz wynik v0.4 i zobacz przynależność molekuł](04-open-v04-results.md) | SD-V4-02 | Otwórz zapisany wynik i przełącz kolory klas/domen. |
| [05 — Oblicz domeny na bieżącej klatce](05-analyze-current-frame.md) | SD-V4-04 | Kliknij Analizuj klatkę i obejrzyj nowy wynik. |
| [06 — Strojenie tworzenia domen i porównanie wyniku](06-tune-domain-formation.md) | SD-V4-05 | Zmień progi domen i porównaj poprzedni/nowy wynik. |
| [07 — Odkryj wspólne klasy z ręcznie podanym K](07-fit-shared-classes.md) | SD-V4-05 | Wybierz zakres, wpisz K i odkryj wspólne klasy. |
| [08 — Przelicz zakres lub całą serię](08-analyze-series.md) | SD-V4-05 | Przelicz zakres, przeglądaj wyniki, anuluj pozostałe. |
| [09 — Reguluj akceptację klasy i zobacz przyczynę odmowy](09-tune-class-acceptance.md) | SD-V4-05 | Zmień progi akceptacji i sprawdź powody odmowy. |
| [10 — Reguluj test porządku z prawidłową kalibracją](10-tune-order-test.md) | SD-V4-05 | Zmień test porządku i obejrzyj wynik po kalibracji. |
| [11 — Odkryj klasy wyłącznie na jednej klatce](11-fit-single-frame.md) | SD-V4-07 | Dopasuj klasy wyłącznie na wybranej klatce. |
| [12 — Wybierz liczbę klas automatycznie](12-automatic-class-count.md) | SD-V4-11 | Wybierz Auto i porównaj z ręcznie zadanym K. |
| [13 — Zapisz projekt i otwórz wynik bez ponownych obliczeń](13-save-open-project.md) | SD-V4-05 | Zapisz projekt i otwórz go bez plików źródłowych. |
| [14 — Wyeksportuj przypisania i widok do CSV oraz PNG](14-export-csv-png.md) | SD-V4-04 | Otwórz CSV i PNG poza aplikacją i porównaj z widokiem. |
| [15 — Dostosuj opis otoczenia i bariery obrazu](15-advanced-descriptors-barriers.md) | SD-V4-07 | Zmień opis otoczenia/barier i sprawdź ich wpływ. |
| [16 — Zobacz kierunek, rozstaw i jakość geometrii na obrazie](16-inspect-local-geometry.md) | SD-V4-05 | Kliknij molekułę i zobacz jej pomiary oraz kierunek na obrazie. |
| [17 — Porównaj domeny tworzone według tolerancji geometrycznych](17-segment-geometric-tolerances.md) | SD-V4-06, SD-V4-16 | Zmień tolerancje kąta i rozstawu, porównaj domeny z v0.4. |
| [18 — Porównaj otoczenia molekuł metodą freud bez zadawania K](18-compare-freud-environments.md) | SD-V4-06, SD-V4-16 | Przelicz jedną klatkę metodą freud i obejrzyj końcowe przypisania. |
| [19 — Porównaj domeny z lokalnego FFT i NMF obrazu](19-compare-local-fft-nmf.md) | SD-V4-06, SD-V4-16; warunek wyboru | Zmień okno analizy obrazu i porównaj wynik na molekułach. |
| [20 — Zachowaj wspólny katalog typów struktury w serii](20-shared-structural-type-catalogue.md) | SD-V4-08, SD-V4-13, SD-V4-16; warunek wyboru | Sprawdź wspólne typy na kolejnych klatkach i po otwarciu zapisanego projektu. |

Można realizować w kolejności numerów. Zależności pozwalają jednak wybrać
wcześniej inną gotową funkcję: po 02 można zrobić 04, bez czekania na 03;
po 04 można zrobić eksport 14; po 05 dostępne są 06–10 oraz zapis 13.
Najkrótsza droga do regulacji parametrów i rzeczywistego wyniku to
**01 → 02 → 04 → 05 → 06**. Ręczne K wymaga potem 07, a Auto — 11 i 12.
Analiza serii 08 może korzystać z dostarczonego modelu jeszcze przed 07.

Rozszerzenia można zacząć od **16 po 05**, bez czekania na wszystkie 01–15.
Po 06 i 16 dostępne są niezależne 17 oraz 18. Jako pierwszą próbę nowej
biblioteki wybieramy 18; 19 pozostaje dalszym wariantem po jej ocenie,
jeśli wskażemy informację, którą może wnieść obraz. 20 czeka na stabilny
opis struktur oraz analizę serii i zapis projektu. Numeracja nie wymusza
ukończenia wszystkich wcześniejszych numerów.

Nie tworzymy osobnych etapów „sam backend” lub „sam refaktor”. Potrzebne
wydzielenie operacji v0.4 należy do pierwszego ticketu, który z nich korzysta.
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
na rzeczywistych molekułach, szare odmowy i możliwość powrotu do v0.4.
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
  Pliki źródłowe i bazowy wynik v0.4 pozostają dostępne bez nadpisywania.
- **Czytelny widok:** podstawą są rzeczywiste molekuły na obrazie,
  kolor konkretnej domeny i szare nieprzypisane oznaczenia. Klasa,
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
- Najpierw odtwarzamy zapisany wynik v0.4, potem umożliwiamy eksperymenty
  z jego parametrami. Metoda dopuszcza jeden kierunek periodyczności.
  Wzrost liczby przypisań nie stanowi sam w sobie walidacji domen 2D.
- Nie przenosimy skryptów paczki w postaci jednego dużego pliku GUI.
  Ustawienia mają trafiać do wykonywanych obliczeń, bez ukrytych
  zależności od pierwszych dziesięciu klatek lub katalogu agenta.

Lokalne materiały do odbioru:

- MPP: `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`.
- Oznaczenia: `data/TTMAPP/detection_full.moltrack.json`.
- Dostarczone archiwa: `data/new_code/`; ich zawartość i identyczność
  danych opisano w przeglądzie v0.4.
- Rozpakowane kopie robocze: `.scratch/new-code-v04-review/`.
  Ścieżki służą odnalezieniu materiałów, a nie są stałymi w aplikacji.

Wynik v0.4 obejmuje 56 spośród 268 klatek. Odbiór ma obejmować różnicę
między zapisanym zerowym wynikiem (np. klatka 160) a klatką bez analizy.
Przypadki importu obejmują również brak masek i brak oznaczeń.

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
