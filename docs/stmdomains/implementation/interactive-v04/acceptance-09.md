# SD-V4-09 — akceptacja klas przy zachowanym katalogu

Data: **2026-11-03**. Gałąź `domains/interactive-v04-ui`, baza **`b34e862`**,
implementacja **`494ab9d`**. [Ticket](09-tune-class-acceptance.md).
**Odbiór ręczny użytkownika oczekuje.** Sprawdzenia agenta opisano osobno.

## Uruchomienie i test ręczny użytkownika

W katalogu `/home/rlew/projekty/NEtCAT-domains`, w środowisku **netcat**:

```bash
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`, przejdź do **259**.
   W **Analiza → Klasy i zakres…** ustaw **K5**, **Wybrany zakres 259–268**
   i kliknij **Dopasuj klasy i analizuj klatkę**. Zostaw bazowe parametry domen.
2. Otwórz **Analiza → Akceptacja klasy…**. Widać klatkę, katalog,
   liczbę zaakceptowanych klas oraz osobno liczbę molekuł w domenach.
   Ustaw **Minimalny margines 0,060**, pozostaw mnożnik **1,10**.
   Samo wpisanie wartości nie zmienia obrazu. Kliknij **Przelicz klatkę**.
3. Przełącz **Pokaż na obrazie → Poprzedni wynik / Nowy wynik**.
   Katalog pozostaje ten sam; pola i opis wskazują ustawienia wyświetlanego
   wyniku. Na tych danych akceptacja rośnie z **272 do 281 z 312**, a końcowe
   domeny nadal obejmują **105 molekuł**. Zmiana progu nie musi zmieniać domen.
4. Przy marginesie **0,060** ustaw mnożnik **0,80** i przelicz. Oczekiwane:
   **236 zaakceptowanych klas**, **81 molekuł w 4 domenach**. Mnożnik dotyczy
   podobieństwa otoczeń, nie fizycznego promienia na obrazie.
5. Włącz **Centra**, wskaż szarą molekułę i otwórz **Dane oznaczenia…**.
   Początek okna opisuje: klasę wstępną, akceptację, margines/promień,
   porządek lokalny i końcową domenę. Sprawdź także kolorową molekułę.
   Akceptacja klasy może być dodatnia mimo braku domeny, np. z powodu porządku.
6. Kliknij **Przywróć bazowe**, a potem **Przelicz klatkę**. Oczekiwane:
   **272/312** na etapie klas i **105/312 w 5 domenach**. Przywrócenie samych
   pól nie jest jeszcze obliczeniem. Zoom, gamma i raw/aligned nie zmieniają
   przypisań. Sprawdź też okno aplikacji o mniejszym rozmiarze.
7. Zmień ustawienie, rozpocznij przeliczenie i je anuluj. Poprzedni ukończony
   wynik pozostaje. Przejdź do nieanalizowanej klatki 260: przeliczanie
   akceptacji jest niedostępne do czasu uzyskania jej wyniku. Powrót do 259
   odtwarza jej wynik. Domknięcie aplikacji podczas pracy nie powoduje crasha.

Małe wejścia kontrolne, bez modeli i gotowych etykiet wynikowych:

```bash
python -m stmdomains.tools.class_discovery_demo --output .scratch/stmdomains-ui-09/demo
```

8. Otwórz `.scratch/stmdomains-ui-09/demo/single.moltrack.json`, w oknie klas
   wybierz **K1**, **Bieżąca klatka** i dopasuj. Bazowo: **12/16**, jedna domena.
   W Akceptacji klasy margines jest nieaktywny i opisany jako **nie dotyczy**.
   Mnożnik **0,05** daje na tym przykładzie **0/16**, a ustawienia bazowe
   przywracają wynik. Szczegóły molekuły nie przedstawiają marginesu K1
   jako porównania z nieistniejącą drugą klasą.
9. Otwórz `empty.moltrack.json` z tego samego katalogu. Po próbie analizy
   widać brak oznaczeń; edytor akceptacji nie uruchamia ukrytego dopasowania.

## Zachowanie i zakres

- Margines **0–1**, wartość bazowa **0,075**; mnożnik **0,05–10**, bazowo **1,10**.
  Ustawienia są walidowane także poza UI i zapisywane w parametrach wyniku.
- Przeliczenie korzysta z katalogu wyświetlanego wyniku, także przy wyborze
  poprzedniej wersji. Nie wywołuje dopasowania PCA ani KMeans, nie zmienia
  centroidów, wstępnych klas ani zakresu, z którego odkryto klasy.
- Punkty, opisy otoczeń, ocena porządku i geometria są odtwarzane z bieżących
  danych. Obowiązuje kontrola ich tożsamości. Nie powstaje dodatkowy cache
  dużych tablic dla każdej klatki. Ustawienia tworzenia domen są zachowane.
- Progi akceptacji nie definiują dopasowania; wyłączono je z parametrów
  tożsamości katalogu. Nowo obliczony katalog może mieć inny hash niż w 08,
  przy tych samych klasach i wyniku bazowym. Podczas strojenia hash i obiekt
  katalogu pozostają niezmienione.
- Szczegóły rozdzielają niewystarczający opis, mały margines, przekroczenie
  promienia, ocenę porządku oraz zbyt małą/rozdrobnioną domenę. Pokazywana
  miara podobieństwa nie jest skalibrowanym prawdopodobieństwem.
- Ustawienia 09 dotyczą **bieżącej klatki**. Strojenie domen i przycisk
  **Analizuj klatkę** zachowują jej zastosowane progi. Jawne odkrycie nowego
  katalogu w **Klasy i zakres…** oraz nowy przebieg **Analiza serii…** używają
  akceptacji bazowej; 09 nie dodaje formularza progów do analizy serii.
