# AE/rVAE i propozycje domen — próba 21

Data: **2026-10-31**. Realizacja [ticketu 21](issues/21-autoencoder-domains.md)
według zamkniętego [protokołu 20](self-supervised-training-protocol.md).
To badanie na obecnym TTMAPP i kontrolach syntetycznych. Nie wdraża
detektora do aplikacji i nie obejmuje lokalnego SSL z ticketu 22.

**Wynik: nie wykazano poprawy końcowego wykrywania domen.** Żadna z ośmiu
głównych konfiguracji z32 (rodzina × reżim × podział) nie spełnia warunków
kontynuacji z 20. Próba została wykonana w pełnym zaplanowanym zakresie;
nie wybrano modelu do aplikacji. Następny niezależny krok to 22, potem
wspólna decyzja 23. [Manifest dowodów](autoencoder-domains-manifest.json).

## Wynik na TTMAPP

Wszystkie propozycje przed odmowami obejmują 100% dostępnych miejsc
wewnątrz częściowych referencji. Poniżej mediana trzech ziaren modeli;
FFT jest jedną deterministyczną bazą. Coverage to procent miejsc,
a merge/split to odsetki błędów odpowiednich par, nie ogólna trafność.

| Reżim | Cechy | Podział | Merge przed | Split przed | Coverage po |
| --- | --- | --- | ---: | ---: | ---: |
| Transfer | FFT | FH | 100,0% | 3,8% | 0% |
| Transfer | FFT | MWS | 0% | 77,5% | 0% |
| Transfer | AE z32 | FH | 85,7% | 2,9% | 0% |
| Transfer | AE z32 | MWS | 0% | 82,2% | 0% |
| Transfer | rVAE z32 | FH | 85,7% | 22,0% | 0% |
| Transfer | rVAE z32 | MWS | 0% | 70,3% | 0% |
| Transdukcja | FFT | FH | 88,0% | 5,8% | 0,51% |
| Transdukcja | FFT | MWS | 1,1% | 52,1% | 0,51% |
| Transdukcja | AE z32 | FH | 95,3% | 8,7% | 0,51% |
| Transdukcja | AE z32 | MWS | 21,2% | 83,3% | 0% |
| Transdukcja | rVAE z32 | FH | 38,0% | 34,6% | 0–0,51% |
| Transdukcja | rVAE z32 | MWS | 8,3% | 71,6% | 0% |

Transfer ma **174 ocenialne miejsca**: BLACK/RED/YELLOW = **172/2/0**.
YELLOW jest niedostępny, z coverage `null`. W transdukcji jest **782 miejsc**:
**671/9/102**. Najwyższe końcowe przypisanie to cztery miejsca BLACK;
RED i YELLOW nie otrzymują przypisań. Nie osiągnięto progu 20% ogółem
ani 10% w każdej reprezentowanej grupie.

Po odmowach merge jest we wszystkich tych wariantach niedostępny.
Split wynosi 0 jedynie tam, gdzie pozostały te cztery miejsca; przy pustej
odpowiedzi również jest niedostępny. Tak ograniczony wynik nie świadczy
o poprawnym wykrywaniu domen. Porównanie błędów przy wspólnym coverage
nie osiąga wymaganego mianownika 20%; nie ogłaszamy korzyści z pominięcia
trudnych miejsc.

Przy FH dominują scalenia, a MWS zamienia część scaleń na rozdrobnienie.
MWS zmienia również interpretację odległości na przyciąganie/odpychanie,
więc różnic nie przypisujemy samemu solverowi. Wspólna bramka porządku
dopuszcza tylko 52/3456 pełnych okien TTMAPP w transferze i 50/3456
w transdukcji; następnie odpadają jeszcze małe składowe. To główne
ograniczenie końcowego coverage, lecz również przed odmowami nie ma
stabilnego rozwiązania problemu scaleń/podziałów.

## Kontrole syntetyczne i stabilność

Poniższe liczby dotyczą uczonych z32 na głównej siatce 48 px:
osiem konfiguracji × trzy ziarna modelu × trzy realizacje kontroli,
czyli **72 oceny każdego przypadku**. To powtórzenia kontrolowane,
nie 72 niezależne akwizycje.

