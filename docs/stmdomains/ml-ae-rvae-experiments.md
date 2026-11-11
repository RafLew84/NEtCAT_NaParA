# AE/rVAE — plan kolejnych eksperymentów

Data: **2026-11-10**. Gałąź: `ml_domain`, baza `dfac8e5`.
Aktualizacja: **2026-11-10**, na bazie `8ca8738`, po przyjęciu przez użytkownika
[oceny propozycji](ml-ae-rvae-proposal-review.md). Status po wykonaniu E7:
**2026-11-11: E0–E3, E5 oraz osobna próba E7 syntetyki → STM wykonane**.
E7 na nadzorowanych etykietach STM i krzywa ilości danych pozostają odroczone;
E4/E6 niewykonane, warunkowe. Bez nowych ticketów wykonawczych.
Właściciel decyzji: użytkownik. Środowisko: `netcat`.
Przy pierwotnym opracowaniu wykonano audyt źródeł i małą kontrolę inferencji
dwóch istniejących modeli tiny16, opisaną poniżej. Następnie wykonano
[E0: audyt i przeglądarkę referencji](ml-ae-rvae-e0.md), bez nowej inferencji
lub treningu. [E1: bramka i mechanika](ml-ae-rvae-e1.md) wykazało utratę
przypisań przez bramkę oraz błędy relacji przed odmowami.
[E2: treść, kąt i odległości](ml-ae-rvae-e2.md) wykazało wybiórczy zysk
treści bez kąta, koszty normalizacji oraz nadal błędny podział domen.
[E3: fotometria i stabilność](ml-ae-rvae-e3.md) wykazało zmiany relacji oraz
domen po perturbacji jasności, z ważnym udziałem normalizacji L2.
[E5: lokalność, skala i centrowanie](ml-ae-rvae-e5.md) wykazało zmiany
kompromisu pokrycia/scalania/podziałów, bez ogólnej poprawy i wyboru detektora.
[E7: syntetyki → STM](ml-ae-rvae-e7.md) wykazało dobrą separację wąskiej
puli par syntetycznych, bez stabilnej poprawy domen na STM. Osiem małych
klasyfikatorów na zamrożonych enkoderach; tylko 45 różnych lokalnych par
train i cztery STM. **Dalszy kierunek: przejrzana referencja rzeczywistych
relacji oraz osobna diagnoza zamiany uczonych relacji na podział grafu.**
Nie uruchomiono tego kontrastu ani E4/E6, nie wybrano parametrów detektora.

## Pytanie i kolejność wykonania

Co ogranicza wynik AE/rVAE: informacja w wycinku, sposób jej kodowania,
odczyt podobieństwa, podział grafu czy odmowy po podziale? Najpierw chcemy
wyznaczać przestrzenne instancje domen; przypisywanie całych domen do klas
jest późniejszym zadaniem i nie wymaga teraz ustalenia K.

Kolejność dla celu wykrywania domen: **E0 → E1 → E2/E3 → E5 → mały E7 →
warunkowo E4/E6**. Identyfikatory E1–E7 zachowują znaczenie z pierwszej
propozycji; nie są numerami kolejności ani istniejących ticketów UI.

| Kolejność | Etap | Warunek i dane |
| --- | --- | --- |
| 1 — wykonane | E0: przypadki celu i inwentaryzacja referencji | 24 obrazy, 54 wnętrza, 10 ROI do przeglądu; [raport](ml-ae-rvae-e0.md). |
| 2 — wykonane | E1: bramki i mechanika podziału | 8 bramek i oracle 2×2; oba ograniczenia potwierdzone, [raport](ml-ae-rvae-e1.md). |
| 3 — wykonane | E2: odczyt cech i odległości | 15 odczytów na reżim, trzy przestrzenie, pięć tasowań; [raport](ml-ae-rvae-e2.md). |
| 4 — wykonane | E3: fotometria | Istniejące wagi i adaptery; zmiany relacji/domen oraz wpływ L2, [raport](ml-ae-rvae-e3.md). |
| 5 — wykonane | E5: lokalność, skala i centrowanie | Zamrożone wagi, 304 nowe adaptery; częściowe korzyści i błędy kontroli, bez wyboru detektora; [raport](ml-ae-rvae-e5.md). |
| 6 — osobna próba wykonana | Mały E7: uczony odczyt relacji | Syntetyki → znane STM, 8 fitów bez retreningu enkoderów; [raport](ml-ae-rvae-e7.md). Nadzór na etykietach STM nadal wymaga referencji i podziału grup. |
| 7 | Warunkowo E4 i E6 | E4: diagnostyka rVAE na tiny16; E6: jeden kontrast treningowy uzasadniony diagnozą. |
| Później | Rozszerzony E7: krzywa ilości danych | Po obiecującym odczycie i przygotowaniu dodatkowych grup MPP/STP. |

E4 można wcześniej wydzielić jako krótką gałąź, jeśli pytaniem jest sama
słaba rekonstrukcja rVAE. Nie jest obowiązkowym poprzednikiem E5/E7 ani
każdego wariantu E6. Mała referencja nie blokuje E1 lub eksploracji E2/E5;
blokuje mocne wnioski o rzeczywistych granicach i nadzorowany E7 na STM.
Plan nie oznacza uruchomienia całej macierzy ani wyboru gotowego detektora.

