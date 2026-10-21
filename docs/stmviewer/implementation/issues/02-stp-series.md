# 02: Otwarcie i przeglądanie serii STP

**What to build:** Po uruchomieniu programu użytkownik otwiera jeden lub wiele STP, ogląda rzeczywiste obrazy i przechodzi między klatkami w układzie z dolnym paskiem miniatur.

**Blocked by:** [01: Pierwszy obraz STP w działającym oknie](01-single-stp.md)

**Status:** ready-for-review

**Wykonawca:** Codex, `viewer/start`.

**Baza code-review:** `3f2e92b59d29dc0ecf74751807e26f530167af7d`.

**Specyfikacja:** [Seria wejściowa i usuwanie klatek](../../issues/01-frame-series.md#answer), [Podgląd, gamma i odtwarzanie serii](../../issues/02-preview-playback.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Okno otwierania przyjmuje jeden lub wiele STP i sortuje nazwy naturalnie; seria ma jednakowe wymiary, bez obowiązku wspólnej skali lub kanału.
- [x] Główny obraz, miniatury, numer i przyciski poprzednia/następna wskazują tę samą klatkę; widoczne są jej pochodzenie i dostępne metadane.
- [x] Odczyt zachowuje orientację, wartości oraz metadane każdej klatki. Nieznana jednostka lub kalibracja pozostaje nieznana; Z Amplitude nie skaluje ponownie danych double.
- [x] Nowy import zastępuje stan dopiero po sukcesie. Uszkodzony plik, inne wymiary lub anulowanie zachowują poprzednią serię i wybór; problematyczne źródło jest wskazane.
- [x] Import ma postęp i anulowanie, a okno pozostaje responsywne. Pierwszy poprawny import pokazuje pierwszą klatkę dopasowaną do okna; stan pusty i pojedyncza klatka są obsłużone.
- [x] Rozszerza istniejące otwarcie pojedynczego obrazu, zachowując sprawdzone dekodowanie i konfigurację środowiska; ten etap dodaje serię, nawigację i pełny przebieg dłuższego importu.

## Testy automatyczne

- Dekodowanie asymetrycznego STP o znanych liczbach i metadanych; sortowanie, różna kalibracja oraz odrzucenie całego importu.
- Przejścia stanu importu i synchronizacja kontrolek; kontrolowany błąd/anulowanie bez podmiany poprzedniego stanu.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Otwarcie plików → seria lub błąd** — Sprawdza dekodowanie, orientację i metadane przez publiczny import; nie dowodzi poprawnego malowania obrazu na ekranie.
- **Działanie na serii → obserwowalny stan** — Sprawdza wybór, odtwarzanie, usuwanie i transakcyjną podmianę; nie mierzy fizycznej płynności ekranu.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Uruchom aplikację i otwórz przygotowane trzy STP o nazwach klatka10, klatka2, klatka1. Oczekuj kolejności 1, 2, 10 i zgodnych miniatur.
2. Przejdź przyciskami i miniaturami przez obrazy; sprawdź asymetryczny znacznik oraz zmieniające się pochodzenie/metadane.
3. Przy otwartej serii spróbuj importu z plikiem uszkodzonym oraz innym wymiarem. Stary obraz i seria zostają.
4. Anuluj dłuższy import, a następnie otwórz pojedynczy STP. Sprawdź działanie okna i właściwy numer klatki.

## Współpraca z integracją

Jeśli wspólny loader nie zachowuje parametrów każdej klatki albo pomija uszkodzone pliki, potrzebny adapter lub poprawkę uzgodnić z integracją. Wcześniejsze otwarcie pojedynczego STP ma pozostać działające.

## Wynik implementacji — 2026-10-21

Dostarczono import STP w tle z postępem i anulowaniem, naturalne sortowanie,
sprawdzanie wymiarów oraz układ B z miniaturami, suwakiem, numerem i przyciskami.
Klatki zachowują własne dane i metadane. Zmiana klatki zachowuje zoom/przesunięcie;
nowy udany import dopasowuje pierwszą klatkę, a błąd i anulowanie zachowują stan.
Wspólne czytniki, zależności i konfiguracja repo pozostają bez zmian.

Commit implementacji: `e054738`. [Przegląd](../review-02-stp-series.md):
Standards — 0 ustaleń; Spec — 0 ustaleń.

33 testy Viewera przechodzą w Qt offscreen; mypy strict obejmuje 12 plików bez
błędów. Automatyczna próba z rzeczywistym oknem xcb i dialogiem wielokrotnego
wyboru przeszła na Linuksie. Szczegóły pełnego zestawu repo i przeglądu:
[przekazanie](../../handoff.md).

Ręczny odbiór użytkownika pozostaje niewykonany, dlatego status to
`ready-for-review`. [Scenariusz, wzorce i generator](../../stp-series-manual.md)
obejmują wszystkie kroki dostępne po tym etapie; Windows pozostaje osobnym odbiorem.

### Poprawka po zgłoszeniu z próby GUI

2026-10-21: usunięto pozostające podświetlenie wcześniejszych miniatur przy
Następna/Poprzednia. Powiadomienia Qt ponownie odświeżają stary i nowy wybór;
zapętlaniu synchronizacji zapobiega pomijanie już aktywnego indeksu.
34 testy Viewera, test regresji na xcb i mypy przechodzą. Automatyczne
porównanie obrazu ekranu potwierdza brak śladu. Ręczne potwierdzenie użytkownika
po poprawce pozostaje do wykonania; szczegóły w przekazaniu.
