# 18 — freud, Panel A

2026-11-04. Wspólne okno Analiza, metoda **freud — podobieństwo otoczeń**.
Rzeczywiste obliczenia `EnvironmentCluster` 3.6.1; bez K, Auto i treningu.
Odbiór ręczny użytkownika pozostaje do wykonania.

## Działanie i interpretacja

Bieżąca klatka. Parametry: tolerancja, liczba sąsiadów (3–8), zasięg,
dopasowanie obrotu lub odbicia. Edycja jest szkicem; Analizuj liczy w tle i zamyka okno.
Zakładka Geometria określa dodatkowe warunki domen, Zaawansowane — bariery.
Przełącznik Bazowa / Geometria / freud zachowuje ostatni wynik każdej metody
w sesji oraz zoom. Kliknięcie molekuły pokazuje rzeczywistych wybranych
sąsiadów żółtymi odcinkami; Dane oznaczenia zawierają ID, odległości i odmowę.

**Klasy** kolorują wszystkie porównane otoczenia, także bez końcowej domeny.
**Domeny** kolorują tylko przypisania spełniające dodatkowe warunki.
Maski i obrysy zawsze dotyczą końcowych domen. Kolory/numery klas są lokalne
dla wyniku; podobna klasa może obejmować wiele osobnych domen. Klasa nie jest
nazwą struktury ani dowodem periodyczności. Bez dopasowania obrotu zależy
również od orientacji; po jego włączeniu orientacja nadal ogranicza domeny.
Rejestracja 3D biblioteki dopuszcza także **odbicia lustrzane w płaszczyźnie**;
UI i metadane mówią o obrocie/odbiciu. Potwierdza to test asymetrycznego
otoczenia przy tolerancji 0,01. Klasy z tą opcją nie rozróżniają lustrzanych struktur.
Grupowanie freud może przechodzić przez pośrednie podobieństwa; tolerancja
nie jest gwarancją średnicy całej klasy. Geometria domen ma limit całego regionu.

Skala jest wspólna dla klatki: mediana NN w metryce X/Y. Zasięg skończony,
brak periodyczności, brak uzupełniania punktami spoza zasięgu. Odmowy:
za mało sąsiadów, otoczenie ucięte polem, remis na granicy wyboru n.
To **nie dowodzi kompletności detekcji**: brakujące centrum może zmienić
kształt otoczenia i jego klasę także wtedy, gdy nadal jest n innych sąsiadów
w zasięgu. Przycięcie pola i brak wewnątrz sieci są różnymi przypadkami.

Projekt i eksport przechowują **jeden wybrany wynik**, nie historię trzech
metod. Wynik zawiera parametry, wersję biblioteki, kalibrację, przypisania,
sąsiadów, pomiary geometrii i maski. Szkic zapisuje się oddzielnie. CSV
`provisional_class_id` oznacza klasę otoczenia przed tworzeniem domen;
`class_id` i tabela klas liczą końcowe przypisania w domenach. Legenda widoku
Klasy liczy wszystkie porównane otoczenia — są to inne, jawne mianowniki.
Pomiary samodzielnej karty C nadal są sesyjne.

Do 1000 aktywnych centrów, 4 mln pikseli i 3000 oznaczeń wejściowych.
Freud działa w osobnym procesie tego samego interpretera, jeden wątek,
limit porównania 90 s. Anulowanie/timeout nie nadpisuje wcześniejszego wyniku.
Brak pakietu wyłącza wyłącznie możliwość uruchomienia freud; zapisany wynik
można oglądać bez niego. W netcat dodano freud-analysis 3.6.1, rowan 1.3.2,
parsnip-cif 1.0.0, more-itertools 11.2.1; NumPy/SciPy pozostały bez zmian.

## Protokół i wyniki

[Protokół zapisany przed próbą](experiment-18.md). Tolerancje 0,12/0,20/0,30
×NN, czterech sąsiadów, zasięg 2 ×NN, bez dopasowania obrotu. Domyślne progi
domen z 17. Te same kontrole i TTMAPP259–266, bazowe lokalne K5 i geometria
obliczone ponownie na identycznych wejściach. Dodatkowo obrót na kontrolach
1 i 2. Nie dostrajano parametrów do wyników. Zapisane wartości prototypu
HTML były demonstracyjne; obowiązują jednostki NN i ustawienia tej próby.

