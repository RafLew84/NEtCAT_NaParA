# Zgodność przesunięć i lokalny sygnał — dwie próby kryterium porządku

Data: **2026-10-28**. Kontynuacja [issue 19](issues/19-frozen-feature-domains.md),
po [ablacji drugiego kierunku](second-direction-trial.md).
Źródło: **`prototype/stmdomains-translation-consistency`, `89cd738`**,
baza `f648afe`. Dokumentacja: `domains/translation-consistency-trial`,
baza `1868426`. Kod eksperymentu pozostaje poza aplikacją.

**Zgodność przesunięć pomaga na syntetycznych rzędach, lecz w badanej
konfiguracji odrzuca wszystkie znane wnętrza TTMAPP. Lokalny sygnał
w małym oknie zależy od tego, czy próbka wypada na molekule, czy między
molekułami; nie nadaje się jeszcze do wyznaczania zasięgu domeny.**
Żaden z 256 zmienionych wariantów detektora nie spełnia kompletu warunków.
Issue 19 pozostaje `claimed`, do omówienia; wyniku nie przyjęto do programu.

[Podgląd HTML](../../.scratch/translation-consistency/index.html) ·
[wykres PNG](../../.scratch/translation-consistency/translation-comparison.png) ·
[PDF](../../.scratch/translation-consistency/translation-comparison.pdf) ·
[CSV](../../.scratch/translation-consistency/controls.csv) ·
[manifest](translation-consistency-manifest.json).

## Co zbadano

Dwie oddzielne hipotezy, także w połączeniu:

1. Rzędy o wspólnym układzie powinny zachowywać zgodność obrazu po
   przesunięciu między rzędami, również po osłabieniu wpływu samych pasów.
2. Porządek w otoczeniu nie wystarcza do przypisania jego środka:
   potrzebne jest lokalne wsparcie sygnału, aby nie wypełniać pustych przerw.

Zachowano cechy FFT/EWT/FCN/DINO, PCA, podziały HDBSCAN/FH4, podparcie
cech, reguły łączenia i minimalnej liczby miejsc w fragmencie. Nie trenowano
sieci, nie podawano wzorca domeny, symetrii ani liczby grup. Referencje
TTMAPP nie wpływają na wejście, progi lub predykcje.

Łącznie **372 obrazy**: 24 pełne klatki TTMAPP, 204 dotychczasowe kontrole,
63 znane już obrazy rzędów oraz **81 nowych obrazów**. Nowy zestaw zawiera
21 poprzednich przypadków z ziarnami 5101–5103 i sześć dodatkowych struktur:
skośną sieć z przesunięciem 4 px między rzędami (0°/27°, modulacje 1/.35)
oraz prostokątną sieć o rozstawie 16×11 px (13°/41°, modulacja .35).
Algorytm otrzymuje ich obrazy i miejsca pomiaru, bez parametrów generatora.

Na wszystkich obrazach rzędów sprawdzano tylko porządek oraz łączność,
przy jednej grupie wyglądu. To kontrola limitu przypisań, nie pełny detektor
domen. Częściowe referencje TTMAPP obejmują 18 klatek i 1678 oznaczeń
we wnętrzach; są oceną kolejnych oznaczeń, nie unikalnych fizycznych molekuł.
Pozostałe części obrazów są nieoznaczone, a nie negatywne.

## Stały protokół

Promienie 24 i 48 px odniesienia. Kandydatami są dokładnie te same dwa
niekolinearne wektory wybrane przez `windowed ACF` co wcześniej:
opóźnienia 6–24 px, 24 maksima, filtr 5, sinus kąta ≥.35. Bez dodatkowego
dobierania pary po wyniku. Nadal używamy filtra górnoprzepustowego sigma 3
i normalizacji RMS całej klatki. Nowy pomiar jest własną diagnostyką,
nie zwalidowaną metodą z publikacji.

