# REG-08: Spójność kilku klatek — etap warunkowy

**What to build:** Użytkownik sprawdza, czy przesunięcie A→C zgadza się
z sumą A→B i B→C, oraz ogląda pary tworzące niespójny zestaw.
**Blocked by:** [REG-07](07-full-movie-comparison.md) i decyzja użytkownika
o uruchomieniu tego etapu po ocenie pełnych filmów.
**Status:** planned
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).
Przed startem potwierdzamy, że problemy pozostałe po REG-07 uzasadniają ten etap.

## Zakres i kryteria odbioru

- [ ] Dla kolejnych trójek i wskazanej trójki program wyznacza także
  bezpośrednie A→C tą samą metodą, z właściwymi maskami i ustawieniami.
- [ ] UI pokazuje trzy wektory, resztę złożenia w pikselach oraz źródłowe
  numery klatek. Można otworzyć każdą z trzech par w porównaniu obrazów.
- [ ] Brak części wspólnej, tekstury lub wyniku jednej pary oznacza brak
  oceny tej trójki. Nie jest to automatycznie zerowa reszta ani błąd dryfu.
- [ ] Niespójność wskazuje potrzebę obejrzenia obrazów, a nie konkretną
  parę, która na pewno jest błędna. Spójność także nie dowodzi poprawności
  na obrazie okresowym.
- [ ] Diagnostyka nie wymusza gładkości, stałego kierunku ani małych kroków.
  Nie zmienia istniejących XY i nie stosuje automatycznej optymalizacji grafu.
- [ ] Próba działa w tle z anulowaniem, zapisuje diagnozy w dokumencie
  próby z REG-07 i pozostawia aktywne aligned oraz eksporty bez zmian.

Poza zakresem: optymalizacja trajektorii, automatyczne zastępowanie źle
dopasowanych krawędzi i interpolowanie brakujących przesunięć w czasie.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Trójka i wyniki par → reszta złożenia:** poprawne znaki, zmienny kierunek,
  jedna błędna para, brak jednego wyniku; znana trajektoria syntetyczna.
- **GUI/dokument → diagnoza:** właściwe pary, przejście do porównania,
  anulowanie i brak modyfikacji pełnego aligned. Spójność nie zastępuje
  niezależnych fragmentów kontrolnych z REG-06.

## Próba manualna

1. Na `cpu.mpp` sprawdź trójkę 1→2→3: zmiana kierunku nie powinna sama
   powodować alarmu. Obejrzyj bezpośrednią parę 1→3 i składane przesunięcie.
2. Na dostarczonym wzorcu z celowo mylącą jedną parą sprawdź resztę i obejrzyj
   wszystkie trzy pary. Diagnostyka nie naprawia automatycznie obrazu.
3. Na obu filmach wybierz trójki obejmujące problemy z REG-07. Porównaj
   wskazania z niezależną kontrolą i zapisz przypadki niejednoznaczne.
4. Zapisz/otwórz próbę i sprawdź zachowanie diagnoz oraz niezmienione XY.

**Oczekiwany wynik:** dodatkowe narzędzie lokalizacji problemów. Decyzja
o późniejszej optymalizacji całej serii wymaga osobnego zakresu i odbioru.