Priorytety dobrano jakościowo według: zdolności rozróżnienia konkurencyjnych
wyjaśnień, kosztu, możliwości użycia istniejących danych oraz znaczenia
wyniku negatywnego. Nie stosowano punktowego rankingu hipotez.

## Co już wiemy

- [21](autoencoder-domains-trial.md): bramka dopuszcza 52/3456 pełnych okien
  transferowych TTMAPP. Przed odmowami FH nadmiernie scala, a MWS rozdrabnia.
  MWS i FH różnią się również interpretacją relacji; ich różnica nie izoluje
  samego solvera. Wynik 0/174 dotyczy częściowej referencji miejsc siatki,
  nie skuteczności wykrywania molekuł na całym obrazie.
  Sam mały udział dopuszczonych okien nie dowodzi błędu bramki bez wiedzy,
  które odrzucone miejsca rzeczywiście należą do domen.
- [21a](rvae-decoder-kl-trial.md): zmniejszenie KL i Fourier w dekoderze
  poprawiają część miar reprezentacji, ale nie końcowe domeny. Kąt pozostaje
  niewiarygodny. Rekonstrukcja nie jest miarą poprawności domen.
  Sprawdzono już różnice orientacji 27° i 8° oraz obroty ±90° bez interpolacji;
  są punktem odniesienia, nie nową próbą. Powtórzenie wymaga zmiany modelu
  lub nowego kontrastu. Symetrii realnej sieci nie ustalono.
- Dekoder AE z32 ma 126 833 parametrów, a pierwotny dekoder rVAE tylko
  6465 (Fourier: 7745). Zbliżona liczba parametrów całych modeli maskuje
  różnicę ich rozkładu między enkoderem i dekoderem. To kandydat na
  ograniczenie, nie dowód jego przyczyny. [Architektury](../../stmdomains/experiments/training/models.py).
- Główny opis rVAE **już zawiera treść oraz sinus/cosinus kąta**, z równym
  ważeniem bloków. E2 bada ich wkład, nie proponuje dodania kąta jako nowości.
- Trening 21 **już usuwał sztucznie dodane zakłócenia fotometryczne**:
  zaszumione wejście miało czysty cel. „Dodać denoising” samo w sobie nie
  jest nowym eksperymentem. [Kod treningu](../../stmdomains/experiments/training/fit.py).
- Skale 32/48/64 px były testowane osobno. E5 dotyczy wspólnego odczytu
  wielu skal i przestrzennej mapy enkodera, a nie ponowienia starej tabeli.
- Zaledwie 28 par różnych referencji, w tym jedna lokalna krawędź w
  transferze, ogranicza ocenę rzeczywistych granic. Nowe syntetyczne ziarna
  nie zastępują niezależnych akwizycji. [Synteza wcześniejszych prób](research-after-training-pilot.md).

### Kontrola istniejących modeli podczas przygotowania propozycji

Odczytano dwa checkpointy tiny16 z kroku 2000, jednego ziarna treningowego.
Inferencja CPU w netcat, te same 16 wycinków, 8 losowań posteriora, seed
20261110. Dane, wagi i metadane starszych prób zachowały hashe.

| Model tiny16 | MSE dekodowania średniej | Średnie MSE 8 losowań | Mediana odchylenia treści posteriora |
| --- | ---: | ---: | ---: |
| beta=1e-3 | 0,0277572 | 0,0289363 | 0,991989 |
| beta=0 | 0,0216786 | 0,0216498 | 0,005365 |

Przy beta=0 różnica MSE wynosi około 0,13%. Losowość w końcowym
checkpointcie nie wyjaśnia więc głównej części jego rozmycia. Nie wyklucza
to wpływu losowania na wcześniejszą trajektorię treningu. MSE dla średniej
każdego wejścia wynosi 0,0429696, a dla osobno dopasowanej płaszczyzny
0,0344651: model odtwarza więcej niż te dwie proste bazy. Nie jest to dowód
odtworzenia molekuł lub granic. Oceniono tylko 16 wycinków, nie cały korpus.

Odtwarzalny skrypt i JSON z hashami, wersjami oraz parametrami:
`.scratch/ae-rvae-proposal-20261110/checkpoint_readout.py` i
`.scratch/ae-rvae-proposal-20261110/checkpoint-readout.json`.
To ograniczona diagnostyka istniejących wag, nie wynik E0–E7.

## E0 — przypadki celu i mała referencja rzeczywistych granic

**Wykonane 2026-11-10:** [raport i obsługa galerii](ml-ae-rvae-e0.md),
[manifest](ml-ae-rvae-e0-reference-manifest.json). Tabela przypadków, role
grup i 10 ROI są gotowe; nowe anotacje pozostają do przeglądu.
`independent_test=[]`, `supervised_split_ready=false`. E1 wykonane na obecnej referencji.
Poniżej zachowano zakres E0 i wymagania dla dalszej pracy z referencją.

Krótki audyt przed interpretacją eksperymentów, bez treningu. Oprzeć się
na [decyzji 02](issues/02-order-types-and-domains.md) i [słowniku](GLOSSARY.md).
W tabeli przykładów oddzielić: spójną sieć 2D, jej wąski fragment, wiele
rzędów o niespójnych fazach, lokalne dwa rzędy o niepewnej interpretacji,
przerwę, rzeczywistą granicę niedopasowania i globalne przesunięcie obrazu.
Każdy przykład ma wskazywać oczekiwane domeny albo jawny brak dostatecznych
danych. Próg ACF jest badanym pomiarem, nie pełną definicją domeny.

