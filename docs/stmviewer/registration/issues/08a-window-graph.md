# REG-08a: Graf dopasowań z oknem 3 lub 5 klatek

**What to build:** Użytkownik tworzy osobną próbę pełnego filmu, w której obecny
Deep dopasowuje także niesąsiednie klatki, a program wspólnie wyznacza ich XY.
Można obejrzeć i zapisać próbę oraz porównać ją z łańcuchem sąsiednich dopasowań.
**Blocked by:** [REG-08](08-temporal-consistency.md), w tym odbiór manualny.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.
**Dodano do planu:** 2026-10-31, na zlecenie użytkownika po research.

Obowiązują [plan](../README.md#kontrakty-rozszerzenia-wieloklatkowego),
[protokół](../manual-protocol.md) i [uzasadnienie](../../registration-multiframe-research.md).
Ten etap bada sam efekt dodatkowych relacji. Nie dodaje nowego modelu pary,
odpornego solvera ani podmiany aktywnego aligned. REG-07 zapewnia zapis bieżącej
pracy; podgląd kandydata grafu i porównanie go z bazą powstają w tym tickecie.
Nie zakładamy istnienia biblioteki pełnych prób A/B.

## Zakres i kryteria odbioru

- [ ] W GUI można wybrać **próbę grafu** z oknem 3 albo 5 i obejrzeć liczbę
  planowanych par przed obliczeniem. Dla każdej pary `i < j`, `j-i ≤ k`, liczymy
  jeden pomiar. Krótka seria używa tylko istniejących klatek; mniej niż dwie
  nie wystarcza do próby. Wybór oglądanej klatki nie zmienia konfiguracji.
- [ ] Używamy obecnego Deep bez ECC, tych samych lokalnych wag, ustawień i
  przygotowania obrazu. Wariant przestrzennego poparcia REG-05 pozostaje osobną
  próbą. Model jest ponownie używany dla wielu par, bez ładowania wag co parę;
  cache ma jawny limit i klucz uwzględniający źródła oraz konfigurację.
- [ ] Wszystkie wektory wracają do pikseli oryginału. Pomiar `d_ij` przesuwa j
  na i; globalne `p` spełniają możliwie dokładnie `p_j-p_i=d_ij`, `p_0=(0,0)`.
  Rozwiązujemy zwykłe LS z równymi wagami ważnych pomiarów, bez wygładzania,
  regularizacji pozycji do zera i zmiany kierunku wektorów na podstawie czasu.
- [ ] Zapisujemy wszystkie rozpatrzone pary, uzyskane XY, stan/powód odmowy,
  konfigurację modelu, numery i tożsamość źródeł, reszty rozwiązania oraz kotwicę.
  Wynik modelu jest informacją pomocniczą, nie automatyczną wagą ani
  prawdopodobieństwem prawdziwego dryfu. Brak dopasowania nie jest zerowym XY.
- [ ] Brak pojedynczej relacji nie blokuje grafu, jeśli inne pomiary łączą
  wszystkie klatki. Graf rozłączny nie tworzy pełnej próby XY; pokazujemy
  komponenty i przyczyny braków. Mosty i obszary bez nadmiarowej weryfikacji są
  oznaczone także w grafie spójnym. Nie resetujemy odłączonej części do zera.
- [ ] UI pokazuje listę relacji i ich rozbieżności oraz pozwala przejść do
  porównania konkretnej pary, również niesąsiedniej. Małe reszty nie nadają
  automatycznej oceny „poprawny”: powiązane artefakty i aliasy okresowe mogą
  spełnić wszystkie relacje. Wynik błędnego solvera jest odmową z przyczyną.
- [ ] Ten ticket dodaje podgląd kandydata grafu z nawigacją/Play i porównaniem
  z bazą we wspólnym kadrze. Korzysta z dotychczasowego renderera i nawigacji.
  Obrazy kandydata renderowane są na żądanie z oryginałów;
  nie trzymamy drugiego pełnego stosu danych dla każdego wariantu.
- [ ] Jeśli dostępne są wszystkie sąsiednie pomiary, ich suma daje bazę
  łańcuchową bez ponownego liczenia Deep. Gdy któregoś brakuje, nie tworzymy
  fałszywie pełnego łańcucha: można porównać aktywny kompletny wynik z sesji,
  z jawnym pochodzeniem, lub tylko dostępne pary. Graf może nadal mieć pełne rozwiązanie.
- [ ] Sesja REG-07 otrzymuje wersjonowane rozszerzenie dla bieżących relacji
  grafu, konfiguracji LS, kandydata i diagnoz, także grafu rozłącznego. Ten ticket
  dodaje zapis tych danych; REG-07 nie zapisywał przerwanych prób diagnostycznych.
  Odczyt zachowuje wyniki bez modelu i odróżnia aktywny aligned od kandydata.
  Starsze sesje bez grafu nadal działają; nieznane wersje i niespójne powiązania
  z obrazami są odrzucane. Nie wracamy do formatu `*.stmtrial.json`.
- [ ] Obliczenia mają postęp/anulowanie i blokady zmiany serii. Anulowanie,
  brak modelu, błąd zasobów i błąd solvera nie są pomijanymi lokalnymi odmowami.
  Aktywny aligned, ręczne korekty i eksport pozostają bez zmian także po sukcesie.
  UI wyraźnie oznacza, że oglądana próba jeszcze nie jest wynikiem do eksportu.

Poza zakresem: Huber/IRLS, ważenie wynikiem confidence, dalsze odniesienia poza
oknem, automatyczne odrzucanie według cykli, zastosowanie do filmu i korekcja
tearingu. Eksport nowego grafu dodaje REG-08c; w tym etapie badamy podgląd i zapis
danych grafu w sesji. REG-06 jest odłożony i nie blokuje tego etapu. Po jego
ewentualnym wznowieniu niezależna kontrola pozostaje poza wyborem relacji
i estymacją; obecnie nie symulujemy jej wyników.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Seria i okno → pomiary oraz wspólne XY:** znane XY z nawrotami, właściwe
  pary i znaki, kotwica, krótka seria, niezmienność oryginałów. Zestaw samych
  sąsiednich relacji odtwarza sumę łańcucha. To nie wymaga opcji okna 1 w GUI.
- **Pomiary z brakami → wynik lub jawna odmowa:** redundantne obejście braku,
  izolowana klatka, dwa komponenty, most i drzewo. Spójny alias okresowy nie
  staje się dowodem jakości. Diagnostyka rozdziela odmowę pary od awarii zadania.
- **GUI i sesja → porównanie:** te same relacje po odczycie, brak ponownego
  modelu, niespójne źródła, wspólny układ, Play/zoom, stan zadania i anulowanie.
  Obliczenie/oglądanie kandydata nie zmienia aktywnego filmu ani eksportu.
  Otwarcie sesji przywraca zapisany aktywny wynik; kandydata nie stosuje.
  Pamięć podglądu nie rośnie o pełny film na każdy wariant.

## Próba manualna

1. Uruchom `python -m stmviewer.main` w `netcat`. Realizujący dostarcza wzorzec
   ze znanymi XY, zmianą kierunku i dostateczną teksturą dla rzeczywistego Deep.
   Oblicz bazę i graf; obejrzyj wspólne XY, relacje oraz kotwicę.
2. Na MOVIE_4 usuń źródłowe 1 i 2 przed obliczeniami. Zapisz sesje z bazą Deep i kandydatem
   okna 3, potem 5. Porównaj wskazane w protokole problemy, pierwsze 150 klatek
   i cały film. Powtórz dla MOVIE_8, zachowując te same ustawienia modelu.
3. Obejrzyj relację sąsiednią i niesąsiednią, ich d_ij oraz globalne różnice XY.
   Rozbieżność pomiaru i rozwiązania ma być widoczna, bez sugerowania, że
   najmniejsza reszta oznacza najlepsze dopasowanie struktur.
4. Realizujący dostarcza także sesje testowe o znanych relacjach: brak krawędzi
   z obejściem, most i rozłączenie. Otwórz je w GUI i sprawdź oznaczenia oraz
   odmowę pełnego wyniku przy rozłączeniu; są to próby solvera, nie modelu Deep.
5. Zapisz i otwórz samą sesję, także bez dostępnego modelu. Sprawdź XY, diagnozy
   i odtworzony aktywny aligned; kandydat grafu nadal nie jest zastosowany.
   Anuluj nowe obliczenie: poprzedni kandydat i aktywny film zostają.
   MPP/AVI nadal przedstawiają aktywny aligned, a nie oglądany kandydat.

**Oczekiwany wynik:** użytkownik może ocenić wpływ kilku odniesień niezależnie
od zmiany matchera. Raport rozdziela jakość, braki, czas modelu/solvera/renderu,
RAM i VRAM. Brak poprawy jest dopuszczalnym wynikiem eksperymentu, nie ukrytą odmową.
