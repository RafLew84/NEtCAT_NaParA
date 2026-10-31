# Dane do uczenia reprezentacji STM — wymagania i skala zbioru

Data: **2026-10-31**. Notatka doradcza dla 21/22. Użytkownik ma archiwum
MPP/STP z różnych molekuł i podłoży; rozmiary skanów są w metadanych.
Nowych plików jeszcze nie audytowano. Ta notatka nie zmienia zamkniętego
[protokołu 20](self-supervised-training-protocol.md) ani statusów ticketów.

**Przyjęta kolejność — 2026-10-31:** użytkownik wybrał najpierw próby 21/22
na obecnym TTMAPP i przygotowanych kontrolach. Dodatkowe dane przygotuje
później, jeśli wyniki będą uzasadniały rozszerzenie. Ocena w 23 określi
potrzebny zakres; poniższe zalecenia dla archiwum nie blokują obecnych prób.

**Decyzja po pilocie — 2026-11-01:** w [23](issues/23-training-comparison-and-next-step.md)
użytkownik przyjął zakończenie obecnej serii bez wyboru detektora i pozostawił
dodatkowe dane odłożone. Poniższe zalecenia i robocze liczebności nie są
zleceniem przygotowania archiwum; przyszły zakres wymaga konkretnej hipotezy.

## Co wynika ze źródeł

