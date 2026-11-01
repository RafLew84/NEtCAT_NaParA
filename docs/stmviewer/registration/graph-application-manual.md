# REG-08c — zastosowanie grafu do filmu

Status: **ready-for-review**. Ręczny odbiór użytkownika oczekuje.

## Uruchomienie i gotowe dane

W katalogu `NEtCAT-viewer`, środowisko `netcat`:

```bash
python -m stmviewer.main
```

Przycisk **Otwórz sesję…** wczytuje samodzielny plik. Przygotowane przykłady:

| Dane | Sesja przed zastosowaniem grafu |
| --- | --- |
| Mały wzorzec, 9 klatek | `/tmp/reg08c-known-v1/ready-to-apply.stmsession` |
| MOVIE_4, 362 klatki, okno 5 | `/tmp/reg08c-movie4-v1/ready-to-apply.stmsession` |
| MOVIE_8, 84 klatki, okno 3 | `/tmp/reg08c-movie8-v1/ready-to-apply.stmsession` |

MOVIE_4 ma już usunięte źródłowe klatki 1 i 2. Nie usuwaj ich ponownie.
Sesje zawierają oryginały, aktywny łańcuch z przykładową korektą X+1 oraz
kandydatów LS i Hubera. Korekta X+1 służy sprawdzeniu zachowania programu;
nie jest proponowaną poprawką fizycznego dryfu. Wzorzec ma zadane relacje,
filmy STM — zachowane rzeczywiste pomiary Outdoor z REG-08a.

W tych samych katalogach są `ls-corrected.stmsession` i
`huber-corrected.stmsession`: graf zastosowany i przykładowa korekta Y+1.
Są również małe eksporty MPP+metadane i AVI FFV1/MJPG. Katalog `/tmp` jest
nietrwały; wybrane wyniki można zachować przez **Zapisz sesję…**.
Do zastosowania zapisanej próby i korekt nie potrzeba modelu, Torch ani GPU.

## Zastosowanie i powrót

1. Otwórz małą sesję `ready-to-apply`. Zanotuj aktywne XY i liczbę korekt.
   Ustaw inną gamma, wybierz klatkę 6 i powiększ obraz.
2. Otwórz **Dopasowanie wieloklatkowe…**. U góry lewego panelu, w grupie
   **Aktywny film**, wybierz **LS — wspólne XY** albo **Huber 1 — próg 2 px**.
   Wybranie kompletnego wyniku przełącza również podgląd filmu.
   Oglądanie kandydata nie zmienia aligned w głównym oknie.
3. Sprawdź model, okno, solver, źródła, mosty i liczbę korekt do zastąpienia.
   **Pełna kolejność źródeł…** rozwija przewijaną listę.
   Kliknij **Zastosuj wynik do filmu**. Po sukcesie główne okno pokazuje tę
   samą klatkę aligned, cały nowy obszar, poprzednią gamma i zatrzymane Play.
4. Obejrzyj Play, original/aligned i szczegóły w zoomie. Original pozostaje
   bez zmian. Przejście na nową bazę zastępuje poprzednie ręczne poprawki,
   ale poprzedni wynik wraz z nimi jest zachowany do przywrócenia.
5. W zakładce **Film** porównaj kandydata, aktywny film i zachowany poprzednik.
   **Przywróć zachowany wynik** odtwarza wcześniejsze XY, bazę i korekty
   z tych samych oryginałów. Nie uruchamia Deep ani solvera.
   To jeden zachowany wynik: przywrócenie zamienia go z aktywnym filmem,
   więc ponowne kliknięcie pozwala wrócić do grafu. Nie jest to pełna historia.

Na dłuższym filmie rozpocznij zastosowanie i kliknij **Anuluj zmianę filmu**,
również podczas przywracania. Poprzedni film i korekty mają pozostać w całości.
Operacja może zakończyć się szybciej niż kliknięcie; anulowanie sprawdzono także
automatycznie z kontrolowanym zatrzymaniem zewnętrznej interpolacji.
Podczas pracy import, usuwanie, zapis i kolejne operacje są zablokowane;
podgląd, zoom i gamma pozostają dostępne.

