# REG-02: Korelacja bez normalizacji fazowej

**What to build:** Użytkownik jawnie wybiera korelację bez normalizacji fazowej,
porównuje ją z Phase dla pary i rejestruje nią całą serię.
**Blocked by:** [REG-01a](01a-manual-alignment.md), w tym odbiór manualny — spełnione 2026-10-31.
Zależność dodana 2026-10-30 po zakończonym REG-01; realizacja zlecona 2026-10-31.
**Status:** done
**Manualny odbiór:** zaliczony — użytkownik potwierdził „testy manualne ok” 2026-10-31 i przekazał ocenę MOVIE_4; bez istotnej poprawy wariantu względem Phase.
**Wykonawca:** Codex, 2026-10-31; baza przeglądu `e1d42d4315280d74a2c5494be93c29687909189b`.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).

## Zakres i kryteria odbioru

- [x] Osobno nazwany wariant korzysta z korelacji bez normalizacji fazowej
  na surowych danych. Nie łączy tej zmiany z filtrowaniem, maskami lub innym
  sposobem wyznaczania odniesienia. Dotychczasowy Phase zachowuje zachowanie.
- [x] Ten sam wariant działa w podglądzie pary i w zwykłym Rejestruj dla całej
  serii; znaki XY, sumowanie względem pierwszej klatki i geometria są wspólne.
- [x] Wynik nie jest przedstawiany jako zweryfikowany na podstawie starego
  wskaźnika piku fazowego. Nowy wariant ma jawną informację o niezweryfikowanej
  pewności; formalne wyliczenie wartości nie jest dowodem poprawności.
- [x] Przechodzi istniejący reproduktor MOVIE_8 1→2: odległość od lokalnego
  konsensusu trzech fragmentów ≤3 px. Wynik ten nie staje się progiem dla filmu.
- [x] Pełny aligned zachowuje oryginały, postęp, anulowanie i atomową podmianę.
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


## Wykonanie — 2026-10-31

Implementacja `d85ba1b`, poprawki przeglądu `bcf0e70`; baza `e1d42d4`.
**Korelacja bez normalizacji (v1)** jest dostępna dla pary i całej serii.
Stała konfiguracja v1 używa `normalization=None`; Phase pozostaje domyślny.
Wyniki estymacji mają jawną niezweryfikowaną pewność (`manual_review`, `null`),
zachowaną również w MPP wraz z nazwą i wersją wariantu. Nie zmieniono wspólnego kodu.

Reproduktor MOVIE_8 1→2 przechodzi przez kod aplikacji: (+13,55;+0,25),
0,51 px od lokalnego odniesienia. Oba pełne filmy kończą obliczenia; rzeczywiste
anulowanie kolejnej próby zachowuje wcześniejszy aligned. To sprawdzenie funkcji,
nie ocena fizycznej poprawności całego filmu.

48 końcowych testów wybranych scenariuszy PASS, mypy strict 38, Ruff bez uwag.
Pełne repo: 2196 passed, 14 failed, 16 skipped; te same 14 wcześniejszych błędów
poza Viewerem. Standards 0; Spec 1 uwaga naprawiona, 0 otwartych. Pliki ≤856 linii.
Aktualne kroki z nazwami układu C: [instrukcja manualna](../unnormalized-correlation-manual.md).
Pełne wyniki, ograniczenia formatu i przegląd: [karta REG-02](../reviews/REG-02.md).
## Odbiór — 2026-10-31

Użytkownik zaakceptował testy manualne. REG-02 zamknięto jako `done`.
Aktualizacja planu 2026-10-31: przed REG-03 dodano
[REG-02a: ręczne korekty filmu](02a-manual-movie-corrections.md); REG-03 czeka
na jego implementację i manualny odbiór. Akceptacja funkcji REG-02 nie oznacza
potwierdzenia poprawy jakości: w MOVIE_4 użytkownik nie widzi dużej różnicy
między Phase a wariantem bez normalizacji. Najlepiej ocenił Deep Matcher
w obejrzanych pierwszych 100 klatkach. [Pełna relacja](../reviews/REG-02.md#ręczny-odbiór-użytkownika).

Dalsze próby MOVIE_4 obejmują źródłowe klatki 3–364, po usunięciu dwóch
błędnie dołączonych klatek w aplikacji przed rejestracją. Źródłowy plik pozostaje
bez zmian. Poprzednie pomiary na 364 klatkach pozostają historyczne.