Wąski fragment znanej sieci i kontrola `independent_rows` to różne przypadki.
Dotychczasowe etykiety negatywnych kontroli pozostają zachowane. Dwa rzędy
mogą pasować do skośnej sieci bez dowodu powtarzalności w drugim kierunku;
nie wymuszać etykiety nieporządku na niejednoznacznym wycinku.
Nie przyjmować nowej reguły „dwa rzędy = domena” ani „kontrast = taras”.
Ewentualne rozszerzenie celu wymaga jawnej decyzji i nowej wersji benchmarku,
z raportowaniem także wcześniejszych kontroli.

Przesunięcie całego wzoru zachowuje tożsamość domen; maska przesuwa się
wraz z obrazem. Porównywać członkostwo na wspólnym wsparciu. Skok fazy tylko
części wzoru z widoczną linią niedopasowania oznacza osobne domeny zgodnie
z decyzją 02; `phase_boundary` i `crop` sprawdzają różne sytuacje.

Zinwentaryzować obecne referencje: zatwierdzone wnętrza, lokalne sąsiedztwa
„ta sama / inna domena”, krótkie odcinki granic i miejsca niepewne.
28 par różnych referencji i jedna lokalna krawędź transferowa nie wystarczają
do mocnej oceny granic. Mały zestaw przejrzanych ROI przygotować równolegle
do E1–E3, **przed rozstrzygającą oceną E2/E5 i uczeniem relacji E7**.
Nie są potrzebne pełne maski całej serii. Zakres anotacji ustalić według
brakujących rodzajów granic, nie arbitralnej liczby par.

Zapisać źródło, klatkę, współrzędne, status pewności, sposób zatwierdzenia
i grupę train/validation/test każdego ROI. Rozdzielić grupy przed wycinaniem
okien i tworzeniem par; uwzględnić wspólne molekuły, nakładające się okna
i kolejne obserwacje tego samego miejsca. Na jednej akwizycji użyć bloków
przestrzennych z buforem dla okien, z jawnym zakresem eksploracyjnym.
Znane trudne klatki pozostają rozwojowe po nowej anotacji. Nieoznaczone
miejsca nie są negatywami; odcinki granic nie pozwalają wyliczyć globalnego IoU.

**Wynik E0:** tabela przypadków i braków referencji, ustalone role danych
oraz lista ROI do przeglądu, z przykładami widocznymi na obrazie.
Niedokończone anotacje ograniczają wnioski dalszych prób, ale nie blokują E1.

## E1 — gdzie znika domena: bramka i mechanika podziału

**Wykonane 2026-11-10:** [wyniki i przeglądarka](ml-ae-rvae-e1.md),
[protokół](ml-ae-rvae-e1-protocol.md), [manifest](ml-ae-rvae-e1-manifest.json).
5880 dokładnie odtworzonych baz, 83 328 ocen, 4536 kontroli mechaniki oracle.
Bramka usuwa większość miejsc, ale jej wyłączenie odsłania błędne relacje.
Idealne wejścia odtwarzają spójne części prawdy; graf centrów z brakami ma
jawne ograniczenia. Wynik uzasadnił wykonane później E2/E3, bez zmiany metody aplikacji.
Poniżej zachowany zakres z doprecyzowaniem rzeczywistego minimum z pilota.

**Hipoteza:** znaczną część użytecznych przypisań usuwa konkretna składowa
odmowy. **Alternatywa:** odrzucany podział już wcześniej jest błędny.

- Zachować modele AE, rVAE i FFT, graf, wsparcie wycinków oraz algorytm
  podziału. Pokazać w każdym miejscu wszystkie przyczyny odrzucenia, a nie
  wyłącznie pierwszą. Oddzielić brak danych od niskiej oceny porządku.
- Wykonać **8 kombinacji włączenia/wyłączenia** trzech decyzji: próg ACF,
  dodatkowy filtr drugiego kierunku widma, minimum wielkości komponentu.
  Sam ACF już szuka dwóch niekolinearnych maksimów; wyłączenie filtra
  widmowego nie usuwa tego wymagania. Ważność danych, finite, dodatnia
  energia i kompletne wsparcie pozostają wymagane we wszystkich kombinacjach.
  Przeliczenie komponentów po usunięciu węzłów zachować jawnie i jednakowo.
  Raportować również interakcje: utrata węzłów zmienia wielkość komponentów.
- Osobno od ośmiu kombinacji bramek, tylko na syntetykach, wykonać pełne
  **2×2: relacje programu/generatora × maska programu/generatora**,
  według tabeli poniżej. To test mechaniki przy idealnym wejściu,
  **nie detektor**. Maska generatora oznacza miejsca prawdziwych domen,
  nie sam materiał; support i ważność danych pozostają osobnymi warunkami.
  Tło nie może otrzymać jednej wspólnej idealnej domeny. Zachować ten sam
  graf; brak połączeń potrzebnych do odtworzenia prawdziwej domeny jawnie
  ogranicza interpretację, bez ukrytej naprawy grafu.
