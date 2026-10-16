# STM Viewer

Pojęcia przeglądania i wyrównywania obrazów STM.

## Language

**Seria**:
Uporządkowany zbiór klatek otwartych wspólnie w programie. Pochodzi z plików
STP/S94 albo z jednego wieloklatkowego pliku MPP.

**Klatka**:
Pojedynczy obraz STM w serii. Plik MPP zawiera wiele klatek.

**Pozycja w serii**:
Bieżące miejsce klatki w uporządkowanej serii, numerowane od 1 do liczby klatek.
Nie jest identyfikatorem klatki źródłowej.

**Pochodzenie klatki**:
Plik źródłowy i, dla MPP, pierwotny numer klatki w tym pliku.
Identyfikuje obraz niezależnie od jego pozycji w bieżącej serii.

**Czas pomiaru klatki**:
Czas przypisany obrazowi w danych źródłowych, jeśli jest dostępny.
Nie jest czasem wyświetlania klatki podczas odtwarzania.

**Oryginał (original)**:
Obraz klatki przed zastosowaniem rejestracji w bieżącej serii.

**Rejestracja**:
Wyznaczenie dopasowania położenia klatek serii względem wspólnego odniesienia.
_Avoid_: registration jako osobna polska nazwa operacji

**Obraz wyrównany (aligned)**:
Obraz klatki po zastosowaniu wyznaczonego dopasowania, umieszczony we wspólnym
obszarze serii. Dostępny jako alternatywny widok do oryginału.
_Avoid_: registered jako osobny rodzaj obrazu

**Brakujący piksel**:
Miejsce wspólnego obszaru obrazu, dla którego dana klatka nie dostarcza pomiaru.
Nie jest to pomiar o wartości zero.
