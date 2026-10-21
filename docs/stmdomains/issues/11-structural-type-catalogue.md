# Jak rozpoznawać typy przy obrocie, zmianie rozstawu i rzadkich wzorach?

ID: 11
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
Assignee: Codex — domains/structural-type-catalogue
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 04, 05

## Question

Jakie cechy i procedura wspólnego katalogu zachowują typ przy obrocie,
odróżniają istotny rozstaw i nie tworzą nowych typów z brzegu lub defektu?
Jak zachować rzadki wzór oraz odmówić przypisania wzoru niejednoznacznego?

Użytkownik wybrał katalog ustalany wspólnie dla całego zaznaczonego zakresu.
Nie wracamy domyślnie do katalogu zamrożonego na klatkach referencyjnych.
[Pilotaż](../method-comparison-pilot.md) zachował typ po obrocie, lecz scalił
rozstawy 16 i 20 px. Zmiana promienia o kolejną powłokę sąsiadów unieważniła
próg regularności, a FFT reagowało głównie na obwiednię sztucznego płata.

Sprawdźmy stabilny wybór sąsiedztwa, wagi cech struktury i rozstawu oraz okno
obrazu obejmujące wystarczającą liczbę okresów. Porównanie ma objąć kontrolowane
obroty, rozstawy, defekty, brzeg, ubytki oznaczeń i rzadkie wzory. Nie narzucamy
rodziny cech ani liczby typów tylko po to, by uzyskać oczekiwaną liczbę domen.

Ustalmy kryterium odrzucenia, niejednoznaczności i kandydata na nowy typ,
odrębne od brakujących danych. Oceńmy wpływ liczebności punktów/klatek na
katalog, powtórzenia oraz zmianę zakresu. Wersje katalogu wymagają jawnego
porównania znaczeń, nie tylko zgodnych numerów. Nie śledzimy konkretnych domen.

Wynik: obejrzane przypisania i pomiary na uzgodnionych referencjach, stabilność
typu wobec obrotu/rozstawu, ocena rzadkich typów i odmów oraz koszt/pamięć.
Wspólne dopasowanie katalogu i niezależna ocena poprawności to osobne czynności.

## Dependencies

- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
- [Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md)

## Work started — 2026-10-21

Na bezpośrednie polecenie użytkownika wykonujemy próbę na zaakceptowanych
częściowych referencjach 250–268 oraz kontrolach syntetycznych. Otwarte pytanie
04 nie blokuje tej lokalnej próby; nie deklarujemy pełnego odbioru metod.
Kolory ręcznych ramek pozostają etykietami porównania, nie narzuconym katalogiem
trzech typów. Katalog powstaje wspólnie dla badanego zakresu.

Porównujemy cechy struktury z orientacją wydzieloną od typu, informację
o rozstawie, wpływ skali okna i braków detekcji, rzadkie wzory oraz zmianę
zakresu katalogu. Źródła prototypu: `prototype/stmdomains-types`; kod i duże
wyniki eksperymentu nie trafią do aplikacji produkcyjnej.

Użytkownik doprecyzował znaczenie kolorów: **głównie różne orientacje tej samej
sieci**. Nie traktujemy BLACK/RED/YELLOW jako trzech prawdziwych typów.
Sprawdzamy, czy cechy oddzielające typ od kąta unikają fałszywego tworzenia
nowych typów z obrotu; realną zmianę rozstawu i geometrii oceniamy na kontrolach.

## Answer — 2026-10-21

Zakończono [próbę katalogu typów](../structural-type-catalogue-trial.md):
9 wariantów, 18 klatek TTMAPP / 54 wnętrza oraz 19 kontroli syntetycznych.
Status `resolved` oznacza wykonany eksperyment i udokumentowaną odpowiedź
na pytanie o zachowanie kandydatów. **Nie oznacza zatwierdzenia metody.**
Użytkownik doprecyzował znaczenie kolorów; nowy wynik przygotowano do jego
obejrzenia, bez deklaracji, że zaakceptował już prototyp lub jego parametry.

Momenty kątowe z wydzieloną orientacją, rozstaw i zróżnicowanie odległości
sąsiadów rozdzielają proste struktury kontrolne, zachowując typ po obrocie
oraz zmianie rozstawu o 2%. Rozszerzenie cechy opracowano na tych kontrolach,
więc nie jest to niezależna walidacja. Na TTMAPP ten wariant tworzy 34 grupy
kandydatów; zmiana zakresu zmienia 11,29% relacji wspólnego przypisania par.
Nie utożsamiamy grup z fizycznymi typami ani kolorów ramek z trzema typami.

Poszerzenie sąsiedztwa o następną powłokę, ubytki centrów i pojedynczy defekt
mogą zmienić typ albo fałszywie odrzucić porządek. FFT nie zależy od braków
centrów, ale ma błędy pomiaru okresu i odmowy zależne od okna/orientacji;
przepuszcza również szum. Wąski RED najczęściej nie mieści pełnego pomiaru.
Rzadki wzór zachowujemy jako kandydata, z jawną liczbą dostępnych próbek,
bez wymuszania rozpoznania. Nie wybrano gotowego zestawu cech i progów.

Porównano wspólny katalog całego zakresu, pierwszej połowy, odwróconej
kolejności, powtórzeń pierwszego przypadku oraz progów 0,75/1/1,25.
Porównania dotyczą relacji między tymi samymi próbkami; stabilność medoidów
oraz stanów niejednoznaczności pozostaje osobną luką. Raport zawiera
parametry, tożsamość wejścia, pomiary kosztu i zakres inspekcji.

Kolejny krok dla rozpoznawania typów: stabilny wybór lokalnego sąsiedztwa
oraz ocena wystarczalności danych przed tworzeniem grup. Te luki pozostają
jawne w [odbiorze metod](13-method-acceptance.md); obecne referencje pozwalają
kontynuować lokalne próby. [Granice niedopasowania](12-phase-boundaries.md)
są osobnym pytaniem. Zamknięcie 11 nie zalicza odbioru 13 i nie czeka na 12.

## Prototype and inspection

Źródła: **`prototype/stmdomains-types`, commit `f2608c7`** — nie scalać do aplikacji.
Lokalny podgląd:
`/home/rlew/projekty/NEtCAT-domains/.scratch/type-catalogue-trial/index.html`.
Obok pełny JSON, CSV i raporty inspekcji. Polecenie odtworzenia jest w raporcie
oraz `stmdomains/prototypes/type_catalogue_README.md` na gałęzi prototypu.

W HTML obejrzyj kolejno „Prostokąt i różnice odległości”, „Wąski RED — 251”,
„Szersze sąsiedztwo” oraz „Sam szum”. Zmień nakładkę grup na kierunek q4/q6;
orientacja pozostaje osobna od typu. Dostępny jest swobodny wybór metod i klatek.

Wykonano inspekcję geometrii 7014 pomiarów, średnic 349 grup, niezależności
81 okien od obrazu poza referencją oraz interakcji HTML w QtWebEngine.
Bez błędów JS; koszt generatora 7,10 s przed eksportem CSV / 618,43 MiB RSS.
Nie zmieniano kodu aplikacji ani nie uruchamiano jej testów.
