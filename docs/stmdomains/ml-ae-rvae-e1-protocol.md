# E1 — protokół wykonawczy

Zapisany 2026-11-10 przed nowym przebiegiem E1, baza `bbfa417`, środowisko
`netcat`. To diagnostyka znanego pilota; żadna klatka nie staje się nowym,
niezależnym testem. Protokół i jego SHA-256 trafiają do manifestu przebiegu.

## Zakres zamrożony przed obliczeniami

- Wszystkie 105 obrazów z pilota 21: 24 rzeczywiste i 81 kontroli syntetycznych.
- Główna skala 48 px; własny graf siatki i osobno własny graf centrów molekuł.
  Nie przenosimy etykiet siatki na molekuły.
- AE i rVAE z32, każde ziarna 20261101–20261103, FFT bez ziaren; oba dawne
  reżimy transfer/transdukcja, oba podziały FH(k=4)/MWS: 5880 zapisanych wyników.
- Osiem kombinacji ACF × dodatkowy drugi kierunek widma × minimum.
  Próg ACF 0.37948280732455153, widmo >=0.25. Historyczne minimum to
  **4 punkty siatki / 8 centrów**, co doprecyzowuje skrót „cztery” w planie.
  Wyłączone minimum oznacza 1, nadal z przeliczeniem spójności.
- Bez treningu, inferencji encodera, refitu adaptera, kalibracji i wyboru
  zwycięskiego wariantu. Brakujące składowe bramki odtworzymy na oryginalnych
  natywnych oknach 48 px, identyczną normalizacją i kodem tekstury.
- Limit roboczy: 45 minut CPU procesu, 8 GiB RSS i 8 GiB nowych artefaktów.
  To limit wykonania, nie kryterium selekcji wyników. Przekroczenie kończy
  przebieg; nie redukujemy po cichu macierzy po obejrzeniu rezultatów.

## Niezmienniki i kontrola odtworzenia

Weryfikujemy hashe użytych zapisów względem zamrożenia 21; źródłowe NPZ
także według ich manifestów. Zachowujemy dokładne węzły, wsparcia, krawędzie
i propozycje. Transfer TTMAPP korzysta z **heldout** wyników i grafów;
wycięcie węzłów z pełnego grafu byłoby innym eksperymentem.

Każde odtworzone `order_pass` musi być identyczne ze starym, a wariant
111 musi odtworzyć wszystkie stare podziały. Wyniki ośmiu bramek zamrażamy
przed ich nową oceną referencją. Oracle powstaje osobno i jawnie korzysta
z prawdy generatora; nie przypisujemy mu statusu detektora.

Stałe H obejmuje wsparcie, zakres, poprawność i skończoność pomiarów,
dodatnią energię; brak cech/propozycji pozostaje dodatkową odmową. Wszystkie
składowe błędu zapisujemy osobno, także współwystępujące. ACF sam wymaga
dwóch niekolinearnych maksimów, więc usunięcie dodatkowego filtra widma
nie znosi tego wymagania. Maski nakładamy **po** podziale, jak w pilocie.

## Oracle 2×2 na tych samych grafach

Relacje programu / idealne × maska programu / idealna, każde przed i po
minimum. Idealna relacja „razem” wymaga dodatnich, równych identyfikatorów
prawdy. Wszystkie pozostałe krawędzie rozdzielają, także tło–tło.
FH: 0 dla „razem”, 5 dla pozostałych (5>k=4). MWS: siła 1, przyciąganie
lub odpychanie, przy remisie odpychanie pierwsze. Kodowanie sprawdzamy
na małych grafach, w tym wykazujemy niewystarczalność FH 0/1.

Maska programu: H & ACF & widmo. Idealna: H & prawdziwa_domena>0.
Zachowujemy pełną prawdę również w niepewnym pasie granicy; maska oceny
`evaluation_valid` służy wyłącznie ocenie. Nie naprawiamy grafu. Raportujemy
rozmiary/spójność prawdziwych domen na dostępnym grafie oraz straty minimum.
Tło pozostaje singletonami przy idealnych relacjach, dopóki nie usunie go
maska lub minimum. Nie ukrywamy tego współdziałania.

## Odczyt i interpretacja

Pokrycie znanych wnętrz ze stałym mianownikiem, scalenia/podziały warunkowe
na przypisaniu wraz z liczebnościami, lokalne relacje, fałszywe domeny na
negatywach. Przed odmowami, po masce i po minimum. Osobno przypadki,
reżimy, solvery, samplery i ziarna. Powtórzenia modeli nie są nowymi obrazami;
brak testów istotności opartych na pozornej niezależności klatek/par.

Rzeczywiste nieoznaczone obszary nie są negatywami. Boundary F1 zachowujemy
tylko jako diagnostykę siatki: stara metryka uwzględnia krawędzie osiowe
i pełen raster, więc nawet oracle może mieć F1<1 przez support/dyskretyzację.
Na grafie centrów nie przedstawiamy go jako wiarygodnej jakości konturu.
Przerwa/disjoint bez styku dodatnich domen ma boundary F1=null.

Przeglądarka lokalna pokazuje wybrany obraz, własne centra molekuł lub
jawnie opisaną siatkę, kolory domen i szare odmowy, warianty oraz wszystkie
powody odmowy po kliknięciu. Więcej koloru samo w sobie nie oznacza poprawy.
Raport wybierze dalszą diagnostykę według układu maska/relacje, bez zmiany
domyślnej metody aplikacji i bez ogłaszania skuteczności na nowych danych.
