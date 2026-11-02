# REG-12: pobrane zasoby i próba środowiska — 2026-11-02

Zlecenie użytkownika: „ściągnij wymagane elementy”. Przygotowano kod
MatchAnything i oficjalny checkpoint ELoFTR w
`/home/rlew/.cache/stmviewer/matchanything/`.
[Pełne ścieżki, wersje, SHA i wyniki](registration/matchanything-environment.md).
Commit dokumentacji podano w odpowiedzi sesji; lokalne modele nie trafiają do Git.

- Kod HF przypięty do `6a7bcb589ec8da3a9e861e799122beaa5eba2193`;
  163 pliki zweryfikowane względem Git blob SHA i lokalnego manifestu SHA-256.
- Checkpoint 64 366 723 B pobrany z oficjalnego Drive, wyłącznie członek
  ELoFTR archiwum ZIP. CRC i SHA sprawdzone; ścisłe ładowanie poprawne.
- Próby rzeczywiste CPU/CUDA na wzorcu 256²: błąd osi poniżej 0,032 px,
  bez prób sieci. Punkty przeszły konsensus v2 Viewera ze statusem `manual_review`.
- 213 pakietów `netcat` ma identyczne wersje przed i po; `pip check` czyste.
  Nie instalowano zależności i nie tworzono środowiska. Pominięto wrapper
  treningowy Lightning; produkcyjny import wymaga izolacji globalnego `src`.
- Zachowano licencje HF i GitHub z odnotowaniem rozbieżności ich treści.

REG-12 pozostaje **ready-for-agent**; kryteria funkcji nie są oznaczone
jako wykonane. Brak zmian kodu aplikacji, wspólnych modułów i konfiguracji.
Nie powtarzano testów Viewera; nie wykonano nowej próby manualnej GUI,
pełnych filmów STM, Windows ani stanowiska 8 GB VRAM.
Brak potrzebnych zmian integracyjnych, publikacji i scalania.

# REG-11: odbiór manualny — 2026-11-02

Użytkownik potwierdził **„testy manualne ok”**. REG-11 zmieniono na `done`;
zsynchronizowano bieżące podsumowania, mapę, instrukcję i raport odbioru.
Implementacja: `cfc1547` i poprawka `4e69d40`; wyniki: `fbbf97d`.
Commit tego potwierdzenia podano w odpowiedzi sesji.

REG-12 jest odblokowany, lecz nie rozpoczęto go bez osobnego zlecenia.
Nie zmieniono kodu ani wyników prób automatycznych; nie powtarzano testów.
Potwierdzenie nie dopisuje szczegółowych wyników Windows, sprzętu 8 GB
lub VLC. Zapisane ograniczenia RoMa i limit Hubera pozostają aktualne.

# REG-11: RoMa v2 — wdrożenie do odbioru — 2026-11-02

Zakres `3a3a684..4e69d40`: implementacja `cfc1547`, poprawka przeglądu
`4e69d40`. Status **ready-for-review**, ręczny odbiór użytkownika niewykonany.
Końcowy commit dokumentacji podany w odpowiedzi sesji.

RoMa działa dla pary, filmu i grafu w osobnym procesie `netcat-romav2`;
GUI, konsensus v2, LS/Huber i eksport pozostają w `netcat`. Jeden model na
zadanie, lokalny kod/wagi z SHA-256, bez pobierania i zmiany urządzenia po
błędzie. Próbkowanie ogranicza punkty w siatce 8 × 8 obu oryginałów.
Wynik pozostaje jedną translacją, z istniejącym rendererem.

Sesja v6 zapisuje także nieaktywną konfigurację RoMa; graf v6 i MPP V9
zachowują pochodzenie i diagnostykę. Poprzednie formaty są odczytywane,
otwarcie sesji nie uruchamia interpretera. Anulowanie i błędy zachowują aligned.

- Końcowy Viewer: **761 passed, 14 skipped**, mypy **94 moduły** bez błędów.
- Osobno **4 rzeczywiste testy CPU/CUDA** i **2 rzeczywiste testy Qt offscreen**
  zaliczone. Anulowanie i zły SHA wag zachowały identyczny poprzedni obraz.
- Pełne MOVIE_4 (bez źródłowych 1/2) i MOVIE_8: kompletne łańcuchy i LS,
  sesje, ręczna korekta przez API, ponowny odczyt MPP i zapis MJPG/FFV1.
  Huber w obu filmach osiągnął limit 200 iteracji — brak wariantu do zastosowania.
- Porównanie tych samych 9 par wzorców: RoMa, EfficientLoFTR v2, Deep outdoor.
  RoMa myli ruch z nieruchomym pasem; nie deklarujemy przewagi jakościowej.
- Pełne repo: 2539 passed, 18 failed, 26 skipped przed poprawką oczekiwanej
  listy metod. Cztery niepowodzenia Viewera usunięto i potwierdzono końcowym
  biegiem; pozostałe 14 ID MolTrack/NanoTrack identyczne z logami REG-10.
- Standards: 0 uwag. Spec: 1 P2 utrwalania konfiguracji naprawiony,
  ponowny przegląd zamknięty z 0 otwartymi uwagami.

[Instrukcja ręczna](registration/roma-manual.md),
[wyniki i lokalne sesje](registration/roma-results.md),
[pełne sprawdzenia i przeglądy](registration/reviews/REG-11.md).
Uruchomienie nadal `conda activate netcat` i `python -m stmviewer.main`.
Domyślne ścieżki lokalnego środowiska RoMa są już przygotowane.

Ręczna ocena STM, VLC, Windows i stanowisko 8 GB pozostają niewykonane.
Nie zmieniono bibliotek `netcat`, wspólnych modułów ani konfiguracji głównej.
REG-12 nie rozpoczęto. Brak publikacji i scalania.

# REG-11: osobne środowisko i kontrakt procesu — 2026-11-02

Na wyraźne zlecenie użytkownika przygotowano **tylko środowisko i aktualizację
ticketu**. REG-11 pozostaje `ready-for-agent`, wszystkie kryteria funkcji
są nieoznaczone. Nie dodano jeszcze RoMa do wyboru metody w GUI.

- Nowe środowisko: `/home/rlew/miniconda3/envs/netcat-romav2/bin/python`.
  Python 3.12.16, RoMa 2.0.1, Torch 2.11.0/CUDA 13.0, torchvision 0.26.0,
  fused-local-corr 0.3.211. Zależności zapisane w zakresie Viewera.
- Zweryfikowany checkpoint i przypięty kod DINOv3 są w
  `/home/rlew/.cache/stmviewer/romav2/`; pełna dokumentacja wersji,
  SHA-256 i licencji: [przygotowanie](registration/roma-environment.md).
- Proces uruchomiony z `netcat` zaliczył rzeczywiste próby CPU/CUDA na
  znanym przesunięciu: błąd osi poniżej 0,04 px, bez połączeń sieciowych.
  Odbiór punktów przez konsensus `netcat` również poprawny. `pip check` czyste.
- Inwentarz wszystkich 213 pakietów `netcat` pozostał identyczny.
  GUI, sesje, graf, render i eksport nadal działają w tym środowisku.
- REG-11 określa jeden proces/model na zadanie, JSON/NumPy bez pickle,
  anulowanie i sprzątanie, jawne błędy oraz brak uruchamiania procesu
  przy samym otwieraniu sesji. Produkcyjny mechanizm jest jeszcze do wdrożenia.

Nie powtarzano testów aplikacji: zmieniono dokumentację oraz osobny plik
wymagań środowiska, bez kodu działającego Viewera. Nie wykonano odbioru
GUI nowej metody, rzeczywistych filmów, Windows lub stanowiska 8 GB VRAM.
Brak zmian wspólnych, publikacji i scalania.

# REG-10: odbiór manualny — 2026-11-02

Użytkownik potwierdził **„testy manualne ok”** po poprawce `7e7084c`
i przekazaniu `b15fb4d`. [REG-10](registration/issues/10-efficient-loftr.md)
zamknięto jako **done**; zsynchronizowano plan, status i raporty odbioru.

Zmiana dotyczy wyłącznie dokumentacji. Nie powtarzano testów kodu; wyniki
712 testów aplikacji i 6 rzeczywistych prób CPU/CUDA pozostają w
[raporcie poprawki](registration/efficient-loftr-weak-results.md).
Potwierdzenie nie dodaje szczegółowej oceny przewagi nad Deep ani
odbioru Windows, VLC lub sprzętu 8 GB VRAM. Zachowano udokumentowane
ograniczenia MOVIE_4: odmowę łańcucha 35→36 i limit iteracji Hubera.

REG-11 jest odblokowany, ale nie rozpoczęty; REG-12 również nie rozpoczęto.
Brak zmian wspólnych, publikacji lub scalenia gałęzi.

# REG-10: słabe wyniki rzeczywistych MPP — 2026-11-02

Baza poprawki: `93a3126`; implementacja `7e7084c`; gałąź `viewer/registration-difficult-movies`.
W chwili przekazania status wynosił `ready-for-review`; użytkownik wcześniej
zaakceptował pokazywanie niepewnych wyników. Późniejszy odbiór zapisano powyżej.

Przyczyną blokady były nowe twarde reguły kwalifikacji par, inne niż
w historycznym Deep. Konsensus v2 zwraca słaby kandydat z `low_confidence`
i bez liczbowej pewności; rzeczywisty brak co najmniej 8 poprawnych punktów
łącznie i 4 zgodnych wektorów nadal daje odmowę. Sesja, graf, ręczne korekty
oraz MPP zachowują ostrzeżenia, a stare diagnozy v1 pozostają odczytywalne.
Wagi, przygotowanie obrazów i model pozostają te same.

Wykonane: 712 testów Viewer passed, 8 skipped; dodatkowo 6 rzeczywistych
prób CPU/CUDA passed. Mypy 90 modułów, Ruff, diff-check czyste. Pełna próba
MOVIE_8 daje łańcuch, graf LS i Hubera; MOVIE_4 daje kompletny graf LS,
ale łańcuch odmawia 35→36, a Huber osiąga limit 200 iteracji.
Zastosowanie, sesje, korekty, MPP i AVI sprawdzono automatycznie.
Przydatność wizualna, Windows, VLC i karta 8 GB VRAM nie są tym potwierdzone.

[Diagnoza, wyniki i instrukcja próby](registration/efficient-loftr-weak-results.md).
[Przeglądy](registration/reviews/REG-10-weak-results.md): 0 otwartych uwag;
doprecyzowano opis wag Hubera.
Uruchom ponownie w `netcat`: `python -m stmviewer.main`. Nie trzeba pobierać
wag. W MOVIE_4 usuń źródłowe 1–2; do całego filmu użyj grafu z oknem 3
oraz jawnie zastosuj kompletny LS. Brak potrzebnych zmian wspólnych.

# REG-10: EfficientLoFTR — 2026-11-02

Historyczny status przy wdrożeniu: **ready-for-review**; odbiór zakończono
po późniejszej poprawce niepewnych wyników.
Baza `03ad8d9`, implementacja `6644d8c`, poprawka testu/raportu `7f96103`.
Gałąź `viewer/registration-difficult-movies`; commit dokumentacji w końcowej wiadomości.

EfficientLoFTR działa jako osobna metoda pary, łańcucha i grafu. Wspólny
konsensus korespondencji oraz rozkład poparcia są wersjonowane. Lokalny
kod i wagi są sprawdzane przez SHA; bez pobierania i fallbacku. Zapisane
sesje działają bez modelu; aktywny wynik, osobny kandydat, ręczne korekty
oraz eksport MPP/AVI zachowują dotychczasowy cykl pracy.

[Próba manualna](registration/efficient-loftr-manual.md),
[wyniki i sesje](registration/efficient-loftr-results.md),
[testy i przeglądy](registration/reviews/REG-10.md).
Uruchomienie w `netcat`: `python -m stmviewer.main`; wybierz EfficientLoFTR.
Przygotowane ścieżki lokalne są domyślne, wcześniejsze wagi Deep pozostają osobne.

- Pełne repo raz: 2480 passed / 18 failed / 22 skipped. Cztery błędy
  oczekiwania starej listy metod GUI poprawiono; następnie 66 testów
  celowanych przeszło. Pozostałe 14 błędów dokładnie odpowiada wcześniejszym
  MolTrack/NanoTrack. Po połączeniu przebiegów Viewer: 698 passed / 8 skipped.
- Osobno 6 rzeczywistych testów Efficient CPU/CUDA, cykl sesja/korekta/MPP/AVI
  zaliczony. Mypy 90 modułów, Ruff, limit 1500 i diff-check poprawne.
  Standards i Spec: 0 uwag w implementacji i delcie poprawki.
- Pełne MOVIE_4 (bez pierwszych dwóch źródłowych klatek) i MOVIE_8 przeliczono.
  Efficient: 430/1080 i 229/246 odmów grafu, wynik rozłączny; oba łańcuchy
  odmawiają pierwszej pary. Zachowano sesje diagnostyczne. Deep outdoor daje
  kompletne łańcuchy i LS; nie twierdzimy, że nowa metoda poprawia te filmy.
- Qt offscreen to weryfikacja automatyczna, nie ręczny odbiór. Ocena jakości
  STM, Windows/VLC i stanowisko 8 GB VRAM pozostają otwarte. Brak niezależnej
  kontroli obrazowej. REG-11/12 nie rozpoczęto, odłożonych etapów nie wznowiono.
- Brak zmian wspólnych, publikacji i scalenia. Pliki użytkownika, źródłowe
  pomiary, modele i duże wyniki pozostają lokalne oraz poza Git.

---

# REG-10: przygotowanie kodu i wag — 2026-11-02

Na zlecenie „biblioteki zainstalowane. ściągnij wagi i kod” pobrano oficjalny
kod EfficientLoFTR oraz checkpoint `eloftr_outdoor.ckpt`. Lokalizacja:
`/home/rlew/.cache/stmviewer/efficientloftr/`. Kod przypięto do
`07e9c1401e71e9c556b1fda9d86d060af36ba176`; SHA-256 i rozmiar wag zgodne
ze sprawdzonymi kopiami. [Instrukcja i pochodzenie](registration/efficient-loftr-setup.md).

- `netcat`: importy, strict-load parametrów oraz rzeczywiste obliczenie pary
  na CPU i CUDA zaliczone. FP32, 256 × 256, 729 dopasowań na obu urządzeniach,
  zadane X=+7/Y=−5 px, błąd mediany w każdej osi <0,02 px. GPU: RTX 5090.
- Checkpoint wymaga wąskiego dopuszczenia `ModelCheckpoint` przy
  `weights_only=True`; skrypt i raport zachowano lokalnie. Kod modelu czysty.
- To przygotowanie środowiska; REG-10 nadal `ready-for-agent`, implementacja
  nierozpoczęta. Bez oceny STM, odbioru GPU 8 GB i ręcznej próby GUI.
  Testów programu nie powtarzano; w repo zmienia się tylko dokumentacja.
- Gałąź `viewer/registration-difficult-movies`, baza `b6c1801`;
  commit dokumentacji w końcowej wiadomości przekazania. Kontrola odnośników
  i diff-check; bez zmian współdzielonych, scalenia lub publikacji.
  Biblioteki zainstalował użytkownik; pobranie nie zmieniało pakietów.

---

# REG-09: odłożenie etapu — 2026-11-02

Użytkownik zdecydował: **„pomińmy na razie ten etap”**. REG-09 pozostaje
`planned`, jest odłożony i nie ma implementacji. Zakres zachowano w tickecie;
wznowienie wymaga osobnego zlecenia. REG-09 nie blokuje REG-10.

Zaktualizowano ticket, plan i mapę. Zmiana dotyczy wyłącznie dokumentacji;
sprawdzono odnośniki oraz `git diff --check`, bez testów programu.
REG-10 ma status `ready-for-agent`; prośba o opis nie uruchamia implementacji.
Commit tej decyzji w wiadomości przekazania.

# REG-08e: metody w dopasowaniu wieloklatkowym — 2026-11-02

Status: **done**; użytkownik potwierdził „testy manualne ok” 2026-11-02.
Gałąź: `viewer/registration-difficult-movies`.
Baza: `a631c79661dff5cb5d7b1bc387edcb22a4a490d6`.
Implementacja: `2626588`; poprawka przeglądu: `c0c5abc`.
Dokumentacja wykonania: `b910234`. Commit potwierdzenia odbioru w wiadomości przekazania.

W istniejącym oknie **Dopasowanie wieloklatkowe…** dodano wybór ośmiu metod
par. Wspólne LS/Huber pracują na zapisanych pomiarach; wynik wymaga jawnego
zastosowania. CPU nie wymaga modelu. Metody, ustawienia, diagnostyka i historia
są zachowane w sesjach oraz pochodzeniu MPP. Starsze zapisy Deep pozostają
obsługiwane; zarezerwowanych formatów wycofanego REG-08d nie użyto ponownie.

[Instrukcja i gotowe sesje](registration/multiframe-methods-manual.md),
[wyniki rzeczywistych prób](registration/multiframe-methods-results.md),
[testy i dwa niezależne przeglądy](registration/reviews/REG-08e.md).
Uruchomienie z tego worktree, w `netcat`: `python -m stmviewer.main`.

- STM Viewer: **666 passed, 2 skipped** w pełnym przebiegu repo.
- Całe repo: **2452 passed, 14 failed, 16 skipped**; dokładnie te same
  14 wcześniejszych błędów MolTrack/NanoTrack, bez nowych błędów Viewera.
- Po poprawce przeglądu: **37 testów celowanych zaliczonych**; mypy 84 moduły,
  Ruff, limit plików i diff-check poprawne. Standards/Spec: 0 otwartych uwag.
- Rzeczywiste próby: wszystkie metody na wzorcu, pełne MOVIE_4/MOVIE_8
  Optical Flow i Deep, sesje/korekty/przywracanie/MPP/AVI. Odczyt 58 sesji
  i 76 AVI oraz trzech starszych sesji Deep sprawdzono osobno.
- Użytkownik potwierdził odbiór manualny 2026-11-02. Nie podał szczegółowej
  oceny jakości metod ani systemu, odtwarzacza i sprzętu; potwierdzeniu nie
  przypisujemy osobnego odbioru Windows 11, VLC ani stanowiska docelowego.
  REG-10–12 nie rozpoczęto; REG-08d nie przywrócono.
- Aktualizacja odbioru dotyczy dokumentacji: kontrola statusów, lokalnych
  odnośników i diff-check, bez ponownego uruchamiania testów programu.

**Do integracji:** wspólny Tile+RANSAC pomijał wszystkie wyjątki lokalnej
korelacji, także brak pamięci, oraz błędne wektory. Lokalny adapter
`stmviewer/graph_tile_backend.py` zachowuje matematykę i propaguje awarie.
Wspólnych modułów nie zmieniono. Sesja integracyjna może zawęzić to zachowanie
w `nanotrack/registration/tile_correlation.py`, z testami jego pozostałych
odbiorców; wtedy lokalną pętlę Viewera będzie można usunąć. Nie blokuje REG-08e.

# REG-08e: ticket metod w dopasowaniu wieloklatkowym — 2026-11-02

Na zlecenie użytkownika dodano
[REG-08e](registration/issues/08e-multiframe-methods.md): **ready-for-agent**,
implementacja nierozpoczęta. Gałąź `viewer/registration-difficult-movies`,
baza tej aktualizacji `c8e9141`; commit planu w końcowym przekazaniu.

- Jedno pole wyboru metody par w istniejącym oknie 3/5; pięć metod CPU,
  Deep, Deep+ECC i Deep+lokalne fragmenty. LS i Huber używają pomiarów
  wybranej metody; bez nowego okna, biblioteki prób i planowania dalszych par.
- Ticket obejmuje brak pewności i odmowy, parametry i odrębność pamięci
  pomiarów, CPU bez wag, sesje i zgodność starych grafów Deep, zastosowanie,
  ręczne korekty oraz MPP/AVI. Dodano granice TDD i testy manualne.
- Plan umieszcza REG-08e po REG-08c, przed REG-10; techniczne zależności
  nowych modeli pozostają. Żadnego etapu implementacji nie uruchomiono.
- Uzupełniono fakt wycofania REG-08d commitem `c8e9141`. Historyczny ticket
  pozostaje odłożony; nowe zadanie nie przywraca usuniętej funkcji.
- Zmiana wyłącznie dokumentacji: kontrola zakresu metod względem kodu,
  zależności, spójności statusów, odnośników i `git diff --check`.
  Testów programu nie uruchamiano; próby manualne nowej funkcji należą
  do przyszłej implementacji. Brak zmian wspólnych, publikacji i scalania.
  Pliki użytkownika i dane pozostają nietknięte.

---

# REG-08c: odbiór manualny i komunikat odmowy — 2026-11-01

Użytkownik potwierdził **„testy manualne ok”**; REG-08c ma status **done**.
Gałąź `viewer/registration-difficult-movies`, baza tej aktualizacji `be46f91`.
Na jego życzenie dodano dialog po obliczeniu niekompletnego Hubera:
commit **`293d392`**. Dokumentacja odbioru w końcowym commicie przekazania.

- Komunikat podaje powód zakończenia, liczbę iteracji i wyjaśnia, dlaczego
  nie można zastosować wyniku. Wskazuje, że podgląd może nadal przedstawiać
  LS lub wcześniejszy wariant, oraz jak jawnie wybrać kompletny wynik.
  Przy limicie iteracji opisuje możliwość zwiększenia go bez obietnicy zbieżności.
- **36 testów GUI zaliczonych**, strict mypy **81 modułów**, Ruff i diff-check
  czyste. Istniejący test rozszerzono RED→GREEN; zrzut Qt offscreen obejrzano.
  [Karta testów i przeglądu](registration/reviews/REG-08c.md): Standards i Spec
  po niezależnym przeglądzie bez ustaleń. Pełnego repo ponownie nie uruchamiano
  dla tego uzupełnienia prezentacji; wcześniejsze wyniki pozostają w karcie.
- Dialog dodano po potwierdzeniu odbioru i nie przypisano mu wcześniejszego
  ręcznego zaliczenia. Uruchomienie: po zapisaniu bieżącej sesji uruchomić
  `python -m stmviewer.main` ponownie w `netcat`. Próba: z grafu MOVIE_4
  obliczyć Hubera z limitem 1; odczytać dialog, zamknąć OK i wybrać kompletny LS.
- Zaktualizowano ticket, plan, mapę, README, instrukcję, wyniki i kartę odbioru.
  REG-10 ma spełnioną zależność, ale pozostaje nierozpoczęty.
- Potwierdzenie użytkownika nie określa systemu, sprzętu ani przewagi algorytmu;
  nie zalicza Windows 11 lub stanowiska docelowego. Brak zmian wspólnych,
  publikacji i scalenia. Pliki użytkownika pozostają nietknięte i poza Git.

---

# REG-08c: graf jako aktywny film — 2026-11-01

Status **ready-for-review**; ręczny odbiór oczekuje.
Gałąź `viewer/registration-difficult-movies`, baza `5f45b36`.
Kod **`140136e`**, poprawka przeglądu **`73bbc44`**; końcowa dokumentacja
w commicie przekazania. Zakres: wyłącznie STM Viewer, testy i dokumentacja.

- Jawne **Zastosuj wynik do filmu** wybiera kompletny LS/Huber. Oryginały są
  interpolowane raz do gotowego aligned; błąd/anulowanie zostawia poprzedni film.
  Wybrana klatka i gamma zostają, obszar jest dopasowany, Play zatrzymane.
- Zamrożona baza G jest punktem odniesienia ręcznych nadpisań; surowe pomiary
  pozostają osobno. Korekty propagują się dalej bez ponownego solvera.
  Jeden lekki poprzednik zachowuje historię bez kopii pikseli.
  **Przywróć zachowany wynik** odtwarza go z oryginałów bez modelu.
- Sesje v3 zachowują aktywny graf, odrębnego kandydata, korekty i poprzednika;
  starsze sesje działają. MPP v5 zachowuje wynik, geometrię i opis historii,
  pełne krawędzie należą do sesji. AVI korzysta z aktywnych poprawionych obrazów.
- **629 testów Viewera zaliczonych, 2 pominięte**, w tym 34 nowe przypadki.
  Pełna próba repo przerwana SIGTERM po 2195 przypadkach; pozostałe 250 to
  Viewer, wszystkie objęte późniejszym pełnym sprawdzeniem aplikacji.
  Po połączeniu rozłącznych zakresów: **2415 passed, 14 failed, 16 skipped**;
  14 błędów dokładnie odpowiada wcześniejszym MolTrack/NanoTrack.
  [Karta testów](registration/reviews/REG-08c.md) opisuje ograniczenie próby.
- Strict mypy 81 modułów, Ruff i diff-check czyste; największy plik 967 linii.
  Dwa niezależne przeglądy: Standards — zamknięta jedna uwaga czytelności,
  Spec — 0 ustaleń. Po poprawce 15 dotkniętych testów ponownie zaliczone.
- Wzorzec oraz pełne MOVIE_4/MOVIE_8 sprawdzono bez Deep: zastosowanie obu
  solverów, korekta, sesja, dokładne przywrócenie i eksport. VLC 3.0.24 odczytał
  FFV1/MJPG do EOF (automatyczne wyjście dummy). Zrzuty Qt offscreen oceniono
  pod kątem czytelności i dostępności kontrolek. To nie odbiór ręczny.
- Start: `python -m stmviewer.main` w `netcat`, katalog `NEtCAT-viewer`.
  [Instrukcja i gotowe sesje](registration/graph-application-manual.md),
  [wyniki](registration/graph-application-results.md). Windows 11, sprzęt docelowy
  oraz ręczna ocena jakości pozostają do sprawdzenia. REG-10 nie rozpoczęto.
- Brak potrzeb wspólnych zmian, publikacji i scalenia. Pliki użytkownika
  `proba.stmtrial.json`, `proba2.stmtrial.json`, `sesja.stmsession` nietknięte;
  duże dane, modele, filmy i sesje pozostają lokalne.

---

# REG-08b: odbiór manualny — 2026-11-01

Użytkownik potwierdził: **„testy manualne ok”**.
[REG-08b — odporny graf](registration/issues/08b-robust-graph.md) ma status **done**.
Baza aktualizacji: `7c6da56`; gałąź `viewer/registration-difficult-movies`.
Kod: `2802837` + `417c107`; dokumentacja implementacji: `7c6da56`.

- Zaktualizowano ticket, plan, mapę, README, instrukcję, raport i kartę odbioru.
- REG-08c ma spełnioną zależność, pozostaje `ready-for-agent` i czeka na zlecenie.
  Nadal odpowiada za zastosowanie grafu do aligned, ręczne korekty i eksport.
- Potwierdzenie nie określa systemu, sprzętu ani porównawczej jakości filmów.
  Nie przypisujemy mu odbioru Windows 11 ani przewagi Hubera nad LS.
  Opisane ograniczenia, w tym niezbieżność MOVIE_4/3, pozostają aktualne.
- Zmieniono tylko dokumentację. Sprawdzono statusy, odnośniki i `git diff --check`;
  testów programu nie powtarzano. Wyniki wcześniejszych testów zachowuje
  [karta REG-08b](registration/reviews/REG-08b.md).
- Brak zmian wspólnych, publikacji lub scalenia. Pliki użytkownika
  `proba.stmtrial.json`, `proba2.stmtrial.json`, `sesja.stmsession` pozostają
  nietknięte. Odbiór zapisano w końcowym commicie tej aktualizacji.

---

# REG-08b: odporny graf — 2026-11-01

Stan przy przekazaniu implementacji: **ready-for-review**; późniejszy odbiór opisano powyżej.
Gałąź `viewer/registration-difficult-movies`, baza `3f6fd5a`.
Implementacja **`2802837`**, poprawki przeglądu **`417c107`**;
końcowa dokumentacja w commicie przekazania.

- Blokowy Huber IRLS na zapisanym grafie LS: te same pomiary, braki i kotwica,
  bez ponownego Deep, kary za kierunek ani wygładzania. Próg i jawny limit
  iteracji tworzą osobne zachowane warianty. Nieukończona próba ma diagnostykę,
  lecz nie ma pełnych pozycji do podglądu.
- UI porównuje LS/Huber we wspólnym kadrze, pokazuje różnice XY, reszty i wagi.
  Warianty są zachowane w wersjonowanej sesji bez dodatkowych stosów pikseli.
  Odczyt nie wymaga modelu ani ponownej optymalizacji. Starsze sesje działają.
  Aktywny aligned, ręczne korekty i eksport pozostają bez zmian; zastosowanie
  kandydata do filmu należy do REG-08c.
