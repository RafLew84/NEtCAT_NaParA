# REG-07 — ręczna próba zapisu i odczytu sesji

Status: odbiór użytkownika potwierdzony 2026-11-01: „testy manualne ok”.
Instrukcja pozostaje do ponowienia próby. Testy Qt offscreen są osobnym
sprawdzeniem automatycznym; użytkownik nie wskazał systemu ani odtwarzacza.

## Uruchomienie i dane

```bash
conda activate netcat
cd /home/rlew/projekty/NEtCAT-viewer
python -m stmviewer
```

Mały wzorzec: `tests/stmviewer/fixtures/registration/cpu.mpp` (3 klatki).
Dłuższe filmy: `data/MOVIE_4.mpp` i `data/MOVIE_8.mpp`. Dla MOVIE_4 usuń
źródłowe klatki 1 i 2 przed rejestracją. Pozostałe numery są numerami bieżącej serii.
Wyniki sesji zapisuj poza Git. Do szybkiej próby wystarczy Phase; do oceny
wizualnej można użyć wcześniejszego wyniku Deep Matcher Outdoor.

## Wznowienie pracy

1. Otwórz cpu.mpp, zmień klatkę, gamma, zoom kółkiem i przesunięcie przeciąganiem.
   Ustaw FPS i pętlę. Wybierz **Zapisz sesję…** (Ctrl+Shift+S), zapisz
   `cpu.stmsession`. Zamknij program i uruchom ponownie.
2. W pustym programie wybierz **Otwórz sesję…** (Ctrl+Shift+O). Wskaż tylko
   `cpu.stmsession`. Obrazy, kolejność, metadane i ustawienia wracają;
   odtwarzanie jest zatrzymane. Zwykłe otwieranie STP/MPP/S94 pozostaje osobne.
3. Wykonaj Phase i popraw dwie pary ręcznie w **Porównaj parę…**:
   **Popraw dopasowanie z filmu**, ruch o 1 px, **Zakończ korektę**,
   **Zastosuj do filmu**. Zrób to osobno dla par 1→2 i 2→3.
   Wybierz różny zoom i przesunięcie widoku original oraz aligned.
4. Zapisz sesję. Przenieś kopię samego `.stmsession` do innego katalogu,
   najlepiej na komputer bez pierwotnego MPP i wag modelu. Otwórz ją w świeżym
   programie. Film, obszar aligned, źródłowe obrysy, braki, XY i ręczna historia
   mają być takie same. Nie powinno ruszyć obliczanie rejestracji.
5. W oknie pary cofnij jedną zastosowaną korektę. Druga pozostaje, a wpływ
   cofniętej zmiany znika także z kolejnych klatek. Dodaj nową korektę,
   zapisz sesję ponownie i sprawdź kolejne otwarcie.
6. Wyeksportuj aligned do MPP oraz AVI (np. FFV1). MPP odczytaj razem
   z towarzyszącym JSON w Viewerze; AVI obejrzyj w VLC. Eksport ma przedstawiać
   bieżący poprawiony film. Ustawienia eksportu są jak przed REG-07.
7. W oddzielnej kopii sesji usuń pierwszą klatkę. Zapisz i ponownie otwórz.
   Klatka nie wraca; rozmiar płótna i położenie pozostałych obrazów pozostają.
   Jak wcześniej po usunięciu klatki, dalsze ręczne korekty wymagają nowej
   rejestracji; przeglądanie i eksport są dostępne.
8. Powtórz zapis/odczyt dla dłuższego filmu. Podczas operacji sprawdź postęp,
   **Anuluj zapis/odczyt sesji** oraz dalsze przewijanie/zoom. Import, zmiana
   składu serii, rejestracja i eksport są na czas operacji zablokowane.
   Sesja zapisuje stan z chwili rozpoczęcia zapisu, także gdy potem zmienisz widok.
9. Przy wczytanym dobrym filmie otwórz kolejno oba przygotowane poniżej
   nieprawidłowe zapisy. Komunikaty mają wyjaśnić uszkodzony plik i nieobsługiwaną
   wersję; dotychczasowy film i eksport pozostają dostępne. Anulowany zapis
   nie niszczy istniejącego pliku docelowego. Następnie sprawdź poprawny zapis i odczyt.

Wzorce do kroku 9 wygeneruj z katalogu repozytorium:

```bash
python tests/stmviewer/diagnostics/make_invalid_sessions.py
```

Generator wypisze pełne ścieżki `damaged.stmsession` i
`unsupported-version.stmsession` w katalogu tymczasowym systemu. Są to celowo
nieprawidłowe pliki do próby odmowy; generator nie dotyka zapisów użytkownika.

Sesja zawiera jedną bieżącą pracę i zastosowane korekty. Niezastosowany szkic
w oknie pary, przerwane obliczenia i lista wcześniejszych prób nie są zapisywane.
Dotychczasowe okno pary pozostaje dostępne; usunięto dodatkowy panel pełnych prób A/B.
Sam zapis sesji nie poprawia jakości rejestracji. Ścieżka wag zostaje ustawieniem;
jeśli pliku wag nie ma, gotowy film, ręczne poprawki i eksport nadal działają.

Limit formatu: 8 GiB nieskompresowanych próbek original+aligned. Plik zawiera
obie wersje, gdy aligned istnieje; może być większy od źródłowego MPP.
Otwieranie w tle chwilowo wymaga pamięci na poprzednią i nową sesję.

Wynik odbioru należy zapisać w [tickecie](issues/07-session-save-load.md),
oddzielnie od [testów automatycznych](session-results.md).