W tabeli: przypisane molekuły / domeny. TTMAPP bez referencji domen — nie
liczymy accuracy, poprawnych granic ani przewagi metody. Kalibracja z
nagłówka 3,90625 nm/px; bez niezależnego potwierdzenia metrologicznego.

| Klatka | Aktywne | Bazowa K5 | Geometria | freud 0,12 | freud 0,20 | freud 0,30 | Klasy 0,20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 259 | 312 | 120 / 6 | 32 / 1 | 9 / 1 | 10 / 1 | 10 / 1 | 196 |
| 260 | 301 | 118 / 6 | 38 / 1 | 18 / 1 | 20 / 1 | 21 / 1 | 195 |
| 261 | 300 | 127 / 5 | 33 / 1 | 14 / 1 | 15 / 1 | 18 / 1 | 182 |
| 262 | 300 | 115 / 6 | 40 / 1 | 10 / 1 | 11 / 1 | 12 / 1 | 179 |
| 263 | 308 | 115 / 5 | 40 / 1 | 0 / 0 | 0 / 0 | 0 / 0 | 185 |
| 264 | 298 | 146 / 7 | 35 / 1 | 18 / 1 | 18 / 1 | 18 / 1 | 173 |
| 265 | 300 | 155 / 7 | 41 / 1 | 25 / 1 | 25 / 1 | 25 / 1 | 176 |
| 266 | 309 | 147 / 6 | 35 / 1 | 16 / 1 | 16 / 1 | 16 / 1 | 183 |

Domyślne freud porównało 246–261 otoczeń na klatkę i utworzyło 173–196 klas,
lecz tylko 0–25 przypisań do domen. Samo porównanie i segmentacja z gotowym
pomiarem geometrii trwały około 0,74–0,80 s; pomiar geometrii jest dodatkowym
kosztem. Na 259: 49 odmów brzegu, 11 braków sąsiadów, 215 odmów geometrii 2D,
27 zbyt małych/rozdrobnionych składowych. Udział pokolorowanych otoczeń nie
jest jakością detekcji domen.

| Kontrola | Klasy 0,20 | Przypisane / aktywne | Domeny | Błędne scalenia | Podzielone regiony | Pominięte regiony |
|---|---:|---:|---:|---:|---:|---:|
| 1: Sieć 17° | 5 | 63 / 99 | 7 | 0 | 1 | 0 |
| 2: Dwie orientacje | 23 | 19 / 99 | 1 | 0 | 0 | 1 |
| 3: Stopniowa deformacja | 7 | 0 / 99 | 0 | — | — | — |
| 4: Skok fazy | 9 | 0 / 99 | 0 | 0 | 0 | 2 |
| 5: Brakujące centra | 11 | 0 / 92 | 0 | 0 | 0 | 1 |
| 6: Luka | 7 | 0 / 78 | 0 | 0 | 0 | 2 |
| 7: Szum | 42 | 0 / 98 | 0 | 0 | 0 | 0 |
| 8: Rzędy 1D | 185 | 0 / 228 | 0 | 0 | 0 | 0 |
| 9: Trzy centra | 0 | 0 / 3 | 0 | — | — | — |

Referencja pochodzi z generatora; brak narzuconej ostrej granicy przy płynnej
deformacji i brak mierzalnej referencji przy trzech centrach. Pełne dane,
powody odmów i pary przy granicach są w lokalnym `report.json`.

- Regularna sieć daje 7 domen zamiast jednej: istniejące bariery obrazu tną
  również rzędy molekuł. Przy płaskim obrazie test publicznego API daje
  jedną domenę. To ograniczenie całego potoku, nie sukces kontroli obrazowej.
- Dwie orientacje: pominięto jeden region referencji. Skok fazy: pominięto
  oba. Zero błędnych scaleń przy zerowych przypisaniach nie oznacza wykrytej granicy.
- Brakujące centra: freud traci wszystkie domeny (geometria: 27 przypisań,
  3 domeny; bazowa: 8 przypisań, 1 domena). Wymóg pełnych porównywalnych
  otoczeń dodatkowo ogranicza już słaby wynik. Luka również pozostaje bez domen.
- Szum i same rzędy: brak fałszywych domen 2D; liczne klasy otoczeń same
  w sobie nie potwierdzają porządku.
- Dopasowanie obrotu zmniejsza liczbę klas 5→2 na regularnej sieci i 23→19
  na dwóch orientacjach, ale nie poprawia końcowych domen. Czas około
  7,7–7,9 s. Osobny mały test rzeczywistej biblioteki potwierdza łączenie
  obróconych otoczeń dopiero po włączeniu tej opcji.

