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

**Tempo odtwarzania**:
Zadana liczba klatek do wyświetlenia w ciągu sekundy podczas przeglądania serii.
Nie określa czasu wykonania pomiaru; rzeczywiste tempo może być niższe.

**Gamma podglądu**:
Korekcja jasności prezentowanego obrazu STM, niezależna od wartości pomiarowych.

**Obszar podglądu**:
Fragment obrazu widoczny w głównym podglądzie przy danym położeniu i powiększeniu.
Może obejmować całą klatkę lub jej wycinek.

**Oryginał (original)**:
Obraz klatki przed zastosowaniem rejestracji w bieżącej serii.

**Rejestracja**:
Wyznaczenie dopasowania położenia klatek serii względem wspólnego odniesienia.
_Avoid_: registration jako osobna polska nazwa operacji

**Klatka odniesienia**:
Klatka źródłowa, względem której określono położenia obrazów w wyniku rejestracji.
Jej pochodzenie identyfikuje odniesienie także wtedy, gdy nie ma jej już w bieżącej serii.

**Wynik rejestracji**:
Dopasowanie położenia klatek konkretnej serii, stanowiące podstawę ich
wspólnego widoku aligned.

**Pole oryginalnej klatki**:
Prostokątny obszar pochodzący z oryginalnego obrazu, umieszczony w układzie
wyniku rejestracji. Jego granice są niezależne od dostępności próbek aligned.

**Obraz wyrównany (aligned)**:
Obraz klatki po zastosowaniu wyznaczonego dopasowania, umieszczony we wspólnym
obszarze serii. Dostępny jako alternatywny widok do oryginału.
_Avoid_: registered jako osobny rodzaj obrazu

**Maska ważności aligned**:
Wskazanie miejsc wyrównanego obrazu, w których dostępne są ważne próbki
wyznaczone z pomiaru. Jest odrębna od granic pola oryginalnej klatki.

**Brakujący piksel**:
Miejsce wspólnego obszaru obrazu, dla którego dana klatka nie dostarcza pomiaru.
Nie jest to pomiar o wartości zero.

**Wartości obrazu STM**:
Liczby opisujące sygnał w pikselach klatki: z odczytu źródła dla original
lub po interpolacji rejestracji dla aligned. Są odrębne od jasności
używanej do wyświetlenia obrazu.

**Metadane towarzyszące MPP**:
Informacje zapisane w osobnym pliku powiązanym z filmem MPP, opisujące
pochodzenie, czasy, parametry i geometrię poszczególnych klatek.

**Klatka filmu AVI**:
Wyrenderowany obraz klatki serii wraz z wybranym tłem i opisami.
Jasność jego pikseli jest prezentacją danych, nie wartością pomiarową.

**Tempo filmu AVI**:
Liczba klatek wyświetlanych na sekundę zapisanego filmu.
Jest niezależna od tempa Play w aplikacji i od czasów pomiaru.

**Poziomy kontrastu**:
Wartości obrazu STM przypisane do czerni i bieli przy prezentacji obrazu.
Wyznaczają zakres jasności przed zastosowaniem gamma.
