# 12: Zapis original do MPP i ponowne otwarcie

**What to build:** Użytkownik zapisuje wszystkie pozostałe klatki original jako MPP z metadanymi, zamyka program i otwiera wynik bez utraty wartości, czasów oraz pochodzenia.

**Blocked by:** [03: S94 i mieszane serie STP/S94](03-s94-series.md), [07: Usuwanie klatek z zachowaniem czasu i pochodzenia](07-frame-deletion.md), [11: Otwarcie MPP z metadanymi towarzyszącymi](11-mpp-metadata-import.md)

**Status:** ready-for-review

**Wykonawca:** Codex, `viewer/start`, 2026-10-23.
**Baza code-review:** `7756c3d6e018ad1820f7400dc2d606b49d0975f2`.

**Specyfikacja:** [Zapis MPP z wartościami i metadanymi](../../issues/04-mpp-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Okno zapisu obejmuje całą bieżącą serię w jej kolejności, także jedną klatkę. Pusta seria nie podlega zapisowi; ten etap zapisuje original.
- [x] Film zachowuje float64 little endian, orientację, pełne wymiary oraz NaN niezależnie od gamma/zoomu. Skończone wartości po odczycie są dokładnie równe wartościom przekazanym do zapisu.
- [x] Towarzyszące wersjonowane metadane zachowują parametry każdej klatki, pochodzenie, czasy z przerwami/brakami i źródłowe nagłówki; są powiązane z treścią, kształtem i liczbą klatek MPP.
- [x] Różna skala/kanał/jednostka nie blokuje zapisu. Wspólny nagłówek nie udaje kalibracji pierwszej klatki dla całej serii.
- [x] Zapis ma postęp i anulowanie, używa spójnego stanu i plików tymczasowych; błąd/anulowanie zachowuje wcześniejsze pliki. Niedopasowanie po przerwaniu publikacji pary jest wykrywane.
- [x] Działają ścieżki STP → MPP, S94 → MPP i MPP → MPP oraz odczyt filmu przez dotychczasowe czytniki w zakresie informacji, które rozumieją. Nie wymaga się zgodności z WSxM.
- [x] Eksporter wytwarza parę zgodną z już działającym importerem dodatku; testy ponownego odczytu uzupełniają niezależne wzorce, aby wspólny błąd zapisu i odczytu nie maskował problemu.

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


## Wynik implementacji — 2026-10-23

Implementacja: `678269f`; poprawka po przeglądzie: `e24e560`.
Zapis przez przycisk, menu Plik i Ctrl+S obejmuje wszystkie pozostałe obrazy
original, także podczas oglądania aligned. Powstaje MPP + dodatek V1.
Gamma, zoom i proporcje podglądu nie zmieniają danych. Zapis działa w tle,
ma postęp, anulowanie i potwierdzenie zastąpienia obu plików; zachowuje
wcześniejszą parę przy zwykłym błędzie/anulowaniu.

- Testy Viewera: **214 passed, 2 skipped**, 21.78 s. Po poprawce przeglądu:
  **38 testów eksportu/importu metadanych zaliczonych**, 3.53 s, w tym nowy
  przypadek bardzo długiego tekstu UTF-8. Mypy strict: **23 pliki**, bez błędów.
- Pełne repo uruchomione raz: **2000 passed, 14 failed, 16 skipped**, 231.70 s.
  Lista 14 niepowodzeń MolTrack/NanoTrack jest identyczna z ticketem 11;
  brak nowych niepowodzeń. Szczegóły wykonania: [handoff](../../handoff.md).
- Automatyczna próba prawdziwego GUI Qt xcb z dialogami: MPP po usunięciu
  środkowej klatki, S94, MPP z różnymi metadanymi oraz lokalny MOVIE_3
  (17 × 256 × 256). Zapis i ponowne otwarcie poprawne; wartości dokładnie
  równe, źródła zachowały SHA-256. Obejrzano zrzuty.
- [Przegląd dwóch osi](../review-12-original-mpp.md): jedno P2 Spec i drobna
  heurystyka Standards poprawione i ponownie sprawdzone; 0 otwartych uwag.
- Największy zmieniony plik kodu: **751 linii**; limit 1500 zachowany.

[Instrukcja manualna](../../original-mpp-manual.md) zawiera dane, kroki,
generator większego wzorca i narzędzie dokładnego porównania. **Ręczny odbiór
użytkownika pozostaje do wykonania**, dlatego status to `ready-for-review`.
Próba xcb była sterowana skryptem. Windows 11 oraz dodatkowe WSxM nie były
sprawdzane w tym etapie. Eksport aligned pozostaje ticketem 13.

Starsze czytniki sprawdzono dla wartości, orientacji używanej przez ich
adaptery, wspólnej kalibracji i znanych czasów. Ich limit 1000 linii
nagłówka, brak obsługi JSON i nieznanej skali wymagają pracy integracji;
nie zmieniono wspólnego kodu ani konfiguracji.
