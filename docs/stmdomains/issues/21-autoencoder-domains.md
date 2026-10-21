# Czy AE i rVAE uczą się cech przydatnych do odkrywania domen?

ID: 21
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 17, 20

## Question

Czy mały autoenkoder oraz rVAE z ciągłymi zmiennymi pozwalają znaleźć
strukturę domen lepiej niż klasyczna tekstura? Sprawdzić korzyść z oddzielania
obrotu od treści, bez zadanej liczby kategorii. Przykład STM opisany
w [przeglądzie](../research-self-supervised-domain-learning.md) jest precedensem,
a nie gotowym rozwiązaniem: jego część dyskretna miała zadaną liczbę składowych.

## Porównanie

1. Wytrenować mały konwolucyjny AE i ciągły rVAE na identycznym zakresie
   nieoznaczonych danych według kroku 20. Zwykły VAE jest dodatkowym
   wariantem, jeśli pomaga oddzielić wpływ regularyzacji od wydzielania obrotu.
   Zapisać architekturę i wymiar cech; wymiar ten nie oznacza liczby domen.
2. Zacząć od wycinków obrazu w kilku skalach. Lokalna FFT może być osobnym
   wariantem w ustalonym budżecie; sam moduł widma nie zachowuje informacji
   o fazie potrzebnej do granic przesunięcia. Nie zastępować nim po cichu
   informacji przestrzennej ani surowych pomiarów.
3. Zachować kąt jako osobny wynik. Na kontrolach sprawdzić, czy opisuje
   orientację sieci, a nie kształt jednej molekuły, brzeg lub pas skanowania.
   Uwzględnić równoważne kierunki sieci; nie zakładać z góry symetrii M6.
   Typ ma zachować rozstaw i strukturę, a obrót może rozdzielać domeny.
4. Ciągłe cechy poddać grupowaniu bez zadanego `K`, z możliwością jednej
   grupy, oraz osobnej ocenie porządku i łączności. Dopuścić zero domen,
   brak danych i niejednoznaczność. Nie nazywać klastra domeną tylko dlatego,
   że ma podobną rekonstrukcję. Katalog jest wspólny dla badanego zakresu.
5. Porównać z wynikiem klasycznej tekstury z kroku 17 przy wspólnej procedurze
   oceny i możliwie tych samych etapach grupowania oraz łączenia. Ujawnić
   konieczne różnice; sukces tekstury nie jest warunkiem próby AE.

## Dane i kryteria porównania

Obowiązują miary i kontrole kroku 14 oraz podział, budżet i powtórzenia
z kroku 20. Ocenić rozstaw, orientację, granicę przesunięcia, pojedyncze
defekty, pas nieuporządkowany, szum, pasy skanowania i niepełne centra.
Raportować fałszywe domeny, scalenia/podziały, odmowy i stabilność katalogu
przy zmianie ziarna i zakresu; nie wybierać modelu tylko po błędzie rekonstrukcji.
Sprawdzić, czy cechy nie dzielą danych głównie według jasności lub numeru klatki.

Po zamrożeniu konfiguracji i predykcji pokazać pełne klatki oraz częściowe
referencje TTMAPP. Ich kolory opisują głównie orientacje, a nie trzy typy.
Zmiana samych referencji nie wpływa na model ani predykcję. Wcześniej
używane ramki pozostają oceną częściową, nie niezależnym testem.

## Wynik do omówienia

Odtwarzalny prototyp, tabela kontroli, nakładki pełnych pól i porównanie
AE/rVAE z teksturą, z kosztem treningu, inferencji, pamięci i checkpointów.
Rozdzielić wynik transdukcyjny od próby przenoszenia oraz brak uruchomienia
od nieskuteczności uruchomionej metody. Udokumentowany wynik negatywny
może zakończyć badanie po omówieniu; niska strata sama go nie zalicza.

Wnioski trafiają do kroku 23. Zastosowanie modelu w aplikacji i przyjęcie
warunków odmowy pozostają zakresem odbioru 13.

## Dependencies

- [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](17-image-texture-domains.md)
- [Jak przygotować odtwarzalny trening bez etykiet domen?](20-self-supervised-training-preparation.md)
