# 11: Ustaw i uruchom pełną analizę w jednym oknie

**ID:** SD-V4-11

**What to build:** Użytkownik otwiera jedno okno „Analiza…”, wybiera obrazy,
źródło klas i wszystkie parametry, a jednym przyciskiem oblicza domeny
bieżącej klatki, zakresu lub całej serii. W tym samym miejscu widzi postęp,
statusy klatek i może porównać poprzedni oraz nowy wynik.

**Blocked by:** [06: Strojenie tworzenia domen](06-tune-domain-formation.md),
[08: Przelicz zakres lub całą serię](08-analyze-series.md),
[09: Reguluj akceptację klasy](09-tune-class-acceptance.md),
[10: Reguluj test porządku](10-tune-order-test.md).

**Status:** done — implementacja `d18048b`; odbiór ręczny użytkownika oczekuje.
[Raport, sprawdzenia i instrukcja ręcznego odbioru](acceptance-11.md).

Decyzja użytkownika **2026-11-03**: osobny ticket o numerze 11.
Poprzedni zakres 11, usunięty jako duplikat dopasowania klas w 05/07,
pozostaje historyczny; ten ticket dotyczy wspólnego okna i konfiguracji.
**12 — Auto nie jest wykonany** i po 11 rozszerzy zakładkę Klasy.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru),
uruchamianie i testowanie w **netcat**, cel **1000**, twardy limit **1500
fizycznych linii na plik kodu i testów**. Podział zakładek i obliczeń ma
zachować odrębne odpowiedzialności; wspólne okno nie oznacza jednego dużego pliku.

## Układ i zachowanie

**Analiza → Analiza…** otwiera jedno niemodalne okno. Dotychczasowe pięć
okien zastępuje ten wspólny punkt wejścia. Przycisk analizy przy obrazie
również otwiera to okno z wybraną bieżącą klatką, zachowując szkic parametrów.

| Zakładka | Ustawienia |
| --- | --- |
| Zakres | Bieżąca klatka, wybrany zakres lub cała seria do obliczenia domen. |
| Klasy | Dopasuj nowe / użyj istniejących; osobny zakres odkrywania klas, domyślnie zgodny z analizą; ręczne K1–8; margines i mnożnik promienia akceptacji. |
| Porządek | Kwantyl kontroli, minima punktów lokalnych i efektywnych, promień i sigma w jednostkach odstępu d, z wyjaśnieniem ograniczenia dotyczącego rzędów. |
| Domeny | Wszystkie dotychczasowe parametry tworzenia domen z 06, z jednostkami i walidacją. |

Pod zakładkami są wspólne podsumowanie planowanego przebiegu, **Analizuj**,
**Anuluj**, postęp, statusy klatek i porównanie poprzedni/nowy dla oglądanej
klatki. Można nawigować po obrazach, gdy okno jest otwarte. W małym oknie
kontrolki pozostają dostępne, a postęp nie powoduje skakania obrazu.

Pola tworzą jeden szkic konfiguracji, dostępny przed pierwszym obliczeniem.
Przejście między zakładkami, zamknięcie i ponowne otwarcie okna oraz
nawigacja po tej samej serii nie gubią parametrów. Zmiana oglądanej klatki
aktualizuje cel w trybie „Bieżąca klatka”, nie podmienia reszty szkicu.
Przy otwarciu innej serii szkic i wybór katalogu są resetowane w sposób jawny.
**Z wyświetlanego wyniku** jawnie kopiuje jego ustawienia; samo porównanie
wyników nie zmienia szkicu. **Przywróć bazowe parametry** resetuje progi
akceptacji, porządku i domen, zachowując wybór zakresów i klas.

## Kryteria akceptacji