Pojedyncze obrazy wystarczają jako wejście do uczenia cech; film nie jest
warunkiem AE/rVAE. W pracy Ziatdinova i Kalinina j-trVAE uczył się na
wycinkach regularnej siatki jednego obrazu STM, bez wskazywania atomowych
centrów. Sprawdzono następnie inny obszar przy tych samych warunkach
obrazowania. Autorzy wskazali urozmaicenie zbioru treningowego jako sposób
poprawy generalizacji. To precedens dla uczenia obrazowego, a nie dowód
wystarczalności jednego skanu do naszego detektora domen ani do różnych
materiałów. [Publikacja, część STM, s. 12–14](https://arxiv.org/pdf/2104.10180).

Oficjalny przykład rVAE AtomAI przyjmuje stos wycinków bez etykiet klas.
Nie trzeba zatem przygotowywać ręcznych domen ani detekcji każdej molekuły,
żeby rozpocząć uczenie reprezentacji.
[AtomAI: Variational Autoencoders](https://github.com/pycroscopy/atomai#variational-autoencoders-vae).
W naszym protokole także lokalne SSL tworzy pary widoków z jednego miejsca
obrazu; ciąg kolejnych klatek nie jest wymagany.
[Protokół 20](self-supervised-training-protocol.md).

Zależnych obserwacji nie należy traktować jak niezależnych przykładów
testowych. Dokumentacja walidacji grupowej zaleca ocenę na grupach
nieobecnych w treningu. Nasz wniosek dla STM: dzielić całe akwizycje i
powtórne skany tego samego obszaru **przed** wycinaniem okien; zapisać
powiązania sesji i próbki. Sąsiednie klatki i nakładające się wycinki nie
pomnażają liczby niezależnych pól.
[scikit-learn: grouped data](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data).

## Ile danych: nasze robocze etapy

Przywołane źródła nie wyznaczają uniwersalnego minimum dla STM Domains.
Poniższe liczby są propozycją organizacji pracy, **nie minimum walidacyjnym
ani gwarancją jakości**.

| Etap | Proponowany zakres | Co pozwala ustalić |
| --- | --- | --- |
| Obecne 21/22 | Przygotowany zbiór jednego MPP | Działanie metod i wynik ograniczony do tej serii |
| Audyt archiwum | 20–50 reprezentatywnych pełnych pól | Odczyt, kalibracja, jakość, rozpiętość skal i systemów |
| Szerszy pilotaż | 100–300 obrazów, jeśli dostępne | Pierwsza ocena transferu między akwizycjami, z liczebnościami osobno dla systemów |

Wybieramy różne obszary, sesje, układy molekuła–podłoże i warunki;
setki niemal identycznych klatek nie zastępują tego pokrycia. Przy wielu
materiałach lepiej zacząć od kilku dobrze reprezentowanych systemów niż
dzielić mały zbiór między dziesiątki pojedynczych przypadków. Docelową
liczebność uzasadni dopiero krzywa uczenia, np. dla 25/50/100% grup
akwizycji train, ze stałą walidacją na odłożonych grupach i analizą błędów.
Końcowy test pozostaje osobny; nie służy do dobierania wielkości zbioru.

Obecny rejestr 20 ma 38 622 rekordy, ale tylko **96 okien siatki 48 px
w train z trzech klatek: 1, 50, 100**. Rejestracja i korelacja jednej
akwizycji ograniczają wniosek o transferze.
[Raport przygotowania](self-supervised-training-preparation.md).

## Co dostarczyć razem z obrazem

Poniższy zestaw to propozycja kontraktu nowego korpusu, wymagająca audytu:

| Informacja | Wymaganie praktyczne |
| --- | --- |
| Oryginalne dane | MPP/STP z liczbową macierzą pomiaru i nagłówkiem; podgląd PNG może być dodatkiem |
| Geometria | Liczba pikseli X/Y, fizyczny rozmiar X/Y, jednostki; orientacja i przekształcenia stosowane przy odczycie |
| System | Molekuła, podłoże, identyfikator próbki; preparatyka, jeśli znana |
| Grupa | Sesja/akwizycja i obszar; informacja o ponownych skanach, filmie i numerze klatki, jeśli dotyczy |
| Kanał | Topografia/prąd/błąd, kierunek skanowania; bias, setpoint i szybkość, jeśli dostępne |
| Historia i jakość | Raw lub wykonane poziomowanie/filtracja; braki danych, nasycenie, dryf, zmiana ostrza i niepewności |

Braki opisujemy jawnie. Sam rozmiar w nagłówku nie dowodzi poprawnej
kalibracji: sprawdzamy jednostki, osie i zgodność z odczytem. Dla konwencji
rozmiaru obejmującego N pikseli skala wynosi `sx = Lx/Nx`, `sy = Ly/Ny`;
konwencję konkretnego formatu trzeba potwierdzić. Kanałów i anonimowych
powtórzeń nie mieszamy bez zachowania pochodzenia.

## Jakość, różne skale i różne materiały

Roboczo wybieramy zarówno czytelne pola z powtarzalnością w dwóch
kierunkach, jak i granice, defekty, nieporządek oraz puste obszary.
Do oceny odmów potrzebne są także trudne przypadki, z osobnym oznaczeniem
jakości. Uszkodzony odczyt, nasycenie lub brak geometrii wymagają wyjaśnienia;
nie powinny stawać się pozorną strukturą po przetwarzaniu. Nie ustalamy
uniwersalnego progu SNR ani liczby pikseli na molekułę bez obejrzenia danych.

Różne rozmiary skanu są przydatne, jeżeli zachowujemy **nm/piksel i fizyczne
wsparcie okna**. Można rozważyć wspólną siatkę fizyczną lub przedziały skal,
z jawnym przeliczeniem. Nie należy automatycznie wyrównywać obserwowanego
rozstawu molekuł we wszystkich obrazach: usunęłoby to rzeczywistą informację
o strukturze. Powiększenie obrazu nie odzyska nierozdzielonych molekuł.
To propozycje do przyszłego protokołu, nie obecna implementacja 20.

Dla wielu molekuł/podłoży proponujemy zachować etykiety systemu i równoważyć
udział akwizycji. Główna ocena powinna osobno pokazać nowe akwizycje znanych
systemów. Odłożenie całego nieznanego materiału sprawdza trudniejsze,
odrębne pytanie. Klastry rozróżniające materiały lub kontrast obrazowania
nie są jeszcze domenami przestrzennymi.

Etykiety domen nie są potrzebne do treningu, ale do oceny potrzebny będzie
odłożony podzbiór z ekspercką referencją oraz zaznaczoną niepewnością;
nie trzeba oznaczać całego archiwum. Także gładka rekonstrukcja AE nie
wystarcza jako ocena domen. Rozdział treningu i referencji obowiązuje już
w [protokole 20](self-supervised-training-protocol.md).

## Konsekwencja dla przygotowania danych

Czytnik [STP](../../napara/io/stp_reader.py) istnieje, lecz adapter
[TTMAPP](../../stmdomains/experiments/real_input.py) oraz przygotowanie 20
obejmują audytowane wejście pilota. Archiwum wymaga inwentaryzacji,
weryfikacji kalibracji każdego obrazu, obsługi niezależnych obrazów oraz
nowego manifestu i jawnie zaktualizowanego protokołu. Nie tworzymy sztucznego
filmu z niepowiązanych STP. Surowe dane pozostają poza Git.
