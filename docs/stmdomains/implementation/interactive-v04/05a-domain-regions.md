# 05a: Obszary i granice domen

**ID:** SD-V4-05a

**What to build:** Po analizie użytkownik widzi obszary domen jako półprzezroczyste wypełnienie, obrysy i numery, podobnie do PNG z paczki v0.4. Może ukryć centra i ramki, pozostawiając sam obraz z domenami.

**Blocked by:** [05: Oblicz klasy i domeny bieżącej klatki](05-analyze-current-frame.md).

**Status:** done — implementacja `dfcf392`; ręczny odbiór użytkownika oczekuje.

[Uruchomienie, wykonane sprawdzenia i test ręczny](acceptance-05a.md).

Baza implementacji/przeglądu: `319c156`, gałąź `domains/interactive-v04-ui`,
środowisko `netcat`. Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).
Zatwierdzony zakres obejmuje testy granic: obliczenia → końcowy wynik
przestrzenny oraz wynik → obraz/kontrolki UI. Testy sprawdzają zgodność
obszarów z przypisaniami i zachowanie widoczne w aplikacji.

## Kryteria akceptacji

- [x] Wynik zachowuje mapę końcowych domen w oryginalnej geometrii obrazu. ID pikseli zgadzają się z przypisaniami po podziale, odrzuceniu małych fragmentów i renumeracji. Bariery, otwory i odrzucone fragmenty pozostają bez wypełnienia; nie rysujemy otoczki wypukłej ani wstępnych składowych.
- [x] Domyślny widok obliczonego wyniku ma półprzezroczyste wypełnienie, obrys i lokalny numer domeny. Każdą warstwę można niezależnie wyłączyć; działa regulacja krycia wypełnienia oraz niezależne centra i ramki.
- [x] Domeny/Klasy używają tych samych kolorów obszarów, molekuł i legendy. Klasy nie łączą oddzielnych domen: obrysy i numery pozostają osobne. Wejściowe ukrywa obliczone obszary.
- [x] „Maski / obrysy” mają nazwę „Maski molekuł” i informację o źródle MolTrack. Brak tych masek nie blokuje obliczonych domen, np. na klatce 259.
- [x] Obszary zachowują położenie przy raw/aligned, przesunięciach ułamkowych, gamma i zoomie. Nic nie jest dorysowywane w dopełnieniu poza oryginalnym polem.
- [x] Brak analizy, brak dopasowania i poprawne zero nie pozostawiają obszarów poprzedniego wyniku. Anulowanie i błędy zachowują poprzedni poprawny wynik wraz z mapą. Ustawienia widoku nie przeliczają analizy ani nie zmieniają przypisań.
- [x] Układ nie skacze podczas obliczeń lub zmiany klatki. Prezentacja pozostaje responsywna, bez nieograniczonego cache kolorowych kopii rastra. Działanie nie wymaga danych ZIP ani instalacji.
- [x] Kontrole obejmują rozdzielenie i renumerację, otwór/barierę, odrzucenie małego fragmentu, geometrię i UI na TTMAPP 7/120/259/268. Podano instrukcję ręczną, odróżniając sprawdzenie agenta od odbioru użytkownika.
- [x] Sprawdzono długość kodu/testów według zasady 1000/1500 linii; zaktualizowano plan i przekazanie, wykonano przegląd i commit.

## Test ręczny użytkownika

1. W `netcat` uruchom `python -m stmdomains.main`, otwórz `data/TTMAPP/detection_full.moltrack.json`, wybierz 259 i kliknij **Analizuj klatkę · K5**.
2. Wyłącz Centra i Ramki. Pozostają kolorowe obszary, obrysy i numery domen; „Maski molekuł” są nieaktywne, bo ta klatka ich nie zawiera.
3. Otwórz **Obszary…** przy legendzie. Osobno wyłącz/włącz wypełnienie, obrysy i numery; zmień krycie od 0 do 100%. Przy 0% obrysy i numery nadal działają zgodnie z własnymi przełącznikami.
4. Przełącz Domeny/Klasy/Wejściowe. Sprawdź kolory względem legendy, oddzielne numery domen tej samej klasy i brak obszarów w trybie Wejściowe.
5. Zmień raw/aligned, gamma, zoom oraz rozmiar okna. Obszary pozostają na tym samym fragmencie obrazu, a układ nie skacze przy analizie i przełączaniu klatek.
6. Przejdź do nieanalizowanej klatki, wróć do 259, powtórz na 7/120/268. Na kontroli zera i braku danych z `python -m stmdomains.tools.analysis_demo` sprawdź brak starych obszarów. Anuluj ponowną analizę i zamknij aplikację podczas pracy.

## Granice zadania

Zmiana prezentacji zachowuje metodę i przypisania 05. Obszar jest
przybliżeniem wspartym centrami i barierami, nie niezależnym pomiarem pełnej
fizycznej granicy. Nie importujemy masek z ZIP ani nie dodajemy modeli,
strojenia 06, analizy serii, eksportu czy zapisu projektu. Ręczny odbiór 05a
nie oznacza naukowego odbioru trafności domen.
