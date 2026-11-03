# SD-V4-10 — regulacja porządku i kalibracja dla użytego otoczenia

Data **2026-11-03**, gałąź `domains/interactive-v04-ui`, baza **`3c09c0b`**,
implementacja **`aa7e039`**. [Ticket](10-tune-order-test.md).
**Ręczny odbiór użytkownika oczekuje.** Sprawdzenia agenta opisano osobno.

## Uruchomienie i ręczny odbiór

W `/home/rlew/projekty/NEtCAT-domains`, w środowisku **netcat**:

```bash
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`, przejdź do **259**.
   W nowo otwartej sesji kliknij **Analizuj klatkę · K5**. To lokalne
   dopasowanie na klatce 259; liczby poniżej nie dotyczą wspólnego katalogu
   259–268 z odbioru 09. Bazowo: **120/312 molekuł w 6 domenach**.
2. Otwórz **Analiza → Test porządku…**. Bazowe ustawienia: kwantyl **0,950**,
   minimum lokalne **10**, efektywne **8**, promień **3 × d**, sigma **4/3 × d**
   (pole wyświetla **1,333333**, zachowując dokładną wartość bazową).
   `d` to odstęp molekuł wyznaczony z danej klatki w pikselach, nie nm.
3. Zmień kwantyl na **0,925**. Obraz pozostaje bez zmian, w oknie widać
   nieprzeliczony szkic. Kliknij **Kalibruj i przelicz klatkę**.
   Oczekiwane: etap kalibracji, ten sam katalog, **134/312 w 7 domenach**;
   licznik porządku rośnie z **159 do 179**. Akceptacja klas nadal **274/312**.
4. Przy kwantylu 0,925 ustaw drugą parę **promień 2 × d, sigma 1 × d**.
   Po przeliczeniu: **47/312 w 2 domenach**, porządek **77/312**,
   dostateczne wsparcie **84/312**. Identyfikator kalibracji zmienia się.
   Przy tej klatce `d ≈ 12,046 px`; promień to około 24,091 px,
   sigma około 12,046 px. Wartości w px są wyświetlane w oknie.
5. W **Pokaż na obrazie** przełącz poprzedni/nowy wynik. Zmieniają się
   obraz, liczniki i parametry wyświetlanego wyniku. Przywróć nowy,
   kliknij **Przywróć bazowe**, następnie **Kalibruj i przelicz klatkę**.
   Oczekiwane: dokładny powrót do **120/312, 6 domen** i bazowych przypisań.
6. Włącz centra, wskaż szarą molekułę i otwórz **Dane oznaczenia…**.
   Widać osobno akceptację klasy, liczbę punktów lokalnych i efektywnych,
   koherencję, próg kontroli, kwantyl, otoczenie i powód braku domeny.
   Przekroczenie progu koherencji nie zastępuje wymaganego wsparcia.
7. Uruchom przeliczenie i kliknij **Anuluj obliczenia**. Wcześniejszy wynik
   zostaje. Nawigacja na inną klatkę także przerywa pracę; powrót odtwarza
   wcześniejszy wynik. Na klatce bez obliczonych klas strojenie jest nieaktywne.
   Sprawdź mniejsze okno, gamma, raw/wyrównany oraz zamknięcie podczas pracy.
8. Sprawdź odmowę kalibracji: ustaw minimum efektywne **200** przy bazowym
   otoczeniu i przelicz. Oczekiwany jest komunikat o niewystarczających
   kontrolach, z zachowaniem poprzedniego wyniku; nie zerowanie domen.
   Przywróć bazowe ustawienia i przelicz.
9. Po zastosowaniu własnych ustawień otwórz **Klasy i zakres…**.
   Podsumowanie pokazuje test używany do doboru próbek nowego katalogu.
   Jawne dopasowanie używa tych ustawień. **Analiza serii…** także pokazuje
   test przed startem: bierze go z wyświetlanego wyniku lub używa bazowego,
   gdy wyniku brak. Szkic niezatwierdzony przyciskiem nie jest przejmowany.

## Gotowe kontrole do tego samego UI

Przygotowano lokalnie plik
`.scratch/stmdomains-ui-10/demo/order-controls.moltrack.json` i powiązany MPP.
Na innym checkoutcie można odtworzyć je w netcat:

```bash
python -m stmdomains.tools.order_demo --output .scratch/stmdomains-ui-10/demo
```

Otwórz JSON. **Analiza → Analiza serii…**: analiza klatek **1–4**, **K1**,
dane do odkrywania **Inny wybrany zakres**, dopasowanie **1–1**; bazowe
parametry domen i porządku. Dzięki wspólnemu katalogowi brak próbek do
nowego dopasowania na losowej klatce nie blokuje oceny jej porządku.

