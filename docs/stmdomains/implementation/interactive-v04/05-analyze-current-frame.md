# 05: Oblicz klasy i domeny bieżącej klatki z danych

**ID:** SD-V4-05

**What to build:** Użytkownik otwiera obrazy i oznaczenia MolTrack, wybiera klatkę i klika Analizuj klatkę. Program sam oblicza opisy otoczeń molekuł, dopasowuje klasy i tworzy domeny, pokazując końcowe kolory na molekułach. Nie ma wyboru pliku modelu ani paczki wyniku v0.4. Działa postęp i anulowanie.

**Blocked by:** [02: Pokaż molekuły i poprawną geometrię obrazu](02-molecules-and-geometry.md).

**Status:** in_progress — realizacja na polecenie użytkownika `implement 05`.

Baza implementacji/przeglądu: `2d01c5e`, gałąź `domains/interactive-v04-ui`,
środowisko `netcat`. Publiczne granice testów wynikają z kryteriów ticketu:
analiza bieżącego obrazu i oznaczeń → wynik po ID oraz analiza → publikacja
w kontrolerze i UI (kolory, odmowy, stany braku danych, anulowanie i nawigacja).
Testy tych granic powstają zgodnie z TDD; nie wczytujemy modelu ani wyników v0.4.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Pełna ścieżka obliczeń korzysta wyłącznie z bieżącego obrazu i jego oznaczeń: opisy otoczeń, ocena porządku, PCA/KMeans, akceptacja klas i przestrzenne tworzenie domen. Parametry klas powstają w aplikacji; nie są wczytywane ani kopiowane z paczki.
- [ ] Pierwszy wariant ma jawne bazowe K5. PCA dostosowuje rozmiar do dostępnych danych; zbyt mała liczba użytecznych lub różnych próbek daje zrozumiały komunikat i brak dopasowania, bez ukrytego dopisywania innych klatek lub zmiany K. Ręczne K1–8 dodaje 07, a Auto 12.
- [ ] Potrzebne operacje metody v0.4 przeniesiono do modułów aplikacji. Uruchomienie nie wymaga dostarczonych archiwów, katalogów roboczych, dawnych modeli, gotowych cech/etykiet, ręcznego słownika q/w ani pierwszych dziesięciu klatek. Skala otoczenia pochodzi z wybranego wejścia według jawnej reguły, bez stałej rozstawu TTMAPP.
- [ ] Bazowa procedura oceny porządku i jej kalibracji jest odtwarzalna z danych/kontroli, a użyte wartości są zachowane. Wydzielenie obliczeń i usunięcie ukrytych zależności należą do 05; późniejsze kontrolki 10 nie są warunkiem uruchomienia metody.
- [ ] Domyślny widok Domeny używa końcowych lokalnych przypisań po ID molekuły. Różne domeny tej samej klasy mają różne kolory; Klasy pokazują wyłącznie końcowe przypisania i własną legendę. Etykiety wstępne pozostają diagnostyką. Zoom, gamma i geometria raw/aligned zachowują zgodność obrazu z wynikiem.
- [ ] Szare nieprzypisane molekuły mają przyczynę dostępną po kliknięciu. Pominięte duplikaty są osobnym stanem poza mianownikiem aktywnych molekuł. Liczniki wynikają z przypisań. Zero domen, brak analizy i niemożliwe dopasowanie są jawnie rozróżnione.
- [ ] Klasy są opisane jako lokalne dla analizowanej klatki, a kolory domen nie sugerują śledzenia. Przejście do innej klatki nie przenosi jej wyniku ani nie uruchamia automatycznie dopasowania. Nie obowiązuje historyczny zakres 56 klatek.
- [ ] Na klatkach 7, 120, 259 i 268 wykonuje się nowe obliczenia, zapisując parametry, identyfikację danych i mierzalne wyniki. Powtórzenie na identycznym wejściu przy zapisanym ziarnie daje zgodne członkostwo domen. Identyczność z historycznym eksportem v0.4 nie jest kryterium odbioru nowego dopasowania.
- [ ] Obliczenia działają poza GUI. Błąd, anulowanie, przejście do innej klatki lub otwarcie nowej serii nie podmieniają widoku spóźnionym wynikiem.
- [ ] Brak oznaczeń albo niewystarczające wsparcie daje jawny stan/odmowę. Ustawienia, zakres dopasowania, wersja wewnętrznego modelu i źródła są związane z obliczonym wynikiem. Zmiana pozostałych klatek nie wpływa na dopasowanie bieżącej.
- [ ] Testy obejmują rzeczywistą ścieżkę obliczeń bez plików paczki, zgodność ID/geometrii/kolorów/liczników, zero i brak analizy, powtarzalność, anulowanie oraz zachowanie poprzedniego poprawnego wyniku. Małe przykłady syntetyczne mają jawne oczekiwania i są dostępne do otwarcia w UI.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz MolTrack/MPP TTMAPP, wybierz 259 i kliknij Analizuj klatkę. Program nie pyta o model lub wynik v0.4; pokazuje postęp, potem molekuły pokolorowane według obliczonych domen oraz liczniki.
2. Przełącz Domeny/Klasy, kliknij szarą molekułę i sprawdź przyczynę. Zmień zoom, gamma oraz raw/aligned: kolory pozostają na odpowiednich molekułach.
3. Przejdź do 268: przed pierwszym obliczeniem widoczny jest brak analizy. Uruchom analizę i powtórz ją dla tych samych ustawień. Sprawdź także 7 i 120; klasy są lokalne dla każdej klatki.
4. Na dostarczonych kontrolach obejrzyj prawidłowo obliczone zero domen, brak oznaczeń i za mało próbek do K5. Program rozróżnia te sytuacje i nie zgłasza awarii. Instrukcja implementacji podaje pliki i oczekiwane liczniki.
5. Uruchom i anuluj analizę lub zmień serię w trakcie; spóźniony wynik nie podmienia widoku, a poprzedni poprawny wynik pozostaje dostępny dla swojej serii. Powtórz podstawowy scenariusz bez dostępu aplikacji do paczek v0.4.

## Granice zadania

To pierwszy pełny przekrój własnych obliczeń na jednej klatce. Przejmuje potrzebny widok wyniku z usuniętego 04 oraz podstawowe odkrywanie jednej klatki z dawnego 11. Model powstaje wewnętrznie bez nadzorowanych etykiet; bazowe K5 nie jest twierdzeniem o liczbie faz. Strojenie, ręczne K, model wspólnego zakresu, analiza serii i Auto są kolejnymi funkcjami. Obsługa nowego detektora molekuł pozostaje poza zakresem.
