# Pokrycie i skala — porównanie wstępne

Data: 2026-10-21. Pytanie:
[Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?](issues/10-coverage-and-scale.md).
Próba na bezpośrednie polecenie użytkownika przed ustaleniem niezależnych
referencji. Użytkownik przyjął wynik wstępny: żadna z pokazanych metod nie
jest gotowa do automatycznego pomiaru; następna próba wymaga referencji.
Pełny zakres ticketu, w tym walidacja na TTMAPP, pozostaje niezakończony.

## Co ma obejmować maska

Po obejrzeniu prototypu użytkownik wyjaśnił, że ciemne pasma w klatce 1
(indeks 0) prawdopodobnie odsłaniają niższą warstwę molekularną. Nie jest to
potwierdzenie wysokości ani oznaczenie wszystkich ciemnych obszarów.
Uzgodnione pokrycie obejmuje materiał **na dowolnym widocznym poziomie**, jeśli
widać molekuły, wraz ze zwykłymi odstępami wewnątrz płata. Nie ograniczamy
pierwszej maski do warstwy wierzchniej ani nie sumujemy powierzchni zakrytych
warstw. Każde miejsce obrazu może wnieść do pola pokrycia najwyżej raz.

Użytkownik zaznaczył, że niższe warstwy bywają ciemne bez widocznych molekuł.
Takich miejsc nie zamieniamy automatycznie ani w podłoże, ani w materiał.
Referencja musi odróżniać pewny materiał, pewne odsłonięte podłoże i obszar
nierozstrzygnięty, wraz z powodem niepewności lub braku danych.
Niepewność samego pokrycia różni się od braku rozpoznanego typu w pewnym
materiale. Zachowujemy zasady
[statystyk częściowych](issues/06-frame-statistics.md): nieznany pełny mianownik
warstwy oznacza niedostępny pełny udział w warstwie, a nie normalizację do
samej rozpoznanej części.

## Materiał i odtworzenie

Źródła: gałąź `prototype/stmdomains-coverage`, pliki
`stmdomains/prototypes/coverage_scale.py`, `.html` i `README-coverage-scale.md`.
Commit podaje ticket. Nie scalać kodu prototypu do aplikacji.

Gotowy HTML:
`/home/rlew/projekty/NEtCAT-domains/.scratch/coverage-and-scale/index.html`.
Obok: `index.json` z metrykami, parametrami i hashami masek, zapis inspekcji
oraz `reference-candidates/` z ośmioma podglądami bez oznaczeń.
To kandydaci do przygotowania referencji, **nie gotowe referencje**.
PNG zawierają kontrast 2–98 i nie zastępują danych pomiarowych z MPP.

Z worktree prototypu, w środowisku `netcat`:

```bash
python stmdomains/prototypes/coverage_scale.py \
  --session /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/detection_full.moltrack.json \
  --mpp /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  --out .scratch/coverage-and-scale/index.html
```

Wejście zgodne z [audytem geometrii](import-geometry-audit.md):

| Plik | SHA-256 |
| --- | --- |
| MolTrack JSON | `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e` |
| MPP | `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66` |

Osiem klatek o indeksach **0, 39, 40, 63, 68, 120, 200, 267**, czyli w UI
**1, 40, 41, 64, 69, 121, 201, 268**. Dawny raport nazywał je indeksami.
Odpowiednio **288, 224, 158, 0, 3, 265, 61, 308** centrów w oryginalnym polu.
Trzy kolejne przypadki to ten sam obraz pierwszej klatki po usunięciu części
oznaczeń: pozostaje 25%, usunięty pas szerokości 80 px albo tylko trzy centra.

Czytnik obraca natywny MPP o 180°, bez odwracania kolejności. Indeksy źródłowe
stosujemy raz; centra z expanded_aligned przenosimy do oryginału zapisanym
globalnym przesunięciem i paddingiem LTRB 224,139,0,13. Nie liczymy nowej
rejestracji. Zapisana niska pewność rejestracji jest ograniczeniem oznaczeń.
Obliczenia dotyczą wyłącznie 256×256 px, bez paddingu. Kalibracja fizyczna
i czas pozostają nieznane; wszystkie odległości podajemy w px. Nie użyto SAM.

