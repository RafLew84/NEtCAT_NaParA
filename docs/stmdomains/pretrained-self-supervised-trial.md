# Adaptacja gotowego DINOv2 — wynik próby 26

Data: **2026-11-01**. [Ticket 26](issues/26-pretrained-self-supervised-adaptation.md),
[protokół ustalony przed treningiem](pretrained-self-supervised-protocol.md),
[manifest wyników](pretrained-self-supervised-manifest.json).

**Adaptacja działa technicznie i zmienia cechy, ale nie wykazała wymaganej
poprawy domen względem oryginalnych wag DINOv2.** Oba osobne werdykty —
poprawa reprezentacji przed odmowami i kwalifikacja całego detektora po
odmowach — są negatywne dla transferu/transdukcji oraz FH/MWS. Nie przyjęto
detektora do aplikacji. Eksperyment kończy 26; odbiór 13 pozostaje otwarty.

Ukończono **6/6 treningów, 6000 kroków, bez zastępowania ziaren**.
Predykcje zamrożono przed oceną. Główna macierz obejmuje 14 040 wyników,
93 nowe realizacje 31 znanych rodzin kontroli oraz 24 znane klatki TTMAPP.
Dodatkowe MPP/STP nadal są odłożone.

## Najważniejszy wynik: granice nadal nie działają

DINOv2 z oryginalnymi wagami i po adaptacji ma **F1 = 0** dla czterech
kontroli granic: różne orientacje, obrót 8°, różny rozstaw i przesunięcie fazy.
Dotyczy to obu solverów, obu protokołów, wszystkich trzech ziaren adaptacji,
zarówno przed, jak i po odmowach. Nie jest to wyłącznie skutek końcowej bramki.

Poniżej F1 **przed odmowami**, główna skala grid48. Wyniki adaptacji
mają medianę i cały zakres równy zeru. Bazowy FFT nie ma ziarna treningowego;
wartości agregują trzy realizacje danej kontroli.

| Protokół i cechy | Podział | Różne orientacje | Obrót 8° | Różny rozstaw | Przesunięcie |
| --- | --- | ---: | ---: | ---: | ---: |
| Transfer, DINO oryginalny / adaptowany | FH i MWS | 0 | 0 | 0 | 0 |
| Transdukcja, DINO oryginalny / adaptowany | FH i MWS | 0 | 0 | 0 | 0 |
| Transfer, FFT | FH | 0,444 | 0,467 | 0,571 | 0,571 |
| Transfer, FFT | MWS | 0,571 | 0 | 0,632 | 0,571 |
| Transdukcja, FFT | FH | 0,444 | 0,467 | 0,571 | 0,571 |
| Transdukcja, FFT | MWS | 0,800 | 0 | 0,800 | 0 |

Nie wybieramy FFT na podstawie tej tabeli: zaliczenie niektórych granic
nie spełnia wszystkich wymagań, a brak poprawy DINO nie stanowi odbioru metody
klasycznej. W formalnym zestawie siedmiu pozytywnych rodzin adaptacja
zalicza tylko 8–19 z 63 sprawdzeń, zależnie od protokołu i solvera.
Warunek stabilności również nie jest spełniony w żadnym z czterech wariantów.

## TTMAPP: mały zysk przed odmowami, bez poprawy końcowych domen

Końcowe przypisania do domen, grid48:

| Cechy | Transfer FH | Transfer MWS | Transdukcja FH | Transdukcja MWS |
| --- | ---: | ---: | ---: | ---: |
| DINOv2 po adaptacji, każde ziarno | 0/174 | 0/174 | 4/782 | 0/782 |
| DINOv2 oryginalny | 0/174 | 0/174 | 4/782 | 0/782 |
| FFT | 0/174 | 0/174 | 4/782 | 4/782 |

Mianowniki 174 i 782 dotyczą dostępnych miejsc **częściowych dodatnich
referencji**, odpowiednio w osobnym grafie testowym i całej obecnej serii.
4/782 to około **0,51%** tego zakresu. Nie jest to czułość wykrywania
molekuł, kompletność domen w całym obrazie ani udział powierzchni materiału.
Brak danego rodzaju ocenialnych par po odmowach pozostaje `null`, bez
zamiany na zerowy błąd. Transdukcyjny FH zachowuje sześć par tej samej
referencji z błędem podziału 0; brak różnych par daje `merge_rate=null`.

Przed odmowami wszystkie trzy metody przypisują 174/174 oceniane miejsca
transferu. Dla MWS widać częściowy, ograniczony efekt:

| Transfer MWS, przed odmowami | Błędne scalenia par | Błędne podziały par |
| --- | ---: | ---: |
| FFT | 0% | 77,55% |
| Oryginalny DINOv2 | 3,57% | 28,59% |
| DINOv2 po adaptacji | 0% w każdym ziarnie | mediana 27,73%; zakres 23,80–28,47% |