- Uwzględnić jedną domenę, dwie orientacje, granicę przesunięcia, przerwę,
  szum, pasy i niezależne rzędy. Obecne GUI geometrii ma inne bramki;
  jego parametrów nie utożsamiać z bramką eksperymentu AE/rVAE.

| Relacje | Maska programu | Maska prawdziwych domen |
| --- | --- | --- |
| Z programu | Punkt odniesienia | Podmiana maski |
| Z prawdy generatora | Podmiana relacji | Obie podmiany jednocześnie |

Idealne relacje zakodować zgodnie z solverem i sprawdzić na małym grafie
o znanym podziale. Dla FH odległości 0/1 przy `k=4` nie gwarantują zakazu
scalania; dla MWS istotne są znaki i siły relacji. Zapisać kodowanie przed
próbą. Każdą z czterech konfiguracji ocenić przed i po minimum komponentu
(cztery węzły siatki / osiem centrów), przy jednakowym przeliczaniu spójności.

**Odczyt:** pokrycie znanych wnętrz, błędne scalenia/podziały i domeny na
negatywnych kontrolach; oddzielnie przed odmowami, po bramce i po minimum.
Idealne relacje przy błędnej masce nie rozstrzygają przyczyny porażki.
Jeśli pomagają dopiero obie podmiany, badać współdziałanie maski i relacji.
Jeśli pomaga tylko maska, priorytetem jest pomiar porządku; jeśli tylko
relacje, ich odczyt. Porażka obu idealnych wejść kieruje do mechaniki
dopiero po sprawdzeniu kodowania, reprezentowalności prawdy w grafie
i minimum wielkości. Domena mniejsza niż jawne minimum nie dowodzi błędu
solvera. Wyłączenie bramki zwiększające błędne przypisania nie jest poprawą.
Koszt: **niski**, cache/CPU, bez treningu i nowych etykiet.

## E2 — czy użyteczna informacja jest w treści, kącie i odległościach

**Wykonane 2026-11-11.** [Raport i przeglądarka](ml-ae-rvae-e2.md),
[protokół](ml-ae-rvae-e2-protocol.md), [manifest](ml-ae-rvae-e2-manifest.json).
Treść pomaga na dwóch orientacjach, pogarsza relacje przesunięcia i nie
naprawia rzeczywistych domen. L2 zmienia wyniki bardziej niż PCA rVAE;
FFT ma osobny przypadek utraty po PCA. Fotometria uzasadniła wykonane później E3.
Zachować odczyty treści i treści+kąta, bez globalnego wyłączenia kąta/bramki.
25 nowych testów PASS; galeria 303 PASS / 105 obrazów / 112 figur / 0 błędów JS.
Bez nowego treningu, inferencji lub zmiany aplikacji. Poniżej pierwotny zakres E2.

**Hipoteza:** niestabilny kąt lub sposób porównania cech osłabia przydatny
sygnał treści. **Alternatywa:** cechy nie rozróżniają rzeczywistych granic.

Porównać na tych samych wycinkach: AE, treść rVAE, obecne treść+kąt,
sam kąt jako diagnostykę oraz FFT. Zachować trening enkoderów zamrożony.
Dodać prostą bazę samych cech jasności/kontrastu, żeby mierzyć informację
wykraczającą poza te zmienne, oraz istniejące miary geometryczne: kierunek
rzędów, rozstaw i pewność okresowości. Nie otwierać osobnego dużego projektu
geometrii. Kąt interpretować według mierzonego obiektu: oś rzędów,
orientacja molekuły lub sieć; nie zakładać automatycznie równoważności
θ i θ+180° ani zamiany sin/cos na sin/cos podwojonego kąta.
Dla zmienionego odczytu dopasować normalizację/adapter wyłącznie na dawnym
treningu; pokazać dystanse również przed adapterem. Kontrolę z tasowaniem
cech wykonywać wewnątrz jednorodnych grup testowych jako bazę braku sygnału,
nie źródło nowych etykiet lub kalibracji.

**Odczyt:** rozkłady odległości sąsiadów wewnątrz domen i przez granicę,
krzywe precision–recall i ROC dla dostępnych relacji, z liczebnościami
oraz oceną osobno według rodzaju granicy. Następnie te same odczyty przez
niezmieniony podział grafu. Nie utożsamiać łatwej separacji czystych wnętrz
z lokalizacją brzegu. Nie powtarzać ogólnej hipotezy o PCA na FCN/DINO,
którą wcześniej już oceniono.

Jeśli treść rVAE pomaga bez kąta, rozwijać ten odczyt bez deklaracji
fizycznego pomiaru orientacji. Jeśli AE pomaga bardziej, może pozostać
główną bazą. Słabe odległości nie dowodzą braku informacji w reprezentacji:
dopuścić ograniczony, uczony odczyt E7 także po takim wyniku. Bez dostatecznej
referencji rzeczywistych granic wnioski pozostają diagnostyczne.
Koszt E2: **niski**, bez nowego treningu; trening klasyfikatora należy do E7.

## E3 — czy model opisuje strukturę, czy warunki obrazowania

**Wykonane 2026-11-11.** [Raport i przeglądarka](ml-ae-rvae-e3.md),
[protokół](ml-ae-rvae-e3-protocol.md), [manifest](ml-ae-rvae-e3-manifest.json).
105 obrazów, oba reżimy/samplery, trzy ziarna AE/rVAE, zamrożone adaptery E2;
bez treningu. Fotometria zmienia relacje i przypisania, a duża zmiana rankingu
odległości treści pojawia się już po L2, przed PCA. Osobna próba struktury
potwierdza wrażliwość na zadane perturbacje, bez zrównania ich fizycznej dawki.

