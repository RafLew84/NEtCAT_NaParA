# REG-05 — ręczne sprawdzenie lokalnych fragmentów

Metoda **Deep Matcher + lokalne fragmenty (v1)** zaczyna od dokładnego XY Deep,
bez ECC. Wybiera rozdzielone fragmenty, szuka ich odpowiedników wokół tego
przesunięcia i wyznacza jedno końcowe XY. Prostokąty są wyłącznie diagnostyką:
nie powstaje lokalna deformacja ani prostowanie tearingu.

Obowiązuje [wspólny protokół](manual-protocol.md). [Wyniki wykonanych prób](local-consensus-results.md)
są odrębne od ręcznego odbioru. Wariant eksperymentalny często odmawia na MOVIE_4
oraz MOVIE_8; samo ukończenie obliczeń nie oznacza poprawy względem Deep.

## Uruchomienie i dane

W katalogu `NEtCAT-viewer`, po aktywowaniu `netcat`:

```bash
PYTHONPATH=. python tests/stmviewer/make_local_consensus_fixtures.py
python -m stmviewer.main
```

Generator tworzy sześć MPP i `manifest.json` w `/tmp/stmviewer-reg05-fixtures`.
Opcja `--output` pozwala wybrać inny katalog, także na Windows. Są to wycinki
większej sceny, bez zawijania brzegów. Znane XY oznacza ruch klatki przesuwanej
na bazową: +X w prawo, +Y w dół, w pikselach original.

| Wzorzec | Znany ruch i oczekiwane zachowanie |
| --- | --- |
| `translation.mpp` | 1→2: (+13,25; −8,5), 2→3: (−19,75; +17,75) px; poparcie w kilku częściach obrazu |
| `noisy.mpp` | (+7; −5) px; silny niezależny szum, niski NCC sam nie przesądza o odmowie |
| `stationary-artifact.mpp` | Struktura (+7; −5), silny nieruchomy pas (0; 0); obejrzyj obie grupy |
| `split-motion.mpp` | Góra (+3; −2), dół (−5; +4); jedno XY nie wyrówna obu części |
| `periodic.mpp` | Wzór powtarza się co 8 px; niejednoznaczność albo odmowa |
| `one-band.mpp` | (+7; 0) px; tekstura w jednym pasie nie wystarcza do globalnego poparcia |

Model Deep może odmówić jeszcze przed etapem lokalnym, szczególnie dla wzorów
okresowych i skąpej tekstury. Te filmy służą także sprawdzeniu jawnej odmowy;
nie zakładamy sukcesu modelu na każdym wzorcu. Znane testy samego konsensusu
nie są dowodem działania całego przebiegu z prawdziwym Deep.

