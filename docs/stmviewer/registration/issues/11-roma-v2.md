# REG-11: RoMa v2 — gęste dopasowania do jednej translacji

**What to build:** Użytkownik porównuje RoMa v2 z odebranymi modelami i widzi,
czy gęste korespondencje poprawiają globalne XY na trudnych obrazach STM.
**Blocked by:** [REG-10](10-efficient-loftr.md), w tym odbiór manualny.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.
**Dodano do planu:** 2026-10-31, na zlecenie użytkownika po research.

Obowiązują [plan](../README.md), [protokół odbioru](../manual-protocol.md)
i [przegląd modeli](../../registration-multiframe-research.md).
Blokada ustala kolejność odbiorów. RoMa v2 nie wywołuje EfficientLoFTR
i nie wymaga jego wag podczas własnych obliczeń.

## Zakres i kryteria odbioru

- [ ] RoMa v2 jest osobnym wyborem dla pary, całej serii sąsiednich klatek
  i odebranego grafu. Wszystkie drogi korzystają z tego samego estymatora
  pary. Dotychczasowe modele pozostają dostępne bez automatycznej promocji.
- [ ] Adapter jawnie przelicza współrzędne znormalizowane/gęstego pola
  oraz przygotowanych wejść na piksele obu oryginałów. Zapisuje skalowanie,
  padding, kanały i normalizację. Próbkowanie gęstych korespondencji ma
  wersjonowane parametry, limit liczby punktów i seed, jeśli jest losowe.
- [ ] Po odrzuceniu korespondencji poza ważnymi próbkami wyznaczamy jedno
  XY agregacją korespondencji odebraną w REG-10, bez wyszukiwania wycinków
  z REG-05. Gęste punkty z jednego zakłócenia nie są niezależną większością.
  Ocena pokrycia i precyzji modelu pozostaje
  jego diagnostyką, bez udawanej kalibracji prawdopodobieństwa poprawnego STM.
- [ ] GUI pokazuje pokrycie dopasowaniami, przestrzenne poparcie i odmowy.
  Porównanie z EfficientLoFTR zachowuje tę samą agregację z REG-10, listę
  kandydatów par, graf, progi w pikselach original i renderer. Historyczny
  Deep jest dodatkowym porównaniem całych estymatorów. Różnice przygotowania
  wejścia oraz kwalifikacji punktów są jawne w zapisanej konfiguracji.
- [ ] Wynikiem do renderowania pozostaje jedna translacja na klatkę.
  Nie zapisujemy gęstego pola jako deformacji pomiaru, nie poprawiamy lokalnie
  ruchu molekuł i nie stosujemy automatycznie ECC po RoMa v2.
- [ ] Opcjonalny adapter działa z lokalnymi wagami i pełnym zestawem
  potrzebnych zasobów DINOv3. Instrukcja przypina wersje kodu/bibliotek,
  warianty i SHA-256 wag oraz warunki kodu i modeli. Brak któregokolwiek
  zasobu daje przyczynę niedostępności, bez próby pobierania w tle.
- [ ] Brak pamięci, błąd modelu lub brak wskazanego urządzenia pozostawia
  poprzedni wynik. Nie zmieniamy po cichu modelu, urządzenia ani rozdzielczości.
  Możliwy jawny preset o mniejszym koszcie jest odrębną zapisaną konfiguracją.
  Model ładuje się raz na zadanie; dane gęste pary zwalniamy po agregacji,
  zachowując tylko potrzebną, ograniczoną diagnostykę.
- [ ] Konflikt opcjonalnych zależności ma udokumentowane rozwiązanie
  w zakresie Viewera, z uruchomieniem z GUI i bez psucia istniejących metod.
  Wymagane zmiany modułów wspólnych lub konfiguracji głównej trafiają do handoff.
- [ ] Dokument próby zachowuje konfigurację modelu/próbkowania, urządzenie,
  pochodzenie wag, XY i diagnozy. Odczyt i porównanie wyniku przy oryginalnych
  źródłach nie wymagają modelu. Nowe obliczenie sprawdza dostępność zasobów.
  Zastosowanie, ręczne korekty i MPP/AVI zachowują kontrakt REG-08c.
