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

**Aktualizacja przyjęta — 2026-10-31:** po
[badaniu usprawnień](../research-domain-plan-improvements.md) nadajemy
priorytet lokalnemu SSL jako próbie cech z oceną relacji/granic według
[wspólnego protokołu 20](20-self-supervised-training-preparation.md#wspólny-protokół-relacji-i-podziału).
Pilot jest częścią 22 i nie wymaga nowej serii przygotowawczej ani powodzenia
21. Status pozostaje `open`; treningu jeszcze nie wykonano.

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
- Wykonać małe porównanie 2 × 2 z protokołu 20, z MWS jako kandydatem
  na jeden nowy podział. Sprawdzić relacje na rzeczywistych krawędziach
  sąsiedztwa wewnątrz domen i przez granice, również przy częściowo wspólnych
  oknach. Dobre grupowanie odległych czystych wnętrz nie zastępuje tej oceny.
  Oddzielić wpływ uczenia, nowych relacji i solvera. Nie wracać do strojenia
  wszystkich historycznych wariantów grafu lub filtrów z 19.

## Opcjonalny wariant zadania bliższego granicom

W budżecie ustalonym w 20 można sprawdzić **jeden** wariant inspirowany
INPAINTAFF: czy przewidywanie zakrytego fragmentu z otoczenia daje relacje
pomocne w odróżnianiu wnętrza domeny od przejścia przez granicę. Hipotezę
porównać z podstawowym lokalnym SSL na tych samych kontrolach orientacji,
przesunięcia wzoru, defektów i pustych przerw. To opcjonalne zadanie uczące,
nie automatyczne uruchomienie osobnej rodziny modeli lub kroku 25.

Oryginalna praca korzystała w pełnej segmentacji z maski obiektów lub sieci
uczonej na oznaczeniach; nie przenosimy tego nadzoru do naszej próby.
Uczenie nadal nie dostaje ręcznych domen ani masek materiału. Sam spadek
przewidywalności nie staje się etykietą granicy, a przewidywalna pusta przerwa
nie dowodzi wspólnej domeny. Obecność materiału i jej niepewność są osobnym
wynikiem. Źródło i ograniczenia opisuje [badanie](../research-domain-plan-improvements.md).

## Dane i kryteria porównania

Wykorzystać manifest, kontrole i miary kroku 14 oraz protokół kroku 20.
Raportować utrzymanie rozstawu/orientacji, granice, defekty, scalenia,
podziały, odmowy, odporność na szum, artefakty i brak centrów. Sprawdzić
kilka ziaren i zakresów. Niski błąd zgodności, wysoka wariancja cech ani
atrakcyjny wykres projekcji nie zastępują tej oceny.
Warunki kontynuacji, błędy przy porównywalnym udziale przypisań i kontrolę
odrzucenia wszystkiego określa protokół 20. Propozycje i końcowe wyniki
pokazać osobno. Zachować przypadki tej samej struktury z granicą przesunięcia
oraz braków oznaczeń bez rzeczywistej przerwy w materiale.

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
Raport zawiera cztery pola porównania i ocenę lokalnych relacji. Wskazuje,
czy ewentualna korzyść wynika z cech, informacji o granicach, podziału lub
zmiany odmów. Po wyczerpaniu budżetu nie dodawać wariantów tylko po to,
aby uzyskać dodatni wynik.

## Dependencies

- [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](17-image-texture-domains.md)
- [Jak przygotować odtwarzalny trening bez etykiet domen?](20-self-supervised-training-preparation.md)
