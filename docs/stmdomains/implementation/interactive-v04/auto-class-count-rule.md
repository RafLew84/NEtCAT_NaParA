# SD-V4-12 — reguła Auto v1 przed oceną TTMAPP

Data: **2026-11-03**. Baza `3297b98`. Regułę zapisano przed uruchomieniem
Auto na rzeczywistych danych TTMAPP. To ograniczona reguła inżynierska dla
obecnych opisów otoczeń, nie estymator liczby fizycznych faz ani test istotności.
Progi nie są dopasowywane do liczby domen lub ręcznego K5 z TTMAPP.

## Wejście i granice

Auto używa wyłącznie wybranego zakresu odkrywania i istniejącej bramki
użytecznych, uporządkowanych otoczeń. Minimum **20** użytecznych próbek
oraz ich udział co najmniej **0,25** w aktywnych oznaczeniach zakresu.
Przy braku oznaczeń, słabym wsparciu lub zbyt małym udziale: **nierozstrzygnięte**,
bez katalogu i bez domyślnego K5. Ustawienia porządku użytkownika obowiązują.
Otoczenia są przestrzennie zależne, a klatki mogą przedstawiać tę samą
powierzchnię; te liczności są kontrolą dostępności, nie liczbą niezależnych pomiarów.

Pozostaje dotychczasowy limit 6000 próbek wspólnego dopasowania i limit
wejścia jednej klatki. Ranking porównuje co najwyżej **1200** próbek,
wybranych równomiernie po uporządkowaniu wejścia, deterministycznie.
Wybrane K jest następnie dopasowywane do całego ograniczonego zbioru.
Małe lub rzadkie grupy mogą zostać pominięte; UI podaje limit i liczności.

## Wybór

1. K1 ma własną regułę: 95. percentyl odległości Hellingera od unormowanego
   średniego opisu wynosi najwyżej **0,15**. Wtedy wystarcza jedna zwarta
   klasa. Nie liczymy silhouette dla K1.
2. Dla K=2…maksimum użytkownika (**1–8**, bazowo 8) porównujemy ten sam
   podzbiór i projekcję PCA bez wybielania, z dotychczasowym KMeans,
   ziarnem 24 i 20 inicjalizacjami. Kandydat wymaga różnych próbek i
   przynajmniej **max(8, ceil(0,05 × N))** członków w każdej klasie.
3. Kandydat K≥2 jest dopuszczalny, gdy **silhouette ≥0,50**, najmniejsza
   odległość Hellingera pomiędzy unormowanymi średnimi klas wynosi
   **≥0,20**, a 95. percentyl promienia każdej klasy **≤0,20**.
   Silhouette liczymy w przestrzeni PCA; promienie i rozdzielenie
   sprawdzamy w pełnej przestrzeni opisów, aby nie ukryć zmienności przez PCA.
4. Gdy K1 jest zwarty, wybieramy K1. W przeciwnym razie wybieramy
   dopuszczalny podział o najwyższym silhouette; w granicy **0,02** od
   najlepszego wybieramy najmniejsze K. Brak dopuszczalnego podziału
   oznacza **nierozstrzygnięte**, nie K1 jako awaryjne zastępstwo.
5. Po dopasowaniu wybranego K do całego ograniczonego zbioru weryfikujemy
   liczność grup, promienie i rozdzielenie (dla K1 jego próg 0,15).
   Niespełnienie warunków kończy się nierozstrzygnięciem. Silhouette
   rankingu dotyczy podzbioru; nie przedstawiamy go jako wyniku całych danych.

Odległość między dwoma unormowanymi opisami pierwiastkowymi to
`||a-b|| / sqrt(2)`. Średnią przed pomiarem normalizujemy do długości 1.
Progi są częścią wersjonowanej reguły, nie dodatkowymi polami użytkownika.
Maksimum ogranicza przeszukiwany zakres, nie gwarantuje istnienia właśnie
tylu klas. Dla maksimum 1 nie wykonujemy podziałów; niezwarty zbiór pozostaje
nierozstrzygnięty. Wynik na górnej granicy ma informację o ograniczeniu zakresu.

## Pochodzenie i prezentacja

Wynik zapisuje żądanie Auto/ręczne, maksimum, wybrane K lub jego brak,
regułę, progi, liczności i źródło, ranking kandydatów z powodami odmowy,
ziarno i uzasadnienie. Wspólny katalog zachowuje tę decyzję na wszystkich
klatkach bez ponownego wyboru K. Zastosowanie istniejącego katalogu nie
wykonuje Auto ponownie. Użytkownik widzi krótkie uzasadnienie i szczegóły
rankingu; szkic i porównanie wyników zachowują zasady z 11.

Ręczne K1–8 zachowuje dotychczasową metodę i próg dostępności danych;
progi Auto nie są narzucane ręcznemu wyborowi. Nierozstrzygnięcie nie
nadpisuje wcześniejszego dobrego wyniku i nie tworzy pozornie zerowej detekcji.

## Kontrole przed TTMAPP

Pojedyncza regularna sieć → K1; dwie rozróżnialne grupy otoczeń → K2;
losowe centra → nierozstrzygnięcie przy bazowym porządku; brak oznaczeń,
cztery centra i za mało próbek → odmowa z powodem. Osobne testy sprawdzają
limit maksimum, stałe opisy, powtarzalność, anulowanie, brak dobrego podziału,
niezmienność modelu ręcznego oraz pełne przekazanie ustawień do serii.
Wszystkie późniejsze zmiany reguły należy opisać wraz z przyczyną;
próby rzeczywiste nie są zbiorem do strojenia tych progów.

Silhouette ma sens dla 2…N−1 etykiet; dlatego K1 ma osobne kryterium.
Dokumentacja API: [silhouette_score](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html)
i [KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).
