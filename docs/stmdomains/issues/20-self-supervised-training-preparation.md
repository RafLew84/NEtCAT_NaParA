# Jak przygotować odtwarzalny trening bez etykiet domen?

ID: 20
Type: task
Labels: wayfinder:task
Mode: AFK
Status: resolved
Assignee: Codex — domains/start
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 14

## Answer — 2026-10-31

Przygotowanie wykonane: [raport](../self-supervised-training-preparation.md),
[protokół](../self-supervised-training-protocol.md),
[manifest](../self-supervised-training-manifest.json).
24 pełne klatki, 38 622 rekordy wycinków, 25 530 z pełnym wsparciem;
rozłączne czasowo/przestrzennie części transferu oraz osobna transdukcja.
Odtworzenie z blokadą referencji i usunięciem centrów potwierdza niezależność
siatki. Zarezerwowano 81 nowych realizacji syntetycznych do późniejszej oceny.

Na RTX 5090 sprawdzono obliczenia i pełne wznowienie checkpointu w nowych
procesach dla trzech ziaren: wynik bitowo identyczny. Przeszło 78 testów.
Zamknięto format relacji/wyników, porównanie 2 × 2, budżet i liczbowe kryteria.
CUDA `grid_sample` nie daje ścisłego deterministycznego backward; protokół
rVAE wskazuje przetestowany obrót współrzędnych przed dekoderem.

To gotowe przygotowanie, bez treningu właściwych modeli lub oceny domen.
Niska wiarygodność rejestracji, mała część train i jedna akwizycja ograniczają
wnioski o przenoszeniu. Kolejne zadania to niezależne 21 i 22, potem 23.
Kod i dokumentacja na `domains/start`; commit podany w przekazaniu/odpowiedzi.

## Question

Przygotować dane, protokół i środowisko dla prób uczenia reprezentacji STM
bez ręcznych klas domen. To rozszerzenie wspólnego zestawu, nie jego zamiana
ani trening docelowego detektora. Podstawa: [ostatni przegląd](../research-self-supervised-domain-learning.md).

**Aktualizacja przyjęta przez użytkownika — 2026-10-31:** wdrażamy
[usprawnienia planu](../research-domain-plan-improvements.md). Przygotowanie
ma określić wspólny protokół relacji i granic dla 21/22. Pilot wykonujemy
w tych dwóch próbach, bez nowego ticketu przygotowawczego i bez ponownego
otwierania 19. W chwili przyjęcia aktualizacji zadanie było `open`;
aktualne wykonanie opisano w Answer powyżej.

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

## Wspólny protokół relacji i podziału

Protokół obowiązuje próby 21/22 i ich ocenę w 23. Celem jest poprawa
wykrywania domen, a grupowanie cech pozostaje etapem pośrednim.

- **Geometria i relacje:** dla otoczenia zapisać ID klatki/elementu,
  współrzędne `raw_edge_xy`, jednostki, skalę i wsparcie w polu pomiarowym;
  dla pary — ID obu końców, regułę sąsiedztwa oraz nakładanie się okien.
  Osobno zapisywać podobieństwo struktury/rozstawu, zgodność orientacji,
  przesłankę nieciągłości lub przesunięcia wzoru i dostępność danych.
  Brak danej jest jawny; nie zmienia się automatycznie w zgodność ani
  granicę. Wartość podobieństwa nie jest skalibrowanym prawdopodobieństwem.
- **Wyjścia:** zachować propozycję podziału, dowody porządku/granicy,
  ocenę wiarygodności i powody odmowy oraz osobno typ i orientację.
  Propozycja może powstać bez znanego typu. ID domen dotyczy jednej klatki;
  wspólny katalog nie łączy odległych obszarów w jedną domenę. Obecność
  materiału jest osobną informacją; nieporządek, niejednoznaczność i brak
  danych pozostają rozróżnione. Etykiety solvera nie stają się automatycznie domenami;
  otoczka przypisanych centrów nie jest potwierdzonym konturem lub powierzchnią.
