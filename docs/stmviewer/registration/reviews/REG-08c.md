# REG-08c — karta wykonania i odbioru

Data: 2026-11-01. Status: **done**; użytkownik potwierdził „testy manualne ok”.
Baza: `5f45b368a00e2895d7ee0248bdd4f46caac1dd67`.
Implementacja: `140136e`; poprawka przeglądu: `73bbc44`.
Gałąź: `viewer/registration-difficult-movies`.

[Ticket](../issues/08c-graph-movie-application.md),
[instrukcja manualna](../graph-application-manual.md),
[rzeczywiste próby i gotowe sesje](../graph-application-results.md).

## Standards

Niezależny przegląd `5f45b36…140136e`: **0 naruszeń udokumentowanych zasad**
i jedna uwaga heurystyczna P3. Konstruktor `MovieSnapshot` w dekoderze używał
wielu argumentów pozycyjnych, utrudniając odróżnienie końcowych XY, bazy,
korekt i diagnostyk. W `73bbc44` zastąpiono je nazwanymi argumentami,
bez zmiany wartości. Recenzent potwierdził zamknięcie uwagi i brak nowych
ustaleń po przeglądzie delty. **0 otwartych uwag Standards**.

Zakres aplikacji zachowany, odpowiedzialności rozdzielone; testy używają
publicznych granic, a kontrolowane podmiany dotyczą bibliotek zewnętrznych
oraz plików. Nie zmieniano wspólnych modułów ani konfiguracji głównej.

## Spec

Niezależny przegląd `5f45b36…140136e`: **0 ustaleń**. Sprawdzono jawne
zastosowanie i odmowy, render oryginałów, zamrożoną bazę G, ręczną propagację,
lekki poprzednik i jego przywrócenie, sesje v3 oraz MPP v5, w tym historię
po usunięciu klatek. Nie stwierdzono rozszerzenia zakresu ani błędnego zachowania.
Przegląd delty `140136e..73bbc44` potwierdził zachowanie kontraktu.
**0 otwartych ustaleń Spec**. Późniejszy odbiór ręczny opisano poniżej.

## Testy automatyczne

Środowisko lokalne `netcat`, Qt offscreen, `OPENBLAS_NUM_THREADS=1`.

- **Cały STM Viewer: 629 passed, 2 skipped**, 67,43 s. Log
  `/tmp/reg08c-viewer-suite.log`, JUnit `/tmp/reg08c-viewer-suite.xml`.
- Pełne repo uruchomiono raz; proces zakończył się sygnałem **SIGTERM, kod 143**
  po 2195 z 2445 przypadków, bez raportu JUnit. Przyczyny sygnału nie ustalono.
  Zapisany postęp: **2165 zaliczonych, 14 błędów, 16 pominiętych**.
  Ostatnie 250 przypadków należało wyłącznie do STM Viewera; wszystkie
  zostały objęte późniejszym pełnym sprawdzeniem tego katalogu.
- Oznaczenia 14 błędów zestawiono z kolejnością kolekcji testów: identyfikatory
  dokładnie odpowiadają bazie `/tmp/reg08b-full-suite.log` (MolTrack/NanoTrack).
  Po połączeniu rozłącznych zakresów: **2415 passed, 14 failed, 16 skipped**.
  To pokrycie całego zestawu w dwóch przebiegach, nie ukończony pojedynczy
  pełny przebieg. Nie stwierdzono nowych błędów Viewera.
  Materiał: `/tmp/reg08c-full-suite.log`, `/tmp/reg08c-collected.log`,
  `/tmp/reg08c-suite-progress.json` i `/tmp/reg08c-suite-remaining.txt`.
- **34 nowe przypadki** REG-08c zaliczone w pełnym zakresie Viewera:
  9 silnika, 13 GUI, 10 sesji/MPP, 2 AVI. Kolejne przypadki rozwijano RED→GREEN.
  Obejmują odmowę niepełnej/starej próby, jeden render oryginałów, G różne od
  surowego pomiaru, dwie korekty, idempotencję, cofnięcie i starą rewizję,
  przywrócenie bez wag, zachowanie historycznej geometrii/skali po usunięciu,
  niezależnego kandydata, starsze formaty i uszkodzone metadane.
- GUI sprawdza postęp, blokady, błąd/anulowanie/zamknięcie podczas zastosowania
  i przywracania, zachowanie gamma i klatki, nowy kadr, wybór LS/Hubera,
  widoczne odmowy oraz sesję z dalszą ręczną korektą bez modelu.
