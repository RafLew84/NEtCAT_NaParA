# E3 — zamrożony protokół fotometrii i stabilności

2026-11-11, `ml_domain`, baza `ed4762b`. Zakres z planu E0–E7 i zlecenia
użytkownika „wykonaj E3”. Ustalony przed inferencją na danych eksperymentu.
Środowisko `netcat`; nie instalować zależności, nie zmieniać wag/aplikacji.

## Pytanie i jednostka

Czy kontrolowana zmiana fotometrii tego samego wycinka zmienia zamrożone
cechy, lokalne relacje i domeny bardziej niż zadane zmiany struktury?
Alternatywy: cechy przesuwają się wspólnie, pozostawiając relacje stabilne;
problem leży w bramce; amplituda zawiera informację o strukturze.
To parowana diagnostyka jednej znanej akwizycji rozwojowej i syntetyków.
Okna, krawędzie i ziarna modeli nie są niezależnymi akwizycjami.
Nie raportować testów istotności ani wyboru nowego detektora.

## Stałe dane, modele i podział

Wszystkie 105 obrazów E2: 24 STM i 81 dotychczasowych syntetyków. Skala 48,
centra i siatka, historyczne zakresy transferu/transdukcji i te same krawędzie.
Transfer oceniany tylko na dawnych węzłach testowych; transdukcja in-sample.
Te same 12 checkpointów AE/rVAE z32 (2 reżimy × 2 modele × 3 ziarna).
Odczyty E2: AE, treść+kąt rVAE, treść, kąt, FFT, fotometria, geometria ACF.
Wszystkie 60 adapterów z zapisów E2, bez refitu, zmiany PCA, progów lub wag.
FH k=4 i MWS; minimum 4 siatka / 8 centra. Brak oracle i nowych etykiet.

Nowa inferencja tylko `encode()`, posterior mean, eval, float32, batch 128,
deterministyczne algorytmy, bez dekodera i próbkowania latentów.
CPU, jeden wątek: CUDA jest obecnie niedostępna. Techniczny pomiar na
stałych sztucznych wejściach, bez danych zadania: 640 wycinków około 0.02 s.
Nie traktować go jako wyniku naukowego ani gwarancji czasu pełnej próby.
Świeży odczyt identity porównać z cache E2 (rtol=1e-4, atol=1e-5; odrębny
zapis różnicy backendu i podziałów). Przekroczenie tolerancji zatrzymuje próbę
do wyjaśnienia. Główne różnice liczyć względem świeżego identity na tym samym
backendzie; osobno zachować historyczny replay. Nie ukrywać zmiany etykiet
komponentów przez porównywanie samych numerów ID.

## Dziesięć warunków

Operacja po historycznej normalizacji i ekstrakcji, na wejściu 64×64.
Native 48×48 dla FFT/ACF jest wyciągane z surowych danych, nigdy zmniejszane
z 64. Te same bezwymiarowe operacje osobno w obu rozdzielczościach.
Zgodnie z dawną augmentacją **bez ponownego clippingu po perturbacji**.

| Warunek | Operacja |
| --- | --- |
| identity | x |
| offset_minus / offset_plus | x − 0.1 / x + 0.1 |
| gain_minus / gain_plus | 0.9x / 1.1x |
| noise | x + N(0, 0.03²) |
| gradient_x_minus / gradient_x_plus | x − gu / x + gu |
| gradient_y_minus / gradient_y_plus | x − gv / x + gv |

u,v to osie `linspace(-1,1,size)`. g ustalić osobno dla reżimów tylko na
dawnych fit ID siatki s48: transfer 96 okien, transdukcja 3456. Dopasować
płaszczyznę do każdego wejścia 64×64; g = clip(mediana(|a|+|b|),0.02,0.10).
To ograniczona amplituda diagnostyczna, nie pomiar dryfu aparatury. Zapisać
rozkład, ID i hashe kalibracji przed właściwą inferencją/oceną. Centra używają
tego samego g; syntetyki nie uczestniczą w kalibracji.
Szum deterministyczny: seed 20261111, klucz window_id + rozmiar, wspólny
dla wszystkich modeli i obu reżimów. Pola 48 i 64 są różnymi realizacjami;
nie interpretować ich różnicy jako czystego efektu architektury. Warunki są
pojedynczymi interwencjami; brak rotacji równoczesnej z fotometrią.
Kolejność wykonania grup losowana raz seed 20261111, zapisana w manifeście;
identity zawsze przed porównywanymi warunkami wewnątrz grupy.

Perturbacje są lokalne dla wycinków. Nie tworzą nowego spójnego pełnego
skanu (szum i gradient zależą od wycinka). Przeglądarka pokazuje oryginalny
pełny obraz i wynik diagnostyczny oraz osobno przykład zmienionego wejścia.
Zapisać początkowy udział pikseli na 0/1, końcowy udział poza [0,1], RMSE,
średnią i odchylenie. Początkowe nasycenie nie odtwarza utraconych surowych
wartości; nie wolno nazywać go nowym clippingiem.

