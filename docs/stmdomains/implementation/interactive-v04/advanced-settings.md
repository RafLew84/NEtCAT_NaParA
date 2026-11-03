# Opis otoczenia i bariery — ustawienia SD-V4-15

**Analiza → Analiza… → Zaawansowane** rozszerza wspólny szkic parametrów.
Zmiana pola nie uruchamia obliczeń. **Analizuj** stosuje wszystkie pięć
zakładek do zakresu wybranego w **Zakres**. Dane do dopasowania w **Klasy**
mogą obejmować inny zakres niż klatki, na których mają powstać domeny.
[Ticket](15-advanced-descriptors-barriers.md), [odbiór i test ręczny](acceptance-15.md).

## Opis i model klas

Jednostką długości jest rozstaw: mediana odległości do najbliższej molekuły
po odrzuceniu oznaczeń poza polem i usunięciu duplikatów na danej klatce.
Nie jest to rozmiar w nm ani rozmiar dopasowany do paczki v0.4.

| Pole | Bazowo | Obsługiwany zakres i znaczenie |
| --- | --- | --- |
| Sigma opisu | 1,25 × rozstaw | 0,25–3; wagi par i zasięg ich środków wokół molekuły. |
| Przedziały odległości | 14 | Całkowite 4–32; rozdzielczość radialna histogramu. |
| Przedziały kąta | 36 | Całkowite 8–72; rozdzielczość kierunków 0–180°, opis czuły na orientację. |
| Minimum odległości par | 0,55 × rozstaw | Co najmniej 0,1; dolna granica długości par. |
| Maksimum odległości par | 2,8 × rozstaw | Najwyżej 4; górna granica długości par. |
| Maksimum składowych PCA | 24 | Całkowite 1–64, nie więcej niż wymiar histogramu. |

Zakres par musi mieć szerokość co najmniej 0,1 rozstawu. Histogram ma
najwyżej 2048 pól. Faktyczna liczba składowych PCA jest ograniczona przez
liczbę próbek minus jeden i wymiar histogramu; dla jednakowych opisów
projekcja pozostaje tożsamościowa. W metadanych są zarówno ustawiony
limit, jak i faktyczny stan modelu. Auto również używa wybranego opisu/PCA.

Środki par są zbierane w promieniu 2,8 × sigma, z wagami Gaussa.
Wygładzanie histogramu pozostaje stałe: sigma 0,65 i 0,95 przedziału,
normalizacja i pierwiastek. Kryteria wsparcia otoczenia zachowują promienie
2,5 i 1,5 rozstawu. Zwiększenie sigma nie zwiększa automatycznie wszystkich
promieni ani parametrów testu porządku z osobnej zakładki.

Zmiana któregokolwiek pola opisu wymaga **Dopasuj nowe klasy**: nowe cechy,
PCA i klastrowanie z otwartych danych. Parametry należą do treści katalogu
i jego ID. Przy **Użyj istniejących klas** wybór katalogu wczytuje jego opis;
późniejsza edycja niezgodna z katalogiem blokuje **Analizuj**. Nie używa się
projekcji o niezgodnym wymiarze. Wcześniejszy wynik pozostaje niezmienny.

## Bariery obrazu

To istniejący detektor kandydatów granic kontrastu: niemal poziome fragmenty,
które jaśnieją w dół oryginalnego obrazu, przy rosnącym numerze wiersza.
Nie jest uniwersalnym detektorem tarasów fizycznych. Nachylenie opisuje
granicę w obrazie, nie orientację molekuły ani tolerancję klas.

| Pole | Bazowo | Obsługiwany zakres i znaczenie |
| --- | --- | --- |
| Dolny percentyl gradientu | 65 | 0–99,9; słabsze piksele dopuszczone do histerezy. |
| Górny percentyl gradientu | 90 | 0–100, większy od dolnego; mocne początki fragmentów. |
| Minimalna długość fragmentu X | 3 × rozstaw | 0,1–100; rozpiętość w osi X, po zaokrągleniu minimum 3 px. |
| Dopuszczalna przerwa | 5/3 × rozstaw | 0–3; maksymalna długość połączenia wspartego gradientem; 0 wyłącza łączenie przerw. |
| Maksymalne nachylenie | 55° | 1–85° od poziomu; ograniczenie wykrywanych fragmentów. |
| Poszerzenie maski | 1/12 × rozstaw | 0–2; 0 bez dylatacji, dodatnia wartość po zaokrągleniu daje co najmniej 1 px. |

Percentyle są liczone z siły gradientu całej surowej klatki, przed gammą
podglądu. Krótkie łączniki wsparte gradientem mogą być bardziej strome
niż limit fragmentów. Pozostają stałe: sigma wygładzania obrazu
(0,25; 5/12) × rozstaw, przedłużenie do bliskiego brzegu 2/3 × rozstaw,
percentyl wsparcia 55 i wymagany udział wsparcia 0,5. Przerwa równa zero
nie wyłącza tego osobnego przedłużania przy brzegu.

Aby zmienić same bariery, wybierz **Użyj istniejących klas**, ich katalog,
zmień pola barier i kliknij **Analizuj**. PCA i klasy nie są dopasowywane
ponownie; ich ID pozostaje takie samo. Aplikacja przygotowuje opis klatki,
stosuje zachowany model oraz oblicza bariery i domeny. Nie ma cache cech
pośrednich pomijającego zmianę ustawień. Parametry barier należą do wyniku
klatki i planu przebiegu, a nie do tożsamości dopasowanego katalogu.

## Podgląd, porównanie i zapis

**Pokaż bariery wyświetlanego wyniku (pomarańczowe)** pokazuje dokładną
maskę używaną przy tworzeniu domen, z uwzględnieniem poszerzenia. Jest to
diagnostyka, nie nowa klasa ani domena. Po edycji pól do kliknięcia
**Analizuj** nadal widać maskę poprzedniego wyniku; opis pod kontrolką
podaje jej dostępność i liczbę pikseli. Porównanie **Nowy/Poprzedni wynik**
zmienia również tę maskę, bez zmiany szkicu parametrów.

**Z wyświetlanego wyniku** kopiuje rzeczywiste parametry. **Przywróć bazowe
parametry** odtwarza wartości aplikacji, bez zmiany zakresów i trybu klas.
Jeśli zachowany katalog ma inny opis, trzeba wybrać nowe dopasowanie.
To samo wejście, zakres i bazowe parametry zachowują ziarno 24; próba
TTMAPP potwierdziła odtworzenie identycznego katalogu, przypisań i barier.

Projekt zachowuje maskę, rzeczywiste parametry wyniku, osobny szkic oraz
widoczność diagnostyki. Stare projekty bez maski można otworzyć; brak maski
nie staje się maską pustą i nie uruchamia obliczeń. PNG uwzględnia włączoną,
dostępną warstwę i jej legendę, także po wyrównaniu i przy wycinku.
Szczegóły: [format projektu](project-format-v1.md), [eksport](export-format-v1.md).

Większa liczba przypisań po zmianie ustawień nie potwierdza poprawy jakości.
Ocena fizycznej poprawności klas, barier i domen wymaga osobnej referencji.
