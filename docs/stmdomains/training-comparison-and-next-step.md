# Porównanie treningów i następny krok — 23

Data: **2026-11-01**. [Ticket 23](issues/23-training-comparison-and-next-step.md).
Zestawienie zapisanych wyników, bez nowego treningu, predykcji lub strojenia.
Status decyzji: **przyjęta przez użytkownika 2026-11-01; ticket 23 `resolved`**.

**Nie wykazano poprawy końcowego wykrywania domen po uczeniu AE/rVAE,
zmianie dekodera/KL ani lokalnym SSL w ustalonym budżecie. Użytkownik
zdecydował zakończyć tę serię porównań bez wyboru detektora i bez aktywowania 24–26.**
Nie oznacza to, że FFT jest wystarczającym detektorem albo że większy zbiór
nie może pomóc. Obecny wynik nie uzasadnia jeszcze kosztu przygotowania
całego archiwum MPP/STP. Jakość 04 i odbiór 13 pozostają otwarte.

## Co porównujemy

Główna tabela obejmuje [21](autoencoder-domains-trial.md) i
[22](local-self-supervised-trial.md): te same 24 klatki jednej akwizycji
TTMAPP, te same 81 realizacji kontroli, okno 48 px i krok siatki 16 px.
FFT, adaptery dopasowane na dozwolonym treningu, grafy, reguły FH/MWS
i bramka mają wspólny protokół. Audyt 22 potwierdził dokładną tożsamość
2808 archiwów FFT z 21 we wszystkich badanych skalach i zakresach.
Własne inicjalizacje SSL pozwalają oddzielić uczenie od architektury.

Transfer ocenia osobny graf miejsc testowych, z buforami przestrzennymi;
pełna klatka w galerii dostarcza kontekstu. Transdukcja uczy się na całej
bieżącej serii i jest oddzielnym zastosowaniem, nie testem generalizacji.
Kontrole ujawnione w 21 są w 22 oceną rozwojową. Kolejne klatki, okna
i trzy ziarna modelu nie są niezależnymi akwizycjami STM.

[21a](rvae-decoder-kl-trial.md) zachowuje te same częściowe referencje
TTMAPP, lecz ma nowe realizacje kontroli: 920011–920013 zamiast
920001–920003. Porównuje nowe warianty ze starymi modelami na tych samych
nowych obrazach; nie łączymy jego kontroli ze wspólną tabelą 21/22.
672 tablice bazowe TTMAPP były dokładnie zgodne z 21.

Historyczne 15–19 mają inne przygotowanie obrazu, skale, kroki i mianowniki.
Ich procentów nie zestawiamy jako rankingu z nową bazą FFT z 20.
Starsze wyniki zamrożonych sieci nie zostały przeliczone nowym protokołem.
Taki refit adapterów i ponowna predykcja byłyby nową próbą, poza tym zestawieniem.

## TTMAPP: cechy i podział przed odmowami

W tabeli mediana trzech ziaren, FFT deterministyczne. `M/S` oznacza procent
błędnych scaleń/podziałów wszystkich ocenialnych par z przypisanymi końcami.
Wszystkie poniższe propozycje **przed odmowami** przypisują 100% ocenialnych
okien. Niższy jeden składnik przy znacznym wzroście drugiego nie jest sukcesem.
Sparowane zmiany średniego błędu poniżej liczymy najpierw dla każdego
ziarna; nie wyprowadzamy ich ze średniej dwóch osobnych median M/S.

| Cechy | Podział | Transfer: M/S | Transdukcja: M/S | Przypisania po odmowach: transfer / transdukcja |
| --- | --- | ---: | ---: | ---: |
| FFT | FH | 100,0 / 3,8 | 88,0 / 5,8 | 0/174 / 4/782 |
| FFT | MWS | 0,0 / 77,5 | 1,1 / 52,1 | 0/174 / 4/782 |
| AE z32 | FH | 85,7 / 2,9 | 95,3 / 8,7 | 0/174 / 4/782 |
| AE z32 | MWS | 0,0 / 82,2 | 21,2 / 83,3 | 0/174 / 0/782 |
| rVAE z32 | FH | 85,7 / 22,0 | 38,0 / 34,6 | 0/174 / 0–4/782 |
| rVAE z32 | MWS | 0,0 / 70,3 | 8,3 / 71,6 | 0/174 / 0/782 |
| SSL z32 przed treningiem | FH | 100,0 / 0,0 | 96,2 / 5,7 | 0/174 / 4/782 |
| SSL z32 przed treningiem | MWS | 85,7 / 8,5 | 38,4 / 59,6 | 0/174 / 0/782 |
| SSL z32 po treningu | FH | 100,0 / 0,0 | 95,4 / 7,2 | 0/174 / 4/782 |
| SSL z32 po treningu | MWS | 100,0 / 0,0 | 16,5 / 80,0 | 0/174 / 0/782 |

