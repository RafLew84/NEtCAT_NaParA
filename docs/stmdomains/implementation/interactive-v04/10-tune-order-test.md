# 10: Reguluj test porządku z prawidłową kalibracją

**ID:** SD-V4-10

**What to build:** Użytkownik zmienia wymagania lokalnego porządku, przelicza ocenę i ogląda wpływ na domeny przy zachowanym słowniku klas.

**Blocked by:** [05: Oblicz klasy i domeny bieżącej klatki z danych](05-analyze-current-frame.md).

**Status:** done — implementacja `aa7e039`, ukończono 2026-11-03; odbiór ręczny użytkownika potwierdzony 2026-11-03 dla wersji `4b55727` („testy manualne ok”).

[Uruchomienie, wykonane sprawdzenia i test ręczny](acceptance-10.md).
Baza `3c09c0b`, gałąź `domains/interactive-v04-ui`, środowisko netcat.
449 testów PASS, mypy 67 modułów PASS, Standards 0 / Spec 0; GUI X11 PASS.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [x] UI udostępnia kwantyl kontroli, minimum punktów lokalnych i efektywnych oraz promień i sigma otoczenia. Wartości faktycznie trafiają do obliczeń.
- [x] Zmiana ustawień unieważnia tylko zależne wyniki i odpowiednio przelicza kalibrację na kontrolach. Stare progi nie są bezwarunkowo stosowane do innego okna.
- [x] Kontrole i progi powstają w aplikacji według jawnej metody, dla bieżącej konfiguracji i skali, z zapisanym ziarnem oraz zakresem danych. Nie są odczytywane z historycznych wyników, modeli lub plików kalibracji v0.4.
- [x] Słownik pozostaje zamrożony w tym trybie. Jeśli użytkownik później odkrywa klasy ponownie, aktualna ocena porządku wpływa na zakres próbek zgodnie z zapisaną konfiguracją.
- [x] UI pokazuje przyczynę odmowy i parametry użyte w wyniku; kwantyl nie jest opisywany jako pewność poprawności domeny.
- [x] Kalibracja i analiza działają w tle, z anulowaniem i zachowaniem wcześniejszego poprawnego wyniku.
- [x] Testy obejmują zależności cache/kalibracji, słabe wsparcie, kontrolę regularną i losową. Rzędy pozostają jawnie przypadkiem metody v0.4, bez zmiany definicji sieci 2D.
- [x] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [x] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz MPP/JSON i oblicz klatkę 259 metodą bazową aplikacji. Przy zachowanym, wyznaczonym z danych słowniku K5 przelicz kwantyl 0,95 i 0,925; porównaj wynik i powody odmowy.
2. Zmniejsz promień oraz sigma otoczenia zgodnie z jednostkami podanymi w UI (instrukcja wykonawcy podaje dokładne dwie pary dla tej próby); UI pokazuje etap nowej oceny/kalibracji i faktyczne ustawienia wyniku, bez niejawnego użycia skali innego pomiaru.
3. Anuluj przeliczenie, potem wróć do ustawień bazowych. Sprawdź dostarczone przykłady regularnego i losowego układu bez utożsamiania braku wyniku z brakiem materiału.

## Granice zadania

Złagodzenie testu nie jest samo w sobie poprawą naukowej jakości. Kontrola przyjętych i odrzuconych przypadków jest częścią odbioru. Punktem odniesienia jest wynik obliczony metodą bazową aplikacji; pliki dawnego eksperymentu v0.4 nie są wymagane do działania.
