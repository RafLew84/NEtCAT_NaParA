# Częściowe referencje domen TTMAPP, klatki 250–268

Data: 2026-10-21. Uzupełnienie
[próby pokrycia i skali](issues/10-coverage-and-scale.md) po wskazaniu przez
użytkownika katalogu `data/ttmapp_frames_250_268_domain_review`.

## Znaczenie oznaczeń potwierdzone przez użytkownika

Ramki w górnej części obrazu wyznaczają **przybliżone granice całych wybranych
widocznych domen**. Nie oznaczono całych klatek. W innych miejscach mogą
występować skupiska o takim samym uporządkowaniu jak zaznaczone.

Wykorzystujemy wyłącznie oznaczone fragmenty jako referencję. Obszar poza
ramkami jest **nieoznaczony**, a nie podłożem, nieporządkiem, negatywnym
przykładem danej klasy ani fałszywym wykryciem. Nie zaznaczamy całej górnej
połowy jako poprawnie opisanej: szczeliny i fragmenty między ramkami również
pozostają poza zakresem referencji.

Kolory BLACK, RED i YELLOW zachowujemy jako etykiety ręcznego zbioru. Nie
przesądzają, czy różnicę opisuje typ sieci, orientacja, rozstaw czy kilka cech.
Nie ustanawiają trzech obowiązkowych typów w całej serii. Odrębne regiony
tego samego koloru pozostają odrębnymi przykładami przestrzennymi.

## Co rzeczywiście jest dostępne

- **18 par** `frame_N_clean_registered.png` i
  `frame_N_clean_registered_manual_domain.png`: numery 250–254 oraz 256–268,
  indeksy od zera 249–253 oraz 255–267. **Brakuje pary dla klatki 255.**
- Rozmiar każdej pary: **960×816 px**; to dwukrotnie powiększone płótno
  expanded_aligned 480×408 px, a nie oryginalne pole 256×256 px.
- Czyste PNG zawierają obraz szary; czarną ręczną kreskę rozpoznajemy przez
  porównanie z czystym plikiem. Ciemny piksel próbki sam nie jest oznaczeniem.
- W katalogu są także wcześniejsze kalibracje, CSV i automatyczne predykcje.
  Nie stają się referencją przez samą obecność obok ręcznych rysunków.

Starsze raporty opisują 19 klatek, łącznie z 255; kod dopuszczał osobny katalog
dla tej klatki. W obecnym przygotowaniu użyto tylko faktycznych par w folderze
wskazanym przez użytkownika. Nie odtworzono brakującej anotacji z predykcji.
Wersje dawnych ekstraktorów i referencji różnią się liczebnościami, dlatego
ich tabel nie łączymy bez sprawdzenia pochodzenia.

## Sprawdzenie geometrii

Użyto istniejącego MPP i zapisu `data/TTMAPP/detection_full.moltrack.json`:

| Źródło | SHA-256 |
| --- | --- |
| MPP | `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66` |
| MolTrack JSON | `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e` |

Oba zapisane snapshoty dawnych kalibracji mają tę samą kolejność źródłowych
klatek oraz identyczne przesunięcia dla tego zakresu. Dodatkowo odtworzono
**wszystkie 18 czystych PNG piksel w piksel**: czytnik MPP obracający o 180°,
zapisane globalne translacje, padding LTRB 224,139,0,13, interpolacja liniowa
z NaN poza polem, percentyle 1–99 z finite próbek i powiększenie Lanczos ×2.
Jest to ścieżka zapisu z `scripts/render_ttmapp_frame_domains.py`.
Maksymalna różnica wynosi 0/255 dla każdej klatki. To weryfikacja zgodności
obrazu i geometrii, nie potwierdzenie fizycznej poprawności rejestracji.

Powiązanie współrzędnych krawędzi:
`p_PNG = 2 × (p_raw + (224 + dx, 139 + dy))`.
Próbkowanie masek na siatce raw odbywa się w środkach `(c+0,5, r+0,5)`.
Pole pomiarowe wynika z geometrii; nie estymujemy go z jasności ani czerni tła.
Padding pozostaje wyłączony. PNG są podglądem; metody mają korzystać z MPP
albo czystego obrazu w jawnie opisanej skali, nigdy z obrazu z kolorową kreską.

## Przygotowane maski robocze

Na gałęzi `prototype/stmdomains-coverage` dodano generator
`stmdomains/prototypes/partial_domain_reference.py`, commit `4e7a757`.
Odtworzenie w `netcat`, z katalogu worktree prototypu:

```bash
python stmdomains/prototypes/partial_domain_reference.py \
  --review /home/rlew/projekty/NEtCAT-domains/data/ttmapp_frames_250_268_domain_review \
  --session /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/detection_full.moltrack.json \
  --mpp /home/rlew/projekty/NEtCAT-domains/data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  --out .scratch/partial-domain-reference
```