- Po poprawce czytelności: **15 testów silnika i sesji zaliczonych**; pełny
  późniejszy zakres Viewera również obejmował poprawkę.
- Strict mypy: **81 modułów bez błędów**; Ruff całego zmienionego kodu
  i `git diff --check` bez błędów. Największy zmieniony plik ma **967 linii**
  (`ui/main_window.py`), poniżej celu 1000 i limitu 1500.

Polecenie pełnej próby:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=.:tests/moltrack:tests/stmviewer python -m pytest --import-mode=importlib -q -p no:cacheprovider -o faulthandler_timeout=120 --junitxml=/tmp/reg08c-full-suite.xml
```

Uzupełnienie: ta sama komenda z argumentem
`tests/stmviewer` i osobnym plikiem JUnit, bez powtarzania całego repo.

## Dane, GUI i ograniczenia odbioru

Wzorzec, pełne MOVIE_4 bez dwóch pierwszych klatek oraz MOVIE_8 przeszły
zastosowanie LS/Hubera, ręczną poprawkę, zapis/odczyt sesji, dokładny powrót
do poprzednika i do grafu, mały MPP oraz AVI. Próby nie importowały modelu.
Poprzednik zawiera pozycje i historię, bez dodatkowych tablic obrazów.
Szczegóły, czasy, RSS i ścieżki w raporcie połączonym na początku karty.

Qt offscreen sprawdzono automatycznie; obejrzano zrzuty przy 1260×740.
VLC 3.0.24 odczytał FFV1 i MJPG do EOF z aktywnymi dekoderami, kodem 0
oraz bez błędów; wyjście dummy nie jest ręczną oceną odtwarzania.
Odczyt sesji bez modelu i symulowany transfer ścieżek nie zastępują próby Windows.

**Decyzja użytkownika: przyjęte, 2026-11-01.** Potwierdzenie: **„testy manualne ok”**.
REG-08c zamknięto jako `done`. Użytkownik nie podał szczegółowej oceny jakości
MOVIE_4/MOVIE_8, systemu ani sprzętu; potwierdzeniu nie przypisujemy przewagi
LS/Hubera, odbioru Windows 11 ani stanowiska docelowego. Przykładowe korekty +1
nie są wynikiem oceny fizycznego dryfu. REG-10 ma spełnioną zależność,
lecz pozostaje nierozpoczęty.

Przy odbiorze użytkownik poprosił o dialog informujący o braku kompletnego
wyniku. Powiadomienie po nowym niekompletnym Huberze wyjaśnia powód zakończenia,
liczbę iteracji i niedostępność zastosowania; przypomina o jawnym wyborze
kompletnego LS/Hubera. Nie zmienia solvera ani wyboru wariantu.
Nowy dialog nie był objęty wcześniejszą próbą manualną użytkownika.

Przeglądy: Standards — 0 otwartych uwag po poprawce; Spec — 0 ustaleń.


## Uzupełnienie: komunikat niekompletnego Hubera

Commit `293d392`, baza przeglądu `be46f91`. Istniejący test granicy GUI
rozszerzono przed implementacją: RED — brak dialogu po limicie iteracji;
GREEN — komunikat pokazuje powód i liczbę iteracji, zamyka się przez OK,
a następnie można wybrać LS i odblokować zastosowanie. Poprawny wynik nie
wyświetla komunikatu. Zachowano poprzedni podgląd i diagnostykę odmowy.

Zakres regresji: **36 testów GUI zaliczonych**, 4,77 s — Huber, zastosowanie
grafu oraz okna grafu i ich cykl pracy. Strict mypy: **81 modułów**, Ruff
obu zmienionych plików i `git diff --check`: bez błędów. Pełnego repo nie
powtarzano dla tej zmiany prezentacji. Pliki kodu mają 215 i 235 linii.
Zrzut Qt offscreen `/tmp/reg08c-incomplete-notice.png` obejrzano: cały tekst
i przycisk OK mieszczą się w oknie 474×277. To sprawdzenie automatyczne.

Dwa niezależne przeglądy `be46f91…293d392`: **Standards — 0 ustaleń;
Spec — 0 ustaleń**. Dialog używa nieblokującego `open()` z rodzicem Qt
i automatycznym usunięciem po zamknięciu. Pojawia się po świeżej odmowie
Hubera, nie przy samym odczycie sesji, sukcesie ani anulowaniu. Algorytm,
warunki zbieżności i wybór wariantu pozostają bez zmian.