Dla wektorów `u,v` definiujemy różnicę jasności
`D_u(x) = I(x+u/4) − I(x−u/4)`. Porównujemy `D_u(x−v/2)` z `D_u(x+v/2)`,
następnie zamieniamy role `u,v`. Liczymy korelacje Pearsona w czterech
częściach kołowego okna, a wynik jest minimum z ośmiu korelacji.
Pomiar korzysta z próbek co 2 px i interpolacji liniowej, wyłącznie przy
zmierzonych pikselach. W każdej części potrzeba ≥16 par, łącznie ≥50%
próbek; brak podstaw daje −1. Stały sygnał różnicowy nie przechodzi.

Wektory pochodzą z całego okna. Sprawdzenie w częściach tego samego okna
jest kontrolą zgodności, **nie niezależną walidacją**. Punkty różnicowe
sięgają poza koło o połowę jednego wektora i ćwierć drugiego, maksymalnie
18 px w zadanym zakresie opóźnień. Ich pomiar nie odbija brzegu, choć
zachowany etap wyboru kandydatów ACF nadal korzysta z odbicia.

Lokalny wskaźnik to wariancja sygnału w kole o promieniu 6 px podzielona
przez wariancję w całym kole 24/48 px. Wymagamy co najmniej połowy
zmierzonego małego koła. Porównujemy brak warunku oraz progi .15 i .35.
To względny sygnał, nie prawdopodobieństwo materiału ani maska pokrycia.

Na każdym promieniu zapisano 10 wariantów:

| Wariant | Wymagania |
| --- | --- |
| `original` | zachowana ACF i drugi kierunek ≥.25 |
| `off_fixed` | zachowana ACF, bez warunku drugiego kierunku |
| `local15`, `local35` | `off_fixed` + lokalny wskaźnik ≥.15/.35 |
| `c99`, `c999` | dodatnia ACF wybierająca parę + zgodność powyżej progu |
| `c99_local15/35`, `c999_local15/35` | zgodność + lokalny wskaźnik |

Wariant zgodności **nie zachowuje dawnego progu wysokości ACF** ani
widmowego drugiego kierunku. Porównanie dotyczy zastąpienia tego kryterium,
a nie wyłącznie dodania ostrzejszego warunku. Wpływ lokalnego wskaźnika
można oddzielić przez warianty `local15/35` i odpowiednie pary `c99/c999`.

Progi zgodności to kwantyle .99 i .999 na 45 znanych negatywnych obrazach:
18 wcześniejszych kontroli i 27 obrazów niezależnych rzędów/pasów/szumu
z poprzedniej próby. Wyłącznie siatka, podparcie ≥.5, dodatni kandydat ACF,
obliczalna zgodność. Progi są wspólne dla wszystkich cech i obu miejsc
próbkowania. Nowe ziarna, dodatnie kontrole i TTMAPP nie kalibrują metody.

| Promień | Próbki kalibracji | Kwantyl .99 | Kwantyl .999 |
| --- | ---: | ---: | ---: |
| 24 | 5934 | .7286 | .9248 |
| 48 | 6784 | .9364 | .9519 |

20 kryteriów × 18 podziałów/limitów = **360 konfiguracji** na poprzednich
228 obrazach: 72 powtórzone, 256 zmienionych detektorów, 32 zmienione limity.
Na 144 obrazach rzędów — po 40 konfiguracji limitu. Parametry i predykcje
zamrożono przed oceną. Nie poprawiano ich po zobaczeniu wyników.

## Próba 1: zgodność przesunięć

Siatka, r24, same porządek i łączność; wszystkie trzy nowe ziarna:

| Kontrola | Bez drugiego kierunku | Zgodność .99 | Zgodność .999 |
| --- | ---: | ---: | ---: |
| Słabsze spójne rzędy 0°: przypisane molekuły | 98.8% | 79.7% | 0% |
| Słabsze spójne rzędy 27° | 86.1% | 78.4% | 0% |
| Słabsza skośna sieć 0° | 98.8% | 79.7% | 0% |
| Słabsza skośna sieć 27° | 86.8% | 77.3% | 0% |
| Prostokątna sieć 13° | 69.6% | 78.2% | 3.1% |
| Prostokątna sieć 41° | 11.9% | 26.1% | 10.6% |
| Niezależne rzędy 0°, modulacja 1: przypisane miejsca / 768 | 756 | 24 | 0 |
| Niezależne rzędy 27°, modulacja 1: miejsca / 768 | 635 | 0 | 0 |

