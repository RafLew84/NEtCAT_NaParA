# Czy dalsze uczenie gotowego modelu na STM poprawia odkrywanie domen?

ID: 26
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 23

## Warunek podjęcia

Rozszerzenie warunkowe: krok 23 wybiera adaptację i wskazuje konkretny
model dostępny po krokach 18–19 oraz oczekiwaną poprawę. Obecnie nie
wybrano go do wykonania. Brak takiego modelu wymaga doprecyzowania zakresu.

## Question

Czy dalsze uczenie bez etykiet na STM poprawia lokalne cechy gotowej
sieci względem jej niezmienionych wag? Kandydaci z
[przeglądu](../research-self-supervised-domain-learning.md) to samodestylacja
inspirowana DINO lub przewidywanie zakrytych reprezentacji inspirowane iBOT.
Nie jest to uczenie klas BLACK/RED/YELLOW ani trening od zera dużego modelu.

## Porównanie

- Ustalić zgodny wariant architektury, wag i zadania uczenia. Nie zakładać,
  że dowolny checkpoint DINOv2/DINOv3 można bez zmian użyć w kodzie DINO/iBOT.
  Zapisać pochodzenie, wersję i hashe, zakres zmienianych warstw, nauczyciela,
  regułę jego aktualizacji, głowicę treningową oraz kontrolę degeneracji.
- Zachować oryginalne wagi jako niezmieniony punkt odniesienia. Porównać
  te same lokalne cechy i warstwy przed i po adaptacji, przy tym samym
  wejściu, geometrii, ocenie porządku i procedurze grupowania. Kroki 18–19
  pozostają próbą zamrożonych modeli; nowy checkpoint ma osobną tożsamość.
- Nie utożsamiać liczby wewnętrznych wyjść zadania uczenia z liczbą typów
  lub domen. Końcowy opis jest ciągły, grupowanie nie ma zadanego `K`,
  a niejednoznaczność i zero/jedna/wiele domen pozostają dopuszczalne.
- Augmentacje mają zachować informację o rozstawie, orientacji i granicach.
  Nie wymuszać zgodności dowolnych miejsc w klatce lub kolejnych obrazów.
  Kontrolować utratę przydatnych cech po adaptacji i zależność od jasności.
- Trzymać się budżetu i protokołu kroku 20; jeśli konieczna jest większa
  karta lub Colab, zapisać pomiar i korzyść, checkpointy oraz odtwarzalne
  środowisko. Nie zmieniać wymagań wspólnych aplikacji na potrzeby próby.

## Wynik do omówienia

Tabela tych samych kontroli przed i po uczeniu, pełne nakładki, odmowy,
orientacja/rozstaw, granice, stabilność i koszt. Osobno wynik transdukcyjny
oraz przenoszenie przy zamrożonym modelu i katalogu, bez dopasowywania
do testu. Referencje nie wybierają wag ani checkpointu.

Raport i polecenie odtworzenia mają wykazać poprawę, pogorszenie albo brak
różnicy w wykrywaniu domen, a nie tylko spadek straty SSL. Brak zgodnej
implementacji pozostaje ograniczeniem technicznym, nie wynikiem jakości.
Po omówieniu także wynik negatywny kończy badanie. Wniosek trafia do
odbioru 13, którego zależności uzupełnia się przy wyborze rozszerzenia.

## Dependencies

- [Czy trening daje poprawę i które rozszerzenie warto wykonać?](23-training-comparison-and-next-step.md)
