# E3 — fotometria, relacje i stabilność domen

Wykonanie 11 listopada 2026, `ml_domain`, baza `ed4762b`, środowisko `netcat`.
[Protokół przed próbą](ml-ae-rvae-e3-protocol.md),
[manifest](ml-ae-rvae-e3-manifest.json), [plan](ml-ae-rvae-experiments.md).

## Wynik i dalszy kierunek

**Fotometria silnie zmienia relacje i domeny rVAE. Normalizacja L2 jest
ważnym miejscem nasilenia tej niestabilności.** Nie jest to wyłącznie problem
bramki ani PCA. Zmniejszenie jasności poprawia część miar STM przy rozluźnionej
bramce, ale pogarsza kontrole różnych domen. Nie wybrano poprawki detektora.

Następne w zaakceptowanej kolejności jest **E5: lokalność, skala i centrowanie**.
E3 uzasadnia późniejszy ograniczony kontrast normalizacji w E6. Przed kosztownym
treningiem warto oddzielić wpływ przygotowania obrazu od L2 i kalibracji
odczytu; ewentualna nowa kalibracja musi używać wyłącznie danych treningowych.
Samo odjęcie 0.1 od jasności nie jest rekomendacją do wdrożenia. E7 nadal
wymaga przeglądu etykiet i bezpiecznego podziału grup; nie rozpoczęto E4–E7.

### Gdzie powstaje niestabilność

Dla treści rVAE po dodaniu offsetu +0.1 korelacja rang odległości z bazą
zmienia się następująco. Każda liczba to mediana po klatkach, następnie
mediana trzech ziaren; oceniano wspólnie dostępne krawędzie wszystkich odczytów.
Transfer obejmuje 19 klatek z niepustym wsparciem spośród 24, transdukcja 24/24.

| Reżim i miejsca | Surowa treść enkodera | Po L2 | Po adapterze |
|---|---:|---:|---:|
| Transfer, siatka | 0.916 | 0.395 | 0.393 |
| Transfer, centra | 0.905 | 0.424 | 0.425 |
| Transdukcja, siatka | 0.977 | 0.112 | 0.114 |
| Transdukcja, centra | 0.974 | 0.120 | 0.121 |

Największe pogorszenie następuje przed PCA, przy L2. To wynik zamrożonej
ścieżki odczytu, a nie dowód, że surowa treść już jest dobrym detektorem.
Usunięcie L2 wymagałoby ponownej kalibracji, której E3 nie wykonuje.

W transdukcji na centrach offset +0.1 zmienia **67.67% stanów relacji treści
rVAE** po adapterze, zakres ziaren 65.58–71.25%. To mediana odsetków klatek,
następnie ziaren. Są to przejścia pomiędzy
przyciąganiem, neutralnością i odpychaniem przy stałych progach E2.
Oceniono łącznie 7721 wspólnych krawędzi z 24 klatek; ich suma nie jest
mianownikiem tej mediany ani liczbą niezależnych obrazów.
Dla pełnego rVAE mediana wynosi 44.57%, a dla AE 24.60% mimo korelacji rang
AE 0.997. Zachowanie rankingu nie gwarantuje stałości decyzji progowych.

Szum sigma0.03 ma dużo słabszy efekt: treść rVAE zachowuje korelację 0.999
i zmienia 1.80% relacji. Gradient +x daje odpowiednio 0.953 i 17.92%.
Wrażliwość zależy więc od rodzaju zakłócenia. FFT i geometria zachowują
relacje przy offset/gain, ale ich stabilność nie usuwa wcześniejszych błędów
domenowych.

### Co dzieje się z domenami

Poniżej transdukcja, centra, treść rVAE, FH, bramka H_M1. Każda kolumna
jest medianą trzech ziaren, po zsumowaniu liczników i mianowników 24 klatek.
Pokrycie ma stały mianownik **1354 miejsc znanych wnętrz domen**.
Scalenia dotyczą błędnego połączenia par różnych domen; podziały — rozdzielenia
par tej samej domeny. Ich mianowniki obejmują tylko pary przypisane i zmieniają
się z warunkiem. Nie są to odsetki błędnie zlokalizowanych molekuł.

| Warunek | Pokrycie wnętrz ↑ | Błędne scalenia par ↓ | Błędne podziały par ↓ |
|---|---:|---:|---:|
| Bazowy | 88.63% | 15.98% | 58.80% |
| Offset −0.1 | 93.57% | 13.44% | 14.70% |
| Offset +0.1 | 84.64% | 66.68% | 47.91% |
| Gain 0.9 | 93.35% | 6.10% | 31.09% |
| Gain 1.1 | 82.27% | 41.23% | 62.42% |
| Szum sigma0.03 | 89.07% | 11.11% | 59.61% |