## Warianty i kontrola parametrów

| Rodzina | Porównanie | Pozostałe parametry |
| --- | --- | --- |
| Gęstość centrów | Skala z klatki albo wspólna; osobno mnożnik σ 0,45→0,65 | Próg 20% maksimum gęstości |
| Jasna faza obrazu | Rozmycie σ 3→6 px | 45 iteracji, smoothing=2, lambda1=lambda2=1 |
| Wygładzenie konturu | smoothing 2→4 | Rozmycie σ=3 px, pozostałe jak wyżej |
| Wybór fazy | Jasna albo ciemna | Ten sam podział dla σ=3 px, smoothing=2 |
| Lokalna zmienność jasności | Okno RMS σ 3→6 px | Cecha `sqrt(Gσ((G1(I)−G3(I))²))`, ten sam wariant regionowy |

Każda para w scenariuszach zmienia jedną rzecz. Przy wyborze innej rodziny
zmienia się model cechy, więc nie interpretujemy tego jako samej zmiany skali.
Skala centrów jest medianą najbliższych odległości. Wspólne **12,22 px** to
mediana sześciu skal klatek z co najmniej 50 oznaczeniami; ich zakres wynosi
10,82–14,74 px. To założenie robocze z tego samego zakresu danych, nie
niezależnie potwierdzona stała fizyczna ani estymator odporny na każdy ubytek.
W kontrolach wspólna skala jest znanym odstępem 16 px.