To częściowa poprawa względem rozluźnionej bramki. Przy `c99` słabsze
spójne sieci dają po jednym fragmencie, ale losowe rzędy 0° nadal tworzą
jeden fałszywy fragment w jednym z trzech ziaren: 24/768 miejsc, **3.1%**.
Oryginalny warunek daje na tej nowej kontroli 14/768 (1.8%), lecz odrzuca
całą słabszą spójną sieć 0°. Nie przedstawiamy `c99` jako wariantu lepszego
od oryginału pod każdym względem.

Mocniejsze zaostrzenie `.999` usuwa te fałszywe miejsca, ale traci słabsze
rzędy. Kontrole najniższej modulacji .10 oraz naprzemiennego przyciemnienia
rzędów pozostają nierozwiązane przy r24. R48 nie daje ogólnej poprawy:
`c99` odrzuca słabsze sieci, a obrócone pasy nadal dostają 4/768 miejsc.

Na TTMAPP **każdy wariant zgodności daje 0/1678 przypisań**, na siatce
i przy centrach, przy obu promieniach. W znanych wnętrzach r24 najwyższa
zgodność wynosi .6548 na siatce i .6729 przy centrach, poniżej progu .7286.
Mediana podparcia par wynosi 100%; odrzucenia nie dają się wyjaśnić samym
brakiem zmierzonego brzegu. To nie dowodzi braku domen: badany zestaw
wektorów, skala, model zgodności i reguła kalibracji nie przenoszą się
wystarczająco na te pomiary.

Bez nowego kryterium zachowany limit wynosi 636/1678 przy r24 i 1313/1678
przy r48. Nie są to miary trafności. Nowy wynik nie oznacza też, że
wszystkie metody oparte na zgodności przesunięć są nieskuteczne.

## Próba 2: lokalny sygnał i puste przerwy

Na znanej kontroli dwóch rozłącznych płatów r48 bez drugiego kierunku
przypisuje 96/96 miejsc w przerwie i skleja płaty. Dodanie lokalnego progu
.15 usuwa błąd, **ale usuwa również oba poprawne płaty na siatce**.
Zmiana 96 → 0 bez pokazania tego kosztu byłaby myląca.

| Siatka, znane ziarna 2701–2703 | Bez lokalnego warunku | Lokalny próg .15 |
| --- | ---: | ---: |
| Jedna sieć, r24: przypisane molekuły | 95.3% | 0% |
| Dwa płaty, r24: przypisane molekuły | 84.6% | 0% |
| Dwa płaty, r48: przypisane molekuły | 88.9% | 0% |
| Przerwa r48: błędne miejsca | 96/96 | 0/96 |

Przy centrach molekuł ta sama kontrola pojedynczej sieci r24 zachowuje
97.3% przypisań także z progiem .15. Wariant centrów nie próbkuje pustej
przerwy bez oznaczeń, więc jego zera błędów nie są równoważnym sprawdzianem
lokalnej maski na całym obrazie.

Pomocniczy audyt wykonany **po zamrożeniu wyników**, bez zmiany metody,
pokazuje dla jednej sieci/ziarna 2701: próbki siatki leżą 8.49 px od
najbliższych molekuł. Mediana lokalnego wskaźnika w pełnych oknach r24
to .055 na siatce i 1.261 przy centrach. Wszystkie oceniane wewnętrzne
miejsca siatki odpadają poniżej .15, żadne centrum nie odpada.
Pomiar w małym kole rozróżnia położenie wewnątrz komórki sieci, a nie
granicę uporządkowanego płata. Nie wykonano pełnego badania przesunięcia
początku siatki; opisujemy konkretną zaobserwowaną geometrię.

Na TTMAPP lokalny próg .15 nie zmienia limitu 636/1313 przypisań.
Zatem nie daje ani uniwersalnej ochrony przed błędami, ani odpowiedzi
na problem jakości rzeczywistych danych.

