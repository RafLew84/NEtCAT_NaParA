# Jak przygotować odtwarzalny trening bez etykiet domen?

ID: 20
Type: task
Labels: wayfinder:task
Mode: AFK
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 14

## Question

Przygotować dane, protokół i środowisko dla prób uczenia reprezentacji STM
bez ręcznych klas domen. To rozszerzenie wspólnego zestawu, nie jego zamiana
ani trening docelowego detektora. Podstawa: [ostatni przegląd](../research-self-supervised-domain-learning.md).

## Zakres przygotowania

- Korzystać z surowych obrazów MPP i geometrii z kroku 14. Pobierać wycinki
  kilku skal z całych oryginalnych pól: regularnej siatki oraz, osobno,
  otoczeń wszystkich poprawnych centrów molekuł. Zapisać pozycję i wsparcie
  każdego wycinka. Bez gamma, paddingu, ręcznych ramek i etykiet MolTrack.
- Rozdzielić dwa protokoły: uczenie na całym analizowanym zakresie
  (transdukcyjne, opis obecnej serii) oraz uczenie na części i ocenę na
  niewidzianych danych. Nie przedstawiać pierwszego jako generalizacji.
- Podział trening/walidacja/test ustalić przed wycinaniem okien. Zapisać
  bloki czasu i przestrzeni, wspólny układ współrzędnych oraz bufory
  uwzględniające maksymalne wsparcie wycinka i augmentacji. Nakładające się
  widoki tego samego obszaru, także po rejestracji, nie mogą udawać
  niezależnych przykładów. Sąsiednie klatki tej samej akwizycji nadal są
  skorelowane; bez osobnej akwizycji ograniczyć wniosek o przenoszeniu.
- W próbie przenoszenia normalizację, redukcję wymiaru, katalog i reguły
  grupowania dopasować na części uczącej, następnie zamrozić. Nowe wzory
  mogą pozostać nieprzypisane. Ponowne grupowanie razem z testem jest
  osobną próbą transdukcyjną, a nie oceną zamrożonego modelu.
- Opisać dozwolone augmentacje i ich zakres. Zachować informację o skali,
  orientacji i granicy przesunięcia; nie narzucać zgodności różnych miejsc
  ani klatek tylko dlatego, że są sąsiednie. Oddzielić dane i ziarna do
  rozwoju od końcowych kontroli oceny. Ramki referencyjne nie służą
  treningowi, wyborowi checkpointu ani strojeniu parametrów.
- Przygotować wspólny zapis konfiguracji: hashe danych, split, sampler,
  normalizacja, skale, augmentacje, kod/model, seed, optimizer, harmonogram,
  batch efektywny, precyzja, warunek zatrzymania i budżet prób. Przed
  porównaniem ustalić liczbę wariantów i powtórzeń, z co najmniej trzema
  ziarnami dla głównych kandydatów; każdą redukcję zakresu uzasadnić.
- Sprawdzić krótki krok forward/backward na RTX 5090 w `netcat`, dostępność
  potrzebnych operacji i pamięć. Ustalić budżet na podstawie pomiaru, bez
  zakładania czasu pełnego treningu. Ewentualne zależności eksperymentu
  izolować od wspólnych wymagań aplikacji.
- Zapisywać checkpoint obejmujący wagi, optimizer, harmonogram, stan
  generatorów i postęp, tak aby trening dało się wznowić. Wagi i tablice
  pozostają lokalnie poza Git; wersjonujemy kod/protokół i małe manifesty.

## Warunek zakończenia zadania

- Gotowy manifest i powtarzalny generator wycinków z kontrolą geometrii,
  podziału oraz braku ramek/etykiet domen na wejściu. Zmiana samych
  referencji nie zmienia próbek; brak centrów nie zmienia wariantu siatki.
- Krótka próba techniczna potwierdza obliczenia GPU, pomiar czasu/VRAM/RAM
  i wznowienie checkpointu w zapisanej tolerancji. Nie dowodzi jakości domen.
- Określono budżet, zakres pierwszego porównania, sposób wyboru checkpointu
  bez referencji i format wyników zgodny z krokiem 14. Braki niezależnych
  danych opisano jawnie; nie blokują próby na obecnej serii.
- Jest polecenie odtworzenia i raport wykonanych sprawdzeń. Gdy trening
  technicznie nie działa, opisać konkretną przeszkodę; nie zastępować próby
  samym opisem sprzętu i nie oznaczać zadania jako gotowe.

Pierwsze przygotowanie dotyczy 32 GB VRAM / 128 GB RAM. Drugi komputer
96 GB i Colab pozostają opcjami wynikającymi z oceny kosztu i korzyści
w kroku 23; ich dostępność nie blokuje tego zadania.

## Dependencies

- [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](14-unsupervised-input-and-controls.md)

## Następne pytania

Po [próbach kryterium porządku 19](../translation-consistency-trial.md)
(2026-10-28) przygotowanie 20 jest proponowanym następnym krokiem;
nie zostało przez to wykonane. Do protokołu porównania włączyć zapis
reprezentacji/podziału przed bramką oraz odmów po bramce. Wykazano
zarówno całkowite odrzucanie znanych wnętrz TTMAPP, jak i odrzucanie
poprawnych miejsc siatki między molekułami. Nowego modelu nie oceniać
wyłącznie przez taki filtr; same klastry bez oceny porządku również
nie są dowodem domen. Znane już kontrole rzędów, różnych sieci i przerw
zachować jako rozwojowe, a nowe realizacje odłożyć przed doborem parametrów.

- [Czy AE i rVAE uczą się cech przydatnych do odkrywania domen?](21-autoencoder-domains.md)
- [Czy lokalne uczenie podobieństwa poprawia wykrywanie domen?](22-local-self-supervised-domains.md)
