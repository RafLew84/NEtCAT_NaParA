# REG-02: Korelacja bez normalizacji fazowej

**What to build:** Użytkownik jawnie wybiera korelację bez normalizacji fazowej,
porównuje ją z Phase dla pary i rejestruje nią całą serię.
**Blocked by:** [REG-01](01-pair-comparison.md), w tym odbiór manualny.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).

## Zakres i kryteria odbioru

- [ ] Osobno nazwany wariant korzysta z korelacji bez normalizacji fazowej
  na surowych danych. Nie łączy tej zmiany z filtrowaniem, maskami lub innym
  sposobem wyznaczania odniesienia. Dotychczasowy Phase zachowuje zachowanie.
- [ ] Ten sam wariant działa w podglądzie pary i w zwykłym Rejestruj dla całej
  serii; znaki XY, sumowanie względem pierwszej klatki i geometria są wspólne.
- [ ] Wynik nie jest przedstawiany jako zweryfikowany na podstawie starego
  wskaźnika piku fazowego. Nowy wariant ma jawną informację o niezweryfikowanej
  pewności; formalne wyliczenie wartości nie jest dowodem poprawności.
- [ ] Przechodzi istniejący reproduktor MOVIE_8 1→2: odległość od lokalnego
  konsensusu trzech fragmentów ≤3 px. Wynik ten nie staje się progiem dla filmu.
- [ ] Pełny aligned zachowuje oryginały, postęp, anulowanie i atomową podmianę.
  MPP+metadane i AVI przyjmują nowy wynik; metadane MPP zachowują jednoznaczną
  nazwę wariantu. AVI nie wymaga nowych napisów ani formatu metadanych.
  Obliczenie nie zależy od ustawień prezentacji.

Poza zakresem: domyślne włączenie wariantu, automatyczny wybór metody i nowa ocena jakości.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Wybrany wariant + oryginały → wynik:** syntetyczne przesunięcia XY i braki
  tekstury, zgodność pary/serii, geometria i ochrona starego wyniku po błędzie.
- **GUI → widoczny wynik i eksport:** poprawna nazwa/stan niepewności,
  brak przełączenia dotychczasowego Phase, mały roundtrip MPP i odczyt AVI.
- Lokalny reproduktor uruchomić dla Phase (znany RED na bazie) i nowego
  wariantu; nie dodawać dużego prywatnego pomiaru jako obowiązkowego fixture CI.

## Próba manualna

1. Na `cpu.mpp` porównaj Phase A i nowy wariant B na obu parach. Oczekuj
   pokrywania znaczników i poprawnych kierunków; obejrzyj też cały aligned.
2. Na MOVIE_8 1→2 porównaj trzy fragmenty reproduktora i dodatkowe struktury.
   Oczekiwane jest zbliżenie do lokalnego (+14,0), a nie obietnica poprawy całej klatki.
3. Wykonaj pełne oba filmy, obejrzyj stałe pary i odtwórz aligned. Zapisz
   oddzielnie poprawę, pogorszenie lub niejednoznaczność dla każdego obszaru.
4. Anuluj kolejną rejestrację. Zapisz mały wynik do MPP+metadane i AVI,
   otwórz ponownie; sprawdź geometrię, nazwę i zachowanie braków.

**Oczekiwany wynik:** uczciwe porównanie jednej zmiany algorytmu. Brak poprawy
na części danych jest informacją do decyzji użytkownika, nie powodem jej ukrycia.