Wybierz lokalne wagi zgodnie z [instrukcją Deep Matcher](../deep-matcher-manual.md#lokalne-wagi-i-dane)
i urządzenie Auto, CPU lub CUDA. Deep działa na wybranym urządzeniu, korelacje
fragmentów na CPU. Aplikacja niczego nie pobiera. Brak SciPy, wag lub bibliotek
modelu wyświetla przyczynę niedostępności; nie przełącza metody. Wariant wymaga
skończonych próbek i obu wymiarów obrazu co najmniej 64 px; brakujące próbki
NaN/Inf są jawnie odrzucane przed Deep, a nie wypełniane.

## Para, dokładny start i mapa fragmentów

1. Otwórz `translation.mpp`, wybierz **Porównaj parę…**, klatkę przesuwaną 2
   i **Deep Matcher + lokalne fragmenty (v1)**. Kliknij **Dopasuj automatycznie**.
2. Odczytaj start Deep, końcowe XY oraz liczbę fragmentów zgodnych, odrzuconych
   i bez dopasowania. Przełącz **Wynik lokalny / Start Deep tej próby**:
   są to dwa etapy tego samego przebiegu, bez ponownego obliczania modelu.
   Kadr, gamma, kontrast i zoom powinny pozostać wspólne.
3. Włącz **Pokaż fragmenty i strzałki**. Zielony oznacza poparcie wybranej grupy,
   pomarańczowy wektor odstający, szary brak dopasowania. Prostokąty należą do
   klatki bazowej; strzałka pokazuje lokalne XY minus aktualnie wyświetlane XY.
   To resztkowy ruch, a nie pełne przesunięcie klatki.
4. Wybieraj wiersze tabeli. Sprawdź współrzędne obu wycinków, XY, przyczynę
   przyjęcia/odrzucenia, NCC i wyróżnienie maksimum. Żadna z tych miar nie jest
   procentowym prawdopodobieństwem poprawności. Przy zoomie i przesuwaniu
   prostokąty powinny pozostawać na tych samych strukturach.
5. Użyj **Zachowaj do porównania**, wykonaj inną próbę i przełączaj wynik
   bieżący/zachowany. Poprzednia próba ma pozostać niezmieniona. Osobno porównaj
   Deep→ECC z REG-04; nie jest on częścią inicjalizacji tej metody.
6. Obejrzyj pozostałe wzorce. Przy różnych ruchach góry i dołu informacja
   o konkurujących grupach musi pozostać widoczna, nawet jeżeli podano jedno XY.

Przy odmowie lokalnej pojawia się **Pokaż fragmenty odrzuconej próby**.
Pozwala obejrzeć przyczynę i dokładny start Deep; to diagnostyka odrzuconego
przebiegu, nie udany wynik lokalny. Dotychczasowy wynik bieżący i zachowany
pozostają. Podglądu odmowy nie można zachować jako nowego udanego wyniku ani
zastosować do filmu. Wyłącz podgląd odmowy, aby wrócić do wcześniejszych prób.

## MOVIE_4 i MOVIE_8

W MOVIE_4 przed rejestracją usuń pierwszą klatkę dwa razy. Bieżący numer i
numer źródłowy są odtąd różne; nie zmieniaj kolejności pozostałych obrazów.

| Film | Bieżące pary | Źródłowe pary |
| --- | --- | --- |
| MOVIE_4 | 1→2, 31→32, 118→119 | 3→4, 33→34, 120→121 |
| MOVIE_4, wskazania użytkownika | 29→30, 35→36, 44→45→46, 61→62, 94→95→96→97 | 31→32, 37→38, 46→47→48, 63→64, 96→97→98→99 |
| MOVIE_8 | 1→2, 16→17, 56→57 | Te same numery |

Przy gamma 1 i proporcjach pikselowych porównuj dokładny start z wynikiem.
Oceń co najmniej trzy rozpoznawalne części próbki: **lepiej / podobnie / gorzej /
niejednoznacznie**, albo zapisz odmowę i jej przyczynę. Sprawdź, czy zgodne
fragmenty opisują molekuły czy zakłócenia; liczba zielonych pól nie rozstrzyga.
Resztkowy tearing zanotuj osobno. Nie zmieniaj parametrów zależnie od filmu.

W głównym oknie wykonaj pełny Deep, potem nowy wariant. Przy lokalnej odmowie
w dowolnej parze cała nowa próba zostaje odrzucona; poprzedni kompletny aligned
pozostaje. Nie powstaje film, w którym brakujące pary ukryto wynikami Deep.
Na udanym wzorcu sprawdź pełny aligned, Play, zoom i gamma. W panelu klatki
zapisane jest automatyczne poparcie sprzed ewentualnych ręcznych poprawek.

## Anulowanie, ręczna korekta i eksport

Podczas próby pełnego filmu naciśnij **Anuluj**. Przerwanie następuje w bezpiecznym
punkcie po powrocie bieżącego wywołania biblioteki; poprzedni aligned i ręczne
korekty pozostają. Brak wyniku nie może zmienić się w (0; 0) ani uruchomić innej metody.

Na wzorcu z kompletnym lokalnym aligned zapisz MPP z metadanymi i mały AVI.
Po odczycie MPP sprawdź obrazy, braki danych, geometrię, XY i nazwę metody.
Obejrzyj AVI w VLC. Prostokąty, strzałki i tabela nie mogą trafić do pikseli
MPP ani zwykłego AVI. Eksport korzysta z aktywnego pełnego aligned, nie z próby pary.
Zgodnie z [REG-02a](manual-movie-corrections-manual.md) popraw ręcznie parę,
zastosuj do filmu i sprawdź przesunięcie także dalszych klatek oraz eksport.
Diagnostyka automatyczna pozostaje historią, nie nową oceną ręcznej korekty.

Pełny zapis/odczyt prób z mapą fragmentów pozostaje w REG-07. Zgodność fragmentów
użytych do wyznaczenia XY nie jest niezależną walidacją z REG-06.
Wynik odbioru i decyzję o zachowaniu wariantu zapisujemy w [karcie REG-05](reviews/REG-05.md).