Offset −0.1 i gain 0.9 poprawiają pokrycie oraz podziały w każdym ziarnie.
Nie poprawiają jednak wszystkiego: w ziarnie 20261103 scalenia po offset−
rosną z **5.46% do 19.28%**, a po gain 0.9 do 6.10%.

Ograniczenie jest jeszcze wyraźniejsze na kontrolach syntetycznych:
offset− scala pary różnych orientacji w **100% we wszystkich trzech ziarnach**
FH/H_M1. Dla granicy przesunięcia scalenia rosną z `[0, 0, 0]%` do
`[33.33, 0, 100]%`. Kontrola niezależnych rzędów nadal daje 416/416
fałszywie przypisanych miejsc, czyli 100%, dla identity, offset− i gain 0.9.
To wyniki transdukcji, centrów i treści rVAE, nie uśrednienie wszystkich metod.

Zmiana metody podziału nie rozwiązuje problemu. Dla MWS/H_M1 na rzeczywistych
centrach pokrycie po offset− rośnie z **34.56% do 79.69%**, ale scalenia
z **3.97% do 100%** — ostatni wynik występuje we wszystkich trzech ziarnach.
Wyższe pokrycie samo w sobie nie oznacza lepszych domen.

### Bramka i porównanie ze zmianą struktury

Pełna bramka nadal daje **0% pokrycia znanych wnętrz** w transferze obu
samplerów oraz w transdukcji na centrach — dla bramki zachowanej i przeliczonej.
W transdukcji na siatce maksimum po wszystkich warunkach i ziarnach to
0.51% przy zachowanej bramce i 1.15% po jej aktualizacji. To pokrycie
referencyjnych domen, nie wykrywalność molekuł.

Na rzeczywistych centrach transdukcji przed minimum rozmiaru przechodzi
bazowo 74/4629 wspieranych miejsc. Offset/gain nie zmieniają tej maski.
Szum zmienia 35 miejsc, a gradient +x 91; aktualizacja maski nie odzyskuje
znanych wnętrz. Wpływ offsetu na domeny H_M1 pochodzi z relacji cech,
nie z poluzowania bramki. Prawie pusty wynik pełnej bramki nie dowodzi odporności.

Na osobnych parach syntetycznych ruch treści rVAE po offset− jest
**8.72–22.03 razy większy** niż po zmianie rozstawu 12→16, a pełnego rVAE
8.46–16.69 razy większy. To zakres median dziewięciu par dla trzech ziaren
i dwóch reżimów, na centrach w przestrzeni adapted. AE daje 0.15–1.28.
Dla rVAE także gain 0.9 wywołuje większy ruch niż ta zmiana rozstawu;
szum ma znacznie mniejszy wpływ. Wynik dotyczy zadanych amplitud, bez
fizycznego zrównania dawek. Jednorodny obrót lub przesunięcie mogą celowo
pozostawiać treść niezmienioną; sama niezmienniczość nie jest błędem domenowym.

Zestawienie potwierdza problem fotometrii, ale **nie uzasadnia odrzucenia
rVAE jako całej rodziny ani rozpoczęcia dużego treningu**. Najpierw trzeba
sprawdzić lokalność i rozdzielić wkład wejścia, normalizacji cech oraz reguły
łączenia domen. Wnioski STM pozostają rozwojowe: jedna akwizycja i częściowa
referencja, bez niezależnej walidacji.

## Obrazy do porównania

Lokalna przeglądarka: `.scratch/ml-e3-20261111/index.html`.

```bash
xdg-open .scratch/ml-e3-20261111/index.html
```

Dwa panele pokazują ten sam pełny obraz źródłowy, z bazowymi domenami oraz
wynikiem po perturbacji wejść modelu. Przełącznik warstw pozwala obejrzeć
sam obraz. Pomarańczowe oznaczenia wskazują zmianę przypisania albo zmianę
współprzynależności sąsiednich molekuł, niezależnie od numeracji domen.
Centra są danymi wejściowymi; nie jest to nowa detekcja molekuł.

Zmiany są wykonywane na lokalnych wycinkach, nie na nowym spójnym skanie.
Szum i gradient w nakładających się wycinkach nie reprezentują pojedynczego
pola zakłóceń pełnego obrazu. Kliknięcie punktu pokazuje jego pomiary.
Dla jednego jawnie wskazanego miejsca zapisano parę wycinków 64×64;
przy innym punkcie te podglądy są ukrywane. Obcinanie do [0,1] dotyczy
wyłącznie wyświetlania PNG; inferencja zachowuje wartości poza zakresem.

