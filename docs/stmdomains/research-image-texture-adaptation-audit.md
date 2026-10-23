# Tekstura obrazu: audyt EWT przed próbą issue 17

Data: 2026-10-23. Zakres: źródła pierwotne, API `pyewt 1.0.0` i jawne
różnice między publikacją STM a proponowaną adaptacją. To audyt źródeł,
nie wynik oceny jakości na TTMAPP. Wynik obliczeń i faktyczne ustawienia
należy odczytywać z raportu próby oraz jej manifestów.

Publikacja potwierdza użyteczność kierunkowych cech tekstury w STM, lecz
nie dostarcza gotowego algorytmu spełniającego warunek samodzielnego wyboru
liczby domen. Oficjalny pakiet pozwala wykrywać liczbę pasm widma, co jest
innym zadaniem niż stwierdzenie istnienia i liczby domen.
[Publikacja STM](https://arxiv.org/pdf/1804.08890),
[oficjalna dokumentacja pyewt](https://pyewt.readthedocs.io/en/latest/index.html).

## Co robi publikacja STM

Bui i współautorzy rozdzielają obraz na składnik gładki i teksturę.
Filtr liniowy ma odpowiedź `Lσ(ξ)=1/(1+(2πσ|ξ|)^4)`.
Lokalna redukcja zmienności `λ` steruje wagą
`w=clip((λ−0.25)/0.25, 0, 1)`; tekstura to `v=w*(f−Lσ*f)`.
Eksperymenty używają `σ=3`. Jest to nieliniowe rozdzielenie Buadesa,
nie samo odjęcie rozmycia Gaussa.

Zmodyfikowana transformata curvelet wykrywa kąty, potem skale wewnątrz
sektorów. Autorzy progowali współczynniki pseudopolarnego FFT percentylem
dobieranym do obrazu, a słabe zewnętrzne pasma łączyli według gęstości
energii, z progiem `0.1` największej gęstości.

Cechą jest lokalna norma L2 współczynników podzielona przez liczbę pikseli
okna: `sqrt(sum(|c|²))/|B|`. To nie RMS. Promień wynosi
`ceil(π/ω)`, brzeg dopełnia się symetrycznie. W opisanym równaniu nie ma
normalizacji całego wektora cech do długości jeden.

Końcowe grupowanie używa liczby klas wskazanej przez użytkownika, odległości
cityblock oraz k-means lub multiclass MBO. MBO inicjalizuje się częścią
etykiet k-means. Nie jest to dowód automatycznego odkrywania liczby domen.
[Bui i in., sekcje 2, 4.3–4.4 oraz 5.2](https://arxiv.org/pdf/1804.08890).

## API i wybór niewielkiego wariantu

`pyewt` jest oficjalnym pakietem laboratorium Gillesa. Oferuje trzy warianty
curvelet oraz empiryczne transformaty Voronoi i watershed. Badana dystrybucja
to `1.0.0`, odczytana lokalnie z `/tmp/stmdomains-issue17-deps/pyewt`;
sumy źródeł podano niżej. Linki do `main` służą nawigacji, nie zastępują
identyfikacji badanych plików.
[Repozytorium autorów](https://github.com/jegilles/pyewt).

| Wariant | Interfejs | Istotna własność |
| --- | --- | --- |
| Curvelet | `ewt2d_curvelet(f, params) → ewtc, mfb, Bw, Bt` | Wariant 1 wykrywa skale i kąty niezależnie; 2 najpierw skale; 3 najpierw kąty. |
| Voronoi | `ewt2d_voronoi(f, params) → ewtc, mfb, maxima, partition, plane` | Wykrywa maksima w dwuwymiarowej przestrzeni skal, następnie dzieli widmo według najbliższego maksimum. |
| Watershed | `ewt2d_watershed(f, params) → ewtw, mfb, maxima, partition, plane` | Używa tych samych maksimów jako znaczników watershed na ujemnym module FFT. |

Źródła interfejsów:
[curvelet](https://github.com/jegilles/pyewt/blob/main/src/pyewt/ewt2dcurvelet.py),
[Voronoi](https://github.com/jegilles/pyewt/blob/main/src/pyewt/ewt2dvoronoi.py),
[watershed](https://github.com/jegilles/pyewt/blob/main/src/pyewt/ewt2dwatershed.py).

Minimalny wariant do tej próby to curvelet 1, z `detect='scalespace'`,
`curvmethod='scalespace'`, `typeDetect='otsu'`, `Completion=False`,
`log=False`. W tych gałęziach `N` i `curvN` nie sterują liczbą pasm.
Włączenie `Completion` wymuszałoby dodatkowe granice. Należy sprawdzić
niezależność od nieużywanych wartości `N`/`curvN` w próbie odtwarzania.
[Parametry domyślne](https://github.com/jegilles/pyewt/blob/main/src/pyewt/defaultparams.py),
[rozgałęzienia detektora granic](https://github.com/jegilles/pyewt/blob/main/src/pyewt/boundaries1d.py).

Audyt kodu wskazuje trzy ograniczenia praktyczne curvelet:

- `ewt_angles_detect` przypisuje `params2=params` i nadpisuje ustawienia
  przetwarzania radialnego ustawieniami kątowymi. Każde wywołanie powinno
  dostawać świeżą kopię parametrów.
- W wariancie 3 ostatni zewnętrzny klin trafia do `mfb[t+1]`, zamiast do
  ostatniej listy. Przy jednej granicy kątowej pojawia się także ryzyko
  niezdefiniowanego `t`. Dlatego wariant 1 jest prostszym punktem odniesienia.
- Kod używa `boundaries[0]` i granic końcowych bez pełnej obsługi pustego
  wyniku. Brak pasm lub degeneracja powinny dać jawną odmowę, bez zastępowania
  wyniku ręcznie zadaną liczbą sektorów.

To obserwacje ze źródła zainstalowanego pakietu, nie potwierdzenie wykonania
każdej ścieżki błędu. [Badany moduł curvelet](https://github.com/jegilles/pyewt/blob/main/src/pyewt/ewt2dcurvelet.py).

Voronoi/watershed mają większy koszt pamięci: `ewt2d_gss` tworzy tablicę
float64 `H×W×(niter*ceil(min(H,W)/kn)+1)` oraz tablicę komponentów.
Z samego wzoru wynika około `1.34 GiB` dla `512×512`, `kn=3`, `niter=4`,
jeszcze przed innymi tablicami. Filtry Voronoi mają ponadto pętle po pikselach.
Jest to oszacowanie z kodu, nie zmierzony szczyt RSS. Te warianty nie są
konieczne do pierwszego porównania kierunkowej tekstury.
[Przestrzeń skal 2D](https://github.com/jegilles/pyewt/blob/main/src/pyewt/boundaries2d.py),
[budowa filtrów](https://github.com/jegilles/pyewt/blob/main/src/pyewt/ewt2dvoronoi.py).

## Proponowana adaptacja do wspólnego zakresu klatek

Poniższe decyzje są naszą propozycją eksperymentalną. Nie przypisujemy ich
publikacji ani autorom biblioteki.

Surowych wektorów z osobno wykrytych banków nie należy sklejać między
klatkami: kanał o tym samym indeksie może mieć inne pasmo i kąt. Rozwiązaniem
do sprawdzenia jest jeden bank wyznaczony z całego wybranego zakresu.
Po ujednoliceniu skali przestrzennej oraz rozmiaru `N×N` zbieramy
`P=Σ_s a_s*abs(PPFFT(v_s))`. Wagi powinny zapewnić jawny udział klatek,
zamiast premiować ich jasność. Normalizacja wykorzystuje wyłącznie obraz.

Dla wariantu 1 stosujemy wzory detekcji z pakietu:

1. `r=fftshift(P.sum(axis=1))[:N]`; wykrywamy granice radialne,
   usuwamy zerową granicę początkową i przeliczamy `Bw=bounds*π/N`.
2. `a=P.sum(axis=0)`; wykrywamy granice kątowe i przeliczamy
   `Bt=bounds*π/(2*N)−3π/4`.
3. `ewt2d_curvelet_filterbank(Bw, Bt, N, N, option=1)` buduje wspólny bank.
   Każdą klatkę filtrujemy przez `ifft2(conj(filter)*fft2(v_s))`.
4. Zapisujemy bank, jego zakres wejściowy, wagi i pasma. Wektory energii
   lokalnej mogą używać wspólnej siatki okien oraz normalizacji, ale będzie
   to adaptacja równania cech z publikacji.

Te operacje nie wymagają centrów ani ramek referencyjnych. Wariant przy
centrach może próbkować ten sam bank, zachowując osobną ocenę wpływu miejsc
pomiaru. Nie wolno uzależniać od centrów wyznaczenia banku w wariancie
korzystającym wyłącznie z obrazu.

Istotne ryzyka i sprawdzenia:

- **Dopełnienie i orientacja.** Odbicie obrazu dodaje odbite kierunki sieci.
  Przy dużym dopełnieniu może zmienić wykrywane pasma. Oddzielić rzeczywiste
  pole od dopełnienia i sprawdzić wrażliwość na jego rozmiar. `PPFFT` samo
  dopełnia wejście zerami do parzystego kwadratu; polityka powinna być jawna.
  [Implementacja PPFFT](https://github.com/jegilles/pyewt/blob/main/src/pyewt/pseudopolarfft.py).
- **Szum i pasy.** Otsu rozdzielające trwałość maksimów nie jest testem
  krystalicznego porządku. Jednostkowa długość wektora energii również nie
  potwierdza porządku. Zachować osobną energię i niezależne kryterium odmowy,
  ocenić je na szumie, punktach losowych oraz pasach skanowania.
- **Przesunięcie fazy.** Moduł FFT i uśredniona energia w dużej mierze
  pomijają fazę translacji. Sukces przy orientacji i rozstawie nie dowodzi
  wykrycia granicy dwóch przesuniętych fragmentów tej samej sieci.
- **Rozszerzenie zakresu.** Ponownie wyznaczyć zarówno bank, jak i grupowanie
  dla mniejszego i większego zakresu. Porównać wspólne klatki bez zależności
  od numeracji etykiet. Ponowne użycie zamrożonego banku nie sprawdza tego
  ryzyka adaptacyjnego katalogu.
- **Brak zadanej liczby grup.** Grupowanie musi dopuszczać pojedynczą grupę
  i odrzucenie szumu. Liczba kanałów, klastrów cech i spójnych obszarów
  przestrzennych to trzy różne wielkości. Bez dodatkowej walidacji obszary
  mają status kandydatów tekstury, nie rozpoznanych typów sieci.

## Identyfikacja odczytanych źródeł pakietu

Wersja dystrybucji: `pyewt 1.0.0`. SHA-256 plików odczytanych podczas audytu:

| Plik | SHA-256 |
| --- | --- |
| `ewt2dcurvelet.py` | `c61a56f21c8ee9b8ae6b6216ce4381f76de37837f5df6a6a00fcd7368a23022e` |
| `boundaries1d.py` | `7dc1fc964e4a196713b3c86fe4165ad7b044657e686f1b5b4b5c3fc77db9080a` |
| `boundaries2d.py` | `4650660e53237c113d55d2232325cf6171030f36bbdc29fafe9519d8de722ee8` |
| `defaultparams.py` | `fe6aceef0d73c64c1d7e962acb5d8821e7e3ac9cb92f066135ad33c30e53a541` |
| `ewt2dvoronoi.py` | `4befb5bfb9900540559a288b1e2c7c43e00b307c8bc25846edc92441773826ce` |
| `ewt2dwatershed.py` | `4b424e9d29e27bf0455311c5285e04dceca72f45f6713d44503f8d2c57b02d86` |

Odczytano publikację, oficjalną dokumentację, repozytoria autorów oraz
lokalną dystrybucję pakietu. Nie modyfikowano biblioteki ani środowiska.
Audyt nie obejmuje odtworzenia wyników autorów w MATLAB; źródło referencyjne
tego odtworzenia wskazuje [repozytorium Bui](https://github.com/kbui1993/Microscopy-Codes).
