# Powtarzalny motyw i kompletność oznaczeń — issue 19

**Aktualizacja po omówieniu — 2026-10-31:** użytkownik zakończył serię
analiz; [ticket 19](issues/19-frozen-feature-domains.md) ma status `resolved`,
bez wyboru detektora. Poniższy raport i manifest zachowują wynik oraz status
z chwili ukończenia próby; przygotowanie 20 pozostaje nierozpoczęte.

Data: **2026-10-31**. Kontynuacja [porównania kandydatów baz](basis-candidates-trial.md),
wykonana na bezpośrednie polecenie użytkownika.

**Oddzielenie zgodności pozycji od liczby oznaczeń pomaga przy brakach.
Model dwóch pozycji lepiej odtwarza kontrolne pary molekuł, lecz tworzy
nowe fałszywe akceptacje niezależnych rzędów. Na TTMAPP rozszerzenie
motywu nie daje przewagi nad nową oceną pojedynczej sieci.** Kryterium
sukcesu całej próby nie zostało spełnione; nie przyjęto detektora domen.

Próba zakończona; **19 pozostaje `claimed`, do omówienia, 20 odłożone**.
Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/motif-completeness/index.html`.
44 obrazy, pięć scenariuszy: jedna/dwie/trzy pozycje, brakujące oznaczenia,
nieporządek i niezależne rzędy, przerwa a brak oznaczeń, pełne TTMAPP.
Kwadraty oznaczają miejsca oceny, kółka dostarczone centra; nie wyznaczono
granic domen. [Manifest](motif-completeness-manifest.json) wskazuje dane,
parametry, źródła i wyniki.

## Co porównano

**103 obrazy:** 19 wcześniejszych unikalnych geometrii negatywnych,
24 pełne klatki TTMAPP i 60 nowych syntetyków (20 przypadków × nasiona
11101–11103). **7960 otoczeń, 581305 dopasowań kandydatów, 23880 wyników
wariantów i 47760 decyzji** dla dwóch końcowych sprawdzianów.

Promień **64 px**, miejsca oceny co 24 px. Rozłączne części otoczenia:
do `.55R` dopasowanie, `.55R–.75R` wybór, `.75R–R` końcowy test.
Minimum osiem centrów do dopasowania i sześć do wyboru. Po wyborze nie
dopasowujemy ponownie i nie przełączamy modelu według wyniku testu.
Zachowano wcześniejsze propozycje baz z pików i dzielników.

| Wariant | Model | Wybór na osobnym pierścieniu |
| --- | --- | --- |
| `baseline` | Jedna pozycja w komórce | Dotychczasowe symetryczne miękkie dopasowanie F |
| `position1` | Jedna pozycja | Kontrast periodyczny S uwzględniający gęstość modelu |
| `motif` | Wybór 1–3 pozycji | S z ustaloną karą za dodatkowe pozycje |

Jedna pozycja korzysta z wcześniejszego dopasowania Huber. Dla dwóch/trzech
pozycji inicjalizacja pochodzi wyłącznie z faz centrów części dopasowania;
sześć iteracji wspólnie poprawia bazę i pozycje, z tolerancją 2 px i limitem
korekty bazy 15%. Każda pozycja wymaga przypisań w co najmniej trzech
różnych komórkach treningowych; minimalny odstęp pozycji wynosi 3 px.
Liczba pozycji motywu nie jest narzuconą liczbą domen.

Nowa miara to średnia `log(0.1 + 0.9 × rho)`, gdzie `rho` jest sumą
periodycznych Gaussianów o sigma 2 px, pomnożoną przez
`pole komórki / (liczba pozycji × 2π × sigma²)`. Uwzględnienie gęstości
ogranicza korzyść z dowolnego zagęszczania przewidywanych węzłów.
To **kontrast periodyczny kalibrowany empirycznie**, nie prawdopodobieństwo
domeny ani znormalizowana wiarygodność na przyciętym pierścieniu. Średnia
gęstości jest jednostkowa na pełnej komórce; brzeg i wybór sektora mogą
wpływać na ocenę. Nie stosowano gwarancji statystycznego poziomu błędu.

Przy wyborze modelu odejmujemy `(K−1) × log(Nwyboru) / Nwyboru`.
To zamrożona heurystyka złożoności, nie BIC; remis preferuje mniejsze K.
**Osobno** raportujemy sumę wag przypisania jeden-do-jednego podzieloną
przez liczbę przewidywanych węzłów oraz przez liczbę obserwowanych centrów.
Pierwsza wielkość opisuje obsadzenie konkretnego modelu. Nie znamy z niej
rzeczywistej kompletności detekcji TTMAPP ani obecności materiału.

Progi q99 powstały przed nowymi kontrolami i TTMAPP, osobno dla wariantów
i sprawdzianów, na wcześniejszych negatywach. Wszystkie sześć komórek
kalibracji ma ≥100 otoczeń z 18 niepustych geometrii. Dla S porównujemy
również **wspólny próg**, wyższy z dwóch zamrożonych: 1.40478 dla całego
pierścienia i 1.09895 dla nowych rzędów. F ma inne jednostki i własne
progi: .74491 oraz .64667. Nie porównujemy F z progiem S.

## Braki oznaczeń: poprawa oceny, nie odtworzenie ukrytej prawdy

Pary kontroli mają identyczne obrazy; usunięto wyłącznie oznaczenia,
z nominalnym prawdopodobieństwem 30% albo 60% na oznaczenie. Osobne przypadki przesuwają same oznaczenia o sigma 1.2 px
lub rzeczywiste molekuły wraz z obrazem o sigma 4 px.

Liczba otoczeń ponad progiem **całego pierścienia**, na 192 otoczenia
każdego przypadku. F korzysta z własnego progu, obie kolumny S ze wspólnego.
To liczby lokalnych ocen, nie domen ani niezależnych próbek.

| Kontrola | Jedna pozycja, F | Jedna pozycja, S | Motyw 1–3, S |
| --- | ---: | ---: | ---: |
| Czysta pojedyncza sieć | 192 | 192 | 192 |
| Pojedyncza sieć, brak 30% oznaczeń | 144 | 175 | 175 |
| Pojedyncza sieć, brak 60% oznaczeń | 1 | **100** | **100** |
| Pojedyncza sieć, błąd oznaczeń 1.2 px | 1 | 1 | 1 |
| Pary molekuł, komplet oznaczeń | 70 | 173 | 173 |
| Pary, brak 30% oznaczeń | 0 | 117 | 119 |
| Pary, brak 60% oznaczeń | 0 | 7 | 7 |
| Pary, błąd oznaczeń 1.2 px | 0 | 0 | **81** |

Przy 60% braków pojedynczej sieci model w ogóle można wybrać w 104/192
otoczeniach; nowe S nie naprawia braku wymaganych danych w pozostałych.
Mediana zgodności przewidywanych miejsc z pełnym obrazem wynosi około
.979. W geometrycznie pełnych oknach jest 11 dostępnych modeli na 12;
S akceptuje wszystkie 11, F zero, przy medianie zgodności pełnych pozycji 1.
Wskazuje to na rzeczywistą naprawę odmów spowodowanych niepełnością.

Osobne podgrupy `interior` zdefiniowano geometrycznie przed oceną:
cały dysk R64 leży w zmierzonym obrazie. Dają 12 otoczeń na kontrolę
z trzech obrazów; nie dobierano ich według dobrego wyniku.

## Dwie pozycje: lepsza geometria, ale nowe fałszywe akceptacje

Ocenę przewidywanych węzłów wykonano po zamrożeniu modeli, względem
pełnych pozycji obrazu generatora, także tych bez oznaczeń. Użyto
przypisania jeden-do-jednego z tolerancją 2 px; `F_pred` łączy odsetek
poprawnych przewidywań i odzyskanych rzeczywistych pozycji. Mediany
dotyczą otoczeń z wybranym modelem, nie całego zbioru bezwarunkowo.

| Kontrola | Mediana F_pred: jedna pozycja S | Mediana F_pred: motyw S |
| --- | ---: | ---: |
| Pełne pary | .754 | **.968** |
| Pary, brak 30% oznaczeń | .750 | **.968** |
| Pary, błąd oznaczeń 1.2 px | .513 | **.757** |

W 12 pełnych oknach czystej pary bogatszy model wybiera K2 i osiąga
F_pred=1. To korzyść geometryczna mimo identycznej liczby akceptacji
w pierwszym wierszu poprzedniej tabeli. Przy 60% braków par pozostaje
jedynie siedem dostępnych modeli na 192 otoczenia; nie ma ogólnej odporności
na tak duży ubytek danych.

Koszt elastyczności widać na niezależnie przesuniętych rzędach o tej samej
nominalnej gęstości co układ par:

| Kontrola negatywna | Jedna pozycja S: pierścień / nowe rzędy | Motyw S: pierścień / nowe rzędy |
| --- | ---: | ---: |
| Niezależne rzędy | 0 / 0 | **9 / 4** |
| Niezależne rzędy obrócone o 27° | 0 / 0 | **16 / 2** |
| Losowe punkty | 0 / 0 | 0 / 0 |
| Zaburzenie rzeczywistych pozycji sigma 4 px, pojedyncza sieć lub pary | 0 / 0 | 0 / 0 |

Każdy przypadek ma 192 otoczenia; próg S jest wspólny. Silne zaburzenie pozycji
jest kontrolą degradacji, nie dowodem całkowitego zaniku każdej informacji
periodycznej. Nowe błędy na rzędach wystarczają jednak do odrzucenia
tezy, że rozszerzenie motywu poprawia wynik bez kosztu fałszywego porządku.

Kontrola trzech pozycji jest bliska drobniejszej sieci w tolerancji 2 px:
`(0,0),(8,5),(15,11)` są blisko `(0,0),(8,6),(16,12)` w komórce 24×18.
Wybór K1 nie dowodzi tu porażki modelu K3 ani pełnego rozpoznania motywu.
Ta kontrola słabo rozdziela te hipotezy; nie zmieniano jej po obejrzeniu
wyników. K sam w sobie nie jest miarą prawdziwości — różne komórki mogą
opisywać ten sam zbiór pozycji.

## Nowe rzędy i obecność materiału

Zachowano osobną, ostrożną ocenę nowych rzędów w obu kierunkach. Cały
poziom komórki musi leżeć poza obszarem dopasowania i wyboru dla wszystkich
pozycji motywu. Każda oś wymaga co najmniej dwóch poziomów z co najmniej
dwiema różnymi komórkami. Kilka molekuł w jednej komórce nie zastępuje
kilku powtórzeń. Brak warunków daje **brak oceny**.

To ogranicza dostępność dla większej komórki w pierścieniu szerokości
16 px. Dla czystych par prawdziwy model generatora ma dostępność tylko
10/192; model dopasowany z wieloma pozycjami również 10/192. Mniejsza
liczba ocen niż przy uproszczonej sieci nie oznacza pogorszenia geometrii.
Warunek zależy także od podziału motywu na komórki: kotwicą jest średnia
centrów dopasowania, identyczna przy diagnostyce generatora. Nie jest to
niezmiennicze względem każdego równoważnego opisu kryterium fizyczne.

Trzy pary „rzeczywista przerwa 36 px” / „przerwa wyłącznie oznaczeń” mają
identyczne dostarczone centra i **identyczne wszystkie wyniki geometrii**,
mimo różnych obrazów. Nowa ocena przyjmuje 189/192 otoczenia obu przypadków.
Pozycje nie wystarczają do rozpoznania materiału; ta próba nie wyznacza maski
pokrycia. Podobnie regularne usunięcie każdej drugiej kolumny na całym
obrazie pozostaje nierozróżnialne od rzeczywiście rzadszej sieci z samych centrów.

## TTMAPP: brak przewagi rozszerzonego motywu

Pełne 24 klatki dają **2904 otoczenia**, z czego w 2403 można wybrać model.
Referencje odczytano dopiero po zamrożeniu pomiarów: 84 otoczenia mają
≥80% centrów w jednym znanym obszarze, 114 jest mieszanych (≥20% w każdym
z dwóch obszarów), a 2706 pozostaje poza rozstrzygającą referencją.
Pierwsza reguła ma pierwszeństwo. Nieoznaczone miejsca nie są negatywami.

| Wynik | Jedna pozycja F | Jedna pozycja S | Motyw S |
| --- | ---: | ---: | ---: |
| Ponad próg całego pierścienia | 1 | 7 | 7 |
| Dostępne nowe rzędy | 845 | 878 | 858 |
| Ponad próg nowych rzędów | 3 | 5 | 5 |
| Znane wnętrza: pierścień / nowe rzędy | 1 / 2 | 1 / 1 | 1 / 1 |

Obie kolumny S mają wspólny próg. Są to te same zbiory akceptowanych
otoczeń; rozszerzenie nie dodaje nowego potwierdzonego miejsca. W znanych
wnętrzach wszystkie 79 wybranych modeli nadal mają K1. W całym TTMAPP
wybrano K2 w 108, K3 w czterech otoczeniach, ale sam wybór na pierścieniu
walidacyjnym nie potwierdza ich poprawności. Mieszane otoczenia nie
przekraczają żadnego końcowego progu. Pozostałych miejsc bez referencji
nie można uznać automatycznie za sukcesy lub błędy.

Nie wyznaczono komponentów domen, granic ani powierzchni. Tych liczb nie
porównujemy z wcześniejszymi odsetkami przypisanych molekuł. Referencje
są częściowe, z jednej serii i wielokrotnie używane, bez niezależnego
potwierdzenia uogólnienia.

## Decyzja wynikająca z próby

Zachowujemy rozdzielenie zgodności pozycji i obsadzenia modelu jako użyteczny
składnik: brak oznaczenia nie powinien sam rozstrzygać o nieporządku.
Zachowujemy porównanie motywów jako dowód możliwości na parach, z jawnym
kosztem fałszywych akceptacji. **Nie wracamy jeszcze do wdrażania granic
ani nie wybieramy tej konfiguracji do programu.**

Warunek całej próby „poprawa bez wzrostu fałszywych wykryć” nie został spełniony,
a TTMAPP nadal nie uzasadnia dalszego rozszerzania tego modelu jako głównej
drogi. Proponowany krok po omówieniu: zachować wyniki jako punkt odniesienia,
zakończyć tę serię diagnostyki i podjąć przygotowanie treningu bez etykiet
w 20. Nie uruchomiono treningu; 19 pozostaje otwarte do decyzji użytkownika.

## Odtworzenie i sprawdzenia

Źródła: **`prototype/stmdomains-motif-completeness`, `25b270e`**,
baza `b450c4f`. Z checkoutu:

```bash
bash stmdomains/prototypes/run-motif-completeness.sh /tmp/motif-completeness-new
```

Wymagane lokalne artefakty poprzedniej próby i środowisko `netcat`.
Wyniki: `summary.csv`, pełne pomiary i ocena, `comparison.png/pdf`,
`review-comparison.png/pdf`, samodzielny HTML oraz manifesty blokad.

- 60 deterministycznych odtworzeń generatora, 33 kontrole par interwencji.
- 103/103 pełne tablice wejściowe zgodne z manifestami.
- Niezależny audyt: 1440 przypisań węzłów, 60 modeli gęstości, 267 węzłów
  równoważnych opisów, 18 permutacji, po sześć zmian walidacji i testu
  bez przecieku do wcześniejszych etapów. Suma 5×5 wobec 15×15 zmienia
  wynik najwyżej o 3.25×10⁻⁷; obrót/translacja stałego modelu <4.6×10⁻¹⁵.
- 103 pomiary i **47760 decyzji** identyczne po pełnym odtworzeniu
  z blokadą referencji; trzy ukończone partie. Pierwszy proces odtwarzania
  przerwano (kod 143); wszystkie partie obliczono ponownie od początku.
- 84 kontrole QtWebEngine, bez błędów JS; 399 kontroli agregatów i
  83778 porównań eksportowanych wartości/modeli. Zrzut i wykres obejrzane.
- Niezależny audyt wyników: 23880 wierszy i wyborów, 47760 decyzji,
  3213 pól agregacji, 5661 pól CSV oraz 94 oceny przewidywań sprawdzone
  niezależnym maksymalnym dopasowaniem grafu dwudzielnego.
- Python/Bash sprawdzone; wrapper wykonany etapami. Są to sprawdzenia
  eksperymentu, nie testy natywnego GUI ani dowód jakości detektora.

CPU, cztery procesy po jednym wątku BLAS. Kalibracja 45.82 s, nowe kontrole
109.39 s, TTMAPP 91.48 s; maksimum RSS pojedynczego procesu 120760 KiB,
nie sumaryczny szczyt pamięci. Suma czasów trzech ukończonych partii
odtworzenia 253.54 s, nie łączny czas ścienny. Bez GPU, treningu i nowych zależności.
Kod prototypu pozostaje na osobnej gałęzi; dokumentacja trafia do mapy.

Kopię 258 plików wynikowych wskazanych w manifeście (149895313 bajtów)
zweryfikowano SHA-256 w docelowym katalogu; poprzednie dane pozostają
pod wskazanym w manifeście lokalnym odsyłaczem.