| Przypadek | Zaliczono | Najważniejsza obserwacja |
| --- | ---: | --- |
| Szum, pasy i trzy warianty losowych punktów | po 72/72 | Brak końcowych domen |
| Jedna pełna sieć | 66/72 | AE/FH transfer rozbija sieć w sześciu ocenach |
| Niezależne rzędy | 0/72 | Fałszywe domeny mimo braku wspólnej sieci 2D |
| Dwie orientacje, różne rozstawy | po 0/72 | Niezaliczone odtworzenie granicy, F1=0 |
| Przesunięcie wzoru, różnica orientacji 8° | po 0/72 | Scalenia oraz niezaliczona granica |
| Rozłączne płaty, pusta przerwa | po 72/72 | Dwie domeny; coverage=0,5, bez przypisań w pustym pasie |
| Niedostateczne pole | 72/72 | Poprawny brak danych, bez domen |

W kontrolach granicy dobre rozdzielenie części wnętrz nie oznacza jeszcze
wyznaczenia granicy: po odmowach może zabraknąć przypisanych końców
krawędzi w jej sąsiedztwie. Szczegółowe kontrole defektu, kontrastu,
odwrócenia, ucięcia, deformacji i resamplingu są raportowane oddzielnie
w CSV; brak osobnego progu zaliczenia nie oznacza ich zaliczenia.

Przy brakach 10/30/50%, brakach lokalnych i brakach oznaczeń w pasie
siatka zachowała identyczne partycje przed/po odmowach: **1800/1800**
porównań całej próby, w tym **420/420** dla głównej konfiguracji z32
i baz FFT. Wrażliwość na same braki centrów nie jest tu problemem.
Warunku stabilności nie zaliczono dla żadnego głównego wariantu na
całym wymaganym zakresie; część niepowodzeń wynika z braku wspólnych
przypisanych par na TTMAPP, a nie wyłącznie z różnicy między ziarnami.

Skale diagnostyczne nie zmieniają wniosku: uczone z32 na siatce 32 px
mają końcowe coverage TTMAPP 0%, a 64 px najwyżej 1,02% w transdukcji
i 0% w transferze. Nie wybrano nowej skali lub checkpointu na tej podstawie.

## Zakres i odtwarzalność

Wejście: 24 audytowane klatki TTMAPP oraz 81 odłożonych realizacji
syntetycznych z 20. Model uczy się wyłącznie na rzeczywistych obrazach;
kontrole oraz częściowe referencje 18 klatek TTMAPP służą późniejszej ocenie.
Transfer ma 362 okna siatki train w trzech skalach oraz 270 validation.
Transdukcja ma 11 616 dostępnych okien siatki w całych 24 klatkach.
Liczby wycinków nie są liczbami niezależnych pomiarów.

Wykonano **18/18 fitów**: AE i ciągły rVAE, transfer z16/z32 po trzy ziarna,
a następnie osobne refity z32 dla całej serii. Łącznie **29 700 kroków**.
W transferze wykonano po 2000 kroków, a checkpoint wybiera najmniejsza
stała strata walidacyjna bez etykiet. Transdukcyjne AE wykonuje 600 kroków,
a rVAE 1300 — mediany wybranych kroków transferowych z32 danej rodziny.
Nie dodano wariantów, ziaren, restartów ani strojenia po ocenie domen.

Encoder ma trzy konwolucje 3 × 3, stride 2, kanały 16/32/64, GELU,
bez BatchNorm. AE ma dekoder konwolucyjny. rVAE ma ciągłe zmienne treści,
kąta i przesunięcia oraz dekoder MLP na obróconych współrzędnych.
Nie ma zadanej liczby klas domen ani założenia symetrii M6. Szczegóły,
hashe kodu i konfiguracje zapisano przed pierwszym fitem. Jest to lokalna
implementacja kandydatów w PyTorch, bez AtomAI lub dodatkowych pakietów.
Różnice dekodera i regularyzacji KL oznaczają, że porównanie nie izoluje
samego wpływu wydzielenia obrotu; zwykły VAE nie należał do budżetu.

## Porównanie i granice interpretacji

Główne cztery pola to FFT/FH, FFT/MWS, uczone cechy/FH i uczone cechy/MWS,
osobno dla każdej rodziny, ziarna i reżimu. Skala główna to 48 px;
32/64 px i bezpośrednie grafy centrów są zaplanowaną diagnostyką tych
samych wag. Pomocniczą ocenę centrów odwzorowanych na siatkę zapisano
oddzielnie od grafów centrów.

Baza `fft48-grid16--fh4-training20-v1` jest jawną adaptacją FFT/FH z 17/19:
natywne okno, średnia lokalna, Hann, 12 częstotliwości × 18 kierunków.
Nie używa historycznego filtra Gaussa i RMS całej klatki. Historyczne
metryki 17/19 nie są wynikami tej nowej bazy.

