# E7 — zamrożony protokół syntetyki → STM

2026-11-11, `ml_domain`, baza `630f29d`, środowisko `netcat`.
Użytkownik zlecił E7 i potwierdził wariant „Wykonaj próbę syntetyki → STM”.
Nie jest to wykonanie nadzorowanego E7 na ręcznych etykietach STM.
Audyt aktualności E0: te same 29 projektów i hashe, 10 ROI nieprzejrzanych,
`supervised_split_ready=false`, jedna akwizycja, bez niezależnego testu.

## Pytanie i zamrożone porównania

Czy mały uczony odczyt relacji wykorzysta informację zamrożonych AE/rVAE
lepiej niż sama geometria i historyczna reguła odległości? Jedna rodzina
klasyfikatora, bez doboru architektury lub parametrów według wyniku.

Centra molekuł, dokładne centrowanie, skala 48 px odniesienia. Sześć dawnych
enkoderów transferowych z32: AE i pełne rVAE, ziarna 20261101–03, wybrane
checkpointy issue21. rVAE zawiera treść i dotychczasowy blok kąta; nie wybierać
wariantu na podstawie E7. Bez mapy AE, wielu skal, snapu lub retreningu.

Osiem fitów tego samego modelu:

- geometria E2 (osiem cech ACF i jej osi);
- geometria + fotometria E2 (stała, średnia, odchylenie wejścia64);
- geometria + AE32, trzy osobne ziarna;
- geometria + pełne rVAE34, trzy osobne ziarna.

Geometria E2 korzysta z obrazu, nie jest samą geometrią położenia punktów.
Pełny graf centrów jest identyczny dla wszystkich wariantów. Oryginalne
współrzędne, ID i krawędzie pozostają stałe. Kodowanie pary jest symetryczne:
konkatenacja bezwzględnej różnicy i średniej wektorów obu końców. Bez absolutnych
pozycji, ID domen, ID punktów, nazw przypadków lub ziarna generatora jako cech.

## Dane i role

Nowe grupy generatora, ustalone przed generowaniem:

| Rola | Ziarna | Obrazy |
|---|---|---:|
| Train | 941101, 941102, 941103 | 27 przypadków × 3 = 81 |
| Validation | 941201, 941202, 941203 | 27 przypadków × 3 = 81 |
| STM development | 24 dotychczasowe klatki TTMAPP | 24 |

Reuse `training.controls.make_control` i całej dotychczasowej listy 27 przypadków,
bez zmiany renderera lub prawdy. Wszystkie przypadki jednego ziarna są jedną
grupą. Braki centrów, kontrast, inwersja, crop, resample, empty_gap/missing_band
nie mogą przekraczać podziału razem z ich rodzicem. Dawnych ziaren użytych
w poprzednich próbach nie przenosić do nowego treningu lub walidacji.

**Oddzielone realizacje szumu nie są niezależnymi strukturami.** Większość
geometrii i położeń granic jest wspólna między ziarnami tego generatora.
To walidacja wewnątrz znanej rodziny syntetyków, nie walidacja generalizacji
na nowe materiały, geometrie lub akwizycje. Wyniki per przypadek są konieczne,
aby globalna miara nie ukryła rozpoznawania rodzaju kontroli.

Enkodery i normalizer obrazu pochodzą ze STM: transfer train obejmował 362
okna siatki na klatkach 1/50/100, wybór checkpointu korzystał z 270 okien
validation na 150/200. Nowy syntetyczny nadzór dotyczy wyłącznie odczytu.
Nie przedstawiać całej metody jako wyuczonej tylko na syntetykach.

Na STM pokazać pełne 24 obrazy jako znaną diagnostykę rozwojową. Późne klatki
nie stanowią nowej niezależnej walidacji; niska pewność rejestracji i wspólne
fizyczne miejsca pozostają ograniczeniem. Nie dopasowywać niczego do etykiet
STM, nie tworzyć etykiet z A/B ani z nieoznaczonych fragmentów obrazu.

## Wejścia, etykiety i uczenie

Zachować oryginalny normalizer transferowy oraz most jednostek syntetycznych
`clip(0.5 + 0.4 * rendered_signal, 0, 1)`, biliniowe wejście64 i osobny native48.
Skala, siatka i margines 3 px są w pikselach odniesienia; resample2x przelicza
je na raw przez `pixel_spacing_xy`. Bez paddingu lub dodatkowej normalizacji
obrazu. Dane STM mogą korzystać z zweryfikowanych cech cache E2; nowe syntetyki
wymagają świeżej inferencji tych samych zamrożonych modeli na CPU.

Główna maska węzłów predykcji: pełne wsparcie i skończone wszystkie osiem
zestawów cech. Skończone zerowe wektory są poprawne dla klasyfikatora. Brak
cechy daje odmowę, ale nie usuwa wspieranego miejsca z mianownika jakości
domen. Historyczny adapter może odrzucić zerowy wektor; zapisać jego maskę
osobno. Pary porównywać na jawnym wspólnym wsparciu i wykazać utracone pary.
Główne porównanie uczonej geometrii z rozszerzeniami ma identyczną maskę
`learned_common`, niezależną od dostępności historycznych adapterów oraz
kalibracji do domen. Osobno `historical_matched` używa przecięcia z bazą
odległości. Degeneracja kalibracji solvera nie usuwa poprawnego wyniku pary.