Domyślnie: TTMAPP259, centra, transdukcja, treść rVAE, ziarno 20261101,
FH, H_M1, offset +0.1. H_M1 jest diagnostyką bez miękkich progów ACF/widma,
nie nowym ustawieniem produkcyjnym. Kolory nie śledzą domen w czasie.

Odbiór ręczny:

1. Porównać offset −0.1/+0.1, gain 0.9/1.1, szum i gradienty na tej samej klatce.
   Wybrać identity: oba panele powinny pokazać ten sam podział i brak halo zmian.
2. Przełączyć treść rVAE / treść+kąt / sam kąt / AE / FFT, zachowując ziarno
   tam, gdzie występuje. Ocenić fragmentację i odmowy, nie sam kolor.
3. Porównać H_M1, pełną bramkę bazową i pełną bramkę przeliczoną.
   Tabela wybranego punktu wskazuje, które pomiary faktycznie użyto w decyzji.
4. Kliknąć miejsce przykładowego wycinka, potem inne centrum: podgląd
   pierwszego miejsca nie powinien udawać podglądu drugiego.
5. Przejść do syntetyków dwóch orientacji, przesunięcia oraz niezależnych
   rzędów. Stałość błędnych przypisań nie oznacza poprawnej domeny.

Odbiór użytkownika pozostaje otwarty; sprawdzenia techniczne poniżej.

## Co porównano

105 obrazów z E2, skala48, dwa samplery i dwa reżimy. Zamrożone 12 enkoderów
AE/rVAE z32 oraz 60 historycznych adapterów. Odczyty: AE, pełne rVAE, treść,
kąt, FFT, fotometria i geometria. Cztery odczyty modeli mają po trzy ziarna;
trzy bazy nie mają sztucznie powielonych ziaren. Bez treningu, refitu adapterów,
nowych etykiet, zmiany grafów, progów lub metody aplikacji.

Dziesięć warunków: identity, offset ±0.1, gain 0.9/1.1, szum sigma0.03,
gradient ±x/±y. Operacje odpowiadają poziomowi wejścia dawnej augmentacji:
po historycznej normalizacji, bez ponownego clippingu. Gradient ustalono
na dawnych oknach fit siatki, bez syntetyków: transfer 96 okien, g=0.087918;
transdukcja 3456, mediana half-range płaszczyzny 0.119730 ograniczona do g=0.1.
Pełny zakres gradientu w wycinku wynosi 2g. To diagnostyka, nie kalibracja
rzeczywistego dryfu aparatury. Centra korzystają z tego samego g.

Osobno: 9 realizacji par strukturalnych o tej samej fotometrii i szumie.
Zmiany: obrót sieci 8°, rozstaw 12→16, faza +(0,4). Porównano je z tymi
samymi perturbacjami fotometrycznymi bazowego wycinka. Jednorodne przesunięcie
fazy nie jest nową granicą domeny. Ruch cech względem zmiany struktury dotyczy
wyłącznie tych amplitud i renderera, nie wszystkich materiałów STM.

## Jak czytać miary

- Ruch native, L2 i adapted ma różne jednostki; porównania między rodzinami
  opierają się na relacjach i podziałach, nie arbitralnej długości wektora.
  Adapted jest skalowane medianą krawędzi treningowych, bez nowej kalibracji.
- Spearman i zmiany stanów relacji obejmują wszystkie wspierane krawędzie.
  q25/q75 stosowane są wyłącznie do adapted. ROC/AP używa tylko końców
  o znanych dodatnich instancjach domen. To różne mianowniki.
- Każdy ROC/AP porównuje się z `paired_identity` tego samego warunku
  i wsparcia, ponieważ dostępność geometrii może się zmienić. Nie dopisano
  odległych par, a nieoznaczone STM nie staje się negatywem.
- Jaccard przypisanych i zmiana statusu dotyczą miejsc z pełnym wsparciem.
  Niezgodność podziału i Jaccard granicznych krawędzi wymagają wspólnego
  przypisania. Pusty zbiór nie daje idealnej stabilności, lecz brak miary.
  To kontur grafowy; na centrach nie wyznaczano pełnej granicy pikselowej.
- Statystyki pikseli w tabelach odnoszą się do wejścia64. FFT/ACF korzystają
  z niezależnie wyciągniętego native48, a pola szumu48/64 są różne. Nie należy
  dzielić ruchu FFT przez RMSE64 ani traktować tego jako czystego porównania
  architektur. Nasycenie bazowe 0/1 nie rekonstruuje utraconych surowych wartości.