Lokalne wyniki:
`/home/rlew/projekty/NEtCAT-domains/.scratch/partial-domain-reference/`.
`index.html` zestawia oryginalne ramki i ostrożne wnętrza. Manifest zapisuje
hashe każdej pary, indeksy, przesunięcia, metodę odtworzenia regionu i błędy
rekonstrukcji PNG. Pliki NPZ zawierają maski wnętrz w raw oraz płótnie PNG,
identyfikatory regionów, maskę kresek i pole klatki. **Zero oznacza obszar
nieoznaczony lub wyłączony, nie podłoże.**

Wnętrza wyznaczono na podstawie domknięć ręcznych konturów, z usunięciem
kreski/pasa domykania i dodatkowym marginesem **3 px oryginału**. Algorytm
dziedziczy progi koloru z dawnych skryptów; parametry morfologii są w manifeście.
Dla brakującej klasy sprawdzane jest także domknięcie jej własnej kreski,
bez głosowania sąsiednich kolorów. Pozwala to zachować wąski czerwony fragment
klatki 251, który dawny ekstraktor wspólnych konturów pomijał.

Przygotowano **54 wnętrza regionów** na 18 klatkach: po 18 przykładów
BLACK, RED i YELLOW. To liczba przykładów z kolejnych klatek, nie niezależnych
fizycznych domen. Klatka 252 ma dwa regiony, a klatka 258 cztery.

To **robocze, konserwatywne wnętrza**, a nie precyzyjny przebieg granicy fizycznej.
Margines 3 px nie jest skalibrowanym błędem ręcznej anotacji. Nie wybierano go
na podstawie wyniku klasyfikatora. Lokalny podgląd pozwala skontrolować ekstrakcję;
pełna ocena granic wymaga osobnego ustalenia tolerancji i fragmentów niepewnych.

## Do czego użyjemy tych danych

Użytkownik 2026-10-21 zaakceptował obecny zbiór jako referencję do najbliższych
prób. Wykorzystujemy go w poniższym zakresie; dodatkowych oznaczeń szukamy
dopiero wtedy, gdy konkretna próba wykaże ich konieczność. Brak pełnej anotacji
klatek nie blokuje lokalnego porównania metod.

1. Porównanie cech i rozróżniania wzorów **wewnątrz zaznaczonych domen**.
   Przy wymaganiu użycia wyłącznie ich wnętrz okno cechy musi mieścić się
   w odpowiednim wnętrzu; brak dostatecznie dużego okna to jawny brak próbki.
2. Lokalna ocena zgodności podziału przy oznaczonych granicach, po ustaleniu
   pasa tolerancji. Granic ocenianego wycinka nie uznajemy za granice domeny.
3. Dla pokrycia — pomocnicze sprawdzenie, czy metoda zachowuje materiał
   we wskazanych fragmentach. Nie wystarczy to do oceny pełnego pokrycia:
   maska „wszystko jest materiałem” też zachowałaby wszystkie dodatnie przykłady.

Nie liczymy z tych oznaczeń globalnego IoU, liczby domen całej klatki,
fałszywych wykryć poza ramkami ani błędu całkowitego pokrycia. Inny zaznaczony
kolor może być przykładem odmiennego wzoru, ale nie jest negatywnym przykładem
obecności materiału. Do pełnego ticketu o pokryciu nadal potrzebne są
referencje pewnego podłoża oraz miejsc nierozstrzygniętych.

Stare podziały 250–262 / 263–268 dotyczą jednej skorelowanej serii. Część
sprawdzająca była już używana przez wcześniejsze eksperymenty; nie deklarujemy
jej jako nowego, niezależnego testu. Pochodzenie, podział i kryteria jakości
pozostają częścią [pytania o referencje](issues/04-reference-and-quality.md).

## Zakres wykonanej kontroli

Sprawdzono kompletność par, zgodność snapshotów rejestracji i rekonstrukcję
18 PNG, przygotowano maski bez etykietowania reszty obrazu, obejrzano zestawienie
wszystkich wnętrz oraz oryginały klatek 250, 251, 258 i 268. Rozdzielono ramki
ręczne od poprzednich predykcji i od dokładnych masek granic. Podczas tego audytu
nie przeliczano klasyfikatorów domen ani nie oceniano skuteczności metod.
Nie zmieniano danych źródłowych, kodu wspólnego ani produkcyjnej aplikacji.

Następnie wykonano [próbę pokrycia na tych wnętrzach](coverage-partial-reference-trial.md).
Zachowano te same maski referencji i oceniono utratę znanego materiału przez
10 wariantów. To wynik kolejnego eksperymentu, nie zmiana znaczenia etykiet
ani pełna walidacja pokrycia lub rozróżniania typów domen.
