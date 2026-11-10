# Dekoder i regularyzacja rVAE — próba 21a

Data: **2026-10-31**. [Ticket 21a](issues/21a-rvae-decoder-and-kl.md)
sprawdza dwie hipotezy po negatywnej [próbie 21](autoencoder-domains-trial.md):
czy kodowanie współrzędnych Fouriera pomaga odtwarzać drobny wzór oraz
czy mniejsza waga KL pozwala zachować więcej informacji o strukturze.
To lokalny eksperyment na jednej akwizycji, bez wdrożenia detektora.

**Wynik:** słabsze KL poprawia rekonstrukcję, a połączenie z kodowaniem
Fouriera zwiększa zróżnicowanie kodu. Nie uzyskano użytecznej orientacji
ani poprawy końcowych domen: wszystkie konfiguracje mają **0/174** przypisań
w ocenianym transferze TTMAPP. Żadna nie spełnia kryteriów kontynuacji.

## Zakres i zamrożenie

Wykonano dokładnie **2 + 9 runów**, łącznie **22 000 kroków**, bez
restartów, zastępczych ziaren lub zmiany architektury po wynikach.
Plan i kod zamrożono przed treningiem. Zachowano przygotowanie 20;
audyt potwierdził zgodność **100 299** zamrożonych artefaktów 21 i jego kodu.

Nowe fity obejmują wyłącznie **transfer z32**, z ziarnami 20261101–20261103.
Zachowano 362 okna treningowe, 270 walidacyjnych, podział przestrzenny,
bufory, normalizację i skale 32/48/64 px z 20/21. Nie wykonano nowych fitów
transdukcyjnych, z16 ani SSL; dziewięć fitów 22 pozostaje niewykorzystanych.

## Dwa sprawdzane czynniki

| Dekoder | Docelowa waga KL | Modele |
| --- | --- | --- |
| Oryginalny MLP | 0,001 | Trzy zachowane modele 21 |
| Oryginalny MLP | 0,0001 | Trzy nowe fity |
| MLP z kodowaniem Fouriera | 0,001 | Trzy nowe fity |
| MLP z kodowaniem Fouriera | 0,0001 | Trzy nowe fity |

Kodowanie otrzymuje współrzędne **po obrocie i przesunięciu**. Zachowuje
surowe `xy` i dodaje `sin(pi*k*xy)` oraz `cos(pi*k*xy)` dla jednego,
ustalonego zestawu `k = 1, 2, 4, 8, 16`, z amplitudą `1/sqrt(5)`.
Nie zastępuje obrazu modułem FFT ani nie usuwa fazy wzoru.

Pierwsza warstwa dekodera przyjmuje 54 zamiast 34 wartości; dwie warstwy
po 64 jednostki `Tanh` i liniowe wyjście pozostają takie same. Dekoder
ma 7745 zamiast 6465 parametrów, cały rVAE 250 631 zamiast 249 351.
Zachowano encoder, head, inicjalizację wspólnych warstw i stan generatora
po konstrukcji, bez przeszukiwania częstotliwości lub rozmiaru sieci.

Trening zachowuje optimizer, batch64 i float32 z 21. KL jest sumą po
zmiennych ukrytych, MSE średnią po pikselach. Beta narasta przez 200 kroków;
walidacja używa od początku wartości docelowej i identycznych batchy.

Checkpoint wybiera minimum własnej straty walidacyjnej: beta zmienia
**trening i wybór checkpointu**. Diagnostyka kroku 2000 ogranicza ten problem,
bez ponownego wyboru modelu po ocenie domen. Wynik domen dotyczy całej procedury.

## Próba zapamiętania 16 wycinków

Wybrano równomiernie 16 pozycji posortowanej listy okien treningowych;
ich ID, skale i hash zapisano przed treningiem. Oba runy mają tę samą
inicjalizację, ziarno 20261101, batche i losowanie posteriora, bez augmentacji.
Beta jest stała. Pomiar na tych samych 16 wycinkach nie ocenia uogólniania.

