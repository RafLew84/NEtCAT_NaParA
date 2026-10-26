# 16: Film AVI z aligned i pełnym obszarem

**What to build:** Użytkownik eksportuje również aligned, zachowując całe powiększone pole filmu i wybrane tło poza ważnymi próbkami.

**Blocked by:** [08: Rejestracja Phase i pełny widok aligned](08-phase-registration.md), [14: Pierwszy film AVI: zakres, FPS i oba kodeki](14-original-avi-basic.md)

**Status:** in-progress

**Wykonawca:** Codex
**Baza przeglądu:** `903d00b6e21c9cbe2609ca151d09480c2551c754`

**Specyfikacja:** [Rejestracja i życie wyniku aligned](../../issues/03-registration.md#answer), [Opcje filmu AVI](../../issues/05-avi-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Okno oferuje original/aligned i domyślnie aktualny widok; brak kompletnego aligned uniemożliwia wybór tego wariantu.
- [ ] Wybrany zakres i usunięcie klatki nie przeliczają położenia ani nie zmniejszają pełnego obszaru istniejącego aligned.
- [ ] Maska, proporcje, gamma, dostępny kontrast i tło korzystają z gotowego wyniku; zapis nie uruchamia rejestracji ani nowej interpolacji pomiaru.
- [ ] Gamma nie zmienia tła, kontrast nie obejmuje brakujących próbek. Wspólna skala daje właściwe proporcje; przy niewspólnej używane są piksele.
- [ ] Oba kodeki, zakres i FPS działają z aligned. Eksport zachowuje spójny wynik nawet gdy później rozpocznie się nowa operacja zgodnie z dopuszczonym stanem UI.
- [ ] Jeśli opcjonalne opisy są już dostępne, stosują geometrię wybranego aligned. Ich implementacja nie jest warunkiem rozpoczęcia tego etapu.

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