| Klatka | Wejście | Dostateczne wsparcie | Porządek | Końcowe domeny |
| --- | --- | --- | --- | --- |
| 1 | Siatka 11×11, obrót 45°, 121 centrów | 117/121 | 117/121 | 117/121, 1 domena |
| 2 | 121 losowych centrów; 23 pominięte jako bliskie duplikaty | 30/98 | 12/98 | 0/98, 0 domen |
| 3 | 121 centrów w rzędach, losowo wzdłuż rzędu; 27 pominiętych | 30/94 | 30/94 | 0/94, 0 domen |
| 4 | Cztery odosobnione centra | 0/4 | 0/4 | 0/4, 0 domen |

Mianowniki odnoszą się do aktywnych oznaczeń po dotychczasowej redukcji
bliskich duplikatów. Losowe wejścia mają ziarno **20261103**, odrębne od
ziarna kontroli kalibracyjnych. Rzędy pokazują ograniczenie metody:
**potrafi przyjąć jeden kierunek periodyczności**, mimo braku sieci 2D.
Zerowy wynik domen dla rzędów wynika tu także z odmowy klasy dopasowanej
na regularnej siatce; sam zerowy wynik nie dowodzi poprawności testu porządku.

Po zmianie klatki 1 na kwantyl 0,925 / promień 2 / sigma 1: wsparcie i
porządek **8/121**, domeny **0/121**. To obliczona odmowa przy za małym
wsparciu i rozdrobnieniu, nie informacja o braku molekuł.

## Obliczenia, pochodzenie i ograniczenia

- `OrderSettings` waliduje pięć parametrów: kwantyl 0,5–0,999, minimum
  lokalne 3–200, efektywne 2–200, promień 0,5–6 i sigma 0,25–4 odstępów.
- Ten sam promień, sigma i minima obowiązują obraz i kontrole. Kontrole
  powstają od nowa przy każdym pełnym przeliczeniu, bez cache progów.
  Zmiana szkicu nie unieważnia poprawnego wyniku na ekranie. Strojenie
  samych domen z 06 zachowuje już obliczone oceny klas i porządku.
- Zachowano bazową metodę: maksimum koherencji Fouriera z korekcją
  skończonej liczby punktów, 48 kierunków, 22 częstości 0,5–2 na odstęp.
  Kontrole: jednostajne losowe oraz z wykluczeniem 0,6 odstępu, pole
  12×12 odstępów, liczności 60/120/180, dwa powtórzenia, ziarno **20261102**.
  Otoczenia kontroli ocenia się przy odstępie 1: normalizacja odpowiada
  promieniowi i sigmie przemnożonym przez rzeczywiste `d` danej klatki.
- Progi to maksimum kwantyli obu typów kontroli. Dla kotwic efektywnego
  wsparcia 8,10,12,14,16,18,20,24,28,32 wybiera się do 350 najbliższych
  próbek; pomiędzy kotwicami interpoluje się liniowo, poza nimi stosuje
  próg skrajny. To zachowana heurystyka bazowej metody, nie p-value ani
  skalibrowane prawdopodobieństwo poprawności domeny. Małe liczności
  kontroli i skrajne konfiguracje ograniczają interpretację; brak
  kwalifikujących się kontroli daje błąd, bez użycia starych progów.
- Wynik zapisuje ustawienia, kalibrację z licznościami i przedziałami
  wsparcia, jej hash i ziarno; osobno klatkę, hash wejścia, `d`, promień
  i sigmę w px. Dopasowanie klas zapisuje ustawienia porządku, ID kalibracji
  i ziarno w rekordach użytych klatek wraz z ID próbek.
- Strojenie zachowuje tożsamość katalogu, klasy wstępne, progi akceptacji
  i parametry domen. Zmieniono rozdział parametrów modelu: regulowane
  ustawienia porządku należą do pochodzenia doboru próbek, a nie do warunku
  zgodności przy stosowaniu gotowego katalogu. Nowy hash katalogu może
  różnić się od 09, lecz strojenie go nie zmienia.
- Ponowne **Analizuj klatkę**, 06 i 09 zachowują zastosowany porządek.
  Jawne odkrywanie w 07 oraz nowa analiza serii 08 korzystają z parametrów
  wyświetlanego wyniku (lub bazowych przy jego braku). Zakres dopasowania
  i zakres ocenianych klatek pozostają oddzielne. Numery domen są lokalne.
- Wyniki i ich poprzednie wersje pozostają tylko w pamięci. Zapis projektu
  to 13, eksport 14. Nie zmieniano danych, środowiska ani wspólnych modułów;
  nie czytano historycznych paczek/modeli/kalibracji v0.4. Brak nowych zależności.

## Wykonane sprawdzenia

