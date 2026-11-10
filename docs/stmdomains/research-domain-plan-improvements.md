# Jak usprawnić plan samodzielnego wykrywania domen STM

Data przeglądu: **2026-10-31**. Pytanie użytkownika: jak poprawić plan po
słabych wynikach 15–19, skoro następne próby dotyczą uczenia cech i klastrowania?

To przegląd źródeł pierwotnych i **propozycja zmian planu**, nie raport nowego
eksperymentu. Nie uruchomiono treningu, nie zmieniono statusów ani zależności
20–26, nie otwarto ponownie zakończonej serii 19. Źródła dotyczące SEM, STEM
i obrazów biologicznych oznaczono osobno: nie są walidacją na molekularnym STM.

**Aktualizacja po badaniu — 2026-10-31:** użytkownik polecił dodać
rekomendacje do planu. Wpisano je do
[20](issues/20-self-supervised-training-preparation.md),
[21](issues/21-autoencoder-domains.md),
[22](issues/22-local-self-supervised-domains.md) i
[23](issues/23-training-comparison-and-next-step.md).
Pilot należy do 21/22, bez nowego ticketu; 24–26 pozostają warunkowe.
Poniższy tekst zachowuje uzasadnienie badawcze. Bieżący zakres wykonania
określają tickety; przyjęcie planu nie jest wynikiem eksperymentu.

## Wniosek

**Rekomenduję uczynić relacje między sąsiednimi obszarami i zachowanie granic
głównym sprawdzianem najbliższych treningów.** Osobno mierzyć, ile zmieniają
cechy, podział przestrzenny i odmowy. Sama zamiana algorytmu klastrowania
nie wystarczy: w 19 już sprawdzono podział grafu i ocenę lokalnych krawędzi.
Nowa hipoteza musi dotyczyć lepszych informacji o łączeniu/granicy lub ich
wykorzystania, a nie ponownego strojenia tego samego podobieństwa cech.

Proponowany pierwszy zakres to: przygotowanie 20, mały AE jako punkt
odniesienia oraz lokalne SSL z oceną relacji; w ich obrębie krótki test
jednego dodatkowego sposobu podziału, następnie decyzja 23. Nie wydłużać
przygotowania o nową serię badań wszystkich starych cech. rVAE pozostaje celowaną próbą oddzielenia
orientacji od typu. Rozszerzenia 24–26 nadal wymagają konkretnego uzasadnienia;
nie należy wykonywać ich automatycznie. Jest to rekomendacja dla tego
projektu, a nie ranking skuteczności potwierdzony na TTMAPP.

## Co już jest dobrze określone, a czego brakuje

[Krok 20](issues/20-self-supervised-training-preparation.md) już wymaga
podziału danych przed wycinaniem okien, kontroli nakładania się pól,
wyłączenia ręcznych referencji z treningu, budżetu i powtórzeń.
[21](issues/21-autoencoder-domains.md) i
[22](issues/22-local-self-supervised-domains.md) wymagają końcowej oceny
domen, nie tylko strat treningowych. W 22 zapisano także ocenę cech/podziału
przed filtrem porządku i odmów po nim. Nie trzeba dopisywać tych zasad jako
nowych odkryć.

Nie jest to brak jakiegokolwiek badania przestrzeni. W 19
[porównano graf Felzenszwalba–Huttenlochera z HDBSCAN](local-feature-graph-trial.md),
pokazano wynik przed/po filtrze oraz oceniono rzeczywiste krawędzie.
Na kontroli obrotu 8° AUC dla FCN/siatka spadło z 0.994 przy porównywaniu
czystych wnętrz do 0.543 na krawędziach. Na TTMAPP podział przed filtrem
także błędnie scalał obszary, a filtr ograniczał przypisania do 2.0–5.8%
z 1678 oznaczeń w ocenianych wnętrzach częściowych referencji.
[Porównanie dwóch modeli](disjoint-models-material-trial.md) badało już
przesłanki granicy i materiału, lecz nie poprawiło TTMAPP.

Luka w 20–26 polega na braku konkretnej hipotezy, jak trening ma poprawić
te relacje, oraz zamrożonych kryteriów kontynuacji. Kolejny solver na tych
samych niewystarczających wagach może powtórzyć porażkę. Dlatego potrzebny
jest krótki sprawdzian nowych cech na sąsiadach przecinających granicę,
również gdy ich okna częściowo się pokrywają. Dobre rozróżnienie odległych
wnętrz nie jest wystarczającym warunkiem sukcesu.

