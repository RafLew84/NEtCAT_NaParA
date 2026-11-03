# 08: Przelicz zakres lub całą serię

**ID:** SD-V4-08

**What to build:** Użytkownik wybiera zakres klatek lub całą serię, ustawia K i uruchamia analizę. Aplikacja dopasowuje wspólne klasy z jawnie wskazanego zakresu, po czym oblicza domeny kolejnych klatek. Zgodny, już obliczony słownik może być użyty ponownie; nie jest potrzebny plik modelu.

**Blocked by:** [07: Wybierz liczbę klas i zakres ich odkrywania](07-fit-shared-classes.md).

**Status:** done — baza `e51b612`, implementacja `1c39ae2`, poprawka `46c274f`,
gałąź `domains/interactive-v04-ui`, ukończono 2026-11-03.

[Uruchomienie, raport i test ręczny](acceptance-08.md). 409 testów PASS,
mypy 59 modułów PASS; 14 plików kodu/testów, maksimum 527 linii.
GUI X11 sprawdzone przez agenta, w tym pełne 268 klatek TTMAPP.
**Odbiór ręczny użytkownika potwierdzony 2026-11-03** dla wersji
`a3a5316` („testy manualne ok”). Następny rekomendowany ticket: 12.

Implementacja: osobne niemodalne okno „Analiza → Analiza serii…” z zakresem
analizy, źródłem wspólnych klas i parametrami domen stosowanymi jednym
przyciskiem. Domyślnie dopasowanie z zakresu analizy; opcjonalnie inny
zakres/cała seria albo wybrany zgodny katalog wspólny z 07.

Testowane interfejsy wynikają z kryteriów zadania: strumień wyników analizy
serii (zakres, jeden katalog, zgodność z pojedynczą klatką, puste dane/błąd),
kontroler sesji (publikowanie częściowych wyników, anulowanie, nawigacja,
ponowne otwarcie i zamknięcie) oraz rzeczywiste kontrolki Qt (ustawienia,
postęp i statusy). Testy syntetyczne sprawdzają działanie, nie trafność domen.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [x] Domyślnie zakres odkrywania klas odpowiada zakresowi analizy. UI pozwala jawnie użyć innego zakresu dopasowania albo zgodnego słownika już wyznaczonego w 07. Po jednym dopasowaniu ta sama konfiguracja i wersja modelu są stosowane do wszystkich analizowanych klatek, bez niezależnego odkrywania klas na każdej.
- [x] UI pokazuje postęp oraz status każdej klatki. Klasy mają wspólny słownik, a domeny lokalne identyfikatory.
- [x] Anulowanie podczas dopasowania zachowuje poprzedni poprawny słownik/wynik. Podczas analizy zachowuje ukończone klatki jako wynik częściowy. Niewykonane klatki pozostają bez wyniku; błąd jednej klatki jest jawny.
- [x] Nawigacja podczas pracy nie miesza obrazu i wyniku. Pamięć/cache nie rosną bez ograniczenia przy kolejnych przejściach.
- [x] Wynik klatki obliczonej w serii jest zgodny z analizą tej samej klatki osobno dla tych samych danych, modelu i ustawień.
- [x] Testy obejmują zakres, puste klatki, anulowanie, błąd i porównanie batch/pojedyncza klatka.
- [x] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [x] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz MolTrack/MPP, wybierz analizę 259–268 i K5. Aplikacja sama odkrywa wspólne klasy i przelicza zakres. Przejdź po wszystkich wynikach; przelicz 259 osobno przy tym samym obliczonym słowniku i porównaj członkostwo domen.
2. Uruchom większy zakres i anuluj; ukończone klatki pozostają dostępne, a reszta jest oznaczona jako niewykonana.
3. Przeanalizuj serię z odcinkiem bez oznaczeń i nawiguj w trakcie pracy; nie powinno być awarii ani nakładania wyniku innej klatki.

## Granice zadania

Wspólny słownik powstaje z danych przez funkcję 07; dlatego 07 jest wymaganą zależnością. Słownik jednej klatki oraz słownik zakresu nie muszą dać identycznego wyniku. Porównanie batch/pojedyncza klatka dotyczy tego samego słownika, a nie ponownego lokalnego dopasowania. Otwieranie zapisanego własnego projektu pojawia się osobno w 13.
