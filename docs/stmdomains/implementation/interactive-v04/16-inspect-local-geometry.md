# 16: Zobacz kierunek, rozstaw i jakość geometrii na obrazie

**ID:** SD-V4-16

**What to build:** Użytkownik uruchamia pomiar bieżącej klatki, wskazuje molekułę lub domenę i widzi kierunek rzędów, rozstaw, zakres sąsiedztwa oraz jakość pomiaru. Opcjonalna nakładka pokazuje kierunek na tym samym obrazie co przypisania domen.

**Blocked by:** [05: Oblicz klasy i domeny bieżącej klatki z danych](05-analyze-current-frame.md).

**Status:** done — 2026-11-04, `c4b6c70`, poprawki `009f38f`, `97988c2`; wybrany wariant C.
**Odbiór ręczny użytkownika oczekuje.** [Raport i instrukcja](acceptance-16.md),
[protokół](geometry-method-v1.md), [przegląd](review-16.md).

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady rozszerzeń](README.md#rozszerzenia).

**Prototyp układów — 2026-11-04:** przygotowano A (panel boczny), B (tabela
pod obrazem), C (pływająca karta). [Uruchomienie, porównanie i źródło](prototype-16-layouts.md).
Źródło pierwotne: gałąź `prototype/stmdomains-geometry-layouts`, commit `2a31997`.
**Decyzja użytkownika 2026-11-04: wariant C — pływająca karta**, zwijana
i przenoszona między stronami obrazu. Wcześniejsza rekomendacja A nie została
wybrana. Pomiary prototypu są demonstracyjne; implementacja 16 oblicza je z danych.

## Kryteria akceptacji

- [x] Przycisk pomiaru liczy dane dla aktualnej klatki poza GUI, z postępem i anulowaniem. Wykorzystuje procedury pomiaru wzorowane na kodzie v0.4 i wcześniejszych próbach; wartości oblicza z otwartego obrazu i oznaczeń, bez odczytu historycznych wyników lub modeli.
- [x] Szczegóły molekuły pokazują kierunek wyróżnionych rzędów, rozstaw poprzeczny, miarę zgodności, liczbę wspierających punktów i rzeczywisty zasięg pomiaru. Rozstaw wzdłuż rzędów jest podawany tylko, gdy został osobno wiarygodnie wyznaczony; brak pomiaru nie staje się zerem.
- [x] Kierunek rzędów jest odróżniony od prostopadłego wektora częstości. Okres jest przeliczany zgodnie z konwencją częstości źródłowego algorytmu. Skala X/Y i transformacje raw/aligned są uwzględnione; nm pojawia się wyłącznie przy dostępnej kalibracji.
- [x] Wynik rozróżnia porządek w jednym kierunku, potwierdzoną sieć 2D i niewystarczające dane. Jeden silny pik nie potwierdza dwóch niezależnych kierunków; parametr symetrii nie jest liczbą klas.
- [x] Niepewność lub stabilność względem małej, zapisanej zmiany sąsiedztwa ma jawną definicję. Sama koherencja nie jest prawdopodobieństwem poprawności. Przy niejednoznaczności UI pokazuje nierozstrzygnięcie i nie rysuje pozornie pewnego kierunku.
- [x] Podsumowanie domeny uwzględnia symetrię kąta, rozrzut i liczbę poprawnych pomiarów. Nie uśrednia liniowo kątów po przeciwnych stronach zakresu ani nie utożsamia orientacji z typem.
- [x] Włączenie pomiarów i nakładek nie zmienia istniejących przypisań obliczonych metodą bazową aplikacji. Wyniki zachowują ustawienia, jednostki i identyfikację źródła.
- [x] Testy sprawdzają znany kierunek i okres, obrót, skalę anizotropową, raw/aligned, słabe wsparcie i brak kalibracji. Raport odróżnia wykonany test GUI od automatycznych sprawdzeń oraz potwierdza zasadę 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz TTMAPP, przelicz klatkę 259 i wybierz Pomierz geometrię. Kliknij molekuły w dwóch wizualnie różnych obszarach; zobacz liczby i kierunki na ich rzeczywistych pozycjach.
2. Włącz i wyłącz nakładkę, powiększ obraz i przełącz raw/aligned. Oznaczenia i kierunki muszą przekształcać się razem z obrazem, a przypisania domen pozostać takie same.
3. Otwórz dostarczony przykład o znanym kącie i rozstawie oraz jego obróconą kopię. Sprawdź wartości względem opisanych parametrów przykładu, także przy nierównej skali X/Y.
4. Sprawdź przykład pojedynczych rzędów, szumu i małej liczby punktów. Program ma pokazać właściwy zakres wniosku lub brak pomiaru, bez fikcyjnej sieci 2D.

## Granice zadania

To pomiar i wyjaśnienie wyniku obliczonego w aplikacji. Nie obejmuje segmentacji według nowych cech, katalogu typów, pełnego dopasowania dowolnej bazy molekularnej ani śledzenia w czasie. Gwyddion może służyć do sprawdzenia kilku wycinków, bez wymaganej integracji lub instalacji po stronie użytkownika. Paczka v0.4 nie jest potrzebna do uruchomienia pomiaru.
