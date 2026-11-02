# 01: Otwórz zapis i przeglądaj obrazy

**ID:** SD-V4-01

**What to build:** Użytkownik uruchamia STM Domains, otwiera zapis MolTrack, wskazuje powiązany MPP, jeśli aplikacja go nie odnajdzie, i przegląda rzeczywiste obrazy. Pierwszy ticket dostarcza działające okno z importem i nawigacją.

**Blocked by:** None (can start immediately after approval of the breakdown).

**Status:** in_progress — wykonanie zlecone przez użytkownika; prowadzi Codex na `domains/interactive-v04-ui`.

Punkt bazowy implementacji i przeglądu: `4c4825f`. Testy przy publicznych
interfejsach importu/modelu oraz pełnej ścieżce import–widok, zgodnie
z kryteriami poniżej; środowisko `netcat`.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Po otwarciu TTMAPP dostępne są 268 klatek we właściwej orientacji i kolejności; UI pokazuje numery od 1. Działa poprzednia/następna, wybór numeru, dopasowanie i powiększanie obrazu.
- [ ] Import zachowuje mapę źródłowych klatek. Nieznana wersja zapisu, błędne źródło, zmieniony mtime i brak pliku są obsługiwane zgodnie z istniejącym kontraktem importu.
- [ ] Jedna klatka działa z nieaktywną zbędną nawigacją. Brak wiarygodnego czasu lub skali nie tworzy fikcyjnych jednostek.
- [ ] Długi odczyt nie blokuje okna; anulowanie lub błąd nowego otwarcia pozostawia poprzednią serię. Spóźniony odczyt nie podmienia aktualnego widoku.
- [ ] Automatyczne sprawdzenia obejmują prawdziwą ścieżkę import–model–widok, niesymetryczny obraz, niestandardową kolejność klatek oraz błąd/anulowanie.
- [ ] Do lokalnych sprawdzeń zadania dołączono kontrolę długości plików według wspólnej zasady; nie zmienia ona wspólnego CI.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Uruchom aplikację i otwórz TTMAPP; sprawdź pierwszą, wybraną środkową i ostatnią klatkę.
2. Przejdź poprzednia/następna, wpisz numer, powiększ i dopasuj obraz; obraz i numer muszą odpowiadać sobie.
3. Spróbuj otworzyć niezgodny plik, anuluj wybór MPP, a następnie otwórz dostarczoną małą serię jednej klatki; błędy nie usuwają poprzedniego poprawnego widoku.

## Granice zadania

Oznaczenia molekuł, wyrównany widok, miniatury i analiza przychodzą w kolejnych zadaniach. Ten ticket nie zamyka całego historycznego odbioru szkieletu.
