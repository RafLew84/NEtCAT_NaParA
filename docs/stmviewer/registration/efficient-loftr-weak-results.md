# REG-10: niepewne wyniki na rzeczywistych pomiarach

Data: 2026-11-02. Baza poprawki: `93a3126`; implementacja `7e7084c`.
Status: `done`; użytkownik potwierdził „testy manualne ok” 2026-11-02
po przekazaniu poprawki `b15fb4d`. To odbiór etapu, bez deklaracji
przewagi modelu nad Deep outdoor ani potwierdzenia wszystkich stanowisk.

## Zgłoszenie i decyzja użytkownika

Użytkownik zgłosił odmowę dopasowania swoich rzeczywistych MPP, podczas gdy
syntetyczny film z ticketu 19 przechodzi. Po diagnozie zaakceptował:
**„Tak — pokazuj również niepewne wyniki”**. Zmiana dotyczy kwalifikacji
wyniku do obejrzenia; nie oznacza poprawy dokładności modelu.

## Przyczyna i rozdzielenie wpływów

W poprzedniej wersji jedna para poniżej progu 25% zgodnych wektorów, zbyt
lokalne poparcie albo konkurencyjny ruch przerywały cały łańcuch. Historyczny
Deep Matcher zachowywał słabe oszacowanie jako wynik o niskiej pewności.
Na tych samych punktach historycznego Deep nowe reguły też odrzucały pierwszą
parę MOVIE_4: 8/93 zgodne punkty. Różnicy nie można przypisać wyłącznie modelowi.

Sprawdzenia diagnostyczne przed zmianą:

- Oficjalny EfficientLoFTR i adapter aplikacji zwróciły identyczne tablice
  punktów dla MOVIE_4, źródłowe 3→4: 100 dopasowań, różnica współrzędnych 0 px.
- Pary pierwszych rzeczywistych klatek MOVIE_1, MOVIE_3, MOVIE_4 po odrzuceniu
  dwóch klatek oraz MOVIE_8 odmawiały. Pierwsze pary MOVIE_2 i TTMAPP przechodziły;
  to nie jest test kompletnych tych dwóch filmów.
- Kontrolowane przesunięcie rzeczywistej klatki każdego z sześciu filmów
  o (+7, −5) px przechodziło. Największy błąd osi był poniżej 0,05 px.
  Odczyt MPP, zakres jasności i układ współrzędnych nie wyjaśniają odmów.
- Powiększenie dłuższego boku do 640 px nie odblokowało żadnej z pięciu
  sprawdzonych rzeczywistych par. Nie zmieniono skali wejścia aplikacji.
- Poprzedni konsensus odrzucał 124/361 sąsiednich par MOVIE_4 i wszystkie
  83/83 par MOVIE_8. Wyniki pośrednie i punkty zapisano lokalnie.

Odtwarzalne skrypty i raporty lokalne: `/tmp/reg10-real-diagnosis/`:
`survey.py/.json`, `resolution_probe.py`, `resolution.json`,
`chain_ablation.py/.json`; punkty kolejnych par w `MOVIE_4/` i `MOVIE_8/`.
Osobny test zgodności upstream: `/tmp/reg10-direct-upstream-audit.py`.
To materiały diagnostyczne; katalog tymczasowy nie jest trwałym archiwum.

## Reguły po poprawce

`translation-consensus-v2` zachowuje ten sam model, przygotowanie oryginałów,
jedno globalne XY, maksymalnie 128 deterministycznych hipotez i medianę.
Promień zgodności wynosi 2 px; minimum to 8 poprawnych korespondencji
łącznie i 4 zgodne wektory, jak w historycznym estymatorze Deep.
Surowy score modelu nadal nie jest wagą ani prawdopodobieństwem.

Wynik otrzymuje `low_confidence`, jeśli występuje którykolwiek warunek:

- mniej niż 8 zgodnych punktów lub udział zgodnych poniżej 25%;
- ograniczone poparcie przestrzenne według dotychczasowych progów;
- konkurencyjna grupa z co najmniej 4 punktami i poparciem ≥80% wybranej,
  której XY różni się o więcej niż 4 px.

Wszystkie przyczyny oraz liczby punktów są jawne w diagnostyce. Wynik bez
tych ostrzeżeń nadal ma `manual_review`, nie potwierdzoną poprawność dryfu.
Żaden przypadek nie otrzymuje wymyślonego liczbowego wskaźnika pewności.
Rzeczywisty brak punktów nadal oznacza odmowę, bez zerowego przesunięcia,
zastępowania metody lub interpolacji brakującej relacji.

Niepewność przechodzi przez parę, łańcuch, graf, sesję, ręczne korekty i MPP.
W łańcuchu późniejsza para bez ostrzeżeń nie usuwa wcześniejszej niepewności.
LS zachowuje równe wagi, a Huber nadal wyznacza wagi na podstawie reszt.
Status i score modelu nie nadają wag; słabe pomiary są jawnie oznaczone.
Zastosowany graf pokazuje liczbę takich par, bez przypisywania pewności
poszczególnym pozycjom wyliczonym przez solver.

Stare diagnozy wersji 1 pozostają odczytywalne i nie są przeliczane przy
otwarciu sesji. Nowe obliczenie zapisuje wersję 2 oraz nowe parametry.

