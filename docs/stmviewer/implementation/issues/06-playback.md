# 06: Play, Pause i tempo odtwarzania

**What to build:** Użytkownik odtwarza serię, steruje tempem i pętlą oraz zatrzymuje się na wybranej klatce bez przeskoków w kolejności.

**Blocked by:** [05: Zoom, gamma i brakujące próbki](05-preview-controls.md)

**Status:** in-progress

**Wykonawca:** Codex, `viewer/start`.

**Baza code-review:** `0d57200d4d606292f95fe56cca831c78e437673f`.

**Specyfikacja:** [Podgląd, gamma i odtwarzanie serii](../../issues/02-preview-playback.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Play domyślnie 5 kl./s, wybór 1/2/5/10/20/30, pętla domyślnie wyłączona; na końcu Pause, a Play na ostatniej zaczyna od pierwszej.
- [x] Ręczny wybór zatrzymuje Play. Pusta seria i pojedyncza klatka nie uruchamiają Play. Udany import resetuje widok; nieudany zachowuje poprzedni stan.
- [x] Przy przeciążeniu odtwarzanie zwalnia bez pomijania klatek. Zmiana gamma/zoomu/tempa działa podczas Play; mierzyć rzeczywiste zmiany obrazu.
- [ ] Na dostępnej serii typowej cel odbioru to 5 kl./s oraz reakcja wyboru/Pause do 250 ms w co najmniej 95% prób. Pełne sprawdzenie dużej serii ma osobny etap.
- [x] Play współpracuje z istniejącą gamma/zoomem, miniaturami i ręcznym wyborem. Po nieudanym imporcie poprzedni stan odtwarzania/podglądu pozostaje zgodny z kontraktem.
- [x] Automatyczny test liczy faktycznie wyświetlane kolejne klatki; pomiar płynności jest odrębny od samego timera.

## Testy automatyczne

- Publiczne akcje odtwarzania: Pause, koniec/pętla, wznowienie, ręczny wybór i brak pomijania klatek.
- Integracja kontrolek z rzeczywiście pokazywaną klatką i oddzielny pomiar reakcji/płynności.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Działanie na serii → obserwowalny stan** — Sprawdza wybór, odtwarzanie, usuwanie i transakcyjną podmianę; nie mierzy fizycznej płynności ekranu.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Odtwórz serię bez pętli do końca, uruchom Play na ostatniej, potem sprawdź pętlę i różne tempa.
2. Podczas Play wybierz miniaturę, suwak i numer; odtwarzanie zatrzymuje się na wskazanej klatce.
3. Podczas Play zmień gamma, zoom i tempo; stan serii oraz kolejność pozostają prawidłowe.
4. Sprawdź pojedynczą klatkę, przeciążenie przy większym FPS oraz krótką próbę 5 kl./s i reakcji Pause.

## Współpraca z integracją

Odtwarzanie jest funkcją Viewera. Ewentualne wspólne zmiany widgetu uzgodnić z integracją; nie przenosić całego UI trackingu/ROI.

## Wynik implementacji — 2026-10-21

Działają Play/Pause, domyślne 5 kl./s, sześć temp i pętla. Film pokazuje
klatki po kolei, kończy się na ostatniej bez pętli, a Play na końcu wraca
do pierwszej. Ręczna nawigacja zatrzymuje odtwarzanie, także przy wybraniu
bieżącej miniatury/uchwytu suwaka. Gamma/zoom/przesunięcie i tempo działają
podczas Play. Błąd i anulowanie importu pozostawiają bieżącą starą serię;
sukces zatrzymuje film i resetuje podgląd. FPS i pętla pozostają ustawieniami okna.

93 testy Viewera i mypy strict (15 plików) przechodzą. Test przeciążenia
obserwuje rzeczywiste malowanie i obrazy, nie sygnały timera.
[Instrukcja próby ręcznej i pomiaru](../../playback-manual.md).
Końcowy pomiar, pełny zestaw repo i przegląd są w toku. Ręczny odbiór
użytkownika i Windows pozostają do wykonania.
