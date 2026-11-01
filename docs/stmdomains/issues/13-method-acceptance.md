# Które metody i warunki odmowy wyniku przyjmujemy po próbach?

ID: 13
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 04, 06, 08, 10, 11, 12, 15, 16, 17, 19, 23, 24, 24a, 25, 26

## Otrzymano wynik adaptacji DINOv2 — 2026-11-01

[26](26-pretrained-self-supervised-adaptation.md) wykonano, `resolved` jako
eksperyment. [Raport](../pretrained-self-supervised-trial.md): sześć fitów,
6000 kroków, brak wymaganej poprawy nad oryginalnymi wagami. Adaptacja
zmienia cechy, ale cztery główne granice mają F1 0 także przed odmowami;
nie przechodzi osobnego werdyktu reprezentacji. Końcowy transfer 0/174,
transdukcja FH 4/782, MWS 0/782. Częściowy zysk przed odmowami względem
FFT nie wykazuje wymaganej przewagi nad oryginalnym DINO. Zachowana bramka
ma znany limit, lecz nie tłumaczy wszystkich błędów przed nią.

Wynik uzupełnia odbiór, bez przyjęcia detektora. 13 i 04 nadal są otwarte;
dodatkowe dane oraz wybór dalszej pracy pozostają odłożone. Poniższe wpisy
opisują wcześniejsze decyzje.

## Otrzymano wynik maskowanego odtwarzania — 2026-11-01

Użytkownik polecił wykonać [25](25-masked-autoencoder-domains.md).
[Próbę zakończono](../masked-autoencoder-trial.md), `resolved` jako eksperyment.
Mask50 poprawia odtwarzanie zakrytych pikseli o około 59%, lecz końcowe
domeny pozostają bez poprawy: transfer 0/174, transdukcja FH 4/782 i MWS 0/782.
Cztery główne granice kontrolne mają F1 0 także przed odmowami. Częściowy
zysk względem AE na syntetykach nie spełnia całych kryteriów. Wynik uzupełnia
odbiór, bez przyjęcia detektora; 13 pozostaje otwarty. 26 nadal niewybrane,
dodatkowe dane odłożone. Poniższe wpisy opisują wcześniejsze decyzje.

## Diagnoza po 24 — 2026-11-01

Użytkownik wybrał [24a — opis otoczenia i brzeg pola](24a-graph-context-boundaries.md).
Próbę wykonano, `resolved`. [Raport 24a](../graph-context-boundary-trial.md):
121/121 centrów pojedynczej sieci trafia do jednej domeny po ujednoliceniu
brzegu okna, lecz rzeczywiste granice nadal nie spełniają kryteriów.
Są regresje i brak poprawy jitteru fazy. To usunięcie konkretnego artefaktu,
bez odbioru detektora. 25/26 pozostają niewybrane; 13 nadal otwarty.

## Dalszy wybór użytkownika — 2026-11-01

Po zakończeniu 23 użytkownik osobno polecił wykonać
[24 — uczenie grafu otoczeń](24-graph-self-supervised-domains.md).
Próbę wykonano zgodnie z [protokołem 24](../graph-self-supervised-protocol.md),
status `resolved`. [Raport](../graph-self-supervised-trial.md) nie wykazał
przewagi uczenia nad geometrią i własną inicjalizacją. Niezerowe przypisania
FH nadal scalają różne referencje; wpływ brzegu kontekstu oraz błędów oznaczeń
pozostaje istotny. To wynik do odbioru, bez przyjęcia detektora. 25/26 nadal
są niewybrane; sam odbiór 13 pozostaje otwarty.

## Question

Czy po porównaniach mamy zestaw metod, parametrów i ograniczeń, który można
włączyć do STM Domains oraz oprzeć na nim zapis wyników? Zakończenie pilotażu
wskazującego braki nie jest jeszcze takim odbiorem.

Przejrzyjmy razem wyniki pokrycia, katalogu typów i granic domen na referencjach,
w tym odmowy, niejednoznaczności, rzadkie typy i błędy scaleń/podziałów.
Czy metody są ze sobą zgodne geometrycznie i znaczeniowo? Czy wnioskowanie
o porządku jest oddzielone od jakości danych i przynależności do katalogu?

