# Interaktywna analiza klas i domen na podstawie v0.4

Data: **2026-11-02**. Użytkownik chce dostosowywać parametry w UI, uruchamiać
analizę serii albo pojedynczej klatki i od razu oglądać wynik. Oczekuje
ręcznego zadawania liczby klas oraz pracy bez znajomości tej liczby.
Ocenę oparto na kodzie z [paczek v0.4](new-code-v04-review.md) i dostarczonej
notatce o strojeniu parametrów. To ocena wykonalności i proponowany zakres,
nie wykonana implementacja ani zatwierdzenie skuteczności metody.

**Tak, v0.4 nadaje się jako baza.** Ma obliczenia cech, dopasowanie modeli,
przypisania molekuł i tworzenie domen. Trzeba wydzielić te operacje ze
skryptów, ujednolicić konfigurację i połączyć je z interaktywnym podglądem.
Istniejące `stmdomains` ma startowe okno PyQt6, które można rozwinąć.

## Co już istnieje, a co wymaga pracy

| Funkcja | Stan v0.4 | Potrzebna zmiana |
| --- | --- | --- |
| Ręczna liczba klas | Dopasowanie kandydatów K2–8 i jawny wybór K | Pole w UI, sprawdzenie liczby dostępnych próbek i spójny wybór modelu |
| Automatyczna liczba klas | Wybór najlepszego silhouette w skrypcie odkrywania | Podłączenie przez cały przebieg; obsługa K1, małych danych i braku uzasadnionego podziału |
| Analiza serii | Wspólny model dla przygotowanego zestawu klatek | Zakres wybierany w UI, niezależna segmentacja klatek |
| Bieżąca klatka ze słownikiem serii | Zapis zawiera PCA, centroidy i promienie klas | Funkcja stosowania modelu i analizy jednej klatki |
| Odkrywanie klas tylko z jednej klatki | Runner wymaga pierwszych dziesięciu klatek i referencji | Usunięcie tego powiązania, skala z wybranego wejścia, dostosowanie PCA/K do ilości danych |
| Zmiana parametrów | K i parametry geometrii w konfiguracji; reszta głównie w kodzie | Pełna konfiguracja obliczeń, nie tylko dodatkowe pola JSON |
| Interaktywny wynik | Gotowy statyczny HTML i CSV | Podgląd molekuł, wywołanie obliczeń w tle, zachowanie ustawień i wyników |

## Liczba klas: ręcznie i Auto

`discover_classes.py:325–330` już wybiera K z największym silhouette, jeśli
nie podano `--selected-k`. Jednak `reproduce_discovery.py:187,222` zawsze
przekazuje K z konfiguracji, a `run_discovery.py:161` również daje mu
pierwszeństwo. Tryb Auto musi być jawny od ustawień aż po segmentację.

Użytkownik nie musi znać K: program może porównać kandydatów i wybrać K
samodzielnie. Nadal jest to wybór w ustalonym zakresie, nie nieograniczone
odkrywanie fizycznych faz. Obecny kod zaczyna od dwóch klas, ogranicza zakres
do ośmiu, używa PCA24 i marginesu między dwoma najbliższymi centroidami.
Obsługę jednej klasy, niewystarczających danych i braku rozróżnialności
trzeba dopisać zamiast zawsze wymuszać co najmniej dwie grupy.

Na danych z paczki najwyższy silhouette ma K2, a K5 wybrano ręcznie po
ocenie obrazów. **Auto oparte na obecnym kryterium nie odtworzy K5.**
Jest użyteczną propozycją statystyczną; UI powinno pokazać wybrane K
i pozwalać porównać je z ustawieniem ręcznym. Ocena stabilności oraz kontrola
pojedynczej sieci są potrzebne przed uznaniem Auto za wiarygodne.

Nie trzeba na początku zmieniać całego klasteryzatora. Alternatywna metoda
grupowania bez podawanego K pozostaje możliwym, odrębnym rozszerzeniem;
nie wybrano jej w tej ocenie.

## Seria i jedna klatka

Rekomendowany domyślny sposób: odkryć wspólne klasy w wybranej serii lub
zakresie, a potem przeliczać domeny na bieżącej klatce albo całym zakresie
z zachowaniem tego słownika. Kolory klas mają wtedy wspólne znaczenie
w ramach modelu. Domeny pozostają osobnymi instancjami każdej klatki.

Oddzielny tryb „Odkryj klasy na tej klatce” również jest wykonalny. Klasy
powstają wtedy tylko z jej danych i nie muszą odpowiadać klasom innych
klatek. Obecne `--frames 259` nie realizuje tego zadania: runner wymaga
klatek 1–10 (`reproduce_discovery.py:102–103`) i modeli referencyjnych.

