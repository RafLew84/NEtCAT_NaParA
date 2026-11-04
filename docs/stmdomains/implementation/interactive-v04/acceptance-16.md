# SD-V4-16 — pomiar geometrii, odbiór

2026-11-04. Baza `901e8d3`, implementacja `c4b6c70`, poprawki przeglądu
`009f38f` i `97988c2`. Gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. Wybrany przez użytkownika wariant C:
pływająca karta, zwijana i przenoszona między stronami obrazu.
[Definicja pomiaru i ustawienia](geometry-method-v1.md), [review](review-16.md).

## Uruchomienie i test ręczny użytkownika

W katalogu projektu, w uzgodnionym środowisku:

```bash
conda activate netcat
python -m stmdomains.main
```

Nie trzeba instalować zależności. Użyty interpreter:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`, przejdź do klatki 259.
   Jeżeli chcesz również podsumowania domen: w **Analiza → Analiza…**
   dopasuj K5 na zakresie 259–268 i oblicz bieżącą klatkę. Bazowy wynik
   tej konfiguracji: 105/312, 5 domen. Sam pomiar geometrii nie wymaga klas.
2. Wybierz **Analiza → Geometria… → Pomierz geometrię**. Obliczenia dotyczą
   wyłącznie bieżącej klatki, mają postęp i **Anuluj**. Po zakończeniu kliknij
   molekułę. Karta pokazuje kierunek rzędów, rozstaw poprzeczny i koherencję;
   przewiń, aby zobaczyć wsparcie, promień, stabilność i źródło skali.
3. Zakładka **Domena** opisuje pomiary molekuł należących do aktualnie
   wyświetlanej domeny: średnia osiowa, rozrzut, n i rozstaw. Molekuła bez
   domeny dostaje wyjaśnienie. Zmiana wersji bazowego wyniku zmienia grupę
   podsumowania, ale nie same pomiary położeń.
4. **⇄** przenosi kartę, **Zwiń/Rozwiń** zmienia tylko kartę, **×** ukrywa
   kartę i geometrię. Przewijanie działa także w oknie 1024×768. Kierunki
   i otoczenie można przełączać niezależnie; opcja wszystkich molekuł
   pokazuje kierunki tylko tam, gdzie pomiar je rozstrzygnął.
5. Zmień zoom i raw/wyrównany. Kreski i elipsa otoczenia powinny przemieszczać
   się z molekułą; liczby oraz przypisania klas/domen pozostają identyczne.
   Przejście do niepomierzonej klatki nie przenosi starego wyniku.
   Powrót do pomierzonej klatki w tej sesji przywraca jej pomiar.
6. Otwórz przygotowany plik
   `.scratch/stmdomains-ui-16/demo/geometry.moltrack.json`.
   Klatki 1/2: środkowa molekuła 50, kąty 17°/47°, rozstawy 14 i 10 px.
   Klatka 3: dwa pola orientacji. Klatka 4: przesunięcie fazy bez zmiany
   kąta i rozstawu daleko od granicy. Klatki 5/6: braki centrów/przerwa.
   Klatka 7: losowe centra bez kierunków; 8: same rzędy co 14 px,
   jeden kierunek; 9: trzy centra, brak pomiaru. Brzegi regularnych pól
   mogą odmawiać z powodu mniejszego wsparcia lub niestabilności.
7. Otwórz `.scratch/stmdomains-ui-16/demo/anisotropic.moltrack.json`:
   X=0,6 nm/px, Y=1,2 nm/px. Środkowa molekuła: fizyczny kąt 17°,
   rozstawy 14/10 nm. Kąt na ekranie jest inny wskutek nierównej skali X/Y.
8. Rozpocznij pomiar i anuluj albo zmień klatkę; nie może pojawić się
   spóźniony wynik. Zamknij program podczas obliczeń. **Dane i ustawienia
   pomiaru…** pokazują rzeczywiste parametry, kalibrację, ID i skrót wejścia.

Kontrole są gotowe lokalnie. Można je odtworzyć w `netcat` poleceniem
`python -m stmdomains.tools.geometry_demo`; nie zawierają gotowych wyników
ani modeli. Odbiór ręczny użytkownika 16 **oczekuje**.

## Wykonane sprawdzenia

- TDD na API pomiaru, kalibracji, podsumowaniu i integracji zadania/UI.
  Kontrole obejmują obrót, zawijanie 179°/1°, nierówną skalę, brak kalibracji,
  szum, rzędy, słabe wsparcie, anulowanie, bufor klatek, niezależne warstwy,
  zachowanie bazowego wyniku i przewijanie całej karty.
- Pełna regresja aplikacji: **530 PASS** (288 + 242, 134,07 s / 99,11 s).
  Dwie rozłączne grupy 76 plików, Qt offscreen, OMP/MKL/OPENBLAS=1.
- Kontrola typów **101 modułów PASS**. Wszystkie nowe/zmienione pliki kodu
  i testów poniżej 1000 linii; największy `session_controller.py`: **736**.
- Wykonano automatyzowaną próbę **natywnego GUI X11/xcb**, nie tylko offscreen:
  9 kontroli i anizotropia, TTMAPP 259–266, obliczenia, wskazanie molekuł,
  podsumowanie domeny, zmiana strony, zwinięcie, zoom, raw/aligned,
  małe okno, anulowanie i zamknięcie. Końcowa próba `native_layers.py`
  sprawdza też kliknięcie centrum na obrazie, samą warstwę otoczenia
  i zamknięcie podczas działającego zadania geometrii. Zrzuty obejrzano. Znalezione przycięcie
  długiego tekstu naprawiono i ponowiono próbę; dodatkowy test regresyjny
  sprawdza dostęp do końca opisu.
- Dodatkowy natywny przebieg ujawnił powtarzalną blokadę w
  `threadpoolctl.ThreadpoolController` / `dl_iterate_phdr` podczas pracy Qt.
  Przerwane przebiegi nie są PASS. `97988c2` usuwa skanowanie bibliotek
  z wątku geometrii: małe kontrakcje liczone przez `einsum(optimize=False)`
  bez pul BLAS. Wzory się nie zmieniły. Test granicy biblioteki zabezpiecza
  brak skanowania. Natywna próba po poprawce PASS, także zamknięcie podczas
  pomiaru; ponowiono TTMAPP i pełną regresję. Jeden błąd dodatkowego harnessu
  wynikał z kliknięcia pustej części szerokiego checkboxa; współrzędną
  poprawiono, po czym sprawdzono rzeczywisty niezależny przełącznik.
- GUI pozostawało responsywne w końcowej próbie; pomiar TTMAPP około
  **1,9–2,0 s** na klatkę. Timer GUI działał podczas obliczeń.
  Pomiary czasu są obserwacją tego komputera, nie gwarancją wydajności.
- SHA256 źródłowego MPP i JSON nie zmieniły się. Guard odczytów nie wykazał
  dostępu do paczek v0.4 ani wcześniejszych modeli. Nie zmieniano wspólnych
  aplikacji ani konfiguracji; brak potrzeb integracyjnych.

Artefakty lokalne: `.scratch/stmdomains-ui-16/` — `report.json`,
`gui_smoke.py`, `gui-smoke.log`, `tests-1.log`, `tests-2.log`, listy testów,
zrzuty `ttmapp-card.png`, `ttmapp-domain.png`, `ttmapp-details-bottom.png`,
`ttmapp-raw.png`, `ttmapp-aligned.png`, `small-window.png`, kontrole i README.

## Wynik próby TTMAPP

Wejście: `data/TTMAPP/detection_full.moltrack.json` oraz
`data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`. K5 dopasowane na 259–268,
parametry bazowe. Metoda i progi geometrii zapisane przed oceną TTMAPP;
nie dostrajano ich do tej serii. Skróty wejścia każdej klatki w `report.json`.
Dla 259: `27c691c573b9168f6bebdc4c6b823551b72827dbc2c2beb812c9e6a915b9155e`.

| Klatka | Dwa kierunki | Jeden kierunek | Nierozstrzygnięte | Za małe wsparcie/pominięte | Bazowo przypisano | Domeny |
|---|---:|---:|---:|---:|---:|---:|
| 259 | 40 | 29 | 221 | 22 | 105 | 5 |
| 260 | 42 | 36 | 202 | 21 | 84 | 3 |
| 261 | 43 | 33 | 200 | 24 | 112 | 5 |
| 262 | 53 | 31 | 191 | 25 | 113 | 6 |
| 263 | 45 | 33 | 199 | 31 | 102 | 4 |
| 264 | 44 | 32 | 198 | 24 | 139 | 6 |
| 265 | 51 | 45 | 176 | 28 | 136 | 6 |
| 266 | 46 | 48 | 194 | 21 | 141 | 6 |

Kolumny geometrii obejmują wszystkie oznaczenia, także pominięte duplikaty;
kolumna przypisań podaje osobno liczbę molekuł przypisanych przez bazową segmentację.
**Przypisania przed/po są identyczne**. Nie ma nowego scalenia,
rozdrobnienia ani przesunięcia granicy przez włączenie geometrii.
Nie oceniano trafności granic ani accuracy pomiaru na TTMAPP: brak pełnej
referencji geometrii. Wzrost liczby kierunków nie jest poprawą detekcji.

Kontrole: regularna sieć 63/99 lokalnych wyników 2D (reszta brzegi),
dwa pola 126/198; losowe centra 0/120 kierunków, same rzędy 62 wyników
jednokierunkowych i 0 dwukierunkowych z 368 oznaczeń; trzy centra 0 kierunków.
Granica przesunięcia pozostaje niewykrywana przez sam kąt/rozstaw;
pomiar nie rości sobie zakresu nowego detektora tej granicy.

## Ograniczenia

Pomiary opisują periodyczność centrów oznaczeń, nie wiarygodność detekcji
molekuł ani chemiczną tożsamość fazy. „Sieć 2D” oznacza dwa lokalnie stabilne
kierunki periodyczności przy zapisanych progach. Progi nie są kalibracją
prawdopodobieństwa poprawności. Rozstaw wzdłuż rzędów nie został osobno
wyznaczony i pozostaje brakującą wartością.

Nagłówek tego MPP daje X=Y=3,90625 nm/px (amplituda 1000 nm / 256).
To przeliczenie z metadanych, **bez potwierdzenia skali metrologicznej**;
UI pokazuje tę informację. Zły nagłówek może dać fizycznie błędne nm.
Wymiary canvasu wyrównanego 480×408 nie służą do kalibracji.

**Pomiary są sesyjne**: przełączanie klatek je zachowuje; otwarcie nowego
źródła lub zamknięcie programu usuwa je. Zapis projektu i eksport domen
z 13/14 nie obejmują tej diagnostyki; karta mówi o tym wprost. Ustawienia
pomiaru w 16 są stałe; 17 będzie odrębną metodą domen z tolerancjami.
