# Czy maskowane odtwarzanie obrazu uczy relacji potrzebnych do domen?

ID: 25
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 23

## Warunek podjęcia

Rozszerzenie warunkowe: krok 23 wskazuje konkretną lukę w reprezentacji
otoczenia i wybiera tę próbę. Obecnie nie wybrano go do wykonania.

## Question

Czy przewidywanie zakrytych fragmentów zmusza model do uczenia układu
molekuł skuteczniej niż zwykły AE lub lokalne SSL? Sprawdzić mały model
maskowany inspirowany MAE z [przeglądu](../research-self-supervised-domain-learning.md),
bez rozpoczynania od dużego treningu modelu podstawowego.

## Porównanie

- Zacząć od małego encodera i masek obejmujących fragmenty otoczenia,
  nie tylko pojedyncze piksele. W protokole zapisać skalę okien, rozmiar,
  udział i sposób losowania masek; sprawdzić kilka wariantów w budżecie
  wybranym w kroku 23. Wszystkie skale mają znaczenie w geometrii pomiaru.
- Oddzielić maskowanie zadania uczenia od braku pomiaru i paddingu.
  Stratę liczyć wyłącznie dla rzeczywiście zmierzonych danych; wartości
  poza polem nie są prawdą do rekonstrukcji. Rekonstrukcja nigdy nie
  zastępuje oryginalnego MPP ani dowodu istnienia molekuły.
- Porównać ze zwykłym AE o zbliżonej pojemności oraz lokalnym SSL
  z pierwszych prób. Sprawdzić, czy zysk pochodzi z maskowania, większego
  kontekstu czy samej wielkości modelu. Zwiększenie sprzętu wymaga pomiaru
  uzasadniającego daną hipotezę, a nie tylko mniejszej straty treningowej.
- Cechy lokalne przekazać do wspólnego grupowania, oceny porządku i granic.
  Zachować rozstaw, osobną orientację, zero/jedną/wiele domen i katalog
  wspólny dla zakresu. Dobra interpolacja jasności nie jest wynikiem domen.

## Wynik do omówienia

Obowiązują dane, podział, kontrola przecieku i powtórzenia kroku 20 oraz
miary kroku 14. Oprócz straty zapisać pełne nakładki, błędy i odmowy,
kontrole granic/rozstawu/orientacji, stabilność oraz koszty treningu
i zastosowania. Referencje służą tylko ocenie zapisanego wyniku.

Wynik to odtwarzalna próba i decyzja, czy maskowanie daje korzyść względem
wcześniejszych modeli. Wynik negatywny może zamknąć zadanie po omówieniu.
Wniosek trafia do odbioru 13 po uzupełnieniu jego zależności przy wyborze
rozszerzenia; nie wymaga automatycznego przejścia na większą kartę.

## Dependencies

- [Czy trening daje poprawę i które rozszerzenie warto wykonać?](23-training-comparison-and-next-step.md)