Sparowany zysk względem FFT spełnia częściowy warunek korzyści:
mediana redukcji średniej dwóch błędów wynosi **0,2491**, przy tym samym
pokryciu. Względem oryginalnego DINOv2 zysk ma medianę około **0,0222**,
poniżej progu 0,05. Nie ma również wymaganej korzyści na pozytywnych
kontrolach. Większość przewagi wobec FFT była już obecna w gotowych wagach.
To nie uzasadnia przyjęcia adaptacji ani detektora.

FH przed odmowami scala wszystkie oceniane pary różnych referencji w
transferze. W transdukcji MWS adaptacja zmniejsza część scaleń względem
oryginału, ale zwiększa fragmentację: mediana błędu podziałów około 76,01%
wobec 73,21% oryginalnego DINO i 52,14% FFT. Nie ma ogólnej poprawy.

## Dlaczego rozdzieliliśmy dwa werdykty

Zachowana bramka porządku i spójności ma znany z 22 limit: maksymalnie
0/174 końcowych przypisań w transferze i 4/782 w transdukcji. Sama zmiana
cech nie usuwa tego ograniczenia. Wynik po odmowach odpowiada temu limitowi.

Dlatego protokół 26 osobno wymagał poprawy reprezentacji **przed odmowami**:
siedmiu pozytywnych rodzin, stabilności oraz korzyści względem obu baz na
kontrolach i TTMAPP. Nie wymagano zerowej liczby składowych negatywnych
kontroli przed uruchomieniem mechanizmu odmowy. Ten osobny werdykt również
jest negatywny: granice i stabilność nie działają dostatecznie dobrze,
a korzyść wobec oryginalnego DINO nie przekracza ustalonego progu.

## Co zostało wyuczone

Użyto lokalnych, oficjalnych wag **DINOv2 ViT-S/14** dostępnych po 18.
Zmieniano tylko ostatni blok transformera i końcową normalizację oraz
małą głowicę treningową: **1 907 392 uczone parametry**. Pierwsze 11 bloków,
wejście i tokeny bazowe pozostały bitowo niezmienione. Implementacja jest
lokalną samodestylacją inspirowaną DINO; nie jest pełnym treningiem DINOv2
ani odtworzeniem iBOT.

Dwa widoki tego samego miejsca zachowują skalę i orientację. Znane
przesunięcia wycinka służą dopasowaniu 36 wewnętrznych tokenów. Nauczyciel
EMA dostarcza celu, a głowica 256 wyjść jest wyłącznie zadaniem treningowym:
**256 nie określa liczby domen lub typów**. Grupowanie otrzymuje średnią
po 64 końcowych tokenach nauczyciela: opis o 384 wymiarach, bez głowicy. Oryginał i adaptacja mają ten
sam odczyt, wejście 64→112 i reguły podziału.

Wybrano z góry krok 1000 w każdym treningu; walidacja nie wybierała
checkpointu. Utrata względem zmieniającego się nauczyciela jest diagnostyką,
nie miarą jakości domen. Nie stwierdzono stałego deskryptora ani zadziałania
kontroli degeneracji. Na stałych wejściach ranga efektywna nauczyciela:

| Protokół | Oryginalny model | Po adaptacji, trzy ziarna |
| --- | ---: | ---: |
| Transfer | 37,00 | 38,75–39,44 |
| Transdukcja | 36,31 | 35,11–35,88 |

Podobieństwo kosinusowe do oryginału wynosi 0,966–0,970 w transferze
oraz 0,976–0,977 w transdukcji. Cechy zmieniły się i zachowały zmienność.
To odróżnia negatywny wynik domen od technicznego nieuruchomienia uczenia.
Okna diagnostyczne transdukcji należą także do jej zbioru uczącego.

## Zakres danych, pochodzenie i koszty

Zachowano dane, podział i normalizację z 20: 362 okna uczące transferu,
270 walidacyjnych i 11 616 uczących transdukcji. Kontrole mają nowe ziarna
930031–930033; są nowymi realizacjami znanych rodzin, nie nowym rodzajem
materiału. Trening nie czytał referencji. Adaptery cech korzystają tylko
z dozwolonej części danych, a transfer ocenia osobny graf testowy.

Oryginalny DINO jest obliczony ponownie przy wspólnym przygotowaniu 26.
Nie przedstawiamy go jako bitowej reprodukcji innego wejścia z 18/19.
FFT zachowuje bitowo 2592 wcześniejsze pliki wyników pomiarowych, 432 pliki
cache i 12 adapterów. Dawnych eksperymentów nie uruchamiano ponownie.