Transfer: BLACK/RED/YELLOW = **172/2/0**, 815 par tej samej referencji
i 28 różnych; w rzeczywistym grafie tylko 369 i **1** odpowiednia krawędź.
Transdukcja: **671/9/102**, lokalnie 2136 par tej samej referencji i 17 różnych.
YELLOW w transferze jest niedostępny, nie ma wyniku 0% dla tego koloru.
Referencje to wybrane wnętrza, a kolory nie są klasami typu sieci.
Nie mamy globalnej trafności obrazu ani dokładnej prawdy granic TTMAPP.

FH często scala różne obszary; MWS często zamienia to na rozdrobnienie.
MWS zmienia zarazem odległości na relacje przyciągające i odpychające,
więc nie jest to izolowany eksperyment samego solvera. Macierz FFT/uczone
cechy × FH/MWS sprawdza cztery procedury przy tych samych danych.
Żadna uczona procedura nie spełnia całego zestawu warunków kontroli
i końcowych przypisań. Jest natomiast **częściowa przewaga AE/FH przed
odmowami w transferze**: średni błąd par poprawia się względem FFT/FH
we wszystkich trzech ziarnach o 13,734 / 1,902 / 7,572 pp, z medianą
7,572 pp. Dotyczy to tych samych 174 okien przy pełnym przypisaniu,
lecz tylko 28 par różnych referencji. Nie rozstrzyga kontroli granic
i nie daje końcowych domen; nie należy pomijać tego dodatniego wyniku
składnika ani przedstawiać go jako kwalifikacji detektora.

rVAE/FH w transdukcji także zmniejsza medianę średniego błędu przed
odmowami o 7,214 pp, ale tylko w dwóch z trzech ziaren: zmiany wynoszą
−4,517 / +7,214 / +13,876 pp. Każde ziarno ma większy split niż FFT
(16,67–41,38% wobec 5,79%). Redukcja scaleń kosztem rozdrobnienia nie
spełnia dopuszczalnego pogorszenia pojedynczego składnika o najwyżej 2 pp.

Uczenie SSL względem własnej inicjalizacji daje w transdukcji z MWS
medianę poprawy średniego błędu par tylko **0,146 punktu procentowego**,
z poprawą w dwóch z trzech ziaren. Z FH mediana się pogarsza, a transfer
scala wszystkie różne referencje. To nie spełnia wymogu poprawy o 5 pp
bez przeciwnego znaku w pozostałych ziarnach.

## Dwie niezależne luki: granice oraz odmowy

Wszystkie uczone główne z32 z 21/22 zawodzą na kontrolach czterech styków:
różnych orientacji, małej różnicy 8°, różnych rozstawów i przesunięcia wzoru.
SSL ma **F1=0 również przed odmowami** na wszystkich czterech przypadkach,
w obu reżimach, dla obu podziałów i wszystkich ziaren. Jego problem nie
powstaje wyłącznie podczas filtrowania. Dla porównania transferowe FFT
przed odmowami ma F1 FH/MWS: orientacje 0,444/0,571; 8° 0,467/0;
rozstaw 0,571/0,706; przesunięcie 0,571/0,571. To częściowo użyteczne cechy,
lecz cały detektor FFT także nie spełnia warunków kontynuacji.

| Kontrola po odmowach | AE/rVAE z32, 21 | SSL z32, 22 |
| --- | ---: | ---: |
| Szum, pasy, trzy rodzaje losowych punktów | po 72/72 | po 36/36 |
| Jedna pełna sieć | 66/72 | 36/36 |
| Niezależne rzędy | 0/72 | 0/36 |
| Każda z czterech granic | 0/72 | 0/36 |
| Rozłączne płaty, pusta przerwa | po 72/72 | po 36/36 |
| Niedostateczne pole | 72/72 | 36/36 |

72/36 to liczby ocen: konfiguracje × trzy ziarna modelu × trzy realizacje
syntetyczne, nie liczba niezależnych obrazów. Braki samych oznaczeń nie
zmieniają wyników siatki: 1800/1800 sprawdzeń w całym 21 i 1530/1530 w 22.
Kontrast, ucięcie, defekt, deformacja i resampling pozostają oddzielnymi
diagnostykami bez dopisanego po fakcie progu zaliczenia.

