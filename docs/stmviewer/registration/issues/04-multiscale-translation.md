# REG-04: Dopasowanie wieloskalowe

**What to build:** Użytkownik wybiera wariant wyznaczający najpierw zgrubne XY,
a potem doprecyzowujący je na pełnej rozdzielczości i porównuje go z REG-03.
**Blocked by:** [REG-03](03-manual-masks.md), w tym odbiór manualny.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).

## Zakres i kryteria odbioru

- [ ] Nowy wariant wykorzystuje piramidę rozdzielczości i przenosi estymatę
  XY do kolejnych skal. Finalne przesunięcie jest w pikselach oryginału.
- [ ] Wspólna część obrazów i maski są uwzględniane podczas oceny kandydatów.
  Przenoszenie masek do mniejszej skali nie czyni wyłączonych próbek ważnymi.
  Granice obrazów nie są traktowane jako zawijające się okresowo.
- [ ] Wynik z pomniejszenia jest sprawdzany i doprecyzowany na oryginałach;
  aliasing i brak szczegółów na małej skali nie stają się automatycznie sukcesem.
- [ ] Alternatywne przesunięcia, w tym różniące się o okres obrazu/wzoru,
  są oceniane na rzeczywistym nakładaniu. Niejednoznaczność ma widoczny status;
  metoda nie wymusza małego kroku ani tego samego znaku co wcześniej.
- [ ] UI pokazuje wynik zgrubny i końcowy oraz powód niepewności. Dostępny
  jest jeden zapisany zestaw ustawień eksperymentu, z widoczną nazwą/wersją;
  nie dodajemy jeszcze rozbudowanego panelu strojenia.
- [ ] Wariant działa na parze i całej serii. Oryginalne wartości są
  interpolowane dopiero przy końcowym tworzeniu aligned. Działają MPP/AVI.

Poza zakresem: lokalny konsensus, automatyczne maski, deformacje, wygładzanie czasu.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Para i maski → XY:** znane duże i subpikselowe przesunięcia w obu osiach,
  niekwadratowe wymiary, zmiana znaku, mała część wspólna, wykluczone pasy
  i tekstura okresowa. Wzorce mają rzeczywiste krawędzie, nie tylko `roll`.
- **Seria → aligned:** zgodność wyniku pary i serii, wartości/geometria,
  anulowanie, brak podmiany po odmowie. Tolerancje wynikają z wzorców testowych,
  nie z rozmiaru estymowanego dryfu.
- **GUI → porównanie:** prawidłowe jednostki obu estymat, wersja ustawień
  i zachowany widok A/B. Test nie potwierdza fizycznego dryfu MOVIE_4/MOVIE_8.

## Próba manualna

1. Na dostarczonym wzorcu z dużym przesunięciem obejrzyj dopasowanie zgrubne
   i końcowe. Zrób to także dla ujemnych XY i zmiany kierunku między klatkami.
2. Porównaj REG-03 A i nowy wariant B przy tych samych maskach na stałych
   parach obu filmów. Zapisz wpływ na duże struktury i drobne szczegóły.
3. Sprawdź wzorzec okresowy: jeśli istnieją równorzędne rozwiązania, UI ma
   zgłosić niejednoznaczność. Mały krok nie jest sam w sobie wynikiem lepszym.
4. Uruchom całe oba filmy, obejrzyj wynik i dodatkowe podejrzane miejsca.
   Powtórz anulowanie i mały roundtrip eksportów według protokołu.

**Oczekiwany wynik:** sprawdzony wpływ wieloskalowości; dalsza praca nie zakłada
automatycznie, że nowy wariant wygrywa ze wszystkimi dotychczasowymi.