Etykieta pary: `1 = ta sama dodatnia domena`, `0 = różne dodatnie domeny`.
Oba końce muszą mieć znane dodatnie instance ID i być poza niepewną granicą.
Nie oznaczać zer, tła, nieprzejrzanych lub niepewnych miejsc jako ujemnych
par. Kontrole bez domeny są osobną oceną fałszywych przypisań; klasyfikator
relacji nie jest uczony jako detektor obecności domeny. Zachować tylko
istniejące lokalne krawędzie, bez dodawania odległych par dla zwiększenia n.
Zapisać liczebności obu klas per grupa/przypadek i przy brakach zwracać brak
miary, nie tworzyć nowych etykiet. Train musi mieć obie klasy w każdej grupie.

Jeden `StandardScaler` i `LogisticRegression(penalty='l2', C=1,
solver='lbfgs', max_iter=2000, tol=1e-8)` na zestaw cech. Wszystkie parametry
stałe; bez CV, wyszukiwania C lub zmiany cech po walidacji. Wagi przykładów
odwrotnie proporcjonalne do liczby par danego ziarna generatora i klasy,
następnie znormalizowane do średniej 1. Zrównuje to klasy i grupy train;
nie tworzy niezależnych obserwacji. Te same wagi dla fitu scalera i klasyfikatora.
Brak dodatkowego `class_weight`. StandardScaler fit tylko na treningowych
etykietowanych parach. Bez PCA lub L2 wektorów w uczonym odczycie.
Warning braku zbieżności zatrzymuje próbę; nie zwiększać budżetu po wyniku.

Modele i skalery zapisać jawnie w JSON (współczynniki, średnie, skale, ID fitu),
bez pickle. Wynik `p_same` jest wynikiem klasyfikatora trenowanego z wagami,
nie zweryfikowanym prawdopodobieństwem populacyjnym.

## Od relacji do domen

Uczona niezgodność `d = 1 - p_same`. Zachować historyczną regułę: mediana
dodatnich d na wszystkich wspólnych, skończonych krawędziach TRAIN, następnie
kwantyle q25/q75 z d/mediana. Kalibracja obejmuje także krawędzie bez etykiet
relacyjnych. Mediana ma dawny floor 1e-10; zapisać również jej surową wartość.
Nie dopisywać tym krawędziom klas. Nie stosować wag klas do tej kalibracji.
Nie używać walidacji lub STM. Degeneracja jawna; nie zmieniać transformacji
na `-log(p)` ani progów na 0.5 po obejrzeniu wyniku.

FH k=4 i MWS z dotychczasowymi regułami. H_M1 oraz A_fixed_M1 z native48,
stary próg ACF i minimum 8 centrów. Nie uczyć bramki i nie dobierać minimum.
Pokazywać propozycje przed odmowami. Kwantyle mogą ograniczyć korzyść uczonego
progu 0.5, dlatego wyniki relacji trzeba oddzielić od wyników domen.

Osobna baza: historyczne cechy i adaptery odległości E2 transfer/centers
dla geometrii, fotometrii, AE i pełnego rVAE. Zastosować je na tym samym
grafie i wspólnej masce. Baza geometrii+fotometrii jest dawną fotometrią,
a bazą fusion AE/rVAE dawny opis modelu. To porównanie całej reguły odczytu,
z różnymi wejściami i źródłami dopasowania adapterów, **nie izolowany wpływ
samego klasyfikatora**. Główne parowanie dodatkowej informacji to uczona
geometria vs ten sam klasyfikator z dodatkowymi blokami.

## Ocena i zabezpieczenie przebiegu

Generator tworzy i zapisuje prawdę obu ról. Po utworzeniu danych kod fitu
i predykcji nie może czytać walidacyjnej lub STM referencji. Zamrozić wszystkie
modele, kalibracje, grafy i predykcje przed ich otwarciem do oceny.

Relacje: ROC-AUC i AP dla różnych domen, jawna częstość klasy dodatniej,
błędy przy stałym progu `p_same=0.5`, wszystkie liczniki i brakujące miary.
Osobno przypadki, grupy generatora i ziarna encoderów; nie traktować par
jako niezależnych próbek, nie deklarować istotności z ich liczby.
Nie uśredniać brakujących miar jako zera. Ziarna encoderów nie są nowymi
akwizycjami. Baza odległości nie ma z góry prawdopodobieństw lub progu 0.5.

Domeny: pokrycie znanych wnętrz, warunkowe scalenia/podziały par, fałszywe
przypisania znanych zer, cięcia krawędzi grafu i koszt odmów. Nie wyznaczać
pełnej granicy pikselowej na centrach lub na częściowych wnętrzach STM.
Sukces wymaga poprawy relacji i domen bez utraty pokrycia/pogorszenia kontroli;
mieszane wyniki pozostają kompromisem, nie wybranym detektorem.

Przeglądarka: te same oryginalne centra na obrazie; po lewej uczona geometria
albo odpowiednia historyczna odległość, po prawej wybrany uczony odczyt.
Klatki, modele/ziarna, FH/MWS, bramki, przed/po odmowach i dane klikniętego
miejsca. Widoczna rola syntetycznej walidacji i znanego STM development.
Odbiór techniczny oddzielny od ręcznego odbioru użytkownika.

CPU, jeden wątek w netcat. Budżet 30 min CPU, 8 GiB RSS, 8 GiB artefaktów;
8 fitów, najwyżej 2000 iteracji każdy. Kolejność wejść mieszana seed20261117,
kolejność fitów deterministycznie mieszana tym samym ziarnem. Protokół,
kod, wersje i wszystkie źródła mają hashe; wyniki w `.scratch/ml-e7-20261111`.
Po próbie nie uruchamiać E4/E6 lub dalszych fitów automatycznie.
