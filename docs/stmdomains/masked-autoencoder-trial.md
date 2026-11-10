# Maskowane odtwarzanie obrazu — wynik 25

Data: 2026-11-01. [Ticket 25](issues/25-masked-autoencoder-domains.md).
[Protokół](masked-autoencoder-protocol.md) przypięto przed treningiem;
[manifest](masked-autoencoder-manifest.json) zachowuje źródła i dowody wyniku.
Galeria lokalna: `.scratch/masked-ae-25/index.html`.

**Maskowanie poprawia uzupełnianie zakrytych pikseli, ale nie daje poprawy
końcowych domen TTMAPP.** Jest częściowy zysk na syntetykach względem zwykłego
AE, bez zbiorczej przewagi nad pozostałymi bazami i bez zaliczenia kryteriów próby.
Zakończono eksperyment, nie przyjęto detektora. Odbiór 13 pozostaje otwarty;
26 i przygotowanie dodatkowych MPP/STP nadal są niewybrane/odłożone.

## Pytanie i zakres

Czy odtwarzanie zakrytych fragmentów daje lepsze cechy do rozdzielania domen
niż zwykły autoencoder, przy tej samej pojemności i kontekście? Użyto dokładnie
konwolucyjnego AE32 z 21: **250 513 parametrów**, wejście 64 × 64 i latent 32.
To inspiracja zadaniem MAE, bez odtwarzania architektury ViT-MAE.

Dwa warianty zakrywają 4 lub 8 z 16 bloków po 16 × 16 pikseli tensora.
Głównym kandydatem jest ustalony wcześniej **mask50**; mask25 to diagnostyka.
Strata obejmuje tylko zakryte, rzeczywiście zmierzone piksele. Zamaskowane
wejście ma wartość zero; brak pomiaru nie jest celem rekonstrukcji.
Do wyznaczania cech domen trafia **oryginalny, niezakryty pomiar**.
Odtworzony obraz nie zastępuje danych STM ani oznaczeń molekuł.

24 znane klatki TTMAPP i podział z 20 pozostają niezmienione. Transfer ma
362 wycinki treningowe i 270 walidacyjnych łącznie dla skal 32/48/64 px.
Główna ocena dotyczy siatki 48 px z krokiem 16 px; pozostałe skale i centra
są diagnostyką. Blok maski odpowiada kolejno 8/12/16 pikselom pomiaru.
93 nowe kontrole to 31 znanych rodzin × ziarna 920031–920033, bez uczenia
na syntetykach. To nowe realizacje tych samych rodzin, nie nowe pomiary STM.

Porównania obejmują zapisane AE21 o identycznej pojemności, SSL22, FFT
oraz własne inicjalizacje. Bazy nie były ponownie trenowane. Na TTMAPP
skopiowano ich zapisane cechy, adaptery i predykcje bitowo; na nowych kontrolach
zastosowano stare wagi i adaptery. Bramka porządku, graf, FH k=4 i MWS
pozostały zgodne z 20. Nie dobierano progów na podstawie referencji domen.

## Domeny TTMAPP

Główna siatka 48 px, **po odmowach**. Mianowniki to okna z dostępnym
wsparciem i częściową pozytywną referencją, nie liczba molekuł. Transfer
korzysta z osobnego grafu testowego. Zakres oznacza trzy ziarna modelu;
FFT jest pojedynczą deterministyczną bazą.

| Reprezentacja | Transfer, FH i MWS | Transdukcja, FH | Transdukcja, MWS |
| --- | ---: | ---: | ---: |
| **mask50 — główny kandydat** | **0/174** | **4/782 (0,51%)** | **0/782** |
| mask25 — diagnostyka | 0/174 | 4/782 | 0/782 |
| Zwykły AE21 | 0/174 | 4/782 | 0/782 |
| Lokalne SSL22 | 0/174 | 4/782 | 0/782 |
| Własna inicjalizacja | 0/174 | 4/782 | 0–4/782 |
| FFT | 0/174 | 4/782 | 4/782 |

Przed odmowami każdy wariant przypisuje wszystkie oceniane okna. Nie oznacza
to poprawnego podziału: mask50 z FH scala różne referencje, a MWS nadmiernie
dzieli wnętrza. Zakresy błędów par dla mask50 przed odmowami:

| Protokół i solver | Błąd scaleń | Błąd podziałów |
| --- | ---: | ---: |
| Transfer, FH | 71,4–100% | 0–6,9% |
| Transfer, MWS | 0% | 82,6–86,9% |
| Transdukcja, FH | 94,3–96,0% | 7,4–10,7% |
| Transdukcja, MWS | 24,8–34,5% | 70,9–77,3% |