| Waga KL | MSE po 100 krokach | MSE po 2000 krokach | KL po 2000 krokach |
| --- | ---: | ---: | ---: |
| 0,001 | 0,047816 | 0,027757 | 4,486 |
| 0 | 0,040689 | 0,021679 | 204,493 |

Wyłączenie kary obniżyło MSE, przy dużym wzroście KL; nie potwierdza to
poprawnej orientacji lub domen. Wagi te nie inicjalizują pełnych treningów.
Obejrzane rekonstrukcje także przy beta0 zachowują głównie zgrubne tło
i gradienty; w tym budżecie nie odtwarzają indywidualnego wzoru molekuł.

## Nieoznaczona walidacja pełnych modeli

Mediany z trzech ziaren dotyczą tych samych 270 okien i odtwarzania czystego
celu z wejścia po ustalonych przekształceniach. MSE nie mierzy granic domen.

| Model | MSE wybranego checkpointu | MSE w kroku 2000 | Wybrane kroki trzech ziaren |
| --- | ---: | ---: | --- |
| AE z 21 | 0,025234 | 0,034429 | 700 / 600 / 600 |
| rVAE z 21, beta 0,001 | 0,055552 | 0,056297 | 1300 / 1300 / 1300 |
| Oryginalny dekoder, beta 0,0001 | 0,047942 | 0,048252 | 500 / 1700 / 2000 |
| Fourier, beta 0,001 | 0,051838 | 0,052817 | 1600 / 1300 / 1200 |
| Fourier, beta 0,0001 | 0,048482 | 0,048482 | 1400 / 2000 / 2000 |

Słabsze KL przy oryginalnym dekoderze obniża MSE względem pierwotnego
rVAE we wszystkich trzech ziarnach. Dodanie kodowania Fouriera nie daje
stałej dodatkowej korzyści ponad słabsze KL: poprawia jedno z trzech ziaren,
a dwa pogarsza. Zmiana samego dekodera przy beta 0,001 również nie poprawia
każdego ziarna. Żaden nowy rVAE nie osiąga mediany błędu AE z 21.

## Ocena reprezentacji i domen

Oceniono **3360** predykcji: 105 obrazów × 16 zestawów cech × dwa podziały.
Weryfikacja **14 370 lokalnych i 50 zewnętrznych artefaktów** poprzedziła
odczyt prawdy. Główne porównanie obejmuje skalę 48, siatkę 16 oraz FH i MWS,
przed i po odmowach. 16 zestawów to dziewięć nowych modeli, sześć modeli
AE/rVAE z 21 i jedna baza FFT. Nie wykonywano transdukcji.
Nowe cechy otrzymują adapter dopasowany wyłącznie na dozwolonym treningu;
adaptery AE/rVAE/FFT z 21 są kopiowane dokładnie, bez ponownego dopasowania.
Wspólna bramka porządku, jej progi i algorytmy podziału pozostają zachowane.
**672 porównania tablic** potwierdziły identyczność baz na niezmienionym
TTMAPP, dla pełnych pól i osobnych grafów części testowej.

Kontrole to 27 tych samych rodzin po trzy nowe realizacje, z ziarnami
**920011, 920012, 920013**; wszystkie modele otrzymują te same obrazy.
To świeża synteza, nie niezależne akwizycje STM. Znane 81 realizacji z 21
i obejrzane TTMAPP są materiałem rozwojowym. Metryki TTMAPP korzystają
z osobnego grafu wyłącznie węzłów części testowej, nie pełnych nakładek.

### Co zmieniło się w kodzie i kącie

Na 3456 dostępnych oknach TTMAPP efektywny rząd kodu wynosi **1,48–1,63**
dla pierwotnego rVAE, **2,71–6,99** po osłabieniu KL, **1,76–1,96** dla
samego Fouriera i **5,91–10,24** dla obu zmian razem. Najsilniejsza korelacja
wymiaru kodu z jasnością spada z 0,94–0,96 do 0,77–0,80 w ostatnim wariancie.
To opisowa poprawa zróżnicowania, bez potwierdzenia rozpoznawania struktury.
Ustalony przykład rekonstrukcji nadal pokazuje w rVAE szerokie plamy
i gradienty; AE odtwarza więcej szczegółów. Nie dobierano korzystnego wycinka.

