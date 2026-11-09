# SD-V4-23a — scalanie i dzielenie klas

2026-11-09. Gałąź `domains/interactive-v04-ui`, baza `ee2071d`.
Implementacja `5ca2e6f`, poprawka doboru zgodnych źródeł `5de0d7f`.
Odbiór ręczny użytkownika **otwarty**. Poniżej wykonane sprawdzenia agenta
oraz oddzielna instrukcja do samodzielnego odbioru.

## Obsługa

Uruchom w **netcat**: `python -m stmdomains.main`.
Wejdź w **Edytuj domeny → Klasy ręczne… → Scal klasy… / Podziel klasę…**.
Okno operacji jest niemodalne; podczas wskazywania molekuł można je przesunąć
obok obrazu. Wybrany wcześniej tryb Klasy/Domeny nadal określa podpisy i kolory.

1. Wybierz wariant źródłowy z konkretną listą klas i jej wersją. Domyślny
   zakres to bieżąca klatka; dostępne są też zakres od/do i cała seria tej listy.
   Kliknij **Ustal / odśwież zakres i wersje**. Tabela pokazuje objęte klatki,
   warianty, liczności klas i powody pominięcia pozostałych.
2. **Scalanie:** zaznacz co najmniej dwie klasy źródłowe z członkami w zakresie.
   Wybierz jedną z nich jako cel albo nową klasę z nazwą i kolorem. Obejmuje
   to również członków klasy bez domeny; punkty innych klas pozostają bez zmian.
3. **Podział:** zaznacz jedną klasę źródłową. W obrazie wybierz molekuły
   kliknięciami lub lassem, następnie **Zapamiętaj wskazania bieżącej klatki**.
   Tryb **Całe wskazane domeny + wybrane punkty bez domeny** rozwija wybór
   do całych wskazanych domen i zachowuje osobno wskazane punkty bez domeny.
   Przy wielu klatkach powtórz wskazywanie i zapamiętanie na każdej klatce
   zawierającej źródłową klasę. Wskazania nie przechodzą między klatkami.
4. **Pokaż podgląd** wyświetla liczniki przed/po, liczbę domen i wynik na
   obrazie. Dwuklik w wierszu otwiera klatkę. Nawigacja nie zmienia
   utrwalonego zakresu. **Anuluj podgląd** przywraca stan bez wpisu w historii.
5. **Zastosuj wszystkie klatki** zapisuje jedną operację w historii sesji.
   **Cofnij/Ponów** odtwarza razem wszystkie jej klatki i wersję listy.
   Późniejsze operacje z 21–23 są cofane w kolejności wykonania.

Zmiana zakresu, wariantu, listy lub przypisań wymaga ponownego przygotowania
podglądu. Zmiana parametrów celu unieważnia poprzedni podgląd. Model, jego K,
centroidy i wynik automatyczny pozostają bez zmian. Źródłowe klasy zachowują
ID i mogą być puste w zakresie; nowa klasa ma odrębne ID. UI osobno pokazuje
K modelu, liczbę klas na liście, ręcznych i obecnych w zakresie.

Scalanie klas zachowuje osobne domeny i ich maski. Podział obejmujący całe
domeny też zachowuje ich geometrię. Zmiana klasy części domeny wydziela tę
część według reguł 22/23, w ramach tej samej operacji. Molekuły bez domeny
pozostają bez domeny. Nazwy prezentacyjne A1/B1 zmieniają się wraz z klasą;
wewnętrzne ID niepowiązanych domen pozostają.

Dobór klatek respektuje katalog/listę, metodę i przebieg źródłowego wariantu.
Na jego klatce obowiązuje wskazany wariant; na pozostałych pierwszeństwo ma
zgodny wybrany wariant, potem ostatnio utworzony zgodny wariant ręczny,
a następnie zgodny wynik automatyczny (nowy, później poprzedni). Wariant
obcego katalogu nie przesłania dostępnego zgodnego wyniku. Tabela ujawnia
wybrane ID; zmiana tego wyboru wymaga odświeżenia zakresu.

## Gotowy przykład i test użytkownika

W katalogu projektu, w środowisku netcat:

```bash
python -m stmdomains.tools.class_operations_demo --open
```

Generator przygotowuje lokalnie `.scratch/stmdomains-ui-23a/demo/`, otwiera
zwykłe okno aplikacji i przypisuje przez operacje 23 dwa punkty bez domeny
do klasy A. Stan startowy jest gotowy do testu: klatka 1 A=6/B=3, klatka 2
A=4/B=3; każda ma dwie domeny. Klatka 3 ma inny katalog mimo takich samych
nazw klas. To kontrola techniczna, nie wynik detektora ani dane treningowe.

Sam plik `class-controls.stmdomains` zawiera A=4/B=3 i dwa punkty bez klasy
na pierwszej klatce. Przygotowanie A=6/B=3 odbywa się jawnie w RAM launchera,
ponieważ zapis ręcznych korekt należy do 24. Nie cofaj początkowego przypisania
launchera podczas testu; w razie potrzeby uruchom przykład ponownie.

