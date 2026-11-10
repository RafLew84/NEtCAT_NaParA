# SBC/MatID — audyt adaptacji do centrów molekuł

Data: 2026-10-23. Materiał do [issue 16](issues/16-sbc-matid-domains.md).
Audyt dotyczy źródeł przypiętych do commitu
`5aa27776df0277e2b75af8680bd0faf760cf924a`; wyniki obliczeń i wybór parametrów
należą do osobnego raportu próby. Nie zakładamy, że instalacja z PyPI zawiera
identyczne pliki.

**SBC jest uzasadnionym kandydatem do próby, ale jego surowy klaster nie jest
jeszcze wiarygodnie rozpoznaną domeną STM.** Szczególnie trzeba sprawdzić
fałszywe wzory w przypadkowych punktach, zależność od kolejności wyszukiwania,
nakładanie regionów i utratę odłączonych fragmentów. Sam argument `radii`
nie usuwa wszystkich założeń atomistycznych z tej wersji kodu.

## Co potwierdza publikacja

Denell i współautorzy opisują identyfikowanie wspólnej komórki przez lokalne
translacje, bez treningu i katalogu struktur. Pokazują warstwy oraz granice
ziaren. Przykłady określane jako rzeczywiste pochodzą z optymalizowanych
symulacji atomistycznych; nie stanowią walidacji centrów molekuł wykrywanych
na STM. Zwiększanie tolerancji pozycji ogranicza odmowy, lecz może tworzyć
nieistniejące wzory. Autorzy powtarzają próby z różnymi początkami wyszukiwania.
Ich dopasowanie tolerancji do szumu jest wyrażone w Å dla badanych układów
i nie jest receptą dla pikselowych detekcji TTMAPP.
[Publikacja, 2025](https://www.nature.com/articles/s41524-024-01498-x).

Dokumentacja deklaruje obsługę struktur skończonych i periodycznych oraz
powtarzania w dwóch lub trzech kierunkach. Struktury jednowymiarowe nie są
obsługiwane. To wyszukiwanie powtarzalnego układu, nie uniwersalne grupowanie
dowolnych zaznaczonych obiektów.
[Dokumentacja SBC](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/docs/docs/learn/symmetry-based-clustering/symmetry-based-clustering.mdx).

## Publiczne API i końcowe przetwarzanie

Wywołanie to `SBC().get_clusters(system, ...)`, gdzie `system` jest `ase.Atoms`.
Parametry domyślne przypiętej wersji:

| Parametr | Wartość |
| --- | ---: |
| `angle_tol` | 20 |
| `max_cell_size` | 6 |
| `pos_tol` | 0.7 |
| `merge_threshold` | 0.5 |
| `merge_radius` | 1 |
| `bond_threshold` | 0.65 |
| `overlap_threshold` | −0.6 |
| `radii` | `"covalent"` |
| `seed` | 7 |

Po wyszukiwaniu następują scalenie, rozstrzygnięcie nakładania i czyszczenie:

- Scalenie wymaga `max(|A∩B|/|A|, |A∩B|/|B|) > merge_threshold`.
  Kod nie porównuje zgodności komórek; zachowuje prototyp większego regionu.
- Nakładanie rozstrzyga liczba sąsiadów w promieniu `merge_radius`, liczonym
  po odjęciu promieni. Remis wygrywa pierwszy region. W tym commicie nie ma
  bezpośredniego losowania zwycięzcy, ale kolejność regionów zależy od losowych
  początków wyszukiwania.
- Czyszczenie zachowuje wyłącznie największą spójną część każdego regionu.
  Przy wyjątku pomija cały region. Potem nie ponawia wyszukiwania.
- Kandydaci na kolejne początki są usuwani także po sprawdzeniu sąsiedztwa,
  nawet gdy nie znaleziono regionu. Stałe ziarno nie gwarantuje odporności
  na zmianę kolejności punktów.

[Implementacja SBC](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/matid/clustering/sbc.py).

## Własne promienie nie docierają do całego algorytmu

`get_radii` dla własnej tablicy zwraca ją bez indeksowania numerami
pierwiastków: potrzebna jest wartość dla każdego punktu. `get_distances`
domyślnie używa promieni kowalencyjnych. `get_dimensionality` także domyślnie
korzysta z takich promieni; jego `cluster_threshold` to próg połączenia
`d − r_i − r_j`, nie minimalna liczba punktów. W publicznym wywołaniu SBC
nie ma argumentu `cluster_threshold`; tę rolę pełni przekazywany
`bond_threshold`. Funkcja `get_clusters` w przypiętym kodzie wyznacza
komponenty grafu progowanych odległości, odpowiadające DBSCAN przy
`min_samples=1`.
[Funkcje geometrii](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/matid/geometry/geometry.py).

`PeriodicFinder` otrzymuje odległości policzone z własnymi promieniami,
lecz waliduje nową komórkę przez `get_dimensionality(proto_cell, ...)`
i `get_distances(proto_cell)` bez przekazania tych promieni. Wtedy wracają
domyślne promienie wybranego pierwiastka. `pos_tol` i `max_cell_size` są
odległościami bezwzględnymi; `angle_tol` określa uznawanie wektorów bazy za
równoległe, nie próg różnicy orientacji między domenami. Jest też stała
tolerancja wyboru rozmiaru komórki `cell_size_tol`, niewystawiona przez SBC.

Istotna różnica względem opisu publikacji: test średniego stopnia grafu
powtarzalności jest wyłączony od MatID 2.0.0, aby zachować skończone brzegi
i narożniki. Pozostaje warunek wielkości grup względem grupy punktu startowego.
Dla skończonej struktury 2D region może przejść końcowy warunek liczności już
przy czterech punktach. Wzrost regionu aktualizuje lokalną komórkę, dlatego
prototyp początkowy nie jest globalnym dopasowaniem do wszystkich punktów.
[PeriodicFinder: walidacja i wzrost regionu](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/matid/core/periodicfinder.py).

**Wniosek adaptacyjny:** ustawienie `radii=np.zeros(N)` wyłącznie na wejściu
SBC nie wystarcza do deklaracji, że analizujemy czystą geometrię punktów.
Prototyp powinien oddzielnie pokazać wynik publicznego API oraz wynik adaptera
usuwającego zależność wewnętrznych kontroli od promieni pierwiastka.

Wykonano dodatkowo małą kontrolę tego konkretnego problemu na instalacji
przypiętej wersji w `/tmp/stmdomains-issue16-deps`: idealna siatka 7×7 punktów,
rozstaw 1, kategoria H, `pbc=False`, `radii=zeros(49)`, `bond_threshold=1.65`,
`pos_tol=0.15`, `max_cell_size=2.5`, `seed=7`. Dla `overlap_threshold=0.5`
nie otrzymano klastrów; dla 0 oraz −0.12 otrzymano jeden klaster 49 punktów.
Pozostałe argumenty zachowano domyślne. Lokalny promień H w ASE wynosi 0.31.
Wynik zgadza się z odczytem kodu: wewnętrzny warunek dla H przy progu 0.5
wymaga odległości co najmniej `0.5 + 2 × 0.31 = 1.12`, więc odrzuca rozstaw 1.
To kontrola propagacji parametrów, nie ocena skuteczności na STM.

W głównej próbie issue 16 ustawiono `overlap_threshold=0` przed pełną
kalibracją na kontrolach syntetycznych i przed oceną referencji TTMAPP.
Wcześniejsze uruchomienia z 0.5 były wyłącznie sprawdzeniem API i nie są
wynikami późniejszego porównania metod. Dla adaptera o zerowych promieniach
próg 0 nie narzuca dodatniego minimalnego rozstawu; w surowym API pozostaje
opisana zależność kontroli prototypu od promieni H.

## Co zachować z wyniku

`Cluster.indices` zawiera końcowe przypisania, a `get_cell()` zwraca prototyp
regionu. `get_dimensionality()` dotyczy topologii badanego układu i nie jest
oceną wiarygodności ani wymiaru obrazu. Klasa nie udostępnia skalibrowanego
prawdopodobieństwa poprawnej domeny.
[Klasa Cluster](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/matid/clustering/cluster.py).

Wewnętrzny `LinkedUnitCollection` przechowuje komórkę prototypową,
komórki lokalne, indeksy dopasowanych punktów, braki i informacje o wzroście.
`get_basis_indices()` zbiera znalezione punkty regionu. Te informacje
pozwalają rozróżnić wsparcie pierwotnego prototypu od końcowego członkostwa
po scalaniu i czyszczeniu, lecz wymagają użycia prywatnego pola `_region`.
[Struktury regionu](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/matid/core/linkedunits.py).

Oficjalne testy oczekują `dimensionality=0` dla poprawnie znalezionych
skończonych płatów przy `pbc=False`. Odrzucanie wszystkich takich klastrów
za pomocą warunku `cluster.get_dimensionality() != 2` byłoby błędem.
Testy obejmują m.in. struktury skończone, niewielki szum, odłączone punkty
i nakładanie atomów, ale nie stanowią testu naszych częściowych oznaczeń STM.
[Testy SBC](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/tests/clustering/test_sbc.py).

## Kontrakt proponowanej próby

Poniższe punkty są projektem naszego eksperymentu, nie deklaracją autorów MatID:

1. Płaskie współrzędne jednej kategorii, jawna jednostka i `pbc=False`.
   Nie zawijać obrazu do torusa. Puste wejście i duplikaty obsłużyć jawnie.
2. Osobne wyniki surowe i adaptera. Zapisać przed i po każdym etapie regiony,
   ich komórki, wsparcie oraz utracone punkty. Nie ukrywać błędów biblioteki
   pod wspólną etykietą „brak porządku”.
3. W adapterze pozostawiać nierozstrzygnięte nakładanie jako niejednoznaczne,
   zachować wszystkie dostatecznie duże komponenty i jawnie opisać wymagane
   wsparcie. Nie dopisywać domen wyłącznie dlatego, że surowy klaster istnieje.
4. Dobór parametrów na kontrolach rozwojowych; osobna ocena kontrolna.
   Brak domen w szumie, dwa rozłączne płaty, brakujące centra, granica
   przesunięcia z szumem i mała różnica kąta są wymaganymi próbami.
5. Porównywać relacje współprzynależności zamiast numerów klastrów.
   Powtórzyć różne ziarna, permutację wejścia, zmianę skali technicznej,
   obrót i usunięcie referencji. Stałe ziarno i sortowanie po stabilnym ID
   rozwiązują odtwarzalność wejścia, ale same nie dowodzą stabilności metody.

## Identyfikacja źródeł

Metadane przypiętego commitu wskazują MatID 2.2.0, Python ≥3.9 oraz zależności
NumPy, ASE, spglib i NetworkX; budowanie korzysta z pybind11.
[Konfiguracja pakietu](https://github.com/FAIRmat-NFDI/matid/blob/5aa27776df0277e2b75af8680bd0faf760cf924a/pyproject.toml).

SHA-256 odczytanych plików:

| Plik | SHA-256 |
| --- | --- |
| `matid/clustering/sbc.py` | `f6db7bf05fcff34167d88e6c221ce4e2f2f3b9ac6d4e3e5f6a2d3b23516b30f8` |
| `matid/core/periodicfinder.py` | `1f7a4bc64140f887bdc24d37812e048b3ecf6a55d5ac7b4c10c731daa4840854` |
| `matid/geometry/geometry.py` | `245782fe81ee9988a138e28ee9954669081bceb62de0ce69f6628d97cb72d7f4` |
| `matid/clustering/cluster.py` | `97e7c6aaaf53d42321cf8a0379e603c6a9153778db7ac96574ea98e09c9dedaf` |
| `matid/core/linkedunits.py` | `8654560bcb9db59d5f7f91fb319820db96a8d9d23c3a0cb152ff963a49d21152` |
| `tests/clustering/test_sbc.py` | `f5076ffe181ace84bf9b91c43ca94964bfaf622ffd2a021ba096e5f737557dae` |

Audyt nie zmienia instalacji biblioteki ani nie mierzy skuteczności na TTMAPP;
poza odczytem źródeł obejmuje wyłącznie opisaną kontrolę idealnej siatki.
Wnioski o jakości muszą wynikać z uruchomionej próby, przy zachowaniu
nieoznaczonych części obrazów jako obszarów bez referencji.