## Co wynika ze źródeł

### 1. Podział przestrzenny może być osobnym modułem bez zadanej liczby domen

Mutex Watershed (MWS) przyjmuje graf z ważonymi połączeniami przyciągającymi
i odpychającymi. Nie wymaga zadanej liczby segmentów ani jednego ziarna na
segment. Autorzy porównują różne sposoby podziału przy tych samych wyjściach
sieci. Wynik mikroskopii elektronowej korzysta jednak z przewidywań relacji
uczonych z etykiet segmentacji; nie dowodzi samodzielnego uzyskiwania takich
relacji bez etykiet na STM.
Określenie „parameter-free” dotyczy algorytmu podziału, nie całego sposobu
tworzenia grafu i jego wag. [Wolf i in., ECCV 2018, §3–4](https://www.ecva.net/papers/eccv_2018/papers_ECCV/papers/Steffen_Wolf_The_Mutex_Watershed_ECCV_2018_paper.pdf),
[kod autorów i osobne skrypty uczenia relacji](https://github.com/sciai-lab/mutex-watershed).

Lifted multicut umożliwia uwzględnianie relacji pomiędzy dalszymi fragmentami
obrazu; praca Pape i współautorów pokazuje wykorzystanie wiedzy o obiektach
w kilku zadaniach biologicznej mikroskopii elektronowej. Przenosimy ideę
oddzielnego kodowania przesłanek łączenia i rozdzielenia, nie ich reguły
biologiczne. [Pape i in., 2019](https://arxiv.org/abs/1905.10535).

Istnieje kod do porównania podziałów grafowych, m.in. MWS i multicut, w
bibliotece `elf`. Dostępność implementacji nie potwierdza jej zgodności
z lokalnym `netcat`; to sprawdzenie techniczne przyszłego eksperymentu.
[Dokumentacja autorów `elf.segmentation`](https://constantinpape.github.io/elf/elf/segmentation.html).

**Nasza rekomendacja:** wybrać najwyżej jeden taki dekoder przestrzenny,
np. MWS, i porównać go z zachowanym podziałem grafu. Nowym elementem są
jawne relacje przyciągające i odpychające, a nie samo użycie grafu. Multicut zostawić
jako alternatywę, jeśli ujawni się konkretne ograniczenie. Nie uruchamiać
od razu wszystkich solverów. Żaden solver nie naprawi braku informacji
o rzeczywistej granicy w wejściowych wagach.

### 2. Klaster struktury i konkretna domena nie są tym samym

W pracy o superstrukturach nanocząstek SEM lokalna transformacja Radona
prowadzi do grupowania hierarchicznego; później osobny etap rozdziela
przestrzennie odłączone obszary tej samej grupy na poszczególne ziarna.
Stosowany jest próg odległości, a nie podana liczba klastrów. Jest to
przydatny precedens rozdzielenia podobnej orientacji i instancji obszaru,
ale nie dowód wykrywania granicy przesunięcia na STM. Dobór okien, progu
i usuwania defektów pozostaje specyficzny dla danych. [Paruchuri i in.,
preprint 2025, §III.D–E](https://arxiv.org/pdf/2501.04172).

Bezpośrednia praca STM Bui i współautorów oddziela segmentację pozornej
wysokości od segmentacji tekstury; wykorzystuje odpowiednio metodę
wariacyjną i EWT z grupowaniem. To uzasadnia rozdzielanie sygnału materiału
i struktury, lecz nie zatwierdza naszego dotychczasowego wariantu EWT ani
nie wymaga ponownego wykonania zakończonego 17. [Bui i in., 2018](https://arxiv.org/abs/1804.08890).

**Nasza rekomendacja:** zachować możliwość tworzenia lokalnych propozycji
domen przed przypisaniem wspólnego typu. Katalog typu nie powinien być
obowiązkową bramką istnienia każdej domeny. Część prób 19 już rozdzielała
te etapy; utrzymanie tej zasady samo nie jest nowym eksperymentem ani
rozwiązaniem granic. Dwa oddalone obszary o tych samych
cechach mają oddzielne identyfikatory domen; orientacja i typ pozostają osobne.
Obowiązują [uzgodnione definicje](issues/02-order-types-and-domains.md).

### 3. Nowy encoder nadal nie dostarcza definicji granicy

VICRegL uczy lokalnych i globalnych reprezentacji przez porównanie
odpowiadających sobie fragmentów przekształconych obrazów. Jest podstawą
uczenia cech, a nie źródłem etykiety „ta sama fizyczna domena” dla dowolnych
sąsiadujących miejsc. [Bardes i in., NeurIPS 2022](https://arxiv.org/abs/2210.01571).

Nawet praca z 6 października 2026 o Gabor–VAE–k-means na STEM określa
wybór liczby klastrów jako wspomagany wiedzą o strukturze. Pokazuje też,
że niższy błąd rekonstrukcji może współwystępować z nadmiernym podziałem.
Nie jest więc gotową realizacją naszego warunku braku narzuconych domen
i ich liczby. [Sohn i in., 2026, Methods i Results](https://link.springer.com/article/10.1186/s40543-026-00570-z).

**Nasza rekomendacja:** zachować dwa rodzaje informacji: opis struktury,
który pozwala porównywać układ i rozstaw, oraz opis lokalnej nieciągłości,
który może ujawnić zmianę orientacji lub przesunięcie wzoru. Jeżeli pierwszy
opis celowo ignoruje przesunięcie, samo podobieństwo tych opisów nie może
rozstrzygać granicy przesunięcia. To konsekwencja projektu reprezentacji,
nie dowód, że określona sieć zawsze gubi fazę.

Istnieje też precedens uczenia bliższego relacjom instancji: INPAINTAFF
wyprowadza podobieństwa par z przewidywalności zakrytych części obrazu,
a potem używa MWS. W wynikach pełnej segmentacji korzysta jednak z prawdziwej
maski obiektów albo dodatkowej sieci foreground uczonej z oznaczeń; parametry
również podlegają walidacji. Nie jest gotowym całkowicie bezetykietowym
detektorem STM. [Wolf i in., 2020, §2–3](https://arxiv.org/pdf/2003.00891).
Nasza propozycja do ewentualnego wariantu 22/25: sprawdzić, czy utrata
przewidywalności między otoczeniami pomaga znaleźć granice. Nie dodawać
obowiązkowej nowej rodziny; wspólna tekstura po obu stronach granicy może
podważyć tę hipotezę.

## Ograniczony pilot relacji i podziału w najbliższych próbach uczenia

Proponuję umieścić go we wspólnym protokole **21/22**, a w 20 ustalić jego
format i budżet. Nie dodawać kolejnego przygotowawczego ticketu, który
odkładałby trening. Zachowane cechy służą jako zamrożony punkt odniesienia, nie
przedmiot nowej długiej serii dopasowywania progów z 19. Planować tę próbę
razem z uczeniem, aby mogła ocenić nowy sygnał relacji.

1. **Wejście:** pełne klatki, lokalne otoczenia w kilku ustalonych skalach;
   centra molekuł i regularna siatka obrazu są osobnymi wariantami. Nie
   wycinać tylko ręcznych domen ani nie odczytywać ich kolorów. Rozdzielić
   sąsiedztwo fizyczne od podobieństwa wyglądu.
2. **Relacje par:** zapisać osobno przesłankę wspólnej struktury,
   nieciągłości/granicy i dostępności danych. Przykładowe wejścia to
   różnica cech, orientacji/rozstawu i lokalne niedopasowanie wzoru.
   Nie nazywać odległości cech skalibrowanym prawdopodobieństwem.
   Bliskie położenie nie jest etykietą tej samej domeny, a brak dowodów
   podobieństwa nie jest automatycznie dowodem granicy.
3. **Podział:** ten sam graf i ta sama dokumentacja relacji dla obu
   porównywanych sposobów łączenia; ujawnić różnice obsługiwanych relacji.
   Zmiana samych wag i zmiana solvera muszą mieć osobne kontrole.
   Ustalić budżet konstrukcji grafu,
   skalowania wag i rozstrzygania remisów. Unikać długich połączeń
   przyciągających wyłącznie dlatego, że dwa odległe fragmenty mają ten
   sam typ. Jeśli występują połączenia dalsze, zapisać ich znaczenie.
4. **Jawne stany wyniku:** najpierw propozycja podziału, następnie jej
   dowody i niepewność. Solver może oznaczyć każdy węzeł, ale nie oznacza
   to obecności domeny przy każdym węźle. Materiał, nieporządek i brak
   wystarczających danych pozostają osobnymi informacjami. Nie przyjmować
   „ciemne = podłoże” ani „brak centrum = przerwa”.
5. **Granice i pole:** na początku obszar propozycji może być zbiorem
   przypisanych otoczeń/centrów. Nie przedstawiać otoczki punktów jako
   sprawdzonego konturu. Osobny wynik ma mówić, gdzie granica jest
   podparta danymi, a gdzie lokalizacja jest niepewna.

Powyższe to hipoteza adaptacji do STM. Nie mamy jeszcze potwierdzenia, że
przesłanki relacji będą wystarczające na TTMAPP. Brak poprawy na ustalonym
budżecie powinien zakończyć tę konkretną próbę zamiast inicjować serię
nieograniczonych wariantów.

Przed właściwym porównaniem wykonać małą kontrolę techniczną solvera na
syntetycznym grafie z relacjami wyznaczonymi ze znanej segmentacji. To test
poprawności podziału, nie trening ani wynik wykrywania; takie relacje nie
trafiają do wejścia TTMAPP. Brak zadanego `K` nie znosi parametrów i założeń.

## Małe porównanie 2 × 2 zamiast kolejnego dużego przeszukiwania

| | Dotychczasowy sposób podziału | Nowy podział przestrzenny |
| --- | --- | --- |
| Zachowane cechy klasyczne lub zamrożone | Punkt odniesienia | Wpływ relacji i podziału |
| Nowe cechy uczone bez etykiet | Wpływ samego uczenia | Wpływ połączenia obu zmian |

Wybrać jeden zachowany zestaw cech i jeden nowy kandydat do pierwszego
takiego porównania; nie brać iloczynu wszystkich historycznych konfiguracji.
Kolejny encoder dopuszczać jako osobną, porównywalną próbę. Zachować te same
klatki i kontrole, porównywalne wsparcie przestrzenne, tę samą regułę
normalizacji relacji oraz uczciwy budżet doboru parametrów. Nie wymagać
identycznej liczby dla progu, jeśli skale dwóch cech są różne; różnicę
i sposób ustalenia parametru opisać przed oceną.

Wpływ **samego solvera** można wydzielić tylko przy równoważnej dostępnej
informacji. Jeżeli MWS dostaje nowe relacje odpychające, których poprzedni
podział nie obsługuje, porównanie mierzy łącznie kodowanie relacji i podział;
nie przypisywać całej zmiany solverowi. Nie wymaga to nowego dużego iloczynu
wariantów, tylko jawnego wskazania, co rzeczywiście zostało zmienione.

W każdym polu pokazać wynik przed oceną wiarygodności i po niej. Starego
filtra porządku nie uznawać automatycznie za prawdę. Jednocześnie nie
zaliczać wszystkich uzyskanych grup jako domen. Wzrost liczby przypisań
bez kontroli fałszywych scaleń nie jest poprawą.

## Ocena, która rozstrzyga decyzję

Następujące zasady są propozycją konkretyzacji istniejących kroków 14/20
i protokołu jakości; nie są nowymi etykietami treningowymi:

- **Przypadki rozstrzygające:** jedna sieć, dwie orientacje, zmiana rozstawu,
  ta sama orientacja z granicą przesunięcia, dwa odłączone obszary tej samej
  struktury, brak centrów bez przerwy w materiale, prawdziwa pusta przerwa,
  nieuporządkowanie i za mało danych. Włączać mieszanki tych trudności,
  nie tylko izolowane idealne sieci.
- **Pełne TTMAPP:** zawsze pokazać pełne klatki i wszystkie nieprzypisane
  miejsca, bez wybierania wyłącznie najlepszych fragmentów. Zachowane
  częściowe ramki oceniają wnętrza i wybrane różnice; ich przybliżony
  obrys nie jest dokładną prawdą granicy całej klatki.
- **Błędy podziału:** na syntezie rozdzielić nadmierne dzielenie od scalania,
  np. przez dwa składniki VI; kod oceny CREMI jawnie rozróżnia oba.
  [Źródło implementacji](https://raw.githubusercontent.com/cremi/cremi_python/master/cremi/evaluation/voi.py).
  Dodać ocenę granic z ustaloną tolerancją. Na TTMAPP oceniać tylko pary
  i wnętrza, których znaczenie da się ustalić; nie liczyć globalnego IoU
  ani traktować obszaru poza ramkami jako podłoża. Nie usuwać odmów z oceny
  tak, by odrzucenie wszystkiego dawało dobry wynik.
- **Odmowy:** zestawić błąd przy porównywalnym udziale ocenionych/
  przypisanych elementów, zamiast chwalić zero błędów przy odrzuceniu
  niemal wszystkiego. Klasyfikacja selektywna formalizuje wymianę między
  ryzykiem a odsetkiem obsłużonych przypadków. Nasze przeniesienie tej idei
  do oceny domen jest propozycją, bez gwarancji teoretycznych z klasyfikacji;
  odsetek przypisań nie oznacza powierzchni materiału. [Geifman i El-Yaniv,
  2017](https://arxiv.org/abs/1705.08500).
- **Kontynuacja:** ustalić z góry tolerancję fałszywych scaleń/podziałów,
  wymagane zachowanie kontroli zerowej/jednej domeny i minimalną korzyść
  na częściowej referencji. Wartości doprecyzować w 20/protokole jakości,
  a nie dobrać po obejrzeniu korzystnej konfiguracji. Raportować też
  stabilność trzech ziaren przewidzianych w 20 i niewielkiej zmiany skali.

24 pełne klatki i 18 częściowych referencji z dotychczasowego zestawu
wystarczą do pierwszego ograniczonego porównania obecnej serii; nie są
24 niezależnymi pomiarami. Sąsiednie klatki i nakładające się otoczenia
nie mnożą niezależnych dowodów. Ten zakres i dotychczasową rolę referencji
opisują [przygotowanie wejścia](unsupervised-input-preparation.md) oraz
[audyt referencji](partial-domain-reference-audit.md).
Dotychczasowe ramki były wielokrotnie oglądane; są oceną rozwojową obecnej
serii, nie nowym niezależnym testem. Nowe realizacje syntetyczne odłożyć
przed strojeniem. Bez niezależnej akwizycji nie deklarować przenoszenia
skuteczności na inne pomiary STM.

## Proponowane zmiany istniejących ticketów

| Element mapy | Propozycja zmiany po akceptacji kierunku |
| --- | --- |
| 20 | Dodać format relacji sąsiednich otoczeń, rozdzielone wyniki propozycji/wiarygodności/typu i zamrożony budżet porównania 2 × 2; zachować istniejący split, powtórzenia i kontrolę przecieku. |
| Krótki pilot w 21/22 | Sprawdzić nowe relacje granicy względem zamrożonych wyników 19 i najwyżej jeden nowy podział grafu; nie odkładać treningów na rzecz ponownego strojenia starych cech. |
| 21 | Mały AE jako punkt odniesienia; rVAE oceniać przez poprawność rozdzielenia typu/orientacji i wynik domen, nie samą rekonstrukcję. |
| 22 | Nadać priorytet lokalnemu SSL jako próbie cech; wpiąć w to samo porównanie podziału, bez nowych referencyjnych klas lub automatycznego uznania sąsiadów za tę samą domenę. |
| 23 | Decyzję oprzeć na korzyści końcowych propozycji oraz źródle błędu: cechy, relacje, podział lub odmowy. Wybrać najwyżej uzasadnione rozszerzenie. |
| 24–26 | Pozostawić warunkowe. Grafy nie naprawią niekompletnych centrów samą zmianą encodera; większy model nie jest automatycznym następnym krokiem. |
| 04/13 | Uściślić odbiór błędów i niepewności granic; nie zmieniać ukończenia badania w deklarację skutecznego detektora. |

Pierwszy pomiar techniczny pozostaje na RTX 5090 z 32 GB VRAM. Większą kartę
lub Colab rozważać dopiero dla zmierzonego ograniczenia konkretnego wariantu,
zgodnie z 20/23. Kluczową niewiadomą jest jakość relacji strukturalnych
i granic w tych danych, a nie sama dostępność większej pamięci.

**Najbliższy krok po przyjęciu rekomendacji:** doprecyzować i wykonać 20,
a w 21/22 zaplanować ograniczone porównanie cech, relacji i podziału.
Nie rozpoczynać kolejnej otwartej serii podobnej do 19. Do nauki nie są
potrzebne ręczne klasy domen. Nowe referencje
mogą być potrzebne później do oceny konkretnej nierozstrzygniętej granicy,
nie jako warunek rozpoczęcia obecnego porównania.
