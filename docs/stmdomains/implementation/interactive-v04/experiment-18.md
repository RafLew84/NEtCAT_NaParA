# SD-V4-18 — protokół próby freud

2026-11-04, zapis przed oceną TTMAPP. Wybrany Panel A. Baza `e4fb4aa`.
Istniejące granice testów: publiczna analiza klatki, sterowanie sesją/GUI,
zapis i eksport; ich zachowania wynikają z kryteriów ticketów 06/13/14/16/18.

## Metoda i wejście

Jeden wariant: `freud.environment.EnvironmentCluster` 3.6.1. Porównanie
konfiguracji najbliższych sąsiadów; bez KMeans, Auto ani treningu.
[Dokumentacja autorów](https://freud.readthedocs.io/en/stable/modules/environment.html#freud.environment.EnvironmentCluster).
Biblioteka porównuje wektory otoczeń o tej samej liczbie punktów, używając
progu odległości. Dopasowanie obrotu jest osobnym, kosztownym wariantem.

Aktywne centra po obsłudze duplikatów i pola jak w 16; metryka uwzględnia
kalibrację X/Y. Normalizacja wszystkich położeń jedną medianą najbliższego
sąsiada (NN) klatki, bez osobnego skalowania każdego otoczenia. Tolerancja
i maksymalny zasięg mają jednostkę ×NN; wynik zapisuje także skalę i kalibrację.

Otoczenie: najbliższe n punktów w skończonym zasięgu. Niepełne otoczenie,
ucięcie obserwowanego otoczenia przez brzeg oraz remis na granicy wyboru
n sąsiadów mają odmowę. Położenia przy przeciwległych brzegach nie są
sąsiadami: jawne listy par i wyłączona periodyczność. Porównanie klas
obejmuje wszystkie pary pełnych otoczeń w klatce, nie tylko przestrzennych
sąsiadów. Etykieta podobieństwa pozostaje lokalna, nie jest typem struktury.

Domeny: ta sama klasa + dwa wiarygodne kierunki 16 + zgodność geometrii
w całym regionie + ograniczenie odległości i bariery. Używamy istniejącego
rastra i spójności z 17; klasy mogą obejmować osobne domeny. Zgodność fazy
nie jest osobno sprawdzana. Skok fazy jest obowiązkową kontrolą, a jego
nierozdzielenie porażką próby, także gdy odmówiono wszystkich przypisań.

## Zamrożone ustawienia i porównanie

- Tolerancje: **0,12 / 0,20 / 0,30 ×NN**; bazowa 0,20.
- **4 sąsiadów**, maksymalny zasięg **2 ×NN**, bez dopasowania obrotu.
  Równe odległości na granicy wyboru są odmawiane, a nie rozstrzygane losowo.
- W kontrolach obrotu dodatkowo ten sam wariant z dopasowaniem obrotu.
  Nie zmieniamy go klatka po klatce dla uzyskania lepszego obrazu.
- Domena: 12°, 16%, koherencja ≥0,75, lokalnie ≥10 punktów; minimum 8
  molekuł, krawędzie do 1,5 NN, promień rastra 0,85 NN, bazowe bariery.
- Bazowa: lokalne K5, domyślne ustawienia; dodatkowy punkt odniesienia 17.
  Te same obrazy i oznaczenia; bez gotowych modeli/przypisań ZIP.

Kontrole generatora 17: jedna sieć, dwie orientacje, deformacja, skok fazy,
brakujące centra, luka, szum, same rzędy i za mało danych. Dodatkowe małe
kontrole sąsiedztwa obejmują brzegi, zasięg, remis i zmianę kolejności ID.
TTMAPP259–266: wspólne ustawienia powyżej, eksploracyjnie, bez nowych etykiet.

Raport: klasy otoczeń, końcowe domeny/przypisania, powody odmów, czas,
błędne scalenia, podziały i pominięcia na kontrolach z referencją. Nie
utożsamiamy udziału przypisań z accuracy. TTMAPP nie ma pełnej referencji
domen i pochodzi z jednej, wielokrotnie oglądanej akwizycji.

## Uruchamianie

Środowisko netcat. Dodano freud-analysis 3.6.1, rowan 1.3.2,
parsnip-cif 1.0.0, more-itertools 11.2.1; istniejące NumPy/SciPy bez zmiany.
Brak freud ma blokować wyłącznie jego analizę. Nowa opcjonalna zależność
jest dokumentowana lokalnie; wspólna konfiguracja pozostaje w sesji integracyjnej.

Kosztowna natywna rejestracja działa w osobnym procesie tego samego
interpretera, z anulowaniem i limitem czasu. Timeout jest błędem obliczeń,
nie wynikiem zerowym. Wcześniejszy wynik pozostaje dostępny. Przed
porównaniem nie dobieramy ustawień na podstawie TTMAPP.

## Uściślenie rejestracji po przeglądzie implementacji

2026-11-04: test asymetrycznego otoczenia wykazał, że rejestracja 3D freud
łączy też **odbicia lustrzane otoczeń płaskich**, mimo `Box.is2D=True`.
Opcja w UI nazywa się „Dopasuj obrót lub odbicie otoczeń”. W wyniku zapisujemy
`registration_transform=proper_3d_rotation_including_planar_reflection`
albo `none`. Jest to doprecyzowanie rzeczywistej symetrii biblioteki;
ustawienia porównań i wcześniejsze wyniki pozostają te same. W szczególności
wszystkie TTMAPP policzono bez rejestracji. Nie wnioskujemy z tych klas
o rozróżnianiu struktur lustrzanych ani o typie struktury.
