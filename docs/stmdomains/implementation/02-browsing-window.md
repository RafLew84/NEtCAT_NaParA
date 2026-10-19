# Natywny podgląd i nawigacja

ID: SD-IMPL-02
Type: implementation
Status: todo
Assignee:
Depends on: [import, model serii i geometria](01-import-model.md)

## Cel

Zastąpić startowe okno natywnym podglądem C w PyQt6: jeden obraz i pasek
miniatur. Otwieranie i nawigacja mają używać tego samego modelu klatki,
żeby obraz, oznaczenia, numer i komunikaty zawsze dotyczyły tych samych danych.

## Zakres

- Układ i działania z [przyjętego podglądu](../issues/07-browsing-and-comparison.md),
  z doprecyzowaniami [przekazania](../issues/09-implementation-handoff.md).
  Lokalne `image_view`, `filmstrip`, `session_controller` i istniejące `main_window`.
- Pusty start i rzeczywisty dialog MolTrack, automatyczne szukanie MPP,
  ręczne wskazanie oraz potwierdzenie zmienionego mtime. Postęp/anulowanie
  długiego odczytu. Dotychczasowa seria pozostaje do poprawnego zatwierdzenia nowej.
- Obraz original/aligned z zapisanej rejestracji, wejściowe ramki i maski,
  krycie masek, granica pola, oddzielne tło NaN/paddingu, informacje o jakości.
  Oznaczenia tylko do podglądu, kliknięcie pokazuje metadane bez zmiany `selected`.
- Automatyczny kontrast 2–98 na oryginalnej klatce i gamma; zoom/pan/dopasowanie.
  Rysowanie nie zależy od ukrytej konfiguracji pyqtgraph lub osi nm.
- Nawigacja przez numer, suwak, poprzednia/następna i miniatury. Odtwarzanie
  1/2/5/10/20 kl./s z pauzą, pełną kolejnością klatek i spowolnieniem, jeśli
  renderowanie nie nadąża. Koniec zatrzymuje, „Od początku” zaczyna od pierwszej.
- Odczyt i przygotowanie klatki poza wątkiem GUI, aktualizacja widgetów w GUI.
  Kontroler odrzuca spóźnione wyniki. Nie używa wymuszonego kończenia wątków.
  Miniatury i cache masek/wyrównania mają ograniczony koszt pamięci.

## Kryteria zakończenia

1. Integracja Qt/offscreen otwiera serię, zachowuje poprzednią po anulowaniu,
   błędzie i odrzuceniu mtime; spóźniony worker z dawnego importu jej nie podmienia.
2. Zmiana klatki zachowuje gamma/warstwy/zoom, a zmiana trybu ponownie dopasowuje
   widok zgodnie z kontraktem. Jedna klatka wyłącza zbędną nawigację i play.
3. Obraz, nakładki i numer klatki są publikowane razem. Pauza nie powoduje
   późniejszego dodatkowego kroku. Przy wolnym przygotowaniu play pokazuje
   kolejne klatki bez opuszczeń; ręczne przewijanie może anulować stare żądania.
4. Brak masek nie ukrywa ramek. Brak ramek nie jest opisany jako zero molekuł.
   Brak rejestracji pokazuje oryginał i jedynie poprawnie umiejscowione oznaczenia.
   Low confidence nie blokuje zapisanej rejestracji i pozostaje widoczne.
5. Testy renderowania obejmują piksel `[r,c]` przy odpowiednim bboxie,
   niekwadratowy wzorzec, ułamkowe translacje oraz NaN. Nie ma przesunięcia
   bboxów o pół piksela, obrotu drugi raz ani odbicia osi.
6. Gamma i normalizacja nie mutują danych; raw/aligned używają tego samego
   zakresu. Zoom/padding nie zmieniają poziomów. Stała i całkowicie niepoprawna
   klatka nie powodują dzielenia przez zero ani fałszywego obrazu pomiarowego.
7. Aplikacja działa bez modeli i bez uruchamiania analizy/rejestracji.
   Nie zawiera niedziałających przycisków zapisu lub metod z etapu 2.
8. W rozmiarze 1100 × 760 podstawowe działania są osiągalne, obraz i miniatury
   mają poprawne proporcje. Resizing/zoom nie przesuwa nakładek względem obrazu.

## Przekazanie

Commit, wyniki testów Qt, instrukcja otwarcia danych i lista znanych ograniczeń.
Kontrole pełnego TTMAPP i osobisty odbiór GUI wykonuje
[zadanie odbioru](03-acceptance.md). Źródeł prototypu HTML nie scalać do aplikacji.