Offset− nie stanowi gotowej poprawki. Dla treści/transdukcji/centrów/FH/H_M1
poprawia mediany STM, ale merge ziarna 20261103 rośnie 5,46→19,28%;
`two_orientations` ma 100% merge we wszystkich ziarnach, a `independent_rows`
nadal 100% fałszywych przypisań. MWS ma w tym odczycie na STM 100% merge.
Pokrycie i warunkowe błędy trzeba oceniać razem; pełna bramka niemal wszystko
odrzuca. To diagnoza ograniczeń, bez wyboru detektora lub parametrów.

Wniosek do dalszej interpretacji: ostrożnie rozdzielić normalizację L2,
odczyt i ewentualne przygotowanie obrazu przed decyzją o retreningu.
E3 nie dowodzi, że dowolne usuwanie tła poprawi domeny ani że PCA jest
główną przyczyną. **Kolejność pozostaje E5 → mały E7 po referencji i audycie
grup; E4/E6 warunkowo.** Nie utworzono ani nie uruchomiono nowego etapu.
20 testów PASS, QtWebEngine 186 PASS / 0 błędów JS; odbiór użytkownika
otwarty. Poniżej zachowano pierwotny zakres E3.

**Hipoteza:** niewielka zmiana tła/kontrastu zmienia cechy mocniej niż
zmiana struktury. **Alternatywa:** korelacja z jasnością nie odpowiada
za błąd lokalnych relacji lub jasność jest tu częścią rzeczywistej różnicy.

Zamrożone modele otrzymują pary tego samego wycinka ze zmianą offsetu,
gainu i osobno łagodnego gradientu. Zacząć od zakresów dotychczasowego
treningu: gain 0,9–1,1, offset ±0,1, sigma szumu 0–0,03 w jednostkach
znormalizowanego wejścia; zmiany gradientu określić z części train.
Zapisywać clipping i wspólne wsparcie, nie dodawać obrotu i fotometrii
jednocześnie w pojedynczym kontraście. Na syntetykach osobno zmieniać
orientację/rozstaw/przesunięcie struktury przy stałej fotometrii.

**Odczyt:** względna zmiana cech, relacji i przypisań; zgodność konturu
po transformacjach zachowujących strukturę. Zachować pełny obraz źródłowy,
ponieważ skok wysokości rzeczywistej warstwy nie jest automatycznie szumem.
Dominacja fotometrii uzasadnia pojedynczy wariant normalizacji w E6.
Stabilne cechy przy słabych domenach kierują uwagę ku relacjom/grafowi.
Koszt: **niski/średni**, nowa inferencja istniejących wag, bez treningu.

## E4 — co potrafi odtworzyć rVAE na 16 wycinkach

**Hipoteza:** ograniczenie leży w dekoderze współrzędnych lub optymalizacji
enkodera. **Alternatywy:** ograniczona informacja wejściowa, nieodpowiednia
strata albo wpływ stochastycznego treningu. KL nie jest jedynym kandydatem.

Użyć identycznych 16 wejść z 21a, bez augmentacji, beta=0. Proponowana
drabina ma najwyżej pięć konfiguracji, uruchamianych etapami:

1. AE z32 jako kontrola, czy dane i budżet pozwalają zapamiętać szczegóły.
2. Sam pierwotny dekoder współrzędnych 2×64, z osobno uczonym kodem każdego
   wycinka, bez enkodera, posteriora i uczenia pozy (kąt/przesunięcie = 0).
3. Ten sam test z jednym większym dekoderem 2×256 (około 75 tys. parametrów).
4. Warunkowo jeden wariant Fouriera w większym dekoderze, jeśli surowe
   współrzędne nie pozwolą odtworzyć szczegółów. Bez przeszukiwania pasm.
5. Jeśli któryś dekoder działa, dołączyć enkoder przy tej samej stałej
   pozie, bez KL i losowania. Zachować checkpoint skutecznego dekodera
   i **zamrozić jego wagi**; uczyć tylko enkoder przez stratę rekonstrukcji
   z tego dekodera. Osobno zoptymalizowane kody pozostają odniesieniem,
   ale nie wymagać identyczności kodów przy tej samej rekonstrukcji.
   Wspólne dostrajanie obu części byłoby oddzielnym, późniejszym kontrastem.

Limit: do 5 konfiguracji × 2 ziarna × 2000 kroków = **20 000 kroków**.
Te same batche, optimizer i jawna liczba parametrów. Samo deterministyczne
**dekodowanie** nie jest nowością — już służyło do walidacji 21/21a.
Nowy trening deterministyczny nie izoluje sam wpływu losowania bez
równoległego, identycznego wariantu stochastycznego; taki wniosek nie jest
celem tej drabiny. Porównanie Fourier obejmuje też zmianę wejścia dekodera.

MSE mierzyć razem z profilem rzędów, odtwarzaniem okresowości i błędem
przestrzennych gradientów, przy jednej skali jasności wejścia i rekonstrukcji.
Wykresy całej trajektorii, bez dobierania kroku według wyglądu domen.
To celowe zapamiętywanie, bez wniosku o transferze lub fizycznym kącie.