| Próba | Oczekiwany wynik |
|---|---|
| Scal A+B do C, tylko klatka 1 | C=9; 2 domeny, 2 molekuły bez domeny; klatka 2 A=4/B=3 |
| Anuluj zamiast zatwierdzać | A=6/B=3, bez zmiany historii i listy |
| Scal A+B do istniejącej A | A=9/B=0; bez nowej klasy |
| Scal A+B do C, wszystkie klatki tej listy | C=9 i C=7; trzecia klatka jawnie pominięta |
| Z C wydziel domenę czterech molekuł i jeden punkt bez domeny do D | D=5/C=4, nadal 2 domeny i 2 punkty bez domeny |
| Cofnij, wydziel jedną molekułę z domeny trzycząsteczkowej | D=1/C=8, 3 domeny; Cofnij odtwarza też maskę |
| Pusty wybór / cała klasa / jedna klasa do scalenia | Wyjaśnienie, bez zmiany przypisań i historii |

Na obrazie czteroczłonowa domena jest po lewej, trzyczłonowa po prawej,
a dwa punkty bez domeny bezpośrednio pod lewą domeną. Do całej domeny
wystarczy wskazać jednego członka i wybrać tryb rozwijający wybór.
Po scaleniu dwóch klatek sprawdź wspólne Cofnij/Ponów oraz nawigację podczas
podglądu. Szczegółowa sekwencja: [ticket 23a](23a-split-merge-classes.md#test-ręczny-użytkownika).

Do próby bez modelu otwórz `class-controls.moltrack.json`, utwórz przez
**Klasy ręczne** dwie klasy i przypisz im rozłączne wskazania. Scal je,
a następnie wydziel część jednej klasy. Bez ręcznego tworzenia domen
ich liczba ma pozostać zerowa, a UI ma pokazywać **Brak modelu**.

## Sprawdzenia agenta

Natywne Qt/X11 w **netcat**: kontrola scalania 9/7, podziału 5/4 oraz 1/8,
zmiany liczby domen 2→3, anulowania, nawigacji przez tabelę i atomowego
Cofnij/Ponów — PASS. Osobna próba bez modelu: scalenie 9, podział 1/8,
0 domen i brak katalogu — PASS. Obejrzano zrzuty okna i obrazu.
Poprawiono odświeżanie limitu zakresu po zmianie serii na dłuższą.

**TTMAPP**, `data/TTMAPP/detection_full.moltrack.json`, klatki **259–260**
(indeksy 258–259), metoda bazowa, domyślne parametry, K=5 dopasowane wspólnie
do tych dwóch klatek; druga klatka analizowana z tym samym katalogiem:

- Początkowo: 7 i 5 domen; 116 i 104 molekuły przypisane do domen.
- Scalenie klas o wewnętrznych ID `1`, `2` (A/B) do **Połączone**:
  odpowiednio **76 i 82 członków**, bez zmiany liczby domen ani pikseli masek.
- Wydzielenie jednej całej domeny na klatce 259 do **Wybrane**: **50 członków**;
  w Połączone pozostaje 26. Liczba domen 7 i maska bez zmian.
- Cofnięcie podziału, następnie scalenia przywróciło oba wyniki automatyczne.
  K=5, obiekt katalogu i maski nie zmieniły się. Porównanie Automatyczny/Po
  korektach, raw/wyrównany i zamknięcie po pracy — PASS.

To sprawdzenie operacji edycji, a nie ocena jakości wykrywania domen.
Artefakty lokalne: `.scratch/stmdomains-ui-23a/` (zrzuty, skrypt próby,
`gui-report.json`, logi). Nie są wersjonowane.

Testy automatyczne obejmują błędne źródła, nieaktualny podgląd na drugiej
klatce przed atomowym zatwierdzeniem, obcy katalog mimo tych samych nazw,
wskazania osobno dla klatek, mieszanie historii klas z operacjami 23,
anulowanie pracy w tle i zamykanie okna. Celowany zestaw: **32 PASS / 22,96 s**;
po poprawce zakresu controls/window: **13 PASS / 7,92 s**.
Pełna końcowa regresja w netcat/offscreen: **624 PASS / 280,46 s**.
Pierwszy pełny przebieg przerwał SIGTERM, bez raportu błędu testu; ponowiony
w sesji terminalowej zakończył się kodem 0. Raport:
`.scratch/stmdomains-ui-23a/regression.xml`.

[Przegląd](review-23a.md): Standards **0 uwag**; Spec **1 uwaga P2 poprawiona**,
**0 otwartych** po ponownym przeglądzie. Mypy **119 modułów PASS**.
Wszystkie **11 zmienionych plików kodu/testów poniżej 1000 linii**;
maksimum **891** (`ui/session_controller.py`), bez wyjątków od limitu.

## Ograniczenia

Korekty nadal tylko w pamięci sesji: zapis/odtworzenie w 24, eksport w 25.
Brak nowych zależności. Nie dodano automatycznej propagacji zaznaczeń,
uczenia klas, łączenia obcych katalogów ani swobodnego rysowania granic.
Odbiór ręczny użytkownika pozostaje otwarty; następny etap **24 → 25 → 26**.