Pary sumujemy wyłącznie wewnątrz klatek. Po odmowach brak wystarczających
par różnych referencji daje **null**, nie zerowy błąd. TTMAPP nie ma pełnej
prawdy granic, więc nie podajemy F1 granicy ani globalnego IoU.
Problem nie sprowadza się do samej bramki: podziały przed nią również
nie rozdzielają wiarygodnie referencji.

Transfer reprezentuje grupy referencji jako 172/2/0 okien; trzecia grupa
jest nieocenialna, nie otrzymuje zerowego wyniku. W transdukcji cztery
zachowane okna należą do pierwszej grupy: 4/671, 0/9 i 0/102 dla kolejnych
grup. Nie jest to rozpoznanie wszystkich trzech orientacji.

## Kontrole i porównanie z bazami

Żaden z czterech wariantów mask50 (transfer/transdukcja × FH/MWS) nie
spełnił pełnej kwalifikacji. Nie zaliczono wspólnie kontroli, stabilności,
pokrycia TTMAPP i wymaganej przewagi nad wszystkimi czterema bazami.
Mask25 również nie kwalifikuje metody; pozostaje diagnostyką.

Istnieje **częściowy zysk transferowego FH względem AE21 na syntetykach**:
mediana zmniejszenia błędu par przy wspólnym pokryciu wynosi 0,23390 przed
odmowami i 0,24428 po nich, bez medianowego wzrostu coverage. Warunku
przewagi w łącznej ocenie wszystkich rodzin nie zaliczono względem SSL,
własnej inicjalizacji ani FFT. Nie ma jej również na TTMAPP. Ten wynik
nie zastępuje progów jakości poszczególnych kontroli.
Zysk występuje wyłącznie w połączonej ocenie wszystkich rodzin: jedno ziarno
remisuje, dwa mają mniej fragmentacji; wspólny błąd scaleń pozostaje 55,04%.
Żadna pojedyncza rodzina nie przechodzi całego warunku przewagi nad AE21.

Jest też izolowany zysk mask50/FH względem FFT na dwóch orientacjach
po odmowach, w obu protokołach: mediana redukcji błędu par 0,11336,
bez zmiany pokrycia. Nie jest to przewaga w pełnym zestawie kontroli;
F1 granicy dla mask50 nadal wynosi 0.

Dla mask50 F1 czterech głównych granic — dwóch orientacji, różnicy 8°,
różnego rozstawu i przesunięcia — wynosi **dokładnie 0** w każdym ziarnie,
przed i po odmowach, w obu protokołach i solverach. Tak samo wypadają tutaj
mask25, AE21 i SSL22. Lepszy zagregowany błąd par względem AE nie oznacza
więc odtworzenia rzeczywistych granic kontrolnych.

Każde ziarno mask50 w obu protokołach i solverach zalicza **51/69 wymaganych
realizacji**, czyli 17 z 23 wymaganych rodzin. Zawsze zawodzą cztery granice
wymienione wyżej, niezależne rzędy oraz faza z zaburzonymi oznaczeniami.
Osiem dodatkowych rodzin ma charakter diagnostyczny i nie wchodzi do tego
mianownika. Dla porównania FFT/FH w transferze uzyskuje F1 po odmowach
0 / 0,093 / 0 / 0,571 dla tych czterech granic — również poniżej wymaganego
0,70. Wynik nie wybiera FFT jako gotowego detektora.

## Rekonstrukcja i opis obrazu

Model nauczył się zadania uzupełniania pikseli. Na **identycznych wejściach
z maską 50%** mediana błędu zakrytych pikseli spada z 0,11605 dla AE21
do 0,04878 dla mask50. Sparowana redukcja błędu wynosi **58,80%**
(55,05–61,24% między ziarnami). Nie porównujemy tu różnych funkcji straty:
każdy model otrzymał ten sam zakryty obraz i oceniano te same piksele.

Poniżej mediany trzech ziaren, 270 tych samych okien walidacyjnych.
Pełne liczniki błędów i zakresy są w `feature-diagnostics.json`.

| Maska zadania | Model | MSE zakrytych pikseli | MSE widocznych | MSE całości |
| --- | --- | ---: | ---: | ---: |
| 25% | Zwykły AE21 | 0,13524 | 0,03743 | 0,06188 |
| 25% | Inicjalizacja | 0,27267 | 0,27517 | 0,27454 |
| 25% | mask25 | 0,04344 | 0,04067 | 0,04117 |
| 25% | mask50 | 0,04638 | 0,04311 | 0,04383 |
| 50% | Zwykły AE21 | 0,11605 | 0,04490 | 0,08323 |
| 50% | Inicjalizacja | 0,27414 | 0,27495 | 0,27454 |
| 50% | mask25 | 0,05553 | 0,04219 | 0,04886 |
| 50% | mask50 | 0,04878 | 0,03981 | 0,04381 |

