# Czy lokalne uczenie podobieństwa poprawia wykrywanie domen?

ID: 22
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 17, 20

## Question

Czy cechy uczone przez zgodność lokalnych fragmentów pomagają odkrywać
domeny bez odtwarzania wszystkich pikseli? Pierwszym kandydatem jest mały
encoder z lokalnym zadaniem inspirowanym VICRegL, zgodnie z
[przeglądem](../research-self-supervised-domain-learning.md). To adaptacja
do STM, a nie potwierdzona w źródłach metoda domen molekularnych.

## Porównanie

- Uczyć zgodności dwóch przekształceń tego samego wycinka, zachowując
  mapowanie odpowiadających sobie lokalnych pozycji. Nie ograniczać modelu
  do jednego wektora całej klatki. Zastosować kontrolę degeneracji cech
  (wariancja/kowariancja); mierzyć, czy sieć nie zwraca stałego opisu.
- Zapisać użyte przekształcenia i ich zakres. Pierwsza próba dopuszcza
  kontrolowany szum, jasność i przesunięcie z zachowaniem korespondencji.
  Dowolne skalowanie może usunąć rozstaw, a identyczność po obrocie —
  orientację. Sąsiedztwo przestrzenne ani czasowe nie stanowi etykiety
  „ta sama domena”. Nie wymuszać rozdzielenia powtarzalnych otoczeń przez
  przypadkowo dobrane pary negatywne.
- Oddzielić opis typu od orientacji; gdy kąt pochodzi z dodatkowej
  geometrii/autokorelacji, pokazać to w konfiguracji i porównaniu.
  Zachować kontrolę granic przesunięcia i rzeczywistego rozstawu.
- Zastosować grupowanie bez ustalonego `K`, ocenę porządku i spójności
  przestrzennej według wspólnego protokołu. Dopuścić zero/jedną/wiele domen
  i odmowy, z katalogiem wspólnym dla zakresu. Klaster podobieństwa sam
  nie dowodzi domeny ani powierzchni płata.
- Porównać z teksturą z kroku 17 i pomocniczo z tym samym encoderem bez
  treningu, aby sprawdzić korzyść z uczenia. Zachować porównywalny budżet
  strojenia i ujawnić różnice etapów. Próba nie zależy od powodzenia AE
  i może przebiegać niezależnie od kroku 21.

## Dane i kryteria porównania

Wykorzystać manifest, kontrole i miary kroku 14 oraz protokół kroku 20.
Raportować utrzymanie rozstawu/orientacji, granice, defekty, scalenia,
podziały, odmowy, odporność na szum, artefakty i brak centrów. Sprawdzić
kilka ziaren i zakresów. Niski błąd zgodności, wysoka wariancja cech ani
atrakcyjny wykres projekcji nie zastępują tej oceny.

Referencje ujawnić po zapisaniu konfiguracji i wyniku; ich zmiana nie może
zmieniać predykcji. Raportować wyłącznie ocenę oznaczonych fragmentów,
bez globalnej trafności na nieoznaczonym otoczeniu. Rozdzielić uczenie
na obecnej serii od oceny na niewidzianych danych.

W [kontynuacji 19 z 2026-10-28](../translation-consistency-trial.md)
kryteria zgodności odrzucają wszystkie znane wnętrza TTMAPP; lokalny
sygnał w małym kole odrzuca też poprawne miejsca między molekułami.
Zachować osobną ocenę reprezentacji i podziału przed bramką oraz odmów
po bramce, aby nie przypisać ich automatycznie modelowi SSL. Same grupy
wyglądu nadal nie stanowią rozpoznanych domen. Użyte już kontrole
syntetyczne są materiałem rozwojowym, nie niezależnym testem nowej próby.

## Wynik do omówienia

Odtwarzalny prototyp z pełnymi nakładkami, tabelą kontroli, manifestem wag
i augmentacji oraz kosztem treningu i zastosowania. Omówić korzyść względem
tekstury i modelu bez treningu oraz konkretną lukę. Wynik negatywny może
zamknąć próbę po omówieniu. Zestawienie z AE i gotowymi modelami nastąpi
w kroku 23; odbiór do aplikacji nadal w kroku 13.

## Dependencies

- [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](17-image-texture-domains.md)
- [Jak przygotować odtwarzalny trening bez etykiet domen?](20-self-supervised-training-preparation.md)