- [ ] Dla REG-06 wskazujemy ocenę zależną, jeśli model lub przygotowanie
  wejścia używały danych kontrolnych. Wybranie punktów poza prostokątem
  nie usuwa wpływu tych pikseli przez kontekstowe cechy DINOv3.
- [ ] Raport rzeczywistych prób obejmuje czas estymacji, solvera i renderu,
  RAM/VRAM, faktyczne urządzenie, odmowy i ocenę obrazową osobno. Uruchomienie
  na GPU z większą pamięcią nie potwierdza dostępności wariantu na 8 GB.
  Brak próby na docelowym budżecie pozostaje ograniczeniem, a nie sukcesem.

Poza zakresem: trening, deformacja obrazów, uśrednianie klatek, automatyczne
łączenie wyników różnych modeli i gwarancja przewagi gęstych dopasowań.
Gorszy lub niejednoznaczny wynik może zakończyć eksperyment po zapisanej
decyzji użytkownika, zgodnie z planem.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Pole/korespondencje → globalne XY:** poprawne osie i znaki, transformacja
  współrzędnych obu obrazów, niekwadratowe wymiary, subpiksele, padding,
  znany ruch i błędna gęsta grupa. Sprawdzamy także odmowę i brak lokalnego warpu.
- **Konfiguracja/zasoby → wykonanie:** brak części wag, błąd/OOM/anulowanie,
  brak sieciowego pobierania i fallbacku. Próbkowanie jest odtwarzalne według
  zapisanych ustawień. Test adaptera nie zastępuje próby rzeczywistego modelu.
- **GUI/seria/graf/dokument:** zgodność XY w poszczególnych drogach, trwałość
  diagnostyki i pochodzenia, ograniczona pamięć, odczyt bez modelu oraz ochrona
  wcześniejszego aligned. Eksport i korekta ręczna obejmują nowe pochodzenie.
- Z rzeczywistymi lokalnymi wagami sprawdzamy znany wzorzec i oba filmy.
  Raport CPU/CUDA, GUI oraz VLC rozdziela dowody; istniejące testy solvera
  i eksportu rozszerzamy tylko w miejscach nowego zachowania.

## Próba manualna

1. Uruchom `python -m stmviewer.main` w opisanym środowisku. Sprawdź komunikat
   przy brakującym zasobie, następnie uruchom z przygotowanymi wagami.
   UI ma wskazywać RoMa v2 i faktyczne urządzenie.
2. Porównaj RoMa v2 z Deep i EfficientLoFTR na `cpu.mpp` oraz wzorcu
   z nieruchomymi pasami. Obejrzyj rozmieszczenie korespondencji i obszary
   poparcia; więcej punktów nie musi oznaczać lepszego XY.
3. Na MOVIE_4 usuń źródłowe 1 i 2 przed obliczeniami. Obejrzyj stałe pary
   i problemy 29→30, 35→36, 44→45→46, 61→62, 94→95→96→97 według numeracji
   po usunięciu. Powtórz porównanie na MOVIE_8 i nowych przypadkach.
4. Uruchom oba pełne filmy w trybie sąsiednim oraz jednym ustalonym wariancie
   grafu. Porównaj przy stałym konsensusie i widoku. Zapisz odmowy, jakość
   pierwszych 150 klatek MOVIE_4 i dalszej części oraz zmierzone zasoby.
5. Anuluj nowe obliczenie. Poprzedni aligned ma zostać. Zapisz/otwórz próbę,
   również przy niedostępnym modelu; dostępny ma być podgląd zapisanych XY.
6. Zastosuj kompletny wynik, popraw parę ręcznie i zapisz małe MPP+metadane
   oraz AVI. Otwórz MPP w Viewerze, AVI w VLC. Sprawdź położenia, brak gęstego
   warpu i nakładek diagnostycznych; zanotuj osobno wynik próby 8 GB VRAM.

**Oczekiwany wynik:** sprawdzenie innej rodziny matcherów przy niezmienionej
warstwie globalnego XY i świadoma decyzja o przydatności na obu filmach.
