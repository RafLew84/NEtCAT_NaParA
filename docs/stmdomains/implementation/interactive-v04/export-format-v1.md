# Eksport CSV/PNG — format 1

[Ticket SD-V4-14](14-export-csv-png.md), [odbiór i test ręczny](acceptance-14.md).
Eksport zapisuje jeden wybrany przebieg: wyświetlany wynik, ostatnią próbę
albo same oznaczenia wejściowe. Zakres klatek jest niezależny od zakresu
dopasowania klas. Nie dopasowuje modelu, nie analizuje brakujących klatek
i nie łączy wyników z różnych przebiegów. Nie zastępuje projektu `.stmdomains`.

## Katalog i metadane

**Plik → Eksportuj PNG/CSV…** tworzy nowy podkatalog we wskazanym miejscu.
Istniejąca nazwa jest odrzucana; wcześniejszy eksport pozostaje bez zmian.
Pliki powstają w katalogu tymczasowym, a publikacja następuje po zakończeniu
całości. Błąd lub anulowanie przed publikacją usuwa tylko tę tymczasową pracę.
Nie deklarujemy odporności na utratę zasilania.

| Plik | Zawartość |
| --- | --- |
| `manifest.json` | `format=stmdomains-export`, `version=1`, czas UTC, SHA-256 źródłowego MPP, pochodzenie danych, ID i zakres analizy, metadane wykonania i katalogi klas, widok, opcje eksportu oraz rozmiary i SHA-256 części. |
| `README.md` | Automatycznie dołączony opis kolumn, jednostek, mianowników i braków. |
| `frame-NNNNNN.json` | Tożsamość klatki/wyniku/katalogu, faktyczne parametry i metadane wykonania, definicje klas i stan katalogu, diagnostyka oznaczeń, rejestracja, prostokąt oryginalnego pola w widoku oraz ustawienia eksportu. |
| `frames.csv` | Jeden wiersz na każdą wybraną klatkę, także bez analizy. |
| `molecules.csv` | Każde dostępne oznaczenie wejściowe i jego przypisanie albo przyczyna odmowy/wyłączenia. |
| `domains.csv` | Istniejące domeny na klatkach z kompletnym wynikiem. |
| `classes.csv` | Klasa × klatka z kompletnym wynikiem, także klasy z zerową liczbą przypisań. |
| `frame-NNNNNN.png` | Obraz z podpisem, legendą i metadanymi tekstowymi PNG pod kluczem `STM Domains`. |

CSV i PNG są wybierane niezależnie; JSON i opis towarzyszą każdemu eksportowi.
Szkic następnej próby nie zastępuje parametrów istniejącego wyniku. Przy
odmowie dopasowania przyczyny/ranking pozostają w metadanych przebiegu,
także gdy nie powstał katalog ani wynik klatki. Szczegółowe rastry i źródłowy
sygnał do ponownego otwarcia zachowuje zapis projektu, nie eksport.

## Kolumny i brakujące dane

CSV: UTF-8, separator przecinek, kropka dziesiętna, standardowe cytowanie.
Brak liczby oznacza puste pole; zero oznacza dostępną wartość zero.
Nie tworzymy sum serii ani tożsamości śledzonej między klatkami.

Wspólne kolumny: `analysis_id`, `catalogue_id`, `frame_key` (SHA-256 MPP
i indeks źródłowy), `working_index`/`source_index` od zera oraz
`working_number`/`source_number` od jedynki. `analysis_status` zachowuje
stan wyniku albo przebiegu: m.in. `complete`, odmowę, `error`, `not_run`.
`not_in_analysis` oznacza klatkę poza wybranym przebiegiem, a `unanalysed`
eksport bez analizy. Pełne ID pozostają w tabelach/JSON; podpis PNG je skraca.

W `frames.csv`:

- `time_s` i `time_status`: rzeczywisty czas pomiaru, jeśli dostępny;
  szybkość odtwarzania nie służy do wyznaczania czasu;
