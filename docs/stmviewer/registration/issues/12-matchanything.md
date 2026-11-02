# REG-12: MatchAnything-ELoFTR — kontrola wpływu treningu

**What to build:** Użytkownik porównuje wariant MatchAnything oparty na
EfficientLoFTR ze zwykłym EfficientLoFTR przy tej samej agregacji i grafie.
**Blocked by:** [REG-11](11-roma-v2.md), w tym odbiór manualny.
**Status:** ready-for-review
**Manualny odbiór:** niewykonany; implementacja gotowa 2026-11-02.
**Wykonawca:** Codex. Baza przeglądu: `1c30ef5`; implementacja `b4d9441`.
[Wyniki](../matchanything-results.md), [próba ręczna](../matchanything-manual.md),
[testy i dwa przeglądy](../reviews/REG-12.md).
**Dodano do planu:** 2026-10-31, na zlecenie użytkownika po research.
**Przygotowanie zasobów — 2026-11-02:** kod i oficjalny checkpoint pobrane,
próby CPU/CUDA w istniejącym `netcat` zaliczone bez instalacji bibliotek.
[Lokalizacje, wersje, sumy i ograniczenia](../matchanything-environment.md).
Pierwsze zlecenie obejmowało pobranie i weryfikację. Kolejne zlecenie
`implement 12` objęło pełną implementację poniższych kryteriów;
otwarty pozostaje ręczny odbiór jakości i platform.

Obowiązują [plan](../README.md), [protokół odbioru](../manual-protocol.md)
i [przegląd modeli](../../registration-multiframe-research.md).
Blokada ustala kolejność odbiorów. Ten wariant używa rodziny ELoFTR z REG-10;
nie wywołuje RoMa v2 ani nie potrzebuje jej wag.

## Zakres i kryteria odbioru

- [x] Dodajemy jeden jawnie nazwany wariant **MatchAnything-ELoFTR**.
  Działa dla pary, całej serii sąsiednich klatek oraz odebranego grafu,
  przez ten sam estymator pary. Wariant MatchAnything-RoMa jest poza zakresem.
- [x] Główna próba porównuje zwykły EfficientLoFTR z REG-10 z tym wariantem.
  Agregacja korespondencji z REG-10, renderowanie, lista kandydatów par,
  okno i solver grafu pozostają takie same. Nie dołączamy wyszukiwania wycinków
  z REG-05. Wagi/model nie są zmieniane między parami.
  Deep i RoMa v2 pozostają dodatkowymi punktami odniesienia, nie etapami metody.
- [x] Przypinamy zgodny checkpoint i konfigurację architektury/inference
  autorów. Nie zakładamy, że nowe wagi można dowolnie podmienić w starym
  adapterze. Różnice wymaganej normalizacji, rozdzielczości i kwalifikacji
  punktów są zapisane; raport nie nazywa takiej próby idealną izolacją samego
  treningu, jeśli jednocześnie musiała zmienić się konfiguracja inference.
- [x] Korespondencje są odwzorowane do pikseli oryginałów z uwzględnieniem
  skalowania obu osi, paddingu i kanałów. Potem stosujemy jeden konsensus
  translacji i jedno XY na klatkę. Braki/padding nie są strukturami,
  a gamma podglądu nie wpływa na wyznaczane przesunięcia.
- [x] Diagnostyka pokazuje przestrzenne poparcie, niejednoznaczność i odmowy.
  Nowy score nie jest bez przeliczenia wspólną wagą z EfficientLoFTR ani
  prawdopodobieństwem poprawnego STM. Zasady kwalifikacji są wersjonowane.
- [x] Zależności i pełny zestaw wag są opcjonalne oraz lokalne. Instrukcja
  przypina źródło, wersje kodu i bibliotek, wariant, SHA-256 i warunki użycia
  kodu/wag. Ścieżka Hugging Face nie oznacza zgody na sieciowe pobieranie
  przez aplikację; także ukryte zależności muszą być dostępne lokalnie.
- [x] Niedostępność, niezgodny checkpoint, brak wskazanego urządzenia i OOM
  mają konkretne komunikaty. Nie zmieniamy po cichu metody, modelu, CPU/CUDA
  ani wielkości wejścia. Model jest używany ponownie w kolejnych parach,
  a błąd/anulowanie zwalnia zasoby i zachowuje wcześniejszy aktywny wynik.
- [x] Konflikty opcjonalnych zależności rozwiązujemy w adapterze/środowisku
  Viewera, z opisanym uruchomieniem z GUI. Zmiany potrzebne we wspólnych
  modułach lub konfiguracji głównej są jawnym zadaniem integracji w handoff.
- [x] Ten ticket rozszerza sesję o rzeczywistą konfigurację, pochodzenie wag,
  urządzenie, wyniki i diagnozy. Odczyt sesji działa bez modelu i odtwarza aktywny
  film, bez stosowania niezastosowanego kandydata. Zastosowanie do filmu, ręczne korekty oraz MPP/AVI zachowują REG-08c:
  render z oryginałów raz, z poprawną geometrią i bez nakładek diagnostycznych.
