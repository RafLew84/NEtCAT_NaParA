# Kolejne metody rejestracji trudnych filmów STM

Stan przeglądu: **2026-11-02**. Kod odniesienia: `92601a7`, gałąź
`viewer/registration-difficult-movies`. Użytkownik potwierdził, że chodzi
o rejestrację klatek Viewera, nie wykrywanie domen molekularnych.

To przegląd źródeł, audyt istniejącego kodu i propozycja eksperymentu.
Nie wykonano nowych dopasowań, instalacji, pobierania wag ani zmian programu.
Nie zmienia statusów ticketów. Obserwacja użytkownika — Deep Matcher i RoMa
są najbliższe oczekiwanemu wynikowi, lecz niektóre klatki nadal przesuwają
się za bardzo — jest punktem wyjścia, nie liczbową walidacją.

**Aktualizacja planu — 2026-11-02:** po tym przeglądzie użytkownik zlecił
[REG-13: LightGlue + SuperPoint](issues/13-lightglue-superpoint.md) oraz
[REG-14: AKAZE](issues/14-akaze.md). Wdrożenie i manualny odbiór każdego
pozostają osobnymi etapami; aktualny stan jest w [planie](README.md).
Poniższa synteza zachowuje wyniki i ograniczenia rozpoznania, a nie raportuje
wykonanego pilotażu. [Protokół](manual-protocol.md) rozdziela go na 54 + 18 wyników.

## Rekomendacja

Najpierw porównać **LightGlue + SuperPoint** oraz **AKAZE** z obecnym
Deep outdoor i RoMa Turbo. Pierwszy wnosi inną rodzinę dopasowania punktów,
drugi jest prostą metodą bez wag z opublikowanym zastosowaniem STM.
**XFeat + LighterGlue** zachować jako kolejny kandydat. Osobno sprawdzić
kontrolowaną redukcję offsetów jasności wierszy przed istniejącym matcherem.
Jest to kolejność prób wynikająca z różnorodności metod i kosztu integracji,
a nie potwierdzony ranking jakości na MOVIE_4/MOVIE_8.

## Co już mamy i czego nie należy proponować ponownie

**Deep Matcher Viewera to LoFTR, nie SuperGlue.**
[Adapter](../../../stmviewer/deep_matcher.py) tworzy `kornia.feature.LoFTR`
i ładuje lokalne wagi. Outdoor oznacza wariant LoFTR. Bazowy Deep wybiera
ważoną grupę zgodnych wektorów i ważoną medianę w
[backendzie NanoTrack](../../../nanotrack/registration/deep_matcher.py).
RoMa, EfficientLoFTR i MatchAnything korzystają z
[translation-consensus-v2](../../../stmviewer/correspondence_consensus.py):
wyboru największej grupy, mediany, oceny konkurencyjnego przesunięcia
oraz przestrzennego poparcia. RoMa dodatkowo
[ogranicza liczbę punktów w komórkach 8×8 obu obrazów](../../../stmviewer/roma_matcher.py).
Samo dodanie mediany, RANSAC lub limitu punktów nie opisuje więc nowej funkcji.

[REG-05](local-consensus-results.md) już sprawdza lokalne fragmenty NCC wokół
startu Deep: siatka 4×4, wycinki 32 px, promień poszukiwania 16 px,
kontrast maksimum i konkurencyjne maksima. Finalnie dał wynik w **2/14**
badanych par i odmówił pełnym filmom. Nowa próba wycinków musi wskazać,
co konkretnie zmienia wobec tego doświadczenia.

Graf LS i blokowy Huber również są dostępne. W
[próbie RoMa](roma-results.md) oba pełne filmy miały łańcuch i LS, lecz
**Huber osiągnął limit 200 iteracji w obu**. Nie wolno przedstawiać tej
próby jako ukończonej poprawy po Huberze. Zgodność grafu nie rozstrzyga,
czy dopasowano strukturę próbki, czy powtarzalny artefakt.