Każdy adapter L2/PCA, mediana odległości i kwantyle relacji są dopasowane
wyłącznie do dozwolonej części rzeczywistych danych. Typ strukturalny,
materiał i niezwalidowany kąt sieci pozostają `null`. Surowy kąt rVAE jest
diagnostyką, a nie automatycznie orientacją sieci.

**Doprecyzowanie kontekstu transferu przed oceną:** pełne nakładki zachowują
wynik inferencji całej klatki. Osobne grafy do metryk zawierają wyłącznie
miejsca `transfer_split=test` i krawędzie między nimi. Ścieżki poza pasem
testowym nie łączą więc ocenianych komponentów. Dla centrów promień grafu
jest ponownie wyznaczany na tym podzbiorze. Nie zmienia to wag, adapterów,
progów ani podziału z 20.

Ocena porządku jest wspólna wszystkim cechom. Kwantyl 0,999 wyznaczono
na regularnej siatce pięciu znanych ujemnych kontroli, po sześć wcześniej
używanych ziaren; jeden próg na skalę dotyczy także diagnostyki centrów.
Nie użyto nowych realizacji do kalibracji. Progi ACF wynoszą odpowiednio
**0,373635 / 0,379483 / 0,347375** dla 32/48/64 px. Warunek drugiego
kierunku i dodatniej energii pozostaje osobny.

Coverage oznacza udział przypisanych we wszystkich ocenialnych miejscach
z pełnym wsparciem; udział w dodatniej referencji podajemy dodatkowo.
Błędy par dotyczą dodatnich referencji i przypisanych końców. Brak
mianownika lub koloru daje `null`. Granice syntetyczne oceniamy tylko
na stykach dodatnich domen, z tolerancją 8 reference_px. Przybliżone ramki
TTMAPP nie są referencją konturu.

## Co reprezentują nauczone cechy

AE odtwarza widoczny układ jasnych obiektów lepiej niż użyty rVAE, lecz
rekonstrukcja nie jest miarą domen. Na ustalonym wycinku środka klatki 250
rVAE odtwarza głównie łagodny gradient. Wszystkie przykłady korzystają
z ustalonego pierwszego ziarna i miejsca, bez wyboru po jakości.

Opisowa diagnostyka wszystkich dostępnych okien siatki 48 px TTMAPP:

| Model z32 | Efektywny rząd kodu, transfer | Efektywny rząd, transdukcja | Największa bezwzględna korelacja wymiaru z jasnością |
| --- | --- | --- | --- |
| AE | 21,0–21,8 | 13,8–18,7 | 0,47–0,90 |
| rVAE | 1,48–1,63 | 1,18–1,50 | 0,94–0,98 |

Zakresy obejmują trzy ziarna, a ostatnia kolumna oba reżimy. Rząd jest
wyznaczony z entropii udziałów wariancji kodu, nie z liczby domen.
To diagnostyka opisowa pełnych pól, bez dopasowywania reguł predykcji.
W tych fitach rVAE zachowuje głównie informację związaną z jasnością;
nie jest to całkowicie stały ani niefinite kod.

Na kontroli różnicy orientacji 27° mediana bezwzględnej różnicy surowych
kątów rVAE między dwiema częściami wynosi tylko **0,29°** w transferze
i **0,39°** w transdukcji. Dla prawdziwych 8° to odpowiednio **0,21°**
i **0,23°**. Są to mediany dziewięciu par (trzy ziarna modelu × trzy
realizacje kontroli); kąty części opisuje średnia kołowa z zapisaną
koncentracją. Nie dopasowywano przesunięcia kąta ani symetrii sieci.
Ten wynik nie uzasadnia interpretowania latentu jako rozpoznanej orientacji.

## Koszt i sprawdzenia techniczne

Środowisko `netcat`: Python 3.12.12, Torch 2.9.1+cu128, RTX 5090.
Łączny czas fitów **469,09 s**, najdłuższy **33,03 s**. Maksimum tensorów
CUDA **390,61 MB**, RSS procesu **1,733 GB**. Wszystkie 297 checkpointów
zajmują około **891 MB**. Limitów treningu nie przekroczono.
To pomiary wykonanej próby, bez obietnicy kosztu innego modelu lub zbioru.

