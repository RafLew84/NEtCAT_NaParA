# Protokół diagnozy opisu otoczenia — 24a

Data: 2026-11-01. Użytkownik zlecił wykonanie zaproponowanej po 24 próby.
To diagnoza na **znanych kontrolach**, nie nowa ocena held-out. Nie zmieniamy
zamrożonego eksperymentu 24, jego interpretacji ani dotychczasowych danych.

## Pytanie i zamknięta macierz

Sprawdzamy, czy usunięcie asymetrii wyboru punktów na granicy okna 72 usuwa
sztuczne domeny w pojedynczej sieci i zachowuje granice orientacji/fazy.
Porównujemy wyłącznie trzy zapisane główne encodery transferowe 24
(sce_scale, ziarna 20261101–20261103) oraz ich własne inicjalizacje.
Nie wybieramy modelu na podstawie wyników tej diagnozy.

1. **closed72:** dokładne zapisane wejście i wyniki 24 — baza.
2. **halfopen72:** punkty o współrzędnych względem korzenia w [-36,36)
   w obu osiach. Dolny brzeg: delta>=-36-1e-10; górny: delta<36-1e-10.
   Opisy 57 przeliczamy wewnątrz nowego ego. Promień krawędzi przypinamy
   z oryginalnego closed72, aby zmiana nie dobierała nowego rozstawu.
3. **root_only:** oryginalne 57 cech korzenia, jeden węzeł z pętlą własną,
   te same dwie warstwy encodera. To ablacja agregacji, nie naprawiony GNN.

Wspólną klasyczną bazą jest root57 z 24. Daje to 19 reprezentacji:
1 klasyczna + 3 tryby × 2 stany wag × 3 ziarna. Każda otrzyma FH k=4 i MWS,
łącznie **3534 wyniki na 93 istniejących kontrolach**. Transdukcja, SCE-only,
nowe pomiary i ponowna ocena TTMAPP nie należą do tej małej próby.

Adaptery/PCA/kwantyle i katalogi z 24 pozostają niezmienione, bez ponownego
dopasowania. Tak samo graf podziału i bramka geometryczna/minimum 8.
Zmiana wejścia względem treningu jest jawna: mierzymy zachowanie zamrożonej
procedury po konkretnej zmianie opisu, bez twierdzenia, że to optymalnie
wytrenowany nowy model. Żadnego skalowania lub uśredniania orientacji.

## Stałe wejście i mianowniki

Używamy wszystkich 93 kontroli 24, z ziarnami 920021–920023, bez wybierania
przypadków po wyniku. **S24** oznacza te same dostępne ID przy pełnym 72 px:
8350 centrów łącznie, w pojedynczej sieci 121 na realizację. Każdy wariant
zachowuje te ID, dostępność, jednostki i graf podziału. Brak przypisania
pozostaje w mianowniku. Obraz jest wyłącznie tłem galerii.

Wariant halfopen może pomijać punkty dokładnie na brzegu ego; nie usuwa
korzeni ocenianych jako S24. Root_only zachowuje cały pierwotny opis B24
korzenia. Nie dodajemy fikcyjnych centrów, odbicia ani dopełnienia pomiaru.
Nie zwiększamy pola, nie poszerzamy pasów 20, nie dopasowujemy progów.

Dodatkowy audyt opisuje wymagane nieucięte sąsiedztwo: węzły osiągalne
w dwóch krokach oraz obwiednia ich opisów R24. Warunek, że obwiednia mieści
się w ego 72 i pomiarze, jest konserwatywnym certyfikatem przy przypiętym
promieniu krawędzi. Nie służy filtrowaniu wyniku lub zmniejszeniu mianownika.
Ograniczone otoczenie jest definicją starego modelu; ten audyt pyta o kompletność
względem sąsiedztwa bez jego ucinania, nie o wyciek danych w 24.

## Kryteria przed obliczeniami

A. **Usunięcie artefaktu single:** dokładnie jedna domena i 121/121 przypisań
przed oraz po odmowach, we wszystkich trzech realizacjach i ziarnach danego
stanu wag. Odrzucenie 21 korzeni brzegowych nie zalicza poprawy.

B. **Prawdziwe granice:** osobno two_orientations, orientation_8deg,
different_spacing, phase_boundary. Przed i po odmowach zachowujemy kryteria 24: coverage>=0.50,
każda część>=0.30, merge<=0.02, split<=0.10 i F1>=0.70. Granice mierzymy
midpointami wszystkich lokalnych krawędzi, tolerancja 8 reference_px.
Zaliczenie A bez B oznacza jedynie usunięcie konkretnego artefaktu.

C. **Brak regresji wobec własnego closed72** na tych czterech rodzinach,
osobno przed i po odmowach: coverage nie spada o więcej niż 2 pp,
merge/split nie rosną o więcej niż 2 pp, F1 nie spada o więcej niż 0.02.
Null pozostaje brakiem dowodu, nie automatycznym sukcesem. Porównujemy
również pary na wspólnych przypisanych ID. Pełne wyniki zachowują każde
ziarno, każdą realizację i liczniki krawędzi przez prawdziwą granicę
z zerem, jednym i dwoma przypisanymi końcami.

Przyjęcie naprawy wymaga A+B+C dla wszystkich ziaren i realizacji,
bez wyboru korzystnego ziarna lub uśredniania ukrywającego niepowodzenie.
Root_only może uzyskać jedynie wynik diagnostyczny ablacji. Jitter fazy,
braki, duplikaty i negatywne rzędy raportujemy jako pozostałe stres-testy.
Puste noise/stripes nie potwierdzają rozpoznania negatywnego obrazu.
Brak prawdy dokładnej dla jakiejś miary nie staje się zerowym błędem.

## Budżet i odtwarzalność

**0 nowych treningów, 0 kroków optymalizacji**, CPU z jednym wątkiem,
1800 s CPU całej obliczeniowej próby i 4 GiB RSS na proces. Bez instalacji,
GPU, nowych skal, zastępczych wariantów lub strojenia po wynikach.
Wagi i adaptery są przypięte hashami. Kontrole są znane z 24; mimo to
nowe źródła/protokół/plan przypinamy przed obliczeniami, predykcje przed
ponownym otwarciem referencji do ich oceny.

Baseline to oryginalne cache i predykcje 24. Techniczny replay encodera CPU
może różnić się od oryginalnego CUDA o błąd numeryczny; sprawdzamy allclose
z atol/rtol 1e-5, nie zmieniamy bazowych etykiet. Audyt obejmuje semantykę
brzegów, permutację i translację, niezmienność root57, stałe ID/mianowniki,
niezmienione wagi/adaptery oraz brak przypisań bez wsparcia.

Wynik to raport, manifest i samowystarczalny HTML porównujący zapisane wyniki.
Dalsze uczenie lub 25/26 wymaga osobnego wyboru; tej diagnozy nie traktujemy
jako niezależnego dowodu generalizacji albo gotowego detektora.