- [x] Raport oddziela poparcie modelu od oceny obrazowej. REG-06 jest
  odłożony; nie wymagamy jego implementacji ani oznaczania fragmentów,
  a brak kontroli pozostaje brakiem oceny. Po ewentualnym wznowieniu REG-06
  jego ocena jest zależna, jeśli model lub przygotowanie wejścia używały
  danych kontrolnych. Sukces treningu między modalnościami nie daje
  automatycznie niezależnej walidacji ani odporności na tearing STM.
- [ ] Raport obejmuje rzeczywiste wagi, oba filmy, odmowy, jakość obrazową,
  czas modelu/solvera/renderowania, RAM i VRAM oraz faktyczne CPU/CUDA.
  Budżet 8 GB sprawdzamy oddzielnie; większa karta nie zalicza tego kryterium.
  Brak danych lub sprzętu jest opisanym ograniczeniem, nie pomyślnym testem.

Poza zakresem: drugi wariant MatchAnything-RoMa, trening, fuzja modeli,
automatyczne ECC, korekcja lokalna obrazu i automatyczny wybór nowej metody
domyślnej. Nie wymagamy poprawy jakości, jeśli pomiary jej nie potwierdzają;
odrzucenie eksperymentu wymaga zapisanej decyzji użytkownika.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Konfiguracja i korespondencje → XY:** identyfikacja właściwego wariantu,
  zgodność checkpointu, odwrócenie przekształceń wejścia i znany ruch w obu
  osiach. Kontrola identycznego konsensusu i parametrów grafu w porównaniu.
- **Dostępność/zadanie → wynik albo odmowa:** brak wag, próba pobierania
  przez bibliotekę, błąd/OOM/anulowanie; zachowanie poprzedniego aligned
  i brak fallbacku. Testy z atrapą nie dowodzą jakości rzeczywistych wag.
- **Para/seria/graf/sesja → zastosowanie i eksport:** spójne pochodzenie
  i XY, zapis/odczyt bez uruchamiania modelu, zgodna ręczna korekta i geometria
  MPP/AVI. Nie powielamy całych testów solvera i renderera.
- Realne wagi muszą przejść próbę na znanym wzorcu i obu filmach; wynik
  rzeczywistego CPU/CUDA jest raportowany oddzielnie od testów kontraktu.

## Próba manualna

1. Uruchom `python -m stmviewer.main` według instrukcji środowiska. Sprawdź
   niedostępność bez wag, a następnie lokalną konfigurację. W UI nazwa ma
   odróżniać MatchAnything-ELoFTR od zwykłego EfficientLoFTR.
2. Porównaj te dwa warianty na `cpu.mpp` i wzorcu z nieruchomymi pasami.
   Sprawdź XY oraz przestrzenne poparcie przy jednakowym widoku i konsensusie.
3. Po usunięciu źródłowych 1 i 2 z MOVIE_4 obejrzyj stałe pary i bieżące
   29→30, 35→36, 44→45→46, 61→62, 94→95→96→97. Powtórz próbę na MOVIE_8
   oraz nowych przypadkach z protokołu, których nie używano do strojenia.
4. Uruchom oba pełne filmy najpierw sąsiednio, potem z jednym ustalonym
   grafem. Zmieniaj tylko wariant modelu, a konieczne różnice inference
   zapisz. Oceń pierwsze 150 klatek MOVIE_4 i dalszy film; zachowaj także
   odmowy i miejsca niejednoznaczne, bez uzupełniania XY zerami.
5. Anuluj obliczenie przy istniejącym aligned: dotychczasowy wynik zostaje.
   Zapisz/otwórz sesję, również bez wag. Podgląd wyników ma działać; nowa estymacja
   ma podać niedostępność. Sesja odtwarza zapisany aktywny film,
   bez stosowania niezastosowanego kandydata.
6. Zastosuj wynik, wykonaj i cofnij ręczną korektę pary, zapisz małe
   MPP+metadane i AVI. Sprawdź MPP w Viewerze, AVI w VLC, pochodzenie metody,
   położenia i tło. Zapisz pomiary zasobów i osobno status próby 8 GB VRAM.

**Oczekiwany wynik:** odtwarzalne porównanie wpływu wariantu wytrenowanego
między modalnościami oraz decyzja, czy wnosi poprawę na naszych filmach STM.

## Stan po wdrożeniu

Finalny preset biblioteki autorów ma próg 0,001, NPE 832 i obraz roboczy
640×480 w kwadracie 640², z odwrotnym mapowaniem do oryginału. Porównanie
uwzględnia tę różnicę inference względem EfficientLoFTR. Oba pełne filmy
mają łańcuch i LS; Huber MOVIE_4 osiągnął limit 200, MOVIE_8 jest zbieżny.
Wszystkie przejścia łańcucha są niepewne. Wzorzec cpu.mpp ujawnia około
1 px błędu Y, mimo poprawnego wykonania programu. Ostateczna jakość,
odtwarzanie w VLC i odbiory platform/sprzętu pozostają do sprawdzenia.
