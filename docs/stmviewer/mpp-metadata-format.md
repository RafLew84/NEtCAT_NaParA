# Metadane towarzyszące MPP — wersje 1 i 2

Kontrakt ticketów [11](implementation/issues/11-mpp-metadata-import.md),
[12](implementation/issues/12-original-mpp.md) i [13](implementation/issues/13-aligned-mpp.md).
Aktualizacja: 2026-10-26. V1 opisuje original bez geometrii rejestracji.
V2 dodaje historię aligned; obie wersje są odczytywane. Zwykły eksport original
nadal używa V1. Eksport aligned oraz original ze znaną historią używa V2.

## Lokalizacja i powiązanie

Dla `movie.mpp` aplikacja szuka `movie.mpp.stmviewer.json` w tym samym
katalogu; dla `movie.MPP` — `movie.MPP.stmviewer.json`. Przyrostek jest
literalnie dopisywany do nazwy otwartego pliku po rozwiązaniu jego ścieżki.
Na systemie rozróżniającym wielkość liter trzeba zachować także wielkość
liter nazwy. Można przenieść parę, a także zmienić nazwę obu plików zgodnie
z tą regułą. Historyczne ścieżki w metadanych nie są otwierane ani rozwiązywane.

JSON ma kodowanie UTF-8, limit 64 MiB i nie może zawierać powtórzonych kluczy,
NaN ani Infinity. `null` oznacza brak informacji. Nieobsługiwana wersja,
rodzaj, pole lub typ, niepełna struktura albo błąd odczytu unieważnia cały
dodatek. Walidacja nie nakłada części metadanych na pierwsze poprawne klatki.
Film nadal otwiera się z własnym nagłówkiem i komunikatem o przyczynie.
Brak dodatku również jest widoczny, bez blokującego okna dialogowego.

Powiązanie sprawdzane jest przez SHA-256 **wszystkich bajtów MPP**, włącznie
z nagłówkiem i ewentualnymi bajtami końcowymi, oraz liczbę i kształt klatek.
Skrót jest liczony przy odczycie tych samych bajtów, z których dekodowane są
obrazy, bez ponownego otwierania filmu. Zmiana samego nagłówka również
unieważnia dodatek. Jest to kontrola zgodności pary, nie podpis autentyczności.

## Struktura V1

Pełny przykład: [mixed.MPP.stmviewer.json](../../tests/stmviewer/fixtures/mpp-metadata/mixed.MPP.stmviewer.json).
Wszystkie opisane pola są obowiązkowe, a nieznane pola odrzucane.

| Pole główne | Wartość |
| --- | --- |
| `format` | Dokładnie `"stmviewer-mpp"`. |
| `version` | Liczba całkowita `1`. |
| `image_kind` | Dokładnie `"original"`; opis wersji eksportu, nie dowód braku wcześniejszej obróbki. |
| `movie.sha256` | 64 małe znaki szesnastkowe, SHA-256 MPP. |
| `movie.frame_count` | Dodatnia liczba całkowita, zgodna z filmem. |
| `movie.shape_yx` | `[liczba_wierszy, liczba_kolumn]`, liczby całkowite zgodne z klatkami. |
| `frames` | Tablica rekordów, po jednym na każdą klatkę w kolejności filmu. |

Rekord klatki:

| Pole | Typ i znaczenie |
| --- | --- |
| `provenance.source` | Niepusty tekst ścieżki historycznego źródła, bez NUL; zachowany dosłownie, także Windows lub względny. |
| `provenance.source_frame_index` | Indeks od zera lub `null` dla źródła bez numeru klatki. |
| `measurement_time_s` | Skończona liczba sekund lub `null`; bez zerowania początku i uzupełniania luk. |
| `measurement_time_raw` | Oryginalny opis czasu jako tekst lub `null`. |
| `channel`, `signal_unit` | Tekst lub `null`; jednostka sygnału jest odrębna od kalibracji X/Y. |
| `size_x_nm`, `size_y_nm` | Dodatni skończony rozmiar pola w nm lub `null`, niezależnie dla każdej osi. |
| `offset_x_nm`, `offset_y_nm` | Skończony offset w nm lub `null`. |
| `bias_v`, `setpoint_a`, `scan_angle_deg` | Skończone wartości w V, A i stopniach albo `null`; rzeczywiste zera zachowane. |
| `calibration_note` | Tekst informacji o kalibracji, np. danych surowych/zastępczych, lub `null`. |
| `raw_header` | Obiekt: klucz → tekst albo klucz sekcji → obiekt klucz → tekst. Zachowuje płaski S94 oraz sekcje STP/MPP. |