## Ręczna korekta bazy grafowej

1. Zastosuj **LS** w małej sesji, zamknij okno grafu, wybierz klatkę 6,
   otwórz **Porównaj parę…** i **Popraw dopasowanie z filmu**.
   W sekcji korekty filmu sprawdź liczby dla pary 5→6:

   | Wartość | ΔX, ΔY w pikselach |
   | --- | --- |
   | Surowy pomiar pary | `(3, −13)` |
   | Baza LS: G[6] − G[5] | około `(6.072718, −15.389892)` |
   | Baza Hubera, jeśli wybrano ten wariant | około `(3.435460, −13.338691)` |

   Start korekty odpowiada aktualnemu filmowi. **Usuń korektę tej pary z filmu**
   przywraca różnicę G wybranego solvera, a nie surowy pomiar modelu.
2. Kliknij X+1 i **Zakończ korektę**. Główny film jeszcze się nie zmienia.
   Kliknij **Zastosuj do filmu**. Zmienia się klatka 6 i wszystkie następne;
   1–5 zachowują XY względem odniesienia. Nowy padding może przesunąć obraz
   w oknie, więc sprawdzaj również zapisane XY.
3. Ponów zastosowanie tej samej próby: korekta nie może się podwoić.
   Popraw też parę 6→7, potem usuń pierwszą i drugą korektę osobno.
   Usunięcie jednej zachowuje drugą; po obu wraca baza G.
4. Zastosowane ręczne przesunięcia nie przeliczają grafu. Jego reszty i wagi
   dotyczą zamrożonej bazy, nie są oceną ręcznie zmienionego filmu.
5. Oblicz nowego Hubera z innym progiem. Dotychczasowy film i poprawki
   pozostają do chwili jawnego zastosowania nowego wyniku.

## Sesja, eksport i odmowy

- Z aktywnym grafem i dwiema korektami użyj **Zapisz sesję…**, zamknij program
  i otwórz ten plik ponownie. Aligned, poprawki i poprzednik mają być dostępne
  bez modelu. Kontynuuj korektę i sprawdź przywrócenie poprzednika.
- Zapisz aligned MPP wraz z `.stmviewer.json`, odczytaj go ponownie i porównaj
  obrazy, granice, XY oraz pochodzenie. MPP przechowuje gotowe próbki i opis
  historii; nie zastępuje edytowalnej sesji i nie zawiera oryginałów sprzed interpolacji.
- Wyeksportuj krótki aligned AVI w FFV1 i MJPG; odtwórz oba w VLC. Sprawdź
  kolejność, tempo, tło i brak nakładek diagnostycznych.
- Usuń klatkę z aktywnego filmu: geometria pozostałych i eksport pozostają.
  Dalsza korekta oraz zastosowanie starego grafu wymagają przeliczenia aktualnej serii.
- Otwórz `/tmp/stmviewer-reg08b-fixtures/disconnected-with-huber.stmsession`:
  zastosowanie ma być niedostępne z powodem. Dla nieukończonego Hubera nie ma
  cichego zastosowania LS. Przykład: MOVIE_4, okno 3 z materiałów REG-08b.

## Odbiór na STM

Na MOVIE_4 obejrzyj pary 29→30, 35→36, 44–46, 61→62, 94–97,
pierwsze 150 klatek i pełny film; numeracja po usunięciu źródłowych 1/2.
Na MOVIE_8 obejrzyj pełny film i wybraną trudną parę, np. 16→17.
Zastosuj wybrany graf, popraw ręcznie rozpoznawalne struktury i sprawdź
propagację dalej. Zapisz ocenę funkcji oraz osobno jakości XY i tearingu,
zgodnie z [protokołem](manual-protocol.md).

[Wyniki automatyczne](graph-application-results.md),
[karta testów i przeglądu](reviews/REG-08c.md).
