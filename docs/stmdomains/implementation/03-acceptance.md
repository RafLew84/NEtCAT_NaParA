# Odbiór szkieletu STM Domains

ID: SD-IMPL-03
Type: acceptance
Status: todo
Assignee:
Depends on: [import i model](01-import-model.md), [natywne okno](02-browsing-window.md)

## Cel i warunek zakończenia

Potwierdzić, że konkretny commit natywnej aplikacji poprawnie otwiera rzeczywisty
zapis MolTrack i pokazuje zgodne obrazy/oznaczenia we wszystkich uzgodnionych
stanach. Wyniki testów, kontrola lokalnych danych i odbiór przez użytkownika
muszą być rozróżnione. Dopiero komplet kończy implementację etapu 1.

To odbiór importu i podglądu, nie ocena trafności detekcji molekuł, rejestracji
ani metod domen. Odtwarzamy zapisane wyniki o niskiej pewności, nie potwierdzamy
ich naukowej poprawności. Własny zapis, eksport i analiza nie są warunkiem.

## A. Automatyczne sprawdzenia bez danych pomiarowych

Uruchomić `python -m pytest -q tests/stmdomains` na końcowym commicie.
Testy mają obejmować zachowania opisane w zadaniach implementacji, w tym:

- schema 1/2/3, nieznaną wersję, jeden MPP, jedną klatkę, podzbiór i kolejność
  `[4,2]` z właściwymi czasami, duplikaty oraz niecałkowite ID;
- kandydatów źródła, zmieniony mtime, potwierdzenie/odrzucenie konkretnego
  MPP, niezgodne źródło i zachowanie poprzedniej serii;
- raw/expanded, niekwadratowy wzorzec, brzegi i ułamkowe przesunięcia,
  historyczne bboxy, granicę FoV niezależną od NaN oraz brak kumulacji resamplingu;
- wszystkie kodowania masek, shape, powiązania, błędny rekord, brak/pusto,
  ograniczony cache i brak pełnego dekodowania przy otwarciu;
- w Qt/offscreen: spójne publikowanie obrazu i nakładek, anulowanie,
  spóźnione odpowiedzi, play/pauzę/koniec, brak pomijania przy wolnym przygotowaniu,
  jedną klatkę, zachowanie ustawień i jawne stany braków;
- kontrast na finite próbkach oryginału, te same poziomy raw/aligned,
  gamma bez mutacji, stałą klatkę, brak skończonych próbek i geometrię piksela.

Fixture'y są małe, syntetyczne i w Git. Testy przekraczają ten sam interfejs
co aplikacja; nie sprawdzają tylko wewnętrznych nazw metod czy układu klas.
Stare testy loadera i geometrii są dodatkową regresją przy wykorzystaniu
ich kodu, nie substytutem testów Domains. W raporcie podać również skipy
oraz ich przyczyny. Brak danych lokalnych nie może pomijać małych fixture'ów.

## B. Sprawdzenia pełnego TTMAPP

Dane lokalne, poza Git, z [audytu importu](../import-geometry-audit.md):

- `data/TTMAPP/detection_full.moltrack.json`;
- `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`.

Przed sprawdzeniem zapisać SHA-256 i porównać z audytem. Różny hash to inny
zestaw wejściowy wymagający wyjaśnienia, nie automatycznie ta sama referencja.
Dane są w worktree Domains; nowe worktree mogą ich nie mieć. Nie kopiować
ich do Git ani zmieniać źródłowego JSON/mtime w celu wymuszenia zgodności.

| Kontrola | Oczekiwany wynik |
| --- | --- |
| Obrazy | 268 klatek, oryginał 256 × 256 px, przyjęta orientacja MPP. |
| Płótno wyrównania | 480 × 408 px; padding LTRB 224, 139, 0, 13; początek klatki źródłowej 0 to (224,139). |
| Rejestracja | Klatka 1 ma zapisane OK; pozostałe 267 oznaczone niską pewnością, nadal dostępne do podglądu. |
| Oznaczenia | 52 494 bboxy; 11 993 maski SAM. Import nie dekoduje całego zbioru masek. |
| Brak masek | Od klatki widocznej jako 41; poprawne ramki pozostają. |
| Brak ramek | Klatki widoczne jako 64–68; obraz dostępny, komunikat nie twierdzi „zero molekuł”. |
| Kalibracja i czas | Nieznane; brak nm i udawanego czasu z tablicy zer lub tempa odtwarzania. |
| Start podglądu | Przywrócona zapisana klatka 268 i widok wyrównany, odtwarzanie zatrzymane. |

W tabeli numery pokazywane użytkownikowi są od 1; źródłowe indeksy w modelu
od 0. Przejść przez klatki **1, 40, 41, 64, 68, 69 i 268**. Sprawdzić powrót
ramek po pustym odcinku, brak przesunięcia rekordów na sąsiednią klatkę oraz
zgodność masek i bboxów w obu trybach.

Na kopiach/małych kontrolnych zapisach, bez modyfikacji źródła referencyjnego:

1. Przenieść JSON/MPP, sprawdzić ścieżkę względną i wskazanie MPP ręcznie.
   Osobno zaakceptować i odrzucić zmieniony mtime oraz wskazać niezgodny obraz.
   W każdym nieudanym/anulowanym przypadku poprzedni podgląd pozostaje.
2. Otworzyć serię jednej klatki oraz pozbawioną rejestracji. W drugim przypadku
   oryginał działa; rekordy expanded o nieustalonym położeniu są niedostępne.
   Poprawne rekordy raw z kontrolnego fixture'a pozostają widoczne.
3. Sprawdzić błąd opcjonalnej maski przy poprawnym bboxie oraz wadliwą mapę
   klatek: izolacja maski w pierwszym przypadku, brak podmiany serii w drugim.
4. Przejść serię i wracać do wcześniejszych klatek. Zmierzyć czas otwarcia,
   pierwszego obrazu, zmiany klatki z maskami/bez, peak RSS i rozmiar cache.
   Pamięć nie rośnie bez ograniczenia z każdą obejrzaną klatką/powtórzeniem.
5. Otwierać, anulować, otworzyć inny zapis i zamknąć okno podczas pracy.
   Nie ma późniejszej podmiany stanu przez porzucone zadanie ani błędu
   niszczenia pracującego wątku. Nieprzerywalny fragment odczytu jest zmierzony
   i opisany; anulowanie nie publikuje jego wyniku.
6. Porównać hashe źródeł po zakończeniu. Podgląd nie zmienił danych pomiarowych.

Pełne sprawdzenia mogą być osobnym poleceniem lub testem opt-in ze wskazaną
ścieżką danych. Sam skip takiego testu nie zalicza sekcji B.

## C. Kontrola w rzeczywistym GUI

Uruchomić `python -m stmdomains.main` w lokalnym `netcat` na tym samym commicie
co powyższe sprawdzenia. Użytkownik lub prowadzący przechodzi poniższe kroki,
a użytkownik potwierdza końcowy odbiór podglądu.

1. W oknie 1100 × 760 otworzyć TTMAPP rzeczywistym dialogiem. Zobaczyć układ C,
   bieżącą miniaturę, numer klatki, obraz i informacje o niskiej pewności.
2. Wybrać klatki z tabeli B przez miniatury, numer, suwak i poprzednia/następna.
   Zmieniać rozmiar okna; podstawowe kontrolki pozostają osiągalne.
3. Obejrzeć ramki i maski, zmienić krycie, podświetlić ramkę, sprawdzić metadane.
   Wyłączyć nakładki. Nie przesuwają się względem obrazu podczas zoom/pan.
4. Zmienić gamma, przybliżyć kółkiem wokół kursora, przesunąć, użyć „Dopasuj”.
   Przełączyć original/aligned i wrócić. Padding ma osobne tło; granica pola
   i oznaczenia odpowiadają obrazowi także przy ułamkowym przesunięciu.
5. Uruchomić play z różnymi szybkościami, zatrzymać na klatce z maskami,
   wznowić i dojść do końca. Nie ma dodatkowego kroku po pauzie, mieszania
   numerów/oznaczeń ani przeskakiwania klatek w celu nadrabiania czasu.
6. W trakcie odtwarzania wywołać otwieranie i anulować. Sprawdzić błąd źródła,
   pojedynczą klatkę i brak rejestracji zgodnie z sekcją B.
7. Ocenić czytelność informacji o brakach, niskiej pewności i auto kontraście
   oraz akceptowalność czasu reakcji. Zapisać konkretne uwagi zamiast uznawać
   samo uruchomienie okna za odbiór.

Nie trzeba uruchamiać modeli, segmentacji domen ani ponownej rejestracji.
Sam Qt/offscreen lub screenshot HTML nie zastępuje tej kontroli.

## Raport i zakończenie

Przy wykonaniu utworzyć `docs/stmdomains/implementation/acceptance-report.md`
z datą, commitem, systemem/interpreterem, wersjami istotnych pakietów, hashami
wejścia, komendami i wynikami A/B/C. Pomiary pamięci/czasu odnoszą się do
natywnej aplikacji. Zrzuty danych i duże logi mogą pozostać lokalnie;
wersjonowany raport wskazuje ich ścieżkę i opisuje wynik.

Oddzielić: zaliczone, niewykonane i niezaliczone kontrole oraz znane ograniczenia.
Brak potwierdzenia końcowego GUI pozostawia zadanie w toku. Przy niezgodności
z kontraktem poprawić implementację lub uzgodnić konkretną zmianę specyfikacji;
nie oznaczać całego etapu jako gotowego przez pominięcie przypadku.

Po zaliczeniu kryteriów i potwierdzeniu użytkownika: status `done`, aktualizacja
README i handoff, przekazanie commita integratorowi. Włączenie nowych zależności
oraz testów do wspólnej instalacji/CI ma własny zapis w przekazaniu; nie
przedstawiać starego pliku zależności PyQt6 jako kompletnego środowiska aplikacji.