To walidacja wykorzystana do wyboru checkpointów, **nie nowy test**.
Na stałych przykładach modele maskowane lepiej uzupełniają rozległe jasne
i ciemne obszary, ale wygładzają drobną teksturę. Nie jest to dowód
odtworzenia położeń molekuł. Krzywe pokazują spadek błędu treningowego
i wypłaszczenie walidacji około 800–1300 kroków, bez rozbiegania optymalizacji.

Deskryptory nie są stałym wektorem. Dla mask50 efektywny rząd reprezentacji
32-wymiarowej wynosi 12,95–17,23 w transferze i 10,68–12,06 w transdukcji;
wszystkie odchylenia standardowe są dodatnie. Rząd jest niższy niż dla AE21.
Część współrzędnych silnie koreluje z jasnością; to opis cech, bez dowodu
przyczynowego wyjaśniającego jakość podziału domen.

## Trening i koszty

Zakończono **12/12 fitów**, 19 800 kroków, bez dodatkowych prób jakości.
Transfer: po 2000 kroków; checkpoint wybiera stała nieetykietowana walidacja.
Wybrane kroki dla ziaren 20261101/02/03: mask25 — 800/1300/1300;
mask50 — 1300/1300/900. Obie mediany wynoszą 1300, tyle trwa każdy
odpowiedni fit transdukcyjny. Nie wybierano korzystnego ziarna po ocenie domen.

Suma zapisanych czasów treningów to **349,86 s** na RTX 5090; najdłuższy 38,70 s.
Szczyt alokacji tensorów GPU: 114 289 664 B; RSS treningu: 2 042 290 176 B.
198 okresowych checkpointów i 12 inicjalizacji zajmuje 752 207 252 B.
Wykorzystano istniejące środowisko netcat, bez instalacji.

Suma zmierzonych etapów poza fitami wynosi **2002,12 s CPU**. Osobna
konserwatywna rezerwa 900 s za przerwaną ocenę daje **2902,12 / 7200 s**
obciążenia budżetu. Najwyższy zarejestrowany RSS to 4 280 102 912 B.
To pomiary procesów raportujących; nie obejmują w pełni pomocniczych
procesów renderera QtWebEngine ani każdego wywołania powłoki. Rezerwa
przerwania nie jest pomiarem i nie została włączona do sumy zmierzonej.

**Ograniczenie porównania:** dawny AE21 w transdukcji miał 600 kroków,
a maskowane modele 1300. Pojemność i kontekst są identyczne, liczba kroków
transdukcji różna. Transfer obu prób kończył 2000 kroków. Audyt potwierdził
identyczne próbki i augmentacje wszystkich 15 600 wspólnych kroków z AE21
oraz 9900 par kroków mask25/mask50. Maska korzysta z osobnego RNG.

## Zapis i sprawdzenia

Macierz obejmuje **44 928 pełnych wyników**: 32 reprezentacje × 117 obrazów
× 3 skale × 2 samplery × 2 solvery. Osobno zapisano 4608 grafów transferu;
960 z nich jest jawnie pustych dla pięciu klatek spoza testu. Pełna nakładka
klatki jest kontekstem oglądania; ocena transferu korzysta z grafu testowego.

Audyt eksportów przeszedł dla **9 934 272 wierszy przypisań**, wszystkich
44 928 + 4608 archiwów i 192 adapterów. Potwierdził pełne wsparcie, osobny
zakres testu, identyfikatory, geometrię i zgodność JSON/NPZ. Bitowo zgodne
z bazami są 432 pliki cache, 1728 archiwów cech, 84 adaptery oraz **18 144
pliki predykcji**. Żadne przypisanie nie ominęło przypiętej bramki porządku.
Zamrożono 172 372 lokalne pliki oraz 20 466 plików zewnętrznych.
Końcowa kontrola kontraktu nie zmieniła żadnego z 49 536 wyników.
Referencje do oceny otwarto dopiero po zamrożeniu i weryfikacji hashów.

Pierwszy proces oceny w sandboxie zakończył się sygnałem SIGTERM (kod 143)
po komunikacie o 29 000 rekordów, bez wyjątku Pythona i bez gotowych wyników
oceny. Przyczyna środowiskowa nie została potwierdzona. Zachowano zapis
przerwania i obciążono budżet konserwatywną rezerwą **900 s CPU**; nie jest
to zmierzony czas. Górne ograniczenie czasu ściennego od końca zamrożenia
do odnotowania awarii wyniosło 284,67 s. Samą niezmienioną ocenę uruchomiono
ponownie poza sandboxem pod `/usr/bin/time`, bez treningów, ponownych
predykcji, zmiany parametrów lub źródeł przypiętych w planie.
Powtórzenie zakończyło się poprawnie: 44 928 predykcji, **46 464 rekordy
oceny** (w tym diagnostyczne przypisanie centrów z siatki), 22 464 porównania
przy wspólnym pokryciu. Zmierzono 177,05 s CPU etapu i 4 280 102 912 B RSS;
nie przekroczono limitu 12 GiB. Ukończenie poza sandboxem nie ustala samo
w sobie przyczyny pierwszego przerwania.

