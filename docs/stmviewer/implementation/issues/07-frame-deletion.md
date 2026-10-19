# 07: Usuwanie klatek z zachowaniem czasu i pochodzenia

**What to build:** Użytkownik usuwa wybraną klatkę z otwartej serii i nadal widzi poprawny obraz, numer, czas oraz pochodzenie pozostałych klatek.

**Blocked by:** [04: Otwarcie filmu MPP z czasami i pochodzeniem](04-mpp-series.md), [06: Play, Pause i tempo odtwarzania](06-playback.md)

**Status:** ready-for-agent

**Specyfikacja:** [Seria wejściowa i usuwanie klatek](../../issues/01-frame-series.md#answer), [Podgląd, gamma i odtwarzanie serii](../../issues/02-preview-playback.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Usunięcie zatrzymuje Play i wybiera następną klatkę, a dla ostatniej poprzednią; usunięcie jedynej zostawia pusty program.
- [ ] Pozycje 1…N aktualizują się, lecz pochodzenie i parametry każdej pozostałej klatki pozostają związane z tym samym obrazem.
- [ ] Czasy zachowują wartości i przerwy, także gdy część jest nieznana. Usunięcie środka [10,20,35] s pozostawia [10,35] s.
- [ ] Źródła pozostają bez zmian na dysku. Nie ma odwracania kolejności ani cofania usunięcia.
- [ ] Kontrolki i miniatury nie wskazują usuniętej klatki. Nowa poprawna seria działa także po opróżnieniu programu.

## Testy automatyczne

- Usunięcie środka/ostatniej/jedynej, czasy z brakami, per-klatkowe metadane i zatrzymanie Play.
- Niezmienność plików źródłowych i poprawne przejście pusty → nowa seria.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Działanie na serii → obserwowalny stan** — Sprawdza wybór, odtwarzanie, usuwanie i transakcyjną podmianę; nie mierzy fizycznej płynności ekranu.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Wczytaj trzyklatkowy MPP z rozpoznawalnymi obrazami i czasami, rozpocznij Play i usuń środkową klatkę.
2. Sprawdź Pause, kolejność, numer 2/2 oraz źródłowy numer i czas trzeciej klatki.
3. Usuń ostatnią, a następnie jedyną pozostałą klatkę; sprawdź wybór poprzedniej i stan pusty.
4. Otwórz ponownie źródło; wszystkie pierwotne klatki nadal istnieją. Wczytaj nową serię i sprawdź kontrolki.

## Współpraca z integracją

Nie kopiować modelu usuwania MolTrack, który nie synchronizuje czasów i odrzuca wynik rejestracji. Ewentualne zmiany wspólnych modeli uzgodnić z integracją, zachowując kontrakty ich odbiorców.
