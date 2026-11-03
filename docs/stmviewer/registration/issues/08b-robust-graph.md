# REG-08b: Odporny graf na tych samych dopasowaniach

**What to build:** Użytkownik porównuje zwykłe LS z odpornym rozwiązaniem
Hubera na identycznym zbiorze relacji i ogląda, które pomiary mają mniejszy wpływ.
**Blocked by:** [REG-08a](08a-window-graph.md), w tym odbiór manualny — spełnione 2026-11-01.
**Status:** done
**Manualny odbiór:** zaliczony 2026-11-01; użytkownik potwierdził „testy manualne ok”.
**Start implementacji:** 2026-11-01, Codex; baza przeglądu `3f6fd5a32105b79a1143551fa1541c5c97ab5d66`.
**Dodano do planu:** 2026-10-31, na zlecenie użytkownika po research.

Obowiązują [plan](../README.md#kontrakty-rozszerzenia-wieloklatkowego),
[protokół](../manual-protocol.md) i [model obliczeniowy z research](../../registration-multiframe-research.md#proponowany-model-obliczeniowy).

## Zakres i kryteria odbioru

- [x] Z bieżących danych grafu REG-08a, także odtworzonych z sesji, można
  utworzyć odporny wariant.
  Korzysta z dokładnie tych samych d_ij, odmów, źródeł i kotwicy. Nie uruchamia
  ponownie Deep ani nie zmienia okna, przygotowania obrazów czy warunków oceny.
- [x] Pierwszy odporny wariant to blokowy Huber/IRLS: funkcja kosztu zależy
  od długości reszty 2D `r_ij=(p_j-p_i)-d_ij`; jedna waga obejmuje obie osie
  danej pary. Wszystkie ważne pomiary mają początkowo równą wagę jak w REG-08a.
  Nie mylimy tego z oddzielnym Huberem na spłaszczonych składowych X i Y.
- [x] Próg Hubera w pikselach, warunki zakończenia, limit iteracji i wersja
  solvera są jawne i zapisane. Propozycję wartości domyślnych dobieramy na
  wzorcach rozwojowych, oddzielnie od nowych przypadków końcowego odbioru.
  REG-06 jest odłożony; po ewentualnym wznowieniu jego niezależne fragmenty
  nie mogą służyć strojeniu tej samej próby.
  UI udostępnia próg; zmiana tworzy nową próbę, nie nadpisuje wyniku zachowanego.
- [x] Rozwiązanie nie ma kary za zmianę kierunku/szybkości, gładkość ani
  odległość od zera. Start LS i kolejne ważone rozwiązania mają tę samą kotwicę.
  Raport wskazuje rzeczywiste zakończenie i warunki numeryczne. Nieskończone
  wartości, nieskuteczny solver lub nieosiągnięte przyjęte warunki zakończenia
  nie tworzą kompletnego wyniku gotowego do zastosowania.
- [x] UI pokazuje LS i Huber we wspólnym układzie, różnice globalnych XY,
  reszty par oraz ich końcowe wagi. Mała waga oznacza konflikt w tym rozwiązaniu,
  a nie pewność, że dana para jest fizycznie błędna. Nie usuwamy relacji po cichu.
- [x] Most, brak nadmiarowych relacji i rozłączenie zachowują diagnozy REG-08a.
  Huber nie naprawia identyfikowalności grafu ani zgodnych błędów okresowych.
  Jeśli osłabione relacje powodują numeryczny problem wyznaczenia pozycji,
  zgłaszamy go zamiast pozornie bardzo precyzyjnych XY.
- [x] Ten ticket rozszerza sesję o identyfikator wspólnego zestawu
  pomiarów, LS, wariant odporny, konfigurację, wagi i zakończenie solvera.
  Odczyt jest możliwy bez modelu i bez ponownego rozwiązania. Starsze sesje
  zachowują zgodność, nieznane wersje mają czytelną odmowę.
- [x] Podgląd całej próby, Play i porównanie korzystają z REG-08a.
  REG-07 zapewnia jedynie zapis sesji, bez biblioteki pełnych prób.
  Obliczenia są anulowalne; nie zmieniają aktywnego aligned, korekt ani eksportu.
  Nie materializujemy kolejnego pełnego filmu dla LS i Hubera.

Poza zakresem: dodatkowe matchery, soft_l1 jako następny obowiązkowy wariant,
automatyczny wybór progu/metody, twarde ręczne ograniczenia i stosowanie do filmu.
REG-08c będzie osobno odpowiadał za publikację wyniku i eksport.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Te same relacje → LS i Huber:** znana sieć z nawrotami i jedną błędną
  nadmiarową krawędzią, poprawne znaki/kotwica i zgodność z kontrolnym kosztem.
  Osobno przypadek różniący blokowy Huber od komponentowego. Sprawdzamy
  odzyskiwanie znanych pozycji w przygotowanym przypadku, nie ogólną wyższość.
- **Niejednoznaczna sieć → ograniczenia/odmowa:** most, drzewo, rozłączenie,
  spójny fałszywy alias i dominujące złe relacje; brak gwarancji prawdy z reszt.
  Niepoprawny próg, błąd numeryczny i przerwanie nie zmieniają poprzedniej próby.
- **GUI i zapis → powtarzalne porównanie:** niezmienne pomiary bez modelu,
  jawny nowy wariant po zmianie progu, wagi/XY po odczycie, wspólny widok,
  anulowanie oraz zachowanie aktywnego filmu.

## Próba manualna

1. Otwórz dostarczoną sesję testową znanej sieci z pojedynczym błędnym pomiarem.
   Porównaj LS i Huber, obejrzyj kontury w filmie oraz reszty i wagi. Źródłowe
   relacje pozostają identyczne. Realizujący podaje oczekiwane pozycje wzorca.
2. Obejrzyj wzorzec okresowy i graf z mostem. UI nie może deklarować prawdziwego
   ruchu tylko dlatego, że reszta wynosi zero; Huber może niczego nie poprawić.
3. Dla sesji MOVIE_4 i MOVIE_8 zapisanych w REG-08a porównaj LS i Huber na tym samym
   oknie. Obejrzyj problemy z protokołu i pełne filmy; zapisz poprawę, pogorszenie
   oraz niejednoznaczność oddzielnie od spadku kosztu matematycznego.
4. Utwórz drugi wariant progu i porównaj go z LS w podglądzie grafu przy tym
   samym zoomie. Zapisz/otwórz sesję z tym stanem grafu; wyniki i wagi zostają.
   Wyłącz dostępność wag: analiza zapisanych relacji nadal działa.
   Otwarcie sesji odtwarza zapisany aktywny aligned, bez stosowania kandydata.
5. Anuluj nowe obliczenie. Sprawdź wcześniejsze próby i aktywny film oraz jego
   eksport. Sam oglądany wynik Hubera nadal nie podmienia MPP/AVI.

**Oczekiwany wynik:** mierzalna i wizualna ocena odpornego łączenia relacji,
oddzielona od jakości modelu pary. Wynik może pozostać eksperymentalny lub
zostać odrzucony po ręcznej ocenie; LS pozostaje dostępną bazą.

## Realizacja — 2026-11-01

Kod: `2802837` + `417c107`; dokumentacja implementacji: `7c6da56`.
Gałąź: `viewer/registration-difficult-movies`.
[Instrukcja i dane do ręcznej próby](../robust-graph-manual.md),
[wyniki obliczeń i ograniczenia](../robust-graph-results.md),
[karta testów i przeglądu](../reviews/REG-08b.md).

Próg domyślny 2 px i limit 200 ustalono na osobnych sieciach rozwojowych.
UI udostępnia także jawny limit iteracji 1–10000; każda próba zachowuje swój
próg, limit, tolerancje, wynik albo diagnostykę odmowy. Zmiana ustawień nie
nadpisuje wcześniejszych wariantów. Sesja przechowuje je razem ze wspólnymi
pomiarami, bez dodatkowych stosów pikseli i bez ponownego solvera przy odczycie.

Na nowym wzorcu odstający pomiar daje maksymalny błąd współrzędnej 5,022 px
w LS i 0,712 px w Huberze. Most i spójny alias pozostają nierozpoznawalne;
przy błędnej większości Huber może pogorszyć wynik. MOVIE_4/3 nie spełnia
warunków zbieżności nawet po 5000 iteracjach i ma wyłącznie diagnostykę.
MOVIE_4/5 oraz MOVIE_8 mają kompletne warianty. Potwierdzenie odbioru nie
zawiera szczegółowej oceny poprawy wizualnej tych filmów. Nie zmieniono
tolerancji na podstawie prób odbiorczych.

Zastosowanie wariantu do aligned i eksportu nadal należy do REG-08c.
REG-08b zamknięto jako `done` po potwierdzeniu „testy manualne ok” 2026-11-01.
Nie podano systemu, sprzętu ani szczegółowej oceny jakości poszczególnych filmów;
odbiorem nie potwierdzamy Windows 11 ani przewagi Hubera nad LS. REG-08c ma
spełnioną zależność i czeka na osobne zlecenie. Kod i wyniki obliczeń bez zmian.
