# E2 — protokół odczytu cech i relacji

2026-11-10, baza `6742e13`, `ml_domain`, środowisko `netcat`. Zapis przed
nowym dopasowaniem adapterów i oceną E2. Dane są znanym materiałem rozwojowym,
nie nowym ślepym testem. Audyt zakresu potwierdził bardzo mało rzeczywistych
krawędzi między referencyjnymi wnętrzami; nie rozszerzamy grafu, aby ukryć brak.

## Pytanie, zakres i stałe

Czy odczyt treści rVAE bez kąta poprawia relacje sąsiedztwa? Czy błąd powstaje
już w odległościach cech, czy przy ich przekształceniu przez adapter/graf?
Porównanie jest opisowe i sparowane na tych samych obrazach. Klatki i krawędzie
jednej akwizycji nie są niezależnymi replikacjami. Kontrole syntetyczne mają
trzy ziarna na przypadek; raportować je osobno i zakresy, bez testów istotności
udających tysiące niezależnych doświadczeń.

Jak E1: wszystkie 24 obrazy STM i 81 syntetyków, skala48, siatka i własny graf
centrów, transfer i transdukcja, FH(k=4) i MWS. Wagi/cechy encoderów zamrożone.
Bez inferencji modeli, treningu, etykietowania i wyboru nowego checkpointu.
Próg ACF, dodatkowe widmo i minimum4/8 zachowane. Transfer STM używa dokładnie
zapisanych grafów heldout, a nie filtrowanego pełnego grafu.

## Odczyty ustalone przed próbą

15 odczytów w każdym reżimie; trzy ziarna20261101–20261103 tylko tam,
gdzie istnieją trzy modele. Baz bezmodelowych nie powielamy jako ziaren.

| Odczyt | Definicja |
| --- | --- |
| AE ×3 | Zapisany kod32D. |
| rVAE treść+kąt ×3 | Historyczne `[content/norm,cosθ,sinθ]/sqrt(2)`,34D. |
| rVAE treść ×3 | Zapisany kod32D bez kąta. |
| rVAE kąt ×3 | `[cosθ,sinθ]`, zwykła pełna kołowość2π; brak utożsamienia z osią sieci. |
| FFT | Historyczny opis216D. |
| Fotometria | `[1,mean,std]` z identycznych wejść64×64 po historycznej normalizacji/clippingu; stała1 zachowuje informację o poziomie po L2. |
| Geometria ACF | Średnie cos2φ/sin2φ oraz cos4φ/sin4φ obu osi, dwie posortowane długości/48, wynik ACF i stosunek widma. |

Geometryczne φ dotyczą dwóch kandydatów translacji ACF, nie zwalidowanego
kąta fizycznej sieci. Symetria znaku i zamiany kolejności wynika z symetrii
ACF, nie z założenia o kącie rVAE. Brak wektorów pozostaje NaN; nie tworzymy
z niego niejawnej pewnej etykiety ani nie wycinamy go z mianowników domen.
Fotometria nie mierzy surowej wysokości STM; korzysta z wejścia modeli.

## Adapter i odległości

Historyczne AE/rVAE treść+kąt/FFT używają dokładnie starych adapterów.
Nowe odczyty dopasowują ten sam L2→PCA≤24→medianę dodatnich odległości→q25/q75
**wyłącznie na starych `fit_window_ids`**, bez referencji ani syntetyków:
transfer96/113 okien siatki/centrów; transdukcja3456/4629.
Transdukcja od początku dopasowywała się do wszystkich dostępnych miejsc
tej akwizycji; jej enkoder nie miał odłożonej walidacji. Nie nazywamy tego
niezależnym transferem. Nie stosujemy bramki ACF/S do wyboru okien adaptera.

Oceniać osobno trzy dystanse euklidesowe: **native** zapisanych cech,
**L2** po jednostkowej normalizacji przed PCA oraz **adapted** po PCA
i podzieleniu przez medianę treningową. Sama mediana nie zmienia rankingu
ROC/AP. Dla kąta dystans jest kołowym dystansem cięciwy, nie różnicą surowych
kątów przez szew ±π. Skale native różnych opisów nie są wspólnym progiem.

Wszystkie wyniki bazowe muszą odtworzyć E1/stary podział. Nowe adaptery,
predykcje i dystanse zamrażamy przed nową oceną etykietami.

