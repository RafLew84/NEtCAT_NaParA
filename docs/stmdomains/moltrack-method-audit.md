# MolTrack jako porównanie dla ogólnego wykrywania domen

Data: 2026-10-21. Audyt kodu w stanie `2e0c8d1`.
Zakres: odczyt implementacji i porównanie z ustaleniami STM Domains;
bez uruchamiania nowej próby skuteczności i bez zmian kodu MolTrack.

## Potrzeba użytkownika i wniosek

Użytkownik szuka rozwiązania, które ogólnie znajduje domeny, również w innych
układach niż warianty jednej znanej sieci. MolTrack ma służyć jako materiał
porównawczy, nie jako wybrana metoda docelowa. Nie wystarczy dostroić jego
progów lub odtworzyć podziału TTMAPP na BLACK/RED/YELLOW.

Proponowany następny eksperyment ma badać lokalny wzór obrazu i łączyć zgodne
fragmenty w domeny, zachowując osobno typ, orientację, granice i niepewność.
Sprawdzenie odporności na pominięte detekcje jest propozycją badawczą.
Użytkownik nie zatwierdził osobnego wymagania całkowitego działania bez oznaczeń;
dotychczasowy kontrakt importu MolTrack + MPP pozostaje aktualny.

## Co rzeczywiście robi MolTrack

| Ścieżka | Mechanizm w kodzie | Ograniczenie dla STM Domains |
| --- | --- | --- |
| Domeny M6 | Graf sąsiadów z centrów, lokalny porządek sześciokrotny, pewne początki domen, wzrost i łączenie według zgodności orientacji. | Zakłada konkretną symetrię i zależy od jakości wykrytych centrów. |
| Sieć M3/M6 | Porównuje modele trójkrotne, sześciokrotne i mieszane; ocenia zgodność sąsiadów, rozwija domeny i oznacza konflikty. | Rozszerza wcześniejszy model, ale nie odkrywa dowolnej nowej geometrii sieci. |
| Tekstura A/B/C | Histogramy kierunków gradientu w wycinkach wokół molekuł, porównanie z trzema prototypami TTMAPP, wygładzanie sąsiedztwem i odmowa przy słabym dopasowaniu. | Wbudowane wzorce opisują trzy orientacje z jednej akwizycji. Nie jest to ogólny katalog typów. |
| Wspólny moduł Domain Analysis | Najpierw publikuje domeny z analizy geometrii; klasyfikator tekstury otrzymuje tylko molekuły w pełnych domenach. | Tekstura nie może w tej ścieżce samodzielnie odnaleźć domeny pominiętej przez etap geometrii. |

Podstawy w kodzie: [adaptery metod](../../moltrack/ui/domain_backend_adapters.py),
[ustawienia M6](../../moltrack/analysis/m6_settings.py),
[analiza orientacji](../../moltrack/analysis/orientation_domain_analysis.py),
[klasyfikacja M3/M6](../../moltrack/analysis/local_symmetry_evidence_classifier.py),
[zgodność krawędzi](../../moltrack/analysis/lattice_domain_edge_compatibility.py),
[tekstura](../../moltrack/analysis/texture_domain_analysis.py) oraz
[wywołanie klasyfikatora](../../moltrack/analysis/domain_analysis/classifier_frame_execution.py).

W `TTMAPP_TEXTURE_DOMAIN_PRESET` zapisano wprost `Orientation A/B/C`, nazwy
BLACK/RED/YELLOW, trzy histogramy, promień 24 px po dwukrotnym powiększeniu
obrazu i status eksperymentalny. Metadane opisują strojenie na klatkach 250–262
i sprawdzenie czasowe na 263–268 tej samej akwizycji. To nie niezależny dowód
uogólnienia na inne układy. Liczba przestrzennych domen nie jest przy tym
ograniczona do trzech: ta sama etykieta może występować w kilku obszarach.

Nie wszystkie katalogi MolTrack mają narzucone trzy klasy.
[Starszy katalog M6](../../moltrack/analysis/m6_domain_type_classifier.py)
grupuje obserwacje bez stałej liczby grup, ale jego
[miara podobieństwa](../../moltrack/analysis/m6_domain_type_similarity.py)
uwzględnia bezwzględną orientację oraz długość wiązań. Samo przeniesienie
takiego katalogu nie spełnia naszej definicji: obrócona sieć ma zachować typ.

`conflict_boundary` w analizie M3/M6 wynika ze zgodności modeli i orientacji.
Nie jest sam w sobie detektorem granicy przesunięcia dwóch takich samych sieci.
Przesunięcie może pośrednio zmienić sąsiedztwo, lecz kod nie uzasadnia uznania
tego za rozwiązanie problemu z kroku 12. Analiza rzędów działa na już
wyznaczonych domenach; nie stanowi ogólnej segmentacji takich granic.

