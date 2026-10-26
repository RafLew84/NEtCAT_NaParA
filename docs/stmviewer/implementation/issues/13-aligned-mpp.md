# 13: Zapis aligned do MPP z pełną geometrią

**What to build:** Użytkownik wybiera original albo aligned przy zapisie MPP i po ponownym otwarciu aligned odzyskuje pełny obszar, braki oraz położenie oryginalnego pola każdej klatki.

**Blocked by:** [08: Rejestracja Phase i pełny widok aligned](08-phase-registration.md), [12: Zapis original do MPP i ponowne otwarcie](12-original-mpp.md)

**Status:** ready-for-review

**Wykonawca:** Codex, `viewer/start`, 2026-10-26.
**Baza code-review:** `6ab0837`.

**Specyfikacja:** [Rejestracja i życie wyniku aligned](../../issues/03-registration.md#answer), [Zapis MPP z wartościami i metadanymi](../../issues/04-mpp-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Okno zapisu oferuje original/aligned i domyślnie aktualnie oglądaną wersję; aligned wymaga kompletnego wyniku.
- [x] Zapisuje gotowe próbki aligned bez ponownej interpolacji, przycinania i zastępowania NaN; zachowuje dokładne liczby i maskę po odczycie.
- [x] Dodatek opisuje cały obszar, przesunięcia XY, pierwotne wymiary, prostokąty źródeł i historyczne odniesienie, osobno od ważności próbek.
- [x] Zapis po usunięciu odniesienia lub skrajnej klatki zachowuje geometrię pozostałego wyniku i nie zmniejsza obszaru.
- [x] Ponownie otwarty plik zachowuje historię i nie udaje odzyskanych oryginałów sprzed interpolacji; jego piksele są wejściem bieżącej serii.
- [x] O nowej rejestracji decydują wczytane wartości, nie etykieta aligned. Obecne backendy odmawiają wejścia z NaN z czytelnym powodem.
- [x] Oba warianty zachowują atomową podmianę po sukcesie, bez utraty poprzedniego zapisu przy błędzie/anulowaniu.

## Testy automatyczne

- Round-trip subpikseli, NaN, prostokątów i historycznego odniesienia; maska i pole źródła sprawdzane osobno.
- Zapis po usunięciu skrajnej klatki i ponownym dopasowaniu, odrębność historii i bieżącego wejścia.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Zapis pary MPP i ponowny odczyt** — Sprawdza wartości, metadane i bezpieczeństwo plików; sam odczyt własnym importerem nie dowodzi zgodności innych czytników.
- **Rejestracja oryginałów → kompletny wynik** — Sprawdza wynik, status, anulowanie i geometrię aligned; nie stanowi uniwersalnej oceny skuteczności na nowych pomiarach.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Zarejestruj wzorzec z przesunięciem subpikselowym, usuń odniesienie i zapisz aligned.
2. Otwórz zapis ponownie; sprawdź rozmiar obszaru, szachownicę, obrys oraz źródłowe dane klatek i raport porównania wartości.
3. Porównaj zapis original i aligned wykonany z tej samej serii; gamma/zoom nie zmienia danych.
4. Spróbuj zarejestrować ponownie plik z NaN; oczekuj wyjaśnienia ograniczenia danych, bez udawania odzyskania pierwotnych obrazów.

## Współpraca z integracją

Adapter materializatora i ewentualne wspólne typy geometrii uzgodnić z integracją. Nie rekonstruować historii z obwiedni skończonych pikseli.


## Wynik implementacji — 2026-10-26

Commity: `ec21f6a` (funkcja) i `35858f1` (poprawki przeglądu).
W oknie zapisu pole **Typ pliku** wybiera MPP original/aligned, domyślnie
aktualny widok. Aligned zapisuje gotowe próbki i dodatek V2 z geometrią
oraz historią; zwykły original pozostaje przy V1. Po odczycie nie powstają
pozorne wcześniejsze oryginały. [Kontrakt V1/V2](../../mpp-metadata-format.md).

- Końcowe testy Viewera: **231 passed, 2 skipped**, 23.95 s; pominięcia
  dotyczą opcjonalnych prób rzeczywistych wag Deep Matcher.
- Mypy strict: **25 plików**, bez błędów. Największy zmieniony plik kodu:
  **767 linii**. `git diff --check` poprawny.
- Pełny zestaw repo przed poprawką przeglądu: **2016 passed, 14 failed,
  16 skipped**, 239.42 s. Niepowodzenia dotyczą MolTrack/NanoTrack.
  Spośród nich 13 odtworzono na czystym archiwum bazy `6ab0837`;
  test NanoTrack `test_edge_correction_and_resume_replace_suffix` przeszedł
  osobno zarówno na bazie, jak i bieżącym kodzie. Pełnego repo nie oznaczamy
  jako zaliczonego. Po poprawce ponowiono cały zestaw Viewera.
- Próba automatyczna rzeczywistego Qt xcb: wybór aligned w dialogu,
  rejestracja subpikselowa, usunięcie odniesienia, zapis i otwarcie z obrysem
  64 × 64 na obszarze 68 × 67. Zrzuty ocenione wizualnie.
- Lokalny `data/MOVIE_3.MPP`: rejestracja Phase, usunięcie odniesienia,
  16 klatek 398 × 398 zapisanych i odczytanych z dokładnymi próbkami i geometrią.
- NaPara/NanoTrack/MolTrack odczytują wartości i NaN nowego eksportu;
  zachowanie V1 i natywnego nagłówka WSxM objęte regresjami.
- [Code-review Standards/Spec](../review-13-aligned-mpp.md): obie uwagi
  poprawione i ponownie sprawdzone; brak otwartych ustaleń.

**Ręczny odbiór użytkownika: oczekuje.** [Instrukcja GUI i porównania wartości](../../aligned-mpp-manual.md).
Automatyczne Qt offscreen/xcb nie zastępuje tego odbioru ani próby Windows 11.
WSxM dla NaN/aligned nie sprawdzano w tym etapie; jest dodatkowym testem.
Pełne wyniki i lokalizacje logów: [handoff](../../handoff.md).

### Dodatkowa diagnoza WSxM — 2026-10-26

[Sprawdzenie MOVIE_3-aligned.mpp](../../wsxm-aligned-investigation.md)
potwierdziło dokładne dane Optical Flow we wszystkich 17 klatkach oraz
problem obsługi NaN w WSxM pod Wine. Identyczny nagłówek i dane skończone
dają obraz po wypełnieniu wyłącznie braków. Przygotowano osobną lokalną
kopię podglądową, bez zmiany eksportera i kontraktu zachowania NaN.
Status pozostaje ready-for-review; nie jest to potwierdzenie odbioru ręcznego.

Po diagnozie użytkownik zlecił [poprawkę zgodności WSxM](13-wsxm-compatibility-fix.md).
Domyślny wariant GUI przechowuje braki w dodatku V3; wariant NaN nadal
spełnia wcześniejszy kontrakt bezpośredniego zapisu braków w MPP.

Następne uproszczenie użytkownika: [biały dodatkowy obszar i tylko original/aligned](13-white-background.md).
GUI używa teraz jednego zapisu z jasnym tłem i odtwarzaniem braków przez V3.