- Względne ruchy i główne porównania obejmują dostępne odczyty z poprawnym
  adapterem; utrata dostępności jest jawna. Stabilność nie zastępuje oceny jakości.

Transdukcja nadal opisuje jedną akwizycję wykorzystaną w dopasowaniu.
Transfer ma starą konwencję rozłączności przy niskiej ufności rejestracji.
Rzeczywistych referencyjnych krawędzi różnych domen jest bardzo mało:
przed przecięciem dostępności jedna w transferze, cztery na centrach transdukcji.
Nie wystarcza to do walidacji generalizacji lub lokalizacji rzeczywistych granic.

## Odtworzenie i weryfikacja

```bash
conda activate netcat
python -m stmdomains.experiments.e3_run --out .scratch/ml-e3-nowy-przebieg
python -m stmdomains.experiments.e3_readout .scratch/ml-e3-nowy-przebieg
python -m stmdomains.experiments.e3_check_gallery .scratch/ml-e3-nowy-przebieg/index.html --out .scratch/ml-e3-nowy-przebieg/browser-check
```

Nowy katalog chroni poprzednie próby. Wymagane są lokalne wejścia/cache E1/E2
oraz checkpointy issue21; nie ma pobierania wag z sieci. Źródła pozostają
niezmienione. NPZ zachowuje cechy, normy, odległości, maski i predykcje;
CSV/JSON/gzip mają osobne ziarna, warunki i zakresy. Protokół i predykcje
zostały zamrożone przed oceną referencją w tym przebiegu. Jest to znany
materiał rozwojowy, bez deklaracji ślepego testu.

Przebieg na CPU, jeden wątek, bez dostępnej CUDA w tym środowisku: **1276.21 s
czasu ściennego, 1276.59 s CPU, szczyt RSS 2.20 GiB**. Zamrożone przewidywania
dały 378000 ocen relacji, 378000 ocen domen i po 100800 agregatów. Przeglądarka
ma 105 obrazów, 12600 zestawów wyników oraz 10 warunków. Artefakty po
postprocessingu i audycie zajmują około 6.5 GiB; budżet 8 GiB zachowany.

Wykonane sprawdzenia:

- **20 testów E3 PASS** w `netcat`: transformacje bez reclipu, inferencja,
  miary relacji/stabilności, kontrolowane pary strukturalne. Kompilacja modułów PASS.
- Replay **37800 historycznych podziałów dokładny** dla zapisanych cech E2.
  Świeża inferencja CPU ma maksymalną różnicę cech 8.11×10⁻⁶; zmienia
  4/37800 podziałów, wyłącznie MWS przed pełną bramką. Brak zmian FH.
  E3 porównuje perturbacje ze świeżym identity na tym samym backendzie.
- **186 sprawdzeń finalnej przeglądarki QtWebEngine PASS**, zero błędów JS,
  trzy zrzuty sprawdzone wizualnie. Wcześniej fixture: 80 sprawdzeń PASS.
  To techniczny odbiór galerii, nie ręczny odbiór użytkownika ani test całej aplikacji.
- Niezależny audyt potwierdził niezmienność 247 wejść i zamrożonych predykcji.
  W 100800 agregatach relacji nie ma rozbieżnych mianowników `paired_identity`
  ani liczbowego AUC/AP przy braku klasy; 86400 poprawnie zawiera brak miary.
- Protokół, wagi, adaptery i źródła pozostały niezmienione. Końcowy renderer
  i postprocessing mają osobne snapshoty i hashe; nie nadpisano manifestu
  przebiegu obliczeń po poprawkach samej przeglądarki. Dodatkowy audyt
  zależności potwierdza zgodność siedmiu użytych modułów z bazą `ed4762b`.

Zwięzły manifest wersjonowany zawiera hashe manifestów lokalnych i eksportów.
Szczegóły: `readout-*.csv`, `readout.json`, `independent-audit.json`,
`backend-drift.json`, `gallery-render.json` i `browser-check/` w katalogu próby.
Nie uruchamiano pełnej regresji aplikacji: zmiana dodaje niezależny eksperyment,
bez modyfikacji istniejących modułów aplikacji. Największy nowy plik kodu
ma 300 linii, poniżej celu 1000 i limitu 1500.

Procedury: `experimental-design` i `scientific-critical-thinking`.
Źródło procedur: Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M.
(2026), *Scientific Agent Skills: A Library of Procedural Knowledge for Research
Agents*, [doi:10.48550/arXiv.2609.00065](https://doi.org/10.48550/arXiv.2609.00065).
Metadane zweryfikowano w arXiv podczas E3. Cytowanie opisuje pochodzenie procedur,
nie jest dowodem skuteczności metod STM.