Wznowienie obu właściwych architektur w nowych procesach (6 kroków wobec
3 + zapis + 3) jest bitowo identyczne: wagi, optimizer, RNG i postęp,
maksymalna różnica 0. Osobny audyt z blokadą ścieżek referencji zachowuje
te same ID i hashe batchy, bez prób zabronionego odczytu. Predyktor ma
taką blokadę podczas przygotowania, inferencji i podziału.

Audyt eksportu przed zamrożeniem uzupełnia jawne wsparcie efektywne,
jednostki i dostępność. Sprawdza niezmienność tablic, relacji i przypisań;
nie uruchamia ponownego treningu lub podziału. Etykiety oceny są otwierane
dopiero po zapisaniu kompletnego manifestu hashy predykcji.

**143 testy STM Domains przeszły**. Sprawdzono m.in. modele i wznowienie,
geometrię resamplingu, niezależność siatki od centrów, puste grafy,
permutacje/remisy, konflikty MWS, mianowniki oceny, granice i blokadę
referencji do czasu zamrożenia. Weryfikacja 100 299 hashy poprzedziła
ocenę 25 200 predykcji; dodatkowe mapowanie centrów daje łącznie
26 160 rekordów oceny. Pomierzony przepływ od przygotowania cache do
końca oceny zużył **1056,61 s CPU** wobec limitu 7200 s; sama ocena
105,67 s CPU, maksymalnie 3,58 GiB RSS.

Finalny HTML zawiera 105 obrazów i 4200 głównych porównań; sprawdzono
15 interakcji w QtWebEngine, zero błędów JS. Obejrzano rzeczywiste
nakładki, screenshoty oraz wykresy rekonstrukcji/walidacji. To kontrola
galerii badawczej, bez odbioru natywnego okna STM Domains. Wszystkie
etapy obliczeń wykonano; wrapper sprawdzono składniowo, bez ponawiania
całej serii treningów tylko w celu sprawdzenia wrappera.

## Wniosek do 23

W tej konfiguracji AE/rVAE nie poprawia końcowego wyniku domen. Różnicę
trzeba rozpatrywać na trzech poziomach: cechy rVAE nie wydzieliły orientacji,
podział pozostawia scalenia/rozdrobnienie, a bramka porządku jednocześnie
odrzuca prawie całe TTMAPP i przepuszcza niezależne rzędy. Samo obniżenie
progu na podstawie tego testu nie byłoby uzasadnioną naprawą.

Zgodnie z przyjętą kolejnością następna jest ograniczona próba lokalnego
SSL w 22, potem wspólna decyzja 23. Ta sama bramka ograniczy także jej
końcowe coverage; porównanie przed odmowami nadal pozwoli ocenić cechy
i relacje. Nie stroimy jej w 22 na już obejrzanych kontrolach 21.
Rozszerzenie danych pozostaje warunkowe i nie jest teraz wymagane.
Koszt i wykorzystane 18 fitów należy uwzględnić we wspólnym budżecie
20–23; dla 22 pozostaje dziewięć zaplanowanych fitów.

## Artefakty i odtworzenie

Lokalny katalog wyników: `.scratch/autoencoder-21/`. Kod i polecenie całej
próby opisuje [AUTOENCODER.md](../../stmdomains/experiments/training/AUTOENCODER.md).
Wagi, wejścia, pełne wyniki i HTML pozostają poza Git. Git przechowuje
źródła, testy, raport i mały manifest dowodów.
Kod eksperymentu zachowuje również gałąź
`prototype/stmdomains-autoencoder-domains`; commit podano w przekazaniu
i odpowiedzi końcowej. Kod aplikacji nie został zastąpiony prototypem.

- `index.html`: pełne pola, wybór modelu i podziału, przed/po odmowach;
  osobny widok ograniczonego grafu testowego.
- `evaluation/`: CSV/JSON wszystkich kontroli, częściowych referencji,
  porównań przy wspólnym zakresie przypisań, stabilności i braków centrów.
- `feature-diagnostics.json`: rozrzut i efektywny rząd cech, związki
  z jasnością/numerem klatki oraz diagnostyka surowych kątów rVAE.
- `figures/`: krzywe walidacyjne i ustalony przykład rekonstrukcji.

Jedna skorelowana akwizycja, mały train i słaba wiarygodność zapisanej
rejestracji ograniczają wniosek. Bufor 8 px nie jest skalibrowanym błędem
rejestracji. Ani wynik pozytywny, ani negatywny tej próby nie rozstrzyga
skuteczności na innych molekułach lub podłożach. Odbiór natywnego GUI
i wybór metody produkcyjnej pozostają poza 21.