Na istniejącym RTX 5090 sześć procesów treningowych zajęło **297,31 s**,
z czego suma wewnętrznych czasów fitów wynosi **289,91 s**. Są to dwa ujęcia
tego samego kosztu, nie wartości do dodania. Maksimum pamięci tensorów GPU:
**573 MB**; RSS fitu: **2,09 GB**; 66 checkpointów: **1,96 GB**. Środowisko
netcat wystarczyło bez instalowania pakietów lub pobierania nowych modeli.
Koszty pozostałych etapów są zapisane w ledgerach i raporcie procesów;
limit 7200 s CPU pozostaje zachowany. Wrapper `wait4` ujmuje także koszt
startu procesów, bez podwójnego dodawania do ledgerów wewnętrznych.

## Sprawdzenia i odtworzenie

Osiem testów mechaniki, zgodność z oficjalnym forwardem i bitowe wznowienie
na trzech ziarnach przeszły. Preflight wykonał 36 technicznych kroków na
sztucznych danych, z odrzuconymi wagami. Audyt sześciu fitów sprawdził
66 checkpointów, pełny schemat 45 tensorów, RNG, optymalizator, EMA i
niezmienność bazy. Audyt eksportu sprawdził **3 104 460 wierszy przypisań**,
**8 952 420 relacji**, 60 adapterów i 14 040 pełnych wyników.

Dodatkowe 1440 archiwów transferu obejmuje 1140 wyników dla 19 klatek
testowych oraz 300 jawnie pustych dla pięciu pozostałych klatek.
Ocena zapisuje 14 520 rekordów: 14 040 predykcji i 480 diagnostycznych
mapowań na istniejące centra. To nie są dodatkowe fity ani predykcje modeli.

Niezależny audyt potwierdził wszystkie 2340 głównych wyników i 4680 etapów,
5616 porównań, 640 agregatów, 544 warunki korzyści oraz osiem werdyktów
etapowych. 96 rekordów metryk pomiarowego FFT jest identycznych z 21.
Audyt używał własnych liczników par i granic, bez produkcyjnego evaluatora.
Pierwsza próba audytu zatrzymała się przed odczytem referencji na błędnym
założeniu, że liczba rekordów oceny równa się liczbie predykcji. Jawna
korekta uwzględniła opisane wyżej 480 diagnostycznych mapowań. Zachowano
oryginalny skrypt, różnicę, nową kopię i koszty obu uruchomień; nie zmieniono
modeli, predykcji, metryk ani progów. Skorygowany audyt przeszedł.

Galeria lokalna: [otwórz HTML](../../.scratch/pretrained-ssl-26/index.html).
Zawiera 117 obrazów, 10 reprezentacji, 2340 porównań grid48, siedem
scenariuszy i dwie figury. QtWebEngine: **55 sprawdzeń, zero błędów JS**.
Obejrzano pięć zrzutów i figurę diagnostyczną. Punkty to środki okien
regularnej siatki; nie oznaczają wykrytych molekuł. Testowano prototyp HTML,
bez zmiany lub uruchamiania natywnego GUI aplikacji.

Odtworzenie: [README prototypu](../../stmdomains/experiments/training/pretrained_ssl/README.md).
Lokalne wyniki: `.scratch/pretrained-ssl-26/`; modele i duże dane poza Git.
Źródła: `stmdomains/experiments/training/pretrained_ssl/`.
Start `9232eb5`, podjęcie `25caf81`, źródła przed treningiem **`77bc6a2`**.
Gałąź archiwalna: `prototype/stmdomains-pretrained-self-supervised`.
Praca wyłącznie w worktree Domains; nie potrzeba zmian wspólnych.

Końcowy audyt integralności potwierdził 57 730 plików bieżących źródeł,
wejść i zamrożonych wyników oraz niezmienność 192 872 plików wcześniejszej
próby 25. Sprawdzono 445 odnośników i acykliczny graf 28 ticketów.
Łączny zewidencjonowany koszt etapów poza fitami po tym audycie wynosi
**605,83 s CPU**, w granicach limitu 7200 s. Uwzględnia obie próby audytu
metryk oraz poprawiony start audytu integralności z ustawioną ścieżką
importu repozytorium. Główny manifest zachowuje wcześniejszą migawkę;
końcowe ledgery i raport integralności są osobnymi lokalnymi dowodami.

## Wniosek do odbioru 13

26 zakończono jako ograniczony eksperyment z wynikiem negatywnym dla
adaptacji ostatniego bloku w tym protokole. Nie jest to dowód niemożliwości
wykorzystania dowolnego SSL lub DINO na STM. Na obecnych danych nie ma
podstaw do wyboru tej adaptacji do aplikacji. Nie uruchamiamy automatycznie
kolejnego treningu, strojenia lub rozszerzenia danych. Odbiór 13, jakość 04
i decyzja o dalszym kierunku pozostają otwarte.
