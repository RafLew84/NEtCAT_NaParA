# 08: Rejestracja Phase i pełny widok aligned

**What to build:** Użytkownik rejestruje bieżącą serię metodą Phase, ogląda pełny powiększony wynik i może wracać do original, ponawiać oraz anulować obliczenia.

**Blocked by:** [07: Usuwanie klatek z zachowaniem czasu i pochodzenia](07-frame-deletion.md)

**Status:** done

**Wykonawca:** Codex, `viewer/start`.

**Baza code-review:** `1dc159ee48341b2180cea47947a3fb38d59dd0c6`.

**Specyfikacja:** [Rejestracja i życie wyniku aligned](../../issues/03-registration.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Phase dopasowuje sąsiednie oryginały i sumuje przesunięcia od pierwszej klatki bieżącej serii; pojedyncza klatka ma wynik zerowy.
- [x] Operacja zatrzymuje Play, pokazuje postęp/Anuluj i blokuje zmianę serii. W trakcie dostępne są wybór klatki, zoom/gamma i dotychczasowy podgląd.
- [x] Wynik obejmuje cały powiększony obszar, liniowo interpolowane próbki i NaN poza pomiarem. Osobno przechowuje maskę oraz prostokąt i położenie oryginalnej klatki.
- [x] Po pełnym sukcesie pokazuje aligned aktualnie oglądanej klatki, dopasowuje nowy obszar i zachowuje gamma. Original/aligned pamiętają osobne ustawienia zoomu.
- [x] Błąd lub anulowanie, także podczas budowy aligned, zachowuje poprzedni kompletny wynik. Niska pewność z kompletnym wynikiem jest widoczna; nie jest automatycznie odrzucana.
- [x] Usunięcie klatki, także odniesienia/skrajnej, zachowuje gotowe aligned pozostałych, obszar i historyczne odniesienie; dopiero nowa rejestracja może je zmienić.
- [x] Różne skale/kanały nie blokują rejestracji w pikselach. Przy niewspólnej kalibracji aligned używa pikseli; wejście z NaN daje czytelną odmowę obecnego backendu.
- [x] Znaki XY, kumulacja, geometria i niezależność od gamma/zoomu są sprawdzone na wzorcu; nie stroić algorytmu dla trudnych pomiarów.

## Testy automatyczne

- Kontrolowane przesunięcia i subpiksele: maska ≠ pole źródła, znak/kumulacja, pełny obszar oraz niemutowanie oryginałów.
- Cykl zadania, błąd materializacji, anulowanie i atomowa podmiana wyniku; usuwanie historycznego odniesienia.
- Integracja z istniejącym Phase i jego progami, odrębnie od testów z kontrolowanym wynikiem.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Rejestracja oryginałów → kompletny wynik** — Sprawdza wynik, status, anulowanie i geometrię aligned; nie stanowi uniwersalnej oceny skuteczności na nowych pomiarach.
- **Działanie na serii → obserwowalny stan** — Sprawdza wybór, odtwarzanie, usuwanie i transakcyjną podmianę; nie mierzy fizycznej płynności ekranu.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Wczytaj przygotowaną serię z rozpoznawalnym przesunięciem; ustaw gamma/zoom i uruchom Phase.
2. Po sukcesie przełącz original/aligned; sprawdź pełny obszar, szachownicę i obrys oraz zachowanie osobnego zoomu.
3. Usuń pierwszą i skrajnie przesuniętą klatkę; pozostałe obrazy nie przemieszczają się i obszar się nie kurczy.
4. Ponów rejestrację, zmień oglądaną klatkę w trakcie, a następnie sprawdź anulowanie kolejnej próby. Stary kompletny wynik pozostaje.
5. Sprawdź serię bez tekstury/niepewny wynik i wejście z NaN; interfejs pokazuje właściwą przyczynę lub oznaczenie jakości.

## Współpraca z integracją

Runner, bezpieczne punkty anulowania i materializator mogą wymagać wspólnych zmian koordynowanych przez integrację. Interfejs Viewera ma zachowywać stary wynik niezależnie od dotychczasowego zachowania NanoTrack/MolTrack.


## Wynik implementacji — 2026-10-23

Działa Phase w tle, postęp/anulowanie i atomowa podmiana kompletnego aligned.
Original/aligned mają osobny kadr i wspólną gamma. Obrys pochodzi z pola
źródłowego; maska ważnych próbek jest osobna. Usuwanie zachowuje historyczny
układ, a nowa rejestracja wyznacza go z pozostałych oryginałów. Niepewność
jest oznaczana także po jej odziedziczeniu. Wspólne moduły pozostają bez zmian.

123 testy Viewera i mypy strict (17 plików) przechodzą. Automatyczna próba
Qt xcb na wzorcach oraz lokalnym MOVIE_3.MPP przeszła; oceniono zrzuty.
[Instrukcja manualna](../../phase-registration-manual.md). Commit implementacji:
`2fea452`. [Przegląd Standards/Spec](../review-08-phase-registration.md):
0 usterek kodu; jedną drobną uwagę do instrukcji manualnej poprawiono.

Pełny zestaw repo: **1909 passed, 14 failed, 14 skipped**, 222.93 s.
Wszystkie 14 niepowodzeń występowało przy tickecie 07; brak nowych
identyfikatorów błędów i błędów zbierania. Nie jest to zielony odbiór repo.
Największy zmieniony plik kodu ma 590 linii. Szczegóły: [przekazanie](../../handoff.md).
Użytkownik potwierdził ręczny odbiór 2026-10-23: „testy manualne ok”.
Ticket ma status `done`. Nie wskazano systemu; potwierdzenie nie zamyka
odrębnych odbiorów platform. Aktualizacja dotyczy dokumentacji;
testów automatycznych nie ponawiano.