Jeśli sam dekoder odtwarza szczegóły, a enkoder z tym zamrożonym dekoderem
nie, badać uczenie mapy obraz→kod w tym budżecie. Nie jest to samodzielny
dowód zbyt małego enkodera lub braku informacji w obrazie.
Jeśli AE odtwarza, a oba dekodery współrzędnych nie,
ma sens przebudowa tej części. Niepowodzenie w skończonym budżecie nie
dowodzi matematycznej niemożliwości; nie zwiększać automatycznie budżetu.
Koszt: **kilka mikrotreningów**, bez dodatkowych obrazów i etykiet.

## E5 — lokalność, skala i położenie wycinka

**Wykonane 2026-11-11:** [raport i przeglądarka](ml-ae-rvae-e5.md),
[protokół](ml-ae-rvae-e5-protocol.md), [manifest](ml-ae-rvae-e5-manifest.json).
Mapa AE, pojedyncze i połączone skale oraz izolowane centrowanie: 255360 ocen,
oba samplery/reżimy, trzy ziarna. Nie uzyskano ogólnej poprawy detektora;
większe pokrycie bywa okupione scalaniem, snap niszczy część granic przesunięcia.
Brak treningu enkoderów lub nowych etykiet. E7 nadal wymaga przejrzanej referencji i grup.
Poniżej zachowano zakres zatwierdzony przed próbą.

W głównej kolejności przed E4, ponieważ bez nowego treningu bezpośrednio
sprawdza użyteczność cech przy granicach. Do mocnej oceny realnych granic
wykorzystać małą referencję z E0; bez niej raportować ograniczoną diagnostykę.

**Hipoteza:** pojedynczy kod całego okna miesza dwie domeny i gubi miejsce
granicy. **Alternatywa:** cechy w ogóle nie opisują potrzebnej struktury.

Testować czynniki kolejno, nie zmieniać wszystkich jednocześnie:

1. Zamrożony AE: obecny z32 kontra jeden ustalony odczyt przestrzennej mapy
   enkodera 64×7×7, przy tej samej skali i kontekście. Regułę lokalizacji,
   receptive field i wymiar adaptera zamrozić przed oceną.
2. Obecny odczyt pojedynczej skali kontra połączenie osobnych opisów
   32/48/64 px. Nie dobierać najlepszej skali osobno dla każdej referencji.
3. Wykorzystać dotychczasową diagnostykę siatki i grafów centrów z 21.
   Nowy, izolowany kontrast centrowania: te same węzły rzeczywistych
   molekuł i te same krawędzie, lecz wycinek wycentrowany dokładnie na
   molekule albo przesunięty na najbliższy punkt ustalonej siatki. Ta sama
   skala, wspólne pełne wsparcie i jawne przesunięcia. To odróżnia wpływ
   centrowania od wcześniejszego porównania dwóch różnych grafów.

Uwzględnić przesunięcie siatki, brzegi, defekty i kontrolę jednej sieci,
żeby nie uznać obrysu każdej molekuły za granicę domeny. Pełne wsparcie
wszystkich porównywanych skal ma być wspólne albo jawnie rozdzielone.
**Odczyt:** lokalizacja granicy oraz fałszywe cięcia przy zachowaniu wnętrz.
Koszt: **średni**, inferencja/przygotowanie odczytu bez treningu enkodera.

## E6 — jeden nowy cel lub sposób przygotowania obrazu

Etap warunkowy po diagnozie z odpowiedniej próby E2–E5 lub małego E7;
E4 nie jest wymagane dla kontrastu fotometrii uzasadnionego przez E3.
Nie uruchamiać szerokiej macierzy KL × z × decoder × loss. Wybrać jedną
przyczynę do testu i zapisać ją przed treningiem:

- Jeśli E3 wykazuje dominację tła: dotychczasowa normalizacja kontra
  usuwanie lokalnej płaszczyzny, z zachowaniem jej parametrów i raw obrazu
  do kontroli. Nie stosować nowej normalizacji tylko podczas inferencji
  i nie nazywać takiego porównania równoważnym treningiem.
- Jeśli E4 pokazuje odtwarzanie tła przy utracie szczegółów: obecne MSE
  kontra MSE z jednym dodatkowym składnikiem gradientowym. Wagę ustalić
  na train, bez wyboru po wyniku domen; kontrolować wzmacnianie szumu.
  Sam moduł FFT nie zastępuje przestrzennego celu tracącego wtedy fazę.
- Jeśli problem dotyczy użycia pozy: warunkowo dopasować zgodność
  reprezentacji dla znanych transformacji. Kontrolować niejednoznaczną
  symetrię, orientację molekuły i sieci osobno; nie zakładać symetrii M6.

Każda wybrana para ma tę samą architekturę, dane i regułę wyboru kroku:
**2 warianty × 3 ziarna = maksymalnie 6 pełnych fitów** na jeden wybrany
kontrast. Dokładny budżet kroków/czasu zapisać w protokole wykonawczym.
Lepsza rekonstrukcja jest wynikiem częściowym; kontynuację uzasadnia
korzyść na relacjach i domenach. Denoising oraz słabsze KL były już badane.
Jeśli celem staje się izolacja mechanizmu rVAE, przygotować osobny kontrast:
AE kontra zwykłe VAE z tym samym dekoderem, a następnie coordinate VAE
bez pozy kontra rVAE z identycznym dekoderem. Dawne AE–rVAE zmieniało
równocześnie dekoder, wariacyjność, KL i pozę; nie izoluje wpływu obrotu.

