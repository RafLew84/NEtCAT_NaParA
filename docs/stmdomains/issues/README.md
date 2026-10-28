# Rejestr decyzji STM Domains

[Mapa decyzji etapu 1](../map.md) jest zakończona. Następny krok aplikacyjny to
[budowa i odbiór szkieletu](../implementation/README.md), nie kolejna decyzja.
Zadania wykonawcze są oddzielone od poniższego rejestru pytań.
[Etap 2: metody i zapis wyników](../map-methods-and-save.md) rozpoczyna się po
implementacji i odbiorze szkieletu. Otwarte decyzje etapu 2 nie blokują etapu 1.
Statusy i zależności przechowujemy w ticketach; indeks poniżej grupuje je według map.

Na bezpośrednie polecenie użytkownika z 2026-10-19 wcześniej podejmujemy
[definicje wyspy, typu i domeny sieci](02-order-types-and-domains.md) oraz
[pilotaż porównania metod](05-stable-types-across-frames.md). Pilotaż zakończono
wskazaniem luk; na polecenie użytkownika utworzono dalsze pytania o pokrycie,
typy, granice domen i odbiór metod. To jawne wyjątki dla wskazanych zadań,
bez deklaracji gotowego szkieletu lub zwalidowanego algorytmu.
Następnie na bezpośrednie polecenie użytkownika uzgodniono także
[definicje statystyk klatek](06-frame-statistics.md). Odbiór metod i zapis
wyników korzystają z tych definicji; sama decyzja nie implementuje statystyk.

W pierwszym etapie rozstrzygnięto również
[podgląd szkieletu](07-browsing-and-comparison.md): po reakcji na prototyp
wybrano jeden obraz i pasek miniatur. Zamknięto też
[przekazanie do implementacji i kryteria odbioru](09-implementation-handoff.md).
Wszystkie decyzje pierwszej mapy są rozstrzygnięte; trzy zadania wykonawcze
pozostają `todo`, a odbiór programu wymaga rzeczywistych danych i GUI.

Na kolejne polecenie użytkownika rozstrzygnięto
[kontrakt zapisu i eksportu](08-save-and-export.md) przed odbiorem metod:
samowystarczalny zapis z MPP, opcjonalnym wynikiem oraz CSV/PNG. Zależność
odwrócono: odbiór metod sprawdzi realizację tego kontraktu na wynikach prób.
Nie oznacza to implementacji zapisu ani odbioru metod.

2026-10-21 na bezpośrednie polecenie użytkownika wykonano
[wstępne porównanie pokrycia i skali](10-coverage-and-scale.md). Wynik omówiono,
po czym wykonano próbę na dostarczonych częściowych referencjach. Po omówieniu
wyników krok 10 ma status `resolved` jako zakończony eksperyment. Nie wybrano
metody; pełna ocena pokrycia pozostaje w zakresie odbioru metod i protokołu jakości.
Krok 10 nie zależy od kroku 11. Dotychczasowy graf zależności pozostaje bez zmian.

Następnie na polecenie użytkownika wykonano [próbę katalogu typów](11-structural-type-catalogue.md).
Krok 11 ma status `resolved` jako ukończony eksperyment. [Raport](../structural-type-catalogue-trial.md)
wykazuje poprawę prostych kontroli po dodaniu rozstawu i różnic odległości,
ale brak stabilnego katalogu TTMAPP. Użytkownik wyjaśnił znaczenie kolorów
jako głównie różnych orientacji tej samej sieci; nie zatwierdzono metody.
Dalsze luki pozostają w odbiorze 13, a granice niedopasowania w osobnym kroku 12.

Na kolejne polecenie wykonano [próbę granic niedopasowania](12-phase-boundaries.md).
Krok 12 ma status `resolved` jako zakończony eksperyment. [Raport](../phase-boundaries-trial.md)
wskazuje przydatność niedopasowania wektorów centrów na kontrolach i ograniczenia
fazy obrazu, dostępności sieci oraz interpretacji rozłączonych grafów.
Nie wybrano metody produkcyjnej ani nie policzono dokładności granic TTMAPP.
Próby 10–12 są zakończone; odbiór metod 13 i protokół jakości 04 nadal otwarte.

