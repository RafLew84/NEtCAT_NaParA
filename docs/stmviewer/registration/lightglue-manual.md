# REG-13 — ręczna próba LightGlue + SuperPoint

Uruchom z katalogu `NEtCAT-viewer`:

```bash
conda activate netcat
python -m stmviewer.main
```

To dodatkowa metoda rejestracji pary, filmu i grafu. Dotychczasowe algorytmy
pozostają dostępne. Stan prób automatycznych i ograniczenia jakości opisuje
[raport](lightglue-results.md). Odbiór użytkownika pozostaje niewykonany.

## Wybór i zasoby

Wybierz **LightGlue + SuperPoint**. Pola mają przygotowane wartości domyślne:

- kod: `/home/rlew/.cache/stmviewer/lightglue/source`;
- wagi LightGlue: `/home/rlew/.cache/stmviewer/lightglue/weights/superpoint_lightglue.pth`;
- wagi SuperPoint: `/home/rlew/.cache/stmviewer/lightglue/weights/superpoint_v1.pth`.

Na innym stanowisku wskaż własne kopie tego samego kodu i wag. Pochodzenie,
wersje, licencje oraz sumy: [przygotowanie](lightglue-environment.md).
Opcjonalne zależności zawiera `stmviewer/requirements-lightglue.txt`;
obecny `netcat` ma już potrzebne biblioteki. Nie potrzeba osobnego środowiska.
Model działa w procesie tego samego interpretera co aplikacja.

**Auto** wybiera CUDA, jeśli jest dostępna. Możesz wskazać **CPU** lub **CUDA**.
Kliknij **Sprawdź model**: weryfikuje kod, oba checkpointy i urządzenie.
Brak/uszkodzenie pliku ma konkretny komunikat. Program nie pobiera zasobów
ani nie zmienia wybranego urządzenia po błędzie.

## Mały wzorzec i podgląd pary

1. Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp`.
2. Wybierz klatkę 2 i **Porównaj parę…**, ustaw nową metodę i oblicz wynik.
   XY do nałożenia na klatkę 2 względem 1 wynosi **(+2, −1) px**.
   Sprawdź nakładkę oraz przełączanie obrazów przy niezmienionym zoomie.
3. Dla klatek 2→3 oczekiwane XY to **(−3, +2) px**.
4. W oknie głównym kliknij **Rejestruj**. Powinno pojawić się aligned tej
   samej wybranej klatki. Skumulowane XY filmu to (0,0), (+2,−1), (−1,+1).
5. Zmień gamma i zoom, wróć do original/aligned: nie zmienia to dopasowania.
   W szczegółach są zgodne punkty, rozkład przestrzenny i przyczyna ostrzeżeń.
   Zgodność punktów nie stanowi niezależnego potwierdzenia fizycznego dryfu.

## Trudne filmy i graf

Otwórz MOVIE_4 i usuń pierwsze dwie klatki **przed** obliczeniem.
Numeracja prób dotyczy pozostałych 362 klatek. MOVIE_8 pozostaw bez usuwania.
[Protokół](manual-protocol.md)
zawiera 18 par oraz zasady porównania z Deep outdoor i RoMa Turbo.

Dla wybranej pary obejrzyj te same struktury przy wspólnym widoku. Możesz użyć
**Zachowaj do porównania**, aby zestawić wynik nowej metody z dotychczasową.
Odnotuj także pogorszenia i przypadki nierozstrzygalne. Słaby wynik jest
widoczny z ostrzeżeniem; rzeczywisty brak wystarczających punktów daje odmowę.

**Rejestruj** wymaga kompletu kolejnych dopasowań. **Dopasowanie wieloklatkowe…**
korzysta także z innych par w oknie 3/5. Wybierz tę samą nową metodę,
oblicz graf i obejrzyj relacje. LS i Huber pracują na zapisanych pomiarach;
Huber nie uruchamia ponownie modelu. Brakująca relacja pozostaje brakiem.
Rozłączny graf lub niezbieżny solver nie może zastąpić całego filmu.

W wykonanych próbach pełne MOVIE_4/MOVIE_8 nie dały kompletnego wyniku
LightGlue — szczegóły i gotowe sesje diagnostyczne są w raporcie. Nie traktuj
samego ukończenia obliczeń jako zaliczenia jakości. Zastosowanie i eksport
można sprawdzić na kompletnym `cpu.mpp`.

## Zastosowanie, sesja i eksport

1. Na `cpu.mpp` oblicz graf, zastosuj kompletny wynik przez **Zastosuj wynik
   do filmu**. Sprawdź aligned; samo oglądanie kandydata go nie podmienia.
2. Popraw ręcznie parę i zastosuj korektę do filmu. Sprawdź zmianę dalszych
   klatek i cofnięcie korekty, zgodnie z [instrukcją korekt](manual-movie-corrections-manual.md).
3. **Zapisz sesję…**, zamknij i otwórz `.stmsession`. Wróć do tej metody:
   obie ścieżki wag i urządzenie powinny pozostać. Powtórz zapis po wybraniu
   Phase — wcześniejsze ustawienia LightGlue również mają zostać.
4. Sam zapisany wynik można otworzyć bez kodu/wag. Wskazanie nieistniejących
   ścieżek nie odbiera podglądu i eksportu; blokuje nowe obliczenie.
5. Wyeksportuj krótki aligned do MPP i AVI. Ponownie otwórz MPP i sprawdź
   wartości, geometrię oraz pochodzenie; AVI obejrzyj w VLC.
6. Przy istniejącym aligned uruchom rejestrację ponownie i kliknij **Anuluj**.
   Poprzedni film i korekty mają pozostać. Sprawdź osobno błąd dla każdego
   checkpointu, wskazując brakujący plik; nie usuwaj przygotowanych wag.

Do ręcznego odbioru zapisz osobno działanie funkcji i jakość na strukturach
próbki. Automatyczne Qt offscreen, poprawne wzorce i zapis sesji nie zastępują
tej oceny. REG-14 czeka na decyzję po REG-13.
