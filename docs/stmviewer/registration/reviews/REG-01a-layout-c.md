# REG-01a — wdrożenie układu C

Data: 2026-10-31. Użytkownik wybrał C po obejrzeniu prototypu i wyjaśnieniu
opcjonalnego zachowania wyniku do porównania. Następnie potwierdził testy
manualne działającego GUI: „testy manualne ok” (2026-10-31).
Status: **done**, odbiór użytkownika zaliczony.

Baza: `9b47c1571c3482ac423ababfea3b3cb61463665b`.
Implementacja: `b7aaf37`, poprawki układu: `a9a072f`.
Źródło decyzji: [prototyp i wybór](../pair-window-prototype.md), pierwotny kod
prototypu `dd8b48f` pozostaje na osobnej gałęzi, bez scalenia do aplikacji.

## Zakres

- Karty wyników i metoda po lewej, podgląd po prawej, ręczne sterowanie pod obrazem.
- „Wynik bieżący” / „Wynik zachowany”, z nazwą metody i XY; osobno rozwijane szczegóły.
- „Zachowaj do porównania” kopiuje bieżący wynik. Porównanie jest opcjonalne.
  „Zakończ korektę” ustawia bieżący wynik ręczny, zachowując kopię drugiego wyniku.
- „Klatka bazowa” / „Klatka przesuwana”, „Bez przesunięcia” / „Z dopasowaniem”,
  „Pokaż cały obraz” i dynamiczna nazwa przełączania oglądanej klatki.
- Bez zmian algorytmów, modelu szkicu, pełnego aligned, eksportów i życia serii.
  Wyniki pary pozostają lokalne dla tego okna. Moduły współdzielone bez zmian.

## Sprawdzenia automatyczne

Istniejące testy zachowań GUI dostosowano do wyboru kart zamiast listy A/B,
bez nowych testów odwzorowujących sam układ lub tekst przycisków. Pierwsze
wywołanie przed implementacją kart: 6 failed, 7 passed (oczekiwane red).
Po wdrożeniu i po poprawkach: **13 passed**. Obejmuje też rzeczywisty zapis
MPP/AVI przed i po ręcznej próbie oraz ochronę pełnego aligned.

Test szerokości panelu rozszerzono o konkretną usterkę znalezioną w xcb:
długą ścieżkę wag i wysokość opisu zakończenia korekty. Przed poprawką
poziomy zakres przewijania w offscreen wynosił 1139 px; po poprawce 0.

- Cały Viewer na końcowym kodzie: **398 passed, 2 skipped**, 56,57 s.
- Pełne repo, jedno wywołanie rozpoczęte dla `b7aaf37`: **2184 passed,
  14 failed, 16 skipped**, 272,78 s. Zestaw 14 nazw błędów identyczny
  z REG-01a przed zmianą układu: MolTrack/SAM2 oraz NanoTrack.
  Poprawki wyglądu sprawdzono ponownie testami GUI i całego Viewera;
  nie ponawiano całego repo. Nie deklarujemy zaliczenia pełnego repo.
- Mypy strict: **38 plików**; fixture ułamkowego startu również sprawdzony.
  Ruff i `git diff --check`: bez błędów. Największy zmieniony plik: **472 linie**.

## Rzeczywiste GUI Qt xcb — sterowanie skryptem

cpu.mpp: Phase → zachowanie → ręczna korekta → zakończenie → wybór obu kart.
Powrót do zachowanego wyniku przywraca identyczny podgląd, również z zoomem,
przesuniętym widokiem i gamma. MOVIE_8, para 16→17: ręczna obsługa dostępna.

Obejrzano zrzuty przy 1180×820 i1080×760, także z rozwiniętymi szczegółami
wyniku i długą nieistniejącą ścieżką wag. Wykryto i poprawiono poszerzanie
lewego panelu oraz pionowe przycięcie tekstu obok „Zakończ korektę”. Po poprawce
poziomy zakres przewijania wynosi 0; opis ma 54 px przy wymaganych 54 px.
Ręczne przyciski są dostępne pod obrazem i mieszczą się w obu rozmiarach.

To automatyczna kontrola GUI, nie ręczny odbiór ani ocena fizycznej jakości XY.
Lokalne artefakty: `data/registration-pair-layout-c/` (skrypt xcb, raporty, zrzuty,
logi pytest). Windows i ręczne odtwarzanie w VLC nie były wykonywane w tej zmianie.

## Standards

**0 uwag** w `9b47c15…a9a072f`. Przegląd odczytowy, niezależny od osi Spec.
Zakres Viewera i limit plików zachowane; testy nadal używają publicznych kontrolek.
Nie znaleziono problemów projektowych wymagających poprawki.

## Spec

**0 uwag** w `9b47c15…a9a072f`. Układ i nazwy zgodne z wybranym C;
porównywanie jest opcjonalne. Zachowane ręczne XY, ułamki, reset/anulowanie,
niezmienność wyników, widok, zadania i ochrona pełnego aligned/eksportów.
Rozwijane szczegóły odpowiadają prototypowi. Brak rozszerzenia zakresu.

## Odbiór użytkownika

Uruchom `python -m stmviewer.main` w `netcat`, otwórz cpu.mpp, wybierz klatkę 2
oraz **Porównaj parę…**. Wykonaj najpierw ręczne XY=(2,−1), bez zachowywania
wyniku. Następnie oblicz Phase, zachowaj do porównania, popraw ręcznie i zakończ;
wybieraj obie karty. Sprawdź też zoom, gamma i zmianę warstw.
Pełne kroki: [instrukcja ręczna](../manual-alignment-manual.md).

Decyzja o działającym oknie: **zaakceptowane**. Użytkownik potwierdził
„testy manualne ok” 2026-10-31 dla kodu `b7aaf37` i `a9a072f`,
z dokumentacją `8574886`. System, szczegółowe kroki i dane nie zostały podane
w potwierdzeniu; nie dopisujemy wyników poszczególnych prób. REG-01a ma status
`done`; późniejszą implementację i potwierdzony odbiór REG-02 opisuje
[jego karta](REG-02.md).

Przy zapisie odbioru sprawdzono statusy, odnośniki i `git diff --check`;
aktualizacja wyłącznie dokumentacyjna, bez ponawiania testów kodu.
