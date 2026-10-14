# STM Domains — przekazanie

Data: 2026-10-14. Gałąź: `domains/start`.

## Zakres i wynik

Po przeglądzie ogólnego wykrywania domen przygotowano
[notatkę o pomiarze orientacji molekuły](research-molecular-orientation.md).
Opisuje wymagane wejście niezależne od formatu MolTrack, metody analizy,
niejednoznaczność symetrii oraz potrzebne referencje i pomiary jakości.

Sprawdzono lokalny `data/TTMAPP/detection_full.moltrack.json` i wskazany przez
niego plik MPP. Oprócz 52 494 detekcji zapis zawiera 11 993 maski SAM2.
Adnotacje są w układzie `expanded_aligned`; opisano ich przeliczenie na surową
klatkę i różnicę między `original_bbox_xyxy` a współrzędnymi surowego obrazu.
Przygotowano przegląd pierwszej klatki, 12 wycinków i kontrolę anizotropii masek.
Artefakty oraz skrypt pozostają lokalne w ignorowanym katalogu
`.scratch/stmdomains/orientation-inspection/`.

Użytkownik potwierdził, że parametry fizyczne nagłówka MPP są zastępczymi
wartościami eksportu. Nie ma jeszcze definicji orientacji molekuły. Proponowany
pierwszy etap dotyczy orientacji widocznego motywu względem obrazu; przypisanie
osi chemicznej i orientacji względem podłoża wymaga dodatkowych informacji.

Nie powstały mapa, tickety ani implementacja funkcji aplikacji. Nie przypisano
molekułom końcowych kątów. Uzupełniono README.

## Commit

Wcześniejsze przeglądy: `a5d6601` oraz `0e45ee3`. Bieżący commit dokumentacji
obejmuje nową notatkę, README i ten plik; jego identyfikator znajduje się
w końcowej wiadomości sesji.

## Wykonane sprawdzenia

- Odczyt JSON, nagłówka i pikseli MPP; zapis SHA-256 wejść w notatce.
- Kontrola liczebności rekordów, klatek, układów współrzędnych i rozmiarów bboxów.
- Inspekcja kodu importu, transformacji współrzędnych i estymatorów MolTrack.
- Uruchomienie lokalnego skryptu `inspect_input.py`: odtworzenie przesunięcia
  pierwszej klatki, dekodowanie 288 masek, momenty kształtu i obrazy diagnostyczne.
- Wizualna inspekcja surowej klatki i 12 wycinków; bez wygładzania lub obracania.
- Przegląd źródeł pierwotnych, kontrola lokalnych odnośników i `git diff --check`.

## Ograniczenia i dalszy odbiór

Inspekcja jednej klatki i rozkład anizotropii nie są oceną skuteczności pomiaru
orientacji. Nie ustalono symetrii TTMAPP z tych danych, nie porównano kątów
z niezależnymi oznaczeniami i nie uruchamiano testów aplikacji ani GUI.
Nie instalowano zależności. Skrypt wykorzystał dostępny w powłoce interpreter
środowiska `netcat` z NumPy i Matplotlib, a nie lokalne `.venv` aplikacji.

Do porównania metod potrzebne są definicja widocznego kierunku, oznaczone
przykłady i potwierdzenie geometrii skali x/y. Warunki obrazowania i geometria
podłoża są potrzebne do dalszej interpretacji fizycznej. Nie ma zmian wspólnych
modułów do scalenia; wykorzystanie istniejących estymatorów pozostaje do oceny.