- Pełny zestaw raz: **2381 passed, 14 failed, 16 skipped**; Viewer:
  **595 passed, 0 failed, 2 skipped**. 14 błędów to dokładnie znane wcześniej
  MolTrack/NanoTrack. Po dwóch poprawkach przeglądu 28 testów solvera oraz
  7 sesji ponownie zaliczone. Strict mypy 73 modułów, Ruff i diff-check czyste.
  [Karta testów i dwóch niezależnych przeglądów](registration/reviews/REG-08b.md):
  Standards i Spec bez otwartych ustaleń. Największy plik zmiany 382 linie.
- Osobne wzorce rozwojowe i odbiorcze; maks. błąd współrzędnej znanego wzorca
  z pojedynczym błędem spada z 5,022 do 0,712 px. Most i zgodny alias nie dają
  się w ten sposób wykryć; błędna większość może pogorszyć wynik.
- MOVIE_4/3 nie osiągnął przyjętej zbieżności nawet po 5000 iteracjach;
  pozostaje diagnostyką. MOVIE_4/5 i MOVIE_8 mają pełne warianty. Nie zmieniono
  domyślnych tolerancji na podstawie odbioru. Ocena wizualna pozostaje manualna.
  [Wyniki i gotowe sesje w /tmp](registration/robust-graph-results.md).
- Start: `python -m stmviewer.main` w `netcat`, katalog `NEtCAT-viewer`.
  [Instrukcja i dane do ręcznej próby](registration/robust-graph-manual.md).
  Qt offscreen jest sprawdzeniem automatycznym. Windows 11, docelowy sprzęt
  i ręczny odbiór nie są zaliczone. REG-08c nie rozpoczęto.
- Brak potrzeb wspólnych zmian, publikacji i scalania. Pliki użytkownika
  `proba.stmtrial.json`, `proba2.stmtrial.json`, `sesja.stmsession` pozostają
  nietknięte i poza Git; duże dane i wyniki są lokalne.

---

# REG-08a: odbiór manualny — 2026-11-01

Użytkownik potwierdził: **„testy manualne ok”**.
[REG-08a — graf dopasowań 3/5](registration/issues/08a-window-graph.md) ma status **done**.
Baza aktualizacji: `51d7049`; gałąź `viewer/registration-difficult-movies`.
Kod: `ae32f1d` + `665a1ed`; dokumentacja implementacji: `51d7049`.

- Zaktualizowano ticket, plan, mapę, README, instrukcję, raport i kartę odbioru.
- REG-08b ma spełnioną zależność, pozostaje `ready-for-agent` i czeka na zlecenie.
  REG-08c nadal obejmuje zastosowanie grafu do filmu i eksportu, po REG-08b.
- Potwierdzenie nie określa systemu, sprzętu ani porównawczej jakości okien 3/5.
  Nie przypisujemy mu odbioru Windows 11, GPU 8 GB ani przewagi metody na konkretnym filmie.
- Zmieniono tylko dokumentację. Sprawdzono statusy, odnośniki i `git diff --check`;
  testów programu nie powtarzano. Wyniki wcześniejszych testów zachowuje
  [karta REG-08a](registration/reviews/REG-08a.md).
- Brak zmian wspólnych, publikacji lub scalenia. Pliki użytkownika
  `proba.stmtrial.json`, `proba2.stmtrial.json`, `sesja.stmsession` pozostają nietknięte.
  Odbiór zapisano w końcowym commicie tej aktualizacji.

---

# REG-08a: graf dopasowań 3/5 — 2026-11-01

Stan przy przekazaniu implementacji: **ready-for-review**; późniejszy odbiór opisano powyżej.
Gałąź `viewer/registration-difficult-movies`; baza `e12a794`.
Implementacja **`ae32f1d`**, poprawki **`665a1ed`**; dokumentacja w końcowym commicie.

- **Dopasowanie wieloklatkowe…**: obecny Deep z lokalnymi wagami, okna do 3/5
  wcześniejszych klatek, LS z równymi wagami, kotwica pierwszej klatki, tabela relacji
  i braków, komponenty/mosty, podgląd filmu i niesąsiednich par.
- Kandydat jest renderowany na żądanie, porównywany z łańcuchem tych samych
  pomiarów (lub jawną bazą aktywną przy braku łańcucha) i zachowywany w sesji.
  Nie zmienia aktywnego aligned, ręcznych korekt ani eksportu. Zastosowanie
  kandydata należy do REG-08c. Stare sesje bez grafu pozostają obsługiwane.
- Poprawiono dwie regresje startu bez SciPy/scikit-image znalezione pełnym zestawem.
  Po poprawkach **134 testy przechodzą**, mypy **67 modułów**, Ruff i diff-check
  czyste. Pełna próba wcześniej: 2331 passed / 16 failed / 16 skipped;
  po naprawie dwóch nowych przypadków pozostaje **14 znanych błędów poza Viewerem**.
  Szczegóły, zakres powtórzeń i ograniczenia: [karta](registration/reviews/REG-08a.md).
- Rzeczywisty Outdoor/CUDA: sześć pełnych prób (wzorzec, oba filmy, oba okna),
  zapis/odczyt sesji i render każdej klatki. Maksymalny błąd współrzędnej wzorca
  0,054/0,065 px. Na MOVIE_4 brakuje 3/5 relacji, lecz graf pozostaje połączony;
  MOVIE_8 bez braków. To nie jest jeszcze ocena wizualnej poprawy STM.
- [Instrukcja uruchomienia i ręcznej próby](registration/window-graph-manual.md),
  [wyniki i gotowe sesje w /tmp](registration/window-graph-results.md).
  Uruchomienie: `python -m stmviewer.main` w `netcat`, katalog `NEtCAT-viewer`.
- Qt offscreen sprawdzono automatycznie. Ręczny odbiór, Windows 11 i sprzęt
  docelowy z 8 GB VRAM pozostają niewykonane. REG-08b czeka na odbiór i zlecenie.
- Dwa niezależne przeglądy: Spec bez ustaleń; Standards wskazał duplikację skali,
  usuniętą lokalnym helperem `calibration.py`. Brak potrzeb zmian wspólnych.
- `proba.stmtrial.json`, `proba2.stmtrial.json`, `sesja.stmsession` pozostają
  nietknięte poza Git. Nie publikowano ani nie scalano branchy.

---

# Usunięcie REG-08 z planu — 2026-11-01

Użytkownik zlecił: **„usuń REG-08”**. Baza tej zmiany: `cc08ec9`;
gałąź `viewer/registration-difficult-movies`.

- Usunięto niewdrożony ticket diagnostyki trójek i jego wymaganie odbioru.
- Następny etap to [REG-08a — graf dopasowań](registration/issues/08a-window-graph.md),
  zależny bezpośrednio od odebranego REG-07. Nadal `ready-for-agent`, bez implementacji.
- REG-08a sam zapewnia podgląd niesąsiednich par; nie dodaje osobnego panelu
  trójek ani zapisu ich diagnostyki. Pozostają reszty rozwiązania grafu oraz
  ochrona przed zastosowaniem niesąsiedniej pary jako korekty przejścia REG-02a.
- Zaktualizowano kolejność, liczby etapów, odnośniki i notatkę badawczą.
  REG-08b/08c i dalsze etapy zachowują zakres oraz numerację. REG-06 pozostaje
  odłożony; REG-09 warunkowy. Liczba etapów podstawowych: 13.
- Zmiana wyłącznie dokumentacyjna. Sprawdzono zależności, linki i
  `git diff --check`; testów programu nie powtarzano. Brak zmian wspólnych.
- `proba.stmtrial.json`, `proba2.stmtrial.json`, `sesja.stmsession` pozostają
  nietknięte poza Git. Dokumentację zapisano w końcowym commicie tej zmiany.

Poniższe wpisy zachowują stan wcześniejszych decyzji i odbiorów.

---

# REG-07: odbiór manualny sesji — 2026-11-01

Użytkownik potwierdził: **„testy manualne ok”**.
[REG-07 — zapis i odczyt sesji](registration/issues/07-session-save-load.md)
ma status **done**. Baza tej aktualizacji: `cbb0f38`;
gałąź `viewer/registration-difficult-movies`.

- Zaktualizowano ticket, plan, README, instrukcję, raport i kartę odbioru.
- Zależność REG-08 jest spełniona. REG-08 pozostaje `ready-for-agent`,
  implementacja nierozpoczęta; wymaga osobnego zlecenia. REG-09 nadal jest
  warunkowy i wymaga decyzji użytkownika. REG-06 pozostaje odłożony.
- Potwierdzenie nie określa systemu, sprzętu ani odtwarzacza. Nie przypisujemy
  mu odbioru Windows 11, GPU 8 GB ani VLC na obu systemach.
- Kod bez zmian. Sprawdzono spójność statusów i linków oraz `git diff --check`;
  testów programu nie powtarzano. Dotychczasowe wyniki są w karcie REG-07.
- Pliki użytkownika `proba.stmtrial.json`, `proba2.stmtrial.json` i
  `sesja.stmsession` pozostają lokalne i poza commitem.
- Zmiany dokumentacji należą do końcowego commita tego odbioru;
  brak nowych potrzeb zmian wspólnych, publikacji lub scalenia.

---

# REG-07: zapis i odczyt przenośnej sesji — 2026-11-01

Stan przy przekazaniu implementacji: **ready-for-review**; późniejszy odbiór opisano powyżej.
Gałąź: `viewer/registration-difficult-movies`; baza przeglądu `750c474`.
Implementacja: **`5afa8c2`**, poprawka po przeglądzie: **`ea30b5f`**.
Końcowy commit dokumentacji domyka przekazanie; bez publikacji ani scalenia.

- Na zlecenie użytkownika usunięto bibliotekę pełnych prób A/B i format
  `*.stmtrial.json`. Wcześniejsze porównanie pary oraz ręczne korekty działają.
  Pliki użytkownika `proba.stmtrial.json`, `proba2.stmtrial.json` pozostawiono.
- **Zapisz sesję… / Otwórz sesję…** obsługują pojedynczy samowystarczalny
  `.stmsession`: original, gotowy aligned, pełne metadane, geometria, zastosowane
  korekty i widok. Wznowienie nie wymaga źródeł ani ponownego uruchomienia modelu.
- Zachowane są możliwość cofania/dalszych korekt oraz ograniczenie edycji po
  usunięciu klatki. MPP/AVI korzystają z odtworzonej aktywnej serii.
- Operacje działają w tle z postępem i anulowaniem. Zapis jest atomowy;
  odmowa odczytu nie zastępuje poprzedniej pracy. Format ZIP/JSON/NPY jest
  wersjonowany, bez pickle; limit obrazów po rozpakowaniu to 8 GiB.

- W pełnym zestawie **499 testów Viewera przeszło, 2 pominięto**.
  Łącznie repozytorium: **2285 passed, 14 failed, 16 skipped**, 293,90 s.
  Wszystkie 14 identyfikatorów błędów odpowiada wcześniejszej bazie
  MolTrack/NanoTrack; brak nowych regresji. Mypy (56 modułów), Ruff i diff-check
  przechodzą. Największy plik kodu: 971 linii.
- Pełne MOVIE_4 (362 klatki) oraz MOVIE_8 (84): bezstratny zapis/odczyt sesji,
  dwie ręczne poprawki i dalsza edycja, pełny MPP+JSON oraz zakres FFV1 poprawne.
  Świeży proces odczytał MOVIE_4 bez importu Torch/Kornia. Sprawdzono semantykę
  ścieżek Linux→Windows→Linux; to nie zastępuje fizycznego odbioru Windows.
- Spec: 0 usterek. Standards: 1 P2 dotyczące braku gotowych błędnych plików
  do manualnego odbioru, naprawione generatorem i ponownie sprawdzone;
  0 otwartych uwag. Próby Qt offscreen nie są odbiorem manualnym GUI/VLC.

[Instrukcja ręcznej próby](registration/session-manual.md),
[wyniki i artefakty](registration/session-results.md),
[przegląd i komendy](registration/reviews/REG-07-session.md).
Nie rozpoczęto REG-08. Brak wymaganych zmian modułów wspólnych.

Poprzednia implementacja REG-07 (`be0e253`, `11441b4`, dokumentacja `750c474`)
została wycofana na prośbę użytkownika; jej opis i wyniki pozostają w historii Git.
Poniższe wpisy opisują wcześniejsze etapy; aktualny zakres REG-07 określa
[ticket sesji](registration/issues/07-session-save-load.md).

---

# REG-06: odłożenie na życzenie użytkownika — 2026-10-31

Użytkownik zdecydował: **„na razie pominiemy 06”**.
Baza dokumentacji: `757f97a`, gałąź `viewer/registration-difficult-movies`.

- REG-06 ma status `planned` z jawną informacją o odłożeniu. Zachowano zakres
  i otwarte kryteria do ewentualnego powrotu; nie oznaczono ticketu jako wykonanego
  ani odebranego. Wznowienie wymaga osobnego zlecenia.
- REG-07 zależy teraz od odebranego REG-05. Najbliższy etap to zapis prób
  i porównanie pełnych filmów; implementacja pozostaje nierozpoczęta.
- REG-07 i dalsze tickety nie wymagają niewdrożonego interfejsu/danych kontroli
  REG-06. Jego zakres nie został przeniesiony do tych zadań. Przyszłe odwołania
  do tej kontroli są warunkowe; brak oceny nie oznacza zerowego błędu.
- Zachowano ręczny odbiór po każdym realizowanym tickecie, uczciwe opisy
  poparcia i ocen zależnych oraz bazowy checkpoint Outdoor. REG-05 pozostaje `done`.
- Zaktualizowano plan, README, protokół i zależności/zapisy dalszych ticketów.
  Kod aplikacji bez zmian. Kontrola: spójność zależności i statusów, linki,
  przegląd dokumentacji i `git diff --check`; testów programu nie powtarzano.
- Wszystkie zmiany należą do końcowego commita dokumentacyjnego tej pracy.
  Brak nowych zmian wymaganych od integracji; nie rozpoczęto REG-07.

---

# REG-05: odbiór manualny i ocena checkpointów — 2026-10-31

Użytkownik potwierdził: **„ok, outdoor wygląda o wiele lepiej. testy manualne 05 ok”**.
[REG-05](registration/issues/05-local-consensus.md) ma status `done`;
zależność [REG-06](registration/issues/06-independent-validation.md) jest spełniona.
REG-06 pozostaje `ready-for-agent`, bez rozpoczętej implementacji.

- Zaktualizowano ticket, jego kryteria, kartę odbioru, plan, README, raporty
  prób oraz blokadę REG-06. Kod aplikacji i ustawienia nie zmieniają się.
- Outdoor pozostaje bazą dalszych prób po ocenie użytkownika w osobnym
  porównaniu checkpointów. Nie utożsamiamy tej oceny z przewagą lokalnego
  konsensusu nad bazowym Deep. REG-05 zamknięto jako odebrany wariant
  eksperymentalny; zachowano ograniczenia 2/14 par i odmów pełnych filmów.
- Potwierdzenie nie zawiera osobnych ocen par/filmów, Windows, VLC ani GPU 8 GB;
  nie dopisano takich wyników. Dotychczasowe dowody automatyczne są zachowane.
- Implementacja REG-05: `303e401`, poprawka `75eb70f`, przekazanie `6e50e57`;
  eksperyment checkpointów i baza tej aktualizacji: `e2d49dd`. Zapis odbioru
  należy do końcowego commita dokumentacyjnego tej pracy.
- Sprawdzenia: spójność statusów i zależności, linki oraz `git diff --check`.
  Zmiana dotyczy dokumentacji; testów aplikacji nie powtarzano.
- Brak nowych potrzeb zmian wspólnych; nie rozpoczęto następnego ticketu.

---

# Porównanie checkpointów LoFTR — 2026-10-31

Na pytanie użytkownika o inne checkpointy wykonano osobny eksperyment,
na bazie `6e50e57`, gałąź `viewer/registration-difficult-movies`.
Kod aplikacji i ustawienia domyślne bez zmian; REG-05 nadal `ready-for-review`.

- Zweryfikowano Kornia 0.8.2: Outdoor/Indoor wymagają `temp_bug_fix=False`,
  Indoor New `True`. Sam wybór pliku Indoor New w obecnym GUI nie odtwarza
  poprawnego wariantu; `strict=True` nie wykrywa tej różnicy kodowania pozycji.
- Pobrano oficjalne Indoor i Indoor New z `kornia/loftr`, sprawdzono SHA-256
  względem metadanych LFS. Wagi pozostają lokalne w `data/weights/loftr/`, poza Git.
- Dodano odtwarzalny runner `tests/stmviewer/diagnostics/checkpoint_trial.py`:
  świeża kopia konfiguracji dla każdego modelu, jawny wariant, dotychczasowy
  publiczny przebieg Viewera i zakaz pobierania w trakcie prób.
  Raport oddziela rzeczywisty wariant/SHA od historycznej etykiety backendu.
- 42 próby par: Outdoor 14/14, Indoor 14/14, Indoor New 12/14. Sześć prób
  pełnych serii: Outdoor i Indoor ukończyły oba filmy, Indoor New tylko MOVIE_8;
  MOVIE_4 odmowa bieżącej 2→3 (źródłowej 4→5), bez niepełnego eksportu.
- Pięć MPP+metadanych w `data/loftr-checkpoint-comparison-20261031/`.
  Odczyt 5/5 PASS, metadane 976 klatek; 15 sprawdzonych obrazów ma wszystkie
  wartości i NaN zgodne z ponownym przesunięciem original. Kontrola zapisu
  nie oznacza potwierdzenia jakości rejestracji. Różnice XY są znaczne.
- CLI/`--help`, Ruff, linki dokumentacji i diffcheck PASS. Read-only przegląd
  runnera potwierdził zgodność konfiguracji oraz brak ingerencji w agregację
  i renderowanie. Nie zmieniano aplikacji i nie powtarzano jej pełnego zestawu testów.
- [Raport, źródła, pliki oraz sposób odtwarzania](registration/checkpoint-comparison-results.md).
  Ręczna ocena struktur, Windows/VLC i GPU 8 GB niewykonane. Próby używały
  RTX 5090 32 GB. Brak nowych zmian wymaganych we wspólnych modułach.
- Skrypt i dokumentacja należą do końcowego commita tej pracy; nie rozpoczęto
  nowego ticketu i nie uznano REG-05 za odebrany.

---

# REG-05: zgodność lokalnych fragmentów — 2026-10-31

Gałąź `viewer/registration-difficult-movies`, baza `a59029d`.
Implementacja: `303e401`; poprawka po przeglądzie: `75eb70f`.
Ten wpis należy do końcowego commita dokumentacji. Status **ready-for-review**;
ręczny odbiór użytkownika **niewykonany**, lista kryteriów pozostaje otwarta.

- Metoda **Deep Matcher + lokalne fragmenty (v1)** dla pary i całej serii:
  dokładny start Deep bez ECC, rozdzielone fragmenty, odporna agregacja,
  jedno XY, jeden końcowy render oryginałów. Bez lokalnej deformacji.
- GUI przełącza dokładny start/wynik i pokazuje fragmenty, wektory, stany oraz
  powody odmów. Diagnostyka odmowy nie nadpisuje prób i nie udaje wyniku.
  Poparcie estymatora nie jest niezależną kontrolą z REG-06.
- Błąd/anulowanie chroni kompletny aligned i korekty ręczne. Działają eksporty
  MPP/AVI bez nakładek; mapa fragmentów pozostaje historią w pamięci.
  Pełny zapis prób to REG-07. Brak pobierania wag lub cichego zastępstwa metody.
- Pełny Viewer: **474 PASS, 2 SKIP**; po poprawce tekstu **6 testów PASS**.
  Mypy strict **49 plików PASS**, Ruff/diffcheck PASS. Najdłuższy plik kodu: 908 linii.
  Pełne repo: **2258 PASS, 14 FAIL, 16 SKIP**. Te same 14 błędów poza Viewerem
  co REG-02a (11 MolTrack/SAM2, 3 NanoTrack). Szczegóły w karcie; brak zielonego
  odbioru całego repo. Przebieg repo poprzedza końcową poprawkę szumu/GUI;
  po nich sprawdzono pełny Viewer.
- Code-review `a59029d…75eb70f`: Standards 1 uwaga P3 naprawiona, 0 otwartych;
  Spec 0 uwag. Usunięto podwójny opis parametrów w szczegółach próby.
- Rzeczywiste wagi CPU/CUDA: local **2/14** wskazanych par, Deep 14/14.
  Pełny lokalny MOVIE_4 odmawia bieżącej 2→3 po pominięciu źródłowych 1/2;
  MOVIE_8 odmawia 1→2. Nie potwierdzono poprawy STM ani nie utworzono
  kompletnego lokalnego filmu tych pomiarów. Znana translacja i zaszumiony
  wzorzec kończą się; MPP translacji ma dokładny ponowny odczyt danych/NaN/geometrii.
- Automatyczne GUI XCB z rzeczywistymi wagami: odmowa MOVIE_4 29→30 oraz
  sukces wzorca, mapy i zachowanie wcześniejszych prób. To odrębne od odbioru
  użytkownika; Windows/VLC oraz GPU 8 GB nie zostały odebrane. Próby CUDA
  wykonano na RTX 5090 32 GB.
- Uruchomienie: aktywuj `netcat`, w katalogu Viewer wykonaj `python -m stmviewer.main`.
  [Instrukcja ręczna](registration/local-consensus-manual.md),
  [wyniki rzeczywistych prób](registration/local-consensus-results.md),
  [karta testów i przeglądu](registration/reviews/REG-05.md).
  Dane i raporty pozostają lokalne w `/tmp/stmviewer-reg05-*`; modele i pomiary poza Git.
- Brak nowych zmian wymaganych w kodzie wspólnym lub konfiguracji. REG-06
  nie został rozpoczęty; czeka na odbiór REG-05 i osobne zlecenie użytkownika.

---

# REG-04: odbiór manualny — 2026-10-31

Użytkownik potwierdził **„testy manualne 04 ok”**. [REG-04](registration/issues/04-multiscale-translation.md)
ma status `done`; zależność [REG-05](registration/issues/05-local-consensus.md)
została spełniona. REG-05 pozostaje `ready-for-agent`, bez rozpoczętej implementacji.

- Zaktualizowano ticket, kartę odbioru, plan, README, podsumowanie prób i blokadę
  REG-05. Potwierdzenie nie zawiera osobnych wyników platform, VLC ani ocen par;
  nie dopisano takich wyników i nie zmieniono wcześniejszych ograniczeń.
- Kod REG-04: `f639fd8` i `1a2766b`; baza tej aktualizacji dokumentacji: `61bd497`.
  Zapis odbioru należy do końcowego commita dokumentacyjnego tej pracy.
- Kontrola: spójność statusów, odnośniki i `git diff --check`. Kod bez zmian;
  testów aplikacji nie powtarzano. Nie rozpoczynano następnego ticketu.
- Brak nowych zmian wymaganych od sesji integracyjnej. Odbiory platform pozostają
  bez zmian; eksperymentalny wariant nie jest automatycznie lepszy od samego Deep.

---

# Plan: graf dopasowań i nowe modele — 2026-10-31

Na zlecenie użytkownika rozszerzono [plan rejestracji](registration/README.md)
na podstawie [przeglądu](registration-multiframe-research.md).
Baza: `903dfac`, gałąź `viewer/registration-difficult-movies`.

- Nowe tickety: REG-08a (graf okna 3/5 i LS), REG-08b (Huber/IRLS na tych
  samych pomiarach), REG-08c (zastosowanie, korekty ręczne, eksport), warunkowy
  REG-08d (dalsze odniesienia) oraz osobno REG-10 EfficientLoFTR, REG-11 RoMa v2,
  REG-12 MatchAnything-ELoFTR. Każdy ma publiczne granice TDD i próbę w GUI.
- REG-08 ma przygotowany zakres diagnostyczny i status `ready-for-agent`,
  po REG-07. REG-05 porównuje przestrzenne poparcie przede wszystkim z samym
  Deep; ECC pozostaje odrębnym wariantem. Aktualizowano zależności i protokół.
- Graf nie wymusza gładkiego dryfu. Brakujące relacje, rozłączenie i mosty są
  jawne. Ręczne korekty działają na zamrożonej bazie globalnych XY, z istniejącą
  propagacją na dalsze klatki, bez ponownego solvera i bez cichego nadpisywania.
- REG-08a/08b kończą się podglądem i lekkim zapisem próby; REG-08c dodaje jej
  zastosowanie i eksport. Modele REG-10–12 działają dla par, łańcucha i grafu,
  z lokalnymi wagami oraz kontrolowanym porównaniem przy stałej agregacji.
- Stan: REG-01/01a/02/02a nadal `done`, REG-04 nadal `ready-for-review`.
  Najbliższy krok to manualny odbiór REG-04, potem zlecenie REG-05.
  Rozszerzenie planu nie zalicza implementacji ani testów tych nowych funkcji.
- Kontrola tej zmiany: przegląd spójności zakresów i zależności, linki lokalne,
  statusy/checklisty oraz `git diff --check`. Kod aplikacji bez zmian;
  nie uruchamiano testów programu, nie pobierano modeli ani nie instalowano pakietów.
- Wszystkie zmiany należą do końcowego commita dokumentacyjnego tej pracy.
  Wspólne adaptery lub konfiguracja, jeśli okażą się potrzebne przy realizacji,
  pozostają zadaniem integracji opisanym w ticketach; teraz brak zmian wspólnych.

---

# Research: rejestracja wieloklatkowa i nowe matchery — 2026-10-31

Na zlecenie użytkownika, skillem `research`, przygotowano jeden
[przegląd źródeł i propozycję eksperymentów](registration-multiframe-research.md).
Baza: `5b7ab58`, gałąź `viewer/registration-difficult-movies`.

- Propozycja: osobny graf translacji z dopasowań do kilku klatek, odporny
  estymator globalnych XY i diagnostyka połączeń. Bez założenia gładkiego dryfu;
  odrębne są dopasowanie pary, łączenie wielu wyników oraz korekcja tearingu.
- Priorytet: obecny Deep jako stała baza, przestrzenne poparcie z REG-05,
  potem porównania EfficientLoFTR, RoMa v2 i MatchAnything. Materiał rozdziela
  wyniki autorów, wcześniejsze próby lokalne i nieprzetestowane propozycje.
- Uwzględniono błędy okresowe i skorelowane artefakty, rozłączny graf,
  ponowne użycie modelu/cech, ręczne korekty oraz jeden render z oryginałów.
- Nie zmieniano kodu, ticketów, zależności ani statusu odbioru REG-04.
  Nie pobierano modeli i nie wykonywano benchmarków nowych algorytmów.
- Kontrola dokumentacji: źródła pierwotne, przegląd merytoryczny, linki lokalne
  i `git diff --check`. Testy aplikacji nie są wymagane dla tej zmiany dokumentacji.
- Wnioski należą do końcowego commita dokumentacyjnego tej pracy;
  brak zmian wymaganych w modułach współdzielonych na etapie research.

---

# REG-04: Deep Matcher + doprecyzowanie ECC — 2026-10-31

Gałąź `viewer/registration-difficult-movies`, baza `29d7fc9`.
Kod: `f639fd8`, poprawki po przeglądzie `1a2766b`; niniejszy wpis należy
do końcowego commita dokumentacji. Status **ready-for-review**;
odbiór użytkownika pozostaje **niewykonany**, lista kryteriów otwarta.

- Nowa metoda Deep Matcher + ECC (v1) dla pary i całego filmu: dokładny start
  Deep, ECC na oryginałach, całkowite końcowe XY i jeden render aligned.
  Lokalne wagi, Auto/CPU/CUDA dla Deep, ECC CPU, brak zastępstwa i pobierania.
- Okno pary przełącza **Wynik po ECC / Start Deep tej próby**, nie przelicza
  modelu i nie nadpisuje zachowanej próby. Wspólny widok oraz jawne start,
  poprawka, wynik, statusy i ustawienia. Jakość pozostaje niezweryfikowana.
- Błędy/anulowanie chronią poprzedni kompletny film i ręczne korekty.
  Ręczne korekty zachowują diagnostykę automatyczną jako historię.
  MPP/AVI działają; metadane zachowują nazwę/wersję, XY, geometrię i status.