Po przeglądzie MolTrack i literatury STM/AFM użytkownik polecił wpisać
[kolejne próby samodzielnego znajdowania domen](#próby-samodzielnego-znajdowania-domen)
do istniejącej mapy. Następny krok badawczy to przygotowanie wspólnego
wejścia i kontroli, potem porównania kandydatów. Po przeglądzie ML dodano
przygotowanie gotowych cech i ich porównanie z klasyczną teksturą, bez
własnego treningu sieci. Analizujemy całe klatki;
ramki służą wyłącznie późniejszej ocenie. Nie zakładamy istnienia domen
ani ich liczby i nie uczymy klas z ręcznie zaznaczonych przykładów.
Nowe tickety są otwarte, próby nie zostały uruchomione.

Po dopuszczeniu treningu bez etykiet i ostatnim przeglądzie użytkownik
polecił dodać [zadania 20–26](#trening-bez-etykiet-domen). Najpierw
przygotowujemy protokół, następnie porównujemy AE/rVAE i lokalne SSL.
Decyzja po tych próbach wybierze ewentualne rozszerzenia. Gotowe modele
z kroków 18–19 zachowują niezmienione wagi jako punkt odniesienia.

## Wayfinding operations

Stan 2026-10-23: [przygotowanie 14](14-unsupervised-input-and-controls.md)
zakończone. [Raport](../unsupervised-input-preparation.md) i
[protokół wejścia/wyników](../experiment-input-protocol.md) opisują gotowy
zestaw. Następnie wykonano [pierwszą próbę 15](../local-neighborhood-domains-trial.md).
Issue 15 początkowo pozostawało `claimed`: użytkownik wybrał dalsze
rozwinięcie próby, bez przejścia do 16. Prosty opis/SOAP nie dały gotowej
metody. Następnie [zbadano kryterium powtarzalności](../recurrence-criterion-trial.md):
38 konfiguracji, 204 próbki, przypisanie w referencjach 31.0% → 62.5%,
lecz nadal scalenia i odmowy przy łączeniu zgodnych orientacyjnie składowych.
Na następne polecenie wykonano [orientację i łączenie](../orientation-and-joining-trial.md):
31 wariantów, 228 próbek. Komórka ze zgodnością ze startem poprawia braki
i część TTMAPP, lecz pomija RED/YELLOW i scala zaburzoną granicę przesunięcia.
Użytkownik polecił przejść do 16; 15 zakończono jako porównanie, bez wyboru
algorytmu produkcyjnego. [Próba SBC/MatID](../sbc-matid-domains-trial.md)
jest wykonana na 228 próbkach. Daje poprawę braków, deformacji i trudnej
granicy, ale fałszywy porządek, mała różnica orientacji i niestabilność
ziarna wykluczają przyjęcie konfiguracji. 16 jest `resolved`: użytkownik zatwierdził porównanie
i wybrał przejście do 17 — tekstury. [Próba 17](../image-texture-domains-trial.md)
jest wykonana i zatwierdzona jako porównanie: `resolved`, bez przyjęcia
metody. Wariant obrazowy jest niezależny od anotacji, ale na TTMAPP ma
0.3–5.8% przypisań i pomija RED/YELLOW. Cechy zachowano do porównań ML.

Stan 2026-10-26: [przygotowanie 18](../frozen-feature-preparation.md) jest
`resolved`. FCN–ResNet101 i DINOv2 ViT-S/14 działają z niezmienionymi
wagami; cechy siatki pozostają identyczne bez centrów i niezależne od
referencji. Gotowe cechy obejmują pilotaż 12 obrazów, bez detekcji domen.
[Porównanie 19](../frozen-feature-domains-trial.md) wykonano: FCN/DINO nie
poprawiły wyniku; 0–5.1% przypisań we wnętrzach TTMAPP i błędy kontroli.
Użytkownik wybrał dalsze omówienie/rozwinięcie, dlatego 19 pozostaje
`claimed`; nie wybrano metody do programu. Następnie wykonano
[diagnozę cech/PCA/epsilon](../feature-separation-trial.md): cechy
zachowują rozróżnienie obrotu/rozstawu na kontrolach, ale 32 warianty
nie naprawiają podziału TTMAPP. Lokalny podgląd `.scratch/feature-separation/`;
status 19 nadal `claimed`, do omówienia kolejnego wyniku.
Wykonano też [lokalny graf i przesunięcie siatki](../local-feature-graph-trial.md):
32 warianty, mniej części scaleń kosztem nadmiernych podziałów jednej sieci,
zależność od położenia siatki i utrzymane ograniczenie przypisań przez ACF.
Żaden wariant nie spełnia wszystkich warunków; `.scratch/local-feature-graph/`.
Wykonano następnie [skalę i podparcie ACF](../acf-scale-support-trial.md)
przy niezmienionych cechach/podziałach: większe okno odzyskuje fragmenty,
ale zaciera przerwy; 0/512 nowych konfiguracji detektora spełnia komplet
warunków. Następny kierunek to osobna ablacja drugiego kierunku widma,
z kontrolami rzędów/pasów/przerw. Nie rozpoczęto jej; 19 nadal `claimed`.
Przygotowanie treningu 20, odbiór 13 i jakość 04 pozostają otwarte.

Lokalny tracker Markdown znajduje się w wersjonowanym `docs/stmdomains/`, zgodnie
z instrukcjami repozytorium. Nie wymaga zewnętrznego trackera.

- **Mapa:** osobny plik z etykietą `wayfinder:map`. Domyślnie aktywna jest
  `../map.md`; jej pytania są już rozstrzygnięte i trwa przekazanie do zadań
  wykonawczych. Do zwykłego toku drugiej mapy przechodzimy po odbiorze szkieletu.
  Samo zamknięcie decyzji nie jest odbiorem programu. Dla kontynuowanego
  na polecenie użytkownika badania metod aktywny jest cykl nowych prób
  w drugiej mapie; nie wymaga odbioru aplikacji.
- **Pytanie:** jeden plik `NN-nazwa.md`. `ID` identyfikuje go w całym rejestrze,
  `Parent` wskazuje mapę, a tytuł służy do nazywania w rozmowie i linkach.
  Zachowujemy dotychczasowe ID i ścieżki również po zmianie zakresu.
- **Typ:** `Type` i odpowiadająca mu etykieta `wayfinder:<type>`; bez etykiet
  implementacyjnych. `Mode: HITL` wymaga rozmowy z użytkownikiem.
- **Status:** `open`, `claimed`, `resolved`; dodatkowo `closed` dla pytania
  usuniętego z zakresu. Zamknięcie zakresowe opisujemy pod `Scope disposition`;
  nie oznacza naukowego rozstrzygnięcia ani spełnienia zależności.
- **Frontier:** wybieramy wyłącznie dzieci aktywnej mapy z `Status: open`,
  pustym `Assignee` i wszystkimi zależnościami `resolved`. Pierwszeństwo ma
  aktualny zakres wskazany w Notes mapy, a w jego obrębie kolejność numerów
  plików. Pytanie innej mapy nie trafia do tej kolejki. W cyklu nowych prób
  pierwsze jest przygotowanie wspólnego wejścia; otwarty protokół pełnej
  jakości pozostaje osobnym pytaniem do odbioru, nie blokadą tych prób.
  Dla ticketów z sekcją `Warunek podjęcia` trzeba dodatkowo sprawdzić
  zapisany wybór w kroku 23. Niewybrane rozszerzenia 24–26 nie trafiają
  do frontier, nawet gdy wszystkie ich zależności są `resolved`.
- **Zależności:** `Blocked by` wskazuje istniejące ID, także innej mapy;
  `Dependencies` zawiera odpowiadające nazwane linki. Zmiana zależności wymaga
  aktualizacji diagramu. Otwarte pytanie nie może zależeć od zakresowo
  zamkniętego pytania; taką zależność trzeba usunąć lub zastąpić.
- **Claim:** przed pracą ustaw prowadzącego w `Assignee` i `Status: claimed`.
  Pytania przypisanego innej sesji nie podejmujemy równolegle.
- **Resolve:** dopisz datowany wynik pod `Answer`, ustaw `Status: resolved`
  i dodaj nazwany link z krótkim wynikiem do Decisions so far właściwej mapy.
  Zamknięcie zakresowe trafia do Out of scope, nie do Decisions so far.
- **Nowe pytania:** najpierw utwórz pliki, potem wpisz realne ID i zależności.
  Dopiero wtedy usuń odpowiadający obszar z Not yet specified mapy.
- **Praca:** grilling korzysta z `grilling` i `domain-modeling`, prototype
  z `prototype`, research z `wayfinder` i `research`. W sesji rozstrzygamy
  najwyżej jedno pytanie, z wyjątkiem research. Aktualizacja zakresu na polecenie
  użytkownika nie potwierdza automatycznie odpowiedzi technicznych.

Metadane do wyboru kolejnego pytania:

```bash
rg -n '^(# |Status:|Assignee:|Parent:|Blocked by:)' docs/stmdomains/issues/[0-9][0-9]-*.md
```

## Etap 1 — szkielet

| Pytanie | Typ |
| --- | --- |
| [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md) | grilling |
| [Jak przeglądać obrazy i oznaczenia w szkielecie?](07-browsing-and-comparison.md) | prototype |
| [Jak przekazać szkielet do implementacji i go odebrać?](09-implementation-handoff.md) | grilling |

## Etap 2 — po odbiorze szkieletu

| Pytanie | Typ |
| --- | --- |
| [Jak definiujemy wyspę, typ uporządkowania i domenę sieci?](02-order-types-and-domains.md) | grilling |
| [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md) | grilling |
| [Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md) | prototype |
| [Jak dokładnie liczymy ilości i udziały na każdej klatce?](06-frame-statistics.md) | grilling |
| [Co zapisujemy i eksportujemy po próbach metod?](08-save-and-export.md) | grilling |
| [Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?](10-coverage-and-scale.md) | prototype |
| [Jak rozpoznawać typy przy obrocie, zmianie rozstawu i rzadkich wzorach?](11-structural-type-catalogue.md) | prototype |
| [Jak rozdzielać domeny o tym samym typie i orientacji?](12-phase-boundaries.md) | prototype |
| [Które metody i warunki odmowy wyniku przyjmujemy po próbach?](13-method-acceptance.md) | grilling |

### Próby samodzielnego znajdowania domen

Kontynuacja badań na obecnych danych, dopuszczona przed odbiorem szkieletu.
Zadanie przygotowania nie zależy od zamknięcia pełnego protokołu jakości;
ten nadal warunkuje odbiór metod. Statusy znajdują się w ticketach.

| Pytanie/zadanie | Typ | Kolejność |
| --- | --- | --- |
| [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](14-unsupervised-input-and-controls.md) | task / AFK | Pierwszy krok; E0 |
| [Czy otoczenie zaznaczonych molekuł pozwala samodzielnie znaleźć domeny?](15-local-neighborhood-domains.md) | prototype / HITL | `resolved`: trzy próby; użytkownik polecił porównanie 16, bez przyjęcia metody, E1 |
| [Czy SBC/MatID odtwarza domeny z niepełnych centrów molekuł?](16-sbc-matid-domains.md) | prototype / HITL | `resolved`: porównanie zachowane, użytkownik wybrał przejście do 17, E2 |
| [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](17-image-texture-domains.md) | prototype / HITL | `resolved`: widmo/EWT zachowane do porównań ML, bez przyjęcia metody; E3 |
| [Jak przygotować cechy gotowych sieci bez treningu na naszych danych?](18-frozen-feature-preparation.md) | task / AFK | `resolved`: oba ekstraktory, cache, geometria i powtarzalność sprawdzone |
| [Czy gotowe cechy sieci pomagają odkrywać domeny bez przykładów?](19-frozen-feature-domains.md) | prototype / HITL | `claimed`: próba, cechy/PCA, graf/siatka, ACF, drugi kierunek oraz zgodność przesunięć/lokalny sygnał wykonane; wynik do omówienia, proponowane następne 20 |

Próby geometrii, SBC/MatID i klasycznej tekstury są niezależne. Porównanie
ML korzysta z wyniku tekstury jako punktu odniesienia, również gdy jest
negatywny. DINOv3 jest opcjonalny; nie warunkuje zakończenia prób.
Ich udokumentowane wyniki, także negatywne, zasilają istniejący
[odbiór metod](13-method-acceptance.md). Zamkniętych badań pokrycia, katalogu
typów i granic nie otwieramy ponownie. Dawny
[plan eksperymentów](../unsupervised-domain-experiments.md) prowadzi teraz
do ticketów; zakres i warunki zakończenia utrzymujemy w ich treści.

### Trening bez etykiet domen

Rozszerzenie na podstawie [ostatniego badania](../research-self-supervised-domain-learning.md).
Każda próba używa pełnych pól pomiarowych; ręczne ramki służą ocenie,
bez dostarczania klas ani liczby domen. Statusy i zależności są w ticketach.

| Pytanie/zadanie | Typ | Kolejność |
| --- | --- | --- |
| [20 — Jak przygotować odtwarzalny trening bez etykiet domen?](20-self-supervised-training-preparation.md) | task / AFK | Po 14; podział danych, augmentacje, budżet i GPU |
| [21 — Czy AE i rVAE uczą się cech przydatnych do odkrywania domen?](21-autoencoder-domains.md) | prototype / HITL | Po 17 i 20; pierwsza próba treningowa |
| [22 — Czy lokalne uczenie podobieństwa poprawia wykrywanie domen?](22-local-self-supervised-domains.md) | prototype / HITL | Po 17 i 20; niezależnie od 21 |
| [23 — Czy trening daje poprawę i które rozszerzenie warto wykonać?](23-training-comparison-and-next-step.md) | grilling / HITL | Po 19, 21 i 22; porównanie i decyzja o dalszym zakresie |
| [24 — Czy uczenie grafu otoczeń molekuł poprawia wykrywanie domen?](24-graph-self-supervised-domains.md) | prototype / HITL | Warunkowo: wybrane w 23, po wyniku 15 |
| [25 — Czy maskowane odtwarzanie obrazu uczy relacji potrzebnych do domen?](25-masked-autoencoder-domains.md) | prototype / HITL | Warunkowo: wybrane w 23 |
| [26 — Czy dalsze uczenie gotowego modelu na STM poprawia odkrywanie domen?](26-pretrained-self-supervised-adaptation.md) | prototype / HITL | Warunkowo: wybrane w 23, z zachowanym modelem odniesienia |

Przygotowanie 20 można prowadzić obok przygotowania gotowych cech 18.
Próby 21 i 22 wymagają wyniku tekstury, również negatywnego; nie muszą
czekać na gotowe modele. Ich wspólne zestawienie 23 korzysta już z 19.
Odbiór 13 czeka na 23, lecz nie na wszystkie warunkowe rodziny modeli.
Jeśli w 23 wybierzemy rozszerzenie, dodajemy je do zależności 13 i diagramu.
Brak wyboru nie oznacza wykonania lub nieskuteczności tego rozszerzenia.

Pierwsze próby planujemy na RTX 5090 32 GB VRAM / 128 GB RAM. Użycie
drugiego komputera z 96 GB VRAM lub Colab wynika z pomiaru i hipotezy
wybranej w 23. Dostępność tych zasobów nie jest warunkiem zakończenia
podstawowego porównania. Żadnego treningu nie uruchomiono przez dodanie mapy.

## Odłożone poza oba etapy

[Jak mierzyć orientację molekuły i oznaczać wynik niepewny?](03-molecular-orientation.md)
zamknięto zakresowo. Zachowano treść i materiały, bez wyboru metody.

## Zależności decyzji

Strzałki pokazują warunki wstępne pytań, nie kolejność implementacji ani status.
Zwykły tok etapu 2 wymaga odebranego szkieletu, zgodnie z mapami; opisany
wyżej cykl badań można prowadzić wcześniej na polecenie użytkownika.
Wyjątek dla zakończonego pilotażu nie zamyka referencji jakości. Ich zależność
przeniesiono do dalszych prób i odbioru metod. Na późniejsze polecenie użytkownika
kontrakt zapisu ustalono wcześniej; teraz odbiór metod zależy od tego kontraktu
i weryfikuje jego realizację.

```mermaid
flowchart TD
    subgraph phase1["Etap 1 — szkielet"]
        a["Import i geometria"]
        g["Podgląd szkieletu"]
        i["Przekazanie i kryteria odbioru szkieletu"]
    end
    subgraph phase2["Etap 2 — metody i zapis"]
        b["Definicja wysp i domen sieci"]
        d["Referencje i jakość"]
        e["Próby metod w serii"]
        f["Statystyki"]
        h["Zapis wyników"]
        j["Pokrycie i skala"]
        k["Katalog typów struktury"]
        l["Granice niedopasowania"]
        m["Odbiór metod"]
        n["Wspólne wejście i kontrole"]
        o["Otoczenie oznaczonych molekuł"]
        p["Odtwarzanie komórki SBC/MatID"]
        q["Lokalna tekstura STM"]
        r["Przygotowanie gotowych cech sieci"]
        s["Domeny z gotowych cech — porównanie ML"]
        t["20: Protokół i przygotowanie treningu"]
        u["21: AE i ciągły rVAE"]
        v["22: Lokalne SSL"]
        w["23: Porównanie treningu i wybór rozszerzeń"]
        x["24: Grafy molekuł — warunkowo"]
        y["25: Maskowany AE — warunkowo"]
        z["26: Adaptacja gotowego modelu — warunkowo"]
    end
    a --> g
    a --> i
    g --> i
    b --> d
    a --> e
    b --> e
    d --> j
    d --> k
    d --> l
    e --> j
    e --> k
    e --> l
    d --> m
    j --> m
    k --> m
    l --> m
    f --> m
    a --> f
    b --> f
    a --> h
    h --> m
    f --> h
    g --> h
    a --> n
    b --> n
    n --> o
    n --> p
    n --> q
    n --> r
    q --> s
    r --> s
    o --> m
    p --> m
    q --> m
    s --> m
    n --> t
    q --> u
    t --> u
    q --> v
    t --> v
    s --> w
    u --> w
    v --> w
    w --> m
    o --> x
    w --> x
    w --> y
    w --> z
```

Krawędzie do 24–26 pokazują warunki wstępne. Dodatkowo wymagany jest
wybór rozszerzenia w 23; dopiero wtedy dodajemy jego krawędź do odbioru 13.