Druga luka wynika z zachowanej bramki porządku oraz spójności.
[Audyt 22](local-self-supervised-trial.md#co-ogranicza-zachowana-bramka)
rozpatruje wszystkie dopuszczone węzły i krawędzie, pomijając granice
podziału z cech. Maksymalna liczba miejsc w połączonych grupach co najmniej
czterech wynosi **0/174 w transferze i 4/782 w transdukcji**. Wszystkie
816 sprawdzonych predykcji głównych mieszczą się w tym ograniczeniu.
Dowolny encoder przy tej samej bramce i regule spójności nie przekroczy
tego maksimum. Jednocześnie niezależne rzędy otrzymują fałszywe domeny.
Samo obniżenie progu nie jest uzasadnioną naprawą obu zachowań.

Nie osiągnięto wymaganych 20% przypisań ogółem i 10% w każdej ocenialnej
grupie. Po odmowach porównanie błędów przy wspólnym coverage jest
**niedostępne**, a nie idealne. Wspólne 0% także nie dowodzi stabilności.
Zerowe lub nieliczne przypisania nie pozwalają uporządkować jakości encoderów;
porównanie przed odmowami zachowuje natomiast powyższe znaczenie diagnostyczne.

## Co dał dodatkowy budżet 21a

Słabsze KL obniżyło medianę MSE rVAE z **0,055552 do 0,047942** (13,7%),
we wszystkich trzech ziarnach. Fourier ze słabszym KL zwiększył efektywny
rząd kodu do 5,91–10,24 wobec 1,48–1,63. Obrazy nadal odtwarzają głównie
zgrubne tło; surowy kąt nie odtwarza znanych różnic orientacji.

| Wariant transferowy z32 | M/S przed, FH | M/S przed, MWS | Przypisania po |
| --- | ---: | ---: | ---: |
| Pierwotny rVAE | 85,7 / 22,0 | 0,0 / 70,3 | 0/174 |
| Słabsze KL | 100,0 / 5,0 | 0,0 / 96,8 | 0/174 |
| Fourier | 50,0 / 16,4 | 0,0 / 89,2 | 0/174 |
| Fourier i słabsze KL | 100,0 / 4,5 | 0,0 / 84,7 | 0/174 |

Korzystniejsza mediana Fouriera/FH nie jest stabilnym zyskiem: sparowany
średni błąd poprawia tylko jedno z trzech ziaren. Na nowych kontrolach
wszystkie cztery granice i niezależne rzędy zaliczają 0/54 ocen nowych
wariantów; pełna sieć 51/54, rozłączne płaty i pusta przerwa po 48/54.
Dodatek wykazał zmianę rekonstrukcji, nie korzyść końcowych domen.

## Co zachowujemy z wcześniejszych prób

| Składnik i źródło | Użyteczny wynik | Ograniczenie |
| --- | --- | --- |
| [Geometria 15](orientation-and-joining-trial.md) | Uzupełniony wariant przypisał 1187/1678 centrów TTMAPP, bez scaleń 3801 ocenianych par różnych referencji | RED tylko 14/101; błędy centrów mogą scalać syntetyczną granicę. To inne mianowniki niż siatka 20 |
| [SBC/MatID 16](sbc-matid-domains-trial.md) | Większa odporność na braki i łagodną deformację; poprawa trudnej granicy względem lokalnej komórki | 355/3195 fałszywych przypisań na losowych punktach, scalenie różnicy 8° i zależność od początku wyszukiwania |
| [Tekstura 17](image-texture-domains-trial.md) | Cechy obrazu nie zależą od kompletności zapisanych oznaczeń | Podobieństwo tekstury i spójność nie wystarczają do wykazania sieci 2D, materiału lub fazy |
| [Cechy FCN/DINO w 19](feature-separation-trial.md) | Bardzo dobre rozróżnianie czystych wnętrz niektórych syntetycznych orientacji/rozstawów | Faza siatki może opisywać położenie wzoru względem okna, a nie granicę domeny |
| [Lokalny graf 19](local-feature-graph-trial.md) | Oddzielono czyste wnętrza od rzeczywistych lokalnych relacji | Dla kontroli 8° FCN ma AUC 0,994 na wnętrzach, 0,543 na rzeczywistych krawędziach; to różne pytania pomiarowe, bez skutecznego całego detektora |
| [Późne próby 19](issues/19-frozen-feature-domains.md) | Lepszy dobór okresu, tolerancja pozycji, osobna faza i sygnał materiału w celowanych kontrolach | Brak jednego wiarygodnego warunku porządku dla rzeczywistych danych i trudnych negatywów |
| AE, rVAE i SSL | Działający trening, odtwarzalność; AE odtwarza więcej szczegółów, 21a poprawia MSE, SSL różnicuje kod i ogranicza zależność od jasności | Żaden z tych wyników nie jest jeszcze miarą poprawnych domen |

Nie zestawiamy 70,7% centrów z 15, procentów historycznego 19 i 0% okien
z 21/22 jako uczciwego rankingu metod. Późne diagnozy 19 bywały oceną
lokalnego otoczenia bez tworzenia domen. Zakończenie serii zachowuje te
użyteczne składniki i nie otwiera ponownie 19.

## Koszt i zakres wniosków

| Próba | Nowe treningi | Kroki | Czas treningu | Zapis checkpointów |
| --- | ---: | ---: | ---: | ---: |
| 21 | 18/18 fitów | 29 700 | 469,09 s | 890 954 997 B |
| 22 | 9/9 fitów | 18 000 | 452,04 s | 167 606 618 B |
| 21a, osobny budżet | 2 diagnostyki + 9/9 fitów | 22 000 | 336,34 s | 756 439 396 B |

Pierwotne 21/22 wykorzystały wszystkie **27 zaplanowanych fitów**,
łącznie 921,13 s treningu; limit czasu nie był problemem. Pomierzone
etapy CPU wyniosły 2088,67/7200 s dla 21/22; 21a oddzielnie 150,53 s.
Nie sumujemy czasów treningu i CPU jako dokładnego czasu ściennego sesji.
Koszty obejmują wykonane małe architektury, bez obietnicy dla innych modeli.
Maksimum tensorów GPU w 21 to około 391 MB, w 22 około 99,5 MB;
nie wykazano bariery uzasadniającej przejście z RTX 5090 na 96 GB/Colab.

| Próba | Ekstrakcja cech / podział, czas ścienny | Maksimum RSS treningu / dalszych etapów | Lokalny katalog artefaktów, pomiar 23 |
| --- | ---: | ---: | ---: |
| 21 | 70,79 / 419,07 s | 1,73 / 3,85 GB | 5 035 150 385 B |
| 22 | 141,38 / 442,94 s | 1,80 / 3,34 GB | 7 715 048 594 B |
| 21a | 11,79 / 51,14 s | 1,70 / 1,70 GB | 1 358 359 818 B |

To pomiary całych odpowiednich etapów zapisanej próby, a nie pojedynczego
obrazu lub identycznych liczb wariantów: 21/22 obejmują trzy skale i dwa
samplery, 21a tylko główną siatkę. Rozmiary katalogów obejmują także oceny,
galerie i diagnostykę; są bieżącym odczytem `du -sb`, nie samymi wagami.

To pilot jednej akwizycji, z małym treningiem transferowym (362 okna),
niepewną rejestracją i częściową referencją. Nie rozstrzyga uczenia na
innych molekułach/podłożach. Więcej wycinków tych samych klatek nie
zastępuje niezależnych pomiarów, ale sama liczba plików również nie naprawia
udowodnionego ograniczenia zachowanego filtra.

## Przyjęta decyzja i granica dalszych prac

| Możliwy kierunek | Ocena na podstawie obecnych wyników |
| --- | --- |
| 24 — grafy molekuł | Geometria daje wynik częściowy, lecz nie wyizolowano błędów kontrastu jako przyczyny, którą miałoby naprawić uczenie grafu. Pozostają jakość centrów i kryterium porządku |
| 25 — maskowany AE | Nie wyizolowano braku kontekstu jako przyczyny. Poprawa rekonstrukcji nie przyniosła domen, a sam nowy encoder zachowa ograniczenie bramki |
| 26 — adaptacja gotowego modelu | Zamrożone cechy mają użyteczność częściową, ale przejście od wnętrz do lokalnych krawędzi pozostaje nierozwiązane. Brakuje wybranego celu adaptacji i kontrolowanego porównania odpowiadającego tej luce |
| Encoder ekwiwariantny | Niewiarygodny kąt rVAE jest faktem, lecz sama naprawa kąta nie usunie ograniczenia odmów i nie dowiedzie granicy przy tym samym kącie |
| Większy zbiór lub GPU | Potencjalne przyszłe zasoby, bez wykazanej teraz korzyści dla konkretnej wybranej procedury |

Decyzja przyjęta przez użytkownika 2026-11-01: kończymy obecny pilot,
pozostawiamy **24–26 niewybrane i warunkowe**, bez nowych fitów, zbioru
lub budżetu. Dodatkowe MPP/STP pozostają odłożone. Nie oznaczać tych
rodzin jako wykonanych ani naukowo nieskutecznych. Nie przyjmować FFT
lub historycznej metody przez brak zwycięzcy uczenia. **13 pozostaje otwarty**.

Jeżeli użytkownik chce osobnego następnego badania, najpierw trzeba
zaprojektować ograniczoną ocenę **porządku i lokalnych relacji**. Każda
przyszła propozycja końcowego detektora musi jednocześnie zachować użyteczne
wnętrza realnej sieci, odrzucić niezależne rzędy oraz rozdzielić granicę
przesunięcia. To wskazanie luki, nie wybrany algorytm, nowy ticket lub
zaakceptowany budżet. Same obniżenie progu, kolejny encoder czy dodatkowe
epoki nie mają obecnie uzasadnienia jako rozwiązanie całości.

Do celowanego przyszłego rozstrzygnięcia przydałyby się przykłady o znanym
porządku/nieporządku przy różnych jakościach sygnału, ocena błędu centrów
oraz wskazana rzeczywista granica przesunięcia z tolerancją. Do twierdzeń
o generalizacji potrzebne byłyby odłożone akwizycje z metadanymi skali
i grupowaniem powiązanych pól. Nie żądamy teraz przygotowania całego
archiwum ani pełnych masek wszystkich klatek.

## Znaczenie punktów i procentów w galerii

Punkty głównego porównania są **środkami okien analizy**, rozmieszczonymi
co 16 px, a nie oznaczeniami molekuł. Okno ma 48 × 48 px i dodatkowy
margines wsparcia. W klatce 259 to 256 planowanych pozycji i 144 dostępne
pełne okna. Dlatego punkty nie muszą trafiać w jasne środki molekuł.
100% przed odmowami oznacza przypisanie dostępnych okien do składowych,
nie wykrycie 100% molekuł. 0% po odmowach oznacza brak zaakceptowanych
przypisań w tym zakresie, nie brak materiału lub uporządkowanych molekuł.

Definicje [słownika](GLOSSARY.md) pozostają bez zmian: oznaczenie molekuły,
orientacja sieci, typ, domena i pokrycie materiałem są osobnymi pojęciami.
Galerie eksperymentalne nie wyznaczają zwalidowanych konturów lub udziału
powierzchni; w przyszłym podglądzie trzeba jawnie oznaczać okna i pokazywać
rozmiar ich wsparcia. W 23 nie zmieniamy zamrożonych galerii.

## Odtworzenie zestawienia

[Manifest porównania](training-comparison-manifest.json) i nowy moduł
`stmdomains.experiments.training.comparison` wiążą tabele z zapisanymi
ocenami 21/21a/22. Lokalne kompletne tabele pozostają w
`.scratch/training-comparison-23/`. Manifest rozróżnia źródła przypięte
wcześniej hashami od pomocniczych plików, których bieżący hash zapisano
dopiero podczas 23. Podstawą wniosku są wcześniejsze przypięte agregaty
i kryteria, nie samo zaufanie do nieprzypiętego podsumowania.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m stmdomains.experiments.training.comparison \
  --output .scratch/training-comparison-23 \
  --manifest docs/stmdomains/training-comparison-manifest.json
```

Pełna lokalna tabela `tables.md` zawiera mediany i zakresy między ziarnami,
osobno wszystkie pary i rzeczywiste krawędzie, granice, wszystkie kontrole,
stabilność oraz porównania przy wspólnym zakresie przypisań.

Nie zmieniono dawnych źródeł, wag, progów, grafów ani przypisań.
Audyt porównania sprawdził odpowiednio 56/61/74 przypięte pliki 21/21a/22,
112 identycznych agregatów FFT, 14 zgodnych agregatów baz TTMAPP i 83 grupy
mianowników. Powtórzenie zestawienia w osobnym katalogu odtworzyło wszystkie
14 artefaktów bajt w bajt. Sprawdzono składnię modułu, lokalne odnośniki,
statusy/zależności ticketów i brak cyklu oraz `git diff --check`.
Nie uruchamiano testów produkcyjnej aplikacji ani GUI: 23 czyta istniejące
wyniki. Wcześniejsze 143/161/181 testów i odbiory galerii dotyczą swoich prób.
