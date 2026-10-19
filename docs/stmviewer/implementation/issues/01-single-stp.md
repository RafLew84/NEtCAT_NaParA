# 01: Pierwszy obraz STP w działającym oknie

**What to build:** Użytkownik uruchamia program, otwiera jeden rzeczywisty STP i widzi poprawny obraz oraz jego pochodzenie i metadane.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Specyfikacja:** [Seria wejściowa i usuwanie klatek](../../issues/01-frame-series.md#answer), [Podgląd, gamma i odtwarzanie serii](../../issues/02-preview-playback.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Okno uruchamia się z repozytorium i otwiera jeden STP przez wybór pliku; rzeczywisty obraz jest dopasowany do głównego podglądu.
- [ ] Odczyt zachowuje orientację, wartości, źródłowy kanał, jednostkę sygnału i skalę. Nieznane parametry pozostają nieznane; Z Amplitude nie skaluje ponownie danych double.
- [ ] Ponowne otwarcie poprawnego STP zastępuje obraz; anulowanie wyboru i błąd odczytu zachowują dotychczasowy obraz. Komunikat wskazuje źródło problemu.
- [ ] Pusty program i pojedyncza klatka mają spójne kontrolki. Zestawy wielu plików i filmstrip należą do następnego etapu.
- [ ] Jest instrukcja uruchomienia na docelowych systemach, minimalne zależności dla tej funkcji i ustalona z integracją komenda sprawdzania typów kodu Viewera.
- [ ] Dołączony mały wzorzec STP pozwala ręcznie sprawdzić orientację i metadane bez posiadania pełnego katalogu pomiarowego.

## Testy automatyczne

- Rzeczywiste dekodowanie małego STP ze znanymi wartościami/metadanymi oraz poprawna orientacja.
- Otwarcie/zastąpienie obrazu przez publiczną akcję aplikacji i zachowanie starego obrazu po błędzie.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Otwarcie plików → seria lub błąd** — Sprawdza dekodowanie, orientację i metadane przez publiczny import; nie dowodzi poprawnego malowania obrazu na ekranie.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Uruchom program i otwórz mały STP z asymetrycznym znacznikiem; sprawdź obraz, orientację, nazwę źródła i parametry.
2. Otwórz drugi poprawny STP, następnie anuluj wybór i spróbuj otworzyć uszkodzoną kopię. Ostatni poprawny obraz zostaje.
3. Zamknij i uruchom program ponownie; sprawdź stan pusty i otwarcie rzeczywistego pomiaru.

## Współpraca z integracją

Minimalne zależności, komenda typecheckingu i potrzebne poprawki wspólnego czytnika STP należą do współpracy z integracją. Przygotowanie małego szkieletu jest częścią działającego otwarcia obrazu, nie oddzielną warstwą bez GUI.