| Model | Mediana bezwzględnej różnicy kąta przy prawdziwych 27° | Przy prawdziwych 8° |
| --- | ---: | ---: |
| Pierwotny rVAE | 1,64° | 1,19° |
| Słabsze KL | 0,58° | 0,61° |
| Fourier | 1,93° | 1,59° |
| Fourier i słabsze KL | 1,37° | 1,10° |

Mediany obejmują dziewięć par, z pełnym wsparciem w jednym dodatnim regionie.
Dotyczą wspólnego nowego zbioru, nie dawnych liczb kąta z 21. Obroty ±90°
bez interpolacji także zawodzą: mediany median resztowego błędu na TTMAPP
wynoszą odpowiednio 79,1° / 87,4° / 102,1° / 84,2°. Równoważności znanych
sieci syntetycznych są osobne, bez założenia symetrii realnego STM.
Reszta modulo 90° dla sieci kwadratowej nie rozstrzyga uczenia kąta przy
obrocie o ćwierć obrotu; dlatego zachowano osobno surowe reszty oraz
nietrywialne kontrole różnic 27° i 8°.
Nie uzyskano wiarygodnego pomiaru orientacji sieci.

### TTMAPP: scalenia i podziały przed odmowami

Ocenialne są 174 miejsca: BLACK 172, RED 2, YELLOW 0; brak YELLOW jest `null`.
Tabela podaje mediany trzech ziaren, a dla FFT jeden wynik. Przed odmowami
pokrycie wynosi 100%. Błędy dotyczą par w obrębie klatek, przy 815 parach
tej samej referencji i zaledwie 28 parach różnych referencji.

| Cechy | FH: scalenia / podziały | MWS: scalenia / podziały |
| --- | ---: | ---: |
| FFT | 100,0% / 3,8% | 0,0% / 77,5% |
| AE z 21 | 85,7% / 2,9% | 0,0% / 82,2% |
| rVAE z 21 | 85,7% / 22,0% | 0,0% / 70,3% |
| Słabsze KL | 100,0% / 5,0% | 0,0% / 96,8% |
| Fourier | 50,0% / 16,4% | 0,0% / 89,2% |
| Fourier i słabsze KL | 100,0% / 4,5% | 0,0% / 84,7% |

Korzystniejsza mediana FH dla Fouriera nie jest powtarzalną korzyścią:
porównanie z pierwotnym rVAE o tym samym ziarnie poprawia średni błąd par
tylko w jednym z trzech ziaren. Wszystkie nowe MWS zwiększają rozdrobnienie.
Po odmowach każda konfiguracja ma **0/174** przypisań; błędy par i przewaga
przy wspólnym pokryciu są niedostępne. Nie interpretujemy braku par jako
bezbłędnego podziału. Stała bramka nadal ogranicza końcowy wynik.

### Nowe kontrole i stabilność

Dla **każdego przypadku** nowe modele dają 54 oceny: trzy warianty × trzy
ziarna modeli × dwa podziały × trzy realizacje. Bazy mają osobno 36 ocen
AE/rVAE i sześć FFT. Poniższe zaliczenia dotyczą tylko nowych modeli.

| Przypadek | Zaliczenia |
| --- | ---: |
| Szum, pasy, trzy warianty losowych punktów | 54/54 dla każdego |
| Jedna sieć | 51/54 |
| Dwie orientacje 27°, rozstaw, granica przesunięcia, orientacja 8° | 0/54 dla każdego |
| Niezależne rzędy | 0/54 |
| Rozłączne płaty oraz pusta przerwa | 48/54 dla każdego |
| Pięć wariantów braków centrów; niedostateczne pole | 54/54 dla każdego |

