# Samowystarczalny projekt STM Domains — format 1

Wprowadzony w SD-V4-13. Rozszerzenie `.stmdomains`, kontener ZIP/ZIP64,
UTF-8 JSON i tablice NPY int32/bool bez pickle. Jeden plik przenosi **cały oryginalny
MPP**, nawet gdy wynik obejmuje jedną klatkę. Nie wymaga zewnętrznego JSON,
MPP ani paczki v0.4. Jest to zapis pracy; eksport PNG/CSV dodaje ticket 14.

| Część | Zawartość |
| --- | --- |
| `manifest.json` | `format=stmdomains`, `version=1`, wersja aplikacji zapisującej, czas UTC oraz rozmiar i SHA-256 każdej pozostałej części. |
| `source.mpp` | Dokładne bajty przyjętego MPP, kopiowane strumieniowo. |
| `input.json` | Potrzebny podzbiór importu: wersja, źródło, mapa serii, rejestracja, detekcje, segmentacje i zapisany stan wejścia. Bez historycznych modeli i wyników MolTrack. |
| `project.json` | Pochodzenie i diagnostyka importu, mapa klatek, stabilne klucze `SHA256_MPP:indeks_źródłowy`, widok, szkic i jedna analiza albo `null`. |
| `catalogues/<id>.json` | Zakres i indeksy dopasowania, parametry, pochodzenie oraz bezpieczne tablice/liczby stanu PCA/klas/kalibracji. ID jest skrótem treści katalogu. |
| `frames/<indeks>.json` | Stan klatki, przypisania wszystkich dostępnych oznaczeń, powody odmów, klasy/kolory, parametry i metadane rzeczywistego wykonania, odwołanie do katalogu. |
| `frames/<indeks>.npy` | Opcjonalna mapa obszarów domen w siatce oryginalnej klatki. Zera oznaczają brak domeny w masce, nie niewykonaną analizę. |
| `frames/<indeks>.barriers.npy` | Opcjonalna maska bool barier z SD-V4-15, w siatce oryginalnej klatki. Zawiera także faktycznie zastosowane poszerzenie. |

Indeksy w pliku są od zera; UI pokazuje numery od jedynki. Domeny pozostają
lokalne dla klatki. Tożsamość klasy obejmuje katalog. Kopia tego samego wyniku
zachowuje ID analizy i katalogu, a nowy przebieg otrzymuje nowe ID analizy.
Nowe otwarcie ma nową tożsamość sesji w pamięci, co nie zmienia tożsamości wyniku.

Analiza zawiera wybrany zakres, listę zapisanych klatek, ich jawne stany oraz
plan/stan przebiegu, jeśli są dostępne. `not_run`, `error`, `unavailable`,
`no_annotations` i `insufficient_data` nie są wynikiem z zerowym przypisaniem.
`unavailable` oznacza część starszego przebiegu już niedostępną w pamięci.
Zapis nie scala automatycznie rezultatów różnych przebiegów. Auto zachowuje
ranking i odmowę wyboru; zapisywany ostatni przebieg może być inny od wyniku
nadal wyświetlanego po nieudanej próbie.

Widok obejmuje klatkę, raw/aligned, gammę, zoom/środek, warstwy i krycie,
tryb Domeny/Klasy/Wejście oraz tempo odtwarzania. Otwieranie zawsze zaczyna od
pauzy. Osobny szkic formularza nie zastępuje użytych parametrów wyniku.
Jeżeli katalog wybrany w szkicu nie należy do zapisywanej analizy, szkic po
otwarciu wymaga jawnego wyboru dostępnego katalogu lub dopasowania nowych klas.

Odczyt weryfikuje wersję, spis, rozmiary, sumy, mapę i tożsamość klatek,
powiązania oznaczeń/klas/domen, liczniki, kształt i ID masek oraz odcisk wejścia
wyniku. Nie uruchamia dopasowania ani segmentacji. Bez stanu katalogu można
oglądać zachowane przypisania; nowe klasy wymagają jawnego dopasowania i nie
dostają starego ID z samego podglądu. Obsługa starego formatu wymaga jawnej
migracji; nie zgadujemy interpretacji nieznanej wersji.

MPP jest haszowany podczas importu i ponownie przy zapisie. Zmiana źródła
zatrzymuje zapis. Pochodzenie zachowuje skrót oryginalnego JSON, ścieżki źródeł,
wynik potwierdzenia dopasowania MPP i informację, że historyczny import nie
zapewniał skrótu MPP. Bieżący odcisk nie jest dowodem tożsamości dawnego pomiaru.

Zapis używa pliku tymczasowego w katalogu celu, `fsync` i atomowego
`os.replace`. Anulowanie przed publikacją lub błąd pozostawia stary plik.
Podgląd otwartej pracy zostaje zastąpiony dopiero po pełnej walidacji odczytu.
Sumy sprawdzają integralność, nie uwierzytelniają autora pliku.

Ograniczenia wersji 1: 64 MiB na rekord JSON, 16 GiB rozpakowanej zawartości,
50 000 części kontenera. Czytnik MPP nadal ładuje surową serię do pamięci.
Wewnętrzna kopia MPP i rekordów jest odtwarzalnym cache w katalogu tymczasowym,
zwalnianym wraz z ostatnim użytkownikiem serii. Wyniki i maski mają cache
maksymalnie trzech klatek. Walidacja czyta nagłówki i ID masek w blokach
1 MiB oraz weryfikuje przypisania bez dekodowania wejściowych segmentacji;
pełne rastry powstają dopiero dla żądanych klatek.
Od SD-V4-15 dotyczy to także masek barier: sprawdzane są kształt, typ bool,
wartości 0/1 i zgodność liczby pikseli z metadanymi. Wynik bez maski zachowuje
brak, a nie fałszywą pustą maskę. Parametry opisu w wyniku muszą zgadzać się
z katalogiem; zapisany stan PCA/klas musi mieć zgodne wymiary.
Nie wymagamy wszystkich masek w RAM. Pełna historia wielu analiz, ręczne
korekty/historia edycji i eksport nie należą do 13. Nie dopisujemy brakujących
miar fizycznych ani pełnego pokrycia do przybliżonych obszarów domen.

SD-V4-15 rozszerza format 1 o opcjonalną maskę, flagę jej obecności w rekordzie
klatki, parametry opisu/barier w planie i szkicu oraz warstwę `barriers` w widoku.
Bieżący czytnik otwiera wcześniejsze projekty wersji 1: brak dodatkowych
ustawień oznacza dotychczasowe wartości bazowe, brak rastra pozostaje jawny.
Nie ma automatycznego przeliczania. Starsza aplikacja sprzed 15 może odrzucić
projekt z nową częścią kontenera; nie deklarujemy zgodności nowszych zapisów
ze starszymi czytnikami. [Parametry i podgląd](advanced-settings.md).
