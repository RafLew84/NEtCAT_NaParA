# Gotowe cechy FCN i DINOv2 — przygotowanie issue 18

Data: 2026-10-26. [Issue 18](issues/18-frozen-feature-preparation.md):
**zakończone przygotowanie techniczne (`resolved`)**. Oba podstawowe ekstraktory
działają z oficjalnymi, niezmienianymi wagami. Gotowe są lokalne cechy,
cache, geometria, kontrola powtarzalności i polecenie odtworzenia.
Nie wykonywano grupowania ani wykrywania domen; ich ocenę przewiduje issue 19.

Kod i testy: commit `e6e7248`, gałąź `domains/frozen-features`, baza `9346d1a`.
Moduły są w `stmdomains/experiments/frozen/`; nie zmieniono uruchamiania aplikacji,
modułów wspólnych ani głównych wymagań. To ponownie używalne przygotowanie
badawcze, nie wdrożenie metody domen do GUI.

Artefakty lokalne:

- `.scratch/frozen-features/index.html` — podgląd **miejsc pobierania cech**;
  krzyżyki siatki, okręgi centrów molekuł i prostokąt analizowanego okna mają
  różne znaczenie. Nie są oznaczeniami znalezionych domen.
- `.scratch/frozen-features/` — cechy, manifesty, wejście pilotażu, niezależne
  powtórzenie oraz przykładowe natywne mapy modeli.
- `.scratch/frozen-feature-assets/` — oficjalne wagi i przypięty kod DINOv2.

Wszystkie powyższe ścieżki odnoszą się do
`/home/rlew/projekty/NEtCAT-domains`. Duże pliki pozostają poza Git.
[Wersjonowany manifest](frozen-feature-preparation-manifest.json) zawiera
identyfikację wejść, modeli, źródeł oraz zmierzone koszty.
[Audyt źródeł](research-frozen-feature-extraction-audit.md) wyjaśnia wybór warstw.

## Modele i pobierane cechy

| Ekstraktor | Wagi i wyjście | Wektor jednego okna |
| --- | --- | --- |
| FCN–ResNet101 | `COCO_WITH_VOC_LABELS_V1`; `backbone.layer1` (256) i `backbone.layer2` (512) | Średnia przestrzenna każdej mapy, konkatenacja: 768 cech |
| DINOv2 ViT-S/14 | LVD-142M, bez rejestrów; `x_norm_patchtokens` po ostatnim bloku i LayerNorm | Średnia tokenów patch, bez CLS: 384 cechy |