## Wynik ponownego użycia zapisanych punktów

| Film | Pary | Bez dodatkowego ostrzeżenia (`manual_review`) | Słabe (`low_confidence`) | Brak oszacowania |
| --- | ---: | ---: | ---: | ---: |
| MOVIE_4 po odrzuceniu dwóch klatek | 361 | 244 | 113 | 4 |
| MOVIE_8 | 83 | 6 | 77 | 0 |

Cztery odmowy MOVIE_4 to bieżące 35→36, 71→72, 85→86 i 115→116
(źródłowe 37→38, 73→74, 87→88 i 117→118). Każda ma tylko trzy zgodne punkty.
Pełny łańcuch zatrzymuje się na pierwszej z nich. Graf może użyć innych
rzeczywiście zmierzonych relacji; połączenie grafu nie potwierdza jakości obrazu.
Raport: `/tmp/reg10-real-diagnosis/v2-cached-aggregate.json`.

## Pełne próby po poprawce

Wykonano ponownie rzeczywiste obliczenia na CUDA, RTX 5090, przez publiczne
ścieżki aplikacji (`diagnostics/efficient_trial.py`). Wyniki i gotowe sesje:
`/tmp/reg10-real-diagnosis/movie4-v2/` oraz `movie8-v2/`.

| Film | Łańcuch | Graf okno 3 | Słabe pary grafu | Huber |
| --- | --- | --- | ---: | --- |
| MOVIE_4 po usunięciu dwóch klatek | odmowa 35→36: 3/91 zgodne | kompletny LS, 24/1080 brakujące relacje | 383/1056 zmierzonych | limit 200 iteracji |
| MOVIE_8 | kompletny, 84 klatki | kompletny LS, 0/246 brakujących relacji | 206/246 | zbieżny po 49 iteracjach |

MOVIE_4: zastosowanie LS, korekta ręczna, sesja, krótki MPP i AVI przeszły.
MOVIE_8: ten sam cykl przeszedł dla LS i Hubera, wraz z przywróceniem
poprzedniego filmu. To próby automatyczne. Później użytkownik potwierdził
odrębnie odbiór ręczny; nie podał szczegółowego porównania jakości ani
osobnego potwierdzenia VLC, Windows lub docelowej karty 8 GB VRAM.

Uruchomienie pierwotnego `/tmp/reg10-movie4-refusal-probe.py` po poprawce
zwraca kod 0: źródłowe pary 1→2, 3→4 i 31→32 mają wynik z ostrzeżeniem,
zamiast wcześniejszej odmowy. Pierwsze dwie klatki nadal należy usunąć
przed właściwą analizą MOVIE_4, zgodnie z informacją użytkownika.

## Sprawdzenia poprawki

- TDD w zatwierdzonych granicach: korespondencje → XY/diagnoza oraz
  wynik → graf/sesja/MPP/ręczna korekta. Przed poprawką odtworzono odmowy,
  utratę statusu i blokady odczytu metadanych bez liczbowej pewności.
- Wszystkie testy `tests/stmviewer`: **712 passed, 8 skipped**, 76,31 s.
  Sześć opcjonalnych prób rzeczywistych wag uruchomiono osobno:
  **6 passed**, 6,72 s, CPU i CUDA. Pozostałe dwa pominięcia dotyczą
  wcześniejszych opcjonalnych testów Deep Matchera.
- Mypy: **90 modułów bez błędów**. Ruff i `git diff --check` czyste.
- Qt offscreen potwierdza widoczność ostrzeżenia, licznika słabych par,
  zachowanie go w MPP oraz możliwość korekty i zastosowania słabej pary.
  To test automatyczny, nie ręczny odbiór GUI.
- [Dwa przeglądy poprawki](reviews/REG-10-weak-results.md): Standards 0 istotnych
  uwag, Spec 0 otwartych uwag; doprecyzowano opis wag Hubera.
- Logi i JUnit: `/tmp/reg10-real-diagnosis/viewer-tests.*`, `real-tests.*`.

## Próba ręczna

1. Uruchom ponownie `python -m stmviewer.main` w `netcat` i wybierz EfficientLoFTR.
2. Otwórz MOVIE_8, uruchom rejestrację. Obejrzyj wynik i oznaczenia słabego
   poparcia. Nie oceniaj poprawności wyłącznie na podstawie zakończenia obliczeń.
3. W MOVIE_4 usuń pierwsze dwie klatki. Obejrzyj pary 1→2 i 29→30:
   można pokazać kandydatów, a szczegóły wyjaśniają słabe poparcie.
   Pełny łańcuch nadal może odmówić przy 35→36; poprzedni aligned zostaje.
4. Oblicz graf z oknem 3. Jeśli jest kompletny, zastosuj go jawnie do filmu;
   sprawdź licznik słabych par i porównaj wizualnie z Deep outdoor.
5. Zapisz i odczytaj sesję oraz krótki MPP aligned. Niepewność i diagnostyka
   mają pozostać dostępne. Ręczna korekta nie usuwa historycznych danych modelu.

[Pełna instrukcja](efficient-loftr-manual.md), [pierwotny raport v1](efficient-loftr-results.md).
