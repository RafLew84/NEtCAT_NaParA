# E7a — reguła tworzenia domen z zamrożonych relacji

2026-11-11, `ml_domain`, baza `f807216`, `netcat`.
Zlecenie użytkownika: „wykonaj e7a”. Protokół przed obliczeniem nowych domen.
Wyniki E7 są znane: to diagnostyczna kontynuacja na materiale rozwojowym,
nie nowy niezależny test. Bez uczenia, inferencji enkoderów lub refitu odczytu.

## Pytanie

Czy zastąpienie historycznej reguły skali FH/kwantyli MWS bezpośrednim
wykorzystaniem zapisanych `p_same` poprawia instancje domen? Nie zmieniamy
samych ocen relacji, więc ROC/AP par muszą pozostać niezmienione.

## Stałe elementy

Źródło `.scratch/ml-e7-20261111`, kotwica w wersjonowanym manifeście E7.
Te same 105 obrazów (81 syntetycznych validation, 24 znane STM), osiem
odczytów, wszystkie trzy ziarna AE/rVAE. Ten sam graf, identyfikatory,
centra, `common_valid`, H, pełna bramka i minimum ośmiu molekuł.
Podział grafu poprzedza odmowy; po odmowach przeliczana jest spójność.
Nie traktować wyniku odmowy jako poprawnej granicy. Nie dodawać etykiet.

## Sześć reguł, ustalonych przed wykonaniem

| ID | Reguła | Rola |
|---|---|---|
| `e7_fh` | E7: FH na `(1-p)/mediana_train`, k=4 | Baza FH |
| `e7_mws` | E7: MWS z q25/q75 train | Baza MWS |
| `fh_raw` | FH na `1-p`, k=4 | Diagnostyka wpływu skali |
| `mws_t050` | MWS z jawną granicą p=0.5 | Główne porównanie z E7 MWS |
| `mws_t025` | Ten sam MWS, p=0.25 | Wrażliwość, bez wybierania najlepszego progu |
| `mws_t075` | Ten sam MWS, p=0.75 | Wrażliwość, bez wybierania najlepszego progu |

Dla progu t: krawędź przyciągająca przy p>t, siła `(p-t)/(1-t)`;
odpychająca przy p<t, siła `(t-p)/t`; p=t neutralne z siłą zero.
Skończone p musi należeć do [0,1]; brak wartości na używanej krawędzi
zatrzymuje próbę. Nie używać logarytmów, dodatkowego pasa neutralności,
kalibracji prawdopodobieństw lub innych funkcji siły po obejrzeniu wyniku.
Zachować istniejący MWS: malejąca siła, odpychanie pierwsze przy remisie,
dalej kanoniczne ID; ograniczenia mutex i liczniki późnych konfliktów.
Nie obiecywać, że każda słaba odpychająca krawędź wymusi rozdzielenie,
jeżeli wcześniej silniejsze przyciąganie połączyło jej końce.

`p_same` pochodzi z ważonego klasyfikatora syntetycznego. Próg 0.5 jest
regułą diagnostyczną, nie zatwierdzoną pewnością fizycznej przynależności.
Zmiana mapowania MWS obejmuje znak, siłę i brak dawnego pasa neutralnego;
nie izoluje pojedynczego progu od pozostałych elementów tego mapowania.

FH raw z tym samym k zmienia efektywną regularyzację; nie przedstawiać go
jako samej zmiany jednostek. Osobna kontrola techniczna: FH na `1-p` z
`k=4*mediana_train` musi odtworzyć E7 FH. Kontrola nie jest dodatkowym
wariantem wybieranym do detekcji. Obie bazy odtworzyć bitowo na 840 wejściach.

## Ocena

Przed otwarciem referencji zamrozić wszystkie nowe predykcje i protokół.
Źródłowe pliki są weryfikowane hashami; predykcja nie interpretuje prawdy.
Osobno pełne propozycje, H_M1 i A_fixed_M1. Pokrycie znanych wnętrz,
warunkowe scalenia/podziały par, fałszywe przypisania znanych zer,
odmowy oraz cięcia lokalnych krawędzi. Mianownik pokrycia zachowuje
fizycznie wspierane miejsca pomimo braków cech. Nie liczyć pełnej granicy
pikselowej z centrów ani z częściowych wnętrz STM.

Wyniki osobno per przypadek, grupa syntetyczna, model i ziarno; agregaty
sumują liczniki tylko wewnątrz jednego odczytu. Nie testować istotności
przy traktowaniu par/klatek jako niezależnych. Brak miary nie jest zerem.
Główny kontrast `mws_t050` vs `e7_mws`; dodatkowo `fh_raw` vs `e7_fh`.
Raportować wszystkie progi, bez wyboru według znanego STM.

Poprawa bez kosztu oznacza: pokrycie nie maleje, błędne scalenia/podziały
i fałszywe przypisania nie rosną, przynajmniej jedna miara się poprawia
(tolerancja arytmetyczna 1e-12, nie margines skuteczności).
Brak odpowiedniej referencji daje ocenę częściową. Sprawdzić również
poszczególne kontrole, nie deklarować sukcesu z samego agregatu.
Niższy błąd przy utracie pokrycia pozostaje kompromisem.

Ograniczenia E7 pozostają: tylko 45 różnych par syntetycznych z dwóch
zmian orientacji, cztery lokalne różne pary STM, jedna znana akwizycja,
wspólne geometrie generatora i brak niezależnego testu. Nadzór nie uczył
obecności domeny 2D. Wyłączenie pełnej bramki nie potwierdza porządku.

## Artefakty, budżet i odbiór

`.scratch/ml-e7a-20261111`: predykcje, liczniki JSON/CSV, porównania
oraz przeglądarka. Lewy panel: E7 FH lub E7 MWS tego samego modelu;
prawy: wybrana reguła. Obrazy, oryginalne centra, kolory przynależności,
klatki/suwak, model/ziarno, reguła, bramka, przed/po odmowach i dane punktu.
Domyślnie TTMAPP259, rVAE20261101, MWS t=0.5 kontra E7 MWS, H_M1.
Źródłowy wynik relacji nie zmienia się po zmianie reguły.

CPU jeden wątek, limit 10 min CPU / 8 GiB RSS / 2 GiB artefaktów.
840 zestawów × 6 reguł = 5040 zestawów galerii; dwa warianty odmów.
Zachować próby nieudane, bez nadpisywania źródła. Testy mechaniki, replay,
audyt mianowników i kontrola Qt oddzielnie od odbioru ręcznego użytkownika.
Bez zmian produkcyjnej aplikacji, nowych etykiet, E4/E6 lub E7b.
