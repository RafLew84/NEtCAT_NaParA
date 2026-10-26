# Próba ręczna: zapis WSxM z odtwarzaniem braków

Poprawka [ticketu 13](implementation/issues/13-wsxm-compatibility-fix.md).
Z worktree Viewera: `conda activate netcat`, `python -m stmviewer.main`.

1. Otwórz `data/MOVIE_3.MPP`, wybierz Optical Flow i wykonaj rejestrację.
   Alternatywa bez lokalnych pomiarów: `tests/stmviewer/fixtures/registration/subpixel.mpp`
   i Phase. Powiększony obraz zawiera szachownicę poza pomiarem.
2. Kliknij **Zapisz MPP…**. W polu Typ pliku domyślna opcja to
   **MPP aligned — WSxM**. Pozostałe: original — WSxM, original — NaN,
   aligned — NaN. Zapisz pod nową nazwą, np. `data/manual-wsxm.mpp`.
   Obok ma powstać `manual-wsxm.mpp.stmviewer.json`.
3. Otwórz MPP w WSxM. Oczekuj widocznych szczegółów pomiaru zamiast całego
   czarnego obrazu. Tło poza pomiarem ma minimum klatki. Jeśli kontrast jest
   słaby: Settings → Movie Settings → Palette range → Fit to frame Max/Min values.
4. Otwórz tę samą parę w STM Viewerze. Wrócą szachownica, obrys i historia,
   a komunikat metadanych poinformuje o odtworzeniu braków WSxM.
   Sprawdź pierwszą, środkową i ostatnią klatkę. Rejestracja danych z
   odtworzonymi NaN nadal zgłasza dotychczasowe ograniczenie NaN/Inf.
5. Dla danych MOVIE_3 sprawdź numerycznie (Python w `netcat`):

```bash
PYTHONPATH=. python tests/stmviewer/check_aligned_mpp.py --source data/MOVIE_3.MPP --saved data/manual-wsxm.mpp --method optical_flow_median
```

Oczekiwane: wszystkie 17 klatek, próbki, NaN i geometria zgodne dokładnie.
Dla wzorca subpixel podaj jego ścieżkę jako `--source` i pomiń `--method`.

6. Już otwarty stary `data/MOVIE_3-aligned.mpp` również można poprawnie
   zapisać: wybierz **MPP original — WSxM** i nową nazwę. Nie wykonuj kolejnej
   rejestracji. Zapisuje to wczytane obrazy wraz z wcześniejszą historią.
7. Zapisz również jako **MPP original — NaN**. Ten wariant zachowuje braki
   bezpośrednio w MPP, a dotychczasowe czytniki repo rozpoznają NaN bez V3.
   Otwieranie go w sprawdzonym WSxM może ponownie dawać czarny obraz.
8. Skopiuj wyłącznie MPP WSxM pod inną nazwę, bez JSON, i otwórz w Viewerze.
   Sztuczne tło pozostanie skończone; komunikat wskaże brak możliwości
   odtworzenia braków. Oryginalna kompletna para pozostaje do analizy.

Wynik wygenerowany poprawionym eksporterem lokalnie:
`data/MOVIE_3-aligned-wsxm.mpp` + `.stmviewer.json`.
Próbki odtwarzają się dokładnie we wszystkich 17 klatkach; fizyczny MPP
jest bajtowo identyczny ze sprawdzoną wcześniej kopią podglądową. JSON V3
odróżnia go od samej kopii `-preview`. Oryginałów nie nadpisano.

Odbiór ręczny użytkownika i Windows: oczekują. Próby automatyczne Qt/Wine
są raportowane osobno w przekazaniu i nie zastępują tych sprawdzeń.