- Finalny Viewer: **455 PASS, 2 SKIP**; mypy strict **46 plików PASS**,
  Ruff i diffcheck PASS. Najdłuższy zmieniony plik kodu: **902 linie**.
- Pełne repo przed końcowymi poprawkami: **2236 PASS, 18 FAIL, 16 SKIP**.
  Cztery asercje starej listy metod Viewera zaktualizowano i sprawdzono
  w finalnym pełnym Viewerze. Pozostałe 14 identyfikatorów błędów jest
  identyczne z REG-02a: 11 MolTrack/SAM2, 3 NanoTrack. Szczegóły i polecenia
  znajdują się w karcie; nie deklarujemy zielonego odbioru całego repo.
- Code-review od `29d7fc9` do `1a2766b`: Standards 2 uwagi naprawione,
  Spec 1 uwaga naprawiona; oba końcowe przeglądy mają **0 otwartych uwag**.
  Poprawka P2 zachowuje numer pary i etap przy odmowie ECC z powodu tekstury.
- Rzeczywiste próby: LoFTR+ECC CPU/CUDA, 14 wybranych par, pełne MOVIE_4
  po usunięciu pierwszych dwóch klatek i MOVIE_8, oba warianty Deep/hybryda,
  odczyt czterech MPP. Automatyczne Qt xcb i oględziny zrzutów pary 29→30.
  Dane i wyniki pozostają lokalne w `/tmp/stmviewer-reg04-*`.
- Ograniczenia: wzorzec nieruchomych pasów pokazuje pogorszenie przez ECC;
  OpenCV nie ujawnia zakończenia przez limit iteracji zamiast epsilon.
  Ręczna ocena struktur/tearing i odtwarzanie VLC pozostają do wykonania.
  Nie wykonano próby Windows w REG-04. REG-05 czeka na odbiór użytkownika.
- Brak zmian wspólnych modułów/konfiguracji i brak potrzeb integracyjnych.
  Program uruchamia się z `netcat`: `python -m stmviewer.main`.

[Instrukcja manualna](registration/deep-ecc-manual.md),
[karta testów i przeglądów](registration/reviews/REG-04.md),
[rzeczywiste próby i wyniki](registration/deep-ecc-results.md).

---

# Przekazanie — STM Viewer

## Plan REG-04: Deep Matcher + doprecyzowanie ECC — 2026-10-31

Na zlecenie użytkownika zmieniono [REG-04](registration/issues/04-multiscale-translation.md)
z ogólnej wieloskalowości na eksperyment Deep Matcher → ECC. Status
`ready-for-agent`, zależność REG-02a spełniona. **Implementacja nierozpoczęta**;
użytkownik zlecił na razie zmianę ticketu. Numer i dotychczasowa ścieżka pliku
pozostają stabilne. Baza tej zmiany dokumentacji: `2790e16`.

- Deep daje początkowe XY, ECC dostaje je jawnie i zwraca końcową translację.
  Porównanie używa dokładnego startu tej samej próby; wyższy score ECC nie
  stanowi werdyktu poprawy. Bez zewnętrznej piramidy i bez ręcznych masek.
- Para oraz pełna seria, końcowe XY sumowane raz, jeden render z oryginałów.
  Brak akceptacji każdej pary; jawnie wybrana hybryda podmienia aligned po
  pełnym sukcesie. Błąd/anulowanie chronią wcześniejszy film; bez cichej
  zamiany na sam Deep lub Phase.
- Ticket określa lokalne wagi, urządzenia, postęp, niepewność, granice testów
  i odbiór obu filmów, w tym wskazane przez użytkownika przejścia MOVIE_4.
  REG-05 zachowuje porównanie z wynikiem REG-04; REG-07 zachowa oba etapy próby.
- Zaktualizowano README aplikacji i planu oraz propozycję dalszych badań.
  Zmiany dotyczą dokumentacji; testów kodu ani GUI nie uruchamiano.
  Sprawdzenia dokumentacji: odnośniki, zależności, zgodność zakresu i diff.

Brak zmian współdzielonych ani nowych wyników pomiarowych. Wcześniejszy
REG-03 pozostaje wycofany, a statusy REG-02a i odbiorów platform bez zmian.

## Wycofanie REG-03 na życzenie użytkownika — 2026-10-31

Użytkownik zrezygnował z rejestracji z ręcznymi maskami i polecił usunąć
ostatnią implementację oraz maski z planu. Cofnięto zmiany commitów
`868dae4`, `b318e1d`, `5bc7175`, `61fa45c`, `3455dbe` nową zmianą w Git,
z zachowaniem dotychczasowej historii.

- Kod `stmviewer/` i testy `tests/stmviewer/` są identyczne jak w `270097b`,
  czyli po zaakceptowanym REG-02a. Usunięto edytor, nową metodę, powiązane
  kontrolki, backend, testy, wzorzec i diagnostykę REG-03.
- Z planu usunięto ticket REG-03 i wymagania edytowalnych masek w dalszych
  zadaniach. Następny [REG-04](registration/issues/04-multiscale-translation.md)
  zależy bezpośrednio od REG-02a i czeka na osobne zlecenie. Numeracja zostaje.
  Fragmenty kontroli i opis ważności próbek aligned nadal należą do ich
  dotychczasowego zakresu; ręczne korekty filmu działają jak w REG-02a.
- Usunięto instrukcję i kartę prób wycofanej implementacji. Wyniki historyczne
  pozostają w commitach oraz lokalnym `data/registration-reg03-review/`.
- Sprawdzenia po wycofaniu: **434 PASS, 2 SKIP**, pełny `tests/stmviewer`
  (63,36 s). Pominięto opcjonalne próby lokalnych wag LoFTR CPU/CUDA.
  Mypy strict: **43 pliki bez błędów**. Potwierdzono pusty diff kodu/testów
  względem `270097b`. Nie ponawiano testów innych aplikacji: brak zmian
  wspólnych, przywrócony kod identyczny z odebranym REG-02a.
- Widoczne Qt/xcb sterowane skryptem: sześć dotychczasowych metod, brak
  kontrolek masek, Phase i ręczna korekta +1X przez „Zastosuj do filmu” PASS.
  Na cpu.mpp końcowe XY: (0,0), (3,−1), (0,1). To próba automatycznie
  sterowana w rzeczywistym oknie, nie nowy odbiór użytkownika.
- Log testów oraz skrypt/zrzuty kontrolne: `data/registration-reg03-removal-review/`.
  Sprawdzono 295 lokalnych odnośników; diff bez błędów formatowania.
  Niezależny przegląd wycofania kodu i zmiany planu: bez uwag.

Start w `netcat`: `python -m stmviewer.main`. Próba kontrolna: otworzyć
`tests/stmviewer/fixtures/registration/cpu.mpp`, sprawdzić brak „Edytuj maski…”
i metody „Korelacja z maskami”, wykonać Phase, otworzyć „Porównaj parę…” i użyć
ręcznej korekty według [instrukcji REG-02a](registration/manual-movie-corrections-manual.md).
Nie wykonywano nowego odbioru użytkownika ani prób Windows/VLC. Brak zmian
współdzielonych. Starsze wpisy poniżej opisują ówczesny stan; wycofany REG-03
nie należy już do aktualnego planu.

## REG-02a: odbiór użytkownika — 2026-10-31

Użytkownik potwierdził **„testy manualne ok”**. [REG-02a](registration/issues/02a-manual-movie-corrections.md)
zamknięto jako `done`. Po późniejszej rezygnacji z REG-03 następnym etapem jest
[REG-04](registration/issues/04-multiscale-translation.md), którego zależność
od zaakceptowanego REG-02a jest spełniona.

