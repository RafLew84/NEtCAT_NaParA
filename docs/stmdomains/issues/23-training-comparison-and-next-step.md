# Czy trening daje poprawę i które rozszerzenie warto wykonać?

ID: 23
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 19, 21, 22

## Question

Czy po pierwszych próbach uczenie reprezentacji daje korzyść uzasadniającą
koszt, czy wystarczają metody klasyczne lub gotowe cechy? Zestawić wynik
tekstury, zamrożonych modeli, AE/rVAE i lokalnego SSL na wspólnych danych.
To decyzja o dalszym badaniu, a nie odbiór produkcyjnej metody z kroku 13.

## Materiał do decyzji

- Tabela wspólnych kontroli, błędów i odmów, stabilności względem ziaren
  oraz zakresu. Oddzielić zero/jedną/wiele domen, typ/orientację, rozstaw,
  granice przesunięcia, nieporządek i brak danych; zobaczyć pełne nakładki.
- Rzeczywiste koszty treningu, zastosowania, pamięci i zapisu. Uwzględnić
  budżet strojenia, zakres dostępnych modeli i różnice etapów interpretacji.
  Brak uruchomienia nie jest porażką metody, a niższa strata nie jest poprawą
  wykrywania. Nie wymagać dodatniego wyniku któregokolwiek kandydata.
- Rozdzielić porządkowanie aktualnej serii od przenoszenia na niewidziane
  dane. Sprawdzić przecieki między oknami/klatkami oraz rolę używanych już
  referencji. Nowe oznaczenia lub akwizycje wskazać tylko dla konkretnej luki.

## Wybór następnego kroku

Każde rozszerzenie wymaga wskazania obserwowanego problemu, hipotezy,
porównania kontrolnego i ograniczonego budżetu:

- [Grafy molekuł](24-graph-self-supervised-domains.md): gdy centra są
  wiarygodne, a obraz/kontrast ogranicza reprezentację. Wynik geometrii
  z kroku 15 jest dodatkowym warunkiem tej próby.
- [Maskowany autoenkoder](25-masked-autoencoder-domains.md): gdy dotychczasowe
  cechy odtwarzają lokalny wygląd, lecz nie wykorzystują relacji w otoczeniu.
- [Adaptacja gotowego modelu](26-pretrained-self-supervised-adaptation.md):
  gdy zamrożone cechy są użyteczne, ale ujawniają konkretną lukę na STM.

Jeśli próby wskażą problem oddzielenia kąta od typu, można zamiast szerokiej
nowej rodziny zaproponować kontrolowany wariant encodera ekwiwariantnego
w odpowiednim tickecie, zgodnie z [badaniem](../research-self-supervised-domain-learning.md).
Nie uruchamiać wszystkich wariantów tylko dlatego, że są dostępne.

RTX 5090 pozostaje punktem startowym. Przejście na deklarowaną kartę
Blackwell Max-Q 96 GB lub Colab uzasadnić zmierzonym ograniczeniem pamięci
istotnym dla hipotezy, np. potrzebą większego kontekstu. Porównać jakość
z kosztem; sama dostępność VRAM nie jest przesłanką większego modelu.
Przy przenoszeniu zachować manifest, checkpointy, wersje i pomiar na obu
maszynach. Dostępność 96 GB/Colab nie warunkuje zakończenia tej decyzji.

## Warunek zakończenia

Po omówieniu zapisać datowaną decyzję: zakończyć tę serię porównań albo
podjąć wskazane rozszerzenia, z konkretną hipotezą i budżetem. Dopuszczalny
jest brak przydatnej metody i opis dalszej luki. Nie trzeba trenować kolejnego
modelu, żeby zakończyć to zestawienie.

Tickety 24–26 są warunkowe. Nie stają się automatycznie aktywne po zamknięciu
tego pytania. Wybrane rozszerzenie dopisać do `Blocked by` i `Dependencies`
odbioru 13 oraz diagramu, aby odbiór czekał na jego wynik. Pozostałe zachować
jako niewybrane albo zamknąć zakresowo z uzasadnieniem użytkownika; nie
oznaczać ich jako wykonane lub naukowo nieskuteczne. Odbiór 13 nie wymaga
realizacji wszystkich możliwych rodzin modeli.

## Dependencies

- [Czy gotowe cechy sieci pomagają odkrywać domeny bez przykładów?](19-frozen-feature-domains.md)
- [Czy AE i rVAE uczą się cech przydatnych do odkrywania domen?](21-autoencoder-domains.md)
- [Czy lokalne uczenie podobieństwa poprawia wykrywanie domen?](22-local-self-supervised-domains.md)