Na niezależnych rzędach fałszywie przypisano **62,5–85,9%** znanych miejsc
bez domeny. F1 granicy wynosi 0 we wszystkich 54 ocenach każdego z czterech
wskazanych przypadków granic; część wnętrz może się rozdzielać mimo braku
przydatnego konturu. Niezaliczenia pojedynczej sieci i rozłącznych płatów
wynikają z niedostatecznego pokrycia w części fitów Fouriera/FH.
Przypadki diagnostyczne bez progu zaliczenia nie są automatycznie sukcesem.

Braki samych centrów nie zmieniają podziału siatki: **480/480** porównań,
w tym 270/270 nowych modeli. Spośród 468 stosowalnych syntetycznych ocen
stabilności nowych rodzin 441 przechodzi, 27 nie. Wszystkie 108 stosowalnych
ocen TTMAPP nie spełnia warunku, także przez brak wspólnych przypisanych
par; nie jest to samo w sobie dowód losowej niestabilności sieci.
Żadna z sześciu nowych kombinacji wariant × podział nie spełnia kryteriów
kontynuacji ani korzyści na kontrolach i TTMAPP.

## Koszt i sprawdzenia

Wszystkie 11 runów ukończyło po 2000 kroków. Łącznie zajęły **336,34 s**
treningu, około 5 min 36 s, wobec pułapu 2 h 25 min. Maksimum alokacji
CUDA wyniosło **422,85 MB**, RSS procesu **1,697 GB**. Zapisano i sprawdzono
**220 checkpointów**, łącznie **756,44 MB**, poniżej dodatkowego limitu 4 GiB.
Audyt potwierdził inicjalizację wspólnych wag, stan generatora po konstrukcji,
zgodność batchy każdego pełnego fitu z pierwotnym rVAE o tym samym ziarnie,
identyczne batche diagnostyczne, stałą wagę walidacji, minimum wyboru
checkpointu oraz hashe wszystkich checkpointów i konfiguracji.
Nie wykonywano dodatkowych treningów do sprawdzania wznowienia.
Przeszło **161 testów STM Domains**. Pomierzony przepływ przygotowania,
inferencji, podziału i oceny zużył **135,20 s CPU** wobec limitu 7200 s;
późniejsze diagnostyki i wizualizacje mają osobne zapisy kosztów.
Łącznie z diagnostyką, figurami i kontrolą galerii zapisany koszt wynosi
**150,53 s CPU**. Galeria przeszła **112 sprawdzeń interakcji**, bez błędów
JavaScript; zapisano i obejrzano pięć zrzutów oraz wykresy rekonstrukcji.
To inspekcja galerii badawczej, nie odbiór natywnego GUI. Wrapper sprawdzono
składniowo; wszystkie jego etapy wykonano osobno, bez ponawiania treningów.

## Wniosek do 23

Słabsze KL pomaga rekonstrukcji, a oba czynniki zwiększają rząd kodu,
bez wiarygodnego kąta lub podziału domen. 21a kończy się jako wykonany
eksperyment z wynikiem negatywnym dla detektora. Następne są 22 i 23;
nie rozszerzamy danych ani strojenia bramki.

## Artefakty

Kod: `stmdomains/experiments/training/rvae_followup/`.
[Manifest dowodów](rvae-decoder-kl-manifest.json) zawiera hashe źródeł,
artefaktów, koszty i wyniki wszystkich 11 runów.
Wyniki lokalne: `.scratch/rvae-21a/`: plan i protokół, `diagnostic/`,
`training/`, `cache/`, `features/`, `predictions/`, `evaluation/` i
`feature-diagnostics.json`. Galeria to `index.html`, wykresy są w `figures/`.
[Instrukcja odtworzenia](../../stmdomains/experiments/training/rvae_followup/README.md)
opisuje polecenia i warunki. Źródło prototypu zachowuje gałąź
`prototype/stmdomains-rvae-decoder-kl`; kod aplikacji pozostaje osobny.