Odebrany kod: `976386c` i `f94b0a8`; dokumentacja wykonania: `8df875c`.
[Pełna karta](registration/reviews/REG-02a.md#ręczny-odbiór-użytkownika) zachowuje
wcześniejsze wyniki automatyczne i próby GUI. Użytkownik nie podał osobno systemu,
VLC ani wyników każdego kroku; nie dopisano takich deklaracji. Statusy wcześniejszych
19–21 i odbiorów platform pozostają bez zmian.

Zmiana dotyczy wyłącznie dokumentacji; sprawdzono odnośniki i diff, bez ponawiania
testów kodu. Brak zmian współdzielonych. Starsze wpisy poniżej opisują stan
w chwili ich zapisania.

## REG-02a: ręczne korekty filmu — 2026-10-31

[Ticket](registration/issues/02a-manual-movie-corrections.md): `ready-for-review`.
Implementacja `976386c`, poprawka po przeglądzie `f94b0a8`, baza `c2c8f1f`.
Gałąź `viewer/registration-difficult-movies`; bez zmian współdzielonych.
REG-03 czeka na ręczny odbiór użytkownika.

- Okno pary: **Popraw dopasowanie z filmu → Zakończ korektę → Zastosuj do filmu**.
  XY pary zastępuje wcześniejsze; różnica wpływa na jej drugą i dalsze klatki.
  Usunięcie korekty jednej pary zachowuje pozostałe. Film renderowany z original.
- Wątek z postępem/anulowaniem w obu oknach, podmiana po sukcesie, stare próby
  zablokowane. Po usunięciu klatki zachowany aligned/eksport; dalsza korekta
  wymaga nowej pełnej rejestracji. Udany import i nowa rejestracja resetują stan.
- MPP V4 zapisuje wspólną lekką historię bazy/nadpisań, także po usunięciu
  klatek. Zgodność V1–V3 zachowana; stary Viewer odrzuci dodatek V4 i otworzy
  sam MPP bez pełnej historii/braków. AVI używa poprawionego aktywnego filmu.
- Automatyczne: rdzeń 15 PASS, eksport 45 PASS, końcowe powiązane GUI 36 PASS;
  mypy strict 43 PASS, Ruff PASS, pliki kodu najwyżej 893 linii.
  Pełne repo: 2220 passed, 14 failed, 16 skipped (271,36 s); te same 14 błędów
  MolTrack/NanoTrack co przy REG-02, bez nowych błędów Viewera. Pierwsza próba
  przerwana SIGTERM, ponowiona do pełnego podsumowania.
- Rzeczywisty MOVIE_4 źródłowe 3–364: Deep Matcher CUDA/RTX 5090 ukończył 362 klatki;
  kontrolna +1X, rzeczywiste anulowanie, cofnięcie oraz pełny MPP i FFV1 roundtrip
  poprawne. To ocena funkcji, nie dowód poprawy dopasowania wzrokowego.
- Qt/xcb sterowane skryptem: CPU/MOVIE_4, anulowanie przyciskiem, błąd/ponowienie,
  widoczna historia MPP; obejrzane zrzuty 1180×820 i 1080×760. Nie zastępuje odbioru
  użytkownika. VLC/Windows w tym tickecie niewykonane; nowe próby MOVIE_8 niewykonane.
- Code-review: Standards: 1 sugestia naprawiona, 0 otwartych; Spec: 0 uwag.

Start: `python -m stmviewer.main` w `netcat`.
[Instrukcja manualna](registration/manual-movie-corrections-manual.md),
[pełna karta sprawdzeń](registration/reviews/REG-02a.md).
Artefakty lokalne: `data/registration-reg02a-review/` (duże filmy poza Git).
Brak potrzebnych zmian integracyjnych. Statusy wcześniejszych 19–21 bez zmian.

## Plan: REG-02a — ręczne korekty filmu — 2026-10-31

Na zlecenie użytkownika dodano [REG-02a](registration/issues/02a-manual-movie-corrections.md)
między odebrany REG-02 a REG-03. Status `ready-for-agent`, implementacja
nierozpoczęta. REG-03 wymaga jego wykonania i manualnego odbioru; kolejne numery
pozostają bez zmian. Baza dokumentacji `822ce96`, gałąź `viewer/registration-difficult-movies`.

- Kompletny automatyczny aligned → ręczna korekta pary → jawne Zastosuj do filmu.
  XY pary zastępuje dotychczasowe; różnica przesuwa tę i dalsze klatki. Ponowienie
  nie dubluje korekty; można usunąć nadpisanie jednej pary, zachowując pozostałe.
- Renderowanie z oryginałów, nowa geometria i ważność próbek, postęp/anulowanie,
  atomowa podmiana oraz ręczne pochodzenie i brak pewności w filmie i eksporcie.
  Samo Zakończ korektę zachowuje diagnostyczny zakres REG-01a.
- Po usunięciu klatki gotowy aligned/eksport pozostaje; dalsze korekty wymagają
  nowej pełnej rejestracji. Stara próba związana z innym wynikiem nie może być użyta.
- Ticket zawiera publiczne granice testów i odtwarzalny scenariusz cpu.mpp oraz
  poprawionego MOVIE_4 (źródłowe 3–364), w tym wskazane przez użytkownika przejścia.
  REG-07 rozszerzono o zachowanie zastosowanych nadpisań w dokumentach prób.

Zmiana tylko planu: aplikacja nie ma jeszcze Zastosuj do filmu. Sprawdzono
spójność zależności, odnośniki i diff; testów kodu nie uruchamiano. Brak zmian
współdzielonych. Statusy odbioru REG-01/01a/02 i wcześniejszych 19–21 bez zmian.

## REG-02: Odbiór i obserwacje MOVIE_4 — 2026-10-31

Użytkownik potwierdził „testy manualne ok”. [REG-02](registration/issues/02-unnormalized-correlation.md)
ma status **done**; REG-03 jest odblokowany i czeka na osobne zlecenie.
Odebrany kod `d85ba1b`, `bcf0e70`; dokumentacja `ad87192`.
[Pełna relacja i miejsca kontroli](registration/reviews/REG-02.md#ręczny-odbiór-użytkownika).

Phase i wariant bez normalizacji nie różnią się znacząco na MOVIE_4: nadmierny
ruch do około klatki 150, później lepiej, nadal do poprawy. ECC podobnie słabo.
Optical Flow i Tile+RANSAC dają mniej pozostałego ruchu; Deep Matcher oceniono
najlepiej w obejrzanych pierwszych 100 klatkach. Zapisano problemy 29→30, 35→36,
44→45→46, 61→62, 94→95→96→97. Użytkownik potwierdził numerację po usunięciu
dwóch klatek: źródłowo odpowiednio 31→32, 37→38, 46→47→48, 63→64,
96→97→98→99. Granica bieżącej klatki 150 to źródłowa 152.
Nie uogólniamy oceny Deep na pozostałą część filmu ani na MOVIE_8.

Pierwsze dwie źródłowe klatki MOVIE_4 błędnie dołączono z późniejszego etapu
pomiaru. Dalszy protokół obejmuje źródłowe 3–364 (362 klatki), usunięcie w GUI
przed ponowną rejestracją, bez zmiany źródłowego MPP. Zachowano historyczne
wyniki 364 klatek; dawna odmowa Deep na źródłowej 2→3 nie jest kryterium jakości
poprawionej serii. Zaktualizowano bieżące instrukcje prób.

Na pytanie użytkownika potwierdzono: ręczne dopasowanie nadal dotyczy tylko
pary i nie podmienia pełnego aligned ani eksportu MPP/AVI. REG-07 zapisuje próby,
nie stosuje ręcznej korekty do filmu. Nie rozpoczęto nowej implementacji.

Zmiany wyłącznie dokumentacyjne; sprawdzono statusy, lokalne linki i diff.
Testów kodu nie ponawiano. Brak zmian współdzielonych; statusy 19–21 bez zmian.
Poniższe wpisy pozostają historią etapów sprzed tego odbioru.

## REG-02: Korelacja bez normalizacji — 2026-10-31

[Ticket](registration/issues/02-unnormalized-correlation.md): **ready-for-review**.
Implementacja `d85ba1b`, poprawki `bcf0e70`, baza `e1d42d4` na gałęzi
`viewer/registration-difficult-movies`. Końcowy commit dokumentacji podany w sesji.
[Instrukcja manualna](registration/unnormalized-correlation-manual.md),
[karta wyników i Standards/Spec](registration/reviews/REG-02.md).

- Osobna metoda **Korelacja bez normalizacji (v1)** dla pary i całej serii;
  publiczny backend NanoTrack z normalization=None, Phase nadal domyślny.
- Niezweryfikowana pewność bez fałszywego wskaźnika fazowego; propagacja do
  skumulowanych XY, podglądu i MPP. Zachowane geometria, braki, postęp,
  anulowanie, wcześniejszy aligned, MPP/AVI i oryginalne pliki.
- 5 nowych scenariuszy i rozszerzenie istniejących prób GUI; końcowy zestaw
  wybranych testów: 48 passed. Mypy strict 38, Ruff i limity plików PASS (maks.856).
  Pełne repo: **2196 passed, 14 failed, 16 skipped**, 263,52 s; te same 14 nazw
  błędów MolTrack/SAM2 i NanoTrack co wcześniej. Przed pełnym przebiegiem naprawiono
  kolizję importu fixture podczas zbierania testów.
- Reproduktor MOVIE_8 1→2: nowy wariant (+13,55;+0,25), 0,51 px od lokalnego
  konsensusu; Phase zachowuje oczekiwany RED. To lokalny przypadek.
- Rzeczywiste Qt xcb sterowane skryptem: cpu.mpp, porównanie kart/zoom/gamma,
  pełne MOVIE_4 i MOVIE_8, rzeczywiste anulowanie, eksport MPP/AVI i ponowny
  odczyt PASS. Wersja v1 ponownie sprawdzona na cpu. Zrzuty 1080×760/1180×820
  bez przycinania nowej nazwy. Artefakty `data/registration-reg02-review/`.
- Standards 0; Spec: brak wersji ustawień naprawiony, 0 otwartych uwag.

**Ręczny odbiór użytkownika oczekuje**; REG-03 zablokowany. Pełne zakończenie
obliczeń nie jest oceną jakości dopasowania wszystkich struktur. Windows i VLC
nie były sprawdzane w tej sesji. MPP z null w jakości wymaga bieżącego Viewera
do odtworzenia całego dodatku; wcześniejsze czytniki mogą go odrzucić, zgodnie
z [opisem formatu](mpp-metadata-format.md). Bez nowych zmian współdzielonych.
Statusy wcześniejszych ticketów 19–21 pozostają bez zmian.

## REG-01a: Odbiór manualny układu C — 2026-10-31

Użytkownik potwierdził „testy manualne ok” po wdrożeniu układu C.
[REG-01a](registration/issues/01a-manual-alignment.md) ma status **done**.
REG-02 jest odblokowany, pozostaje `ready-for-agent` i czeka na osobne zlecenie.
Kod układu: `b7aaf37` i `a9a072f`; dokumentacja wdrożenia: `8574886`.
Gałąź: `viewer/registration-difficult-movies`.

Zaktualizowano ticket, mapę, karty odbioru i odnośniki statusu w instrukcjach.
Sprawdzono spójność statusów, lokalne odnośniki i `git diff --check`. Zmiana
wyłącznie dokumentacyjna; nie ponawiano testów kodu. Wcześniejsze wyniki:
Viewer 398 passed, 2 skipped; pełne repo 2184 passed, 14 istniejących błędów
poza Viewerem, 16 skipped; Standards 0 i Spec 0.

System, szczegółowe dane i wyniki poszczególnych kroków nie zostały podane
w potwierdzeniu użytkownika. Odbiór funkcji nie oznacza oceny fizycznej
poprawności wszystkich XY ani zakończenia odbiorów platformowych. Brak
nowych zmian współdzielonych; tickety 19–21 zachowują dotychczasowe statusy.
Poniższe wpisy opisują wcześniejsze etapy, w tym stan przed odbiorem.

## REG-01a: Wybrany układ C — 2026-10-31

Użytkownik wybrał C. Produkcyjne wdrożenie `b7aaf37`, poprawki `a9a072f`,
baza `9b47c15`; gałąź `viewer/registration-difficult-movies`.
[Karta, przegląd i sprawdzenia](registration/reviews/REG-01a-layout-c.md),
[aktualna instrukcja manualna](registration/manual-alignment-manual.md).

Karty wyników i metoda po lewej, podgląd po prawej, ręczne sterowanie pod nim.
Opisowe nazwy zastępują A/B; „Zachowaj do porównania” jest opcjonalne, a „Zakończ
korektę” ustawia bieżący wynik pary. Obliczenia, szkic, pełny aligned i eksport
zachowują wcześniejsze działanie. Nie scalono kodu HTML prototypu do aplikacji.

13 testów GUI PASS; pełny Viewer 398 passed, 2 skipped. Pełne repo 2184 passed,
14 failed, 16 skipped; 14 nazw błędów identycznych z poprzednim REG-01a.
Mypy strict 38, Ruff i limit plików bez uwag; największy plik 472 linie.
Niezależny przegląd: Standards 0, Spec 0. Qt xcb: cpu.mpp i MOVIE_8 16→17,
oba rozmiary okna, zachowanie podglądu, szczegóły i długie ścieżki wag sprawdzone.
Naprawiono poziome przewijanie i przycięcie opisu korekty; po poprawkach ponowne
oględziny oraz testy GUI/Viewer. Artefakty `data/registration-pair-layout-c/`.

**Ręczny odbiór użytkownika nadal oczekuje.** Wybór projektu C nie oznacza odbioru
implementacji. REG-01a ready-for-review, REG-02 pozostaje zablokowany. Wspólnych
zmian nie potrzeba. Końcowy commit dokumentacji podany w sesji.

## Prototyp nazw okna dopasowania — 2026-10-31

Na zlecenie użytkownika przygotowano 3 klikalne warianty okna REG-01/REG-01a,
z opisowymi nazwami wyników zamiast A/B, „Zakończ korektę” oraz wyraźnym zakresem
pary. [Opis, uruchomienie i źródło](registration/pair-window-prototype.md).
Prototyp: `prototype/stmviewer-pair-naming`, commit `dd8b48f`, baza `b0ef173`;
pozostaje poza gałęzią aplikacji. Tutaj zapisano wyłącznie dokumentację i odnośnik.

Qt WebEngine: 3 układy 1360×1000, B także 980×850, obejrzane zrzuty i ścieżka
obliczenie/zachowanie/ręczna korekta/wybór wyniku; brak błędów JS. Audyt odczytowy
zachowania głównych funkcji. Bez testów prototypu i bez produkcyjnego zestawu testów.
Lokalny serwer: 127.0.0.1:8783; artefakty `data/registration-pair-ui-prototype/`.
Rekomendacja: C; **decyzja użytkownika oczekuje**. Nie wdrożono żadnego wariantu.
REG-01a nadal ready-for-review, REG-02 czeka. Brak potrzebnych zmian współdzielonych.

## REG-01a: Ręczne dopasowanie pary — 2026-10-31

[Ticket](registration/issues/01a-manual-alignment.md): **ready-for-review**.
Implementacja `846a479`, poprawki `2276755`, baza `c5ec70a` na
`viewer/registration-difficult-movies`. Końcowy commit dokumentacji podany w sesji.
[Instrukcja manualna](registration/manual-alignment-manual.md),
[karta i Standards/Spec](registration/reviews/REG-01a.md).

- Kroki ±1 px X/Y w oknie porównania; start od zera albo kopii wybranej próby.
  Ułamkowe XY zachowane, szkic oddzielny od A/B, reset/odrzucenie i zastosowanie B.
- Pochodzenie ręczne, początkowe XY, suma korekt, końcowe XY oraz jawny brak
  automatycznej jakości. Każdy podgląd powstaje z oryginałów, bez kumulacji interpolacji.
- Zachowane A, widok/gamma/kontrast i główny aligned; rzeczywiste MPP/AVI przed/po
  ręcznej korekcie mają te same dane. Manual działa bez wag oraz po błędzie ECC.
- 14 nowych testów; po poprawkach 28 testów par PASS. Viewer: **398 passed, 2 skipped in 63.41s (0:01:03)**.
  Pełne repo: **14 failed, 2184 passed, 16 skipped in 276.92s (0:04:36)**; 14 nazw błędów identycznych z REG-01
  (MolTrack/SAM2 i NanoTrack). Mypy strict 38, Ruff i limit długości bez uwag.
- Qt xcb sterowane skryptem: 6 stałych par obu MOVIE, ręczne sterowanie po
  rzeczywistym błędzie ECC 2→3 MOVIE_8, ułamkowy wzorzec i układ kontrolek PASS.
  SHA źródeł bez zmian. To próby automatyczne, jakość ręcznego dopasowania nieoceniana.
- Niezależny przegląd: Standards 2 uwagi naprawione, Spec 0; po poprawkach brak
  otwartych uwag. Największy zmieniony plik 409 linii.

Uruchom `python -m stmviewer.main` w `netcat`. Na cpu.mpp wybierz klatkę 2,
**Porównaj parę… → Zacznij od zera → X+ → X+ → Y−**: XY=(2,−1).
Sprawdź zastosowanie B/korektę/reset, a potem obie serie pomiarowe według instrukcji.
Dostarczony launcher `PYTHONPATH=. python tests/stmviewer/manual_pair_fixture.py`
zapewnia deterministyczny ułamkowy początek. Artefakty lokalne:
`data/registration-manual-pair-review/`.

**Ręczny odbiór użytkownika: oczekuje.** Windows i VLC niewykonane w tym zadaniu.
REG-02 czeka na odbiór REG-01a; zakres ręcznego składania filmu i zapis prób na dysk
pozostają poza REG-01a. Brak nowych zmian współdzielonych; statusy 19–21 bez zmian.

## Plan: REG-01a — ręczne dopasowanie pary — 2026-10-30

Na zlecenie użytkownika dodano [REG-01a](registration/issues/01a-manual-alignment.md)
między zakończony REG-01 a REG-02. Status nowego ticketu `ready-for-agent`;
implementacja nierozpoczęta. Numery pozostałych zadań pozostają zachowane.

- To samo okno porównania, nieruchome odniesienie i przesuwana klatka,
  nakładka/przełączanie, kroki ±1 piksel original w X/Y niezależnie od zoomu.
- Ręczny szkic od zera lub kopii wybranej próby, reset/odrzucenie, zastosowanie
  jako nowe B. Zachowane przypięte A, pochodzenie i ułamkowe początkowe XY;
  ręczny wynik ma jawny brak automatycznej oceny jakości.
- Zakres: próba jednej pary. Pełny aligned i eksport pozostają niezależne;
  ręczne składanie całego filmu nie wchodzi do tego ticketu. REG-07 obejmuje
  zapis/odczyt zatwierdzonego ręcznego XY, źródła i łącznej korekty.
- Zaktualizowano kolejność i zależność REG-02, kontrakty planu, protokół
  odbioru i REG-07. Nowy ticket ma publiczne granice TDD oraz wykonalną
  próbę GUI na cpu.mpp i obu MOVIE. REG-01 zachowuje status done.

Baza zmiany planu: `ef5f861`, gałąź `viewer/registration-difficult-movies`.
Sprawdzono spójność zależności, odnośniki i `git diff --check`; niezależny
audyt wskazał rozdzielenie obrazów od prób A/B, szkicu od wyniku, jednostki
źródłowe, ułamkowy punkt startu i pochodzenie ręczne. Zmiana tylko dokumentacji,
bez uruchamiania testów kodu ani deklarowania odbioru nowej funkcji.
Commit dokumentacji podany w wiadomości sesji; nowe zmiany współdzielone nie są wymagane.

## REG-01: Porównanie par klatek — 2026-10-28

[Ticket](registration/issues/01-pair-comparison.md): **done**.
Użytkownik potwierdził 2026-10-29: „testy manualne ok”. Odbiór obejmuje
implementację `4a61ba4` i przekazanie `893b4b1`. Nie podano systemu ani
szczegółowych ustawień próby; odbiory platform pozostają osobne.
Aktualizacja potwierdzenia dotyczy dokumentacji: sprawdzono spójność statusów,
odnośniki i `git diff --check`; nie ponawiano testów kodu.
Implementacja **`4a61ba4`**, baza **`b1050103d255f366697887619590bd76d734557e`**,
gałąź `viewer/registration-difficult-movies`. Commit końcowego przekazania
podany w wiadomości sesji. [Próba manualna](registration/pair-comparison-manual.md),
[karta i przegląd Standards/Spec](registration/reviews/REG-01.md).

- Osobny podgląd wybranej sąsiedniej pary: źródłowe numery, metoda i jej ustawienia,
  obliczenie w tle, anulowanie; oryginały nie wymagają pełnej rejestracji filmu.
- Przed/po XY, odniesienie/ruchoma/nakładka 50/50, lekkie próby A/B. Stałe pole
  odniesienia, wspólny kontrast oryginałów, gamma, zoom i proporcje; informacja
  o części wspólnej. Obrazy wychodzące poza ten kadr są przycięte tylko w podglądzie.
- Błąd/anulowanie zachowują poprzedni wynik. Escape i zamknięcie czekają na backend.
  Nowy udany import/usunięcie unieważniają próby. Główny aligned i eksport pozostają
  niezależne. Nie zmieniono algorytmów ani modułów współdzielonych.

Sprawdzenia automatyczne: 14 nowych testów passed; testy Viewera łącznie 384 passed,
2 skipped (szczegóły poprawionego PYTHONPATH w karcie); mypy strict 36 plików,
Ruff i limity długości bez uwag. Pełne repo: **2170 passed, 14 failed, 16 skipped**.
Nazwy 14 błędów MolTrack/NanoTrack identyczne z końcową próbą ticketu 19.
Przeglądy niezależne: Standards 0, Spec 0. Największy zmieniony plik: 850 linii.

Rzeczywiste GUI Qt xcb sterowane skryptem: 16 prób, oba MOVIE, znane XY wzorca,
A/B, Deep Matcher CUDA, rzeczywiste błędy ECC/Deep i anulowanie Optical Flow (~8 s).
SHA-256 wejść bez zmian. Zrzuty obejrzane przez agenta; końcowy układ kontrolek
sprawdzony ponownie. Artefakty lokalne: `data/registration-pair-review/`.
Wzorzec anulowania: `data/registration-pair-cancel.mpp`, generator wersjonowany.

**Odbiór manualny użytkownika: zaliczony 2026-10-29.** Uruchomienie: `python -m stmviewer.main`
w `netcat` z katalogu Viewera. Otwórz cpu.mpp, wykonaj pełne Phase, wybierz klatkę 2,
**Porównaj parę… → Oblicz parę → Przypnij B jako A**; porównaj kolejną metodę
i wykonaj dalsze kroki instrukcji na obu MOVIE. Automatyczne GUI nie zastępuje odbioru.
Windows nie został zweryfikowany przez agenta; systemu ręcznej próby nie podano.
Po dodaniu REG-01a kolejny REG-02 czeka na jego ręczny odbiór; historyczne statusy 19–21 bez zmian.
REG-01 nie wymaga nowej zmiany współdzielonej; problem czytnika z ticketu 19 pozostaje.

## Plan rozwoju rejestracji — 2026-10-28

Zlecenie użytkownika: rozpisać poprawę rejestracji trudnych filmów na tickety,
z ręczną oceną wpływu i jakości wizualnej po każdym. Powstał
[plan REG-01–09](registration/README.md), dziewięć oddzielnych ticketów i
[wspólny protokół manualny](registration/manual-protocol.md).

- REG-01–07: porównanie par A/B, korelacja bez normalizacji, ręczne maski,
  wieloskalowość, lokalny konsensus, kontrola na wydzielonych fragmentach,
  zapis prób i odbiór pełnych MOVIE_4/MOVIE_8.
- REG-08/09: warunkowe rozpoznanie spójności kilku klatek i deformacji pasów.
  Rzeczywista korekcja tearingu wymaga późniejszej decyzji i specyfikacji
  geometrii oraz eksportów; nie może być opisana pojedynczym XY.
- Po każdym etapie `ready-for-review` i ręczny odbiór przed następnym.
  Oddzielamy działanie funkcji od wyniku lepiej/podobnie/gorzej/niejednoznacznie.
  Nowe warianty nie stają się automatycznie domyślne.
- Uwzględniono limit 1500 linii, porównanie bez dodatkowych pełnych stosów,
  kontrolę przypadków błędu i ochronę istniejących wartości oraz eksportów.
- Dwa niezależne przeglądy planu: granulacja/kontrakty i wykonalność prób
  manualnych. Poprawiono przygotowanie wcześniejszego aligned, wykonalność
  anulowania, brak pełnego wyniku, niezależność danych kontrolnych oraz
  rozdzielenie nazw metody od napisów AVI.

Baza planowania: `81ff1a0`, gałąź `viewer/registration-difficult-movies`.
Nie rozpoczęto implementacji ani nie wykonano odbiorów nowych funkcji.
Sprawdzenia tej zmiany: odnośniki lokalne, spójność numeracji/zależności,
kompletność kryteriów i scenariuszy oraz `git diff --check`.
Bez zmian kodu nie uruchamiano ponownie pytest ani GUI. Statusy 19–21 bez zmian.
Commit planu podany w wiadomości sesji.

## Trudne filmy: osobna gałąź i rozpoznanie — 2026-10-28

Na życzenie użytkownika utworzono **`viewer/registration-difficult-movies`**
z `26f5538` (`viewer/start` zachowuje dotychczasowe zadania).
[Wyniki i odtwarzalne próby](registration-difficult-movies.md).
Dopisano [przegląd metod poprawy](registration-improvement-options.md) na podstawie
źródeł STM/SPM i kodu: maski, dopasowanie wieloskalowe, zgodność fragmentów;
korekcja deformacji jako osobny etap. To propozycja dalszych prób, bez wdrożenia.
Zakres tego etapu: rozpoznanie MOVIE_4 / MOVIE_8 i zapis narzędzi diagnostycznych.
Kod rejestracji aplikacji pozostaje bez zmian; nie wdrożono niezweryfikowanej
zmiany domyślnej metody. Kierunek dryfu może się zmieniać i sam znak lub duży
krok nie jest kryterium błędu. Nie znamy kierunków skanowania trace/retrace.

- Sprawdzono wszystkie 363 i 83 pary czterema metodami CPU i Deep Matcher/CUDA
  na istniejących wagach. Estymaty rozchodzą się; dodatkowo Deep Matcher MOVIE_4
  oraz ECC MOVIE_8 przerywają aplikację na parze 2→3.
- MOVIE_8 1→2: trzy oddzielne fragmenty surowego obrazu wskazują około (+14,0),
  a obecny Phase około (0,0). Reproduktor daje powtarzalny RED z rozbieżnością
  14,10 px. To lokalne odniesienie obrazowe, nie ground truth całego filmu.
- Wyłączenie normalizacji daje lokalnie (+13,55; +0,25), rozbieżność 0,51 px.
  Przebieg wszystkich 446 par nie potwierdza uniwersalnej naprawy; proste filtry
  również nie rozwiązały tej konkretnej próby. Potrzebna walidacja zgodności
  struktur, a nie optymalizacja wielkości obszaru lub gładkości trajektorii.
- Narzędzia: `tests/stmviewer/diagnostics/registration_baseline.py` oraz
  `repro_movie8_phase.py`. Smoke wszystkich backendów, celowy RED i porównawczy
  GREEN odtworzone; dokumentacja, Ruff i limity sprawdzone. Bez zmian produkcji
  nie ponawiano pełnego pytest ani testów manualnych GUI.

Dane, pełne JSON, skrypty eksperymentów i figury są lokalne w
`data/registration-difficult-movies/`. Hipoteza dominowania zakłóceń nie jest
jeszcze dowiedziona dla wszystkich metod/klatek. Rozpoznanie nie zamyka
zależności czytnika MPP z ticketu 19 ani nie uruchamia ticketu 20.

## 19: Duże eksporty i wspólna praca funkcji — 2026-10-28

[Ticket 19](implementation/issues/19-large-exports.md): **ready-for-review**.
Baza `6b43765f71f28f77d1b8bf74cf2643f67e0dba15`.
[Raport](large-exports-results.md), [ręczna próba](large-exports-manual.md).
Implementacja **`6888cff`**, [przegląd dwóch osi](implementation/review-19-large-exports.md).
Użytkownik potwierdził 2026-10-28: „testy manualne ok”. Odbiór obejmuje
`6888cff` i poprawki przeglądu `716451c`. Nie podano systemu próby; końcowe
odbiory platform pozostają osobne. **Do `done` pozostaje poprawka i odbiór
wspólnego czytnika przez integrację.** Sprawdzono `stm-next` (`0e8bc53`):
limit 1000 wierszy nadal obowiązuje, więc status pozostaje `ready-for-review`.
Aktualizacja potwierdzenia dotyczy wyłącznie dokumentacji: sprawdzono spójność,
odnośniki i `git diff --check`; nie ponawiano testów kodu.

Pełny eksport aligned 1000 klatek wymagał 512 998 przedziałów braków przy limicie
500 000; zapis JSON z wcięciami przekraczał także 64 MiB. Podniesiono limit do
1 000 000 i zapisano kompaktowy JSON, zachowując limit bajtów, schemat i dokładne
wartości. Regresja TDD obejmuje publiczny zapis/odczyt 1000 małych klatek.
Dodano odtwarzalne, opcjonalne narzędzia dużych pomiarów; dane pozostają lokalne.

Wykonane sprawdzenia:

- 13 pełnych publikacji: MPP original/aligned i MJPG/FFV1, początkowo 1000 klatek,
  po usunięciu odniesienia/ostatniej i po ponownym Phase — 998. Wszystkie opisy,
  oba kontrasty, gamma 1/2, czarne/szare/białe tło.
- 4994 klatki MPP: identyczne bity próbek i wszystkie metadane; 3996 klatek FFV1:
  identyczne rastry. Kolejne 3996 MJPG sprawdzono z tolerancją stratnej kompresji,
  także lokalnie w numerach. Pięć MPP otwarto ponownie przez GUI; osiem pełnych
  AVI zakończyło odtwarzanie w VLC 3.0.24 na Ubuntu (sterowanie skryptem/X11).
- Szczyt RSS procesu wraz z dziećmi: eksporty/ponowne Phase **10,112 GB**;
  ponowne otwieranie przez GUI **14,120 GB**. Po każdym z dwóch pełnych AVI i MPP
  osobny tracemalloc wykazał **0 B nowych żywych buforów NumPy** eksportu.
- Anulowanie MPP, AVI podczas kontrastu i dekodowania zachowało wcześniejsze
  pliki. Kontrolowane OSError przy publikacji drugiego pliku MPP przywróciło
  parę, MemoryError kodeka po ćwierci filmu zachowało AVI. SHA-256 bez zmian,
  brak pozostałych katalogów tymczasowych.
- Szybkie testy regresji/WSxM/bezpieczeństwa: **34 passed**. Mypy strict: **33 pliki**,
  bez błędów. Nowe narzędzia: smoke i pełne pomiary, Ruff bez uwag.
- Pełny zestaw repo raz: **2156 passed, 14 failed, 16 skipped**, 276,77 s.
  Te same 14 testów w czystym archiwum bazy: **13 failed, 1 passed**.
  `test_edge_correction_and_resume_replace_suffix` przechodzi również osobno
  na bieżącym kodzie. Powtarzalne błędy MolTrack/SAM2 i sesji NanoTrack
  oraz niestabilność całego zestawu pozostają dla integracji.

**Potrzebna zmiana wspólna:** `napara/io/mpp_reader.py::read_mpp_file`
(używany też przez NanoTrack) ogranicza nagłówek do 1000 wierszy.
Oba pełne MPP mają 1029 wierszy z 1000 znanymi czasami i są odrzucane:
`ValueError: Missing [Header end] in MPP.`. Przekazać integracji bezpieczną
obsługę dłuższych nagłówków wraz z testami odbiorców. Nie usuwać czasów
z eksportu jako obejścia. W tej sesji nie zmieniano wspólnych modułów;
własny roundtrip nie jest odbiorem innych czytników. Ograniczenie pozostaje otwarte.

Przegląd Standards: brak naruszeń, jedna drobna uwaga o powtórzeniu kontroli
wcześniejszych publikacji. Wydzielono `repeat_export`; ponowny smoke GUI
(13 eksportów, 3 anulowania i 2 awarie) przeszedł. Przegląd Spec: brak nowych
usterek implementacji, jedna jawna zależność integracyjna odbioru pozostaje.
Dopisano jednoznaczne warunki `done` przy statusie. Największy zmieniony plik
kodu ma 197 linii; odnośniki i `git diff --check` poprawne.

Stanowisko ma 132,61 GB RAM i HDD; nie potwierdza czasów zimnego SSD ani pracy
systemu fizycznie ograniczonego do 16 GB. Zrzuty X11/Xvfb nie stanowią ręcznego
odbioru monitora. Windows i końcowe odbiory platform pozostają 20/21; WSxM nie
sprawdzano dodatkowo na dużej serii. Artefakty: `data/large-export-ticket19/`,
`data/large-export-ticket19-allocations/`; logi `/tmp/stmviewer19-*.log`.


## 18: Duża seria: podgląd i rejestracja — 2026-10-28

[Ticket 18](implementation/issues/18-large-series-preview.md): **done**.
Baza `08c1f3c`, narzędzia/testy/raport **`fb6b4e4`**, poprawki **`ae06831`**.
[Instrukcja uruchomienia i ręcznej próby](large-series-manual.md),
[pełny raport](large-series-results.md),
[przegląd dwóch osi](implementation/review-18-large-series-preview.md).
Użytkownik potwierdził 2026-10-28: „testy manualne ok”. Odbiór obejmuje
`fb6b4e4`, `ae06831` i przekazanie `0edaef6`. Nie podano systemu próby;
nie oznacza to zbiorczego odbioru Windows. Aktualizacja statusu dotyczy
wyłącznie dokumentacji: sprawdzono spójność, linki i `git diff --check`;
nie ponawiano testów kodu.

Pomiary nie wykazały potrzeby zmiany produkcji. Dodano strumieniowy generator
MPP 1000 × 512 × 512, odtwarzalny benchmark publicznych kontrolek GUI,
osobny pomiar żywych buforów NumPy i małe testy cyklu życia zasobów.
Dane `data/large-ticket18-v2/large.mpp` i manifest są lokalne, generator
w Git. Raporty zapisują identyfikację wejścia, czas, postęp, piksele X11,
rozkłady opóźnień, szczyt RSS oraz faktyczny rozmiar aligned.

Wykonane pomiary:

- Duża seria: import 2,263 s; Phase 21,721 s, **aligned 640 × 640**.
  Usunięcie trzech klatek, ponowne Phase, anulowanie obu etapów rejestracji,
  odczytu i miniatur oraz dwa kolejne otwarcia/rejestracje zakończone poprawnie.
- Original/aligned: nominalne 5 kl./s dało **4,95–4,96 kl./s**, odstępy
  około 200 ms, bez pomijania. 30 s Play na każdy widok dużej serii
  i rzeczywistego TTMAPP (268 klatek, aligned 313 × 656).
  **400 prób** wyboru/Pause: wszystkie poniżej 250 ms; p95 wyboru do 13,01 ms,
  Pause do 6,75 ms. Wyższe tempo zwalniało z zachowaniem kolejności.
- Szczyt RSS całego dużego przebiegu: **10,331 GB**. Żywe bufory NumPy po
  pierwszym i ponownym Phase: jednakowe 5 783 552 000 bajtów; po otwarciu
  małego MPP: **288 bajtów**. RSS może nadal obejmować wolne bloki alokatora.
  Nie wymuszano GC ani platformowego oddawania pamięci.

Testy i ograniczenia:

- Szybki zestaw importu/Play/Phase/generatora/zasobów: **46 passed**.
  Po poprawce znacznika wzorca generator i zasoby: **4 passed**.
  Nowe testy zasobów potwierdziły już istniejący kontrakt; nie było potrzeby
  produkcyjnej poprawki TDD. Kontrolowany MemoryError/anulowanie zachowują
  stary wynik i zwalniają częściowe alokacje zewnętrznej biblioteki SciPy.
- Końcowe narzędzie pomiarowe sprawdzone w trybie smoke na X11; smoke nie
  zastępuje opisanych pełnych pomiarów. Mypy strict: **33 pliki, bez błędów**.
- Pełny zestaw repo raz: **2154 passed, 15 failed, 16 skipped**, 295,17 s.
  Wszystkie niepowodzenia dotyczą MolTrack/NanoTrack. Powtórzenie tych samych
  15 na czystym archiwum bazy `08c1f3c`: **13 failed, 2 passed**.
  Dwa pozostałe (`test_edge_correction_and_resume_replace_suffix` oraz
  `test_real_worker_cli_roundtrips_batch_contract_with_injected_sam2_repo`)
  przeszły również powtórzenie na bieżącym kodzie: **2 passed**.
  Nie deklarujemy zielonego odbioru repo; powtarzalne problemy SAM2/ścieżek
  i sesji NanoTrack oraz niestabilność pełnego przebiegu należą do integracji.
- Największy nowy plik ma 226 linii, poniżej limitu 1500.
  Sprawdzono odnośniki i `git diff --check`.
- Lokalna maszyna ma 132,61 GB RAM, a pliki są na HDD z cache systemowym.
  Zmierzono rzeczywisty budżet RSS, nie ograniczano systemu do 16 GB.
  Zrzuty X11/Xvfb oceniono wizualnie; nie jest to ręczny odbiór ani pomiar
  fizycznego monitora. Nie potwierdza czasu zimnego odczytu z SSD.
  Windows nie był dostępny; końcowe odbiory platform pozostają 20/21.

Artefakty lokalne: `/tmp/stmviewer18-large-final.json`,
`/tmp/stmviewer18-typical.json`, `/tmp/stmviewer18-live-memory.json`,
`/tmp/stmviewer18-full-suite.log`, `/tmp/stmviewer18-baseline-failures.log`,
`/tmp/stmviewer18-transient-recheck.log` i zrzuty z prefiksem `stmviewer18`.
Nie zmieniono wspólnych modułów, konfiguracji głównej ani algorytmów.
Nie ma nowej zależności od zmiany integracyjnej. Eksporty dużej serii należą
wciąż do ticketu 19; ten etap ich nie odbiera.

## 17: Podziałka, numer i czas w AVI — 2026-10-27

[Ticket 17](implementation/issues/17-avi-annotations.md): **done**.
Baza `f051a143`, implementacja **`367f714`**, napisy bez czarnych pól **`b3ca58d`**.
[Instrukcja uruchomienia i próby ręcznej](avi-annotations-manual.md),
[przegląd dwóch osi](implementation/review-17-avi-annotations.md).
Użytkownik potwierdził 2026-10-27: „testy manualne ok”. Odbiór obejmuje
implementację `367f714`, poprawkę `b3ca58d` i przekazanie `3ae7bcd`.
Nie podano systemu wykonania próby; nie oznacza to zbiorczego odbioru Windows.
Aktualizacja statusu dotyczy wyłącznie dokumentacji: sprawdzono spójność,
linki i `git diff --check`; nie ponawiano testów kodu.

Okno Zapisz AVI zawiera trzy niezależne, domyślnie wyłączone opcje:
podziałkę długości, numer klatki i czas pomiaru. Działają dla original/aligned
oraz MJPG/FFV1. Numer odnosi się do całej bieżącej serii po usuwaniu,
a czas do metadanych pomiaru; brak jest wyświetlany jawnie. Podziałka używa
wspólnej kalibracji wybranego zakresu, a przy jej braku, niezgodności lub
włączonych proporcjach pikselowych podaje px. Techniczny padding nie zmienia
przelicznika. Rozmiar i położenie opisów są stałe w całym filmie.

Zgodnie z doprecyzowaniem użytkownika napisy i podziałka są białe z cienkim
ciemnym obrysem, bez prostokątnych czarnych pól. Nakładane są po gamma/kontraście.
Zbyt mały obraz blokuje zapis z podaniem wymaganych wymiarów. Plan eksportu
zachowuje wybrane opcje podczas zmian podglądu; anulowanie i błąd nadal chronią
poprzedni plik. Źródłowe próbki i metadane pozostają bez zmian.

Sprawdzenia automatyczne:

- TDD: red → green na zatwierdzonej granicy klatka/opcje → raster oraz
  kontrolki GUI → wynik. Dodatkowy test bez czarnych pól był czerwony przed poprawką.
- Po ostatniej poprawce: **96 passed** dla `tests/stmviewer/test_avi*.py`
  w Qt offscreen; sprawdzono także odczyt filmów obu kodeków i stan eksportu.
- Qt xcb na lokalnym ekranie X11: **39 passed** dla kontrolek opisów
  i eksportu (sukces, błąd, anulowanie, zamknięcie, original/aligned). To
  automatyczna próba okna, odrębna od ręcznej akceptacji użytkownika.
- Mypy strict: **33 pliki, bez błędów**.
- Pełny zestaw repo uruchomiony przed poprawką wyglądu:
  **2149 passed, 15 failed, 16 skipped** w 291.14 s.
  Żaden niezaliczony test nie dotyczył Viewera. Powtórzenie tych 15 testów
  na czystym archiwum bazy `f051a143`: **13 failed, 2 passed**.
  Dwa pozostałe testy NanoTrack (`test_edge_correction_and_resume_replace_suffix`
  oraz `test_real_worker_cli_roundtrips_batch_contract_with_injected_sam2_repo`)
  przeszły również powtórzenie na bieżącym kodzie: **2 passed**.
  Drugi wcześniej przekroczył timeout 10 s. Nie ustalono przyczyny zależności
  pierwszego od pełnego przebiegu; nie deklarujemy zielonego odbioru repo.
  Trzynaście powtarzalnych błędów dotyczy testów SAM2 MolTrack/NanoTrack
  i zapisu/odczytu sesji NanoTrack; należy je diagnozować w sesji integracyjnej.
- Największy zmieniony plik kodu: **186 linii**; wszystkie poniżej limitu 1500.

Próba zewnętrznego odtwarzacza: osiem AVI z lokalnego `data/avi-ticket17/movies.json`
uruchomiono w VLC 3.0.24 na Linuksie/X11. Każdy proces zakończył się kodem 0
po czasie odpowiadającym filmowi. Zrzuty original/aligned, nm/px i braku czasu
oceniono wizualnie: poprawne proporcje, czytelne znaki, brak prostokątnych pól.
To odtwarzanie sterowane skryptem z oceną zrzutów, nie ręczny odbiór użytkownika.
Pakiet VLC Snap nie przekazał logów dekodera, więc nie traktujemy pustych logów
jako dowodu braku błędów. Odbiór Windows/VLC pozostaje w tickecie 21.

Lokalne artefakty: `data/avi-ticket17/` (MPP, JSON i filmy),
`/tmp/stmviewer-avi17-final-avi.log`, `/tmp/stmviewer-avi17-final-xcb.log`,
`/tmp/stmviewer-avi17-full-suite.log`,
`/tmp/stmviewer-avi17-baseline-failures.log`,
`/tmp/stmviewer-avi17-transient-recheck.log`,
`/tmp/stmviewer-avi17-vlc/` (zrzuty i wyniki odtwarzania).
Generator danych wejściowych jest w Git; pomiary i filmy pozostają lokalne.
Nie zmieniono wspólnych modułów ani głównej konfiguracji. Brak nowej zależności
od zmiany integracyjnej; istniejące błędy pełnego zestawu przekazano powyżej.


## 16: Aligned do AVI — 2026-10-26

[Ticket 16](implementation/issues/16-aligned-avi.md): **done**.
Baza `903d00b`, implementacja **`ecc8663`**, poprawka **`883b3ae`**.
[Instrukcja uruchomienia i próby ręcznej](aligned-avi-manual.md),
[przegląd dwóch osi](implementation/review-16-aligned-avi.md).
Użytkownik potwierdził 2026-10-26: „testy manualne ok”. Odbiór obejmuje
implementację `ecc8663`, poprawkę `883b3ae` i przekazanie `72bbef3`.
Aktualizacja dotyczy wyłącznie dokumentacji: sprawdzono spójność statusów,
linki i `git diff --check`; nie ponawiano testów kodu.

Przycisk/menu „Zapisz AVI…” otwiera opcje z wyborem original/aligned,
domyślnie zgodnym z podglądem. Bez kompletnego wyniku związanego z bieżącą
serią dostępne jest tylko original. Podsumowanie zmienia rozmiar wraz z wyborem;
proponowana nazwa ma sufiks odpowiedniej wersji. Zmiana wyboru nie zmienia podglądu.

Adapter `avi_sources.py` bierze gotowe tablice aligned i zachowuje pełny canvas
również po usunięciu odniesienia/skrajnej klatki albo wybraniu zakresu. Nie ma
nowej rejestracji ani interpolacji pomiaru. Kopiowane są tylko rekordy metadanych,
bez kopiowania tablic. Kalibracja każdego oryginału odnosi się do pełnego canvas;
planner sprawdza wspólną skalę eksportowanych klatek. To pozwala zapisać fizyczne
proporcje jednorodnego zakresu pierwotnie mieszanej serii, bez zmiany skali podglądu.
Opcja proporcji pikselowych działa jak wcześniej.

Oba kodeki, FPS, zakres, gamma, kontrast i trzy tła korzystają z dotychczasowego
renderera/workera. Maska braków i dopełnienie parzystych rozmiarów zachowują
wybrany kolor. Opcje i tablice są ustalone na czas eksportu; podgląd pozostaje
dostępny, zmiany serii/rejestracja/pozostałe eksporty są blokowane do zakończenia.
Nie dodano napisów ani podziałki (ticket 17).

Sprawdzenia:

- TDD red → green dla wyboru aligned i eksportu po usunięciu odniesienia,
  niedostępności niekompletnego/niedopasowanego wyniku oraz poprawki kalibracji
  jednorodnego podzbioru (zakres i usunięcie odstającej klatki).
- Po poprawce **86 passed**, 19.58 s: `/tmp/stmviewer-avi16-focused-final.log`.
  AVI oraz powiązane MPP; rzeczywisty odczyt obu kodeków, geometryczne oczekiwania
  po usunięciu, maski i subpikselowe próbki, wspólna/nieznana skala, wybór wersji,
  zamrożenie opcji, anulowanie, błąd, zamknięcie i nowa operacja po zakończeniu.
- Mypy strict: **32 pliki, 0 błędów**. Największy zmieniony plik kodu:
  `main_window.py`, **803 linie**. `git diff --check` czysty.
- Pełne repo raz po implementacji, przed poprawką z przeglądu:
  **2120 passed, 14 failed, 16 skipped**, 266.40 s;
  `/tmp/stmviewer-avi16-full-suite.log`. Porównanie z ticketem 15:
  te same 14 identyfikatorów niepowodzeń MolTrack/NanoTrack, bez nowych.
  Po poprawce powtórzono właściwe zestawy AVI/MPP/GUI i mypy. Pełny zestaw
  nie jest deklarowany jako zielony.
- Po poprawce GUI Qt xcb/Xvfb: **28 passed**, 7.24 s;
  `/tmp/stmviewer-avi16-xcb-final.log`. Obejrzano główne okno i nowy dialog.
- VLC **3.0.20**, osobny ekran Xvfb z wyjściem xcb_x11: 10 filmów, oba kodeki,
  trzy tła, kontrasty, gamma i anizotropia; obraz, EOF, kod 0, bez błędów.
  Po poprawce powtórzono próbę dwóch zmienionych filmów mieszanego wzorca.
  Raporty i zrzuty: `/tmp/stmviewer-avi16-vlc/`, w tym `results.json`
  oraz `calibration-results.json`. Użyto tymczasowej kopii VLC z poprzednich
  etapów, bez instalowania programów w systemie.
- Rzeczywista rejestracja Phase **256 klatek 512 × 512**, wynik 524 × 519.
  Zapis aligned ze wspólnym kontrastem anulowany przez przycisk GUI podczas
  kodowania klatki 1/256; poprzedni AVI pozostał identyczny bajtowo.
  `/tmp/stmviewer-avi16-vlc/cancel-result.json`. Nie jest to pełny test wydajności
  ticketów 18–19 ani ręczna akceptacja użytkownika.
- Lokalne dane `data/avi-ticket16/`: trzy małe MPP z JSON, 10 filmów AVI
  oraz `long.mpp` (~537 MB). Generator
  `tests/stmviewer/make_aligned_avi_fixtures.py` z opcją `--long`.
  Dane i duże wyniki pozostają poza Git.

Przegląd Standards: początkowa opcjonalna uwaga o odpowiedzialności dialogu
rozwiązana przez adapter; finalnie 0 uwag. Spec: P2 o kalibracji zakresu
rozwiązane w `883b3ae`, recenzent niezależnie potwierdził wynik; finalnie 0 uwag.
Ręczny odbiór użytkownika potwierdzony. Nie wskazano systemu; nie przypisujemy
więc temu potwierdzeniu odbioru konkretnej platformy.
Nie zmieniono wspólnego kodu, konfiguracji ani zależności. Integracja nie wymaga
nowych ustaleń. Odbiory platform nadal należą do ticketów 20 i 21.

## 15: Prezentacja AVI — 2026-10-26

[Ticket 15](implementation/issues/15-avi-presentation.md): **done**.
Baza `d6a08e1`, implementacja **`3e1fddf`**.
[Instrukcja ręczna i dane](avi-presentation-manual.md),
[przegląd dwóch osi](implementation/review-15-avi-presentation.md).
Użytkownik potwierdził 2026-10-26: „testy manualne ok”. Odbiór obejmuje
implementację `3e1fddf` i przekazanie `e80a93d`. Aktualizacja dotyczy wyłącznie
dokumentacji: sprawdzono spójność statusów, linki i `git diff --check`;
nie ponawiano testów kodu.

Dialog AVI daje gamma z podglądu lub 1, kontrast osobno dla każdej klatki
lub wspólny dla wybranego zakresu oraz tło czarne/szare/białe (0/128/255).
Wartości domyślne pozostają: gamma podglądu, kontrast osobny, czarne tło.
Nowe otwarcie dialogu przywraca te wartości. Opcje po rozpoczęciu są niezmienne;
zmiana podglądu nie wpływa na rozpoczęty film. Nie zmieniono podglądu ani MPP.

Wspólne poziomy wyznacza worker tylko ze skończonych próbek wybranych klatek,
blokami około 4 MiB z punktami anulowania. Nie powstaje dodatkowy stos filmu.
Postęp obejmuje wyznaczanie poziomów, zapis i weryfikację. Braki i dopełnienie
używają wybranego koloru po gamma, bez udziału w poziomach. Przy stałym zakresie
u=0,5 przed gamma; pusty film/klatka z punktu widzenia próbek daje wybrane tło.
MJPG/FFV1 nadal mają wspólne renderowanie i zabezpieczenia z ticketu 14.

Zakres AVI to nadal original. Renderer działa też na pikselach gotowego aligned
wczytanego z MPP jako źródło; dodanie wyboru bieżącego aligned jest w tickecie 16.
Nie dodano opisów ani nowych zależności, nie zmieniono wspólnych modułów.

Sprawdzenia:

- TDD: red → green kolejno dla teł, wspólnego kontrastu i publicznych opcji GUI;
  pozostałe scenariusze rozszerzają regresje granic zatwierdzonych dla AVI.
- **57 passed**, 12.83 s, `/tmp/stmviewer-avi15-focused.log`. Obejmuje 24
  kombinacje kodeka/tła/kontrastu/gamma przez GUI i faktyczny odczyt AVI,
  skrajne finite float64, NaN/Inf, stały zakres, brak próbek, wybór zakresu,
  niezmienność ustawień podczas pracy i anulowanie obliczeń kontrastu.
- Mypy strict: **31 plików, 0 błędów**. `git diff --check` czysty.
  Największy zmieniony plik kodu: `avi_export.py`, **171 linii**.
- Pełne repo raz na końcu implementacji: **2095 passed, 14 failed, 16 skipped**,
  259.60 s, `/tmp/stmviewer-avi15-full-suite.log`. Porównanie z logiem ticketu 14
  `/tmp/stmviewer-avi-full-suite.log`: identyczne 14 identyfikatorów błędów
  MolTrack/NanoTrack, bez nowych. Nie deklarujemy zielonego całego repo.
- **34 passed**, 9.69 s, GUI Qt xcb na osobnym Xvfb; log
  `/tmp/stmviewer-avi15-xcb.log`. Obejrzano także rozszerzony dialog.
- Faktyczne **VLC 3.0.20** odtworzyło 10 filmów w MJPG/FFV1 z nowymi opcjami,
  do EOF, z wyjściem obrazu xcb_x11 i kodem 0, bez błędów; obejrzano zrzuty.
  Raporty: `/tmp/stmviewer-avi15-vlc/`. Użyto tymczasowej kopii VLC z poprzedniego
  etapu; niczego nie instalowano w systemie. Brak stanowiska Windows.
- Dane: `data/avi-ticket15/presentation.mpp` i JSON oraz 10 lokalnych AVI;
  generator `tests/stmviewer/make_avi_presentation_fixtures.py`. Pięć klatek
  65 × 49, wynik 66 × 50, rozpoznawalne skale i skrajna pierwsza klatka.
  Pomiary i filmy pozostają poza Git.

Przegląd skilla code-review: Standards **0 ustaleń**, Spec **0 ustaleń**.
Nie były potrzebne poprawki kodu. Ręczny odbiór użytkownika potwierdzony.
Nie wskazano systemu; odrębne próby platformowe w ticketach 20 i 21 pozostają
otwarte. Współpraca z integracją: brak nowych wspólnych
zmian i zależności; użyto netcat oraz konfiguracji OpenCV z ticketu 14.

## 14: Original do AVI — 2026-10-26

[Ticket 14](implementation/issues/14-original-avi-basic.md): **done**.
Baza `60785df`, implementacja `959c5c6`, poprawki `a9cf6b4`.
[Instrukcja uruchomienia i ręcznej próby](original-avi-manual.md),
[przegląd dwóch osi](implementation/review-14-original-avi.md).
Użytkownik potwierdził 2026-10-26: „testy manualne ok”. Odbiór obejmuje
implementację i poprawkę wskazane wyżej oraz przekazanie `7d546d3`.
Aktualizacja statusu dotyczy wyłącznie dokumentacji: sprawdzono spójność
statusów, linki i `git diff --check`; nie ponawiano testów kodu.

Dostępny przycisk/menu „Zapisz AVI original…”: cała seria lub zakres włącznie,
FPS 1–30 (domyślnie Play), MJPG domyślnie lub FFV1. Podsumowanie pokazuje
liczbę klatek, rozmiar i czas. Pełne obrazy niezależne od zoomu; gamma pobrana
z podglądu, kontrast per klatka, czarne braki, bez opisów. Wspólna skala daje
proporcje fizyczne; nieznana/niespójna lub opcja Proporcje pikselowe daje
pikselowe. Nearest sampling zachowuje wspólnie dane/maskę przy rozszerzeniu;
nieparzyste wymiary są dopełniane z prawej/dołu bez obcinania krawędzi.

Worker blokuje import, Play, usuwanie, rejestrację i oba eksporty; przeglądanie,
zoom i gamma działają dalej bez zmiany ustawień bieżącego filmu. Zapis etapowy
chroni istniejący plik. Pełny odczyt sprawdza liczbę, FPS, geometrię i kodek;
FFV1 dodatkowo skróty rastrów uint8. Brak kodeka lub błąd daje komunikat.
Próba kodera odbywa się w osobnym procesie po wykryciu natywnej awarii MJPG
przy 4 × 4. Bez automatycznej zamiany kodeka czy pobierania. Zamknięcie okna
anuluje pracę i czeka na worker. MPP i białe tło jego podglądu są zachowane.

Wykonane sprawdzenia:

- TDD na zatwierdzonych granicach: renderer, publiczny eksport z rzeczywistym
  odczytem i publiczne kontrolki GUI. Testy awarii kodeka obejmują też faktyczny
  SIGABRT małego MJPG izolowany w procesie potomnym.
- Po przeglądzie **62 passed**, 18.71 s: AVI oraz powiązane MPP, Play,
  rejestracja i usuwanie. Log `/tmp/stmviewer-avi-focused-final.log`.
- Mypy strict: **31 plików, 0 błędów**. `git diff --check` czysty.
  Największy zmieniony plik `main_window.py`: **802 linie** (limit 1500).
- Pełne repo raz na końcu implementacji: **2056 passed, 14 failed, 16 skipped**,
  239.70 s, `/tmp/stmviewer-avi-full-suite.log`. Porównanie z
  `/tmp/stmviewer-white-full-suite.log`: identyczne 14 identyfikatorów błędów
  MolTrack/NanoTrack; nie dodano nowych. Nie deklarujemy zielonego całego repo.
- Qt xcb na osobnym Xvfb: **13 passed**, 2.78 s, AVI/MPP GUI.
  Obejrzano główne okno i dialog. To próba automatyczna, nie akceptacja użytkownika.
- Faktyczne VLC **3.0.20**: sześć filmów (MOVIE_3, odd, anisotropic × oba kodeki),
  renderowanie xcb_x11, dojście do EOF i kod wyjścia 0, bez błędów; obejrzano
  zrzuty. Pakiety Ubuntu rozpakowano wyłącznie do `/tmp/stmviewer-avi-vlc/`;
  tam logi, `results.json` i obrazy. Windows nie był dostępny.
- Rzeczywiste anulowanie przez GUI w trakcie kodowania 600 klatek 512 × 512:
  komunikat anulowania, wcześniejszy AVI identyczny bajtowo. Mały wzorzec
  kończył zapis przed kliknięciem, więc większy plik generuje opcja `--long`.
- Dane: `data/avi-ticket14/`, generator `tests/stmviewer/make_avi_fixtures.py`.
  Gotowe AVI i MPP są poza Git. `MOVIE_3.MPP`: 17 klatek 256 × 256;
  `odd`: sześć 65 × 49 → 66 × 50; `anisotropic` → 130 × 50.

Przegląd Standards: 0 twardych naruszeń, 1 uwaga P3 o powtarzaniu blokad
rozwiązana w `a9cf6b4`, potwierdzona przez recenzenta; Spec: 0 ustaleń.
Końcowo obie osie bez otwartych uwag. Ręczny odbiór użytkownika potwierdzony.
Nie wskazano systemu, więc osobne odbiory platform w ticketach 20 i 21
pozostają otwarte.

Współpraca: brak zmian wspólnego kodu/konfiguracji. Lokalny
`stmviewer/requirements-avi.txt` korzysta z istniejącego przypięcia OpenCV
w requirements-ecc.txt. Integracja powinna uwzględnić ten zestaw podczas
przygotowania pełnego środowiska; netcat już zawiera wymagany build.
Duże serie, dodatkowe prezentacje, aligned i opisy pozostają w ich ticketach.

## 13: Potwierdzenie odbioru — 2026-10-26

Użytkownik potwierdził: „teraz jest ok. testy manualne ok”.
[Ticket 13](implementation/issues/13-aligned-mpp.md),
[poprawka zgodności MPP](implementation/issues/13-wsxm-compatibility-fix.md)
i [białe tło oraz uproszczony zapis](implementation/issues/13-white-background.md)
mają status **done**. Potwierdzenie dotyczy końcowego rozwiązania z dwoma
wyborami original/aligned, jasnym tłem i odtwarzaniem braków przez V3.

Implementacja i kolejne poprawki znajdują się w zakresie `6ab0837..223c1bb`,
w tym `ec21f6a`, `35858f1`, `2343bd6`, `e013d73` i `2175cfe`.
Aktualizacja odbioru obejmuje wyłącznie dokumentację: sprawdzono spójność
statusów, linki i `git diff --check`; nie ponawiano testów kodu.
Nie przypisujemy ogólnemu potwierdzeniu odbioru konkretnych platform;
użytkownik nie wskazał systemu, więc pozostają osobne zadania 20 i 21.
Ticket 14 ma spełnioną zależność 07 i status ready-for-agent; nie rozpoczęto go.

## 13: Białe tło i dwa wybory zapisu — 2026-10-26

Baza `7123d1b`, implementacja **`2175cfe`**.
[Ticket poprawki](implementation/issues/13-white-background.md): **ready-for-review**.
[Próba ręczna](wsxm-export-manual.md), [przegląd](implementation/review-13-white-background.md).
Zmiana wynika z prośby użytkownika o ujednolicenie dodatkowego obszaru.

W oknie zapisu pozostają original/aligned, domyślnie bieżący widok.
Zapis z GUI zawsze używa skończonego tła z dokładnymi brakami w V3.
Tłem MPP jest maksimum klatki, a przy braku skończonych próbek zero.
Podgląd i miniatury malują braki na biało po zastosowaniu gamma do pomiaru.
NaN/Inf pozostają w pamięci, maska i historia odtwarzają się z JSON.
Rejestracja, interpolacja i skończone wartości nie zmieniły się.

Kolor MPP zależy od zewnętrznej palety i kontrastu — to liczby, nie RGB.
Dokumentacja wyjaśnia też klatki stałe/puste oraz zakres całego filmu.
Czytnik nadal obsługuje stare V3 z minimum i V1/V2. API zachowało poprzedni
parametr i domyślny zapis NaN; dodatkowych wariantów nie ma już w GUI.
Komunikaty limitu nie sugerują usuniętej opcji interfejsu.

Sprawdzenia:

- Trzy przebiegi TDD red → green na publicznym eksporcie i GUI.
- Zestaw zmiany: **32 passed**, 3.49 s; rzeczywiste Qt xcb na oddzielnym
  ekranie: **13 passed**, 1.22 s. Gamma, białe piksele i miniatury, dialog,
  odczyt i resave starego aligned zostały sprawdzone automatycznie.
- Mypy strict: **26 plików** bez błędów. Największy zmieniony plik kodu:
  **765 linii**. `git diff --check` i linki dokumentacji poprawne.
- Pełne repo raz na końcu: **2038 passed, 14 failed, 16 skipped**, 239.13 s.
  Wszystkie 14 identyfikatorów błędów MolTrack/NanoTrack jest identycznych
  z `/tmp/stmviewer-wsxm-full-suite.log`; brak nowych niepowodzeń.
- `data/MOVIE_3-aligned-white.mpp` + JSON wygenerowano publicznym eksportem
  original z istniejącego aligned. Każda z **17 klatek** zachowuje dokładne
  skończone próbki, a po odczycie V3 także pełne bajty braków i historię.
  Publiczny `check_aligned_mpp.py` ponownie obliczył Optical Flow i potwierdził
  próbki, maskę, geometrię oraz metadane wszystkich klatek.
- Nowy plik otwarto w rzeczywistym WSxM 5.0 Develop 12.0 pod Wine:
  widoczny jasny dodany obszar i szczegóły pomiaru. Wycinek pomiaru:
  **167** kolorów spełniających próg diagnostyczny; zrzut oceniono wizualnie.
- Przegląd Standards: 0 uwag; Spec: 0 uwag. Bez zmian wspólnych modułów.

Logi: `/tmp/stmviewer-white-full-suite.log`, `/tmp/stmviewer-white-xcb.log`,
`/tmp/stmviewer-white-values.log`; WSxM: `/tmp/wsxm-aligned-investigation/white-export-result.log`
i `white-export-frame0.png` (etykieta próby, faktyczna klatka na zrzucie: 8).
Oryginalny pomiar i JSON nie były nadpisywane. Izolowane okno WSxM nie
zmieniało konfiguracji użytkownika. Ręczny odbiór i Windows oczekują.

Uruchom ponownie `python -m stmviewer.main` w środowisku `netcat`.
Stary aligned wystarczy otworzyć i zapisać jako original pod nową nazwą;
nie wymaga ponownej rejestracji. Do analizy przenosić MPP i JSON razem.
Starsze czytniki bez V3 nadal interpretują sztuczne tło jako liczby;
ewentualna wspólna obsługa V3 pozostaje zadaniem sesji integracyjnej.

## 13: Poprawka eksportu WSxM w aplikacji — 2026-10-26

Baza `01259e1`, implementacja **`2343bd6`**, korekta przeglądu **`e013d73`**.
[Poprawka](implementation/issues/13-wsxm-compatibility-fix.md) i ticket 13:
**ready-for-review**, ręczny odbiór użytkownika oczekuje.
[Instrukcja GUI](wsxm-export-manual.md), [kontrakt V3](mpp-metadata-format.md),
[przegląd Standards/Spec](implementation/review-13-wsxm-compatibility.md).

### Zachowanie

Okno zapisu domyślnie wybiera bieżącą wersję original/aligned w wariancie
WSxM. Zachowano wariant NaN i dotychczasowe domyślne API. WSxM zapisuje
skończone tło zamiast NaN/Inf: minimum danej klatki lub zero, gdy nie ma
skończonych wartości. Skończone pomiary i natywny nagłówek nie są zmieniane.
Dodatek V3 przechowuje dokładne pozycje i bity zastąpionych próbek; otwarcie
pary przywraca maskę, NaN/Inf, historię i pochodzenie. Działa też zapis
original po otwarciu wcześniejszego aligned. Odrzucenie błędnego dodatku
nie pozostawia częściowo odtworzonych pikseli. Zapis używa dotychczasowego
postępu, anulowania i przywracania pary przy błędzie.

### Wykonane sprawdzenia

- TDD red → green: publiczny zapis/odczyt, następnie publiczne kontrolki
  GUI (domyślne WSxM i identyczny podgląd z szachownicą po odczycie).
- Końcowy Viewer po poprawce przeglądu: **252 passed, 2 skipped**, 26.74 s.
  Pominięcia dotyczą opcjonalnych wag Deep Matcher. Zakres obejmuje V1/V2/V3,
  niezależny czytnik, NaN payloady/Inf/dziury, błędny/brakujący dodatek,
  rollback/anulowanie i zachowanie alternatywnego zapisu NaN.
- Mypy strict: **26 plików**, bez błędów. Największy zmieniony plik kodu:
  **766 linii**, wszystkie poniżej 1000/1500; `git diff --check` poprawny.
- Pełne repo: **2038 passed, 14 failed, 16 skipped**, 235.44 s.
  Dokładnie te same 14 identyfikatorów niepowodzeń MolTrack/NanoTrack co
  `/tmp/stmviewer-aligned-full-suite.log`; brak nowych. W poprzedniej sesji
  13 odtworzono na bazie, jeden test NanoTrack był niestabilny w pełnym biegu.
  Pierwsze polecenie bez importlib zatrzymało się przy zbieraniu (6 kolizji
  nazw istniejących modułów); pełny przebieg wykonano udokumentowaną komendą:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib -p no:cacheprovider`.
- Qt xcb na oddzielnym ekranie: **4 passed**, 0.96 s. Rzeczywisty dialog
  zapisu, warianty WSxM/NaN, ponowny odczyt, historia i szachownica.
- `data/MOVIE_3.MPP` → Optical Flow → nowy eksporter:
  `data/MOVIE_3-aligned-wsxm.mpp` + `.stmviewer.json` (502 882 B).
  Wszystkie **17 klatek** po otwarciu odzyskują dokładne bajty, NaN,
  geometrię i parametry; kontrola publicznym `check_aligned_mpp.py` zaliczona.
  Resave starego aligned przez original WSxM daje te same bajty MPP.
- MPP jest bajtowo identyczny z diagnostyczną kopią podglądową:
  SHA-256 `dfc7013b984eb05a101070f13a930893e451320bbb6f4b5dc624746e253d6fc4`.
  Nowy plik rzeczywiście otwarto w WSxM 5.0 Develop 12.0 pod Wine:
  obraz ma szczegóły, wycinek zawiera **207** kolorów spełniających próg
  diagnostyczny; zrzut oceniono wizualnie. To nie próba wszystkich wersji WSxM.
- Standards: brak uwag. Spec: drobne P3 komunikatu limitu poprawione
  i zamknięte przez recenzenta; **0 otwartych uwag**.

Logi: `/tmp/stmviewer-wsxm-final-viewer.log`, `/tmp/stmviewer-wsxm-full-suite.log`,
`/tmp/stmviewer-wsxm-collection.log`, `/tmp/stmviewer-wsxm-xcb.log`,
`/tmp/stmviewer-wsxm-values.log`. Próba WSxM i zrzut:
`/tmp/wsxm-aligned-investigation/production-export-result.log`,
`production-export-frame0.png` (etykieta próby, faktyczna pozycja na zrzucie: 5).
Izolowany prefiks i ekran nie zmieniały konfiguracji WSxM użytkownika.

### Odbiór i ograniczenia

Zrestartuj program: `conda activate netcat`, `python -m stmviewer.main`.
Własny stary aligned można otworzyć i zapisać jako **original — WSxM**
bez ponownej rejestracji. [Próba ręczna](wsxm-export-manual.md) pozostaje
użytkownikowi; Windows nie był dostępny. Oryginalny pomiar i JSON bez zmian.
Dla odtworzenia braków przenosić trzeba MPP i JSON razem. Brakujący,
nieprawidłowy lub nieobsługiwany dodatek pozostawia sztuczne skończone tło.
Starsze czytniki repo nie odtwarzają V3: należy do nich wybrać wariant NaN;
ewentualną wspólną obsługę V3 koordynuje sesja integracyjna. Nie zmieniano
wspólnych modułów. Limit dodatku 64 MiB; eksporter ogranicza też liczbę
przedziałów do 500 000. Zapis NaN pozostaje dostępny bez tej listy.

## 13: Diagnoza czarnego aligned w WSxM — 2026-10-26

Na bazie `e49bc6b` sprawdzono zgłoszony `data/MOVIE_3-aligned.mpp`.
[Raport](wsxm-aligned-investigation.md): zapis Optical Flow, nagłówek i
dodatek są poprawne; ponowne obliczenie potwierdza dokładną zgodność
wszystkich 17 klatek, NaN i geometrii. Rzeczywisty WSxM pod Wine pokazuje
czarny obraz przy NaN. Kopia z identycznym nagłówkiem i skończonymi
próbkami, w której zmieniono tylko brakujące piksele na minimum klatki,
odzyskuje szczegóły. Plane i tryb palety nie usuwają błędu oryginału.

Lokalna kopia wyłącznie do oglądania:
`data/MOVIE_3-aligned-wsxm-preview.mpp` oraz opis `.README.txt`.
Oryginał i JSON pozostają bez zmian; kopia nie ma dodatku geometrii/maski.
Nie zmieniono kodu, kontraktu NaN ani statusu **ready-for-review**.
Ręczny odbiór ticketu 13 i próba kopii na Windows oczekują. Automatyczne
GUI Wine oraz kontrola wszystkich próbek zostały wykonane; pełnego
zestawu testów kodu nie ponawiano przy zmianie samej dokumentacji.
Brak potrzebnych zmian wspólnych. Commit dokumentacji podany w odpowiedzi.

## 13: Zapis aligned do MPP — 2026-10-26

Gałąź `viewer/start`. Baza `6ab0837abb5b4e6ba356a1ff6121779302e3585a`.
Implementacja **`ec21f6a`**, poprawki przeglądu **`35858f1`**.
[Ticket 13](implementation/issues/13-aligned-mpp.md): **`ready-for-review`**.
[Próba ręczna](aligned-mpp-manual.md), [kontrakt V1/V2](mpp-metadata-format.md),
[przegląd Standards/Spec](implementation/review-13-aligned-mpp.md).

### Wynik

Zapisz MPP… / Ctrl+S oferuje original/aligned w polu Typ pliku okna zapisu,
domyślnie aktualny widok. Aligned wymaga gotowego wyniku rejestracji.
Oba warianty zapisują całą pozostałą serię, używając wspólnego zapisu
z postępem, anulowaniem i przywracaniem poprzedniej pary przy błędzie.

Eksport aligned zachowuje float64, NaN, pełny obszar, padding, skumulowane
przesunięcia, prostokąty źródeł i historyczne odniesienie — także usunięte.
Nie interpoluje ponownie. Dodatek V2 rozdziela źródłowe pole/offsety od
rozmiaru obszaru aligned i regułę ważności próbek od prostokąta źródła.
Odczyt traktuje zapisane piksele jako nowe wejście original; pokazuje
historię i obrys bez tworzenia fikcyjnych oryginałów ani wyniku rejestracji.
Ponowny zapis original zachowuje historię; nowa rejestracja tworzy nowy etap,
zachowując poprzednie. NaN/Inf blokują obecne backendy z czytelną przyczyną;
skończony plik ze znacznikiem aligned może być rejestrowany.

Przegląd wskazał niespójność tolerancji wspólnej skali: kolejne porównania
mogły uznać dryfujące wartości za wspólne. Teraz wszystkie klatki porównuje
się z jedną skalą odniesienia. Przy niespójności aligned używa pikseli,
a zapis zachowuje indywidualne parametry źródeł. Wspólna walidacja pochodzenia
obsługuje również odniesienie historyczne.

### Sprawdzenia

- TDD na zatwierdzonych granicach: dokładny zapis/odczyt subpikseli po
  usunięciu odniesienia, publiczny wybór wersji i historia w GUI, niespójna
  skala kolejnych etapów oraz regresja dryfujących skal — red → green.
- Końcowy Viewer: **231 passed, 2 skipped**, 23.95 s. Obejmuje V1/V2,
  zachowanie maski i prostokąta osobno, różne/nieznane kalibracje, ponowny
  zapis i rejestrację, błędy dodatku, rollback i anulowanie obu wariantów,
  rzeczywisty dialog Qt oraz odczyt przez trzy dotychczasowe aplikacje.
  Dwa pominięcia dotyczą opcjonalnych testów wag Deep Matcher.
- Mypy strict: **25 plików** bez błędów. Największy zmieniony plik Python:
  `main_window.py`, **767 linii**; wszystkie poniżej 1000/1500.
- Pełny zestaw repo uruchomiony raz przed poprawką przeglądu:
  **2016 passed, 14 failed, 16 skipped**, 239.42 s, bez błędów zbierania.
  Wszystkie niepowodzenia dotyczą MolTrack/NanoTrack. W czystym archiwum
  bazy `6ab0837` uruchomiono te 14 testów: **13 failed, 1 passed**.
  Przechodzący osobno `test_edge_correction_and_resume_replace_suffix`
  przeszedł również na bieżącej gałęzi (0.66 s). To niepowtarzalny lokalnie
  błąd pełnego przebiegu; nie deklarujemy zielonego odbioru całego repo.
  Po poprawce przeglądu uruchomiono pełny zestaw Viewera, bez ponawiania repo.
- Automatyczne Qt xcb na Linuksie: rzeczywisty wybór pliku i wersji w oknie,
  Phase na `subpixel.mpp`, usunięcie odniesienia, gamma 2, zapis i otwarcie.
  Zrzuty pokazują prawidłowy wybór aligned oraz odtworzony obrys 64 × 64
  na obszarze 68 × 67. Skrypt kontrolny potwierdził dokładne próbki,
  3969 ważnych pikseli i całą geometrię.
- Lokalny `data/MOVIE_3.MPP`: Phase, usunięcie pierwszej klatki,
  **16 klatek 398 × 398**, dokładna zgodność bajtów próbek i prostokątów.
  Wyniki zapisano pod nowymi nazwami w `/tmp/stmviewer-ticket13/`.
- Przegląd dwóch niezależnych agentów: Standards — jedna drobna duplikacja;
  Spec — jeden błąd P2 wspólnej skali. Obie poprawki zatwierdzone przez
  recenzentów, **0 otwartych ustaleń** w obu osiach.

Logi lokalne: `/tmp/stmviewer-aligned-full-suite.log`,
`/tmp/stmviewer-aligned-final-viewer-tests.log`,
`/tmp/stmviewer-aligned-baseline-failures.log`,
`/tmp/stmviewer-aligned-edge-repeat.log`, `/tmp/stmviewer-ticket13-probe.log`.
Zrzuty: `/tmp/stmviewer-ticket13/save-dialog.png` i `reopened.png`.

### Odbiór i integracja

Uruchomienie: z katalogu repo `conda activate netcat`, `python -m stmviewer.main`.
Ręczna próba użytkownika **oczekuje**; automatyczne offscreen/xcb nie są jej
zastępstwem. Windows 11 oraz opcjonalne odczytanie aligned z NaN w WSxM
pozostają niesprawdzone w tym etapie. Do ręcznej próby dostarczono istniejące
małe wzorce i `tests/stmviewer/check_aligned_mpp.py` z kontrolą wartości i geometrii.

Nie zmieniono współdzielonych aplikacji ani głównej konfiguracji; brak
nowej blokady integracyjnej. Istniejące czytniki wspólne nadal nie rozumieją
indywidualnej historii JSON; jej obsługa jest lokalna dla STM Viewera.
Historia ma limit 32 etapów i limit dodatku 64 MiB. MPP oraz JSON należy
przenosić razem. Nie jest to atomowa operacja dwóch plików przy twardym
zakończeniu procesu; niezgodny dodatek jest wtedy odrzucany przez SHA-256.


## 12: Potwierdzenie odbioru — 2026-10-26

Użytkownik potwierdził: „testy manualne 12 ok”.
[Ticket 12](implementation/issues/12-original-mpp.md) ma status **`done`**.
Implementacja i poprawki są w zakresie `7756c3d..6282365`, w tym eksport
`678269f`, korekta przeglądu `e24e560` i nagłówek WSxM `b887b2b`/`0cb6644`.
Aktualizacja potwierdzenia obejmuje tylko dokumentację; sprawdzono spójność
statusów i `git diff --check`, bez ponawiania testów kodu.
Nie przypisujemy temu ogólnemu potwierdzeniu pełnego odbioru obu platform;
pozostają osobne tickety platformowe. Ticket 13 — zapis aligned do MPP —
ma spełnione zależności 08 i 12, jest gotowy do podjęcia.

## 12: Nagranie Windows i zakres palety — 2026-10-23

Dalsze zgłoszenie słabego kontrastu w Windows sprawdzono na nagraniu
`bandicam 2026-10-23 19-19-29-772.mp4`. Kopia v2 z pendrive ma ten sam
SHA-256 co sprawdzony film. Objaw odtworzono w WSxM pod Wine przez wybór
zakresu palety całego filmu. Przełączenie **Settings → Movie Settings →
Palette range → Fit to frame Max/Min values**, zatwierdzenie i odświeżenie
klatki przywróciło szczegóły: kontrast percentylowy tej samej klatki 24 → 217.
Zmiana dotyczy wyłącznie konfiguracji podglądu WSxM. Kod i pliki pomiarowe
pozostały bez zmian, więc nie ponawiano testów aplikacji. [Raport](wsxm-investigation.md).
Ręczny odbiór ticketu 12 potwierdzono 2026-10-26. Użytkownik nie opisał
osobno wyniku zmiany ustawienia na Windows.

## 12: Poprawka odczytu MPP w WSxM — 2026-10-23

Baza poprawki: `7eab8e9`. Commity **`b887b2b`**, **`0cb6644`**.
[Raport diagnozy](wsxm-investigation.md),
[przegląd Standards/Spec](implementation/review-12-wsxm.md).

Pierwszy nagłówek CRLF z zakresem wartości przywracał odcienie, ale
pozostawiał przesunięcie obrazu. Nagrania użytkownika ujawniły pasek przy
lewej krawędzi. Rzeczywisty odczyt/zapis wzorca w WSxM wykazał zmianę
pozycji próbek: program odczytywał dane z offsetu odpowiadającego długości
natywnego układu nagłówka, niezależnie od poprawnej deklaracji jego rozmiaru.
Końcowa poprawka odtwarza ten układ, łącznie z wcięciami, odstępami między
sekcjami i pominięciem pustych sekcji. Dane nie są przeskalowywane ani
przesuwane w eksporterze. Pełne indywidualne metadane pozostają w JSON.

Wynik dla użytkownika: **`data/test-wsxm-v2.mpp` + `.stmviewer.json`**.
Oryginał `test.mpp` i pierwsza kopia `test-wsxm.mpp` nie były nadpisane.

Wykonane sprawdzenia:

- Publiczna regresja zapisu: RED przed poprawką, GREEN po poprawce;
  literalny nagłówek oparty na wzorcu sprawdzonym w rzeczywistym WSxM.
- Wszystkie 369 klatek v2 dokładnie zgodne ze źródłowymi S94: wartości,
  parametry, czasy i pochodzenie. Bajty pomiarów identyczne z oryginałem.
- WSxM 5.0 Develop 12.0, Wine 9: otwarcie i zapis całego filmu bez Plane,
  **24 182 784 próbek dokładnie zgodnych**, we właściwej kolejności.
  Oceniono zrzuty klatek 0/184/368; brak paska. Dodatkowy prostokątny
  film z czasami 2/5/9 s: **18 432 próbek zgodnych**, czasy zachowane.
- Końcowy zestaw Viewera: **217 passed, 2 skipped**, 22.07 s;
  obejmuje eksport przez czytniki NaPara/NanoTrack/MolTrack.
  Mypy strict: **23 pliki** bez błędów. `git diff --check` poprawny.
- Pełny zestaw repo po pierwszej poprawce: **2002 passed, 14 failed,
  16 skipped**, 230.78 s. Wszystkie identyfikatory niepowodzeń są zgodne
  z ticketem 12; brak nowych błędów. Końcowa korekta miała następnie pełne
  sprawdzenie Viewera, bez ponawiania całego repo.
  Logi: `/tmp/stmviewer-wsxm-full-suite.log`,
  `/tmp/stmviewer-wsxm-edge-viewer-tests.log`.
- Przegląd: Standards bez naruszeń, jedna uwaga do nieaktualnego opisu
  testu poprawiona; Spec bez uwag. Największy zmieniony plik kodu: 234 linie.

Próby Wine były automatyczne, sterowane GUI. Ręczny odbiór użytkownika
potwierdzono 2026-10-26; ticket 12 ma status `done`. Windows 11, NaN
w WSxM oraz indywidualna kalibracja JSON w tym zewnętrznym programie nie
zostały potwierdzone. Zmiana nie obejmuje wspólnych modułów. Instalacja
Wine/WSxM, dane i artefakty `/tmp/wsxm-investigation/` pozostają lokalne.


## 12: Zapis original do MPP — 2026-10-23

Gałąź `viewer/start`. Baza `7756c3d6e018ad1820f7400dc2d606b49d0975f2`.
Implementacja **`678269f`**, poprawki przeglądu **`e24e560`**.
[Ticket 12](implementation/issues/12-original-mpp.md): `done` po potwierdzeniu
ręcznego odbioru użytkownika 2026-10-26.

### Wynik

Przycisk Zapisz original MPP…, menu Plik i Ctrl+S zapisują całą pozostałą
serię original do MPP i `<nazwa MPP>.stmviewer.json`. Jedna klatka jest
obsługiwana; pusta seria wyłącza zapis. Wybrana klatka ani widok aligned
nie zmieniają zakresu. Gamma, zoom i opcja proporcji pikselowych nie trafiają
do eksportera. Dane to float64 little endian w konwencji orientacji MPP;
zachowane są NaN, pełne wymiary i dokładne skończone wartości.

Dodatek [V1](mpp-metadata-format.md) zachowuje własne parametry każdej klatki,
surowe nagłówki, braki i przerwy czasu oraz historyczne pochodzenie.
Wspólny nagłówek ma tylko wspólne znane parametry, a przy różnicach/nieznanych
wartościach jednostki umowne i Unknown. Znany prąd zapisuje się w nA, ponieważ
wspólny starszy parser myli A z angstromem. Pełne długie teksty pozostają
w JSON; reprezentacja w nagłówku mieści się w limicie czytnika.

Worker zapisuje dane partiami wierszy, bez kopii całej serii. Zapisany snapshot
to niezmieniana podczas operacji krotka obrazów. UI zatrzymuje Play i blokuje
nowy import, usuwanie, rejestrację oraz kolejny zapis; przeglądanie/gamma/zoom
pozostają dostępne. Przycisk Anuluj i zamknięcie okna kończą operację przez
worker. Spóźnione anulowanie po zakończonej publikacji nie udaje wycofania.

MPP i JSON powstają w katalogu tymczasowym obok celu. Przed podmianą
zabezpieczane są kopie istniejących plików; błąd/anulowanie przywraca parę.
Gdy samo przywracanie zawiedzie, kopie pozostają, a komunikat wskazuje katalog.
Dwa renamy nie są transakcją odporną na twarde zakończenie procesu: jeśli
pozostanie nowy MPP ze starym JSON, import wykryje niezgodność SHA-256.
Przerwanie procesu między podmianami sprawdzono osobnym podprocesem.

### Sprawdzenia

- TDD RED → GREEN: zapis z niezależnymi oczekiwaniami bajtowymi; bezpieczeństwo
  zastępowania pary; publiczne kontrolki GUI; poprawka długich tekstów UTF-8.
  Testy obejmują STP/S94/MPP, NaN, skrajne float64 i ujemne zero, długi
  nagłówek, indywidualne metadane, przeniesienie pary, błąd/krótki zapis,
  anulowanie pomiędzy publikacjami, twarde zakończenie procesu, blokady GUI,
  potwierdzenie nadpisania także samego JSON i zamknięcie podczas zapisu.
- Zestaw Viewera: **214 passed, 2 skipped**, 21.78 s. Pominięte istniejące
  opcjonalne testy lokalnego LoFTR; eksport nie zmienia modelu.
  Po poprawce przeglądu **38 passed**, 3.53 s: eksport, bezpieczeństwo,
  GUI eksportu, import metadanych i GUI importu; zawiera dodatkowy test UTF-8.
  Mypy strict: **23 pliki**, bez błędów.
- Pełny zestaw repo uruchomiony raz:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-original-mpp-full-pytest`.
  Kompletny log: **2000 passed, 14 failed, 16 skipped**, 231.70 s,
  bez błędów zbierania. Wszystkie 14 identyfikatorów niepowodzeń jest identyczne
  z `/tmp/stmviewer-mpp-metadata-full-suite.log`; brak nowych niepowodzeń.
  Log bieżący: `/tmp/stmviewer-original-mpp-full-suite.log`. Narzędzie sesji
  procesu zwróciło kod 143 po pełnym podsumowaniu pytest; podane wyniki
  pochodzą z logu zawierającego 100% testów i końcową listę niepowodzeń.
  Zestaw rozpoczęto dla `678269f`; poprawkę `e24e560` sprawdzono wymienionymi
  38 testami i mypy. Nie deklarujemy zielonego odbioru całego repo.
- Automatyczne rzeczywiste Qt xcb z dialogami: zapis/ponowne otwarcie
  znanych czasów po usunięciu środka, S94, mieszanych metadanych oraz
  **MOVIE_3: 17 klatek 256 × 256**. Dokładne wartości i parametry zachowane;
  źródła mają niezmienione SHA-256. Obejrzano dwa zrzuty podglądu.
  Skrypt/log/manifest: `/tmp/stmviewer-original-mpp-smoke.{py,log,json}`.
  Zrzuty: `/tmp/stmviewer-original-mpp-{saved,reopened}-xcb.png`.
- Sprawdzono CLI porównania eksportu na dwóch klatkach po usunięciu środka
  oraz generator wzorca na 4 × 16 × 16 z NaN i jego zapis/odczyt.
  Nie jest to odbiór dużej serii 1000 × 512 × 512 z ticketu 18/19.
- [Przegląd](implementation/review-12-original-mpp.md): jedno P2 Spec i drobna
  heurystyka Standards zamknięte po poprawce; **0 otwartych uwag** w obu osiach.
  Największy zmieniony plik kodu: **751 linii**, poniżej celu 1000 i limitu 1500.
  Sprawdzono lokalne odnośniki dokumentacji i `git diff --check`.

### Ręczny odbiór i integracja

[Instrukcja manualna](original-mpp-manual.md) podaje uruchomienie, gotowe dane,
generator dużego wzorca, raport dokładnego porównania oraz oczekiwane wyniki.
Ręczna próba użytkownika **potwierdzona 2026-10-26**; Qt offscreen i xcb
pozostają odrębnymi próbami automatycznymi. Dodatkowe sprawdzenia WSxM
opisano powyżej; potwierdzenie ticketu nie zamyka odbiorów platformowych.

Zmiany tylko w Viewerze, jego testach i dokumentacji. Nowych zależności nie ma;
bez zmian wspólnego kodu, konfiguracji, środowiska i pomiarów. Bez push/scalania.
Istniejące czytniki NaPara/NanoTrack/MolTrack czytają wartości i wspólne parametry
z typowych filmów. NaPara zwraca kolejność plikową, NanoTrack/MolTrack wykonują
własny obrót 180°. Dla integracji pozostają znane ograniczenia wspólnego
czytnika: limit 1000 linii nagłówka, błędna interpretacja A, nieznanej skali
oraz brak indywidualnych metadanych JSON. Eksporter używa nA; pełen kontrakt
nieznanych i mieszanych parametrów zapewnia para otwierana w Viewerze.
Eksport aligned i geometria są zakresem ticketu 13, odblokowanego po
potwierdzeniu ręcznego odbioru ticketu 12.

## 11: Otwarcie MPP z metadanymi towarzyszącymi — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`b71305bfb2886d734cc087708780f22ea12fd30d`. Implementacja: `137655d`.
Ticket: [11-mpp-metadata-import](implementation/issues/11-mpp-metadata-import.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Raport implementacji i przeglądu: `33a672b`. Commit potwierdzenia odbioru
podany w wiadomości sesji.

### Wynik i kontrakt

MPP automatycznie szuka obok siebie dodatku `<pełna nazwa MPP>.stmviewer.json`.
[Kontrakt V1](mpp-metadata-format.md) wiąże go ze wszystkimi bajtami filmu
przez SHA-256, liczbą oraz kształtem klatek. Skrót powstaje na tych samych
bajtach, które są dekodowane; uwzględnia nagłówek i ewentualny koniec pliku.
Przeniesienie lub wspólna zmiana nazwy pary zachowuje powiązanie.

Adapter w Viewerze waliduje cały JSON przed nałożeniem jakichkolwiek danych.
Wersja, format, rodzaj obrazu, komplet pól, typy, skończone wartości, dodatnia
skala i integralność muszą się zgadzać. JSON UTF-8 ma limit 64 MiB; powtórzone
klucze, NaN i Infinity są odrzucane. Błąd dowolnego rekordu odrzuca cały
dodatek. Brak, nieprawidłowy dodatek i błąd jego odczytu pozostawiają działający
film z metadanymi nagłówka oraz widoczną przyczyną. Anulowanie jest odrębne:
zachowuje poprzednią serię, jej pozycję, gamma i kadr. Praca jest w istniejącym
workerze, z punktami anulowania przy odczycie i walidacji rekordów.

Każda klatka odzyskuje własne parametry, kanał, jednostkę, surowy nagłówek,
czasy i ich źródłowy opis oraz informację o kalibracji. Null i rzeczywiste
zero pozostają rozróżnione; nie zgadujemy parametrów z nagłówka ani nie
przeliczamy próbek. `ImageFrame.source` oraz `source_frame_index` nadal
wskazują faktycznie otwarty plik i indeks w nim. Nowe `provenance` przechowuje
historyczną ścieżkę jako tekst i historyczny indeks od zera. Ścieżka jest
zachowana dosłownie, także Windows i względna; nie jest rozwiązywana/otwierana.

Panel i podpowiedzi miniatur rozdzielają obie lokalizacje i numery;
miniatury pokazują historyczne nazwy, a bieżąca pozycja nadal należy do serii.
Usuwanie nie zmienia pochodzenia pozostałych klatek. Komunikat o dodatku
pozostaje przy nawigacji i znika po opróżnieniu lub otwarciu STP/S94.

### Sprawdzenia i odbiór

- TDD red → green: indywidualne metadane przez publiczny import; odrzucenie
  całego nieprawidłowego dodatku; prezentacja przez publiczne kontrolki GUI.
  Pozostałe próby obejmują zmianę nagłówka/próbek/końca MPP, przeniesienie
  i zmianę nazwy pary, null/zera/typy, brak/uprawnienia, anulowanie odczytu
  dodatku i zachowanie starego podglądu. Oczekiwane liczby i orientacja
  wzorców są niezależne od przyszłego eksportera.
- **193 testy Viewera zaliczone, 2 pominięte**, 18.86 s. Pominięcia to
  istniejące opcjonalne próby rzeczywistego LoFTR bez ścieżki do wag;
  ticket 11 nie dotyka modelu. **Mypy strict: 21 plików**, bez błędów.
- Automatyczne rzeczywiste GUI Qt xcb z dialogami plików: poprawny dodatek,
  sześć przypadków braku/odrzucenia, wszystkie klatki i parametry, przeniesiona
  oraz przemianowana para, usunięcie pierwszej klatki z zachowaniem obu
  indeksów, lokalny MOVIE_3 (17 klatek) bez dodatku — zaliczone.
  Źródła zachowały SHA-256. Obejrzano zrzuty poprawnego i odrzuconego dodatku.
  Skrypt/log/manifest: `/tmp/stmviewer-mpp-metadata-smoke.{py,log,json}`;
  zrzuty `/tmp/stmviewer-mpp-metadata-{valid,rejected,measurement}-xcb.png`.
- Pełne repo uruchomione raz w netcat:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-mpp-metadata-full-pytest`:
  **1979 passed, 14 failed, 16 skipped**, 229.88 s, bez błędów zbierania.
  Wszystkie 14 niepowodzeń MolTrack/NanoTrack jest identyczne z ticketem 10;
  nie ma nowych niepowodzeń. Całe repo nadal nie ma zielonego odbioru.
  Log `/tmp/stmviewer-mpp-metadata-full-suite.log`; porównanie z
  `/tmp/stmviewer-deep-full-suite.log`.
- [Code-review](implementation/review-11-mpp-metadata-import.md): Standards — 0,
  Spec — 0. Kod po przeglądzie niezmieniony. Generator odtwarza wszystkie
  13 plików bajtowo. `git diff --check` i lokalne odnośniki poprawne;
  największy zmieniony plik kodu ma **640 linii**, poniżej celu 1000 i limitu 1500.
- [Instrukcja manualna](mpp-metadata-manual.md) zawiera uruchomienie,
  gotowe poprawne/błędne pary i oczekiwane parametry. Użytkownik potwierdził
  ręczny odbiór 2026-10-23: „testy manualne ok”. Nie wskazał systemu;
  potwierdzenie nie zamyka odrębnych odbiorów platform. Tekstowe ścieżki
  Windows sprawdzono automatycznie na Linuksie; to nie zastępuje odbioru
  Windows. Aktualizacja odbioru zmienia wyłącznie dokumentację; testów
  automatycznych nie ponawiano.

### Integracja i następne etapy

Zmiany wyłącznie w Viewerze, jego testach i dokumentacji. Nie zmieniono
wspólnych czytników, konfiguracji głównej, środowiska ani lokalnych pomiarów.
Nowych zależności nie ma; moduły modelu/metadanych nie importują Qt.
Nie publikowano ani nie scalano gałęzi.

Ticket 12 powinien zapisywać ten kontrakt dla original. Przy ponownym
zapisywaniu zaimportowanej pary należy zachować istniejące `provenance`;
dla klatki bez niego pochodzenie pochodzi z `source/source_frame_index`.
Nie należy zastępować historii nazwą najnowszego kontenera MPP. Wersja 1
jawnie odrzuca rodzaj aligned; ticket 13 ma rozszerzyć wersjonowany kontrakt
z zachowaniem odczytu V1 i dodać geometrię, maskę, historyczne odniesienie
oraz ich podgląd. Ten etap nie wprowadza eksportera ani odtwarzania historii
rejestracji, nie obiecuje zgodności dodatku z zewnętrznymi programami.


## 10: Diagnoza obwódki na cpu.mpp — 2026-10-23

Baza: `3ba1ea0`, gałąź `viewer/start`. Zmiana wyłącznie dokumentacji:
[wyjaśnienie i porównanie w GUI](deep-matcher-manual.md#obwódka-przy-ostrych-krawędziach-wzorca).
Diagnoza zapisana w `2b13195`. Następnie użytkownik potwierdził ręczny odbiór
2026-10-23; ticket 10 ma status `done`. Samo wcześniejsze zgłoszenie
nie stanowiło jeszcze odbioru.

Dwie próby rzeczywistego LoFTR CPU odtworzyły pas przy krawędzi ciemnego
obiektu. Klatka 3: XY = (−0,7461051941; +0,9392890930) wobec dokładnego
(−1; +1) wynikającego z generatora `np.roll`. W punkcie lewej krawędzi
różnica względem klatki odniesienia wynosi 0,352253 jednostki danych.
Minimalna próba z dwiema klatkami i tym zmierzonym przesunięciem odtwarza
identyczny efekt bez modelu i GUI. Zmiana wyłącznie przesunięcia na (−1; +1)
sprowadza tę różnicę do zera. Rzeczywisty Phase również daje (−1; +1) i zero.

Niezależny rachunek wag czterech sąsiadów dla wszystkich 6241 ważnych próbek
klatki 3 potwierdza interpolację biliniową z maksymalnym błędem
4,44 × 10⁻¹⁶. Żadna próbka nie wychodzi poza zakres swoich czterech sąsiadów.
Na lewej krawędzi udział tła wynosi 25,3895%, obiektu 74,6105%.
To wyjaśnia pas wartości pośrednich widoczny na zrzucie. Nie jest wymagane
poprawianie implementacji interpolacji; zaokrąglenie do pikseli zmieniłoby
uzgodniony kontrakt rejestracji subpikselowej. Zmierzony błąd estymacji modelu
mieści się w obecnej tolerancji testu 0,75 px; nie dowodzi dokładności
modelu na innych obrazach. Nie zmieniono kodu, danych ani wag.

Diagnostyka lokalna: `/tmp/stmviewer-halo-probe.py` (rzeczywisty model),
`/tmp/stmviewer-halo-minimal.py` (domyślnie zmierzona translacja;
`--integer` przełącza na dokładną), macierze `/tmp/stmviewer-halo-arrays.npz`
i porównanie `/tmp/stmviewer-halo-comparison.png`. Warunek wykrywający
widoczny pas celowo zgłasza błąd w obu próbach ułamkowych i przechodzi
w próbie całkowitej. Jest to detektor objawu, nie nowy wymóg testów aplikacji.
Zrzut porównania obejrzano. Wszystkie próby automatyczne; GUI użytkownika
oraz Windows nie były ponownie testowane. Pełnego zestawu nie powtarzano
przy tej zmianie dokumentacji. Commit przekazania podany w wiadomości sesji.


## 10: Deep Matcher z lokalnymi wagami — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`d899ea0648af2ab507b41fc24d2c2bdcf5c356c2`. Commit implementacji: `30ddddf`.
Ticket: [10-deep-matcher](implementation/issues/10-deep-matcher.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Raport implementacji i przeglądu: `3ba1ea0`; diagnoza obwódki: `2b13195`.
Commit potwierdzenia odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Deep Matcher ma pole lokalnego checkpointu, wybór Auto/CPU/CUDA i Sprawdź
model. Pole można wypełnić przez `STMVIEWER_LOFTR_WEIGHTS`. Domyślnie jest
puste. Wstępna kontrola sprawdza plik i moduły, bez importowania modelu;
panel nie twierdzi wtedy, że model został już zweryfikowany. Sprawdź model
można uruchomić przed wczytaniem obrazów; nie zmienia istniejącego aligned.

Import bibliotek, ładowanie i weryfikacja wag oraz rejestracja działają
w QThread, z postępem i punktami anulowania. Checkpoint jest czytany przez
`torch.load(weights_only=True)` na CPU, następnie `LoFTR(pretrained=None)`
sprawdza ścisłą zgodność parametrów i przechodzi na wybrane urządzenie.
Nie ma pobierania bibliotek/wag. Auto wybiera CUDA, gdy Torch zgłasza jego
obecność, inaczej CPU; błąd wykonania na CUDA nie powoduje ponowienia na CPU.
Wykonywana jest rzeczywista operacja na urządzeniu, a wynik zapisuje jego
numer/nazwę. Zmiana wyboru metody lub urządzenia nie zmienia starego wyniku.

Każde Rejestruj ponownie ładuje wskazany plik. Jeden model obsługuje wszystkie
pary danej próby. Adapter zachowuje normalizację NanoTrack i domyślny
konsensus translacji XY. Wykorzystuje istniejący punkt
`DeepMatcherTranslationBackend(matcher=...)`, bez modyfikacji wspólnego kodu.
Geometria, sąsiednie oryginały, kumulacja względem pierwszej klatki, statusy,
interpolacja, publikacja kompletnego wyniku i usuwanie pozostają wspólne
z wcześniejszymi metodami. Błąd, brak zasobów i anulowanie zachowują poprzedni
wynik. Rozdzielczość wejścia nie jest zmieniana dla modelu.

### Sprawdzenia i odbiór

- TDD red → green w zatwierdzonych granicach rejestracji i publicznego GUI.
  Kontrolowany model używa prawdziwego Torch i konsensusu NanoTrack;
  sprawdza znane XY, lokalny odczyt, niezgodne/uszkodzone/brakujące wagi,
  brak bibliotek, Auto/CPU/CUDA, błędy zasobów i anulowanie. Testy GUI
  sprawdzają stare aligned, blokady, nawigację, gamma i zoom w trakcie pracy.
- **177 testów Viewera zaliczonych, 2 opcjonalne pominięte**, 18.58 s.
  Te dwie próby rzeczywistych wag wykonano osobno po ustawieniu
  `STMVIEWER_TEST_LOFTR_WEIGHTS`: **2 passed**, CPU i CUDA, 1.72 s,
  przy zablokowanych funkcjach pobierania. Log: `/tmp/stmviewer-deep-real-tests.log`.
  **Mypy strict: 19 plików**, bez błędów.
- Rzeczywisty checkpoint LoFTR outdoor: 46 341 978 bajtów,
  SHA-256 `21f5bec5968178e8bc8b7633441836fe5de4f47d861dd2cd7dc38e271b0479ec`,
  11 561 456 parametrów. Ścieżka w [instrukcji](deep-matcher-manual.md).
  Torch 2.9.1+cu128, Kornia 0.8.2, kornia_rs 0.1.10; CUDA:0,
  NVIDIA GeForce RTX 5090. Sprawdzono rzeczywistą operację CUDA oraz model,
  a nie samą nazwę GPU. Niczego nie instalowano ani nie pobierano.
- Automatyczne GUI Qt xcb z prawdziwymi dialogami: Phase → brak wag →
  wybór pliku → Sprawdź model/Rejestruj na CPU, CUDA i Auto. Dla klatki 2
  wzorca CPU: XY około (1.955, −1.072), CUDA: (1.956, −1.072), obszar 83 × 83.
  Auto wybrało CUDA. Błędne wagi i rzeczywiste anulowanie zachowały stary wynik.
  Pełny MOVIE_3, 17 klatek, zakończył się wynikiem 312 × 291 px.
  To potwierdzenie wykonania i prezentacji, nie fizycznej poprawności każdego
  dopasowania. Źródła oraz wagi zachowały SHA-256. Obejrzano zrzuty GUI.
  Skrypt/log/manifest: `/tmp/stmviewer-deep-smoke.{py,log,json}`;
  zrzuty `/tmp/stmviewer-deep-{CPU,CUDA,Auto,measurement}-xcb.png`
  oraz `/tmp/stmviewer-deep-missing-settled-xcb.png`.
- Pełne repo, uruchomione raz w netcat:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-deep-full-pytest`:
  **1963 passed, 14 failed, 16 skipped**, 227.13 s, bez błędów zbierania.
  Zestaw 14 niepowodzeń MolTrack/NanoTrack jest identyczny z ticketem 09;
  brak nowych niepowodzeń. Całe repo nadal nie ma zielonego odbioru.
  Log `/tmp/stmviewer-deep-full-suite.log`; porównanie z
  `/tmp/stmviewer-cpu-full-suite.log`.
- [Code-review](implementation/review-10-deep-matcher.md): Standards — 0,
  Spec — 0. Kod po przeglądzie niezmieniony. `git diff --check` i lokalne
  odnośniki dokumentacji poprawne; największy zmieniony plik kodu ma 634 linie.
- [Instrukcja manualna](deep-matcher-manual.md) zawiera uruchomienie,
  wzorzec, lokalne wagi i scenariusze. Użytkownik potwierdził ręczny odbiór
  2026-10-23: „testy manualne ok”, po wyjaśnieniu obwódki interpolacyjnej.
  Nie wskazał systemu ani urządzenia użytego do próby; potwierdzenie nie
  zamyka odrębnych odbiorów platform. Aktualizacja odbioru dotyczy wyłącznie
  dokumentacji; testów automatycznych nie ponawiano.

### Integracja

Zmiany wyłącznie w Viewerze, jego testach i dokumentacji. Wspólne moduły,
konfiguracja główna, pomiary i istniejące środowisko netcat niezmienione.
Opcjonalne zależności zapisano w `stmviewer/requirements-deep.txt`;
instrukcja rozdziela instalację CPU i CUDA. Ewentualne wspólne wydzielenie
lokalnego loadera może prowadzić integracja, ale nie blokuje tej funkcji.
Nie publikowano ani nie scalano gałęzi.

## 09: Pozostałe metody rejestracji CPU — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`b8dcc4596988e8a2ee529f60b860f030b1be9749`.
Ticket: [09-cpu-registration-methods](implementation/issues/09-cpu-registration-methods.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Commit implementacji: `3e31161`; poprawka importu testowego: `5d4ea6b`.
Raport implementacji i przeglądu: `935c638`; pełny zakres `b8dcc45..HEAD`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Lista rejestracji zawiera Phase, Tile+RANSAC, ECC i Optical Flow.
Adapter używa istniejącej `build_registration_backend_from_settings` NanoTrack,
`reference_strategy=adjacent`, `registration_view=raw`, pustych backend_params.
Nie zmieniano algorytmów, progów ani domyślnych parametrów. ECC ma własne
wstępne oszacowanie Phase, a Optical Flow używa mediany TV-L1 do wyznaczenia
jednego przesunięcia XY. Brak automatycznego zastępowania metody po błędzie.

Wybór jest zapamiętany w uruchomionym zadaniu, a nazwa metody w kompletnym
wyniku. Zmiana listy nie zmienia starego aligned, jego opisu ani kadru.
Wszystkie metody korzystają z cyklu, geometrii, interpolacji i anulowania
wprowadzonego w tickecie 08. Usuwanie zachowuje także metodę starego wyniku.
Niska pewność/manual_review pozostają dostępne i są dziedziczone jak wcześniej.
Błąd, failed, brak wyniku lub nieprawidłowe XY odrzuca całą nową próbę.

Lokalna dostępność sprawdzana jest przy starcie okna. Brak OpenCV wyłącza
wyłącznie ECC. Brak SciPy/scikit-image wyłącza rejestrację, zachowując start
aplikacji, import i przeglądanie. Powód pojawia się osobno od opisu starego
wyniku; niedostępne metody pozostają na liście. Instalacja biblioteki wymaga
ponownego startu. Program nie instaluje ani nie pobiera zależności.

### Sprawdzenia i odbiór

- TDD: red → green dla wyboru realnych backendów i porównania z domyślnym
  NanoTrack, wyboru metody w GUI oraz braku OpenCV. Kontrolowane wyniki
  i błędy uzupełniają próby prawdziwych metod; nie zastępują oceny dopasowania.
- **155 testów Viewera zaliczonych**, w tym 32 nowe. **Mypy strict: 17 plików**
  bez błędów. Opcjonalne cv2 ma ignore_missing_imports w lokalnej konfiguracji.
- Nowe testy obejmują wszystkie trzy metody, znane XY, status/quality zgodne
  z NanoTrack, postęp, usuwanie oraz zachowanie starego aligned po anulowaniu,
  wyjątku, failed, braku wyniku i nieprawidłowym XY. Kontrolowane manual_review
  i low_confidence sprawdzają kompletny wynik, dziedziczenie i ostrzeżenia GUI.
- Osobne procesy z pustym cache importów i kontrolowanym brakiem cv2/scipy/skimage:
  rzeczywisty start okna, import MPP i widoczne powody niedostępności przeszły.
  To symulacja na granicy importu bibliotek, nie instalacja nowego środowiska.
- Automatyczna próba Qt xcb z rzeczywistymi dialogami: cztery metody na
  `cpu.mpp` i `data/MOVIE_3.MPP`, zmiana wyboru, błąd ECC, rzeczywiste anulowanie
  Optical Flow, usunięcie odniesienia — zaliczona. SHA-256 źródeł zachowane.
  Obejrzano zrzuty ECC/wzorca i Optical Flow/pomiaru. To nie ręczny odbiór.
  Skrypt, log i manifest: `/tmp/stmviewer-cpu-smoke.{py,log,json}`;
  zrzuty `/tmp/stmviewer-cpu-{cpu,MOVIE_3}-{Phase,TileRANSAC,ECC,OpticalFlow}.png`.
- Na wzorcu 80 × 80 przesunięcia są zgodne z (0,0), (2,−1), (−1,1),
  z tolerancją 0,3 px dla metod subpikselowych. Aligned: Phase/Tile 83 × 82,
  ECC 84 × 83, Optical Flow 84 × 84 px. Generator odtwarza plik bajtowo.
- Lokalny MOVIE_3, 17 klatek: Phase 398 × 398, Tile+RANSAC 256 × 305,
  Optical Flow 274 × 281 px, z oznaczeniami niepewności. ECC nie zbiega się
  dla pary 2 → 3 i zachowuje wcześniejszy wynik. To test kontraktu i prezentacji,
  nie potwierdzenie fizycznej poprawności dopasowań każdego pomiaru.
- Pełne repo uruchomione raz w netcat:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-cpu-full-pytest`:
  **1934 passed, 14 failed, 14 skipped, 1 błąd zbierania**, 225.91 s.
  Log: `/tmp/stmviewer-cpu-full-suite.log`. Wszystkie 14 niepowodzeń
  MolTrack/NanoTrack jest identyczne z listą ticketu 08; brak nowych failed.
  Nowy błąd zbierania wynikał z importu `test_registration` z MolTrack zamiast
  pomocnika Viewera. Poprawiono w `5d4ea6b`, używając publicznego odczytu gotowego
  `cpu.mpp`. Powtórka dwóch modułów CPU wraz z kolidującym modułem MolTrack
  w tej samej konfiguracji ścieżek/importlib: **36 passed**, 2.36 s.
  Ponowne zbieranie całego repo: **1969 testów, bez błędów**, 0.85 s;
  log `/tmp/stmviewer-cpu-collection.log`. Całego wykonania nie powtarzano.
  Pełny zestaw repo nadal nie ma zielonego odbioru.
- [Przegląd Standards/Spec](implementation/review-09-cpu-registration.md):
  Standards — 0; Spec — 0, także po poprawce testu. Kod aplikacji po przeglądzie
  nie był zmieniany. `git diff --check` bez błędów; największy zmieniony plik
  Python ma **608 linii**, poniżej celu 1000 i limitu 1500.
- [Instrukcja manualna](cpu-registration-manual.md), wzorzec i generator są
  w repo. Użytkownik potwierdził pozytywny wynik testów manualnych 2026-10-23.
  Nie podał systemu ani szczegółów osobnej próby środowiska bez OpenCV.
  Potwierdzenie zamyka ticket 09, lecz nie oznacza zaliczenia odrębnych
  odbiorów platform. Zmieniono wyłącznie dokumentację; testów automatycznych
  nie ponawiano.

### Integracja

Zmiany wyłącznie w Viewerze, jego testach i dokumentacji. Wspólne moduły,
konfiguracja główna i pomiary pozostają bez zmian. Podstawowy zestaw zależności
obsługuje Phase/Tile/Optical Flow. Lokalny `stmviewer/requirements-ecc.txt`
dodaje opencv-python 4.11.0.86, użyty w netcat; [README](README.md#uruchomienie)
podaje instalację dla Ubuntu 24.04 i Windows 11. Zmiana wspólnych zależności
nie jest potrzebna do tego ticketu. Deep Matcher pozostaje w tickecie 10.

## 08: Rejestracja Phase i pełny widok aligned — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`1dc159ee48341b2180cea47947a3fb38d59dd0c6`.
Ticket: [08-phase-registration](implementation/issues/08-phase-registration.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Commit implementacji: `2fea452`; końcowy raport: `c4c6fe5`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Lokalny runner korzysta z istniejącego `PhaseCorrelationShiftBackend`
(default: upsample 20, normalization phase, min_texture_std 1e-8,
peak_exclusion_radius 3, low_confidence_peak_ratio 3). Jak NanoTrack UI używa
raw, sąsiednich oryginałów i kumulacji XY, jakości minimum i najgorszego statusu.
Nie zmieniano algorytmu ani progów. Pojedyncza klatka ma przesunięcie zerowe.

`RegistrationResult` przechowuje pole każdej klatki, przesunięcia, status,
maskę, cały obszar i lekkie historyczne pochodzenie odniesienia. Metadane
źródeł pozostają w oryginalnych `ImageFrame`. Aligned ma float64 i NaN,
SciPy affine_transform order=1, constant NaN, bez ekstrapolacji. Geometria
odpowiada NanoTrack (ceil marginesów); lokalny materializator zachowuje
float64 oraz punkty anulowania między klatkami. Wspólna kalibracja wynika
z każdej klatki, a przy braku/niezgodności aligned ma proporcje pikselowe.
Pole źródłowe opisuje prostokąt krawędzi pikseli; maska nie określa jego rozmiaru.

QThread publikuje tylko kompletny wynik. Start zatrzymuje Play i blokuje
import/usuwanie/metodę/Play/kolejną próbę. Nawigacja, widoki i ustawienia
obrazu pozostają dostępne. Anulowanie utrzymuje blokady do końca pracy;
zamykanie okna także czeka na zakończenie. Błąd lub anulowanie zachowują
stary wynik i zmiany bieżącego podglądu. Sukces dopasowuje nowe aligned
aktualnej klatki, zachowuje gamma i zapisany kadr original.

Miniatury pozostają original gamma 1; ostrzegają o niepewności, także
odziedziczonej. Usuwanie nie interpoluje ponownie, nie przycina obszaru
ani nie usuwa historycznego odniesienia/niepewności. Rejestracja po usunięciu
korzysta z pozostałych oryginałów i tworzy nowe odniesienie. Nowa seria
czyści wynik; nieudany import go zachowuje.

### Sprawdzenia i odbiór

- TDD w uzgodnionych granicach: znaki/kumulacja, subpiksele i maska ≠ pole,
  anulowanie aligned, błędy i niekompletny wynik, historyczne odniesienie,
  wspólna skala, GUI i bezpieczne zamknięcie. Kontrolowane wyniki backendu
  sprawdzono osobno od rzeczywistego Phase oraz porównania z runnerem NanoTrack.
- **123 testy Viewera zaliczone**, w tym 20 nowych; **mypy strict 17 plików**.
- Automatyczna próba Qt xcb z rzeczywistymi dialogami i lokalnym MOVIE_3.MPP
  przeszła. Źródła zachowały bajty/hash; obejrzano zrzuty aligned/subpixel/pomiar.
  Skrypt i log: `/tmp/stmviewer-phase-smoke.py`, `/tmp/stmviewer-phase-smoke.log`.
  Zrzuty: `/tmp/stmviewer-phase-{aligned,subpixel,uncertain,measurement}-xcb.png`.
  MOVIE_3: 17 klatek, wynik **398 × 398**, 16 niepewnych klatek
  (łącznie z odziedziczoną niepewnością); manifest SHA-256 i przesunięcia:
  `/tmp/stmviewer-phase-measurement.json`. To test wykonania/prezentacji,
  nie potwierdzenie fizycznej poprawności wszystkich dopasowań.
- Pełny zestaw repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors -o cache_dir=/tmp/stmviewer-phase-full-pytest`:
  **1909 passed, 14 failed, 14 skipped**, 222.93 s. Wszystkie 14 identyfikatorów
  niepowodzeń MolTrack/NanoTrack występuje w poprzednim logu ticketu 07;
  brak nowych niepowodzeń oraz błędów zbierania. Wcześniejszy timeout workera
  SAM2 nie powtórzył się. Nie jest to zielony odbiór całego repo. Log:
  `/tmp/stmviewer-phase-full-suite.log`, porównanie z
  `/tmp/stmviewer-deletion-full-suite.log`.
- [Przegląd Standards/Spec](implementation/review-08-phase-registration.md):
  Standards — 0 uwag; Spec — 0 usterek kodu, 1 drobna uwaga do instrukcji
  manualnej, poprawiona po przeglądzie. Nie zmieniano kodu po testach.
- Generator odtwarza pięć wzorców bajtowo. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **590 linii** (limit 1500).
  `git diff --check` oraz lokalne odnośniki zmienionej dokumentacji poprawne.
- [Instrukcja manualna](phase-registration-manual.md) i pięć małych filmów
  oraz generator są w repo. Użytkownik potwierdził ręczny odbiór 2026-10-23:
  „testy manualne ok”. Nie wskazano systemu; potwierdzenie nie zamyka
  odrębnych odbiorów platform. Zmieniono wyłącznie dokumentację,
  bez ponawiania testów automatycznych.

### Integracja

Lokalne wymagania Viewera rozszerzono o sprawdzone SciPy 1.15.2 i scikit-image
0.25.2. Mypy pomija śledzenie starego NanoTrack i brak stubów SciPy; sam kod
Viewera pozostaje strict. Nie zmieniono konfiguracji głównej ani wspólnych
modułów. Istniejący batch/materializator NanoTrack nie mają punktów anulowania,
więc Viewer używa lokalnego cyklu z tym samym backendem i regułami geometrii.
Wspólne wydzielenie runnera/materializatora może koordynować sesja integracyjna;
nie jest blokadą obecnej funkcji. Pozostałe metody: 09–10; duża seria: 18.

## 07: Usuwanie klatek z zachowaniem czasu i pochodzenia — 2026-10-23

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`e8102e9d21924c8d661e72df223a46343e0183ff`.
Ticket: [07-frame-deletion](implementation/issues/07-frame-deletion.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-23.
Commit implementacji: `bfffd83`; końcowy raport: `6f35585`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Przycisk Usuń klatkę jest pod obrazem. Zatrzymuje Play, usuwa tylko bieżący
obraz z pamięci serii i pokazuje następną klatkę (dla ostatniej poprzednią).
Usunięcie jedynej czyści obraz, źródło, metadane, zaznaczenie i miniatury;
numer pokazuje 0 z 0, a kontrolki obrazu/nawigacji/Play/usuwania są nieaktywne.
Nowe poprawne otwarcie po opróżnieniu przywraca normalne działanie.

Pozostałe obiekty ImageFrame zachowują dane, pochodzenie, parametry i czasy.
Usuwamy odpowiadającą parę obraz/miniatura; pozycje są ponownie numerowane,
cache ikon odświeżany, a źródłowy indeks MPP oraz czas nie są przeliczane.
Gamma, zoom, przesunięcie i Proporcje pikselowe są zachowane dla następnego
obrazu. Źródła pozostają bez zmian; nie dodano cofania ani odwracania.

Podczas importu w tle można edytować starą serię. Błąd i anulowanie zachowują
jej aktualny, skrócony lub pusty stan. Sukces zastępuje ją nową kompletną serią.
Wynik aligned należy do ticketu 08; usuwanie trzeba z nim połączyć zgodnie
z mapą, zachowując geometrię pozostałych klatek.

### Sprawdzenia i odbiór

- TDD: red → green przez publiczne kontrolki dla usunięcia podczas Play,
  wyboru następnej/poprzedniej i opróżnienia programu. Dalsze testy sprawdzają
  czasy 10/20/35 s i częściowe braki, metadane mieszanych STP/S94, ustawienia
  podglądu, niezmienność źródeł i współpracę z importem.
- **103 testy Viewera zaliczone** w Qt offscreen, w tym 10 nowych przypadków.
- Mypy strict: **15 plików bez błędów**.
- Automatyczna próba rzeczywistego okna Qt xcb przeszła z dialogiem, nowym
  wzorcem known-times.mpp i lokalnym data/MOVIE_3.MPP (17 klatek).
  Sprawdzono usunięcie środka/ostatniej/jedynej, Pause, czas, źródło, ponowne
  otwarcie i niezmienność zawartości źródeł (porównanie bajtów/hash SHA-256).
  Skrypt: `/tmp/stmviewer-deletion-smoke.py`; zrzuty:
  `/tmp/stmviewer-deletion-{middle,empty,measurement}-xcb.png`.
  Oceniono wizualnie. To próba automatyczna, odrębna od późniejszego
  potwierdzenia użytkownika; odbiór Windows pozostaje w osobnym tickecie.
- Pełny zestaw repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1888 passed, 15 failed, 14 skipped**, 241.66 s, bez błędów zbierania.
  Wszystkie niepowodzenia dotyczą MolTrack/NanoTrack. Log:
  `/tmp/stmviewer-deletion-full-suite.log`. Obecne lokalne `data/` usuwa
  wcześniejszy brak pomiarów; nie przypisujemy zmniejszenia liczby błędów
  implementacji usuwania klatek.
- Sprawdzenie niepowodzeń na czystym archiwum bazy `e8102e9` z dowiązanym
  tym samym `data/`, tym samym Pythonem i opcjami pytest: **13 failed,
  2 passed**, 10.03 s. Wszystkie 13 identyfikatorów i rodzaje błędów pokrywają
  się z pełną próbą: starsze ścieżki Windows/SAM2 i stan GUI MolTrack/NanoTrack.
  Log: `/tmp/stmviewer-deletion-baseline.log`; checkout:
  `/tmp/stmviewer-deletion-baseline-u84rcczz`.
  Dwa pozostałe testy NanoTrack —
  `test_edge_correction_and_resume_replace_suffix` (niewymieniona polilinia)
  i `test_real_worker_cli_roundtrips_batch_contract_with_injected_sam2_repo`
  (timeout 10 s) — przeszły również osobno na bieżącym kodzie: **2 passed**,
  1.33 s, log `/tmp/stmviewer-deletion-recheck.log`.
  Ich przyczyny w pełnym zestawie nie ustalono; brak powtarzalnej regresji
  nie oznacza zielonego odbioru całego repo. Nie zmieniano starszych aplikacji.
- [Przegląd Standards/Spec](implementation/review-07-frame-deletion.md):
  **0 uwag w obu osiach**. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **424 linie** (limit 1500).
  `git diff --check` i lokalne odnośniki zmienionej dokumentacji poprawne.
- [Instrukcja ręczna i wzorce](frame-deletion-manual.md). Nowy mały film
  known-times.mpp jest odtwarzany przez istniejący generator MPP.
  Użytkownik potwierdził ręczny odbiór 2026-10-23: „testy manualne ok”.
  Nie wskazano systemu; potwierdzenie nie zamyka odrębnych odbiorów platform.
  Zmieniono wyłącznie dokumentację, bez ponawiania testów automatycznych.

Nie zmieniono wspólnych modułów, zależności ani głównej konfiguracji.
Nie ma nowego wymagania integracyjnego blokującego tę funkcję.

## Lokalny katalog danych — 2026-10-21

Użytkownik udostępnił `/home/rlew/projekty/NEtCAT-viewer/data/` do testów.
W kolejnych zadaniach korzystać przede wszystkim z tej lokalizacji.
Sprawdzono obecność 515 STP, 370 S94 i 10 MPP oraz ignorowanie `data/` przez Git.
Bieżący spis: [aktualizacja inwentarza](acceptance-reconnaissance.md).
Nie zmieniano plików pomiarowych ani nie ponawiano testów przy aktualizacji
lokalizacji. Starsze raporty zachowują faktycznie użyte ścieżki i wyniki.
Obecność `data/MOVIE_3.MPP` może usunąć wcześniejszy brak danych w testach
repozytorium; kolejny wynik porównać z bazą, uwzględniając tę zmianę środowiska.

## 06: Play, Pause i tempo odtwarzania — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`0d57200d4d606292f95fe56cca831c78e437673f`.
Ticket: [06-playback](implementation/issues/06-playback.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.
Commit implementacji: `83c20a9`; końcowy raport: `0f3229d`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Sterowanie pod obrazem: Play/Pause, domyślnie 5 kl./s, wybór 1/2/5/10/20/30,
pętla domyślnie wyłączona. Pause pozostawia bieżący obraz. Bez pętli film
kończy się na ostatniej; Play na końcu pokazuje pierwszą od razu.
W pozostałych pozycjach wznawia od bieżącej. Pusta i pojedyncza seria mają
nieaktywne Play. Zamknięcie okna zatrzymuje odtwarzanie.

Ręczny wybór miniaturą, suwakiem, numerem i przyciskami zatrzymuje Play.
Kliknięcie bieżącej miniatury lub uchwytu suwaka także zatrzymuje film;
wpisywanie numeru zatrzymuje go przed zatwierdzeniem. Synchronizacja miniatur
przez odtwarzanie nie udaje ręcznej nawigacji. Gamma, zoom i przesuwanie
pozostają aktywne, a zmiana FPS od razu przestawia czas następnej klatki.

Planowanie używa pojedynczego timera: jedna następna klatka i synchroniczne
malowanie przed ponownym uruchomieniem timera. Czas przygotowania i malowania
odejmujemy od okresu. Przy przeciążeniu kolejny termin jest liczony od tej
klatki, bez nadrabiania zaległości skokiem i bez pomijania indeksów.

Import w tle pozostawia stare Play dostępne. Błąd lub anulowanie nie zmienia
jego stanu; w międzyczasie film może naturalnie dojść do końca. Sukces pokazuje
pierwszą klatkę w pauzie i resetuje widok według ticketu 05. Wybrane FPS
oraz pętla pozostają preferencjami okna. Czasy pomiaru nie są modyfikowane.

### Sprawdzenia i odbiór

- TDD przez publiczne kontrolki: red → green dla kolejnych klatek, końca/pętli,
  ręcznej nawigacji (także bieżący wybór), zmiany FPS oraz cyklu życia importu.
- **93 testy Viewera zaliczone** w Qt offscreen. W tym wymuszone przeciążenie
  Paint z odczytem kolejnych obrazów, anulowanie na granicy I/O i zamknięcie.
- Mypy strict: **15 plików bez błędów**; cache w `/tmp/stmviewer-playback-mypy`.
- Pełny zestaw repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1832 passed, 63 failed, 12 skipped**, 220.35 s. Porównano wszystkie
  identyfikatory błędów z `/tmp/stmviewer-preview-full-suite.log`: identyczne
  63 wcześniejsze niepowodzenia MolTrack/NanoTrack, bez nowych i bez błędów
  zbierania. Nie jest to zielony odbiór całego repo.
  Log: `/tmp/stmviewer-playback-full-suite.log`.
- Osobny pomiar po zakończeniu testów: `PYTHONPATH=. QT_QPA_PLATFORM=offscreen
  python tests/stmviewer/measure_playback.py
  /home/rlew/projekty/NEtCAT-domains/data/nanotrack_registration/trudne/MOVIE_8.mpp
  --output /tmp/stmviewer-playback-offscreen-512.json`.
  **84 klatki 512 × 512**, 30 s; 148 zmian obrazu, **4,956 kl./s**.
  Odstępy min/mediana/p95/max: **199,63 / 201,61 / 204,34 / 207,36 ms**.
  Każda zmiana odpowiada następnej referencji obrazu; brak pominięć.
  Po 50 prób obu czynności: Pause min/mediana/p95/max
  **5,18 / 5,26 / 5,40 / 5,55 ms**; wybór numerem
  **8,97 / 9,66 / 10,70 / 10,85 ms**. **100% prób poniżej 250 ms**.
  Otwarcie z automatycznym dialogiem: 0,217 s; nie jest częścią pomiaru Play.
  Skrypt odczytuje już pomalowany bufor przez QScreen.grabWindow, bez
  wymuszania malowania przez QWidget.grab. To potok Qt offscreen, bez
  kompozytora/monitora. Zrzut `/tmp/stmviewer-playback-offscreen-512.png`
  oceniono wizualnie; log `/tmp/stmviewer-playback-measurement.log`.
- Automatyczna próba na pulpicie Qt xcb otworzyła rzeczywisty MPP i pokazała
  kontrolki. Pomiar został przerwany po zasłonięciu okna i nie jest zaliczony
  jako liczbowy pomiar płynności monitora. Późniejsze potwierdzenie ręczne
  użytkownika zamyka próbę tego etapu; nie dostarcza nowych liczb ani
  potwierdzenia systemu. Wynik offscreen pozostaje opisany osobno.
- [Przegląd Standards/Spec](implementation/review-06-playback.md): brak naruszeń
  standardów i usterek implementacji. Warunek ręcznej płynności zamknięto
  potwierdzeniem użytkownika. Największy zmieniony plik kodu ma **396 linii**.
  `git diff --check` i lokalne odnośniki dokumentacji poprawne.
- [Instrukcja ręczna i pomiar](playback-manual.md) korzysta z istniejących
  wzorców MPP/STP oraz lokalnego filmu. Użytkownik potwierdził ręczny odbiór
  2026-10-21: „testy manualne ok”. Nie wskazano systemu; odrębne odbiory
  platform, dużej serii i aligned pozostają w późniejszych etapach.
  Aktualizacja odbioru dotyczy tylko dokumentacji; testów nie powtarzano.

Nie zmieniono wspólnych modułów, zależności ani głównej konfiguracji.
Nie ma nowej zmiany integracyjnej wymaganej do działania Play.

## 05: Zoom, gamma i brakujące próbki — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`4b4f6d478b5c734a196821106e984a6ade865536`.
Ticket: [05-preview-controls](implementation/issues/05-preview-controls.md).
Status: `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.
Commit implementacji: `b2903b8`; końcowy raport: `253f806`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Główny podgląd ma gamma 0,1–4 (domyślnie 1), reset gamma, +/− wokół środka,
Dopasuj oraz dotychczasowy zoom pod kursorem i przesuwanie bez zmiany skali.
Gamma używa `u ** (1 / gamma)` po normalizacji skończonych próbek; stała
klatka ma `u = 0,5`. Miniatury pozostają original z gamma 1. Braki są
przezroczyste w rastrze; pod nimi rysowana jest niezależna od gamma szachownica
(8 px na pole, poziomy 96/144). NaN/±Inf nie stają się zerami pomiaru.

Użytkownik zatwierdził opcję Proporcje pikselowe: pomija skalę nagłówka
w podglądzie i miniaturach, zachowując dane źródłowe. Ustawienie jest wspólne
dla serii. Bez niego dodatnia skończona skala X/Y określa proporcje, a jej
brak/nieprawidłowy stosunek daje proporcje pikselowe. Etykieta „Parametry z pliku”
nie potwierdza rzeczywistej kalibracji; nie wykrywamy zastępczych 1000 nm
po nazwie ani wartości. Miniatury dla wymuszonych proporcji są liczone na żądanie.

Zmiana klatki zachowuje gamma/zoom/przesunięcie/proporcje. Nowa poprawna seria
resetuje gamma do 1, opcję proporcji do domyślnej i dopasowuje obraz. Błąd
lub anulowanie zachowują ustawienia. Ustawienia są nieaktywne w pustej aplikacji.
Prawy panel otrzymał przewijanie: dodatkowe kontrolki i postęp nie mogą
powiększać okna, co zmieniałoby kadr po nieudanym imporcie.

### Sprawdzenia

- TDD przez publiczne kontrolki i podgląd: wartości szarości dla znanej gamma,
  neutralne miniatury, maska braków, przyciski zoomu, proporcje, dostępność
  kontrolek oraz reset/zachowanie ustawień. Gesty z wcześniejszych ticketów
  pozostają sprawdzane. Test przekazuje dane tylko do odczytu do publicznego
  podglądu i potwierdza niezmienność macierzy, NaN oraz metadanych.
- **77 testów Viewera zaliczonych** w Qt offscreen. Rozszerzony rzeczywisty
  import MPP potwierdza zachowanie gamma/proporcji/zoomu po anulowaniu.
- Mypy strict: **15 plików bez błędów**. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **314 linii**.
- Automatyczna próba rzeczywistego okna Qt xcb: dialog, gamma/reset, przyciski
  zoomu, puste próbki, proporcje oraz nawigacja lokalnego MOVIE_3.MPP.
  Zrzuty: `/tmp/stmviewer-preview-{gamma,missing,pixels,measurement}-xcb.png`.
  Oceniono wizualnie wygląd podglądu i ustawień. To próba automatyczna.
- Pełny zestaw repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1816 passed, 63 failed, 12 skipped**, 208.14 s. Porównanie identyfikatorów
  wszystkich niepowodzeń z `/tmp/stmviewer-mpp-full-suite.log` potwierdza
  identyczny zestaw 63 wcześniejszych błędów MolTrack/NanoTrack. Brak nowych
  niepowodzeń i błędów zbierania; nie jest to zielony odbiór całego repo.
  Log: `/tmp/stmviewer-preview-full-suite.log`.
- [Niezależny przegląd Standards/Spec](implementation/review-05-preview-controls.md):
  0 naruszeń zasad, 0 istotnych uwag projektowych, 0 usterek specyfikacji.
- Generator odtwarza wzorce bajtowo bez zmian w Git. `git diff --check`
  i lokalne odnośniki zmienionej dokumentacji sprawdzono bez błędów.

### Odbiór i integracja

[Instrukcja ręczna](preview-controls-manual.md) zawiera start, wzorce STP,
generator, kroki i oczekiwane wyniki. Użytkownik potwierdził ręczny odbiór
2026-10-21: „testy manualne ok”. Nie wskazano systemu; potwierdzenie nie zamyka
odrębnych ticketów odbioru platform. Aktualizacja odbioru dotyczy wyłącznie
dokumentacji; testów automatycznych nie powtarzano.
Play i original/aligned są w kolejnych ticketach; gamma i pamięć widoku
muszą zostać z nimi połączone zgodnie z mapą.

Nie zmieniono wspólnych modułów, zależności ani głównej konfiguracji.
Nie ma wymaganej zmiany integracyjnej blokującej tę funkcję.

## 04: Otwarcie filmu MPP z czasami i pochodzeniem — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`8aa12416d6225d63d1378b535e140b2063b65bf6`.
Ticket: [04-mpp-series](implementation/issues/04-mpp-series.md),
status `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.
Commit implementacji: `03f4917`; końcowy raport: `2f18b67`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.

### Wynik i kontrakt

Jeden MPP przechodzi przez istniejący import w tle: klatki, miniatury, postęp,
anulowanie i podmiana całej serii po sukcesie. Nie można łączyć kilku MPP
ani MPP z STP/S94. GUI pokazuje pierwotny numer klatki, czas pomiaru w sekundach
i oryginalny zapis czasu. Nawigacja, zoom i przesuwanie pozostają dostępne.

Lokalny adapter `stmviewer/mpp.py` dekoduje double little-endian, obraca 180°
raz na wejściu (zgodnie z STP i loaderem NanoTrack), zachowuje float64/NaN oraz
nagłówki z sekcjami. Amplituda Z określa jednostkę, bez przeskalowania wartości.
Wspólne dla STP/MPP parsowanie wielkości z jednostkami jest w lokalnym
`stmviewer/quantities.py`. Nieznane dane nie są zastępowane zerami.

`ImageFrame` przechowuje `source_frame_index` (indeks MPP od 0),
`measurement_time_s` oraz `measurement_time_raw`. W GUI numer źródłowy
jest liczony od 1, oddzielnie od pozycji w bieżącej serii. Brak/nieznana
jednostka czasu dotyczy tylko jednej klatki; FPS nie tworzy czasu.
Nagłówek nie ma limitu liczby linii (limit pojedynczej linii: 64 KiB).
Wymiary i długość danych są sprawdzane przed alokacją; przerwanie jest
sprawdzane w trakcie nagłówka, między klatkami i przed publikacją wyniku.

### Sprawdzenia

- TDD przez publiczny import i GUI: realne dekodowanie/wartości/orientacja,
  czasy z jednostkami i częściowymi brakami, długi nagłówek, 1000 klatek,
  postęp/anulowanie, wadliwy typ/długość oraz niedozwolony wybór.
- **68 testów Viewera zaliczonych** w Qt offscreen; mypy strict:
  **15 plików bez błędów**. Testy prawdziwych plików nie zastępują adaptera
  atrapą; kontrolowane opóźnienie oraz brak uprawnień są na granicy systemu plików.
- **12 lokalnych filmów MPP**: wszystkie klatki zgodne element po elemencie
  (także NaN) z `read_mpp_file` po obrocie 180°. Obejmuje prostokątne filmy,
  364 × 256 × 256 oraz 84 × 512 × 512; część plików to kopie tego samego pomiaru.
  Nie traktujemy ich jako 12 niezależnych wzorców. Pomiary pozostają poza Git.
- Automatyczna próba Qt xcb: prawdziwy dialog, częściowe czasy, wybór klatki
  1000 oraz klatek 1/9/17 lokalnego `MOVIE_3.MPP`. Zrzuty w
  `/tmp/stmviewer-mpp-{timed,third,1000,measurement}-xcb.png`.
- Pełne repo w netcat:
  `PYTHONPATH=.:tests/moltrack:tests/stmviewer QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`
  — **1807 passed, 63 failed, 12 skipped**, 207,50 s. Zestaw niepowodzeń
  jest identyczny z poprzednią próbą S94: starsze MolTrack/NanoTrack,
  m.in. brak MOVIE_3.MPP, ścieżki Windows i SAM2. **Brak nowych niepowodzeń
  i błędów zbierania**. To nie jest zielony odbiór całego repo.
  Log: `/tmp/stmviewer-mpp-full-suite.log`. Dodatkowa ścieżka testów udostępnia
  generator binarnych wzorców przy używanym w repo trybie pytest importlib.
- [Przegląd Standards/Spec](implementation/review-04-mpp-series.md): brak
  naruszeń zasad, jedna drobna sugestia formatowania pochodzenia; Spec bez uwag.
  Sugestię pozostawiono jako możliwość późniejszego uproszczenia trzech
  powtórzonych linii, bez usterki zachowania.
- Generator odtwarza wzorce bajtowo bez zmian. Sprawdzono 44 lokalne odnośniki
  dokumentacji przed dodaniem raportu. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **263 linie**. `git diff --check` poprawne.

### Odbiór i integracja

[Instrukcja GUI](mpp-series-manual.md) zawiera uruchomienie, wersjonowane małe
wzorce, generator, lokalne pomiary oraz oczekiwane wyniki. Użytkownik
potwierdził pozytywny wynik testów manualnych 2026-10-21: „testy manualne ok”.
Nie wskazano systemu; potwierdzenie nie zamyka odrębnych ticketów odbioru
platform, w tym Windows. Test 1000 × 1 × 1 sprawdza liczbę klatek i nagłówek;
nie zastępuje testu 1000 × 512 × 512 z ticketu 18. Aktualizacja statusu zmienia
wyłącznie dokumentację; nie ponawiano testów kodu.

Nie zmieniono modułów wspólnych ani konfiguracji głównej/zależności.
Dla przyszłych zmian integracyjnych wspólny czytnik/loader wymaga:
zniesienia limitu 1000 linii, kontroli deklarowanego typu, wydajnego odczytu
float64, poprawnych jednostek i częściowych czasów oraz uzgodnionej orientacji.
Wspólny kontrakt musi być sprawdzony u dotychczasowych odbiorców. Lokalny
adapter pozwala kontynuować Viewer niezależnie; dodatkowe metadane MPP
i eksport należą do kolejnych ticketów.

## 03: S94 i mieszane serie STP/S94 — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i przeglądu:
`b904045e7626e97cd924920d9fbb0e52fbdb3bcc`.
Commit implementacji: `d6fbb7d`; końcowy raport: `18d6ca9`.
Commit potwierdzenia ręcznego odbioru podany w wiadomości sesji.
Ticket: [03-s94-series](implementation/issues/03-s94-series.md),
status `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.

### Wynik i kontrakt danych

Dialog, menu i Ctrl+O otwierają jeden lub wiele STP/S94, także mieszanych.
Importer `open_frame_series` zastępuje nazwę ograniczoną wcześniej do STP.
Kolejność nazw, zgodność wymiarów, postęp, anulowanie, zachowanie stanu przy
błędach i nawigacja korzystają z dotychczasowego przebiegu. Wymiary są porównywane
po transformacji każdego wejścia. Zoom i pojedyncze podświetlenie miniatur pozostają.

Adapter `stmviewer/s94.py` korzysta z układu nagłówka i zakresów wzmocnienia
wspólnego czytnika. Sam odczytuje jawnie little-endian int16 i przechowuje float64;
waliduje nagłówek, dodatnie wymiary, flagę Swapped oraz długość danych przed
alokowaniem macierzy. Dla trybu 0: gain 1/2/3 odpowiada 5,5/22/88 nm na 65536
jednostek surowych; tryb 1: 20 nA na 65536 jednostek. Nieznany gain topografii
lub tryb zachowuje liczby surowe, brak jednostki i opis przyczyny w panelu.
Pole `ImageFrame.calibration_note` przekazuje tę informację do podglądu.

Swapped=1 transponuje macierz i zamienia osie rozmiarów oraz offsetów.
Oryginalny nagłówek, w tym Image_Number, Swapped i wszystkie pozostałe pola,
pozostaje zachowany. Kąt skanowania jest źródłowym ustawieniem pomiaru,
nie kątem wyliczonym dla przekształconego rastra. Brak wiarygodnej dodatniej
skali lub niefinitywny parametr jest reprezentowany przez None. Rzeczywiste zera
pozostają zerami. Bias mV jest przeliczany na V. Pole It nie ma potwierdzonej
jednostki w istniejącym kontrakcie czytnika, więc nie jest zgadywane jako setpoint.

### Sprawdzenia

- TDD red → green: znana kalibracja i para S94/STP, nieznana kalibracja,
  prostokątny obraz Swapped, walidacja, wspólna seria i kontrolki GUI.
  Testy nie zastępują wewnętrznych komponentów atrapami.
- **54 testy Viewera zaliczone** w offscreen. Nowe przypadki obejmują
  signed little-endian, dane fizyczne/surowe, metadane po transpozycji,
  zachowanie stanu po błędnym S94 i anulowanie podczas jego odczytu w mieszanej serii.
- Mypy strict: **13 plików bez błędów**. Największy zmieniony plik kodu:
  `tests/stmviewer/test_series_window.py`, **264 linie**.
- Rzeczywiste lokalne pary 17851, 17544 i 85291r: macierze nowego odczytu
  S94 są identyczne element po elemencie z STP (256 × 256). Pierwsze dwie
  pary mają nm; eksport 85291r.STP podaje nm mimo prądowego trybu S94/nA.
  Wartości nie są nadpisywane na podstawie innego pliku; różnica jest opisana
  w instrukcji ręcznej. Pomiary pozostają lokalne poza Git.
- Automatyczne GUI xcb na Linuksie: prawdziwy dialog obu formatów, nawigacja,
  opis surowych wartości oraz identyczny podgląd pary 17851. Zrzuty oceniono
  wizualnie: `/tmp/stmviewer-s94-mixed-xcb.png`, `/tmp/stmviewer-s94-raw-xcb.png`,
  `/tmp/stmviewer-s94-measurement-xcb.png`.
- Pełny zestaw repo w netcat:
  `PYTHONPATH=.:tests/moltrack QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`
  — **1793 passed, 63 failed, 12 skipped**, 204.61 s. Zestaw 63 niepowodzeń
  jest identyczny z bazą `/tmp/stmviewer-series-full-suite.log` (starsze
  MolTrack/NanoTrack, m.in. brak MOVIE_3.MPP, ścieżki Windows i SAM2).
  Brak nowych niepowodzeń i błędów zbierania. To nie jest zielony odbiór całego repo.
  Log: `/tmp/stmviewer-s94-full-suite.log`.
- [Przegląd Standards/Spec](implementation/review-03-s94-series.md): obie osie
  bez uwag. Generator odtwarza wzorce bajtowo bez zmian; sprawdzono 37 lokalnych
  odnośników dokumentacji przed dopisaniem raportu. `git diff --check` poprawne.

### Odbiór i integracja

[Ręczna próba S94](s94-series-manual.md) zawiera uruchomienie w netcat,
wersjonowane wzorce i generator, lokalne pary pomiarów oraz oczekiwane wyniki.
Użytkownik potwierdził pozytywny wynik testów manualnych 2026-10-21:
„testy manualne ok”. Nie wskazano systemu; potwierdzenie nie zamyka
odrębnych ticketów odbioru platform, w tym Windows.
Aktualizacja statusu zmienia wyłącznie dokumentację; nie ponawiano testów kodu.

Nie zmieniono modułów wspólnych, konfiguracji głównej ani zależności.
Do wykorzystania przez integrację przy przyszłej poprawce wspólnego czytnika:
explicit `<i2` zamiast natywnego int16, jawna jednostka i informacja o danych
surowych, walidacja parametrów oraz spójna zamiana offsetów wraz z osiami.
Taka wspólna zmiana wymaga testów odbiorców; nie blokuje działającego adaptera
Viewera. Testy z `tests/stmviewer/test_s94_import.py` opisują jego obecny kontrakt.

## Poprawka ticketu 02: podświetlenie miniatur — 2026-10-21

Baza: `89614aa`, gałąź `viewer/start`. Commit poprawki: `cb40891`. Użytkownik zgłosił pozostawanie podświetlenia poprzednich
miniatur przy użyciu Następna/Poprzednia. Odtworzono to dwukrotnie na xcb:
model zaznaczał tylko aktualną klatkę, ale poprzednie podświetlenie znikało
z ekranu dopiero po wymuszonym przemalowaniu.

Przyczyną był `QSignalBlocker` na modelu zaznaczenia: blokował również
powiadomienia potrzebne widokowi Qt do odświeżenia poprzedniej miniatury.
Usunięto blokadę tych sygnałów. Obsługa wyboru ignoruje już aktywny indeks,
co zapobiega ponownemu wykonywaniu tej samej zmiany podczas synchronizacji.

Test regresji poprzez publiczne przyciski sprawdza pojedyncze zaznaczenie
oraz zdarzenia malowania starej i nowej miniatury (dwa kroki w przód i dwa
wstecz). Przed poprawką nie otrzymywał przemalowania starej miniatury;
po poprawce przechodzi w offscreen i xcb. Niezależna automatyczna próba xcb
porównuje obraz z ekranu przed i po wymuszonym odświeżeniu — po poprawce
obrazy są identyczne. Lokalny skrypt diagnostyczny i zrzuty:
`/tmp/stmviewer-selection-debug/`.

Sprawdzenia: **34 testy Viewera zaliczone**, test regresji na xcb zaliczony,
mypy strict bez błędów, `git diff --check` poprawne. Największy zmieniony plik
kodu ma 263 linie. Nie powtarzano pełnego zestawu repo dla tej lokalnej
poprawki GUI; poprzedni wynik i 63 istniejące błędy są opisane niżej.
Nie zmieniono wspólnych modułów ani zależności. Powyższe próby są automatyczne.
Użytkownik następnie potwierdził ręczny odbiór po poprawce 2026-10-21:
„testy manualne ok”. Ticket 02 ma status `done`. Nie wskazano systemu;
potwierdzenie nie zamyka odrębnych ticketów odbioru platform.

## 02: Otwarcie i przeglądanie serii STP — 2026-10-21

Gałąź: `viewer/start`. Baza implementacji i code-review:
`3f2e92b59d29dc0ecf74751807e26f530167af7d`.
Commit implementacji: `e054738`. Finalny zakres tego etapu: `3f2e92b..HEAD`;
commit raportu podany w końcowej wiadomości sesji.
Ticket: [02-stp-series](implementation/issues/02-stp-series.md),
status `done` po potwierdzeniu ręcznego odbioru użytkownika 2026-10-21.

### Wynik

Otwieranie jednego lub wielu STP sortuje nazwy naturalnie i wymaga jedynie
zgodnych wymiarów pikselowych. Odczyt wykorzystuje sprawdzony adapter;
każda klatka zachowuje własne wartości, orientację, skalę, kanał i pozostałe
metadane. Miniatury oryginałów są na dole, ustawienia po prawej.
Przyciski, suwak, edytowalny numer, zaznaczenie miniatury, główny obraz i panel
źródła wskazują tę samą klatkę. Pasek przewija się do wybranej miniatury.

Odczyt i przygotowanie miniatur wykonuje zadanie w tle. Postęp obejmuje obie
fazy. Błąd lub anulowanie nie zastępują poprzedniego zestawu i wyboru.
Podczas importu działają podgląd i nawigacja starej serii; nowy import jest
zablokowany. Anulowanie czeka na ukończenie bieżącego odczytu pojedynczego
pliku; okno nadal obsługuje zdarzenia. Zamknięcie podczas importu anuluje
zadanie i zamyka okno po zakończeniu wątku.

Zmiana klatki zachowuje zoom i przesunięcie. Sukces nowego importu pokazuje
pierwszą klatkę dopasowaną do okna. Pusta i pojedyncza seria mają odpowiednio
nieaktywne kontrolki. To realizuje również część przyszłego ticketu 05;
gamma i szachownica pozostają do wykonania.

### Sprawdzenia

- TDD: red → green dla naturalnego sortowania/odczytu, kontroli wymiarów,
  anulowania, nawigacji GUI oraz responsywności przy opóźnionym I/O.
  Testy korzystają z uzgodnionych publicznych granic. Zastępowane są jedynie
  dialog systemowy i czas odczytu pliku, bez atrap wewnętrznych komponentów.
- **33 testy Viewera zaliczone** w Qt offscreen. Obejmują regresje pojedynczego
  STP i gestów, dane liczbowe/metadane, odmienne znane kanały i skale,
  orientację miniatur, synchronizację, anulowanie, błędy oraz zamykanie w trakcie pracy.
- Mypy strict: **12 plików bez błędów**. Największy zmieniony plik kodu:
  `stmviewer/ui/main_window.py`, **252 linie**; wszystkie poniżej 1500.
- Pełne repo w `netcat`:
  `PYTHONPATH=.:tests/moltrack QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1772 passed, 63 failed, 12 skipped**, 205.54 s. Zestaw 63 niepowodzeń
  jest identyczny z poprzednią próbą (`/tmp/stmviewer-navigation-full-suite.log`):
  starsze testy MolTrack/NanoTrack, m.in. brak MOVIE_3.MPP, ścieżki Windows,
  SAM2. **Brak nowych niepowodzeń i błędów zbierania**. To nie jest zielony odbiór
  całego repo. Log: `/tmp/stmviewer-series-full-suite.log`.
- Automatyczna próba rzeczywistego okna Qt xcb na Linuksie: dialog wielu STP,
  kolejność 1–2–10, przyciski i miniatury, następnie rzeczywisty pomiar 34855.STP.
  Zrzuty oceniono wizualnie: `/tmp/stmviewer-series-xcb.png`,
  `/tmp/stmviewer-series-current-xcb.png`, `/tmp/stmviewer-series-measurement-xcb.png`.
- Generator większych danych sprawdzono na trzech STP 64 × 64 z ponownym
  odczytem. Duża próba wydajności z ticketu 18 nie została tu wykonana.

- [Przegląd Standards/Spec](implementation/review-02-stp-series.md): obie
  niezależne osie bez ustaleń wymagających poprawki. Generatory odtworzyły
  wzorce bajtowo bez zmian; 38 odnośników dokumentacji było poprawnych,
  `git diff --check` bez błędów.

### Odbiór i integracja

[Instrukcja GUI i wzorce](stp-series-manual.md) obejmują ręczny scenariusz,
łącznie z generowaniem większego zestawu do anulowania. Użytkownik potwierdził
ręczny odbiór serii po poprawce miniatur 2026-10-21. To nowe potwierdzenie
ticketu 02, niezależne od wcześniejszego odbioru ticketu 01. Systemu nie podano;
odbiór Windows pozostaje odrębnym etapem.

Zmiany dotyczą wyłącznie aplikacji Viewera, jej testów i dokumentacji.
Nie zmieniono konfiguracji głównej, zależności ani współdzielonych loaderów;
nie potrzeba nowej poprawki integracyjnej. Uruchomienie pozostaje
`python -m stmviewer.main` w `netcat`. Nie publikowano ani nie scalano gałęzi.

## Uzupełnienie: zoom i przesuwanie — 2026-10-21

Baza dodatku: `7a43715`, gałąź `viewer/start`. Commit kodu: `75f419d`.
Commit raportu testów i przeglądu: `df4bbc5`.
Użytkownik potwierdził ręczną próbę otwierania STP i zlecił wcześniejsze dodanie
nawigacji obrazu. To część zakresu [05](implementation/issues/05-preview-controls.md),
bez zamykania jego przyszłych wymagań dotyczących serii i gamma.

Kółko zmienia zoom pod kursorem (czynnik 1.2 na krok, zakres 0.1–64 względem
dopasowania), lewy przycisk przesuwa obraz w obu osiach bez zmiany zoomu.
Przycisk „Dopasuj” przywraca cały obraz. Poprawny import dopasowuje nową klatkę,
anulowanie i błąd zachowują nawigację. Pusty program ma nieaktywne Dopasuj.
Zależności i wspólny kod pozostają bez zmian. Przy wprowadzaniu przeglądania
serii trzeba zachować zoom na zmianie klatki: obecne `set_frame` oznacza nowy import.

Sprawdzenia dodatku: pięć testów publicznych gestów GUI przechodzi w offscreen
(zoom pod kursorem, ruch podczas przeciągania i stała wielkość znacznika,
Dopasuj, zachowanie/reset przy imporcie, pusty program). Mypy strict: 8 plików,
bez błędów. Automatyczna próba xcb otworzyła rzeczywisty 34855.STP przez dialog,
sprawdziła kółko, przeciąganie i powrót przez Dopasuj. Użytkownik potwierdził
ręczny odbiór nawigacji 2026-10-21: „testy manualne ok”.
[Scenariusz](single-stp-manual.md#zoom-i-przesuwanie). Nie wskazał platformy;
potwierdzenie nie zamyka osobnych odbiorów Ubuntu i Windows.
[Przegląd dodatku](implementation/review-preview-navigation.md): Standards — 0 ustaleń,
Spec — 0 ustaleń. Największy zmieniony plik kodu ma 132 linie, `git diff --check`
bez błędów. Zrzut automatycznej próby: `/tmp/stmviewer-navigation-xcb.png`.
Pełny zestaw repo w `netcat`:
`PYTHONPATH=.:tests/moltrack QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`
— **1758 passed, 63 failed, 12 skipped** w 203.27 s. Wszystkie 19 testów
Viewera przeszły. Zestaw 63 niezaliczonych testów jest identyczny z wcześniejszą
bazą `ba4e0d3`; nie ma nowych błędów ani błędów zbierania testów.
Log: `/tmp/stmviewer-navigation-full-suite.log`.

## 01: Pierwszy obraz STP — poprzedni etap

Data: 2026-10-21. Gałąź: `viewer/start`. Baza zmiany i code-review: `ba4e0d3`.
Commit implementacji: `960101c`; finalny zakres `ba4e0d3..HEAD`.
Commit raportu odbioru podany w końcowej wiadomości sesji.
Ticket: [01-single-stp](implementation/issues/01-single-stp.md).

## Wynik

Działa otwieranie pojedynczego STP z przycisku, menu i Ctrl+O. Obraz jest
w całości dopasowany, z proporcjami fizycznymi przy znanej skali obu osi,
a przy braku skali — pikselowymi. Panel pokazuje źródło, rozmiar, kanał,
jednostkę sygnału, pole i offsety X/Y, napięcie, prąd oraz kąt.
Brak metadanych pozostaje brakiem, rzeczywiste zera są zachowane.
Anulowanie i błąd odczytu nie wymieniają poprzedniego obrazu.

`stmviewer.io.open_stp` wykorzystuje dekodowanie double i obrót 180°
w `napara.io.stp_reader`. Adapter zachowuje źródłowy kanał, metadane
z nagłówka i jednostkę z Z Amplitude bez skalowania próbek. Odczytuje UTF-8
oraz starsze nagłówki Latin-1 bez usuwania µ. Odrzuca jawny typ inny niż
`double`, błędne wymiary, niepełny payload i brak końca nagłówka.
Nagłówek adaptera ograniczono do 1 MiB, 64 KiB na linię i limitu liczby
linii wspólnego czytnika. Wartości pozostają float64; podgląd to osobny raster.

Nie zmieniono wspólnych aplikacji ani głównej konfiguracji. Małe wzorce,
ich generator i [ręczny scenariusz](single-stp-manual.md) są w Git.
Uruchomienie z `netcat`: `python -m stmviewer.main` z katalogu repo.
Instrukcje środowisk Ubuntu/Windows: [README](README.md#uruchomienie).

## Sprawdzenia

- TDD: zaobserwowane red → green dla dekodowania, publicznego otwarcia
  w GUI, błędów importu z nazwą źródła oraz zachowania jednostki µ w Latin-1.
- Testy Viewera: 12 testów importu i 2 testy GUI offscreen — zaliczone.
  Publiczne kontrolki sprawdzają również zastąpienie, anulowanie i błędny plik.
- `python -m mypy --config-file stmviewer/mypy.ini`: 8 plików aplikacji,
  strict, bez błędów. Stary kod `napara` nie jest objęty tym sprawdzeniem typów.
- Trzy rzeczywiste STP (34855, 17851, 17544) wczytane poprawnie: 256 × 256,
  kanał Topo, jednostka nm, zachowane zakresy wartości i skala X/Y.
- Automatyczna próba z prawdziwym oknem Qt xcb na Linuksie: wybór wzorca
  i rzeczywistego 34855.STP w dialogu, zmiana rozmiaru okna do 640 × 480.
  Zapisane obrazy ocenione wizualnie: prawidłowe L i pełne pole pomiaru.
  To próba sterowana skryptem, nie ręczny odbiór użytkownika.
- Pełny zestaw repo uruchomiony raz w `netcat` z
  `QT_QPA_PLATFORM=offscreen python -m pytest -q --import-mode=importlib --continue-on-collection-errors`:
  **1479 passed, 64 failed, 12 skipped, 36 errors**. Błędy dotyczą
  MolTrack/NanoTrack (brak `data/MOVIE_3.MPP`, ścieżki Windows, SAM2)
  oraz importów helperów testowych MolTrack przy `importlib`.
  Czyste archiwum `ba4e0d3` uruchomione tą samą komendą:
  **1466 passed, 63 failed, 12 skipped, 36 errors**. Wszystkie 99
  niepowodzeń bazy występuje też w bieżącym kodzie. Jedyna różnica to timeout
  10 s workera SAM2; powtórzony samodzielnie w bieżącym kodzie przeszedł
  w 0.70 s. Nie stwierdzono regresji Viewera; nie jest to zielony odbiór repo.
  Błędy zbierania wynikają z braku `tests/moltrack` w ścieżce importów
  pomocników testowych przy wybranym trybie `importlib`.
  Ponowiono tylko te 36 modułów z `PYTHONPATH=.:tests/moltrack`:
  **273 passed in 151.70 s**, bez błędów zbierania. Nie zmieniano ich kodu.
- Limit plików: największy nowy/zmieniony plik Python ma 109 linii.
  `git diff --check` bez błędów.
- [Przegląd Standards/Spec](implementation/review-01-single-stp.md):
  Standards — 0 ustaleń; Spec — 0 usterek kodu. W chwili przeglądu pozostały
  2 warunki odbioru; ich zamknięcie opisano poniżej.
  Obie osie wykonane przez niezależnych recenzentów od uzgodnionej bazy.

Lokalne logi: `/tmp/stmviewer-full-suite.log`, `/tmp/stmviewer-baseline-suite.log`
i `/tmp/stmviewer-collection-recheck.log`. Generator odtworzył wzorce bajtowo
bez zmiany w Git; 36 lokalnych odnośników zmienionej dokumentacji jest poprawnych.
Zrzuty próby xcb: `/tmp/stmviewer-asymmetric-xcb.png`,
`/tmp/stmviewer-measurement-xcb.png`, `/tmp/stmviewer-measurement-small-xcb.png`.
Artefakty lokalne nie są częścią repozytorium.

## Odbiór i integracja

Ticket 01 ma status `done`: funkcja działa, testy i instrukcje są dostarczone,
a użytkownik zatwierdził odbiór. Następny odblokowany etap to ticket 02.
Użytkownik potwierdził ręczny scenariusz otwierania STP 2026-10-21:
„testy manualne ok”. Nie podał systemu, więc nie oznacza to odbioru Windows.
Usunięto dodatkową blokadę osobnego potwierdzenia lokalnej konfiguracji:
nie zmieniono konfiguracji głównej ani wspólnych modułów. Doprecyzowanie
zapisano w kryterium ticketu i zasadach implementacji.

Do wykorzystania przy integracji: minimalne wymagania aplikacji
`stmviewer/requirements.txt` (wspólny PyQt6 + NumPy 2.2.5),
`stmviewer/requirements-dev.txt` oraz komenda
`python -m mypy --config-file stmviewer/mypy.ini`. Konfiguracja działa lokalnie
bez zmiany root i została przekazana w dokumentacji. Odrębnego zatwierdzenia
przez sesję integracyjną nie przeprowadzono; nie jest ono warunkiem zamknięcia
tego lokalnego etapu. Scalenie gałęzi pozostaje osobną czynnością.
Wspólny czytnik wymaga w przyszłości obsługi Acquisition channel,
X-Offset/Y-Offset, nieznanych wartości, osobnej jednostki sygnału i kodowania
nagłówka bez utraty µ. Adapter zapewnia ten kontrakt już w Viewerze.
Zmiany wspólnego czytnika powinny objąć testy jego istniejących odbiorców.

Pozostałe potrzeby integracyjne i zakres całej aplikacji zachowano
we [wcześniejszym przekazaniu planu](planning-handoff.md).