## E7 — mały uczony odczyt relacji i późniejsza krzywa ilości danych

**2026-11-11 — wykonano osobny wariant syntetyki → STM na wyraźny wybór
użytkownika.** [Raport i przeglądarka](ml-ae-rvae-e7.md),
[protokół](ml-ae-rvae-e7-protocol.md), [manifest](ml-ae-rvae-e7-manifest.json).
81 nowych syntetyków train, 81 validation, 24 znane obrazy STM; osiem
regularizowanych odczytów. AP rVAE=1 na wąskiej referencji syntetycznej,
bez stabilnej poprawy domen nad geometrią. Na STM silna zależność od ziarna,
pełna bramka nadal 0% pokrycia znanych wnętrz. Reguła skali FH oraz progi
kwantyli MWS nie odpowiadają progowi klasyfikatora 0.5. Brak treningu enkoderów.
19 testów i 167 kontroli Qt PASS; odbiór użytkownika galerii otwarty.
Nadzorowany E7 na rzeczywistych etykietach oraz krzywa ilości danych
**nie zostały wykonane**. Poniżej zachowane warunki tych etapów.

Mała próba jest dopuszczona **również po słabych dystansach E2/E5**,
jeśli istnieją zatwierdzone relacje i grupy do uczenia oraz walidacji.
Sygnał w zwykłych odległościach nie jest warunkiem wejścia. Ograniczyć się
do jednej, z góry określonej regularizowanej rodziny klasyfikatora, bez
poszukiwania wielu modeli. Przy tym samym grafie i algorytmie podziału
porównać ten sam mały klasyfikator otrzymujący:
**geometrię**, **geometrię+AE**, **geometrię+rVAE**. Enkodery pozostają
zamrożone; złożoność klasyfikatora i dobór parametrów mają ten sam budżet.
Osobno porównać klasyfikator z dotychczasową regułą odległości.
Zachować bazę fotometrii z E2, aby nie utożsamić korzyści jasności/kontrastu
z informacją strukturalną. Skalowanie, adaptery i dobór parametrów mają
korzystać tylko z odpowiedniej części treningowej; sprawdzić także, jakie
dane widziały istniejące enkodery, i ujawnić ewentualny charakter transdukcyjny.

Dobry wynik na oddzielonych grupach przy słabych dystansach uzasadnia
rozwój odczytu. Słabe dystanse i słaby mały klasyfikator oznaczają brak
użytecznego odczytu w tym zakresie danych/metody; przemawiają praktycznie
za zmianą reprezentacji, ale nie dowodzą matematycznej nieobecności informacji.
Korzyść na parach potwierdzić na domenach po niezmienionym podziale grafu.

To uczenie nadzorowane relacją, bez konieczności nazw klas domen. Dodatnie
pary pochodzą z zatwierdzonych wnętrz, ujemne z zatwierdzonych styków;
niepewne i nieprzejrzane obszary są pomijane. Możliwe źródła: małe ręczne
korekty albo osobna próba synthetic→real. Prawda generatora w treningu
oznacza nadzór syntetyczny; nie przedstawiać jej jako uczenia bez etykiet.

Referencję przygotować wcześniej w E0 i równolegle do E1–E3; E7 korzysta
z ustalonych grup i przejrzanych ROI. Podział poprzedza tworzenie par:
wspólne molekuły, nakładające się wycinki i to samo miejsce w kolejnych
klatkach nie mogą przeciekać między train i validation. Dawne 174 miejsca
nie tworzą nowego niezależnego testu. Bez właściwej referencji odroczyć
nadzorowaną próbę STM; synthetic→real pozostaje osobnym kontrastem.