**Wniosek:** wdrożona próba służy porównaniu otoczeń i diagnozowaniu odmów.
Nie wykazała poprawy detekcji domen. Tolerancja zmienia liczbę klas, ale
wynik nadal ograniczają pomiary geometrii, brakujące centra i bariery.
Nie zastępujemy metody bazowej; granice fazowe pozostają nierozwiązane.

## Sprawdzenia

Testy publicznej analizy, sąsiedztwa, kalibracji, powtarzalności, prawdziwego
freud, anulowania/timeout i zwolnienia procesu, opcjonalnej zależności,
Panelu A, przełączania wyników, projektu, eksportu oraz współrzędnych nakładki.
Przebiegi TDD: publiczne API, panel i zapis projektu RED→GREEN.
Mypy: 105 modułów core/ui/io/analysis PASS.
Pełna regresja **557 testów PASS / 256,20 s** na `85a90e0`. Po przeglądzie
dodano test symetrii rejestracji, doprecyzowano UI/metadane, zachowano podgląd
sąsiadów przy zmianie raw/aligned i wydzielono wspólne pochodzenie wyników 17/18.
Końcowe sprawdzenia tych zmian są w toku.

Natywne GUI X11/netcat: kontrole 1–9 i TTMAPP259–266, rzeczywiste wyniki
trzech metod, Klasy/Domeny, raw/aligned, sąsiedzi, karta C, niezmienny zoom,
okno 1024×768, anulowanie, PNG, zapis/otwarcie oraz zamknięcie podczas
obliczeń **PASS**, bez błędów aplikacji. Źródła pomiarowe pozostały niezmienione.
W pierwszym przebiegu poprawiono tylko pomocniczy skrypt odczytu rozmiaru
okna (`QSize`), po czym pełny przebieg GUI przeszedł. To automatyzowane
sprawdzenie GUI, nie odbiór użytkownika.

Artefakty lokalne: `.scratch/stmdomains-ui-18/` — `report.json`, demo,
projekt, log i PNG. Reprodukcja w netcat:

```bash
python -m stmdomains.tools.freud_trial .scratch/stmdomains-ui-18-repeat --source data/TTMAPP/detection_full.moltrack.json
```

## Test ręczny użytkownika

1. `conda activate netcat`, `python -m stmdomains.main`. Otwórz TTMAPP, klatka 259.
2. Analiza → Analiza… → Bazowa: bieżąca klatka, nowe lokalne K5, parametry bazowe; Analizuj.
3. W tym samym oknie wybierz freud. Zostaw 0,20 ×NN, 4 sąsiadów, 2 ×NN,
   obrót wyłączony; Geometria i bariery bazowe. Analizuj. Oczekiwane:
   **196 klas otoczeń; 10/312 molekuł w jednej domenie**.
4. Przełącz Klasy/Domeny: 252 porównane otoczenia kontra 10 w domenie.
   Kliknij molekułę; zobacz sąsiadów i Dane oznaczenia. Sprawdź także szare
   punkty przy brzegu. Zmień raw/aligned i powiększenie.
5. Przełącz Bazowa/freud (i Geometria po jej obliczeniu): zachowane wyniki,
   bez ponownego dopasowania i zmiany zoomu. Zmień szkic tolerancji na 0,30:
   obraz zmieni się dopiero po Analizuj; wtedy 117 klas i nadal 10/312 w domenie.
6. Włącz dopasowanie obrotu lub odbicia, uruchom i anuluj. Dotychczasowy wynik pozostaje.
   Zamknięcie aplikacji podczas tej pracy powinno zakończyć proces bez błędu.
7. Zapisz wyświetlany wynik do nowego `.stmdomains`, otwórz ponownie,
   wyeksportuj PNG/CSV. Zapis zachowuje jedną metodę, parametry użyte i szkic.
8. Otwórz `.scratch/stmdomains-ui-18/demo/domain-geometry.moltrack.json`.
   Sprawdź dziewięć kontroli według tabeli, również opisane porażki.

## Źródła wejściowe

- `data/TTMAPP/detection_full.moltrack.json`: SHA256 `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.
- `data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`: SHA256 `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`.
- Osobne odciski obrazu i oznaczeń każdej klatki zapisano w raporcie.