## Dwie różne powierzchnie w MolTrack

W [klasycznym module powierzchni](../../moltrack/analysis/orientation_domain_footprint.py)
komórki Voronoia są ograniczane polem widzenia i promieniem wokół centrów.
Obszar bez takiego wsparcia nie jest dowodem odsłoniętego podłoża.

W nowszej ścieżce [geometria wejściowa](../../moltrack/analysis/domain_analysis/canonical_geometry.py)
korzysta z masek molekuł lub ich bboxów, a
[publikacja wyniku](../../moltrack/analysis/domain_analysis/module.py)
przydziela wspólne piksele i sumuje te obszary dla domeny. To powierzchnia
oznaczeń, która zależy od ich kompletności i sposobu wyznaczenia.

Żadnej z tych wielkości nie należy automatycznie utożsamiać z uzgodnioną
powierzchnią całego płata warstwy, obejmującą normalne odstępy między molekułami.
Rozdzielenie tych definicji pozostaje konieczne po próbie pokrycia z kroku 10.

## Co warto zachować

Przydatne są rozdzielenie pewnych wnętrz od niepewnych granic, jawna odmowa,
kontrola geometrii raw/aligned i pola obserwacji, pochodzenie wyniku oraz
oddzielenie korekt użytkownika od automatycznej analizy. MolTrack zawiera takie
mechanizmy; nie jest tylko prostym progiem na jednym wskaźniku porządku.
Ich obecność i testy programu nie dowodzą jednak trafności na nowych sieciach.

## Następna próba: wzór obrazu zamiast zamkniętej listy wzorców

To propozycja do wykonania, nie już wybrana lub zwalidowana metoda:

1. Opisywać lokalny wzór w kilku rozmiarach okna: kierunki, rozstaw i kształt
   powtórzeń. Porównać autokorelację z kierunkową analizą tekstury, np. EWT
   lub filtrami Gabora. Nie opierać całej decyzji na dwóch pikach FFT.
2. Ustalać podobieństwa wspólnie dla wybranego zakresu, bez wpisanego katalogu
   A/B/C i bez obowiązkowej symetrii M6. Przy porównywaniu typu uwzględniać
   obrót, ale zachowywać istotne różnice rozstawu; orientację zapisać osobno.
3. Łączyć przestrzennie zgodne fragmenty. Osobno oceniać granice zmiany
   orientacji, pasy bez porządku i niedopasowanie przy tym samym typie i kącie.
   Sam histogram kierunków lub widmo mocy nie wystarczy dla wszystkich granic.
4. Porównać wynik z użyciem obrazu oraz obrazu wspomaganego centrami, w tym po
   kontrolowanym usunięciu detekcji. Brak oznaczeń nie może automatycznie
   stawać się wykrytym podłożem ani granicą.

Bezpośredni precedens STM daje praca
[Bui i in., *Segmentation of Scanning Tunneling Microscopy Images Using Variational Methods and Empirical Wavelets*](https://arxiv.org/abs/1804.08890).
Autorzy oddzielają składową obrazu związaną z jasnością od tekstury; dla
tekstury stosują dwuwymiarowe falki empiryczne i grupowanie, a dla pierwszej
składowej wariant Chan–Vese. Pokazują wyniki na monowarstwach cyjankowych
na Au(111). To uzasadnia próbę tej rodziny metod, nie gwarantuje skuteczności
na TTMAPP ani spełnienia naszych definicji typu i granicy.

Level set może być sposobem prowadzenia granic na podstawie takiego opisu.
Sam wybór reprezentacji granicy nie rozstrzyga, jakie wzory są tą samą siecią,
co jest materiałem ani gdzie brakuje dowodów. Najpierw trzeba sprawdzić cechy.

Korzystamy z obecnych 54 wnętrz i przybliżonych ramek oraz kontroli obrotu,
rozstawu, kontrastu, szumu, defektów i braków centrów. Kolory służą głównie
porównaniu orientacji, nie trzem etykietom typu. Ocenie podlegają odmowy,
nadmierne podziały/scalenia i stabilność przy zmianie zakresu; bez dokładnych
konturów nie deklarujemy błędu całej powierzchni ani dokładności granic.
Potrzebę nowych oznaczeń powinien ujawnić konkretny brak takiego porównania.

## Status i sprawdzenia

Przeczytano implementacje, adaptery i dokumentację techniczną; zweryfikowano
opis publikacji w źródle autorów. Nie uruchamiano metod ani testów aplikacji.
Sprawdzenia tej zmiany obejmują odnośniki i `git diff --check`.
Kroki 10–12 pozostają zakończonymi eksperymentami; odbiór 13 jest otwarty.
Audyt nie przyjmuje metody ani nie rozszerza produkcyjnego zakresu szkieletu.
