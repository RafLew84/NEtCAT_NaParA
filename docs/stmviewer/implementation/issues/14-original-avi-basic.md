# 14: Pierwszy film AVI: zakres, FPS i oba kodeki

**What to build:** Użytkownik zapisuje pełne obrazy original jako MJPG lub FFV1, wybiera klatki i FPS, a gotowy film odtwarza w VLC.

**Blocked by:** [07: Usuwanie klatek z zachowaniem czasu i pochodzenia](07-frame-deletion.md)

**Status:** ready-for-review

**Wykonawca:** Codex
**Baza przeglądu:** `60785df41de0d5f20517e53cdf4abb0878df6e3c`

**Specyfikacja:** [Opcje filmu AVI](../../issues/05-avi-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Okno zapisuje całą serię lub zakres od–do włącznie w bieżącej numeracji; FPS 1–30 jest domyślnie kopiowane z Play, a kodek to MJPG domyślnie lub FFV1.
- [x] Każda wybrana klatka trafia raz do filmu; jedna klatka jest poprawna, pusta seria nie. FPS nie zmienia Play ani czasu pomiaru.
- [x] Pierwszy wariant stosuje zatwierdzone ustawienia domyślne: gamma podglądu, kontrast osobno dla klatki, czarne tło braków i czysty obraz. Dodatkowe wybory prezentacji mają osobny etap.
- [x] Renderowanie używa wyłącznie ważnych próbek i obsługuje stały obraz/brak próbek. Film obejmuje pełny obraz niezależnie od okna/zoomu.
- [x] Wspólna wiarygodna skala X/Y daje proporcje fizyczne, inaczej proporcje pikselowe. Nieparzyste wymiary są dopełnione z prawej/dołu, bez utraty krawędzi.
- [x] Przed startem widać liczbę klatek, rozmiar i czas filmu. Wybrany kodek jest sprawdzany bez automatycznej zamiany lub pobierania.
- [x] Postęp/anulowanie, spójny zestaw danych/opcji i zapis tymczasowy chronią poprzedni wynik przy błędzie. FFV1 zachowuje dokładnie raster uint8, a MJPG jest stratny.
- [x] Oba filmy są faktycznie odczytane i odtworzone w VLC na dostępnym stanowisku; brak zewnętrznej próby jest raportowany jawnie.

## Testy automatyczne

- Renderer ustawień domyślnych: ważne próbki, gamma, proporcje i pełne krawędzie, z niezależnymi małymi wzorcami.
- Publiczny eksport i rzeczywisty odczyt MJPG/FFV1: zakres, liczba klatek, FPS, rozmiar, dokładność FFV1 oraz błąd/anulowanie.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Klatka i opcje prezentacji → raster filmu** — Sprawdza gamma, kontrast, maskę, geometrię i opisy; nie sprawdza kodeka ani VLC.
- **Eksport AVI → rzeczywiście odczytany film** — Sprawdza liczbę, kolejność, FPS, rozmiar i raster kodeka oraz błędy zapisu; nie zastępuje odtworzenia w VLC.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Zapisz oryginalną serię i krótki zakres w obu kodekach, z FPS innym niż Play. Otwórz wyniki w VLC.
2. Zmień gamma podglądu, rozmiar okna i zoom; film ma przejąć gamma, ale nadal obejmować pełne obrazy.
3. Sprawdź wzorzec 65 × 49 (film 66 × 50), anizotropię oraz klatkę bez ważnych próbek z czarnym tłem.
4. Anuluj dłuższy zapis przy istniejącym filmie; dotychczasowy plik nadal się otwiera.

## Współpraca z integracją

Zależności OpenCV/FFmpeg i konfigurację główną koordynuje integracja. Renderer i zapis nie mogą polegać na zrzucie wspólnego widgetu, który zastępuje NaN medianą.

## Wynik implementacji — 2026-10-26

Commity: `959c5c6`, `a9cf6b4`; baza `60785df`.
[Instrukcja i gotowe dane manualne](../../original-avi-manual.md),
[przegląd Standards/Spec](../review-14-original-avi.md).
Kryteria powyżej potwierdzono implementacją i próbami automatycznymi oraz VLC;
ręczna akceptacja użytkownika pozostaje do wykonania, stąd `ready-for-review`.

- 62 testy zakresu po przeglądzie: passed. Qt xcb: 13 passed.
- Mypy: 31 plików bez błędów; największy zmieniony plik kodu: 802 linie.
- Pełne repo: 2056 passed, 14 failed, 16 skipped, 239.70 s. Dokładnie te same
  14 niepowodzeń MolTrack/NanoTrack co przed zmianą; brak nowych identyfikatorów.
- VLC 3.0.20/Ubuntu/Xvfb: sześć AVI, oba kodeki, rzeczywisty obraz i EOF,
  bez błędów. Windows 11 pozostaje osobnym odbiorem.
- Test małego MJPG wykrył natywne przerwanie procesu przy 4 × 4. Próba kodeka
  jest izolowana w procesie potomnym, a błąd nie zamyka Viewera i nie zmienia
  istniejącego filmu. Bez zastępowania kodeka lub pobierania.
- Użyto netcat, lokalnych danych i OpenCV 4.11.0. Wspólnego kodu ani głównej
  konfiguracji nie zmieniono; zależności AVI opisuje lokalny requirements-avi.txt.