- Indywidualnie przeliczony wynik nie podszywa się pod wynik wcześniejszego
  przebiegu serii. Wyniki pozostają w pamięci, do dwóch wersji na klatkę.
  Zapis projektu to 13, eksport 14. Nie wymagamy plików v0.4 ani instalacji.

## Wykonane sprawdzenia agenta

Interpreter zweryfikowany:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.

- TDD: brak operacji → działające strojenie; brak menu → test UI;
  brak opisu etapów → szczegóły molekuły; wykryty reset progów przy
  Analizuj klatkę → zachowanie zastosowanych ustawień.
- **18 nowych przypadków PASS**, wraz z celowanymi regresjami domen/klas.
  Kontrole obejmują znany przykład dwóch klas, odrębny wpływ marginesu
  i promienia, K1, walidację, brak modelu, zmienione dane, porównanie,
  przywrócenie, anulowanie/nawigację/otwarcie innej serii oraz błąd obliczeń.
- Mypy **63 moduły PASS**; zmieniony kod/testy **15 plików, maksimum 544 linii**.
- **Rzeczywiste GUI X11/xcb PASS**, sterowane kontrolkami Qt: TTMAPP 259,
  wspólne K5 z 259–268, dwa progi, porównanie i odtworzenie bazowego wyniku,
  szczegóły szarej/kolorowej molekuły, raw/aligned, gamma, nawigacja,
  okna 900×650 i 1250×850, K1, brak oznaczeń, anulowanie i zamknięcie w pracy.
  Obejrzano sześć zrzutów. Geometria głównego okna stabilna przy przeliczeniu.
- Trzy warianty TTMAPP: około **0,70–0,71 s** na przeliczenie. K1: **0,58 s**.
  Szczyt RSS **631,90 MiB**, maksymalna przerwa timera **0,228 s**.
  Po zamknięciu trzy pule miały po **0 aktywnych zadań**.
- Podczas strojenia zablokowano dopasowanie PCA/KMeans: brak prób ponownego
  fitu. Audyt odczytów: **0 odczytów paczek/historycznych modeli**.
  MPP/JSON niezmienione: porównanie SHA-256 przed/po PASS.
- Pierwsza próba X11 w piaskownicy nie mogła połączyć się z `DISPLAY=:1`.
  Ponowiono ten sam test z dostępem do lokalnego ekranu; PASS. Nie instalowano
  pakietów. To ograniczenie uruchomienia, nie błąd zamykania programu.

Pełny zestaw STM Domains uruchomiony **raz na koniec**, po przeglądzie:
**427 passed, bez pominięć, 111,88 s**. Log: `pytest-full.log` w katalogu
artefaktów. **365 lokalnych odnośników z kotwicami w 7 dokumentach PASS**;
24 tickety, zgodne zależności i brak cykli. `git diff --check` PASS.

Polecenia w aktywnym netcat:

```bash
python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
python -m stmdomains.tools.check_code_size --base b34e862
QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
```

Artefakty lokalne poza Git: `.scratch/stmdomains-ui-09/`, w tym
`gui_smoke.py`, `gui-smoke.json`, `gui-smoke.log`, wejścia kontrolne i PNG.
Hashe rzeczywistych źródeł:

- JSON: `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.
- MPP: `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`.

Wyniki potwierdzają działanie sterowania i odtwarzalność. Nie są pomiarem
trafności domen ani odbiorem naukowym metody. Odbiór użytkownika pozostaje otwarty.

## Przegląd kodu

Skill `code-review`, dwa niezależne przeglądy. Baza `b34e862`, implementacja
`494ab9d`, polecenie `git diff b34e862...494ab9d`. Recenzenci nie zmieniali
plików ani nie uruchamiali pełnego zestawu; sprawdzenia wykonania opisano powyżej.

## Standards

Brak istotnych ustaleń. Twardych naruszeń nie stwierdzono. Zakres zmian
pozostaje w STM Domains. Progi mają osobny typ domenowy, są zapisywane
w wyniku i nie zmieniają tożsamości katalogu. Przeliczenie korzysta
z istniejącej obsługi postępu, anulowania i odrzucania spóźnionych wyników.
Diagnostyka rozróżnia akceptację klasy, test porządku i przynależność do domeny.

Nie znaleziono heurystycznego problemu uzasadniającego zmianę przed przyjęciem.
Podobieństwo konstrukcji dialogów odpowiada obecnemu wzorcowi UI; nie uznano
go za istotny dług w tym zakresie.

## Spec

Nie stwierdzono niezgodności ze specyfikacją ani niezamówionego rozszerzenia
zakresu. Przeliczenie zachowuje obiekt katalogu i centroidy, progi sterują
akceptacją niezależnie od dopasowania, a K1 pomija margines dwóch klas.
UI rozróżnia klasę wstępną, akceptację, porządek oraz domenę; pokazuje
warunki odmowy i wyjaśnia znaczenie confidence. Ustawienia mają walidację
i trafiają do wyniku.

Sprawdzono kod oraz testy pokrywające zachowanie katalogu, przywracanie
progów, porównanie wersji, przerwanie obliczeń i szczegóły molekuły.
Artefakt GUI potwierdza dla klatki 259 niezmienne ID wspólnego katalogu,
wzrost akceptacji 272→281 po zmianie marginesu i spadek przypisań do domen
105→81 po zawężeniu promienia.

**Standards: 0 ustaleń; Spec: 0 ustaleń. Brak otwartych uwag obu osi.**