- **Budżet przed treningiem:** zapisać hipotezę, jeden zachowany zestaw
  cech i podziału, głównego kandydata uczonego, dozwolone skale/augmentacje,
  liczbę konfiguracji i ziaren, sposób wyboru checkpointu oraz limit kosztu.
  Ustalić też liczbowe kryteria kontynuacji: tolerancje scaleń/podziałów,
  zachowanie na zerowej/jednej domenie, minimalny zakres przypisań i korzyść
  względem punktu odniesienia. Wartości lub zamkniętą procedurę ich kalibracji
  ustalić na danych rozwojowych przed końcową oceną, bez ręcznych ramek.
  Nie rozszerzać budżetu po niekorzystnym wyniku, aby szukać zwycięzcy.

Pierwsze porównanie ma cztery pola, z tymi samymi klatkami i porównywalnym
wsparciem otoczeń. Kolejne reprezentacje oceniać jako osobne ograniczone
porównania; nie tworzyć iloczynu wszystkich historycznych konfiguracji.

| | Zachowany sposób podziału | Nowe wykorzystanie relacji i podział |
| --- | --- | --- |
| Zachowane cechy klasyczne lub zamrożone | Punkt odniesienia | Wpływ relacji i podziału |
| Nowe cechy AE/SSL | Wpływ uczenia przy zachowanym podziale | Wpływ połączenia zmian |

Kandydatem na **jeden** nowy sposób podziału jest Mutex Watershed (MWS)
z relacjami przyciągającymi i odpychającymi, bez zadanej liczby segmentów.
To kandydat eksperymentalny, nie przyjęty detektor STM. Zachować porównywalny
graf, udokumentować wagi, ich normalizację, parametry i remisy. Wpływ samego
solvera można mierzyć tylko przy równoważnej dostępnej informacji; nowe
relacje, których stary podział nie obsługuje, oznaczają wspólną zmianę
informacji i solvera. Nie przypisywać całego zysku samemu MWS. W 19 był już
graf FH i ocena krawędzi; nie powtarzać strojenia tych prób jako nowej hipotezy.

W 21/22 wykonać krótki techniczny test podziału na syntetycznych relacjach
ze znaną odpowiedzią. To sprawdzenie implementacji, nie nauka domen ani
wynik skuteczności; idealne relacje nie trafiają do predykcji TTMAPP.
Prawda syntetyczna służy ocenie i temu testowi technicznemu, nie uczeniu
modelu relacji. Wspólne zapisane bazy można wykorzystać w obu próbach,
ale ich współdzielenie nie tworzy zależności 21 od 22 ani odwrotnie.
Pełne próby relacji i podziału nie są warunkiem zakończenia przygotowania 20.

Ocena musi obejmować rzeczywiste krawędzie między sąsiednimi otoczeniami,
także z oknami przecinającymi granicę. Same odległe, czyste wnętrza nie
wystarczą. Kontrole obejmują zmianę orientacji/rozstawu, granicę przesunięcia,
defekt, dwie oddzielone części tej samej sieci, brak centrów bez ubytku
materiału, pustą przerwę, nieporządek i niedostateczne dane. W każdej części
porównania pokazać propozycje przed filtrem wiarygodności i wynik po nim.

Raportować osobno błędne scalenia i podziały, fałszywe domeny, odmowy,
stabilność oraz udział przypisanych elementów z jawnym mianownikiem.
Zestawić błędy przy porównywalnym udziale przypisań; odrzucenie wszystkiego
nie daje dobrego wyniku, a brak ocenialnych par daje brak miary, nie zero
błędów. Udział przypisań nie jest powierzchnią materiału. Na syntezie
oceniać także granice z ustaloną tolerancją; na TTMAPP tylko ocenialne pary
i wnętrza częściowych referencji, bez globalnego IoU lub dokładnej prawdy
przybliżonych ramek. Zachować pełne nakładki i nieprzypisane miejsca.
Obecne referencje są materiałem rozwojowym; nowe realizacje syntetyczne
odłożyć przed strojeniem. Zmiana referencji nie zmienia uczenia, wyboru
checkpointu ani predykcji. Potrzeba dodatkowych oznaczeń wynika dopiero
z konkretnej nierozstrzygniętej oceny.

