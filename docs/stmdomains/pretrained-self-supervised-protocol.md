# Adaptacja gotowego DINOv2 — protokół 26

Data: 2026-11-01. Użytkownik bezpośrednio wybrał
[26](issues/26-pretrained-self-supervised-adaptation.md) po zakończeniu 25.
To osobna ograniczona próba na obecnych danych; wcześniejsze źródła i wyniki
pozostają niezmienione. Dodatkowe MPP/STP są nadal odłożone.
Parametry maszynowe: [protocol.json](../../stmdomains/experiments/training/pretrained_ssl/protocol.json).

## Pytanie i zgodność

Czy dalsza samodestylacja gotowego encodera poprawia jego lokalne cechy
do rozdzielania domen względem **tych samych wag przed adaptacją**?
Punktem wyjścia jest istniejący DINOv2 ViT-S/14 bez rejestrów z 18:
22 056 576 parametrów, 12 bloków, 384 kanały. Wagi SHA-256
`b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9`,
kod upstream `7764ea0f912e53c92e82eb78a2a1631e92725fc8`.
Korzystamy z lokalnych zasobów i istniejącego Torch/netcat; nie zmieniamy
wymagań wspólnych aplikacji. Techniczny preflight sprawdzi zgodność z CUDA.

To lokalna samodestylacja **inspirowana DINO**, nie odtworzenie całego
treningu DINO/DINOv2 ani iBOT. DINO dostarcza pomysł nauczyciela EMA,
centrowania i wyostrzania rozkładu. iBOT obejmuje dodatkowo przewidywanie
zakrytych tokenów, którego tutaj nie stosujemy.
[DINO](https://arxiv.org/abs/2104.14294),
[oficjalny trening DINO](https://github.com/facebookresearch/dino/blob/main/main_dino.py),
[iBOT](https://arxiv.org/abs/2111.07832),
[przypięty kod DINOv2](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/layers/attention.py).

Nie używamy rozproszonego trenera, ścieżki list/nested tensors ani xFormers.
Zwykła ścieżka tensorowa SDPA jest dostępna w przypiętym kodzie. Preflight
porówna własny wrapper z oryginalnym `forward_features`, bez treningu na
referencjach. Weryfikujemy pliki źródłowe względem przypiętego archiwum.

## Wejście, model i cel uczenia

Zachowujemy podział, normalizatory, miejsca i wsparcia z 20: 24 klatki,
362 okna train i 270 validation, łącznie dla skal 32/48/64 px. Transdukcja
ma 11 616 dostępnych okien. Siatka ma krok 16 px. Główna ocena: grid48;
pozostałe skale i centra są diagnostyką tych samych wag.

Dokładny wycinek 64 × 64 z 20 jest interpolowany biliniowo do 112 × 112
(`align_corners=False`), kopiowany do RGB i normalizowany stałymi ImageNet
mean/std. Ta sama transformacja obowiązuje przed i po adaptacji. Nie
uzupełniamy brakującego pomiaru. Nie są to stare wejścia 18/19: miały inne
normalizatory, krok i obsługę brzegu, więc nie kopiujemy ich predykcji jako
bezpośredniej bazy. Niezmieniony model otrzymuje nową inferencję.

Uczymy ostatni blok transformera i końcowy LayerNorm. Pozostałe parametry
backbone są bitowo niezmienne. Głowica DINOHead: 384→256→64, GELU, L2,
wyjście 256 z normalizacją wag; bez BatchNorm. Skala `weight_g=1` pozostaje
zamrożona; reszta głowicy jest uczona. Łącznie **1 907 392** parametrów
ucznia podlega optymalizacji. **256 wyjść głowicy nie jest liczbą domen.**

Dwa widoki tego samego miejsca mają niezależne augmentacje z 20:
przesunięcia ±2 raw px, gain 0,9–1,1, offset ±0,1 i szum sigma 0–0,03.
Nie dokładamy obrotów, zmian skali ani pozytywnych par z innych miejsc
lub klatek. Dopasowujemy 36 wewnętrznych kotwic siatki tokenów 8 × 8:
indeksy 1…6, `view_index = canonical_index − 8 * shift_raw / scale_raw`.
Deterministyczne wagi biliniowe i `bmm` nie wymagają ekstrapolacji.
Attention nadal czyta cały wycinek: kotwica tokenu nie ogranicza jego kontekstu.

Strata to symetryczna entropia krzyżowa między odpowiadającymi tokenami
ucznia i nauczyciela z przeciwnych widoków. Nauczyciel zaczyna jako dokładna
kopia ucznia; po kroku optymalizatora aktualizujemy jego uczoną część EMA
z kosinusowym momentum 0,996→1. Centrum logitów ma momentum 0,9;
temperatura nauczyciela 0,04, ucznia 0,1. Centrum i EMA używają tylko train.
Zamrożony prefiks można obliczyć raz na widok pod `no_grad` i współdzielić.

Opis do grupowania to **średnia końcowych `x_norm_patchtokens`, 384 liczby**,
bez CLS, głowicy i dodatkowego L2 w ekstraktorze. Operacja jest identyczna
przed i po adaptacji i odpowiada odczytowi warstwy z 18. Nie dodajemy drugiej
macierzy podziałów ze spłaszczonych tokenów. Model nie zwraca skalibrowanego
kierunku, rozstawu ani typu struktury; katalog i `type_id=null` pozostają jawne.

## Trening i kontrola degeneracji

Jeden wariant × ziarna 20261101–20261103 × transfer/transdukcja = **6 fitów**.
Każdy ma z góry **1000 kroków, batch64**, ostatni encoder nauczyciela EMA
jest jedynym głównym checkpointem. Uczeń pozostaje diagnostyką.
To jawne odstępstwo od selekcji/mediany kroków z 20: strata zmieniającego się
nauczyciela nie jest stałym celem wyboru checkpointu. Nie wybieramy wag
według jakości domen ani minimum takiej straty.

AdamW: lr backbone 2e−5, głowicy 2e−4, rozgrzewka 50 kroków i kosinus do
10% lr; weight decay 0,04 tylko dla macierzy, clip norm 1. Float32, bez AMP
i TF32. Walidacja co 100 kroków ma stałe pary, bez aktualizacji EMA/centrum.
Pokazuje zgodność widoków, dryf względem zamrożonych cech oraz STD/rząd
deskryptora. Osobno zapisujemy `H(mean p)`, `mean H(p)` i ich różnicę:
sama duża entropia marginalna nie wyklucza jednostajnego zapadnięcia głowicy.

Niefinite wartości lub maksymalne STD tokenów/deskryptora ≤1e−6 kończą run.
Różnica entropii ≤1e−6 w dwóch kolejnych minibatchach train po kroku 50 również
oznacza degenerację zadania. Diagnostyka nie wybiera alternatywnych wag.
Brak udanego ziarna jest brakiem dowodu; nie zastępujemy go nowym fitem.
Transdukcja ma niezależny ustalony czas, bez wyboru na testach transferu.

Checkpoint co 100 kroków i inicjalizacja zawierają delty ucznia/nauczyciela,
głowice, centrum, optymalizator, harmonogram i wszystkie RNG. Zamrożony
prefiks odtwarzamy z bazowego pliku o sprawdzonym SHA; audyt wymaga ścisłego
zbioru kluczy. Krótkie techniczne wznowienia mają odrzucone wagi.

Osobne limity 26: 900 s/fit, 5400 s fitów łącznie, 8 GiB tensorów GPU,
12 GiB RSS, 10 GiB checkpointów i 7200 s CPU pozostałych etapów.
Walidacja i zapis wliczają się do fitu. Watchdog procesu daje 30 s na
start i zapis końcowy ponad wewnętrzny limit 900 s; łączny limit 5400 s
obejmuje zmierzony czas procesów. Kolejny fit wymaga pozostających 930 s. Zewnętrzny wrapper zbiera status
oraz CPU/RSS przez `wait4`, także po przerwaniu procesu; do rachunku dodaje
tylko koszt nieuwzględniony w ledgerze wewnętrznym. Nie zwiększamy sprzętu
ani budżetu po obejrzeniu wyników.

## Porównanie, zamrożenie i dwa wnioski

Bazy: oryginalny DINOv2 oraz FFT, każda osobno dla normalizacji i adaptera
transferu/transdukcji. Bazy bez ziarna są wspólnym odniesieniem do trzech
ziaren adaptacji; nie powielamy ich jako fikcyjnych powtórzeń. L2/PCA24,
kwantyle relacji, graf, FH k=4, MWS i bramka porządku pozostają z 20.
Adaptery DINO pasują wyłącznie do dozwolonego train. Pomiarowe cache i
zapisane FFT z 21 zachowujemy bitowo. Żadne referencje nie trenują modelu.

Nowe kontrole: 31 znanych rodzin × ziarna 930031–930033 = 93 realizacje.
Mają oddzielne pliki wejścia i prawdy. Dziesięć reprezentacji daje najwyżej
**14 040 pełnych wyników i 1440 archiwów testowych**; z tych ostatnich
1140 dotyczy 19 klatek testowych, 300 jest jawnie pustych poza testem.
Nieudany fit zmniejsza macierz z podaną przyczyną i uniemożliwia kwalifikację.
Kod/protokół/wejścia przypinamy przed fitami, predykcje przed oceną referencji.

**Poprawa reprezentacji przed odmowami** wymaga kryteriów pozytywnych z 20
dla każdego ziarna: pojedyncza sieć oraz cztery główne granice, rozłączne
wyspy i przerwa. To siedem rodzin, 21 realizacji na ziarno. Progi: jedna
sieć coverage≥0,90 i split≤0,02; dwie części coverage≥0,50, każda≥0,30,
merge≤0,02, split≤0,10, F1 istniejącej granicy≥0,70. Do tego stabilność
przed odmowami oraz osobna przewaga nad **obiema** bazami na pozytywnych
kontrolach i częściowych referencjach TTMAPP. Negatywne obrazy nie muszą
mieć zera komponentów przed bramką — ten etap przypisuje je z definicji.

Przewaga zachowuje progi 20: redukcja średniego błędu par o ≥0,05 przy
wspólnym coverage≥0,20 albo zysk coverage≥0,10 bez wzrostu błędu o >0,02;
mediana nie może ukrywać przeciwnego znaku, brak/null nie jest zaliczeniem.
Pełne porównania wszystkich rodzin i częściowe korzyści pozostają w raporcie.

**Kwalifikacja całego detektora po odmowach** zachowuje komplet wymagań 20,
w tym brak domen na negatywach. Ma znane ograniczenie: niezmieniona bramka
grid48 dopuszcza najwyżej 0/174 okien transferu i 4/782 transdukcji TTMAPP
po minimum czterech elementów ([audyt 22](local-self-supervised-trial.md)).
Same nowe cechy nie usuną tego limitu. Werdykt reprezentacji przed bramką
nie jest przyjęciem detektora; 13 pozostaje osobnym odbiorem.

TTMAPP jest jedną znaną akwizycją, a kontrole nowymi realizacjami znanych
rodzin. Brak dokładnych granic i pełnej referencji powierzchni TTMAPP.
Coverage okien nie jest wykrywalnością molekuł. Zmiana samych oznaczeń
sprawdza niezależność siatki od anotacji, nie odporność na szum obrazu.
Nie wybieramy solvera, skali lub ziarna na podstawie wyniku końcowego.