Sprawdźmy zgodność z [definicjami statystyk](06-frame-statistics.md#answer--2026-10-19):
geometrię powierzchni płatów, oba mianowniki udziału powierzchni, przypisanie
molekuł według środka bboxa, brak podwójnego liczenia oraz częściowe wyniki.
Ręczny wybór domeny w konkretnym konflikcie ma przeliczać wynik i pozostawiać
informację o korekcie; nie jest dowodem trafności automatycznej segmentacji.

Sprawdźmy również [przyjęty kontrakt zapisu](08-save-and-export.md#answer--2026-10-19):
czy adaptery metod zwracają wszystkie maski/obszary, definicje typów, stany
niepewności, geometrię konfliktów i parametry potrzebne do samowystarczalnego
odtworzenia wyniku? Zapis/odczyt przykładowych wyników powinien zachować
ich znaczenie bez uruchamiania metod i bez modeli, również po ręcznej korekcie.
Szczegółowe metadane algorytmu można uzupełnić podczas prób; nie wolno gubić
wspólnych mianowników, jednostek, wersji katalogu ani pochodzenia decyzji.

Potrzebne są też mierzalne koszty na docelowych seriach, pamięć, najdłuższy
nieprzerywalny etap i zachowanie anulowania, odtwarzalność parametrów oraz
warunki unieważnienia katalogu po zmianie zakresu. Pilotaż ośmiu klatek nie
rozstrzyga tych własności dla całego wejścia. Dobór zakresu sprawdzeń wynika
z uzgodnionego niewielkiego, wewnętrznego zastosowania. Obejmuje także koszty
samowystarczalnego zapisu i odtworzenia wyników z maskami na docelowej serii,
bez pełnej materializacji wszystkich masek przy otwarciu.

Wynik: zaakceptowany przez użytkownika zestaw z jasno określonymi warunkami
użycia/odmowy albo konkretna dalsza luka. Nie przyjmujemy metody na podstawie
samego uruchomienia programu ani dostrojenia do tych samych przykładów.
Ten odbiór weryfikuje metody i ich zgodność z wcześniej ustalonym kontraktem
zapisu, nie jest warunkiem odbioru szkieletu. Kontrakt rozstrzygnięto wcześniej
na bezpośrednie polecenie użytkownika; nie oznacza to zaliczenia tego odbioru.

## Ocena przyszłych prób treningu — 2026-10-31

[Przygotowanie 20](../self-supervised-training-preparation.md) jest wykonane:
rozdzielone transfer/transdukcja, kontrole, protokół relacji i kryteria są
gotowe, GPU/checkpoint sprawdzone. 21/21a/22 następnie wykonano; samo 20 nie
dostarcza wyniku domen ani nie zalicza odbioru. Ograniczenia rejestracji
i liczebności train przechodzą do oceny wniosków o przenoszeniu.

W ramach przyjętego 2026-10-31 planu treningu ocena 13 uwzględni
[porównanie 23](23-training-comparison-and-next-step.md): wpływ cech,
lokalnych relacji, podziału oraz odmów, według protokołu z 20.
Wymaga osobnego pokazania błędnych scaleń/podziałów i zakresu przypisań;
klaster wyglądu, wzrost liczby przypisań lub etykieta nadana przez solver
nie stanowią samodzielnie dowodu domeny. Przyjęcie planu nie zalicza
odbioru; 24–26 nie były wymagane bez wyboru konkretnego rozszerzenia.
Późniejsze polecenie wybrało 24, które dodano do zależności powyżej.

**Uzupełnienie 2026-11-01:** [zestawienie 23](../training-comparison-and-next-step.md)
nie wykazało poprawy końcowych domen przez trening i nie wybrało detektora.
Użytkownik przyjął zakończenie pilota; 23 jest `resolved`, a 24–26 w tej
decyzji pozostawiono niewybrane i warunkowe. Późniejsze polecenie tego samego
dnia wybrało 24. Dodatkowe dane nadal są odłożone.
Ograniczenie bramki nie unieważnia błędów granic przed odmowami, a brak
wygranej uczenia nie zalicza metod klasycznych. Ten odbiór pozostaje otwarty.

## Wynik próby pokrycia do uwzględnienia

Zadanie 10 zakończono jako próbę badawczą (`resolved`), bez zatwierdzenia metody.
[Raport na częściowej referencji](../coverage-partial-reference-trial.md)
wykazuje zależność od kompletności centrów i wybiórczość prostych cech obrazu.
Przed przyjęciem pomiaru pokrycia pozostają: ocena nadmiaru maski poza ramkami,
granic całych płatów oraz uzasadnione warunki odmowy. Jeżeli do odbioru potrzebna
będzie kolejna próba lub konkretne oznaczenia otoczenia, należy wskazać ten zakres.
Zamknięcie kroku 10 nie zalicza tych sprawdzeń ani niniejszego odbioru.

## Wynik próby katalogu typów do uwzględnienia

Zadanie 11 zakończono jako eksperyment (`resolved`), bez zatwierdzenia metody.
[Raport](../structural-type-catalogue-trial.md) uwzględnia doprecyzowanie,
że kolory ręczne opisują głównie różne orientacje tej samej sieci. Nie należy
optymalizować katalogu tak, aby traktował je jako trzy różne typy.

Przed przyjęciem metody pozostają: wybór lokalnej powłoki sąsiadów odporny
na defekty i brak detekcji, estymacja okresu przy małym oknie oraz warunki
odmowy na szumie bez odrzucania regularnej sieci. Trzeba ograniczyć nadmierne
dzielenie TTMAPP i sprawdzić znaczenie typów po zmianie zakresu, wraz
z reprezentantami oraz stanami niejednoznaczności. Test powtórzeń z kroku 11
obejmował tylko surowe relacje przynależności par, nie te dodatkowe własności.
Sukces rozwijanej cechy na znanych kontrolach nie jest niezależną walidacją.
Obecne referencje wystarczą do dalszych lokalnych prób; nowe oznaczenia
powinny wynikać z konkretnej potrzeby, nie z samego pozostawienia 04 otwartym.

## Wynik próby granic do uwzględnienia

Zadanie 12 zakończono jako eksperyment (`resolved`), bez zatwierdzenia metody.
[Raport granic przesunięcia](../phase-boundaries-trial.md) wskazuje kierunek:
niedopasowanie wektorów między centrami w obrębie wiarygodnej sieci i orientacji.
Działa na prostych kontrolach przesunięcia 4/8 px i nie rozcina pojedynczych
defektów. Wariant ten zależy jednak od kompletności centrów i estymaty sieci,
uzyskanej tylko w 7/54 obecnych wnętrz TTMAPP; przesunięcia 1 px nie wykrywa.

Przed przyjęciem metody trzeba oddzielić przerwę detekcji od granicy i przerwy
materiału, sprawdzić orientację przed narzuceniem wspólnej sieci oraz uzasadnić
progi i interpretację małych fragmentów. Faza obrazu daje fałszywe cięcia przy
odwróceniu kontrastu; filtrowanie długości i większe okno mogą usuwać prawdziwą
granicę. Nie wolno zaliczać rozłączenia przez brak pomiaru jako wykrytej linii.
Komponenty grafu i dokładny kontur powierzchni pozostają różnymi wynikami.

Obecne ręczne ramki dotyczą głównie orientacji i nie dają dokładnej prawdy
dla granicy przesunięcia przy tym samym kącie. Późniejsza ocena realnego błędu
potrzebuje wskazanego przykładu takiej linii z tolerancją, nie ogólnego żądania
pełnych anotacji wszystkich klatek. Obecny zbiór nadal służy lokalnym próbom.
Zamknięcie badań 10–12 nie zalicza odbioru 13 ani protokołu jakości 04.

## Kierunek po przeglądzie MolTrack — 2026-10-21

Użytkownik potrzebuje ogólnego znajdowania domen, nie tylko wariantów znanej
sieci. [Audyt kodu MolTrack](../moltrack-method-audit.md) opisuje ograniczenia
M3/M6, prototypów A/B/C, zależności tekstury od wcześniejszych domen i dwóch
różnych definicji powierzchni. MolTrack służy jako porównanie, nie wybrana
metoda. Propozycja następnej próby obejmuje lokalne wzory obrazu w kilku
skalach, katalog wspólny dla zakresu i osobną orientację. Trzeba sprawdzić
odporność na brak detekcji; całkowite uniezależnienie od oznaczeń nie jest
zatwierdzonym wymaganiem. Odbiór pozostaje otwarty.

[Dalszy przegląd źródeł](../research-domain-discovery-and-object-clustering.md)
obejmuje także dowolne oznaczone obiekty. Kandydaci do próby: cechy lokalnego
otoczenia i grupowanie z kontrolą przestrzennej spójności, SBC/MatID oraz
tekstura obrazu. Klastry gęstości, klasy podobieństwa, konkretne domeny
i powierzchnie płatów pozostają odrębnymi wynikami. Dostępność biblioteki lub
wynik publikacji na innych danych nie oznacza zaliczenia odbioru.

## Samodzielne znajdowanie domen — doprecyzowanie 2026-10-21

Użytkownik potwierdził użycie dostarczonych oznaczeń molekuł jako wejścia,
bez narzucania istnienia domen i treningu na wybranych przykładach domen.
[Przegląd STM/AFM](../research-stm-afm-unsupervised-domain-discovery.md)
rozróżnia metody bez ręcznych etykiet od metod wymagających liczby grup.
Nie potwierdził gotowego rozwiązania całego zakresu.

[Następne eksperymenty](../unsupervised-domain-experiments.md) mają działać
na pełnym polu klatek, bez dostępu do masek referencyjnych podczas analizy.
Ramki służą późniejszej, częściowej ocenie, a ich brak nie oznacza tła.
Wymagane są kontrole zero/jedna/wiele domen oraz osobna ocena porządku:
stabilna grupa podobnych cech sama nie dowodzi istnienia domeny sieci.
Plan rozpisano na osobne pytania o otoczenie molekuł, SBC/MatID, klasyczną
teksturę obrazu i gotowe cechy sieci bez własnego treningu, poprzedzone
przygotowaniem wspólnego wejścia. Próby nie zostały jeszcze uruchomione.
Odbiór czeka na ich wyniki, a wcześniejsze ograniczenia
powierzchni i granic nadal obowiązują.

Porównanie końcowe ma zestawić te kierunki na wspólnym wejściu i kontrolach:
zdolność do odmowy, zachowanie jednej poprawnej domeny, rozdzielenie typu
od orientacji, scalenia/podziały, braki centrów, stabilność katalogu i koszt.
Dokumentujemy również odrzuconych kandydatów; negatywny wynik zakończonej
próby nie oznacza, że trzeba przyjąć tę metodę lub badać ją bez końca.
Wynik odbioru to uzasadniony wybór metody/połączenia metod albo konkretna
dalsza luka. Ostateczne miary jakości i potrzeby dodatkowych referencji
pozostają związane z protokołem jakości, nie z samą atrakcyjnością nakładek.

## Wynik ML do uwzględnienia

[Porównanie gotowych cech sieci i dalszą diagnostykę](19-frozen-feature-domains.md)
zakończono na polecenie użytkownika 2026-10-31 (`resolved`). Badane konfiguracje
FCN/DINO nie dały kompletnej metody domen TTMAPP; zachowano użyteczne wyniki
cząstkowe i prototypy jako punkty odniesienia. Nie zatwierdzono detektora
ani nie rozstrzygnięto nieskuteczności wszystkich zastosowań tych modeli.
Odbiór 13 pozostaje otwarty i uwzględni ten zakończony wynik obok kolejnych
prób przewidzianych w mapie.

Samo przygotowanie wag i ekstrakcji nie wystarcza do odbioru. Uwzględnić
odmowy, wpływ rozdzielczości i przygotowania obrazu, rozstaw/orientację, granice,
stabilność wspólnego katalogu oraz czas i pamięć. Rozróżniać wynik negatywny
od braku uruchomienia konkretnego modelu; nieobecność opcjonalnego DINOv3
nie blokuje odbioru pozostałych kandydatów.

Jeśli wybór obejmie sieć, zapisać jej wariant, źródło i hash wag, wybrane
warstwy oraz przygotowanie wejścia. Odtworzenie zapisanego wyniku nadal
nie wymaga obecności modelu ani ponownego przeliczania. Odbiór może
odrzucić wszystkie gotowe cechy sieci; nie wymaga wyboru metody ML.

## Wynik treningu bez etykiet do uwzględnienia

[Zestawienie pierwszych prób treningowych](23-training-comparison-and-next-step.md)
porównało AE/rVAE i lokalne SSL z teksturą oraz historycznymi wynikami
zamrożonych modeli. W 23 użytkownik zakończył pilot bez wyboru detektora.
Odbiór uwzględnia ten negatywny wynik; nie wymaga wybrania metody
uczonej. Rozdzielić poprawę na obecnej serii od przenoszenia na niewidziane
dane i sprawdzić protokół podziału, pochodzenie wag, wybór checkpointu,
stabilność, koszty oraz brak uczenia z ręcznych ramek.

Po decyzji 23 z 2026-11-01 grafy, maskowany autoenkoder i adaptacja modelu
pozostały niewybrane i warunkowe. Późniejsze polecenie użytkownika wybrało
grafy (24), a następnie 24a, 25 i 26. Wszystkie te próby wykonano; ich ID,
nazwane linki i krawędzie diagramu dodano do zależności, a wyniki opisano
powyżej. Odbiór nadal jest otwarty, bez przyjętego detektora. Nie wracamy
do treningu bez końca, jeśli próby nie dają uzasadnionej korzyści.

Przyjęty wynik ma zachować manifest treningu i identyfikację checkpointu,
lecz samo oglądanie zapisu nadal nie wymaga modelu ani przeliczania.
Osobno sprawdzić zapis wyniku i możliwość odtworzenia eksperymentu.

## Dependencies

- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
- [Jak dokładnie liczymy ilości i udziały na każdej klatce?](06-frame-statistics.md)
- [Co zapisujemy i eksportujemy po próbach metod?](08-save-and-export.md)
- [Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?](10-coverage-and-scale.md)
- [Jak rozpoznawać typy przy obrocie, zmianie rozstawu i rzadkich wzorach?](11-structural-type-catalogue.md)
- [Jak rozdzielać domeny o tym samym typie i orientacji?](12-phase-boundaries.md)
- [Czy otoczenie zaznaczonych molekuł pozwala samodzielnie znaleźć domeny?](15-local-neighborhood-domains.md)
- [Czy SBC/MatID odtwarza domeny z niepełnych centrów molekuł?](16-sbc-matid-domains.md)
- [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](17-image-texture-domains.md)
- [Czy gotowe cechy sieci pomagają odkrywać domeny bez przykładów?](19-frozen-feature-domains.md)
- [Czy trening daje poprawę i które rozszerzenie warto wykonać?](23-training-comparison-and-next-step.md)
- [Czy uczenie grafu otoczeń molekuł poprawia wykrywanie domen?](24-graph-self-supervised-domains.md)
- [Opis otoczenia i brzeg pola — 24a](24a-graph-context-boundaries.md)
- [Czy maskowane odtwarzanie obrazu uczy relacji potrzebnych do domen?](25-masked-autoencoder-domains.md)


## Wynik tekstury 17 do uwzględnienia — 2026-10-23

Użytkownik zakończył [próbę 17](../image-texture-domains-trial.md) jako
porównanie, bez przyjęcia konfiguracji. Lokalna tekstura działa bez
anotacji, lecz na TTMAPP wybrane warianty mają 0.3–5.8% przypisań i brak
RED/YELLOW. EWT tworzy przed bramką jedną grupę całego zakresu; końcowe
fragmenty wynikają głównie z odmów i łączności. Niskie błędy przy niemal
całkowitej odmowie nie mogą kwalifikować metody.

W dalszej ocenie kontrolować jakość cech oddzielnie od bramki porządku,
podziały pojedynczej sieci obok jej przypisania, małe różnice orientacji
na odłożonych próbach oraz zakres banku/katalogu przed odmowami. Granica
przesunięcia z błędem centrów nie sprawdza odporności na pogorszenie obrazu,
gdy generator zmienia tylko oznaczenia. Odbiór 13 nadal pozostaje otwarty.

- [Czy dalsze uczenie gotowego modelu na STM poprawia odkrywanie domen?](26-pretrained-self-supervised-adaptation.md)
