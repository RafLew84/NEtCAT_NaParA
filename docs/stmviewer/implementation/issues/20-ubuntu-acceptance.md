# 20: Odbiór programu na Ubuntu 24.04

**What to build:** Użytkownik odtwarza środowisko na Ubuntu 24.04 i przechodzi pełny scenariusz GUI wraz z odczytem MPP oraz odtwarzaniem obu AVI w VLC.

**Blocked by:** [09: Pozostałe metody rejestracji CPU](09-cpu-registration-methods.md), [10: Deep Matcher z lokalnymi wagami](10-deep-matcher.md), [19: Duże eksporty i wspólna praca funkcji](19-large-exports.md)

**Status:** ready-for-agent

**Specyfikacja:** [Seria wejściowa i usuwanie klatek](../../issues/01-frame-series.md#answer), [Podgląd, gamma i odtwarzanie serii](../../issues/02-preview-playback.md#answer), [Rejestracja i życie wyniku aligned](../../issues/03-registration.md#answer), [Zapis MPP z wartościami i metadanymi](../../issues/04-mpp-export.md#answer), [Opcje filmu AVI](../../issues/05-avi-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Środowisko Python 3.12 jest odtwarzalne na Ubuntu 24.04; zapisano wersje zależności, kodeków, VLC, sterownika oraz dostępność metod i wag.
- [ ] Na tym systemie wykonano pełny uzgodniony scenariusz GUI na wspólnym manifeście danych: import, podgląd/usuwanie, rejestracja, MPP i AVI.
- [ ] Wymagane testy kontraktów i odbiorców przechodzą. Oba AVI rzeczywiście odtwarzają się w VLC, a MPP zachowuje liczby/metadane.
- [ ] Potwierdzono duży zestaw i kryteria płynności na udokumentowanym sprzęcie: 16 GB wolnego RAM, SSD i NVIDIA/CUDA z minimum 8 GB VRAM.
- [ ] Sprawdzono błąd/anulowanie i niedostępne metody, a przy dostępnych wagach także rzeczywisty Deep Matcher. Atrapa nie zastępuje dowodu modelu/CUDA.
- [ ] Raport rozróżnia zaliczone/niezaliczone/niewykonane/nie dotyczy. Brak tego systemu, danych lub VLC nie jest zaliczeniem ticketu.
- [ ] Znalezione błędy platformowe są poprawione i sprawdzone. Wspólna poprawka wymaga ponownego sprawdzenia dotkniętego zachowania także na drugim systemie.
- [ ] WSxM jest dodatkowy; strojenie skuteczności algorytmów nie jest warunkiem. Raport zawiera commit, uruchomienie, wyniki, ograniczenia i kontrolę długości plików kodu.
- [ ] Pełna pierwsza wersja jest odebrana dopiero po zaliczeniu obu ticketów platformowych na zgodnym zintegrowanym zestawie zmian.

## Testy automatyczne

- Pełny zestaw i testy odbiorców na Ubuntu 24.04 oraz rzeczywiste formaty, kodeki i zasoby; ręczne GUI raportowane osobno.
- Test regresji poprawianego błędu w odpowiedniej zatwierdzonej granicy, bez dopisywania testów szczegółów implementacji.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Otwarcie plików → seria lub błąd** — Sprawdza dekodowanie, orientację i metadane przez publiczny import; nie dowodzi poprawnego malowania obrazu na ekranie.
- **Zapis pary MPP i ponowny odczyt** — Sprawdza wartości, metadane i bezpieczeństwo plików; sam odczyt własnym importerem nie dowodzi zgodności innych czytników.
- **Eksport AVI → rzeczywiście odczytany film** — Sprawdza liczbę, kolejność, FPS, rozmiar i raster kodeka oraz błędy zapisu; nie zastępuje odtworzenia w VLC.
- **Pełny przebieg użytkownika → pomiar zasobów** — Sprawdza płynność, pamięć i czas na wskazanych danych/sprzęcie; nie uogólnia wyniku na dowolną stację.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Na Ubuntu 24.04 utwórz środowisko według instrukcji i uruchom rzeczywistą aplikację.
2. Przejdź cały uzgodniony scenariusz, używając wspólnego manifestu pomiarów i dużego wzorca; zapisz dowody wykonania.
3. Otwórz MPP w wymaganych czytnikach i odtwórz MJPG/FFV1 w VLC; zanotuj wersje, urządzenie i wyniki.
4. Po poprawkach powtórz dotknięte przypadki i uzgodnij wspólne sprawdzenia z odbiorem drugiego systemu.

## Współpraca z integracją

Sesja integracyjna scala potrzebne wspólne zmiany i sprawdza ich odbiorców. Pełny odbiór wykonywać na faktycznie zintegrowanym zestawie commitów, bez modyfikowania aktywnych cudzych worktree.