Należy rozdzielić zakres danych do odkrywania klas od zakresu przeliczanych
domen. Zmiana minimum wielkości domeny nie powinna samoczynnie zmieniać
słownika całej serii. Przycisk ponownego odkrywania klas ma oznaczać
świadomą zmianę modelu, z zachowaniem poprzedniego wyniku do porównania.

## Proponowany pierwszy interfejs

- Otwarcie serii MPP wraz z istniejącymi oznaczeniami MolTrack.
- Duży obraz, nawigacja po klatkach i powiększanie.
- Liczba klas: **ręcznie / Auto**; obok zakres analizy.
- Przyciski **Analizuj bieżącą klatkę**, **Analizuj zakres** oraz jawne
  **Odkryj klasy ponownie** dla zmiany słownika.
- Widok **Domeny** zgodny z [wymaganiem użytkownika](trial-result-browser.md):
  kolor konkretnej domeny na molekułach, szary brak przypisania.
  Dodatkowy widok **Klasy** pokazuje przypisanie geometrii; etykieta klasy
  nie oznacza automatycznie potwierdzonej domeny.
- Zachowanie ustawień i wyniku, porównanie z poprzednim uruchomieniem.
  Postęp i anulowanie obliczeń, bez blokowania nawigacji.

Pierwszy zestaw ustawień: minimum molekuł w domenie, próg podobieństwa
sąsiadów, dopuszczalne zróżnicowanie całej domeny i odległość łączenia.
Parametry testu porządku, akceptacji klasy i opisu otoczenia mogą być
w rozwijanej części zaawansowanej. Punkt wyjścia to zapisane ustawienia v0.4;
łagodniejsze wartości z dostarczonej notatki są propozycjami, nie wynikami prób.

## Co jest potrzebne, żeby zmiana parametrów była interaktywna

Rozdzielić import, cechy, ocenę porządku, model klas, akceptację punktów
i segmentację. Przechowywać wyniki pośrednie z informacją o wejściu
i ustawieniach, aby liczyć tylko zmienione etapy:

- progi łączenia i minimum domeny: ponownie segmentacja;
- progi wiarygodności klasy: ponownie akceptacja i segmentacja przy
  zachowanych centroidach, jeśli opis i zakres modelu nie zmieniły się;
- parametry porządku: ponowna ocena i odpowiednia kalibracja na kontrolach;
- opis otoczenia lub zakres odkrywania: nowe cechy/dopasowanie klas.

W obecnym kodzie test porządku także wybiera próbki do dopasowania modelu.
Przy zachowanym słowniku jego strojenie zmienia akceptację; przy ponownym
odkrywaniu może zmienić również klasy. UI i zapis wyniku muszą zachować
to rozróżnienie. Zmiana promienia lub sigmy nie pozwala używać bez sprawdzenia
starych progów kalibracyjnych.

Wymagają wyprowadzenia do konfiguracji m.in. minimum 8 stosowane dwa razy
w `run_discovery.py:184–192`, margines 0,075 i promień klasy ×1,10
w `discover_classes.py:295–300`, stałe z `assess_order.py:27–35,90`,
odległość krawędzi w `geometry_segmentation.py:18–21` i zasięg maski
w `run_prototype.py:60–64`. Notatka użytkownika prawidłowo wskazuje,
że dopisanie tych wartości do JSON nie podłącza ich do obliczeń.

Szybkość odpowiedzi wymaga pomiaru. Zachowanie gotowych cech/modeli pozwala
unikać niepotrzebnych dopasowań, ale nie potwierdza natychmiastowej analizy
całej serii przy dowolnej zmianie ustawień.

## Zakres i stan oceny

V0.4 korzysta z **już oznaczonych molekuł**. Analiza samych obrazów bez
położeń wymaga dodatkowego etapu detekcji molekuł. Pierwszy zakres powinien
wykorzystać obecny MPP/JSON; obsługa innych rozmiarów, skal i wariantów
formatu potrzebuje usunięcia założeń TTMAPP, opisanych w przeglądzie paczek.

Proponowana kolejność budowy: import i prosty podgląd → obliczenia z pełną
konfiguracją → wspólny model i analiza jednej klatki/zakresu → ręczne K/Auto
oraz samodzielne odkrywanie na jednej klatce → sprawdzenie GUI i wyników.
Warto zachować v0.4 jako odtwarzalny punkt odniesienia dla domyślnych ustawień.

Wykonano statyczną analizę kodu i wklejonej notatki, bez nowych obliczeń,
instalacji albo implementacji UI. Nie utworzono ticketów i nie zmieniono
statusów odbioru metody 04/13. Interaktywny program będzie narzędziem
eksploracji; samo dostarczenie suwaków nie potwierdza trafności segmentacji.
