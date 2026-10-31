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

**Aktualizacja przyjęta — 2026-10-31:** po
[badaniu usprawnień](../research-domain-plan-improvements.md) rozstrzygamy
także źródło błędu: cechy, relacje, podział lub odmowy. Obowiązuje
[wspólny protokół 20](20-self-supervised-training-preparation.md#wspólny-protokół-relacji-i-podziału),
realizowany w 21/22, bez nowego ticketu przygotowawczego. Zmiana planu nie
uruchamia badań; status pozostaje `open`, a 24–26 nadal są warunkowe.

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
- Zestawić cztery pola porównania: zachowane/nowe cechy i zachowane/nowe
  wykorzystanie relacji oraz podział. Pokazać lokalne krawędzie, nie tylko
  czyste wnętrza, i osobno wynik przed/po filtrze wiarygodności. Jeśli nowy
  podział otrzymał dodatkowe informacje o granicy, nie przypisywać całej
  korzyści solverowi. Wskazać, czy poprawiono także końcowe propozycje domen.
- Dla każdego głównego kandydata podać spełnienie lub niespełnienie
  kryteriów zamrożonych w 20: scaleń/podziałów, zerowej/jednej domeny,
  użytecznego zakresu przypisań, stabilności i kosztu. Mało błędów przy
  niemal pełnej odmowie nie stanowi sukcesu. TTMAPP oceniać w dostępnym
  zakresie referencji, bez ogólnej dokładności lub dokładnych granic.

## Wybór następnego kroku

Najpierw podjąć decyzję o kontynuacji na podstawie powyższych kryteriów.
Gdy brak poprawy w ustalonym budżecie, zakończyć dany kierunek i zapisać
konkretną lukę. Rozszerzenie można wybrać tylko wtedy, gdy jego hipoteza
odpowiada rozpoznanej przyczynie błędu. Samo ukończenie treningu nie
uzasadnia kolejnego rozszerzenia. Gdy poprawa wystąpiła,
opisać jej zakres i ograniczenia; kwalifikacja do aplikacji nadal wymaga 13.

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
