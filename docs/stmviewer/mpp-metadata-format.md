# Metadane towarzyszące MPP — wersja 1

Kontrakt importu [ticketu 11](implementation/issues/11-mpp-metadata-import.md),
2026-10-23. Ten etap odczytuje metadane **original**. Eksport original jest
w tickecie 12; pełna historia i geometria aligned w tickecie 13. V1 odrzuca
rodzaj aligned z czytelnym powodem, zamiast częściowo interpretować jego dane.
Rozszerzenie kontraktu musi zachować odczyt V1 i otrzymać nową wersję.

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

## Struktura

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
(obrót 180° względem tablic Viewera) i tworzy dodatek V1. Cała pozostała seria
zachowuje wymiary, wartości, NaN, kolejność, czasy i pochodzenie. Podgląd nie
jest wejściem eksportera. Istniejące historyczne pochodzenie jest zachowane;
przy jego braku pochodzi z faktycznego źródła i indeksu klatki.

Wspólny nagłówek używa wyłącznie wspólnych znanych parametrów. Każda oś
bez wspólnej skali ma rozmiar pikselowy w `a.u.`; różne/nieznane jednostki
sygnału dają `a.u.`, kanał `Unknown`. Nieznane napięcie, prąd, offset lub kąt
są pomijane. Znany wspólny prąd zapisuje się w nA: stary czytnik interpretuje
`A` jako angstrom. Znane czasy w nagłówku mają jednostkę sekund i bieżące
indeksy, bez uzupełniania braków. Dokładne parametry wszystkich klatek,
łącznie z surowymi nagłówkami i opisami czasu, pozostają w JSON.

Eksporter zapisuje parę tymczasową na tym samym systemie plików, synchronizuje
zapis i zabezpiecza kopie zastępowanych plików przed podmianami. Błąd lub
anulowanie powoduje przywrócenie wcześniejszych plików; niepowodzenie samego
przywracania zachowuje kopie i wskazuje ich katalog. Po twardej awarii między
podmianami niezgodny stary dodatek jest odrzucany przy odczycie dzięki SHA-256.
Nie jest to obietnica atomowości dwóch plików ani odporności na utratę zasilania.