## Ocena całości i weryfikacja

**0/256 zmienionych konfiguracji detektora** spełnia pełne dotychczasowe
warunki rozwojowe. Również żaden z pozostałych powtórzonych wariantów
i limitów nie przechodzi całego zestawu. Brak sukcesu bramki nie jest
nową oceną jakości cech FCN/DINO; były zachowane. Typy strukturalne,
ostateczne granice i powierzchnie pozostają nieustalone.

- 128 kontroli Pearsona i 400 interpolacji liniowych względem osobnego
  rachunku; maksymalne różnice 4.45e-16. 400 kontroli masek pomiaru
  i cztery przypadki analityczne/bez podstaw.
- 81 dokładnych odtworzeń nowych obrazów. **4656** zachowanych tablic
  ACF/energii/podparcia/kierunku zgodnych do tolerancji 1e-12.
- **16920** poprzednich wyników zgodnych dokładnie w tablicach bramki,
  fragmentów i przypisań. 456 tablic siatki oraz 4320 par wyników
  identycznych przy brakach samych oznaczeń.
- Wszystkie **372 pliki / 87840 wyników konfiguracji** ponowiono przy
  blokadzie odczytów ścieżek referencji/oceny: identyczne hashe zawartości.
  372 nowe i 291 poprzednich plików predykcji zgodnych z hashami; protokół,
  ustawienia i kod analizy niezmienione po ocenie.
- **187 kontroli QtWebEngine**, brak błędów JS/przepełnienia poziomego;
  podgląd zawiera 106 obrazów i wszystkie ustawienia. Obejrzano HTML
  oraz wykresy. Sprawdzono składnię Python/Bash, linki i manifest.

Obliczenia CPU, cztery procesy po jednym wątku BLAS/OpenMP. Pomiary
174.26 s, predykcje 15.61 s, ponowienie bez referencji 13.91 s.
Największy RSS pojedynczego procesu przygotowania 120468 KiB (~118 MiB),
bez pomiaru łącznego szczytu. Bez instalacji, nowych wag i GPU.
Nie testowano produkcji, natywnego GUI ani pełnych 268 klatek.

Kopia: **931 plików / 293617956 B**, wszystkie SHA-256 zgodne; następnie
dopisano potwierdzenie kopii. Dane i wyniki poza Git. Względne linki
wymagają poprzednich artefaktów; HTML/PNG/PDF/CSV są samowystarczalne.
Runner: `bash stmdomains/prototypes/run_translation_consistency.sh`
na gałęzi prototypu. Etapy wykonano osobno, wrapper sprawdzono składniowo.

Nowe ziarna i struktury są kontrolą syntetyczną, nie niezależną walidacją
rzeczywistych obrazów STM. Znane ramki służą ocenie po zamrożeniu;
nie podają wzorców domen. Wynik poza ramkami pozostaje bez referencji.

## Proponowany dalszy krok

Zachować oba wyniki jako diagnostykę i **przejść do przygotowania treningu
bez etykiet w kroku 20**, następnie porównać AE/rVAE i lokalne SSL
w 21/22 zgodnie z mapą. To propozycja dalszej kolejności, nie wybór modelu
ani zamknięcie 19. Kolejne drobne zmiany progów tej samej bramki nie mają
obecnie wykazanej drogi do poprawnego wyniku na TTMAPP.

Protokół nowych metod powinien pokazywać informację w cechach i podział
**przed** odmowami bramki oraz osobno wynik po ocenie porządku. Nie wolno
bez sprawdzenia podłączyć kryterium, które zeruje wszystkie znane
wnętrza referencyjne, i przypisać całego niepowodzenia uczonemu modelowi. Podział bez
bramki również nie stanowi automatycznie domeny. Zachować słabe rzędy,
losowe fazy, różne sieci i przerwy jako kontrole, ze świeżymi realizacjami
po ustaleniu parametrów. Sam trening nie gwarantuje rozwiązania tych luk.
Krok 20 i treningi nie zostały uruchomione w tej próbie.
