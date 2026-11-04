# 17 — protokół porównania przed obliczeniami

Zapisano 2026-11-04, przed uruchomieniem metody na TTMAPP259–266.
Jedna metoda: łączenie poprawnych dwukierunkowych pomiarów 16,
bez katalogu klas. Oba kierunki są osiowe (modulo 180°); dopuszczamy
zamianę rodzin, lecz dopasowujemy razem kąt i odpowiadający mu rozstaw.
Względna różnica rozstawu to `100 * |a-b| / min(a,b)`.
Każda para pomiarów w całym regionie musi spełniać obie tolerancje.
Kolejność łączenia jest deterministyczna. Zachowujemy limity odległości,
barier obrazu i spójności rastra. Nie interpolujemy odmów pomiarowych.

Zestaw do porównania (bez doboru na podstawie wyników TTMAPP):

| Nazwa | Kąt | Rozstaw | Min. koherencja obu osi | Min. lokalnych punktów |
|---|---:|---:|---:|---:|
| bazowy geometryczny | 12° | 16% | 0,75 | 10 |
| ścisły | 6° | 8% | 0,85 | 12 |
| łagodny | 20° | 25% | 0,75 | 10 |

W każdym: minimum domeny 8, odległość krawędzi 1,5 odstępu NN,
promień maski 0,85 odstępu NN; bazowe bariery aplikacji.
Pomiar 16 dodatkowo wymaga Neff≥8 i stabilności dla trzech promieni.
Obniżanie progu poniżej podłogi pomiaru nie jest oferowane.
Bazowa metoda porównawcza: K5 dopasowane lokalnie na tej samej klatce,
pozostałe ustawienia domyślne aplikacji. Nie używamy przypisań z ZIP.

Kontrole: regularna sieć, dwie orientacje, płynna deformacja/obrót,
skok fazy przy stałym kącie i rozstawie, brakujące centra, luka,
szum, same rzędy, zbyt mało punktów. Jawne etykiety generatora
służą do liczenia domen łączących różne regiony, rozdrobnienia regionów
i krawędzi przekraczających znaną granicę; odmowy raportujemy osobno.
Płynna deformacja nie ma ostrej fizycznej granicy: sprawdzamy ograniczenie
rozpiętości pomiarów w wynikowych regionach, nie fikcyjne etykiety prawdy.

TTMAPP nie ma ręcznej referencji domen: liczby przypisań i różnice metod
nie są accuracy ani poprawą detekcji. Granice/scalenia/podziały względem
prawdy pozostają nieocenione. Skok fazy jest obowiązkową próbą negatywną:
brak rozdzielenia to porażka tej metody. Nie dodajemy estymatora fazy.