Interpreter:
`/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.

- TDD: brak ustawień → kwantyl w kalibracji; brak przeliczenia → zachowany
  katalog i odtworzenie domen; brak przekazania konfiguracji → dobór próbek
  odkrywania; brak menu → dialog; reset w analizie serii → zachowanie
  konfiguracji; brak czytelnych danych porządku → szczegóły molekuły.
- **22 nowe przypadki PASS**; **58 celowanych regresji PASS**. Sprawdzenia
  obejmują niezależny wpływ ustawień, skalowanie współrzędnych, walidację,
  układ regularny/losowy/rzędy, anulowanie w kalibracji, zmianę klatki,
  ponowne otwarcie, shutdown i odmowę bez nadpisania wyniku.
- **Mypy 67 modułów PASS**, **22 pliki kodu/testów, maksimum 566 linii**.
- **Rzeczywiste GUI X11/xcb PASS**: TTMAPP 259, 12 zrzutów, przejścia
  poprzedni/nowy, odtworzenie mapy piksel w piksel, szczegóły szarej molekuły,
  raw/wyrównany, gamma, okna 900×650 i 1250×850, nawigacja, anulowanie,
  wszystkie cztery kontrole w analizie serii oraz zamknięcie podczas pracy.
  Obejrzano okno parametrów, szczegóły, wynik TTMAPP i widoki kontroli.
- Przeliczanie TTMAPP około **0,4–0,7 s**, RSS około **621 MiB**, największa
  przerwa timera **0,235 s**. Po zamknięciu trzy pule mają po 0 aktywnych zadań.
- Podczas strojenia zablokowano wywołania fit PCA/KMeans: żadna próba nie
  wystąpiła. Audyt odczytów: **0 odczytów historycznych paczek/modeli**.
- Kontrolę czterech molekuł dodatkowo rozsunięto i poszerzono plamki,
  aby były widoczne mimo kontrastu percentylowego; osobna próba X11 PASS,
  cztery centra, odmowa wsparcia, 0 domen. Obejrzano końcowy PNG.
- SHA-256 MPP/JSON przed i po próbie: **bez zmian**. JSON:
  `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`;
  MPP: `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`.

Pełny zestaw po przeglądzie: **449 passed, bez pominięć, 139,80 s**.
Pierwsze uruchomienie zostało przerwane sygnałem zakończenia (kod 143)
przed podsumowaniem, bez zgłoszonego błędu testu; przyczyny sygnału nie
ustalono. Zachowano `pytest-full-interrupted.log` i ponowiono cały przebieg.
Powyższy wynik pochodzi z kompletnego ponowienia, `pytest-full.log`.
**376 lokalnych odnośników z kotwicami w 7 dokumentach PASS**, plan ma
24 tickety, `git diff --check` PASS.
Polecenia w aktywnym netcat:

```bash
python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
python -m stmdomains.tools.check_code_size --base 3c09c0b
QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
```

Artefakty poza Git: `.scratch/stmdomains-ui-10/`, w tym `gui_smoke.py`,
`gui-smoke.json`, `gui-smoke.log`, `sparse_smoke.py`, `sparse-smoke.log`,
`pytest-full.log`, wejścia i PNG. Sprawdzenia dotyczą działania funkcji,
nie trafności naukowej wykrywania domen. Odbiór użytkownika pozostaje otwarty.

## Przegląd kodu

Skill `code-review`, dwa niezależne przeglądy, `git diff 3c09c0b...aa7e039`.
Recenzenci nie zmieniali plików ani nie uruchamiali pełnego zestawu.

## Standards

**0 ustaleń wymagających poprawki.** Zmiany pozostają w zakresie aplikacji;
parametry mają osobny typ, wyniki zapisują pochodzenie, a operacje korzystają
z istniejącego anulowania i ochrony przed publikacją spóźnionego wyniku.
Testy obejmują publiczne obliczenia, kontroler i kontrolki. Brak naruszeń
udokumentowanych zasad i istotnych uwag heurystycznych.

## Spec

**0 uwag.** Pięć parametrów trafia do obrazu i kalibracji. Strojenie zachowuje
katalog i pozostałe ustawienia, nowe odkrywanie używa zmienionego testu do
wyboru próbek. Sprawdzone są kontrolne układy i bezpieczne przerwanie pracy;
UI rozdziela porządek od domen oraz wyjaśnia ograniczenie dotyczące rzędów.
Przekazanie konfiguracji do serii mieści się w wymaganiu nowego odkrywania.

Po przeglądzie zmieniono jedynie rozstaw czterech centrów demonstracyjnych
w `order_demo.py`; ponowiono celowaną próbę GUI. **Standards 0, Spec 0**,
brak otwartych ustaleń przeglądu.
