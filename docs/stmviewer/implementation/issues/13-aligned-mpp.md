# 13: Zapis aligned do MPP z pełną geometrią

**What to build:** Użytkownik wybiera original albo aligned przy zapisie MPP i po ponownym otwarciu aligned odzyskuje pełny obszar, braki oraz położenie oryginalnego pola każdej klatki.

**Blocked by:** [08: Rejestracja Phase i pełny widok aligned](08-phase-registration.md), [12: Zapis original do MPP i ponowne otwarcie](12-original-mpp.md)

**Status:** in-progress

**Wykonawca:** Codex, `viewer/start`, 2026-10-26.
**Baza code-review:** `6ab0837`.

**Specyfikacja:** [Rejestracja i życie wyniku aligned](../../issues/03-registration.md#answer), [Zapis MPP z wartościami i metadanymi](../../issues/04-mpp-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Okno zapisu oferuje original/aligned i domyślnie aktualnie oglądaną wersję; aligned wymaga kompletnego wyniku.
- [ ] Zapisuje gotowe próbki aligned bez ponownej interpolacji, przycinania i zastępowania NaN; zachowuje dokładne liczby i maskę po odczycie.
- [ ] Dodatek opisuje cały obszar, przesunięcia XY, pierwotne wymiary, prostokąty źródeł i historyczne odniesienie, osobno od ważności próbek.
- [ ] Zapis po usunięciu odniesienia lub skrajnej klatki zachowuje geometrię pozostałego wyniku i nie zmniejsza obszaru.
- [ ] Ponownie otwarty plik zachowuje historię i nie udaje odzyskanych oryginałów sprzed interpolacji; jego piksele są wejściem bieżącej serii.
- [ ] O nowej rejestracji decydują wczytane wartości, nie etykieta aligned. Obecne backendy odmawiają wejścia z NaN z czytelnym powodem.
- [ ] Oba warianty zachowują atomową podmianę po sukcesie, bez utraty poprzedniego zapisu przy błędzie/anulowaniu.

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