Sześć testów maskowania przeszło. Preflight CUDA sprawdził dla trzech ziaren
bitowo identyczne wznowienie 6 kroków względem 3 + odtworzenie + 3, łącznie
36 technicznych kroków na sztucznych danych; ich wagi odrzucono.
Sprawdzono izolację zakrytego wejścia, gradientów, niemierzonych pikseli,
inicjalizacji oraz generatorów masek i augmentacji. To sprawdzenia działania
programu, a nie dowód jakości domen.

Niezależny audyt wejścia objął 117 obrazów, 702 grupy cache, 135 912 wierszy,
3996 odtworzonych wycinków oraz ponowne sprawdzenie po usunięciu oznaczeń.
684 archiwa siatki w parach obrazów o zmienionych tylko oznaczeniach są
identyczne. Zachowano podział i normalizację z 20 oraz pełne wsparcie pomiaru.

Skopiowane JSON baz zachowują identyfikatory protokołów 21/22; powiązanie
z 25 zapisuje nowy indeks i rejestr kopii. W eksporcie `support_xyxy`
oznacza wsparcie cech, a `effective_support_xyxy` obejmuje również margines.
Odziedziczone miary nakładania w artefaktach relacji dotyczą tego drugiego
wsparcia i nie sterują solverem. Typ oraz fizyczna orientacja pozostają
nieokreślone; kolor komponentu nie jest rozpoznanym typem struktury.

Galeria ma 117 obrazów, 32 reprezentacje i 7488 zapisanych widoków podziału
dla siatki 48, siedem scenariuszy oraz dwie osadzone figury. Działa jako
samowystarczalny HTML bez ponownej inferencji. QtWebEngine: **143 sprawdzenia
interakcji, zero błędów JavaScript**, pięć zrzutów obejrzanych wizualnie.
Sprawdzono oba solvery, wszystkie modele, zakres testowy, punkty, nawigację
i figury. Widoczny opis mówi, że punkty są środkami okien siatki, nie
wykrytymi molekułami. To kontrola galerii badawczej; natywnej aplikacji
nie uruchamiano ani nie zmieniano. Źródło odziedziczonego renderera
`training/gallery.py` dodatkowo przypięto w audycie GUI i potwierdzono
jego zgodność z commitem sprzed fitów.

Niezależny audyt metryk przeszedł bez importowania produkcyjnych funkcji
oceny: 192 872 hashe, 7488 wyników głównej siatki, 14 976 etapów przed/po,
22 464 porównania wspólnego pokrycia, 6336 agregatów porównań, 2112 warunków
przewagi, 2340 ocen stabilności i 24 decyzje kwalifikacji. Wszystkie 672
bazowe rekordy TTMAPP są zgodne z ocenami 21/22. Audyt obejmuje również
niezależne odtworzenie F1, liczników par i zera/jednego/dwóch przypisanych
końców krawędzi przecinającej referencyjną granicę.

Końcowo potwierdzono niezmienność **192 872** unikalnych plików zamrożonych,
zewnętrznych i źródłowych oraz zgodność źródeł z `b8fdc9a`. Przeszły:
429 odnośników dokumentacji, acykliczny graf 28 ticketów i `git diff --check`.
Osobne sprawdzenie manifestu zachowało bitowo pełne lokalne podsumowanie;
wersjonowany skrót wskazuje hashami także zrzuty, audyty i szczegółowe tabele.

## Ograniczenia i odtworzenie

TTMAPP jest wielokrotnie oglądaną, pojedynczą akwizycją z częściowymi
pozytywnymi referencjami. Nie znamy dokładnych granic ani pełnej powierzchni
materiału. Odsetek przypisanych elementów nie jest wykrywalnością molekuł.
Zmiana samych oznaczeń przy identycznym obrazie sprawdza niezależność siatki
od oznaczeń, nie odporność na szum pomiaru. Rekonstrukcja na walidacji
wybierającej checkpoint nie jest niezależnym testem generalizacji.

Instrukcja odtworzenia:
[README prototypu](../../stmdomains/experiments/training/masked_ae/README.md).
Kod: `stmdomains/experiments/training/masked_ae/`; duże wyniki i modele
w `.scratch/masked-ae-25/`, poza Git. Podjęcie: `36d5cb1`; źródła przypięte
przed fitami: **`b8fdc9a`**. Prototyp zachowuje gałąź
`prototype/stmdomains-masked-autoencoder`; bieżąca praca pozostaje na
`domains/start`. Nie zmieniano modułów wspólnych ani innych worktree.