Liczby JSON typu boolean nie są akceptowane jako liczby ani indeksy.
Surowe nagłówki nie są ponownie parsowane w celu nadpisania pól dodatku.
Jawne `null` zastępuje parametr z nagłówka MPP, nawet jeśli ten podaje liczbę.
Nie przelicza się wartości obrazu według jednostki, skali ani amplitudy Z.
Kalibracja pozostaje deklaracją źródła; dodatek nie potwierdza jej fizycznej
poprawności. Ustawienie podglądu „Proporcje pikselowe” nie modyfikuje tych danych.

## Model i interfejs

`ImageFrame.source` i `source_frame_index` opisują faktycznie otwarty plik
oraz pozycję w nim. `provenance` przechowuje niezależne historyczne pochodzenie.
Pozostałe pola pomiaru, włącznie z `raw_header`, po poprawnej walidacji pochodzą
z dodatku; `data` pozostaje niezmienione. `metadata_note` przekazuje wynik
weryfikacji do GUI. Brak dodatku nie tworzy domniemanej historii przekształceń.

Panel rozdziela „Plik otwarty” i „Pochodzenie” oraz oba numery klatki.
Numery wyświetlane są od 1; kolejność w serii nadal jest oddzielna i zmienia
się po usunięciu klatki. Nazwy miniatur pochodzą z historycznego źródła,
a podpowiedzi zawierają obie lokalizacje. Komunikat o dodatku pozostaje
widoczny przy nawigacji i znika po opróżnieniu serii albo otwarciu STP/S94.
Oryginalne pliki oraz ich dodatki nie są modyfikowane.


## Zapis original (ticket 12)

`save_original_mpp` zapisuje float64 little endian w kolejności plikowej WSxM
(obrót 180° względem tablic Viewera) i tworzy dodatek V1 lub V2 z historią. Cała pozostała seria
zachowuje wymiary, wartości, NaN, kolejność, czasy i pochodzenie. Podgląd nie
jest wejściem eksportera. Istniejące historyczne pochodzenie jest zachowane;
przy jego braku pochodzi z faktycznego źródła i indeksu klatki.

Wspólny nagłówek używa wyłącznie wspólnych znanych parametrów. Każda oś
bez wspólnej skali ma rozmiar pikselowy w `a.u.`; różne/nieznane jednostki
sygnału dają `a.u.`, kanał `Unknown`. Nieznane napięcie, prąd, offset lub kąt
są pomijane. Znany wspólny prąd zapisuje się w nA: stary czytnik interpretuje
`A` jako angstrom. Znane czasy w nagłówku mają jednostkę sekund i bieżące
indeksy, bez uzupełniania braków. Tekstowe pola nagłówka przekraczające 65 000 bajtów UTF-8 lub zawierające
znaki sterujące używają wartości umownych; pełna treść pozostaje w JSON.
Dokładne parametry wszystkich klatek,
łącznie z surowymi nagłówkami i opisami czasu, pozostają w JSON.

Eksporter zapisuje parę tymczasową na tym samym systemie plików, synchronizuje
zapis i zabezpiecza kopie zastępowanych plików przed podmianami. Błąd lub
anulowanie powoduje przywrócenie wcześniejszych plików; niepowodzenie samego
przywracania zachowuje kopie i wskazuje ich katalog. Po twardej awarii między
podmianami niezgodny stary dodatek jest odrzucany przy odczycie dzięki SHA-256.
Nie jest to obietnica atomowości dwóch plików ani odporności na utratę zasilania.


## V2: geometria i historia aligned (ticket 13)

Główne pola są takie jak w V1, ale `version` wynosi `2`, `image_kind` może
być `original` lub `aligned`. Każdy rekord klatki ma dodatkowo obowiązkowe
pole `alignment`: obiekt poniżej albo `null`. Dla `image_kind=aligned`
wszystkie rekordy muszą zawierać historię jednego kompletnego wyniku:
zgodny obszar, padding, skalę, odniesienie, metodę i urządzenie.
Dla `original` historia pozostaje opcjonalna, również osobno dla każdej klatki.