## Oddzielne pary strukturalne

Stały renderer z repo: Gaussian PSF 1.25, noise 0.025, most jednostek
clip(0.5+0.4*sygnał,0,1), pole 96×96, środkowy wycinek 48, wejście 64.
9 realizacji = fazy bazowe (0,0),(2,1),(4,3) × seeds 20261111–20261113.
W każdej parze to samo pole szumu, PSF, gain i offset:
identity; obrót sieci 8°; rozstaw 12→16; przesunięcie fazy o (0,4).
Zmiana liczby pików/średniej przy rozstawie pozostaje częścią struktury;
nie normalizować jej post hoc. Wszystkie perturbacje fotometrii stosować
też do identity tych samych 9 realizacji, nigdy łączyć ich ze strukturą.
Te pary porównują ruch cech, nie dokładność domen ani fizyczny kąt rVAE.
Stosunek ruchu fotometria/struktura ma sens tylko dla tych zadanych amplitud;
nie jest uniwersalną miarą przewagi zakłóceń. Brak nowych etykiet do uczenia.

## Odczyty i mianowniki

1. Ruch cech native/L2/adapted: norma bezwzględna, względna względem
   normy bazowej, zmiana normy. Zero normy bazowej → brak względnej miary.
   Dla rVAE także kołowa różnica kąta oraz ruch wyjścia przesunięcia,
   bez deklaracji fizycznej orientacji/przemieszczenia molekuły.
2. Zmiana dystansów krawędzi, Spearman z obsługą stałych danych, zmiana
   stanów przyciąganie/neutralne/odpychanie przy zamrożonych q25/q75
   tylko w przestrzeni adapted, w której te progi były kalibrowane.
   Wspólne wsparcie identity/warunek oraz przecięcie 15 odczytów obok
   własnej dostępności. ROC/AP dostępnych relacji referencyjnych z E2,
   bez uzupełniania brakujących par lub uznawania nieoznaczonego tła za negatyw.
3. Domeny dla FH/MWS: H_M1 (bazowa twarda ważność), A_fixed_M1 (cała
   bramka identity), A_updated_M1 (bramka obliczona ponownie na native48).
   Progi pozostają identyczne. Pozwala to oddzielić cechy i bramkę.
4. Stabilność: status przypisany/odmowa, Jaccard przypisanych, niezgodność
   współprzynależności par, Jaccard krawędzi granicznych na wspólnie
   przypisanych końcach. Puste zbiory → null, nie doskonała stabilność.
   To zgodność konturu grafowego; na centrach nie ma pełnego konturu pikselowego.
5. Te same miary jakości domen i stałe referencyjne mianowniki jak E2.
   Stabilna, błędna segmentacja nie oznacza dobrego detektora. Raportować
   pełne ocenialne dane oraz wsparcie wspólne przy porównaniach relacji.

Podsumowania osobno dla reżimu, samplera, rodzaju syntetyku i ziarna modelu;
mediany/zakresy ziaren oraz rozrzut obrazów opisowe. Nie wybierać najlepszego
ziarna po wyniku. Główny widok: TTMAPP259, centra/transdukcja, rVAE treść
seed20261101, FH/H_M1; możliwość porównania wszystkich warunków i obrazów.
Zapisać predykcje i kalibrację przed otwarciem referencji w tym przebiegu.
Historyczne referencje były już oglądane w E0–E2: brak twierdzenia o ślepym teście.

## Budżet, kontrola i decyzja

Budżet: 60 min CPU, 8 GiB RSS, 8 GiB artefaktów, bez treningu/GPU.
Zachować osobny katalog `.scratch/ml-e3-20261111`, zamrożony protokół,
kod i hashe źródeł/adapterów/cech/predykcji. Nie nadpisywać poprzednich prób.
Sprawdzić transformy, odczyty modelu, metryki niezależne od ID, null przy
brakach, identity replay i aktualizację bramki. Sprawdzić przeglądarkę oraz
obejrzeć zrzuty; odbiór użytkownika osobno. Nowe pliki <1000 linii.

Jeśli ruch cech nie zmienia relacji, nie uznawać fotometrii za główne
wyjaśnienie niepowodzenia. Jeśli psuje relacje/domeny, wskazać konkretną
perturbację i warunki jako motywację jednego przyszłego kontrastu E6.
Bez zmiany planu automatycznie: następne E5; E7 nadal wymaga przejrzanych
relacji i audytu grup. Odrębna normalizacja wycinków nie jest tu wdrażana
ani dopasowywana do testu. Źródłowy obraz i ewentualne skoki wysokości
pozostają dostępne do interpretacji fizycznej.