- `status_reason` i `annotation_status`: przyczyna stanu i niezależna
  dostępność wejściowych oznaczeń;
- `input_count`: liczba dostępnych oznaczeń; puste pole przy brakującej
  lub uszkodzonej sekcji oznaczeń;
- `active_count`: mianownik przyjęty przez analizę, bez duplikatów
  i oznaczeń poza polem; ich liczby to `excluded_duplicates`/`excluded_outside`;
- `assigned_count`, `unassigned_count`, `domain_count`: liczby z kompletnie
  obliczonej klatki; brak wyniku/odmowa nie dostaje zer;
- `counts_status` i `percentage_status`: kompletność liczebności/udziału,
  niezależnie od wykonania analizy; `assigned_percent` to 100 × przypisane
  / aktywne, a nie zwalidowana wykrywalność. Zerowy mianownik daje stan
  `undefined` i puste pole procentu.

`molecules.csv` zachowuje `detection_id`, `origin`, `source_view`,
`center_x_raw_px`/`center_y_raw_px` (środek bboxa w surowej klatce),
`confidence`, włączenie do mianownika `included_in_analysis_denominator`,
`domain_local_id`, `class_id`, `provisional_class_id`, `assignment_status`
i `rejection_reason`. Domena 0 to znane nieprzypisanie; pusta domena oznacza
brak wyniku dla oznaczenia. ID klasy ma znaczenie w danym katalogu; lokalne
ID domeny nie identyfikuje tej samej domeny na następnej klatce.

Tabele klas/domen podają `assigned_count`, `active_denominator`, udział
i jego stan. Mianownik zawsze dotyczy całej klatki, bez renormalizacji
według wycinka lub widocznych warstw. Wiersz klasy ma puste `domain_local_id`.
Brak wierszy w `domains.csv` należy interpretować razem z `frames.csv`.

## Powierzchnie i obraz

`field_area_px2` to pole surowego obrazu bez paddingu. `approx_area_px2`
to liczba pikseli przybliżonej maski domen: na klatce suma jej zajętych
pikseli, dla klasy suma jej domen. `approx_area_status` to `approximate`
albo `unavailable`. `approx_area_percent_field` odnosi tę maskę do pełnego
pola obrazu. `touches_field_edge` opisuje kontakt maski z brzegiem;
nie określa rozmiaru domeny poza pomiarem.

`physical_area_nm2` i `coverage_area_px2` pozostają puste ze statusem
`unavailable`: obecna metoda nie dostarcza zwalidowanej kalibracji fizycznej
ani pokrycia materiału. Nie tworzy również wysp; brak tabeli wysp nie jest
twierdzeniem o ich braku w pomiarze. Maska przybliżona nie stanowi
zwalidowanego obszaru fizycznej domeny.

PNG używa tych samych warstw i kolorów co podgląd: Klasy/Domeny/Wejściowe,
centra, ramki, dostępne maski molekuł, obszary/obrysy/numery domen i krycie.
Zachowuje gammę i normalizację z podglądu. Pełny widok surowy to oryginalne
pole, a wyrównany to płótno z paddingiem i obramowaniem pola pomiaru.
Wycinek jest opisany współrzędnymi widoku; dla zakresu używa tego samego
prostokąta na każdej klatce. Legenda/liczniki nadal dotyczą całej klatki.

Szerokość części obrazowej wynosi 320–4096 px; podpisy i legenda powiększają
cały PNG. Maksimum 64 mln pikseli chroni przed skrajnie wysokim wycinkiem.
Metadane PNG zawierają rzeczywisty prostokąt wycinka, prostokąt obrazu
w pliku, numery klatki, ID, stan, gammę, tryb, normalizację i legendę.
Eksport nie zmienia predykcji ani aktualnie oglądanej klatki.

Ręczne korekty, ich rewizje i eksport wyniku po edycji należą do
[ticketu 25](25-export-manual-corrections.md). Ten format zachowuje
obecnie dostępne wyniki automatyczne.