## Dlaczego klatka może przesuwać się za bardzo

Bez wskazania aktualnych par i zapisanych XY nie można przypisać przyczyny.
Rozsądne hipotezy do rozróżnienia są następujące:

- **Inne powtórzenie motywu:** model znajduje podobną molekułę lub okres sieci,
  ale nie ten sam obiekt. Wielu zgodnych punktów nie wystarcza do rozpoznania
  takiego błędu. Niejednoznaczność korelacji na okresowej powierzchni opisują
  również autorzy [unDrift, Algorithms I–III](https://www.beilstein-journals.org/bjnano/articles/14/101).
- **Zakłócenie udające strukturę:** lokalny wzorzec `stationary-artifact`
  skłonił RoMa do około (0; −0,20) zamiast znanego (7; −5) px.
  Deep także podążył za pasem. Turbo, Fast, Base i Precise nie usunęły
  tego problemu; [wyniki](roma-results.md) nie wspierają tezy, że wystarczy
  zwiększyć preset lub liczbę punktów.
- **Tearing wewnątrz klatki:** różne części mogą wymagać różnych przesunięć.
  Jedno XY jest wtedy kompromisem, nawet przy poprawnych korespondencjach.
- **Sumowanie błędów:** [łańcuch](../../../stmviewer/registration.py)
  sumuje kolejne XY. Drobne błędy mogą przesunąć późniejszą część filmu.
  Zmiany samych molekuł dodatkowo utrudniają wybór nieruchomego odniesienia.

Próby znanych translacji ograniczają podejrzenie ogólnego błędu znaku/skali,
ale nie wykluczają błędu dotyczącego konkretnej geometrii wejścia.
Mniejsze płótno, krótszy wektor i gładsza trajektoria nie są kryteriami
poprawności. Nie proponujemy przycinania ruchu ani wymuszania jego kierunku.

## Kandydaci

### 1. LightGlue + SuperPoint; ALIKED jako późniejsza zmiana ekstraktora

LightGlue dopasowuje rzadkie punkty i deskryptory, adaptując koszt do pary.
Autorzy publikują wagi dla SuperPoint, DISK, ALIKED i SIFT.
To inny tor niż obecny LoFTR: najpierw detekcja punktów, potem ich dopasowanie.
[Publikacja](https://arxiv.org/abs/2306.13643),
[oficjalny kod i checkpointy](https://github.com/cvg/LightGlue).

Istnieje bliski przykład SPM: publikacja AFM z 2026 r. używa
SuperPoint–LightGlue na **15 kolejnych obrazach 256×256 SiO₂/Si**, wraz
z preprocessingiem i Grid-RANSAC. Ocenia m.in. inliery i lokalny NCC.
To dowód wykonalności w AFM, nie niezależny pomiar poprawności dryfu STM:
klatki jednego obszaru są zależne, a zoptymalizowane podobieństwo nie
wyznacza prawdziwego ruchu.
[Pełny artykuł, §2.1–2.2 i tabela 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC13535920/).

Hipoteza próby: lokalne punkty mogą inaczej rozkładać poparcie niż gęste
korespondencje. Nadal mogą jednak skupiać się na krawędzi pasa lub mylić
powtarzalne molekuły. Najpierw SuperPoint–LightGlue; dopiero później
ALIKED–LightGlue przy niezmienionym konsensusie.

Kod/wagi LightGlue mają Apache-2.0, ALIKED BSD-3-Clause; SuperPoint ma
[odrębne, bardziej restrykcyjne warunki](https://github.com/magicleap/SuperPointPretrainedNetwork/blob/master/LICENSE).
Potrzebne są lokalne checkpointy
obu składników i sprawdzenie zależności Torch/torchvision/Kornia/OpenCV.
Konstruktor może pobierać wagi, więc adapter Viewera musi używać wcześniej
przygotowanych plików. [Licencje i instalacja](https://github.com/cvg/LightGlue),
[kod ładowania](https://github.com/cvg/LightGlue/blob/main/lightglue/lightglue.py).

### 2. AKAZE + wzajemne dopasowanie deskryptorów

Diao i współautorzy zastosowali AKAZE, Brute-Force `crossCheck`
i grupowanie wektorów w STM; opisali utrzymanie obszaru przez 25 godzin,
również przy zmianach kontrastu. Ich rozwiązanie obejmuje sterowanie dryfem
online, którego nie przenosimy automatycznie do filmu MPP.
[APL 2023, DOI 10.1063/5.0139330, pełny PDF autorów](https://mdr.nims.go.jp/datasets/15adbe74-0767-42f4-970c-8a741fa4018f?locale=ja).

Propozycja: użyć AKAZE jako nowego dostawcy punktów dla istniejącego
konsensusu translacji. Nie wymaga wag sieci. Publiczny
[kod autorów](https://github.com/DIAOZHUO/drift_compensation_by_feature_point_matching)
ma licencję MIT i przykład dwóch obrazów. Demonstracja korzysta także
z SPMUtil, ale samo wykrywanie i dopasowanie OpenCV nie wymaga zmiany
czytników Viewera. To atrakcyjna kontrola prostszego rozwiązania,
nie dowód przewagi nad LoFTR/RoMa na naszych zakłóceniach. Powtarzalna
sieć może generować błędne odpowiedniki także przy wzajemnym dopasowaniu.

### 3. XFeat + LighterGlue — rezerwa o małym koszcie obliczeń

XFeat dostarcza konwolucyjny ekstraktor i deskryptory 64D; LighterGlue jest
wariantem matchera dla tych cech. Autorzy udostępniają wagi, inference CPU/GPU
i kod Apache-2.0. [Artykuł CVPR 2024](https://arxiv.org/abs/2404.19174),
[repozytorium i wariant LighterGlue](https://github.com/verlab/accelerated_features).

Wartość eksperymentu to odmienny ekstraktor i potencjalnie niższy koszt grafu.
Benchmarki lokalizacji kamery nie potwierdzają odporności na STM. Do Viewera
przenosimy korespondencje i jedno XY, nie homografię z demonstracji.
Dokładne zależności i lokalne ładowanie checkpointów wymagają sprawdzenia
przy implementacji; żadnego modelu tutaj nie uruchomiono.

### 4. Redukcja offsetów wierszy przed LoFTR/RoMa

SmartAlign pokazuje rzeczywiste STM oraz etap wyrównania median wysokości
wierszy przed dalszym dopasowaniem. Inspiruje to **osobny eksperyment
z wejściem pomocniczym**, nie kopiowanie całego algorytmu.
[Jones i wsp. 2015, część STM, s. 13–14](https://users.ox.ac.uk/~mrc/papers/JonesASCI15.pdf).

Porównać jeden ustalony wariant redukcji offsetów z wejściem oryginalnym
na tych samych parach LoFTR/RoMa. Końcowe XY nakładać raz na oryginały;
nie zapisywać odfiltrowanych wartości jako pomiaru. Odejmowanie median może
usunąć prawdziwą rozległą strukturę i nie naprawia geometrycznego tearingu.
[Wcześniejsza próba prostych filtrów](../registration-improvement-options.md)
nie pomogła jednej badanej parze. Nowy wariant wymaga kontroli bez pasów
i nie może być z góry opisany jako poprawa.

## Warunkowe i dalsze kierunki

**SmartAlign — deformacja zależna od linii:** ma ograniczenia `row-locked`
i `row-fitted`, a publikacja pokazuje też zagrożenia swobodnego warpowania.
To korekcja wewnątrz klatki, potrzebna dopiero po potwierdzeniu, że dobre
fragmenty wymagają różnych XY. Wymaga znajomości kierunku skanu i kontroli,
czy nie kasuje rzeczywistego ruchu oraz granic domen. Aktualny produkt jest
plug-inem DigitalMicrograph, nie zwykłą biblioteką z checkpointem.
[Artykuł](https://users.ox.ac.uk/~mrc/papers/JonesASCI15.pdf),
[oficjalny podręcznik](https://www.hremresearch.com/Eng/download/documents/SmartAlign%20Manual.pdf).

**QuantEM — preprint 2026:** rozwija korekcję afiniczną/niesztywną
ortogonalnych skanów oraz pasów względem skorygowanego odniesienia.
Demonstracje obejmują HAADF, XEDS i 4DSTEM, nie nasze dynamiczne STM.
Nie znamy orientacji skanów ani takiego odniesienia dla MOVIE_4/8.
Obrócenie gotowego obrazu nie tworzy niezależnego skanu ortogonalnego.
Kod MIT/PyTorch jest publiczny; propozycja ma sens przy odpowiedniej
akwizycji, nie jako zamiennik matchera tych samych MPP.
[Preprint, §2–3](https://arxiv.org/html/2609.30866v1),
[QuantEM](https://github.com/electronmicroscopy/quantem).

**MINIMA i GIM:** alternatywne treningi znanych architektur. MINIMA stosuje
syntetyczne modalności, GIM pseudoetykiety z filmów. Mają publiczne wagi,
ale ich warianty RoMa nie są checkpointami obecnego RoMa v2. Deklarowane
środowiska są starsze, a dane treningowe nie potwierdzają odporności na
tearing. Zachować jako rezerwę po próbach zmieniających rodzinę cech;
nie pobierać automatycznie wszystkich wariantów.
[MINIMA: publikacja](https://arxiv.org/abs/2412.19412),
[kod i wagi](https://github.com/LSXI7/MINIMA),
[GIM: publikacja](https://arxiv.org/abs/2402.11095),
[kod i warunki](https://github.com/xuelunshen/gim).

Te kierunki nie wznawiają odłożonych REG-06, REG-08d ani REG-09 i nie
przywracają masek. Ewentualna korekcja lokalna wymaga osobnej decyzji.

## Eksperyment przed kolejną implementacją

### Etap 1: porównanie czterech torów na tych samych parach

Zamrozić cztery warianty: **Deep outdoor, RoMa Turbo, AKAZE,
SuperPoint–LightGlue**. Proponowany pilotaż obejmuje **18 par × 4 = 72
wyniki par**; jest propozycją, nie wcześniej zadanym limitem użytkownika.

Wziąć 14 istniejących par z [REG-05](local-consensus-results.md):
MOVIE_4 bieżące 1→2, 31→32, 118→119, 29→30, 35→36, 44→45, 45→46,
61→62, 94→95, 95→96, 96→97 oraz MOVIE_8 1→2, 16→17, 56→57.
Dodać z góry ustalone MOVIE_4 **160→161, 250→251** oraz MOVIE_8
**25→26, 70→71**. Dodatkowe pary nie są z założenia łatwe ani niezależne.
MOVIE_4 zawsze pomija źródłowe 1/2; zapisać oba rodzaje numeracji i SHA danych.
Zachować commit kodu, SHA wag, wersje bibliotek, parametry i ziarna losowania
modelu oraz kolejności prezentacji wyników.

AKAZE, LightGlue i RoMa używają tego samego konsensusu v2. Bazowy Deep
zachowuje historyczny agregator: to uczciwe porównanie całych torów,
a nie izolowanego wpływu sieci. Opcjonalny, osobny adapter Deep→v2 pozwoli
później oddzielić te czynniki. Nie zmieniać progów osobno dla trudnych par.

### Etap 2: kontrola błędów i pełny film

Dołożyć osobne wzorce znanego XY: różne kierunki i ruch podpikselowy,
szum, nieruchomy pas, okresowość, kontrast i tearing. Przy tearingu
zdefiniować globalne XY i deformację resztkową osobno. Potem porównać
łańcuch i identyczny graf LS/Hubera na zachowanych pomiarach wybranych
wariantów; raportować odmowy i niezbieżność, bez zastępowania ich zerem
lub inną metodą. Eksperyment redukcji offsetów wierszy prowadzić osobno,
aby nie pomylić skutku preprocessingu ze zmianą matchera.

Na wzorcach mierzyć błąd wektora XY. Na prawdziwych danych, bez niezależnego
odniesienia, podawać ocenę wizualną lub rozbieżność względem jawnie oznaczonego
ręcznego odniesienia — nie „błąd prawdziwego dryfu”. Porównanie A/B ma losową
kolejność i ukryte nazwy metod, wspólny kontrast/zoom oraz te same kontury
w kilku częściach obrazu. Dopuszczać wynik nierozstrzygalny.

Raportować także odmowy, pogorszenia, duże skoki według tolerancji ustalonej
przed oceną, czas całego procesu i pamięć. Nie wybierać zwycięzcy tylko
wśród udanych dopasowań ani po liczbie punktów. Powtórzenia wykonania
mierzą zmienność obliczeń, a nie zwiększają liczby niezależnych próbek.

Oba filmy były już używane do rozwoju. Wyniki sparowane należy przedstawić
opisowo, z rozdzieleniem filmów i fragmentów; tysiące punktów/krawędzi nie
uzasadniają wąskich przedziałów ufności. Przedziały dla uogólnionej poprawy
wymagają odpowiedniej liczby niezależnych filmów i uwzględnienia ich grupowania.
Po zamrożeniu ustawień sprawdzić nowy film, wcześniej niewykorzystywany
do wyboru metody. Ręczna kontrola badawcza nie wymaga dodawania panelu REG-06.

## Strategia wyszukiwania i granice przeglądu

Przeszukano źródła 2026-11-02: publikacje autorów/arXiv, pełne teksty SPM,
oficjalne repozytoria i dokumentację. Zapytania obejmowały `STM drift AKAZE
feature matching`, `AFM SuperPoint LightGlue`, `SmartAlign STM row median`,
`2026 scanning microscopy drift correction QuantEM`, `XFeat LighterGlue`,
`MINIMA image matching` i `GIM image matching`. Sprawdzono mechanizm,
dane demonstracyjne, dostępność kodu/wag oraz ograniczenia integracji.

Pierwszeństwo otrzymały odmienne, dostępne tory korespondencji i zastosowania
SPM. Benchmarki naturalnych zdjęć, AFM i STEM opisano jako takie, bez
przenoszenia wyników liczbowych na STM. Same abstrakty nie stanowią podstawy
silnego wniosku o jakości. Pominięto segmentację/śledzenie molekuł,
ponowne proponowanie wdrożonego grafu i metody wymagające nieobecnego
sygnału akwizycji jako gotowe rozwiązanie MPP. To ukierunkowany przegląd,
nie wyczerpująca metaanaliza ani nowy benchmark.

## Narzędzia metodologiczne

Wykorzystano skille `research`, `experimental-design` 1.5 i
`scientific-critical-thinking` 1.5 do doboru źródeł, rozdzielenia faktów
od hipotez i zaprojektowania porównania. Zgodnie z zasadami użytych skilli
odnotowano: Timothy Kassis, Vinayak Agarwal, Yuhuan He, Darshil Patel,
Aubrey M. Brueckner (2026), *Scientific Agent Skills: A Library of Procedural
Knowledge for Research Agents*, [arXiv:2609.00065](https://arxiv.org/abs/2609.00065),
[DOI](https://doi.org/10.48550/arXiv.2609.00065). To źródło narzędzia
metodologicznego, nie dowód skuteczności któregokolwiek algorytmu STM.
