# Podgląd, gamma i odtwarzanie serii

Type: prototype
Label: wayfinder:prototype
Status: resolved
Assignee: rlew
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 01

Zależy od: [Seria wejściowa i usuwanie klatek](01-frame-series.md).

## Question

Jaki prosty układ okna i zachowanie podglądu pozwolą wygodnie przeglądać serię,
regulować gamma, przybliżać oraz odtwarzać i zatrzymywać klatki?

Prototyp ma pomóc uzgodnić listę/suwak klatek, jeden lub więcej obszarów
podglądu, zachowanie zoomu i gamma przy zmianie klatki i original/aligned,
prędkość odtwarzania, koniec serii (stop/pętla), ręczną nawigację podczas Play
oraz wygląd brakujących pikseli po rejestracji. Użytkownik ocenia prototyp;
nie jest on implementacją produkcyjną.

## Comments

### 2026-10-14 — wymagania użytkownika

Punktem odniesienia jest NanoTrack. Potrzebne są zoom, kontrola gamma,
przycisk Play, wybór prędkości i zatrzymanie na klatce. Widok aligned zastępuje
original w podglądzie, z możliwością przełączenia. Gotowy widget zapewnia zoom
i gamma, lecz nie odtwarzanie. Zobacz [rozpoznanie](../reconnaissance.md).

### 2026-10-19 — prototyp i ocena użytkownika

Przygotowano samodzielny prototyp HTML w trzech układach: lista klatek (A),
pasek miniatur pod obrazem (B) i siatka miniatur obok obrazu (C). Działały
odtwarzanie, gamma, zoom, original/aligned, odwracanie i usuwanie klatek.
Użytkownik wybrał „B — obraz z paskiem miniatur na dole” oraz potwierdził
przedstawione zasady odtwarzania i podglądu.

Źródło eksperymentu: gałąź `prototype/stmviewer-preview-playback`, commit
`bf8e849`. [Artefakt, uruchomienie, dane i sprawdzenia](../preview-playback-prototype.md).

### 2026-10-19 — korekta po decyzji o rejestracji

Użytkownik wycofał odwracanie kolejności z zakresu STM Viewer. Usunięto tę
operację z poniższej odpowiedzi i z aktualnego prototypu (`efb7e50`);
wybrany układ B i pozostałe zasady podglądu pozostają bez zmian.

## Answer

### Układ i wybór klatki

Przyjmujemy **wariant B**. Jeden główny obraz zajmuje środkową część okna,
ustawienia podglądu znajdują się po prawej, a poziomy pasek miniatur — na dole.
Sterowanie odtwarzaniem jest pod obrazem, nad miniaturami.
Original i aligned przełączają zawartość tego samego głównego podglądu.

Do wybierania klatki służą miniatury, suwak, bieżący numer oraz przyciski
poprzednia/następna. Numer bieżący i pochodzenie obrazu pozostają rozdzielone
zgodnie z [kontraktem serii](01-frame-series.md). Wybór synchronizuje wszystkie
kontrolki. Miniatury pokazują original z gamma 1,0; ustawienie gamma dotyczy
głównego obrazu. Pasek miniatur wskazuje i odsłania bieżącą klatkę.

### Odtwarzanie

- Play/Pause; domyślnie 5 kl./s. Wybór tempa: 1, 2, 5, 10, 20 i 30 kl./s,
  jak w ocenionym prototypie. To tempo podglądu, niezależne od czasu pomiaru.
- Domyślnie odtwarzanie kończy się na ostatniej klatce i pozostawia ją na ekranie.
  Opcjonalna pętla przechodzi z ostatniej do pierwszej.
- Play naciśnięte na ostatniej klatce zaczyna od pierwszej. W pozostałych
  pozycjach wznawia od bieżącej; Pause pozostawia bieżącą klatkę.
- Ręczny wybór miniaturą, suwakiem, numerem lub przyciskiem poprzednia/następna
  zatrzymuje Play na wskazanej klatce.
- Zmiana original/aligned i usunięcie klatki również zatrzymują odtwarzanie.
  Reguły wyboru obrazu po usunięciu pozostają zgodne z kontraktem serii.
- Gamma, zoom, przesuwanie obrazu i zmiana tempa mogą być regulowane podczas
  Play; nie zmieniają wybranej kolejności ani danych pomiarowych.
- Pusta seria i pojedyncza klatka nie uruchamiają Play. Dla jednej klatki
  pozostają dostępne ustawienia podglądu i jej usunięcie.

### Gamma, zoom i brakujące piksele

- Gamma ma zakres 0,1–4,0, domyślnie 1,0, z kontrolką wartości i możliwością
  resetu. Ustawienie jest wspólne dla wszystkich klatek oraz original/aligned.
  Zmienia tylko prezentację obrazu, nie wartości pomiaru.
- Położenie i powiększenie podglądu są zachowane przy zmianie klatki.
  Original i aligned pamiętają osobny obszar podglądu; powrót do widoku
  przywraca jego ustawienie. Pierwsze otwarcie widoku dopasowuje cały obraz.
- Kółko myszy przybliża pod kursorem, przeciąganie przesuwa obraz.
  Dostępne są przyciski przybliżenia, oddalenia i „Dopasuj”. Dopasowanie
  obejmuje pełny rozmiar aktywnego widoku, także powiększony obszar aligned.
- Brakujące piksele pokazujemy **szachownicą**. Pozostają wizualnie odróżnione
  od czarnych, prawidłowych pikseli pomiaru; gamma nie zmienia szachownicy.
  W aligned obrys wskazuje oryginalne pole klatki.
- Po poprawnym otwarciu nowej serii: pierwsza klatka, pauza, original,
  gamma 1,0 i dopasowanie obrazu. Nieudany import zachowuje dotychczasowy
  stan zgodnie z kontraktem serii.

### Przykłady do późniejszego odbioru implementacji

| Czynność | Oczekiwany wynik |
| --- | --- |
| Wybierz miniaturę podczas Play | Odtwarzanie staje; obraz, suwak i numer wskazują wybraną klatkę. |
| Dojdź do końca bez pętli | Pozostaje ostatnia klatka w stanie Pause. |
| Włącz pętlę | Po ostatniej wyświetlana jest pierwsza, Play trwa. |
| Naciśnij Play na ostatniej klatce | Odtwarzanie zaczyna od pierwszej. |
| Ustaw gamma i zoom, zmień klatkę | Gamma i obszar podglądu są zachowane. |
| Ustaw różny zoom original i aligned, przełącz widoki | Każdy widok przywraca własne ustawienie; gamma pozostaje wspólna. |
| Zmień gamma w aligned | Obraz zmienia jasność, szachownica pozostaje taka sama. |
| Usuń jedyną klatkę | Pusty podgląd i niedostępne Play; źródło na dysku pozostaje bez zmian. |

### Granice decyzji

Panel porównywania zachowań i przełącznik A/B/C służą wyłącznie eksperymentowi.
Prototyp pozostaje na osobnej gałęzi; ten ticket ustala specyfikację przyszłego
okna PyQt6, nie wdraża funkcji aplikacji.

[Rejestracja i życie wyniku aligned](03-registration.md) rozstrzyga dostępność
i ważność aligned, w tym po usunięciu. Powiązanie pola oryginalnej
klatki z wynikiem jest potrzebne do obrysu i prezentacji brakujących pikseli.
[Opcje filmu AVI](05-avi-export.md) osobno rozstrzygają tempo, gamma, wycinek
i wygląd brakujących danych w pliku wynikowym. Ten wybór podglądu nie zamyka
kontraktu eksportu.