- [x] Jedno okno i wspólny przycisk obejmują pełną drogę od wybranych danych do widocznych domen dla klatki, zakresu i serii. Nie pozostają niezależne formularze z rozbieżnymi kopiami ustawień ani przycisk uruchamiający niejawny wariant K5.
- [x] Zakres analizy i zakres odkrywania klas są rozdzielone. Można odkryć klasy z 259–268 i obliczyć tylko 259 albo wszystkie wybrane klatki. K oznacza liczbę klas, a numery domen są lokalne.
- [x] Wszystkie parametry czterech zakładek trafiają do obliczeń i metadanych każdego wyniku, również akceptacja klas w analizie serii. Nie ma cichego powrotu do wartości bazowych ani pobierania części ustawień z innej oglądanej klatki.
- [x] „Dopasuj nowe” używa wybranego testu porządku do doboru próbek. „Użyj istniejących” zachowuje katalog bez fitu; lokalny katalog można stosować tylko do jego niezmienionych danych, a analiza wielu klatek wymaga zgodnego katalogu wspólnego. Brak zgodności ma czytelny komunikat bez ukrytego dopasowania.
- [x] Zmiana promienia/sigmy/kwantyla przelicza właściwą kalibrację. Samo strojenie parametrów przy istniejącym katalogu nie zmienia jego ID. Wynik jednej klatki jest zgodny z wynikiem tej klatki w serii dla tego samego katalogu, danych i parametrów.
- [x] Szkic, parametry wyświetlanego wyniku i konfiguracja trwającego przebiegu są rozróżnione. Start utrwala kompletny zestaw i zakres; nawigacja podczas pracy ich nie podmienia. Edycja pól nie zmienia obliczonego obrazu, licznika ani historycznego wyniku.
- [x] Działają kopiowanie ustawień z wyniku, przywrócenie bazowych parametrów, porównanie i zachowanie szkicu opisane powyżej. Podsumowanie przed startem mówi, które klatki otrzymają domeny i skąd pochodzą klasy.
- [x] Obliczenia działają w tle. Anulowanie dopasowania zachowuje wcześniejszy katalog i wynik; anulowanie serii zachowuje ukończone klatki, a pozostałe jawnie oznacza jako niewykonane. Wcześniejsze wyniki takich klatek nie udają wyników bieżącego przebiegu. Błąd, otwarcie innego zapisu i zamknięcie aplikacji nie publikują spóźnionych rezultatów.
- [x] Zachowano widok molekuł i obszarów, zoom, gamma, raw/wyrównany, wyjaśnienia odmów, rozróżnienie braku danych od obliczonego zera oraz funkcje odebrane w 05–10. Odbiór obejmuje rzeczywiste GUI także przy rozmiarze okna głównego 900×650.
- [x] Testy publicznych obliczeń i kontrolek sprawdzają pełne przekazanie parametrów, zgodność klatka/seria przy tym samym katalogu, szkic/porównanie, anulowanie, brak danych i błędy. Raport podaje wykonane testy automatyczne, próby GUI i oddzielny status ręcznego odbioru użytkownika.
- [x] Testy i uruchomienia wykonano w netcat, sprawdzono limit 1000/1500 linii, zaktualizowano instrukcję menu i kolejny ticket 12. Dostarczono działające przykłady i dokładne oczekiwane wyniki testu ręcznego.

## Test ręczny użytkownika

1. Uruchom aplikację w netcat i otwórz dotychczasowy MolTrack/MPP TTMAPP.
   Przejdź do 259. Menu Analiza oraz przycisk przy obrazie prowadzą do tego
   samego okna z czterema zakładkami; można nadal przeglądać obrazy.
2. Wybierz analizę tylko bieżącej klatki, nowe K5 i zakres odkrywania
   259–268. Ustaw margines **0,060**, mnożnik klasy **0,80**, kwantyl
   **0,925**, otoczenie porządku **3 / 4⁄3 × d**, minimum domeny **6**
   i odległość łączenia **1,80 × d**. Pozostałe parametry bazowe. Przełącz
   zakładki i zamknij/otwórz okno: szkic i podsumowanie muszą zostać.
3. Kliknij Analizuj. Wynik powstaje tylko na 259. Metadane i opis użytych
   parametrów potwierdzają cały zestaw, w tym akceptację klas. Raport
   wykonawcy podaje liczniki oczekiwane dla tej konkretnej konfiguracji.
4. Wybierz **Użyj istniejących klas** i analizę 259–268, zachowując parametry.
   Oblicz zakres i obejrzyj kolejne klatki. Klasy mają to samo ID katalogu;
   wynik 259 jest identyczny z krokiem 3. Wszystkie klatki używają także
   ustawionego marginesu 0,060 i mnożnika 0,80.
5. Wróć do jednej klatki i zachowanego katalogu. Zmień kwantyl oraz parę
   promień/sigma na **2 / 1 × d**, przelicz, porównaj poprzedni/nowy.
   Sprawdź nową kalibrację i odmowy. Porównanie nie nadpisuje szkicu;
   kopiowanie z wyświetlanego wyniku jest osobną, jawną czynnością.
6. Sprawdź **Przywróć bazowe parametry**: zakresy i wybór klas pozostają,
   obraz zmienia się dopiero po Analizuj. Przejście do innej klatki zachowuje
   szkic, a podsumowanie pokazuje nowy cel. Powtórz próbę w mniejszym oknie.
7. Uruchom całą serię i anuluj po kilku klatkach. Obejrzyj ukończone
   wyniki i statusy niewykonanych klatek; poprzednie wyniki pozostają
   rozróżnione. Sprawdź także anulowanie dopasowania i zamknięcie w trakcie pracy.
8. Na gotowych kontrolach z 07/10 sprawdź K1, losowe/rzędowe otoczenie,
   słabe wsparcie i brak oznaczeń. Brak zgodnego katalogu albo nieudana
   kalibracja daje wyjaśnienie i nie usuwa wcześniejszego wyniku.

## Granice zadania

To ujednolicenie istniejących operacji i ich ustawień, bez nowego algorytmu
detekcji. Auto dodaje dopiero 12 w zakładce Klasy tego okna. Nie obejmuje
zapisu projektu/presetów na dysku, eksportu, ręcznych korekt ani historii
większej niż dostępne porównanie poprzedni/nowy. Nie wymaga modeli v0.4.
Wydzielenie wspólnej konfiguracji i kontrolek należy do tego zadania;
odbiór kończy się działającym przebiegiem w UI, nie samym przeniesieniem formularzy.
