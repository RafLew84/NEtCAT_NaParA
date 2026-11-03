# MPP a zgodność z WSxM — rozpoznanie

Sprawdzenie: 2026-10-19. Cel: decyzje dla eksportu STM Viewer, nie implementacja.
Nie uruchomiono WSxM i nie potwierdzono interoperacyjności nowego pliku.

## Co wynika ze źródeł

Dokumentacja UAM opisuje **STP**, a nie pełny format filmu MPP. Podaje
nagłówek z rozmiarem w bajtach, sekcje parametrów, typy 8-, 4- i 2-bajtowe
oraz jednostki. Dopuszcza dodatkowe pola. Opisuje kolejność danych przez
odwołanie do macierzy: rosnące Y i malejące X. Nie definiuje maski brakujących
próbek, NaN, pól źródłowych klatek ani metadanych zmiennych między klatkami.
Tolerowanie dodatkowych pól STP nie dowodzi ich zachowania przez zapis MPP
w WSxM. [Specyfikacja UAM](https://spmimages.ftmc.uam.es/file-specifications/)

W lutym 2024 autor Gwyddion i zgłaszający sprawdzali rzeczywiste WSxM.
Wniosek dla badanych **STP**: wartości całkowite były przeliczane według
amplitudy Z, natomiast zmiennoprzecinkowe używały bezpośrednich wartości
z jednostką deklarowaną w nagłówku. Gwyddion poprawił ten przypadek;
notatki wydania potwierdzają korektę skali danych zmiennoprzecinkowych.
To ważna wskazówka dla double MPP, ale nie dowód zachowania każdego filmu
czy wersji WSxM. Nie należy normalizować znanych fizycznych wartości do liczby
z pola amplitudy. [Pierwotne eksperymenty i odpowiedź autora Gwyddion](https://sourceforge.net/p/gwyddion/discussion/fileformats/thread/5f6d25624d/),
[Historia Gwyddion](https://gwyddion.net/news.php)

W kodzie SciFiReaders, plik ostatnio zmieniony w commicie
`17bcd0cd72a17c9dc9d14c8255f3721ec30b879f` (2025-02-12), czytnik filmów:

- używa jednego nagłówka, jednego kanału i wspólnej kalibracji wszystkich klatek;
- odczytuje kolejne macierze zgodnie z zadeklarowanym typem; obsługuje double;
- mnoży próbki, także double, przez amplitudę Z podzieloną przez różnicę
  maksimum i minimum z nagłówka, z wyjątkiem zerowej amplitudy;
- tworzy oś numerów klatek, nie korzysta z czasów synchronizacji;
- obraca i odwraca osie w warstwie tworzącej wynik;
- parser przechowuje zwykłe nieznane pary klucz–wartość, ale rozdziela po
  wszystkich dwukropkach: pole zawierające JSON z dwukropkami może pominąć;
- nie ma mechanizmu maski ani zastępowania NaN w funkcji odczytu filmu.

To dowód działania **tego czytnika**, nie gwarancja WSxM. W szczególności
rozbieżność kalibracji float względem opisanych prób STP oznacza, że sukces
odczytu w SciFiReaders nie wystarczy do akceptacji wartości.
[Źródło czytnika: parser, film i orientacja](https://github.com/pycroscopy/SciFiReaders/blob/17bcd0cd72a17c9dc9d14c8255f3721ec30b879f/SciFiReaders/readers/microscopy/spm/afm/wsxm.py)

Gwyddion wymienia wsparcie obrazów WSxM i krzywych, lecz nie wymienia MPP
w tabeli formatów. Nie jest zatem potwierdzonym odbiorcą całego filmu.
[Tabela formatów Gwyddion](https://gwyddion.net/documentation/user-guide-en/file-formats.html)

## Odpowiedzi na istotne pytania

**Czy WSxM prawidłowo traktuje NaN w rozszerzonym filmie?** Nie ustalono.
Przejrzane źródła nie dokumentują ani obsługi, ani zakazu. Sam binarny zapis
NaN i poprawny odczyt w NumPy nie potwierdzają poprawnego zakresu kolorów,
statystyk, filtrów ani ponownego zapisu w WSxM. Nie można opisać tej cechy
jako wspieranej albo jako niemożliwej bez próby w wymaganej wersji WSxM.

**Czy jeden MPP przeniesie zmienne metadane oraz pola oryginalnych klatek?**
Dodatkowe dane można zapisać w umówionym rozszerzeniu dla STM Viewer.
Nie znaleziono udokumentowanego standardu, dzięki któremu WSxM sam zrozumie
indywidualne skale, jednostki, źródła, maski i prostokąty. Czytnik SciFiReaders
wyraźnie używa wspólnej kalibracji. Nie jest to dowód ograniczeń wszystkich
wersji WSxM; jest to brak podstaw do obiecania interoperacyjności.

## Rekomendacja projektowa

Poniższe punkty są rekomendacją, nie ustaloną specyfikacją formatu.

1. Zdefiniować wymagany odbiór w konkretnej wersji WSxM: liczba i kolejność
   klatek, orientacja, wartości, jednostki i geometria. Nie deklarować pełnej
   zgodności jedynie dlatego, że plik się otwiera.
2. Zachować naukową semantykę braków. NaN z pełnego aligned to rozsądny
   kandydat wymagający testu. Jeśli WSxM go nie obsłuży, nie podmieniać po
   cichu na zero i nie kadrować bez decyzji użytkownika. Maska w pliku obok
   nie sprawia, że WSxM zacznie ją respektować w obliczeniach.
3. Rozważyć **MPP oraz towarzyszący zapis metadanych**: MPP jako dane do
   WSxM, wersjonowany dodatek jako pełny kontrakt odczytu STM Viewer.
   Dodatek zachowuje pochodzenie, czas/nieznany czas, metadane każdej klatki,
   geometrię źródłową, transformację i ważność próbek. Spójność z MPP powinna
   być sprawdzana identyfikatorem lub sumą kontrolną. Rozszerzenie w nagłówku
   może dać jeden plik, ale jego przeżycie ponownego zapisu w WSxM jest
   również niezweryfikowane.
4. Dla różnych kanałów/jednostek/skali nie przepisywać parametrów pierwszej
   klatki jako prawdy o wszystkich. Osobny zapis pozwala zachować metadane,
   lecz WSxM może nadal prezentować tylko wspólną kalibrację. Wymagania dla
   takiej serii muszą być wyraźnie ustalone (np. brak deklaracji fizycznej
   kalibracji filmu, podział na zgodne serie albo odmowa tego eksportu).

Minimalny test w rzeczywistym WSxM: mały niesymetryczny film double ze
znanymi ujemnymi i ułamkowymi wartościami; różne rozmiary X/Y; kopia z NaN
na krawędzi oraz we wnętrzu; nieregularne czasy; dodatkowa sekcja; ponowny
zapis i porównanie. Należy osobno sprawdzić piksele i metadane, wyświetlanie,
statystyki oraz zachowanie braków po ponownym zapisie.

## Zakres pracy

Przejrzano wskazane źródła oraz istniejące rozpoznanie lokalnych readerów
w `docs/stmviewer/reconnaissance.md`. Pobrano wyłącznie otwarty kod
SciFiReaders (~50 kB) i identyfikator jego wersji. Nie instalowano programu,
nie pobierano dużych danych, nie zmieniano kodu wspólnego i nie wykonywano
prób w WSxM.