## Kontrola tasowania i wspólna dostępność

Pięć ustalonych ziaren tasowania:20261110–20261114. Tasować całe wektory
w obrębie tego samego obrazu × samplera × reżimu × wzorca dostępności cech.
Wspólna permutacja dla odczytów; treść i kąt podróżują razem. Wzorzec
dostępności zapobiega przenoszeniu NaN i zmienianiu masek; nie używa prawdy.
Poza zakresem/historycznym testem i bez pełnego wsparcia nie tasować.
Nie tasować etykiet, grafu, masek ani zbioru dopasowania.
W transdukcji tasujemy ewaluacyjną kopię tych samych miejsc, nigdy cache
treningowy ani adapter. Zapisać liczbę przemieszczonych miejsc i rozmiary grup.
To kontrola utraty lokalnej zgodności, nie formalny test niezależności;
zachowuje korelację braków z położeniem i niszczy część autokorelacji obrazu.

Metryki dystansów: własna dostępność odczytu oraz wspólna część wszystkich15
odczytów. Zapisać utratę krawędzi na wspólnej części. Predykcje domen na całym
własnym ocenialnym zbiorze, ze stałym mianownikiem jak E1.
Wspólnej dostępności relacji nie ograniczać bramką H/ACF/S; decyzje te
należą do kolejnych etapów odmów domen. Zapisać także rzeczywiste liczby
ważnych okien/krawędzi dopasowania geometrii, obok nominalnych fit ID.

## Ocena i wyjścia

Klasa dodatnia ROC/PR: **różne prawdziwe domeny**; większy dystans wskazuje
granicę. Wyłącznie niezmienione krawędzie z dwoma dodatnimi, ocenialnymi
końcami. Nieoznaczone STM, tło syntetyczne i pas niepewności nie są negatywami
tej klasyfikacji relacji. Referencja domen nadal ocenia tło syntetyczne
osobno. Brak którejkolwiek klasy par daje null, nie pozornie dobrą krzywą.
Podać liczebności, częstość granic jako bazę AP, rozkłady/kwantyle, ROC-AUC,
AP, krzywe ROC i precision–recall, osobno dla rodzaju kontroli i reżimu.
Nie dobierać progu według oceny. Zagregowane relacje łączyć tylko w obrębie
tego samego przypadku/reżimu/odczytu/samplera; zapisać też wyniki każdego obrazu.

Krzywe można narysować na maksymalnie512 rzeczywistych punktach progowych;
AUC/AP zawsze obliczyć z wszystkich progów. Pełne dystanse zapisać do NPZ.
Nie dodajemy odległych „sąsiadów” przez ręczne wnętrza w celu zwiększenia n.
Audyt E1: transfer ma tylko jedną znaną krawędź różnych domen na sampler;
realne ROC/AP pozostaną opisowe i nie walidują lokalizacji prawdziwej granicy.

Podział grafu: dla rzeczywistych cech i **pierwszego ustalonego tasowania**
użyć tego samego adaptera i solvera. Pozostałe cztery tasowania służą
odczytowi dystansów. Pokazać przed odmowami, po H bez minimum, po H z minimum
oraz pełną bramkę przed/po minimum. Nie wybierać najlepszej permutacji.
Miary domen i negatywów takie jak E1; F1 konturu tylko diagnostyka siatki.

Przeglądarka molekuł/domen według E1, zmieniany odczyt i kontrola tasowania;
obok wyniki relacji, osobne krzywe i rozkłady. Raport oraz manifest w Git,
duże dane lokalnie. Limit:60min CPU,8GiB RSS,8GiB nowych artefaktów.
Przekroczenie zatrzymuje przebieg i wymaga jawnej korekty wykonawczej,
nie wyboru podzbioru według wyglądu wyników.

## Reguła wniosku

Przewaga treści bez kąta musi być widoczna względem pełnego odczytu i kontroli
tasowania, z pokryciem i błędami domen, nie samym AUC. Wynik geometryczny
ma własne ograniczenia dostępności; fotometria może ujawnić wyjaśnienie
niezwiązane z poszukiwaną strukturą. Słabe odległości nie dowodzą braku
informacji w enkoderze: ograniczony uczony odczyt E7 pozostaje dopuszczony
po przygotowaniu referencji. Wynik nie wybiera automatycznie nowej metody.
