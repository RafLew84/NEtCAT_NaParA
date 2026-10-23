# 12: Zapis original do MPP i ponowne otwarcie

**What to build:** Użytkownik zapisuje wszystkie pozostałe klatki original jako MPP z metadanymi, zamyka program i otwiera wynik bez utraty wartości, czasów oraz pochodzenia.

**Blocked by:** [03: S94 i mieszane serie STP/S94](03-s94-series.md), [07: Usuwanie klatek z zachowaniem czasu i pochodzenia](07-frame-deletion.md), [11: Otwarcie MPP z metadanymi towarzyszącymi](11-mpp-metadata-import.md)

**Status:** in-progress

**Wykonawca:** Codex, `viewer/start`, 2026-10-23.
**Baza code-review:** `7756c3d6e018ad1820f7400dc2d606b49d0975f2`.

**Specyfikacja:** [Zapis MPP z wartościami i metadanymi](../../issues/04-mpp-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Okno zapisu obejmuje całą bieżącą serię w jej kolejności, także jedną klatkę. Pusta seria nie podlega zapisowi; ten etap zapisuje original.
- [ ] Film zachowuje float64 little endian, orientację, pełne wymiary oraz NaN niezależnie od gamma/zoomu. Skończone wartości po odczycie są dokładnie równe wartościom przekazanym do zapisu.
- [ ] Towarzyszące wersjonowane metadane zachowują parametry każdej klatki, pochodzenie, czasy z przerwami/brakami i źródłowe nagłówki; są powiązane z treścią, kształtem i liczbą klatek MPP.
- [ ] Różna skala/kanał/jednostka nie blokuje zapisu. Wspólny nagłówek nie udaje kalibracji pierwszej klatki dla całej serii.
- [ ] Zapis ma postęp i anulowanie, używa spójnego stanu i plików tymczasowych; błąd/anulowanie zachowuje wcześniejsze pliki. Niedopasowanie po przerwaniu publikacji pary jest wykrywane.
- [ ] Działają ścieżki STP → MPP, S94 → MPP i MPP → MPP oraz odczyt filmu przez dotychczasowe czytniki w zakresie informacji, które rozumieją. Nie wymaga się zgodności z WSxM.
- [ ] Eksporter wytwarza parę zgodną z już działającym importerem dodatku; testy ponownego odczytu uzupełniają niezależne wzorce, aby wspólny błąd zapisu i odczytu nie maskował problemu.

## Testy automatyczne

- Dokładny round-trip wartości i NaN wszystkich trzech ścieżek, metadane/kalibracja i czasy po usunięciu.
- Weryfikacja powiązania dodatku, długi nagłówek, błędy/anulowanie oraz przerwanie między publikacjami dwóch plików.
- Kompatybilność z dotychczasowymi czytnikami i kontrola braku normalizacji/obrotu przy ponownym odczycie.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Zapis pary MPP i ponowny odczyt** — Sprawdza wartości, metadane i bezpieczeństwo plików; sam odczyt własnym importerem nie dowodzi zgodności innych czytników.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Otwórz mały MPP ze znanymi czasami, usuń środek, zmień gamma i zapisz original. Zamknij/otwórz wynik; sprawdź obrazy, liczbę, czasy i pochodzenie.
2. Powtórz zapis dla serii STP/S94 o różnych metadanych. Obejrzyj wynik i raport porównania wartości.
3. Przenieś parę plików do innego katalogu i otwórz. Następnie na kopiach sprawdź brak dodatku oraz dodatek innego filmu.
4. Anuluj dłuższy zapis przy istniejącym wyniku, a w kontrolowanym przypadku wywołaj błąd zapisu. Poprzedni film nadal się otwiera.

## Współpraca z integracją

Wspólne korekty orientacji/odczytu i metadanych koordynuje integracja. Własny zapis i dodatek mogą pozostać modułami Viewera; rozszerzenie wspólnych API musi zachować odbiorców.
