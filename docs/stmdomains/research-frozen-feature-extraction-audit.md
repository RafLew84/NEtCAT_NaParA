# Zamrożone cechy FCN i DINOv2 — audyt źródeł do issue 18

Data: 2026-10-26. Zakres: identyfikacja ekstraktorów, ich geometrii i warunków
odtworzenia. To audyt kodu i publikacji; nie jest oceną wykrywania domen STM.
Wyniki uruchomień, SHA-256 pobranych wag oraz wybrane warianty przygotowania
wejścia należą do manifestu i raportu wykonania issue 18.

## FCN–ResNet101: które warstwy i które wagi

Publikacja Koleva i współautorów pobiera wczesne cechy, skaluje mapy do wspólnej
rozdzielczości i grupuje je metodą k-means. Liczba grup jest wybierana przez
człowieka; artykuł nie wykazuje automatycznego ustalania liczby domen. Jego dalsze
etapy obejmują uczenie U-Net i klasyfikację few-shot. Issue 18 wykorzystuje tylko
zamrożony ekstraktor. [Artykuł, sekcje 3.2 i 11.2.2](https://arxiv.org/html/2506.01678v2)

Oficjalny notebook rozstrzyga niejednoznaczne określenie „pierwsza i druga
warstwa”: są to **`backbone.layer1` i `backbone.layer2`**, a nie `conv1` i `bn1`.
Autor tworzy `fcn_resnet101(weights=FCN_ResNet101_Weights.DEFAULT)`, włącza `eval()`
i wyłącza gradienty. Obie mapy są powiększane i łączone po kanałach. Pin źródła:
`b36c51582bbbc87752b6e0c859c75b8affd89c11`.
[Notebook, komórki kodu 22–26](https://github.com/nickkolev97/FSL_STM/blob/b36c51582bbbc87752b6e0c859c75b8affd89c11/unsupervised_segmentation.ipynb)

`DEFAULT` oznacza **`COCO_WITH_VOC_LABELS_V1`**, czyli wagi całego FCN po uczeniu
segmentacji na części COCO obejmującej klasy VOC. Nie należy opisywać ich jako
niezmienionych wag klasyfikatora ImageNet, mimo skrótu użytego w artykule.
Oficjalny plik to
[fcn_resnet101_coco-7ecb50ca.pth](https://download.pytorch.org/models/fcn_resnet101_coco-7ecb50ca.pth).
Jego pełny SHA-256 trzeba wyliczyć po pobraniu; sufiks nazwy nie zastępuje sumy.
[Definicja wag w torchvision 0.24.1](https://github.com/pytorch/vision/blob/v0.24.1/torchvision/models/segmentation/fcn.py)

Poniższa geometria wynika z analizy implementacji ResNet v1.5: splot 7/2,
max-pool 3/2, następnie trzy i cztery bloki Bottleneck. Wartości pola dotyczą
samej sieci w trybie ewaluacji, przed interpolacją i statystykami preprocessing.
[Kod ResNet 0.24.1](https://github.com/pytorch/vision/blob/v0.24.1/torchvision/models/resnet.py)

| Wyjście | Kanały | Krok względem wejścia sieci | Maksymalne pole splotów |
| --- | ---: | ---: | ---: |
| `backbone.layer1` | 256 | 4 px | 35 × 35 px |
| `backbone.layer2` | 512 | 8 px | 91 × 91 px |
| konkatenacja po interpolacji | 768 | zależny od siatki zapisu | suma wsparć pobranych komórek |

Powielenie mapy do pełnej rozdzielczości nie tworzy nowych niezależnych pomiarów.
Interpolacja wektora między komórkami może poszerzyć jego wsparcie; nie wolno
utożsamiać go z jednym pikselem wyświetlania. To wniosek z powyższej geometrii.

## Normalizacja FCN: dwie różne konwencje

Notebook stosuje kolejno min–max i z-score, a następnie kopiuje szary obraz do
trzech kanałów. W wariancie szczegółowym normalizuje osobne otoczenia 64 × 64
i powiększa je do 520 × 520; wariant zgrubny składa wcześniej znormalizowane
otoczenia z oknem sinusoidalnym. Funkcje autora zakładają kwadratowe obrazy
i nie zabezpieczają dzielenia przez zero dla stałego obrazu.
[Funkcje `norm`, `norm2`, `make_stitched`, `extract_features`, `extract_patches_features`](https://github.com/nickkolev97/FSL_STM/blob/b36c51582bbbc87752b6e0c859c75b8affd89c11/unsupervised_segmentation.ipynb)

Standardowy `weights.transforms()` FCN działa inaczej: skaluje krótszy bok do
520, używa interpolacji bilinear, wartości 0–1 oraz RGB mean
`(0.485, 0.456, 0.406)` i std `(0.229, 0.224, 0.225)`.
[Oficjalny opis presetu FCN](https://docs.pytorch.org/vision/0.24/models/generated/torchvision.models.segmentation.fcn_resnet101.html)

**Wniosek dla próby:** oba sposoby mogą być jawnymi wariantami, ale nie należy
nazywać ich równoważnymi ani pełną replikacją publikacji. Rozmiar otoczenia
w oryginalnych współrzędnych i techniczny rozmiar wejścia sieci trzeba zapisywać
osobno. Normalizacja z całego otoczenia wprowadza zależność każdego wektora od
całego obszaru użytego do wyliczenia statystyk, także gdy same sploty są lokalne.

## DINOv2 ViT-S/14 bez rejestrów

Przypięty kod: **`7764ea0f912e53c92e82eb78a2a1631e92725fc8`**. Funkcja
`dinov2_vits14` tworzy `vit_small`, patch 14, bez dodatkowych tokenów rejestrów,
z wagami LVD-142M. Oficjalny plik:
[dinov2_vits14_pretrain.pth](https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth).
Domyślna siatka pozycyjna pochodzi z obrazu 518 × 518; nie oznacza to obowiązku
skalowania każdego obrazu do 518. [Konstruktor i adres wag](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/hub/backbones.py)

ViT-S daje 384 cechy na token, ma 12 bloków i 6 głów attention.
`forward_features(x)['x_norm_patchtokens']` zwraca tokeny po ostatnim bloku
i LayerNorm, bez CLS. `get_intermediate_layers(x, n=1)` wybiera ostatni blok,
natomiast lista `n=[0,1]` wskazuje konkretne bloki numerowane od zera.
`norm=True` oznacza LayerNorm modelu, nie normalizację L2 wektora.
`reshape=True` daje mapę `[B,384,H/14,W/14]`; zwykłe `model(x)` zwraca CLS,
więc nie jest właściwą ścieżką dla lokalnej mapy. Kod interpoluje pozycje
bicubic, dla tego wariantu z `interpolate_offset=0.1` i bez antialiasingu.
[Semantyka API i interpolacji](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/models/vision_transformer.py)

Rozmiary wejścia muszą być podzielne przez 14: aktualny `PatchEmbed.forward`
sprawdza to asercjami. Starszy opis w model card mówi o przycinaniu do mniejszej
wielokrotności; implementacja tego nie robi. Trzeba jawnie dopełnić lub
przeskalować obraz i zachować transformację współrzędnych oraz maskę pomiaru.
[Kod PatchEmbed](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/layers/patch_embed.py),
[model card](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/MODEL_CARD.md)

**Token ma pozycję lokalną, lecz jego kontekst nie kończy się na 14 × 14 px.**
Attention bez maski łączy wszystkie tokeny podanego obrazu. Dla ekstrakcji z całej
klatki wsparciem kontekstowym jest klatka, dla otoczenia molekuły — całe
otoczenie. Pole zakotwiczenia tokena, kontekst i udział rzeczywistego pomiaru
powinny mieć osobne metadane. To wniosek z kodu attention, a nie obietnica
lokalności reprezentacji. [Implementacja attention](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/layers/attention.py)

Oficjalne transformacje używają tych samych mean/std RGB co powyżej. Preset
klasyfikacji dodaje resize 256 i centralny crop 224; bezrefleksyjne zastosowanie
go do mapy STM usunęłoby brzeg. Można zachować normalizację i zdefiniować osobne,
jawne skalowanie dla mapy. Powielenie szarości do RGB jest adaptacją do STM.
[Transformacje DINOv2](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/data/transforms.py)

## Zależności, licencje i zakres użycia

- Lokalny `netcat` w audycie importował `torch 2.9.1+cu128` i
  `torchvision 0.24.1+cu128`. To zgodna para rodzin 2.9/0.24 według
  [tabeli torchvision](https://github.com/pytorch/vision/blob/v0.24.1/README.md).
  Zależności pakietu obejmują też NumPy i Pillow.
  [Deklaracja zależności](https://github.com/pytorch/vision/blob/v0.24.1/setup.py)
- Dla pojedynczych tensorów ekstraktor DINO używa PyTorch i NumPy; xFormers jest
  opcjonalny, a ścieżka bez niego używa PyTorch SDPA. Nie potrzeba pełnego
  środowiska treningu ani cuML. Wejścia typu lista/nested tensor mają inne
  ograniczenia. [Importy modelu](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/models/vision_transformer.py),
  [fallback attention](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/layers/attention.py)
- Kod torchvision: BSD-3-Clause. Dokumentacja oddziela licencję biblioteki od
  możliwych warunków dotyczących gotowych wag; nie przypisujemy automatycznie
  tej samej licencji wszystkim plikom modelu.
  [Licencja](https://github.com/pytorch/vision/blob/v0.24.1/LICENSE),
  [informacja o gotowych modelach](https://github.com/pytorch/vision/blob/v0.24.1/README.md#pre-trained-model-license)
- Standardowe DINOv2 i jego wagi: Apache-2.0. Dodatkowe modele Cell-DINO i
  XRay-DINO w tym repozytorium mają osobne warunki i nie należą do tej próby.
  [Licencje według README](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/README.md#license)
- W drzewie wskazanego commitu FSL_STM nie znaleziono pliku LICENSE/COPYING.
  Notebook służy tu do identyfikacji metody; nie kopiujemy jego implementacji
  do aplikacji. [Drzewo źródłowe](https://github.com/nickkolev97/FSL_STM/tree/b36c51582bbbc87752b6e0c859c75b8affd89c11)

## Konsekwencje dla zakończenia issue 18

Zapis musi obejmować pin kodu, pełny hash wag, warstwy, preprocessing,
transformacje współrzędnych, kontekst oraz maskę rzeczywistego pomiaru.
Ekstrakcja wymaga `eval()`, wyłączonych gradientów i sprawdzenia niezmienności
parametrów oraz buforów, w tym statystyk BatchNorm. Sam brak optymalizatora
nie wyklucza zmiany buforów w trybie treningowym.
[Zachowanie trybów modeli torchvision](https://docs.pytorch.org/vision/0.24/models.html#using-the-pre-trained-models)

Przygotowanie takich wektorów nie dostarcza jeszcze domen, ich liczby ani
klasyfikacji molekuł. Nie używa ramek referencyjnych do pobierania cech;
ocenę przydatności i grupowanie przewiduje osobno issue 19.
