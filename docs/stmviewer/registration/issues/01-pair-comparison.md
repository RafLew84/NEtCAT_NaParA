# REG-01: Porównanie par klatek

**What to build:** Użytkownik ogląda wybraną sąsiednią parę przed i po dopasowaniu
oraz przypina dwie próby A/B do porównania przy identycznych warunkach podglądu.
**Blocked by:** brak — pierwszy etap tego planu.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.

Obowiązują [plan i kontrakty](../README.md) oraz [protokół odbioru](../manual-protocol.md).

## Zakres i kryteria odbioru

- [ ] Z działającego okna można otworzyć podgląd wybranej sąsiedniej pary,
  zobaczyć jej źródłowe numery, wybrać dostępną metodę i obliczyć tylko tę parę.
  Operacja nie wymaga poprawnego dopasowania całego filmu.
- [ ] Podgląd oferuje przełączanie odniesienie/ruchoma i nakładkę 50/50,
  przed oraz po zastosowaniu XY. Przesunięcie jest opisane jako nakładane na
  następną klatkę względem poprzedniej, nie jako fizyczny kierunek ruchu próbki.
- [ ] Można przypiąć poprzednią próbę A i porównać z nową B. Nazwa metody,
  ustawienia, status i para są widoczne; nie przypisujemy wyniku innej parze.
- [ ] A/B zachowują identyczny zoom, punkt zakotwiczenia, gamma i proporcje.
  Wspólny zakres jasności jest wyznaczony z oryginalnej pary i zamrożony dla
  porównania. Różny padding nie wywołuje pozornego ruchu lub zmiany skali.
- [ ] Ważny wspólny obszar jest rozpoznawalny; białe marginesy nie trafiają
  do obliczania zakresu jasności. Przy braku części wspólnej UI to wyjaśnia.
- [ ] A/B przechowują lekkie wyniki i renderują tylko oglądaną parę.
  Próba pary nie podmienia pełnego aligned ani nie staje się wynikiem eksportu.
- [ ] Obliczenia działają w tle z anulowaniem. Błąd zachowuje ostatnią poprawną
  próbę, pokazując wyraźnie niepowodzenie nowej; nie pojawia się zastępcze XY=0.
  Nowy import i zmiana składu serii unieważniają niepasujące próby.

Poza zakresem: nowe algorytmy, maski, zapis porównań na dysk, automatyczna ocena jakości.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Para i przesunięcie → wspólny podgląd:** znany niesymetryczny wzorzec,
  dodatnie/ujemne XY i różne obszary wynikowe; zgodne położenia, ważność oraz
  niezależność od gamma. Nie sprawdza skuteczności algorytmu na pomiarze STM.
- **Kontrolki GUI → próba i A/B:** przypięcie, zmiana pary, ochrona pełnego
  aligned, błąd i anulowanie; testy offscreen nie zastępują oceny wzrokowej.

## Próba manualna

1. Uruchom program według protokołu, otwórz `cpu.mpp` i wykonaj pełne Phase,
   aby istniał aktywny aligned. Następnie otwórz próbę pary 1→2 z Phase.
   Przed dopasowaniem znaczniki skaczą; po dopasowaniu powinny się pokrywać.
   Oczekiwane XY=(+2,−1). Sprawdź też 2→3 z przeciwnymi znakami.
2. Przypnij A, wykonaj B inną dostępną metodą. Przybliż znacznik, przesuń
   widok i przełącz A/B. Położenie odniesienia, zoom i kontrast nie zmieniają się.
3. Otwórz oba rzeczywiste filmy; obejrzyj stałe pary z protokołu. Zapisz
   fragmenty do dalszej kontroli. To odbiór wierności podglądu, nie poprawy XY.
4. Dla bieżącego rzeczywistego filmu najpierw wykonaj pełne Phase. Następnie
   wywołaj w podglądzie par znany błąd ECC/Deep, jeśli metoda jest dostępna;
   sprawdź komunikat i zachowanie pełnego wyniku. Anulowanie sprawdź na
   dostarczonym większym wzorcu i metodzie działającej dostatecznie długo,
   aby można było kliknąć Anuluj. Szybki sukces nie potwierdza anulowania.
5. W głównym oknie wcześniejszy aligned nadal ma właściwą metodę i obrazy;
   podgląd pary nie zmienił wartości original ani aktywnego eksportu.

**Oczekiwany wynik:** wiarygodne narzędzie oceny. Jakość algorytmów pozostaje
bez zmian. Zapis karty i jawny odbiór użytkownika blokują start REG-02.