| Pole `alignment` | Znaczenie |
| --- | --- |
| `canvas_shape` | `[wiersze, kolumny]`, dodatnie liczby całkowite; pełny obszar zapisanych próbek. |
| `padding_ltrb` | `[lewo, góra, prawo, dół]`, nieujemne całkowite piksele względem historycznego odniesienia. |
| `pixel_size_nm` | Wspólna dodatnia skończona skala `[X, Y]` w nm/piksel albo `null`. |
| `reference` | `source` i `source_frame_index` jak w `provenance`; odniesienie historyczne, także usunięte z serii. |
| `method`, `device` | Niepuste nazwy metody i urządzenia użytego do rejestracji. |
| `original_shape` | `[wiersze, kolumny]` wejścia tego etapu rejestracji. |
| `original_size_nm` | Źródłowe pole `[X, Y]` w nm; każdy element dodatni skończony lub `null`. |
| `original_offset_nm` | Źródłowy offset `[X, Y]` w nm; każdy element skończony lub `null`. |
| `shift_xy` | Skończone skumulowane przesunięcie `[X, Y]` w pikselach względem odniesienia. |
| `origin_xy` | Początek źródłowej klatki w obszarze aligned: `[lewo + ΔX, góra + ΔY]`. |
| `original_rect` | `[x, y, szerokość, wysokość]` na krawędziach pikseli; musi odpowiadać `origin_xy` i `original_shape`. |
| `validity` | Dokładnie `isfinite(samples)`. Maska jest wyznaczana z próbek MPP; prostokąt nie jest maską. |
| `status` | `ok`, `low_confidence` albo `manual_review`. |
| `quality_score` | Skończona liczba pewności z wyniku algorytmu. |
| `inherited_uncertainty` | Boolean: niepewność odziedziczona z wcześniejszych dopasowań sąsiednich klatek. |
| `previous` | Poprzedni etap tej samej klatki o identycznej strukturze albo `null`. Limit 32 etapów. |

Klatka z przesunięciem subpikselowym może mieć prostokąt większy niż obwiednia
ważnych próbek interpolacji. Nie rekonstruujemy prostokąta z NaN ani maski.
Eksporter sprawdza zgodność `valid_mask` z `isfinite(data)`; zachowuje gotowe
float64, NaN i pełny obszar bez ponownej interpolacji, skalowania lub kadrowania.
Wymiary źródła wraz z paddingiem muszą dawać wymiary obszaru; prostokąt musi
mieścić się w tym obszarze. Padding i odniesienie nie zmieniają się po usunięciu
klatki. `previous.canvas_shape` i jego skala muszą odpowiadać wejściu kolejnego etapu.

Parametry klatki `size_x_nm` i `size_y_nm` opisują zapisany obszar: jego
wymiary razy wspólna skala pikseli. Gdy wspólna skala nie istnieje, oba są
`null`. Offsety zapisanego obszaru są nieznane (`null`); oryginalne offsety
i pola znajdują się w historii. Kanał, jednostka sygnału, czas, napięcie, prąd,
kąt, pochodzenie oraz surowy nagłówek zachowują wartości źródłowe.

Odczyt zawsze tworzy wejście nowej sesji. `ImageFrame.alignment` jest historią,
a nie obiektem `RegistrationResult` z odzyskanymi oryginałami. Podgląd pokazuje
obrys i opis historii; przełącznik aligned jest dostępny dopiero po nowej
udanej rejestracji. Eksport tego wejścia jako original zachowuje historię V2.
Nowa rejestracja bierze faktycznie wczytane próbki; NaN/Inf odrzuca z podaniem
przyczyny. Skończone wejście jest dozwolone także ze znacznikiem aligned.
Po nowej rejestracji eksport zapisuje nowy etap i poprzednią znaną historię.

V2 podlega tym samym regułom SHA-256, rozmiaru, liczby klatek i walidacji
całości co V1. Niepełna albo sprzeczna geometria unieważnia cały dodatek;
film nadal można otworzyć bez zgadywania historii. Inne czytniki repo
odczytują wartości MPP i wspólny nagłówek, ale nie interpretują dodatku V2.
Odczyt NaN przez WSxM pozostaje osobnym, niepotwierdzonym sprawdzeniem.
