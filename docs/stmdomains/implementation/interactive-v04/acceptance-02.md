# SD-V4-02 — oznaczenia molekuł i zapisana geometria

Data: **2026-11-02**. [Ticket 02](02-molecules-and-geometry.md) wykonano na
`domains/interactive-v04-ui`, baza `152146a`, implementacja **`df5c48b`**.
Raport i aktualizacja planu: **`3572b6d`**. Użytkownik potwierdził pomyślny
ręczny odbiór tej wersji 2026-11-02 słowami „testy manualne ok”.

## Uruchomienie i test ręczny

W katalogu `/home/rlew/projekty/NEtCAT-domains`, w środowisku **netcat**:

```bash
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`. Jeśli pojawi się
   potwierdzenie daty MPP, sprawdź ścieżkę i wybierz **Użyj tego pliku**.
   Zapis otwiera ostatnią klatkę. Wybierz klatkę **1** numerem lub suwakiem.
2. **Centra**, **Ramki**, **Maski / obrysy** przełączają niezależne warstwy.
   Domyślnie widać centra. Włącz maski i przeciągnij **Krycie masek** od 0
   do 100%; przy 0% obraz pozostaje widoczny bez maski, ramki i centra zachowują
   własne ustawienia. Kolor oznacza warstwę wejściową, nie domenę ani klasę.
3. Kliknij oznaczenie: pod obrazem pojawią się ID, pochodzenie i dostępna
   pewność. **Dane oznaczenia…** otwiera zapisane metadane tylko do odczytu.
   Klikanie nie zmienia flagi `selected` ani pliku wejściowego.
4. Powiększ i przesuń obraz, zmień rozmiar okna. Oznaczenia mają pozostać
   na tych samych molekułach. Przełącz **Oryginał / Wyrównany** kilka razy:
   widok dopasuje się do płótna, obraz i nakładki zmienią układ razem.
   Zmiana klatki o tych samych wymiarach zachowuje zoom.
5. W widoku wyrównanym szare dopełnienie leży poza polem pomiarowym.
   Przerywana granica pokazuje oryginalne pole; ciemniejsze tło wewnątrz
   oddziela brak skończonej próbki od dopełnienia. Płótno TTMAPP ma
   **480×408 px**, obrazy oryginalne **256×256 px**.
6. Przejdź przez poniższe klatki w obu widokach. Brak oznaczeń nie może
   pozostawiać nakładki z poprzedniej klatki. Od klatki 2 widoczna jest
   zapisana **niska pewność** rejestracji; nie blokuje ona podglądu.

| Klatka w UI | Ramki detekcji | Dostępne maski |
| --- | ---: | ---: |
| 1 | 288 | 288 |
| 40 | 224 | 224 |
| 41 | 158 | 0 |
| 64 | 0 zapisanych rekordów | 0 zapisanych rekordów |
| 68 | 0 zapisanych rekordów | 0 zapisanych rekordów |
| 69 | 3 | 0 |
| 268 | 308 | 0 |

7. Przygotuj małe przypadki do sprawdzenia braków:

   ```bash
   python -m stmdomains.tools.annotation_demo
   ```

   Pliki powstaną w `.scratch/stmdomains-ui-02/demo/`, wraz z `README.txt`.
   Otwieraj kolejno:

   - `registered.moltrack.json`: dwa obrazy 48×32 px; molekuła A ma centrum
     `(12,9)`, B `(34,23)` w oryginale. Wyrównana druga klatka przesuwa A
     do `(12.5,10.25)`, ma niską pewność i płótno 51×34 px.
   - `bad-mask.moltrack.json`: uszkodzona maska A, ale poprawne centrum,
     ramka i obrys pozostają. **Informacje o klatce…** podaje przyczynę.
   - `no-registration.moltrack.json`: wyrównanie niedostępne; poprawne
     oznaczenie `raw-A` pozostaje. Oznaczenie zapisane tylko w układzie
     wyrównanym nie jest nakładane na oryginał bez znanego przesunięcia.
   - `empty.moltrack.json`: jawna informacja o zapisanej pustej liście.
   - `missing.moltrack.json`: informacja o braku danych. Żaden z tych
     przypadków nie jest deklaracją braku molekuł na powierzchni.

**Ręczny odbiór 02 potwierdzony przez użytkownika 2026-11-02 (`3572b6d`).**
Nowe warstwy i geometria zostały odebrane po wcześniejszym odbiorze 01 i suwaka.

## Wykonane sprawdzenia

W istniejącym `netcat`, bez instalacji:

- **49 nowych testów**: 22 rejestracji, 24 oznaczeń/kodowań masek oraz
  3 integracyjne GUI. Testy obejmują publiczne interfejsy i rzeczywisty MPP,
  niekwadratowy obraz, ułamkowe przesunięcia, ID/klatki, brakujące sekcje,
  duplikaty, maski, fallback ramek, kliknięcie, krycie, resize i zoom.
