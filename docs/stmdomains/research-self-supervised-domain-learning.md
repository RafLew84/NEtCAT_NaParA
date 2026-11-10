# Uczenie bez etykiet do odkrywania domen STM

Data przeglądu: 2026-10-21. Pytanie: jakie dodatkowe metody warto sprawdzić,
skoro dostępny jest RTX 5090 z 32 GB VRAM i użytkownik dopuszcza trening,
lecz nadal nie chce dostarczać przykładów domen ani narzucać ich liczby?

To przegląd źródeł i propozycja eksperymentów. Nie trenowano modeli,
nie pobierano wag ani nie oceniano skuteczności nowych metod na TTMAPP.
Rozszerza [wcześniejszy przegląd bez własnego treningu](research-training-free-ml-domain-discovery.md).

Na kolejne polecenie użytkownika wnioski rozwinięto w
[tickety 20–26](issues/README.md#trening-bez-etykiet-domen): dwie pierwsze
próby i decyzję o warunkowych rozszerzeniach. Aktualne zależności oraz
warunki zakończenia znajdują się w ticketach; ta notatka zachowuje
uzasadnienie badawcze i nie stanowi raportu wykonania eksperymentów.

## Wniosek

**Tak: warto dopuścić uczenie na nieoznaczonych wycinkach naszych obrazów.**
Najbardziej uzasadnione pierwsze porównanie to mały autoenkoder/rVAE oraz
sieć uczona lokalnego podobieństwa metodą self-supervised. Uczenie grafowe
otoczeń zaznaczonych molekuł jest trzecim, odrębnym kierunkiem. Poniższa
kolejność jest rekomendacją dla tego projektu, nie rankingiem skuteczności
wykazanej na naszych danych.

| Kierunek | Czego uczy się model bez etykiet domen | Rola w pierwszym porównaniu |
|---|---|---|
| Mały AE/VAE i ciągły rVAE | Odtwarzać lokalne obrazy z krótkiego opisu; w rVAE oddzielać obrót od treści | Pierwsza próba; precedensy w mikroskopii sondowej opisano niżej |
| Lokalne SSL, np. adaptacja VICRegL | Nadawać zgodne cechy odpowiadającym sobie fragmentom różnych wersji obrazu | Druga próba; uczenie reprezentacji bez odtwarzania wszystkich pikseli |
| Grafowe SSL, inspirowane GraphMAE | Odtwarzać ukryte cechy węzłów z ich otoczenia | Trzeci kierunek, wykorzystujący gotowe oznaczenia molekuł |
| Mały autoenkoder maskowany / MAE | Przewidywać zakryte części wejścia | Rozszerzenie próby obrazowej, jeśli prostsze reprezentacje nie wystarczą |

Każda z tych metod wytwarza przede wszystkim **reprezentację danych**.
Następnie nadal potrzeba grupowania, oceny uporządkowania i połączenia
przestrzennego. Nie znaleziono w przejrzanych źródłach zwalidowanego,
uniwersalnego rozwiązania, które bez dodatkowych założeń wyznacza dowolne
domeny molekularne STM zgodne z naszym kontraktem. Istnieją natomiast
konkretne składniki i bezpośrednie precedensy, od których można zacząć.

## Co zmienia zgoda na trening

Brak ręcznych etykiet nie oznacza braku uczenia. W autoenkoderze sygnałem
uczącym jest obraz, który model ma odtworzyć; w uczeniu maskowanym — jego
zakryta część; w lokalnym SSL — zgodność reprezentacji znanych przekształceń
tego samego fragmentu. To inne zadanie niż uczenie klasyfikatora na ramkach
BLACK/RED/YELLOW. Przykłady treningu VAE bez etykiet udostępnia
[AtomAI](https://github.com/pycroscopy/atomai#variational-autoencoders-vae),
a lokalnego SSL — [VICRegL](https://arxiv.org/abs/2210.01571).

W naszym proponowanym protokole oznaczenia molekuł mogą określać centra
otoczeń albo węzły grafu. Nie podają przynależności do domen. Równoległy
wariant siatki obrazu pozwala sprawdzić zależność od niekompletnych detekcji.
Kolorowe ramki nadal służą wyłącznie ocenie już zapisanego wyniku.
Nie stają się danymi treningowymi, wyborem obszaru analizy ani źródłem
liczby klas. Obowiązują [definicje domen](issues/02-order-types-and-domains.md)
i [wspólne kontrole](issues/14-unsupervised-input-and-controls.md).

## 1. AE, VAE i rVAE: najsilniejszy związek z naszym pytaniem

Mały autoenkoder konwolucyjny jest użytecznym punktem odniesienia: kompresuje
otoczenie obejmujące kilka molekuł, a dekoder próbuje je odtworzyć. Wersja
VAE opisuje rozkład zmiennych ukrytych. rVAE dodatkowo wydziela obrót
i opcjonalne przesunięcie, pozostawiając pozostałe zmienne do opisu treści.
Gotowe implementacje z treningiem są w [AtomAI](https://github.com/pycroscopy/atomai)
i [pyroVED](https://github.com/ziatdinovmax/pyroVED); oba repozytoria udostępniają
kod na licencji MIT. Dostępność kodu nie potwierdza jeszcze zgodności
z lokalnym środowiskiem ani jakości naszych wyników.

**Bezpośredni precedens STM:** Ziatdinov i Kalinin badali grafen, wykorzystując
j-trVAE uczony bez etykiet na transformatach Fouriera lokalnych wycinków
pobranych regularną siatką. Otrzymali rozdzielenie czystej sieci, defektów
i wzorów interferencyjnych, a następnie pokazali zastosowanie modelu do
drugiego obszaru przy tych samych warunkach pomiarowych. To preprint z 2021 r.,
dotyczący struktury atomowej i interferencji, nie walidacja domen molekularnych.
Wariant ma jednak zadaną część dyskretną reprezentacji; w przykładzie STM
występują trzy składowe. Nie należy przedstawiać go jako automatycznego
wyboru liczby domen. [Oryginalna praca, rys. 6–7](https://arxiv.org/pdf/2104.10180).

**PFM:** rVAE zastosowano do sekwencji obrazów przełączania domen
ferroelektrycznych. Zmienne ukryte opisywały obecność i geometrię ścian,
a wynik zależał od rozmiaru okna. Jest to rzeczywista demonstracja uczenia
bez etykiet w mikroskopii sondowej, ale domena polaryzacji PFM nie jest
domeną sieci molekularnej STM.
[Praca Kalinina i współautorów](https://arxiv.org/pdf/2007.06194).

**Nasza adaptacja:** porównać zwykły AE/VAE z rVAE o ciągłych zmiennych,
a liczbę grup ustalać osobno z danych. Wymiar wektora cech pozostaje
parametrem modelu, lecz nie jest liczbą domen. Kontrola zwykłym AE pokaże,
czy wydzielanie obrotu daje rzeczywistą korzyść.

Trzeba zachować kąt jako osobny wynik. Usunięcie go z całego potoku
mogłoby połączyć obszary tego samego typu o różnych orientacjach. Z kolei
kąt odtworzonego fragmentu nie staje się automatycznie poprawnym kątem
sieci: może opisywać dominujący brzeg, pojedynczy obiekt lub pas skanowania.
Sprawdzamy go na kontrolach, również przy symetrii dającej kilka równoważnych
kierunków. Tak samo nie należy usuwać informacji o rozstawie przez
niezmienniczość względem skali.

Wariant FFT jest wart porównania z obrazem, ale sam moduł widma nie zachowuje
pełnej informacji o fazie przestrzennej. Reprezentacja niewrażliwa na
przesunięcie może pomagać porównać typy i jednocześnie ukrywać granicę
niedopasowania. Dlatego granice weryfikujemy również w obrazie albo
w geometrii sąsiednich oznaczeń. To ograniczenie naszej adaptacji,
nie dowód nieskuteczności źródłowego modelu.

## 2. Lokalne uczenie self-supervised

VICRegL uczy równocześnie cech globalnych i lokalnych z dwóch przekształconych
wersji obrazu. Lokalna zgodność wykorzystuje znane przekształcenia położenia
lub podobieństwo cech. Metoda była oceniana na zadaniach klasyfikacji
i przenoszenia reprezentacji do segmentacji; nie jest publikacją o STM.
[Praca NeurIPS 2022](https://arxiv.org/abs/2210.01571),
[kod autorów](https://github.com/facebookresearch/VICRegL).

Proponujemy mały encoder konwolucyjny uczony lokalnej zgodności inspirowanej
VICRegL. Byłaby to własna adaptacja, nie odtworzenie dużego treningu
ImageNet. Model ma porównywać otoczenia, nie nadawać całej klatce jedną
etykietę. Można zacząć od dwóch umiarkowanie zmienionych wersji tego samego
wycinka: znanego szumu, jasności lub niewielkiego przesunięcia, z zachowanym
powiązaniem położeń.

Dobór przekształceń jest częścią hipotezy naukowej. Dowolne skalowanie
może nauczyć ignorowania rozstawu, a wymuszanie identycznego opisu po
obrocie — ignorowania orientacji. Samo podobieństwo sąsiednich wycinków
nie uzasadnia traktowania ich jako tej samej domeny, bo mogą leżeć po
dwóch stronach granicy. Na początek nie wymuszamy też zgodności tej samej
pozycji między kolejnymi klatkami: materiał może rzeczywiście się zmienić.

Warto odróżniać tę rodzinę od kontrastowego SimCLR, które korzysta
z par negatywnych; VICReg zapobiega degeneracji reprezentacji za pomocą
składników wariancji i kowariancji.
[SimCLR](https://arxiv.org/abs/2002.05709),
[VICReg](https://arxiv.org/abs/2105.04906).
Dla powtarzalnych sieci traktowanie innych, bardzo podobnych otoczeń
jako obowiązkowo różnych może być niepożądane. Dlatego lokalny wariant
bez takich par jest naszym pierwszym kandydatem, a nie przesądzonym
zwycięzcą nad metodami kontrastowymi.

## 3. Uczenie grafowe oznaczonych elementów

Graf może reprezentować molekuły jako węzły i lokalne sąsiedztwo jako
krawędzie. To graf ułożenia molekuł na powierzchni, nie graf atomów
i wiązań wewnątrz pojedynczej molekuły. Może korzystać z położeń,
odległości, kierunków i ewentualnie cech obrazu przy centrach.

GraphMAE uczy się przez maskowanie i odtwarzanie **cech węzłów**, a nie
przez samą rekonstrukcję macierzy sąsiedztwa. Autorzy oceniali metodę
na zadaniach grafowych, w tym klasyfikacji i przewidywania właściwości
molekularnych; nie wykazali odkrywania domen w obrazach STM.
[Publikacja KDD 2022](https://arxiv.org/abs/2205.10803),
[kod autorów](https://github.com/THUDM/GraphMAE).

Nasza adaptacja wymagałaby geometrycznych cech i dobrze określonego
zadania ich odtwarzania. Identyczny wektor „molekuła” przy każdym węźle
daje zbyt łatwe, mało informacyjne zadanie maskowania. Parametry grafu
muszą zachować rzeczywisty rozstaw i kierunki; nie zakładamy sześciu
sąsiadów ani znanej symetrii sieci. Normalizacja cech i oryginalny błąd
kosinusowy GraphMAE wymagają szczególnej kontroli: sama zgodność kierunku
wektora nie wymusza zachowania bezwzględnego rozstawu. Potrzebny może być
osobny kanał skali i inny składnik funkcji straty. Sama gęstość połączeń
nie dowodzi uporządkowania.

Ten kierunek jest atrakcyjny, gdy kontrast obrazu mocno się zmienia,
a środki oznaczeń pozostają wiarygodne. Jest jednocześnie zależny od
brakujących i błędnych detekcji. Porównanie z klasyczną geometrią
z [kroku 15](issues/15-local-neighborhood-domains.md) ma wykazać, czy uczenie
daje coś ponad sam opis sąsiedztwa. Wariant obrazowy pozostaje potrzebny
tam, gdzie lista centrów jest niekompletna.

## 4. Maskowane obrazy i dalsze możliwości

MAE uczy encoder na widocznej części obrazu, a dekoder odtwarza zakryte
fragmenty. Nie wymaga etykiet klas. Oryginalna praca dotyczy ogólnych
reprezentacji obrazów; instrukcja dużego eksperymentu ImageNet używa wielu
GPU. To opis ich konfiguracji, nie minimalne wymaganie każdego autoenkodera
maskowanego. [Praca CVPR 2022](https://arxiv.org/abs/2111.06377),
[instrukcja autorów](https://github.com/facebookresearch/mae/blob/main/PRETRAIN.md).

U nas rozsądnym rozszerzeniem jest mały encoder z maskowaniem obejmującym
więcej niż pojedyncze piksele. Sprawdzamy, czy nauczył się relacji pomiędzy
molekułami, czy tylko interpolacji jasności. Dobra rekonstrukcja i mały
błąd nie są kryterium rozpoznania domen. Dekoder nie zastępuje danych
pomiarowych, zwłaszcza gdy odtwarza nieobserwowany szczegół.

Możliwa jest również dalsza adaptacja wcześniej wytrenowanego encodera
przez zadanie bez etykiet. Przykładem jest samodestylacja DINO lub
przewidywanie reprezentacji zakrytych fragmentów w iBOT. Ich źródłowe
wyniki dotyczą ogólnych obrazów; przeniesienie treningu na STM jest naszą
propozycją. [DINO](https://arxiv.org/abs/2104.14294),
[iBOT](https://arxiv.org/abs/2111.07832).
Taka adaptacja wymaga osobnego wariantu eksperymentu i porównania
z niezmienionym modelem z [kroków 18–19](issues/19-frozen-feature-domains.md).
Nie zaczynamy od trenowania dużego modelu podstawowego od zera.

Modele ekwiwariantne względem obrotu są kolejnym sposobem zachowania
informacji o orientacji: cechy zmieniają się przewidywalnie przy obrocie,
zamiast wszystkie pozostawać identyczne. Jest to konstrukcja reprezentacji,
którą można połączyć z uczeniem bez etykiet, a nie samodzielny detektor
domen. [E(2)-steerable CNNs, NeurIPS 2019](https://arxiv.org/abs/1911.08251).
Rozważałbym je dopiero, jeśli porównanie rVAE i zwykłego encodera ujawni
konkretny problem rozdzielania typu od orientacji.

## Sprzęt i wykonalność

W tej sesji odczyt `nvidia-smi` potwierdził NVIDIA GeForce RTX 5090,
32607 MiB pamięci i sterownik 595.91.07; `/proc/meminfo` podał
129498124 kB pamięci systemowej, zgodnie z deklarowaną klasą 128 GB RAM.
Metadane środowiska `netcat` wskazują Python 3.12.12, torch 2.9.1+cu128
i torchvision 0.24.1+cu128. Nie wykonano testu obliczeń tensora na GPU,
pomiaru szybkości treningu ani próby zaalokowania docelowego modelu.

Nasza ocena techniczna: małe AE/rVAE, konwolucyjne lokalne SSL i lokalne
grafy są rozsądnymi kandydatami na pojedynczą kartę z 32 GB VRAM.
Dokładny batch, rozmiar okna i czas ustali dopiero krótki pomiar.
RAM pomaga przygotować dane, lecz nie zastępuje VRAM. Nie wynika z tego
gwarancja zmieszczenia dowolnego transformera ani potrzeba użycia
największego modelu.

PyTorch wprowadził obsługę Blackwell w wydaniu 2.7 z CUDA 12.8;
lokalna wersja jest nowsza, więc nie zakładamy potrzeby aktualizacji.
Zgodność konkretnego treningu trzeba jednak sprawdzić krótką próbą.
[Informacja o obsłudze Blackwell](https://pytorch.org/blog/pytorch-2-7/).
Nie należy kopiować starych zależności notebooka bez sprawdzenia ani
zmieniać wspólnych zależności aplikacji na potrzeby eksperymentu.

Użytkownik dodatkowo deklaruje dostęp do drugiego komputera z Blackwell
Max-Q i 96 GB VRAM; dokładnego modelu i środowiska nie weryfikowano.
To rezerwa dla eksperymentu, w którym pomiar pokaże ograniczenie pamięci
istotne dla jakości, np. potrzeby większego kontekstu albo batcha.
Pierwsze próby warto przeprowadzić na 5090; większa karta nie zapewni
większej różnorodności danych ani poprawności interpretacji.

Colab może być kolejnym zasobem po obiecujących wynikach. Typ GPU,
dostępność i limity sesji są zmienne, również dla płatnych wariantów;
nie zakładamy konkretnej pojemności VRAM. Ewentualny eksperyment powinien
zapisywać stan treningu i manifest poza tymczasową maszyną, aby dało się
go wznowić. [Oficjalne FAQ Colab](https://research.google.com/colaboratory/faq.html).
Ten przegląd nie obejmuje uruchamiania zdalnych zasobów ani zakupu usługi.

## Jak wykonać porównanie bez wymuszania domen

Proponowany protokół rozszerza istniejący [krok 14](issues/14-unsupervised-input-and-controls.md):

1. **Ustalić wejście.** Surowe MPP, maska rzeczywistego pomiaru, pozycje
   oznaczeń i jawny zakres klatek. Bez gamma podglądu i paddingu.
   Wycinki pochodzą z całego pola, nie z ręcznych ramek. Kilka skal okna
   pozwala odróżnić kształt obiektu od powtarzalnego układu jego otoczenia.
2. **Rozdzielić dwa pytania.** Można uczyć reprezentację na całym aktualnie
   analizowanym zbiorze i pytać, czy porządkuje tę serię — to próba
   transdukcyjna. Osobna próba uczy na części danych, zamraża model
   i sprawdza przeniesienie na niewidziane dane. Pierwszego wyniku
   nie przedstawiamy jako odpowiedzi na drugie pytanie.
3. **Zapobiec przeciekowi przy próbie przenoszenia.** Podział ustalamy
   przed pobieraniem nakładających się okien. Stosujemy oddzielone bloki
   czasu/przestrzeni i bufor większy od wsparcia cechy. Sąsiednie klatki
   nadal mogą pokazywać tę samą powierzchnię; nawet poprawny podział
   jednej serii nie dowodzi generalizacji na inną akwizycję.
4. **Zachować wspólny etap interpretacji.** Ciągłe cechy trafiają do
   grupowania bez zadanej liczby grup, np. HDBSCAN z dopuszczeniem jednej
   grupy, następnie do oceny porządku i łączności. Zero rozpoznanych domen,
   jedna i wiele pozostają prawidłowymi możliwościami. Punkt odrzucony
   przez grupowanie nie oznacza automatycznie fizycznego nieporządku.
5. **Porównywać odkrywanie, nie sam trening.** Obok błędu uczenia zapisujemy
   wyniki kontroli rozstawu, orientacji, granicy przesunięcia, szumu,
   pasów skanowania, defektów i brakujących centrów. Sprawdzamy kilka
   inicjalizacji i zakresów danych. Stabilność klastra jest potrzebnym
   sprawdzeniem, ale sama nie stanowi dowodu istnienia domeny.
6. **Oddzielić wybór od oceny.** Przed odsłonięciem referencji zapisujemy
   parametry, wersję modelu i wynik. Dotychczasowe ramki były już używane
   w pilotażach; pozostają użyteczną oceną częściową, nie niezależnym
   testem całej powierzchni. Brak nowych oznaczeń nie blokuje pierwszej
   próby; ich potrzeba ma wynikać z konkretnej niepewności.

Warianty muszą mieć porównywalny budżet strojenia i jawny koszt. Nie
wybieramy modelu wyłącznie po atrakcyjnym wykresie dwóch zmiennych ukrytych.
Jeżeli sieć rozdziela przede wszystkim jasność lub numer klatki, raportujemy
to jako brak przydatnej reprezentacji, nawet przy bardzo dobrej rekonstrukcji.

## Zalecana kolejność

Najpierw przygotować wspólne dane i kontrole oraz zachować klasyczne
i zamrożone modele jako punkty odniesienia. Następnie przeprowadzić
**jedną próbę AE/VAE–rVAE** i **jedną próbę lokalnego SSL**. Dopiero ich
wyniki powinny zdecydować, czy warto rozwijać maskowanie obrazu,
ekwiwariantny encoder lub uczenie grafowe. Grafy można awansować do
pierwszej serii, jeśli wcześniejsza próba geometrii potwierdzi jakość centrów.

Zgoda na trening usuwa poprzednie ograniczenie badawcze; nie zmienia
wymagania odkrywania bez ręcznych klas. Wynik wszystkich kandydatów nadal
wymaga [odbioru metod](issues/13-method-acceptance.md). Ta notatka nie
zamyka istniejących zadań ani nie ogłasza wybranej metody produkcyjnej.
