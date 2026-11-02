# 19: Porównaj domeny z lokalnego FFT i NMF obrazu

**ID:** SD-V4-19

**What to build:** Użytkownik wybiera eksperymentalną analizę lokalnego widma obrazu, reguluje rozmiar okna oraz liczbę składowych i ogląda wynik przypisany do molekuł w tym samym widoku porównawczym co v0.4 i pomiary geometrii.

**Blocked by:** [06: Strojenie tworzenia domen i porównanie wyniku](06-tune-domain-formation.md), [16: Zobacz kierunek, rozstaw i jakość geometrii na obrazie](16-inspect-local-geometry.md).

**Status:** deferred — dalsza próba porównawcza, zapisana w planie; obecnie niewybrana do wykonania.

**Warunek wyboru:** Po ocenie 18 wskazać konkretną nierozwiązaną różnicę, którą mogą pokazać piksele, oraz ograniczony zakres próby. Ocena 18 wyznacza kolejność decyzji, nie zależność techniczną od biblioteki freud. Nie trzeba czekać na pozytywny wynik 18.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady rozszerzeń](README.md#rozszerzenia).

## Kryteria akceptacji

- [ ] Zaimplementowano jeden przebieg lokalnego FFT i NMF, wybrany oraz opisany przed oceną. Można wykorzystać SlidingFFTNMF lub odpowiednik o sprawdzonym pochodzeniu; dwie niezależne integracje nie są częścią zadania.
- [ ] UI steruje wielkością i krokiem okna oraz liczbą składowych NMF. Zakres okna widać na obrazie; jego jednostki i zależność od skali są jawne. Liczba składowych nie jest przedstawiana jako automatycznie ustalona liczba domen lub tryb Auto z 12.
- [ ] Wynik lokalnych okien jest przypisany do rzeczywistych ID i pozycji molekuł, a następnie do przestrzennie spójnych domen. Środki okien nie zastępują molekuł. Klasa widmowa, końcowa domena i brak wiarygodnego przypisania mają odrębne znaczenie.
- [ ] Okna z mieszaniną struktur, przy brzegu, z artefaktem lub zbyt małym wsparciem mogą pozostać nierozstrzygnięte. Oceniono kompromis rozmiaru okna na wąskich domenach; samo zwiększenie okna nie uchodzi za poprawę lokalizacji granicy.
- [ ] Pomiary obrazu są porównane z kierunkami i rozstawem z 16 w tych samych współrzędnych i jednostkach. Zgodność nie jest opisywana jako dwa statystycznie niezależne pomiary, ponieważ detekcje pochodzą z tego obrazu.
- [ ] Zachowano v0.4 i sposób porównania na wspólnych kontrolach, w tym granicy przesunięcia, oraz wskazanych klatkach TTMAPP. Zapisano skalowanie widm, zakres dopasowania NMF, ziarno i parametry; ustawienia nie są dobierane osobno po obejrzeniu każdej oceny.
- [ ] Długie obliczenia mają postęp i anulowanie, a duża liczba okien nie powoduje nieograniczonego wzrostu pamięci. Testy sprawdzają mapowanie okno–molekuła, rzeczywisty wpływ ustawień, powtarzalność i braki danych.
- [ ] Wynik próby, wykonany odbiór GUI i testy automatyczne są opisane oddzielnie; negatywny wynik pozostaje widoczny. Obowiązuje kontrola kodu i testów 1000/1500 linii oraz przekazanie ewentualnych zmian wspólnych zależności integratorowi.

## Test ręczny użytkownika

1. Na klatce wskazanej w ograniczonym planie próby uruchom lokalne FFT/NMF. Przełącz wynik z v0.4 i sprawdź, czy oznaczenia leżą na tych samych molekułach.
2. Osobno zmień okno i liczbę składowych. Zobacz rzeczywisty zakres okna oraz porównaj wąski obszar i granicę dwóch orientacji.
3. Wskaż molekułę i porównaj kierunek/okres uzyskany z obrazu z pomiarem centrów z 16. Niejednoznaczne okno ma dawać jawny brak wyniku, a nie wymuszoną klasę.
4. Otwórz kontrole brzegów, szumu i przesunięcia sieci, następnie anuluj przebieg na większym obrazie. Poprzednie poprawne wyniki pozostają dostępne.

## Granice zadania

Jedna metoda porównawcza. Nie obejmuje pełnej GPA, korekcji deformacji, nowego detektora molekuł ani zastąpienia wymagania 2D przez pojedyncze pasy. Wcześniejsze próby FFT/fazy pozostają punktem odniesienia.