Normalizacja obrazu: percentyle 2–98 każdej klatki. Gamma wyłącznie podglądu.
Filtry Gaussa mają warunek brzegowy `reflect`. Wariant regionowy to
[morfologiczny Chan–Vese w scikit-image 0.25.2](https://scikit-image.org/docs/0.25.x/api/skimage.segmentation.html#skimage.segmentation.morphological_chan_vese),
inicjowany powyżej mediany cechy. Wariant RMS dodano wobec zawodności wyboru
jasnej fazy: bada lokalne zmiany jasności niezależnie od znaku kontrastu.
**Nie jest to implementacja Gibou–Fedkiwa** ani porównanie jego skuteczności.

## Kontrole i pomiary błędu

Czternaście kontroli obejmuje: cały płat z brakiem jednej molekuły, trzy
poziomy ubytku oznaczeń i brak oznaczeń, odwrócony kontrast, otwór 48×48 px,
dwa płaty z pasem podłoża 16 px, małą wyspę, ucięcie brzegiem, samo zaszumione
podłoże i stały obraz. Dwie referencje tego samego dodatkowego obrazu
z dwoma poziomami pokazują różnicę między celem „cały materiał” i „wyższy
poziom”. Drugi cel nie jest wyborem użytkownika dla pierwszej maski.

Znane maski wynikają z konstrukcji geometrycznej, a nie z wykrytych centrów.
Jasny płat ma podwyższenie tła i piki molekuł; sprzyja to modelowi dwóch
jasności. Ziarno losowe 20261021. Nie odwzorowano fizyki STM, pełnego zakresu
artefaktów skanowania ani wszystkich nastaw. Nie stroiliśmy na wydzielonej
próbie, nie ma zbioru testowego; to kontrola zachowania, nie walidacja.

- IoU maski, błąd udziału w polu w punktach procentowych.
- Średnia i P95 dwukierunkowych odległości granic w px. Kontur cięcia kadrem
  nie jest fizyczną granicą; jeśli jednej granicy brak, odległość jest niedostępna.
- Scalenia, podziały, pominięte wyspy i dodatkowe komponenty z grafu przecięć.
  Łączność czterech sąsiadów; krawędź grafu przy przecięciu co najmniej
  `max(4 px, 1% pola referencyjnej wyspy)`. Próg jest jawny i umowny, więc
  wynik oglądamy także na maskach; nie jest to przyjęte kryterium odbioru.

Żadna z tych metryk nie jest liczona względem domniemanej referencji TTMAPP.

## Najważniejsze wyniki

| Przypadek | Obserwacja |
| --- | --- |
| TTMAPP, indeks 68: trzy centra | Lokalny d≈90 px: 45,53% / 78,78% pola dla mnożnika 0,45 / 0,65. Wspólna skala: 1,34% / 2,41%. Żadna propozycja nie ustala pełnego pokrycia. |
| TTMAPP, indeks 0: ubytek oznaczeń | Stała skala 0,45: 79,96% ze wszystkich zapisanych centrów → 29,54% po pozostawieniu 25% → 1,38% z trzech. Obraz się nie zmienił. |
| Kontrola: luka oznaczeń | Stała skala 0,45 tworzy dwa komponenty zamiast jednego płata; IoU 0,554, błąd udziału −15,91 pp, P95 51 px. |
| Kontrola: dwa płaty | Zmiana mnożnika gęstości 0,45→0,65 błędnie scala płaty: IoU 0,868→0,788, błąd +6,52→+11,59 pp, P95 5→65,38 px. |
| Kontrola: jasny płat / kontrast odwrócony | Wybór jasnej fazy ma IoU 0,982 / 0,008. Odległość granicy P95 nadal wynosi 1 px: sama zgodność granic nie rozstrzyga, która strona jest materiałem. |
| Kontrola: RMS przy odwróceniu kontrastu | Maski obu ustawień RMS pozostają bitowo identyczne. Dla okna 3 px IoU 0,924, ale defekt robi dziurę: P95 64 px. Niezależność od znaku kontrastu nie wystarcza. |
| Kontrola: mała wyspa | Jasna faza σ3→6: IoU 0,866→0,799. RMS: 0,251 / 0,307; część wnętrza jest tracona. |
| Kontrola: puste podłoże z szumem | Jasna faza proponuje 50,76% / 48,47% pokrycia; RMS 45,14% / 44,26%, przy prawdziwym zerze. Normalizacja wzmacnia także szum. |
| Kontrola: stały obraz | Warianty obrazu zwracają brak propozycji. Brak oznaczeń daje brak propozycji z centrów. Nie utożsamiamy tego z potwierdzonym zerem. |

Na TTMAPP indeks 0 zmiana rozmycia 3→6 px daje 48,58%→51,25% pokrycia
i 31→11 komponentów. Osobna zmiana smoothing 2→4 przy σ=3 px daje
48,58%→44,44% i 31→8 komponentów. Spadek liczby komponentów nie dowodzi
poprawy; po wyjaśnieniu znaczenia pasm tym bardziej nie można uznać jasnej
fazy za całość materiału.

Otwór w kontroli zachowuje się inaczej niż luka oznaczeń. Dla jasnej fazy
σ3/6 IoU wynosi 0,978/0,992, a P95 1/2 px. Płat ucięty brzegiem zachowuje
IoU 0,998/0,997, lecz jest to jedna prosta geometria z jawnym kontrastem.
Nie przyjmujemy na tej podstawie parametrów dla rzeczywistego obrazu.

## Warunki braku wyniku i dalsza próba

Wnioski do następnej próby, **bez gotowego automatycznego walidatora**:

1. Z brakujących centrów nie wyznaczamy podłoża. Wspólna skala ogranicza
   rozrost obwiedni z trzech punktów, ale nie odtwarza materiału bez detekcji.
2. Stały, niedostępny lub częściowo niefinite obraz nie daje pełnej propozycji
   z użytego wariantu. Brak podziału na dwie fazy także nie potwierdza zera.
3. Podział szumu lub dwóch jasności nie jest dowodem obecności warstwy.
   Rozbieżne warianty i nieznany związek kontrastu z materiałem wymagają oceny,
   a nie wyboru wariantu z oczekiwaną liczbą wysp.
4. Na materiale z wieloma poziomami potrzebne są przykłady widocznych molekuł
   obu poziomów oraz ciemnych obszarów bez rozstrzygnięcia. Sam próg jasności
   albo globalny model dwóch faz nie otrzymuje uprawnienia do ich rozpoznania.
5. Obszary nierozstrzygnięte zachowujemy osobno. Nie uznajemy wszystkich
   pikseli spoza pewnego materiału za pewne podłoże.

Ostrzeżenie przy mniej niż 12 centrach i wybór co najmniej 50 centrów do
wspólnej skali to pomocnicze reguły prototypu, nie zatwierdzone minima danych.
Nie ustalono progów kontrastu, separacji, stabilności parametrów ani wielkości
wyspy, które uprawniałyby do automatycznego pomiaru.

Po tej próbie użytkownik dostarczył
[częściowe referencje domen](partial-domain-reference-audit.md): przybliżone
ramki wybranych obszarów klatek 250–268. Przygotowano ich robocze wnętrza,
bez uznawania reszty obrazu za podłoże. Nie są to pełne maski pokrycia.
W [pytaniu o referencje](issues/04-reference-and-quality.md) trzeba ustalić
pochodzenie i geometrię, granice materiału i niepewność, przykłady podłoża,
podział do strojenia i sprawdzenia oraz sposób ograniczenia wpływu obejrzanych
propozycji na ręczne oznaczenia. Nie traktować obecnych detekcji/SAM jako referencji.

Następny kandydat powinien wykorzystywać informacje odróżniające materiał
od podłoża mimo zmiany poziomu jasności i szumu: porównanie lokalnej struktury
z pewnymi fragmentami materiału/podłoża, z możliwością odmowy. To kierunek
do sprawdzenia po referencjach, nie wybrany algorytm. Dalszy wariant level set
ma sens dopiero ze zdefiniowaną cechą/energią i rzeczywistą implementacją;
nie przypisujemy obecnych błędów całej rodzinie metod ani Gibou–Fedkiwowi.

## Koszt i wykonane sprawdzenia

Python 3.12.12, NumPy 2.2.5, SciPy 1.15.2, scikit-image 0.25.2.
Pierwszy zestaw 23 obrazów: dwa przebiegi 28,59 i 26,88 s; szczyt RSS 464,95
i 588,71 MiB. RSS obejmuje pełny odczyt MPP/JSON i generowanie artefaktu,
nie jest pomiarem pamięci samego algorytmu. Dodatkowe dwa cele maski obrazu
wielopoziomowego dołączono po uwadze użytkownika. Ostateczny przebieg
25 obrazów: **28,91 s, 589,81 MiB RSS, HTML 2,38 MiB**. Ponowne obliczenie
pierwotnych 23×10 wariantów dało identyczne maski, dostępność i metryki.

W pierwszym przebiegu: stała skala gęstości 1,16–1,48 ms na obraz;
jasna faza σ3 162–203 ms; smoothing=4 295–347 ms; RMS σ3 165–200 ms.
To lokalne pomiary pojedynczych przebiegów, bez benchmarku innych rozmiarów,
pełnej serii, sprzętu ani pamięci przeglądarki. Interfejs wyświetla już
obliczone wyniki; szybkość przełączania nie mierzy szybkości segmentacji.

Sprawdzono zgodność liczby centrów z audytem/pilotażem i SHA-256 wejścia.
Maski metod obrazu nie zmieniły się przy usuwaniu oznaczeń. Maski RMS
zachowały się bitowo po odwróceniu kontrastu kontrolnego. Zapis inspekcji HTML
obejmuje scenariusze, listy klatek/metod, gamma, przełączanie nakładek,
kliknięcie metryki i jawny brak propozycji. Obejrzano zrzuty QtWebEngine.
Kontrola dokumentacji i `git diff --check` nie zastępuje oceny naukowej.

Nie dodawano testów prototypu, nie zmieniano produkcji ani nie uruchamiano
testów aplikacji. Nie oceniono dokładności na TTMAPP, niezależnych akwizycjach,
skalowania pamięci, anotacji niepewności ani zatwierdzonej odmowy wyniku.
