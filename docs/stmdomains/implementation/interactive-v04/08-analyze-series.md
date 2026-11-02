# 08: Przelicz zakres lub całą serię

**ID:** SD-V4-08

**What to build:** Użytkownik wybiera zakres klatek lub całą serię, ustawia K i uruchamia analizę. Aplikacja dopasowuje wspólne klasy z jawnie wskazanego zakresu, po czym oblicza domeny kolejnych klatek. Zgodny, już obliczony słownik może być użyty ponownie; nie jest potrzebny plik modelu.

**Blocked by:** [07: Wybierz liczbę klas i zakres ich odkrywania](07-fit-shared-classes.md).

**Status:** ready-for-agent — wymaga ukończenia zależności.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Domyślnie zakres odkrywania klas odpowiada zakresowi analizy. UI pozwala jawnie użyć innego zakresu dopasowania albo zgodnego słownika już wyznaczonego w 07. Po jednym dopasowaniu ta sama konfiguracja i wersja modelu są stosowane do wszystkich analizowanych klatek, bez niezależnego odkrywania klas na każdej.
- [ ] UI pokazuje postęp oraz status każdej klatki. Klasy mają wspólny słownik, a domeny lokalne identyfikatory.
- [ ] Anulowanie podczas dopasowania zachowuje poprzedni poprawny słownik/wynik. Podczas analizy zachowuje ukończone klatki jako wynik częściowy. Niewykonane klatki pozostają bez wyniku; błąd jednej klatki jest jawny.
- [ ] Nawigacja podczas pracy nie miesza obrazu i wyniku. Pamięć/cache nie rosną bez ograniczenia przy kolejnych przejściach.
- [ ] Wynik klatki obliczonej w serii jest zgodny z analizą tej samej klatki osobno dla tych samych danych, modelu i ustawień.
- [ ] Testy obejmują zakres, puste klatki, anulowanie, błąd i porównanie batch/pojedyncza klatka.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz MolTrack/MPP, wybierz analizę 259–268 i K5. Aplikacja sama odkrywa wspólne klasy i przelicza zakres. Przejdź po wszystkich wynikach; przelicz 259 osobno przy tym samym obliczonym słowniku i porównaj członkostwo domen.
2. Uruchom większy zakres i anuluj; ukończone klatki pozostają dostępne, a reszta jest oznaczona jako niewykonana.
3. Przeanalizuj serię z odcinkiem bez oznaczeń i nawiguj w trakcie pracy; nie powinno być awarii ani nakładania wyniku innej klatki.

## Granice zadania

Wspólny słownik powstaje z danych przez funkcję 07; dlatego 07 jest wymaganą zależnością. Słownik jednej klatki oraz słownik zakresu nie muszą dać identycznego wyniku. Porównanie batch/pojedyncza klatka dotyczy tego samego słownika, a nie ponownego lokalnego dopasowania. Otwieranie zapisanego własnego projektu pojawia się osobno w 13.