Wagi FCN: `fcn_resnet101_coco-7ecb50ca.pth`, SHA-256:
`7ecb50ca17844860a70d5ed0c748d997cf8adb62932abaa0233430c68594d749`.
Wagi DINO: `dinov2_vits14_pretrain.pth`, SHA-256:
`b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9`.
Kod DINO przypięto do `7764ea0f912e53c92e82eb78a2a1631e92725fc8`.
Pobieranie w `assets.py` sprawdza pełne hashe wag i archiwum kodu;
rozpakowanie używa filtra danych. Ekstrakcja czyta pliki lokalne, nie pobiera
niczego z sieci. Dane pomiarowe nie są wysyłane.
[Oficjalne wagi FCN](https://download.pytorch.org/models/fcn_resnet101_coco-7ecb50ca.pth),
[oficjalny konstruktor DINOv2](https://github.com/facebookresearch/dinov2/blob/7764ea0f912e53c92e82eb78a2a1631e92725fc8/dinov2/hub/backbones.py).

Wybór dwóch warstw FCN odpowiada kodowi autorów modułu STM. **Uśrednianie
lokalnych map oraz preprocessing są naszą adaptacją**. Publikacja interpoluje
mapy do wspólnej siatki i grupuje je z zadanym K; my nie przenosimy ani tego
wyboru liczby grup, ani dalszego treningu. Model FCN ma wagi po segmentacji
COCO/VOC, nie wyłącznie klasyfikacyjny backbone ImageNet.
[Notebook autorów](https://github.com/nickkolev97/FSL_STM/blob/b36c51582bbbc87752b6e0c859c75b8affd89c11/unsupervised_segmentation.ipynb).

Pole lokalnych wektorów pokrywa cały obraz na siatce; dodatkowy wariant
obejmuje wszystkie poprawne centra z wejścia. To nie pojedynczy opis całej
klatki. API `FrozenExtractor.maps()` udostępnia także mapy przed uśrednieniem;
`witness-maps/` zawiera je dla pięciu okien brzegowych/wewnętrznych TTMAPP 250,
obu modeli i obu rozdzielczości. Nie zapisujemy wszystkich dużych map pośrednich.

DINOv3 jest opcjonalny; nie pobierano go w tym zadaniu. Dwa wymagane modele
są dostępne, nie zastosowano zamienników.

## Wejście, skale i normalizacja

Pilotaż obejmuje **12 pełnych obrazów** ze wspólnego wejścia issue 17:

- TTMAPP: klatki **1, 50, 250, 255, 268**;
- ziarno kontrolne 2701: szum (`control-0070`), jedna sieć (`0072`),
  dwie orientacje (`0073`), różny rozstaw (`0074`), brak 30% oznaczeń (`0081`),
  prostokątny wycinek (`0086`) i techniczne powiększenie ×2 (`0087`).

Zestaw ma **2608 centrów**. Nie dobierano okien ani klatek według ramek domen.
Odtworzone dane MPP pochodzą z audytowanego `input/analysis`, bez gamma podglądu,
masek SAM, klas MolTrack czy referencji. Zapisane identyfikatory i SHA-256
prowadzą do wspólnego wejścia. To próba przygotowania, bez oceniania
jakiegokolwiek wyniku względem znanych domen.

16 konfiguracji: 2 modele × 2 skale okna × 2 rozdzielczości wejścia ×
2 normalizacje. Każda działa na siatce i przy centrach:

| Parametr | Wartości / znaczenie |
| --- | --- |
| Siatka | Co 12 pikseli odniesienia; pierwsza pozycja (6,6) |
| Promień okna | 24 albo 36 pikseli odniesienia, czyli szerokość **48/72** |
| Wejście modelu | 112×112 albo 224×224; wielokrotności 14 |
| Normalizacja 1 | Percentyle 2–98 całego zmierzonego pola → [0,1] |
| Normalizacja 2 | Minimum–maksimum całego zmierzonego pola → [0,1] |
| Kanały | Kopia szarości do RGB, mean (0.485,0.456,0.406), std (0.229,0.224,0.225) |
| Arytmetyka | float32, bez autocast i TF32; deterministyczne operacje |

Normalizacja nie korzysta z centrów i nie jest dopasowywana osobno do
rozstawu molekuł. Statystyki liczone są na zmierzonych pikselach całej klatki.
Stały obraz ma jawny znacznik `flat`; braki pomiaru uzupełniamy medianą
znormalizowanego obrazu i zachowujemy ich maskę. W notebooku STM autorzy
używali z-score otoczeń i innej rozdzielczości. Tu porównano dwie własne,
jawne normalizacje i rozmiary; nie jest to pełna reprodukcja publikacji.
Nie stosowano automatycznego cropu klasyfikatora usuwającego brzeg obrazu.

Rozmiary 48/72 wynikają z ciągłych współrzędnych krawędzi pikseli. Próba 17
używała okien 49/73; ta różnica jest jawna i powinna pozostać uwzględniona
przy zestawianiu ekstraktorów. `pixel_spacing_xy` opisuje wyłącznie techniczne
przeskalowanie kontrolnego obrazu; nie deklarujemy wiarygodnej kalibracji nm.

## Współrzędne i wsparcie pomiaru

Każdy wektor zachowuje ID próbki/molekuły, pozycję w oryginalnym polu,
żądane okno i jego przecięcie z polem, maskę źródłowego pomiaru oraz udział
rzeczywistych pikseli. Kolejność centrów jest ustalana przez ID.
Próbkowanie bilinear używa współrzędnych krawędzi pikseli i
`align_corners=False`. Prostokątne obrazy są obsługiwane bez ukrytego cropu.

Odbicie poza polem wypełnia wejście sieci, ale **maska poza polem pozostaje
zerowa**. `measured_support_fraction` mierzy średni udział zmierzonych pikseli
w interpolacji, a `inside_field_fraction` — geometryczne przecięcie okna z polem.
Te wielkości mogą się nieznacznie różnić przy brzegu/interpolacji. Nie
ukrywamy cech z małym podparciem; ich przyjęcie/odmowę będzie oceniał krok 19.

W FCN natywne mapy mają krok 4/8 pikseli wejścia sieci i maksymalne pola
splotów 35/91. Uśredniony deskryptor korzysta z całego okna; wewnętrzne
paddingi splotów są zapisane jako sztuczny kontekst. DINO nie wymaga
przestrzennego dopełnienia, bo oba rozmiary są podzielne przez 14.
Jego tokeny mają zakotwiczenie 14×14, ale attention może łączyć całe okno.
Dodatkowo oba ekstraktory zależą od klatki przez statystyki normalizacji.
Nie opisujemy więc zakresu zależności wektora wyłącznie rozmiarem tokena.
[Audyt geometrii modeli](research-frozen-feature-extraction-audit.md).

## Cache i gotowy zapis

Zapisano **384 wpisy** klatka/konfiguracja/sposób próbkowania, łącznie
104288 wektorów licząc wszystkie wpisy. Są **368 unikalne zestawy cache**:
kontrola jednej sieci i braków 30% ma identyczny obraz, więc 16 wpisów siatki
korzysta z tych samych cech. To poprawna niezależność od centrów.

Klucz obejmuje obraz, maskę pomiaru, techniczną skalę, model, wagi i kod,
wersje wykonawcze/urządzenie, warstwy, preprocessing oraz skalę okna/wejścia.
Dla centrów uwzględnia posortowane ID i pozycje; dla siatki nie zawiera
anotacji. Nie zawiera referencji. Zmiana modelu, obrazu lub preprocessing
unieważnia zgodność klucza. Ponowny odczyt sprawdza hash pliku i tożsamość
konfiguracji, a uszkodzenie jest błędem, nie cichym użyciem starego wyniku.

`cache/*.npz` zawiera tablice; odpowiadający JSON — metadane, hashe i koszty.
`manifest.json` wiąże je z klatkami i zawiera dowody niezmienności modeli.
Ścieżki wyników są względne, więc lokalny artefakt można przenieść.
`audit-manifest.json` i jego wersjonowana kopia opisują przebieg.

## Wykonane sprawdzenia

- **41 testów pytest** w `tests/stmdomains`, w tym 6 nowych dotyczących
  współrzędnych, brzegów, braków pomiaru, skali, cache i obrazu stałego.
  Test rampy sprawdza pobranie rzeczywistych wartości w znanych pozycjach;
  przypadek narożnika potwierdza 25% podparcia zamiast zaliczenia odbicia.
- **192/192 zestawy cech siatki bitowo identyczne** po usunięciu wszystkich
  centrów/bboxów/ID i wprowadzeniu zmienionych, celowo niepoprawnych danych
  referencji obok wejścia. Ponownie obliczono 176 unikalnych kombinacji;
  16 duplikatów obrazu korzysta z wyniku powstałego w tym samym świeżym
  powtórzeniu. Główne wejście nie miało drzewa referencji.
- Kontrola 384 zestawów: zgodność współrzędnych centrów, liczności,
  skończoności cech, zakresu podparcia i hashy cache. Cztery dodatkowe
  odczyty istniejącego cache trafiły w zapisany wynik.
- Przed i po głównej ekstrakcji oraz powtórzeniu hashe parametrów i buforów
  obu ekstraktorów są identyczne. Zero modułów w trybie treningu, zero
  parametrów z włączonym gradientem i zero gradientów. Brak optymalizatora.
- Osiem sprawdzeń wielkości/kolejności partii na pięciu oknach TTMAPP 250.
  FCN oraz odwrócenie kolejności dają zgodność bitową. DINO przy zmianie
  partii z 5 do 1 ma maksymalną różnicę **4.20e-5** (112) i **1.13e-5** (224).
  Wariant 112 nie przeszedł pierwotnej tolerancji `atol=1e-5, rtol=1e-4`.
  Zapisano ten fakt; dla zmiany wielkości partii przyjęto osobną tolerancję
  `atol=1e-4, rtol=1e-4`, spełnioną w 8/8 sprawdzeniach. Zwykłe powtórzenie
  przy tej samej partii zachowuje pierwotną tolerancję i jest tu dokładne.
- **19 kontroli lokalnego HTML** w QtWebEngine: modele, siatka/centra,
  brak centrów, prostokątny obraz, techniczne powiększenie, skala,
  normalizacja i wybór brzegu/wnętrza. Bez błędów JS; obejrzano zrzut.
- Sprawdzono składnię Python/Bash, zgodność źródeł z kluczami obliczonych
  cech i `git diff --check`. Nie wykonywano testów natywnego GUI aplikacji,
  oceny domen ani pełnej ekstrakcji 268 klatek.

W trakcie kontroli poprawiono sprawdzanie duplikatów obrazu w świeżym cache
oraz zapis nowych linii w HTML. Nie zmieniło to cech. Kontrolę numeryczną
partii dokończono na zapisanym świeżym powtórzeniu; główna ekstrakcja nie
została dostrojona do referencji ani do wyników domen.

## Koszt na lokalnym sprzęcie

`netcat`: Python 3.12.12, PyTorch 2.9.1+cu128, torchvision 0.24.1+cu128,
CUDA 12.8; dokładna wersja cuDNN w manifeście. RTX 5090, 32607 MiB VRAM,
sterownik 595.91.07, około 128 GB RAM. GPU jest dostępne poza sandboxem.
Nie instalowano nowych pakietów i nie zmieniano środowiska netcat.
Użyto czterech wątków CPU i partii po 32 okna. DINO pracuje bez xFormers;
komunikaty o tej opcjonalnej bibliotece nie oznaczają niepowodzenia.

| Pomiar | FCN | DINOv2 |
| --- | ---: | ---: |
| Suma czasów świeżej ekstrakcji i zapisu wpisów | 15.60 s | 20.10 s |
| Maksimum pamięci tensorów CUDA | 339811328 B, ok. 324 MiB | 281049600 B, ok. 268 MiB |
| Maksimum rezerwy alokatora CUDA | 455081984 B, 434 MiB | 364904448 B, 348 MiB |
| Szczyt RSS procesu do tego etapu | 1321676 KiB | 1408788 KiB |
| Unikalne skompresowane tablice cech | 140237018 B | 73187733 B |

Cały główny przebieg: **37.01 s**, wraz z ładowaniem i odczytem duplikatów.
Świeże powtórzenie siatkowe: **22.87 s**. RSS jest rosnącym maksimum procesu,
a nie niezależnym pomiarem pamięci każdego modelu. CUDA podaje pamięć
alokatora PyTorch, bez całego kontekstu/sterownika. Nie utożsamiamy tych
wyników z kosztem całej serii, przyszłego grupowania ani większych wejść.

Kopia wyników: 1126 plików / 394049728 B; kopia modeli i źródeł:
222 pliki / 312982757 B. Każdy skopiowany plik zweryfikowano SHA-256.

## Odtworzenie i przekazanie do 19

Z katalogu głównego checkoutu z commitem `e6e7248`:

```bash
bash stmdomains/experiments/frozen/run_preparation.sh \
  /home/rlew/projekty/NEtCAT-domains/.scratch/image-texture-domains/input/analysis \
  /home/rlew/projekty/NEtCAT-domains/.scratch/frozen-feature-assets \
  /tmp/frozen-feature-reproduction
```

Katalog wynikowy musi być nowy. Etapy polecenia wykonano i sprawdzono
osobno; nie powtarzano całej próby wyłącznie dla sprawdzenia wrappera.
[Instrukcja kodu](../../stmdomains/experiments/frozen/README.md) podaje także
polecenia poszczególnych etapów, CPU, własnego zakresu i sprawdzeń.

Issue 18 ma komplet wymaganych wyników technicznych i nie wymaga decyzji
HITL. **Issue 19 jest gotowe do podjęcia**, lecz nie zostało uruchomione.
Powinno porównać cechy na wspólnym zakresie z 15–17, jawnie uwzględnić
pooling i rozmiar okien oraz oddzielić jakość cech od bramki porządku,
która w 17 odrzucała większość TTMAPP. Wykorzystanie zamrożonych modeli
nie gwarantuje rozdzielenia orientacji, rozstawów ani granic fazowych.
Nienadzorowane grupowanie pozostaje osobnym zadaniem; referencje domen
nie będą wejściem ekstraktora ani wymaganiem działania metody.