- **Pełny zestaw STM Domains: 279 passed, bez pominięć, 12,17 s**, uruchomiony
  po przeglądzie kodu. To testy tej aplikacji, nie innych programów repozytorium:

  ```bash
  QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
  ```

- Mypy **23 pliki PASS**, sprawdzany także w trakcie implementacji:

  ```bash
  python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
  ```

- Limity kodu **17 plików PASS, maksimum 274 linie**:

  ```bash
  python -m stmdomains.tools.check_code_size --base 152146a
  ```

- Rzeczywiste GUI X11/xcb: **14 par klatka/widok** z powyższej tabeli oraz
  **5 plików kontrolnych**. Sterowanie Qt sprawdziło wybór widoku, nawigację,
  nakładki, kliknięcia, komunikaty i zakres suwaka. Obejrzano zrzuty raw,
  aligned i klatki bez oznaczeń. To techniczna próba agenta, odrębna od
  ręcznego odbioru użytkownika.
- SHA-256 JSON i MPP przed/po próbie pozostały identyczne. Nie wykonywano
  ponownej detekcji, rejestracji ani analizy domen.
- Lokalne odnośniki dokumentacji oraz `git diff --check`.

Artefakty lokalne: `.scratch/stmdomains-ui-02/gui_smoke.py`, `gui-smoke.json`,
zrzuty `frame-*-*.png`, `demo-*.png` i przykłady `demo/`; pozostają poza Git.

## Geometria, pamięć i ograniczenia

Padding wyznacza cała zapisana rejestracja, a obrazy i oznaczenia korzystają
z indeksów roboczych zachowujących mapę MPP. Dla pierwszej klatki TTMAPP
początek wynosi `(224,139)`; 267 wyników ma niską pewność. Raw nie jest ponownie
odbijany. Obraz wyrównany powstaje z oryginału interpolacją liniową z NaN,
maski najbliższym sąsiadem z False. Bboxy i polygony są przesuwane bez
zaokrąglania; przycinane jest rysowanie, nie zapisane współrzędne.

Raw i aligned używają zakresu kontrastu 2–98 oryginalnej klatki. Granica
pola pomiarowego nie jest tożsama z ważnością interpolowanych próbek.
Przełączanie nie kumuluje interpolacji. Kodowane dane i historyczne metadane
pozostają zachowane; masek historycznych nie materializuje się do podglądu.

Cache oznaczeń ma maksymalnie **2 wpisy klatka/widok i 64 MiB rastrów**;
cache obrazów do podglądu **3 wpisy i 32 MiB**. Większy pojedynczy wynik
można wyświetlić bez utrwalania w cache. Aktualnie wyświetlany wynik,
chwilowe bufory i obiekty GUI mają osobny koszt pamięci. JSON i MPP nadal
są wczytywane w całości; ograniczenia importu 01 pozostają.

Jedna lokalna próba: otwarcie około **0,86 s**, przygotowanie/przełączenie
i zapis zrzutu **0,03–0,31 s**, szczyt RSS około **1121 MiB**. To pomiar
tego komputera, a nie gwarancja wydajności. Anulowanie odrzuca wynik;
nie przerywa siłowo trwającego odczytu/dekodowania. Brak wiarygodnej
kalibracji/czasu TTMAPP pozostaje oznaczony, z jednostkami px.

## Standards

Niezależny przegląd `152146a...df5c48b`: brak twardych naruszeń standardów
repozytorium. Zachowano granice STM Domains, brak Qt w modelu, pracę poza
wątkiem GUI, tworzenie QPixmap w GUI, ograniczony cache i odrzucanie starych
wyników. Nie użyto prywatnego dekodera ani pełnego loadera MolTrack.
Nie znaleziono istotnych heurystycznych uwag do organizacji kodu.

## Spec

Niezależny przegląd tej samej różnicy: brak istotnych niezgodności,
braków lub rozszerzenia zakresu SD-V4-02. Zapisana geometria, izolacja błędów
rekordów/masek, dostępność raw, ID, jakość, braki danych i cache odpowiadają
kontraktowi. Ręczny odbiór użytkownika potwierdzono osobno po tym przeglądzie.

Bilans: **Standards — 0 uwag; Spec — 0 uwag.**

## Przekazanie integracyjne

Zmiany wyłącznie w aplikacji, jej testach i dokumentacji. Wspólny kod
i konfiguracja pozostają bez zmian. Do wcześniejszego zgłoszenia NumPy
i pytest-qt dochodzi używane teraz **SciPy**; integrator powinien uwzględnić
je w zależnościach szkieletów. Lokalny `netcat` już zawiera potrzebne pakiety.
Następny ticket w kolejności to 03; 04 można podjąć po 02 zgodnie z mapą.