**Późniejszy etap ilości danych:** po obiecującym małym odczycie większą
pulę MPP/STP dołączać po sprawdzeniu odczytu, skali i grup pomiarów.
Porównanie 25/50/100% grup train przy stałej walidacji pozwoli oszacować,
czy kolejne pomiary pomagają. Test końcowy pozostaje poza doborem danych.
[Walidacja grupowa](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data),
[krzywe uczenia](https://scikit-learn.org/stable/modules/learning_curve.html#learning-curve).

## Wspólny protokół i sposób pokazania wyników

- Zachować wagi, dane i raporty 21/21a; nowe artefakty w osobnym katalogu.
  Przed próbą sprawdzić hashe, identyfikatory wejść i netcat; adaptery,
  normalizację i progi dopasowywać tylko do odpowiedniego train.
  Zapisywać nm/piksel, fizyczny rozmiar wycinka, liczbę widocznych okresów
  oraz układ odniesienia orientacji obrazu/próbki. Brak skali lub orientacji
  pozostaje jawny; nie przeliczać jednostek na podstawie założenia.
- Jednostka oceny to pole/akwizycja i rodzaj kontrolowanej granicy. Okna,
  pary, sąsiednie klatki i ziarna modeli nie są niezależnymi akwizycjami.
  Całe grupy pomiarowe rozdzielać przed wycinaniem okien. Obecne TTMAPP
  i widziane syntetyki pozostają materiałem rozwojowym.
- Porównania sparowane na tych samych wejściach. Raportować wszystkie
  warianty i ziarna; główne kontrasty określić przed obliczeniami. Kolejność
  fitów przeplatać, jeśli porównujemy też koszt. Nie wybierać najlepszego
  wyniku według znanej częściowej referencji i nie nazywać jej testem.
- Mierzyć scalenia, podziały, pokrycie i błędne przypisania oddzielnie.
  Ocena par na wspólnym zbiorze dostępnych miejsc; odmowy raportować
  osobno. Błąd liczony tylko na zachowanych łatwych parach nie wystarcza.
  Kontury oceniać liczbowo na syntetykach lub dokładnych maskach; obecne
  przybliżone ramki nie umożliwiają pełnego boundary F1/IoU na STM.
  Ten sam procent pokrycia może dotyczyć innych, łatwiejszych miejsc.
  Pokazywać błędy i odmowy na całym ocenialnym zbiorze, wynik na wspólnej
  części i liczebności; poważne błędne scalenia raportować osobno.
  Progów nie dopasowywać do referencji testowej w celu wyrównania pokrycia.
- Kandydat do dalszej pracy: poprawa podziału przy zachowaniu pokrycia lub
  lepsze pokrycie bez wzrostu błędów; bez pogorszenia wcześniej zaliczonych
  negatywnych kontroli. Wyniki mieszane pozostają kompromisem do oceny,
  nie automatycznym sukcesem. Przy 0 przypisań miary wymagające par są
  niedostępne. Progi praktycznej poprawy i tolerancję granicy doprecyzować
  w wybranym protokole przed jego uruchomieniem, nie po obejrzeniu wyniku.
- Przeglądarka: ta sama klatka, zoom i skala; domeny na obrazie, rzeczywiste
  molekuły z przypisaniami, nieprzypisane szare. Przełączniki wariantu oraz
  przed/po odmowach; kliknięcie pokazuje powód. Wyniki siatki mają jawny
  osobny tryb. Projekcji siatki na centra nie przedstawiać jako źródłowej
  predykcji molekuł; przed użyciem określić regułę i jej niepewność.
  Kolory porównywanych domen stabilizować w obrębie porównania.

## Sprawdzone źródła, granice przeglądu i pochodzenie propozycji

Przegląd ograniczony, 2026-11-10: raporty/kod projektu oraz źródła
pierwotne o rVAE, denoising i rozdzielaniu czynników zmienności. Zapytania:
„Vincent Larochelle Bengio Manzagol 2008 Extracting Composing Robust
Features Denoising Autoencoders pdf” i „Locatello Challenging Common
Assumptions Unsupervised Disentangled Representations 2019 pmlr”; dodatkowo
bezpośredni odczyt poniższych stron. Nie jest to przegląd systematyczny
ani ustalenie nowości metod. Nie przesyłano obrazów lub wag na zewnątrz.

- [Valleti i in., rVAE w STEM](https://arxiv.org/abs/2101.06892): precedens
  oddzielania orientacji w innym typie obrazowania. Nie potwierdza jakości
  kąta w naszych danych ani potrzeby stosowania tej samej architektury.
- [Ziatdinov i Kalinin, j-trVAE](https://arxiv.org/abs/2104.10180): uzasadnia
  sprawdzanie modelu niezmienniczego w mikroskopii; nie gwarantuje domen.
- [Locatello i in., ICML 2019](https://proceedings.mlr.press/v97/locatello19a.html):
  rozdzielenie czynników bez założeń nie jest identyfikowalne; wymagana jest
  ocena konkretnej korzyści w zadaniu. Motywacja do E2/E7, nie dowód, że
  obecny rVAE musi zawieść.
- [Vincent i in., ICML 2008](https://doi.org/10.1145/1390156.1390294): podstawa
  uczenia odszumiania; ten ogólny mechanizm już występuje w naszym treningu.
- [Alain i Bengio, linear classifier probes](https://arxiv.org/abs/1610.01644):
  prosty niezależnie uczony odczyt jako diagnostyka reprezentacji. Motywacja
  do małego E7 mimo słabych dystansów; nie dowód skuteczności na naszych danych.

Zastosowano `scientific-brainstorming`, `hypothesis-generation`,
`experimental-design`, `scientific-critical-thinking`: niezależne propozycje
dwóch analiz, konfrontacja z kodem/źródłami i osobny przegląd krytyczny.
To wsparcie AI, nie konsensus niezależnych eksperymentów. Przygotowanie
wykorzystuje procedury opisane przez Kassis, Agarwal, He, Patel i Brueckner
(2026), [Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://doi.org/10.48550/arXiv.2609.00065).
Metadane zweryfikowano 2026-11-10. Skille nie stanowią dowodu skuteczności
proponowanych metod. Użytkownik przyjął uwagi do planu 2026-11-10;
aktualizacja obejmuje E0, kolejność, układ 2×2, wcześniejszą referencję,
mały E7 i zamrożenie dekodera. Wybór konkretnej próby do uruchomienia
pozostaje osobnym krokiem. Po aktualizacji użytkownik zlecił E0; jego wykonanie
i ograniczenia odnotowano powyżej. Następnie wykonano E1, E2, E3, E5
oraz wybraną osobno próbę E7 syntetyki → STM. E4/E6 pozostają warunkowe;
nadzorowany E7 na etykietach STM oraz krzywa danych są odroczone.
