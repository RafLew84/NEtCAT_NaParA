# Maskowane odtwarzanie obrazu — protokół 25

Data: 2026-11-01. Użytkownik bezpośrednio wybrał [25](issues/25-masked-autoencoder-domains.md)
po zakończeniu 24a. To osobny, ograniczony eksperyment na obecnych danych.
Nie zmieniamy źródeł ani wyników21/21a/22/24/24a. 26 i dodatkowe MPP/STP
pozostają odłożone. Parametry są zapisane także w
[protocol.json](../../stmdomains/experiments/training/masked_ae/protocol.json).

## Hipoteza i model

Czy przewidywanie zakrytych fragmentów obrazu daje cechy lepiej rozdzielające
domeny niż odtwarzanie całego obrazu, przy tej samej pojemności i kontekście?
Używamy dokładnie `Autoencoder(32)` z 21: 250 513 parametrów, wejście 1×64×64,
encoder 16/32/64, trzy konwolucje 3×3 stride 2 bez paddingu i BatchNorm, latent 32,
ten sam dekoder konwolucyjny. Wnioskowanie otrzymuje niezamaskowany pomiar;
do grafu trafia jego latent 32. Nie zwiększamy kontekstu ani liczby parametrów.

To konwolucyjne zadanie odtwarzania inspirowane
[publikacją MAE](https://arxiv.org/abs/2111.06377) i
[oficjalną implementacją](https://github.com/facebookresearch/mae/blob/main/models_mae.py).
Oryginał usuwa tokeny z encodera ViT; tutaj zerujemy bloki wejścia małego AE.
Nie nazywamy tego reprodukcją ViT-MAE ani nie zakładamy jego przyspieszenia.

Maska dzieli tensor na 16 bloków 16×16. Dla każdej próbki losujemy permutację
bloków: pierwsze 4 zakrywają 25%, pierwsze 8 zakrywają 50%. Główny kandydat
**mask50**, mask25 to ustalona diagnostyka. Maski są zagnieżdżone przy tym
samym stanie RNG. Generator masek jest oddzielny od samplera i augmentacji,
aby nie zmienić kolejności wycinków i ich zakłóceń względem zwykłego AE.
Zamaskowane wejście ma wartość 0, bez dodatkowego kanału lub parametru maski.
Zerowa jasność może występować w pomiarze; nie jest etykietą braku materiału.

Strata to MSE wyłącznie na **zamaskowanych i zmierzonych** pikselach celu.
Cel jest czystym, przestrzennie odpowiadającym wycinkiem z 20. Puste wsparcie
straty jest błędem; padding i brak pomiaru nigdy nie są celem. Przygotowanie
20 dopuszcza do uczenia tylko całe zmierzone wycinki. Diagnostyka sprawdzi
również jawnie maskę pomiaru i niezmienność straty przy zmianie poza nią.
Rekonstrukcja nie zastępuje MPP, oznaczeń ani dowodu istnienia molekuły.

## Dane i porównania

Podział, normalizacja, losowanie, skale 32/48/64 px, augmentacje i pełne
wsparcie pozostają zgodne z [20](self-supervised-training-protocol.md).
Trening transferu: 362 wycinki siatki, walidacja 270 łącznie dla trzech skal.
Główny wynik: siatka 48 px, krok 16 px. Pozostałe skale i wszystkie centra są
oddzielną diagnostyką tych samych wag. Bloki maski odpowiadają 8/12/16 raw px
w kolejnych skalach. Nie zmieniamy kalibracji na podstawie wyglądu domen.

24 klatki TTMAPP to znane dane rozwojowe jednej akwizycji. Osobny graf testowy
transferu korzysta wyłącznie z dostępnych węzłów testowych i ich krawędzi;
pełne nakładki są kontekstem. Nie twierdzimy, że to nowa akwizycja ani pełna
referencja powierzchni. Osobne refity transdukcyjne opisują tę samą serię.

Nowe kontrole: 31 znanych rodzin z 24 × ziarna 920031–920033 = 93 realizacje.
Ich wejście i referencje są rozdzielone. Maskowanie nie uczy się na syntetykach.
Cztery perturbacje samych oznaczeń zachowują obraz i prawdę: wymagamy
identycznych wyników siatki, a nie nazywamy tego odpornością na szum obrazu.
Szumiące/pasmowe obrazy mają ocenialną siatkę także bez centrów molekuł.

Porównujemy zapisane AE21 z32 (dokładnie ta sama pojemność i kontekst), SSL22 z32,
FFT i własne początkowe wagiAE. Nie trenujemy ponownie tych baz. Identyczne
wyniki baz na TTMAPP kopiujemy bitowo; nowe kontrole otrzymują nowe inferencje
starymi wagami i adapterami. Nowe adaptery/PCA/kwantyle dopasowujemy wyłącznie
w odpowiednim train. Bramka, graf, FH k=4 i MWS pozostają zgodne z 20.
Katalog wspólny dla zakresu nie oznacza automatycznego rozpoznania typu;
`type_id` i fizyczny kąt mogą pozostać nieokreślone.

32 reprezentacje: 12 maskowanych modeli + 6 AE + 6 SSL + 6 inicjalizacji + 2 FFT.
Pełne 3 skale × 2 samplery × 117 obrazów × 2 solvery = **44928 wyników**.
Osobne grafy transferu: 4608 archiwów, w tym 3648 dla 19 klatek testowych
oraz 960 pustych dla 5 klatek spoza testu, zgodnie z kontraktem 21/22.
Puste wyniki nie są dowodem jakości i otrzymują nieocenialny status.

## Trening i zamrożenie

Dwie maski × trzy ziarna 20261101–20261103 × dwa protokoły = **maks. 12 fitów**.
Transfer: 2000 kroków, batch 64, float32, AdamW lr 1e-3, weight decay 1e-4,
clip norm 1, bez AMP/schedulera zmieniającego LR. Co 100 kroków walidacja na
stałych wycinkach, transformacjach i maskach. Najmniejszy nieetykietowany MSE
wybiera checkpoint, remis wcześniejszy. Nie porównujemy wartości różnych
celów jako dowodu jakości domen.

Transdukcja: liczba kroków to mediana wybranych kroków trzech zakończonych
transferów danego udziału maskowania; zapisujemy ostatni checkpoint.
Brak trzech poprawnych transferów oznacza pominięcie odpowiednich refitów,
bez nowych ziaren. Zachowujemy inicjalizacje, pełne stany optymalizatora,
samplera, augmentacji i maski oraz krótki techniczny audyt wznowienia.

Osobny budżet 25: 900 s na fit, 10 800 s łącznie, 8 GiB tensorów GPU, 12 GiB RSS,
10 GiB checkpointów,7200 s CPU przygotowania/inferencji/oceny/audytów.
Pierwsze 100 kroków mierzy rzeczywisty koszt w ramach fitu. Nieudane etapy
zużywają budżet; nie dodajemy wariantów lub restartów po ocenie jakości.
Techniczne krótkie kontrole wznowienia zapisujemy oddzielnie od fitów jakości.
Używamy istniejącego środowiska i RTX 5090, bez instalacji lub zwiększania sprzętu.

Kod, protokół i wejścia przypinamy przed fitami, pełne predykcje przed
odczytem referencji do oceny. Stare wyniki pozostają zamrożone. Nowe ziarna
kontroli są powtórzeniami znanych rodzin; nie dowodzą generalizacji na STM.

## Kryteria i wynik

Zachowujemy miary i progi 20: zero domen na kontrolach negatywnych; jedna sieć
z coverage ≥0,90 i split ≤0,02; na rozdzieleniu coverage ≥0,50, każda część ≥0,30,
merge ≤0,02, split ≤0,10, F1 granicy ≥0,70. Granice siatki mierzymy osiowymi
krawędziami z tolerancją 8 reference_px; nie stosujemy tej miary do nieregularnych
centrów. Formalne porównania dopasowanego pokrycia, przewagi i stabilności
dotyczą głównej siatki 48; pozostałe skale i centra mają pełne metryki
diagnostyczne. Raportujemy przed/po odmowach, mianowniki, wspólne ID, dopasowane
pokrycie, stabilność ziaren, odmowy i nieocenialne wartości jako null.

TTMAPP ma częściowe wnętrza referencji: brak globalnego IoU lub dokładnego F1
granic. Transfer i transdukcja pozostają osobne, nieobecna grupa referencji
jest nieocenialna. Warunki pokrycia i stabilności są dokładnie te z 20.

Przewagę mask50 porównujemy **osobno z każdą z czterech baz**, przy tym samym
solverze i protokole: zmniejszenie średniego błędu par o ≥0,05 przy wspólnym
coverage ≥0,20 albo zysk coverage ≥0,10, bez wzrostu żadnego błędu o >0,02;
pozostałe kryteria nadal muszą być spełnione. Mediana trzech ziaren nie może
ukrywać przeciwnego znaku, a podstawowe progi dotyczą każdego ziarna.
Mocny wniosek o poprawie metody wymaga zaliczenia wszystkich kryteriów i
przewagi nad wszystkimi czterema bazami. Częściowy zysk względem pojedynczej
bazy, wyłącznie przed bramką lub tylko na syntetykach zostaje nazwany osobno.
Nie wybieramy maski, skali, solvera lub ziarna na podstawie oceny końcowej.

Wynik: raport, manifest, pełne nakładki i samowystarczalny HTML, diagnostyka
rekonstrukcji na stałych walidacyjnych przykładach, koszt i decyzja o korzyści
maskowania. Wynik negatywny jest dopuszczalny; odbiór 13 nie jest automatyczny.
