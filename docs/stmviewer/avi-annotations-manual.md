# Ticket 17 — podziałka, numer i czas w AVI

Ręczny odbiór zatwierdzony przez użytkownika 2026-10-27: „testy manualne ok”.
Uruchomienie z katalogu repozytorium:

```bash
conda activate netcat
python -m stmviewer.main
```

W oknie **Zapisz AVI…** są trzy niezależne opcje: **Podziałka długości**,
**Numer klatki w bieżącej serii** i **Czas pomiaru**. Domyślnie są wyłączone,
także po ponownym otwarciu okna. Działają dla original i aligned.

Numer i czas są u góry po lewej, podziałka u dołu po lewej. Białe znaki
z cienkim ciemnym obrysem są czytelne na wszystkich tłach. Nie mają czarnych
prostokątnych pól; obraz wokół znaków pozostaje widoczny. Opisy zachowują
rozmiar i położenie w całym filmie. Rozmiar filmu
się nie zmienia. Opisy nie trafiają do MPP ani podglądu aplikacji.

## Dane

Gotowe lokalnie: `data/avi-ticket17/`. Odtworzenie wejściowych MPP i JSON:

```bash
PYTHONPATH=. python tests/stmviewer/make_avi_annotation_fixtures.py
```

- `calibrated.mpp`: 21 klatek 256 × 256, skala X 2 nm/px, Y 1 nm/px.
  Fizyczne proporcje AVI: 512 × 256; podziałka 100 nm ma 100 pikseli filmu.
- `unknown.mpp`: te same obrazy bez skali X; film 256 × 256, podziałka 50 px.
- `mixed.mpp`: pierwsza klatka ma inną skalę; cała seria daje 256 × 256
  i 50 px. Zakres omijający pierwszą klatkę ma wspólną skalę i może użyć nm.
- `drift.mpp`: skalibrowane obrazy z przesunięciami. Phase daje obszar
  268 × 263; AVI w proporcjach fizycznych ma 536 × 264 i podziałkę 100 nm.
- `tiny.mpp`: mały obraz do sprawdzenia odmowy zapisu kompletu opisów.

Czas pomiaru wynosi 0, 15, 30…300 s, z brakiem dla źródłowej klatki 7.
Osiem gotowych AVI w MJPG/FFV1 służy do porównania: calibrated/unknown/drift
po usunięciu klatki 3, zakres 5–10 przy 1 FPS; mixed obejmuje całą serię
przy 5 FPS. Parametry są w lokalnym `movies.json`. Wykonaj także własny zapis.

## Próba ręczna

1. Otwórz `calibrated.mpp`, usuń klatkę **3**. Pozostaje 20 klatek.
   Wybierz **Zapisz AVI…**, original, zakres **5–10**, FPS **1**, FFV1.
   Wszystkie trzy dodatki są początkowo wyłączone. Włącz je i zapisz.
2. Otwórz film w VLC: sześć klatek, 512 × 256. Numeracja to **5/20…10/20**,
   a czasy **75 s, brak, 105 s, 120 s, 135 s, 150 s**. Nie są to numery
   1–6 ani czasy wynikające z FPS. Podziałka: **100 nm**.
3. Powtórz zapis w MJPG i przy innym FPS. Teksty i podziałka mają to samo
   znaczenie, a FPS zmienia tylko tempo odtwarzania. Kompresja MJPG może
   zmiękczać krawędzie; FFV1 zachowuje raster dokładnie.
4. Sprawdź każdą opcję osobno oraz zapis ze wszystkimi wyłączonymi.
   Wyłączenie dodatków przywraca czysty obraz. Zmiana gamma na 2 oraz
   kontrastu osobnego/wspólnego zmienia obraz, lecz nie kolor znaków ani teł.
5. Powtórz próbę dla `unknown.mpp` i `mixed.mpp` z całą serią: podziałka
   jawnie podaje **px**. W `mixed` zakres 2–21 korzysta ze wspólnej skali
   i podaje nm. Przy niewiarygodnych, zastępczych metadanych (np. eksport
   TTMAPP) zaznacz **Proporcje pikselowe** w głównym oknie: także podziałka
   użyje px. Program nie rozpoznaje automatycznie nieoznaczonych wartości
   zastępczych w nagłówku.
6. Otwórz `drift.mpp`, wykonaj Phase, usuń klatkę 3 i zapisz aligned,
   zakres 5–10, z trzema opisami. Oczekuj 536 × 264, podziałki 100 nm
   i tej samej numeracji/czasów co wyżej. Porównaj czarne, szare i białe
   tło braków: tekst oraz podziałka są czytelne, a ostatni wiersz dopełnienia
   pozostaje wybranym tłem. Obrys z podglądu nie trafia do AVI.
7. Otwórz `tiny.mpp` i włącz trzy dodatki. Okno wyjaśnia, że obraz jest
   za mały, podaje wymagane wymiary i blokuje Zapisz przed wyborem ścieżki.
   Wyłącz dodatki: czysty eksport znów jest dostępny. Nic nie jest obcinane
   ani pomijane po cichu.
8. Podczas dłuższego eksportu zmień klatkę, gamma, zoom i original/aligned
   w podglądzie. Rozpoczęty film zachowuje swoje opisy i geometrię.
   Anulowanie nadal pozostawia wcześniejszy plik bez zmian.

Podziałka używa wspólnej skali wybranego zakresu i szerokości obrazu przed
technicznym dopełnieniem. Długość dobierana jest z 1/2/5 × potęga 10, do około
ćwierci szerokości; jej raster jest zaokrąglany do najbliższego piksela
(maksymalnie pół piksela różnicy). Tekst czasu podaje sekundy pomiaru.

Wyniki automatyczne i próby VLC: [przekazanie](handoff.md).
Ręczna akceptacja użytkownika została zapisana. Nie podano systemu wykonania
próby; zbiorcze odbiory Ubuntu oraz Windows są osobnymi ticketami 20 i 21.