## Warunek zakończenia zadania

- Gotowy manifest i powtarzalny generator wycinków z kontrolą geometrii,
  podziału oraz braku ramek/etykiet domen na wejściu. Zmiana samych
  referencji nie zmienia próbek; brak centrów nie zmienia wariantu siatki.
- Krótka próba techniczna potwierdza obliczenia GPU, pomiar czasu/VRAM/RAM
  i wznowienie checkpointu w zapisanej tolerancji. Nie dowodzi jakości domen.
- Określono budżet, zakres pierwszego porównania, sposób wyboru checkpointu
  bez referencji i format wyników zgodny z krokiem 14. Braki niezależnych
  danych opisano jawnie; nie blokują próby na obecnej serii.
- Zapisano format relacji i rozdzielonych wyjść oraz plan porównania 2 × 2
  z hipotezą, limitem wariantów i kryteriami kontynuacji według powyższego
  protokołu. Wykonanie porównania pozostaje w 21/22, a decyzja o wyniku w 23.
- Jest polecenie odtworzenia i raport wykonanych sprawdzeń. Gdy trening
  technicznie nie działa, opisać konkretną przeszkodę; nie zastępować próby
  samym opisem sprzętu i nie oznaczać zadania jako gotowe.

Pierwsze przygotowanie dotyczy 32 GB VRAM / 128 GB RAM. Drugi komputer
96 GB i Colab pozostają opcjami wynikającymi z oceny kosztu i korzyści
w kroku 23; ich dostępność nie blokuje tego zadania.

## Dependencies

- [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](14-unsupervised-input-and-controls.md)

## Historyczny stan po zamknięciu 19, przed wykonaniem 20 — 2026-10-31

Użytkownik zakończył [serię analiz 19](19-frozen-feature-domains.md).
Niniejsze przygotowanie pozostaje **`open`, nierozpoczęte**, jako kolejny
zaplanowany krok do osobnego podjęcia. Nie uruchomiono treningu ani prób GPU.

Do protokołu przenosimy wnioski 19: ocenę cech/podziału i odmów oddzielnie,
kontrole brakujących oznaczeń niezależne od rzeczywistego nieporządku,
kontrole niezależnych rzędów i pustych przerw oraz jawny brak wystarczających
powtórzeń. Porównania mają zachować wyniki klasyczne i zamrożonych sieci.
Znane już kontrole są materiałem rozwojowym; nowe realizacje i ewentualne
niezależne akwizycje służą późniejszej ocenie. Nie używamy ręcznych domen
jako etykiet treningowych, wyboru checkpointu ani oczekiwanej liczby grup.

## Wcześniejszy kontekst i następne pytania

Po [próbach kryterium porządku 19](../translation-consistency-trial.md)
(2026-10-28) proponowano przygotowanie 20. Użytkownik następnie wybrał
pozostanie przy 19 i [audyt odmów](../vector-refusal-audit.md): **wtedy 20
odłożono**. Tę serię 19 zakończono zgodnie z aktualnym stanem powyżej;
przygotowanie 20 nie zostało wykonane. Do przyszłego protokołu porównania włączyć zapis
reprezentacji/podziału przed bramką oraz odmów po bramce. Wykazano
zarówno całkowite odrzucanie znanych wnętrz TTMAPP, jak i odrzucanie
poprawnych miejsc siatki między molekułami. Nowego modelu nie oceniać
wyłącznie przez taki filtr; same klastry bez oceny porządku również
nie są dowodem domen. Znane już kontrole rzędów, różnych sieci i przerw
zachować jako rozwojowe, a nowe realizacje odłożyć przed doborem parametrów.

- [Czy AE i rVAE uczą się cech przydatnych do odkrywania domen?](21-autoencoder-domains.md)
- [Czy lokalne uczenie podobieństwa poprawia wykrywanie domen?](22-local-self-supervised-domains.md)
