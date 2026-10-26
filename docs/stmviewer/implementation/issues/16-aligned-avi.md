# 16: Film AVI z aligned i pełnym obszarem

**What to build:** Użytkownik eksportuje również aligned, zachowując całe powiększone pole filmu i wybrane tło poza ważnymi próbkami.

**Blocked by:** [08: Rejestracja Phase i pełny widok aligned](08-phase-registration.md), [14: Pierwszy film AVI: zakres, FPS i oba kodeki](14-original-avi-basic.md)

**Status:** ready-for-review

**Wykonawca:** Codex
**Baza przeglądu:** `903d00b6e21c9cbe2609ca151d09480c2551c754`

**Specyfikacja:** [Rejestracja i życie wyniku aligned](../../issues/03-registration.md#answer), [Opcje filmu AVI](../../issues/05-avi-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Okno oferuje original/aligned i domyślnie aktualny widok; brak kompletnego aligned uniemożliwia wybór tego wariantu.
- [x] Wybrany zakres i usunięcie klatki nie przeliczają położenia ani nie zmniejszają pełnego obszaru istniejącego aligned.
- [x] Maska, proporcje, gamma, dostępny kontrast i tło korzystają z gotowego wyniku; zapis nie uruchamia rejestracji ani nowej interpolacji pomiaru.
- [x] Gamma nie zmienia tła, kontrast nie obejmuje brakujących próbek. Wspólna skala daje właściwe proporcje; przy niewspólnej używane są piksele.
- [x] Oba kodeki, zakres i FPS działają z aligned. Eksport zachowuje spójny wynik nawet gdy później rozpocznie się nowa operacja zgodnie z dopuszczonym stanem UI.
- [x] Jeśli opcjonalne opisy są już dostępne, stosują geometrię wybranego aligned. Ich implementacja nie jest warunkiem rozpoczęcia tego etapu.

## Testy automatyczne

- Geometria/padding i maska po usunięciu odniesienia/skrajnej klatki, podzbiór bez zmniejszania obszaru.
- Rzeczywisty odczyt obu kodeków dla aligned i niezmienność wyniku rejestracji przez eksport.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Eksport AVI → rzeczywiście odczytany film** — Sprawdza liczbę, kolejność, FPS, rozmiar i raster kodeka oraz błędy zapisu; nie zastępuje odtworzenia w VLC.
- **Klatka i opcje prezentacji → raster filmu** — Sprawdza gamma, kontrast, maskę, geometrię i opisy; nie sprawdza kodeka ani VLC.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Zarejestruj serię, usuń klatkę skrajną i wyeksportuj krótki zakres aligned w obu kodekach.
2. Odtwórz w VLC: rozmiar i umieszczenie pola mają odpowiadać pełnemu wynikowi, bez kadrowania do eksportowanego podzbioru.
3. Sprawdź gamma i tło brakujących próbek; jeżeli dodatkowe wybory prezentacji są już dostępne, porównaj również ich działanie na aligned.
4. Porównaj eksport original/aligned i sprawdź anulowanie nowej próby zapisu.

## Współpraca z integracją

Wspólne API geometrii powinno być używane w uzgodnionej orientacji; potrzebne korekty adaptera/materializatora prowadzić z integracją.

## Wynik implementacji — 2026-10-26

Implementacja `ecc8663`, poprawka kalibracji zakresu `883b3ae`; baza `903d00b`.
[Instrukcja ręczna](../../aligned-avi-manual.md),
[przegląd Standards/Spec](../review-16-aligned-avi.md).
Kryteria potwierdzają testy automatyczne i próby techniczne; ręczna akceptacja
użytkownika pozostaje do wykonania, stąd **ready-for-review**.

- Wybór original/aligned domyślnie odpowiada podglądowi; dostępny jest tylko
  kompletny wynik zgodny z bieżącą serią. Obie wersje mają wspólne opcje AVI.
- Obszar i tablice aligned nie są przeliczane ani kopiowane. Per-frame
  kalibracja oryginałów pozwala wybrać fizyczne proporcje jednolitego zakresu,
  także po rejestracji mieszanej serii. Podgląd pozostaje bez zmian.
- Po poprawce: **86 passed**, 19.58 s (AVI i powiązane MPP);
  **28 passed**, 7.24 s (GUI Qt xcb). Mypy strict: **32 pliki, 0 błędów**.
- Pełne repo raz po implementacji, przed poprawką z przeglądu:
  **2120 passed, 14 failed, 16 skipped**, 266.40 s. Identyczne 14 błędów
  MolTrack/NanoTrack co w tickecie 15; po poprawce ponowiono zestawy właściwe
  dla zmiany. Nie deklarujemy zaliczenia całego repozytorium.
- VLC odtworzył 10 filmów w obu kodekach; dwa filmy mieszanego wzorca
  sprawdzono ponownie po poprawce kalibracji. Bez błędów, obraz i EOF.
- Rzeczywisty eksport aligned po Phase 256 × 512 × 512 anulowany przez GUI
  podczas kodowania: poprzedni AVI identyczny bajtowo. To próba automatyczna.
- Przeglądy obu osi: bez otwartych uwag. Największy zmieniony plik kodu:
  `main_window.py`, 803 linie. Brak zmian wspólnych modułów i zależności.
- Opisy filmu należą do ticketu 17; nie są jeszcze dostępne. Odbiór Windows
  i końcowe odbiory platform pozostają w ticketach 20–21.
