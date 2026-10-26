# Ticket 16 — AVI z pełnym obszarem aligned

Implementacja do ręcznego odbioru. Uruchomienie z katalogu repozytorium:

```bash
conda activate netcat
python -m stmviewer.main
```

Przycisk i menu nazywają się **Zapisz AVI…**. Pole **Obrazy** w oknie opcji
pozwala wybrać original albo aligned; domyślnie wybrany jest aktualny podgląd.
Bez gotowego, kompletnego wyniku rejestracji dostępne jest tylko original.
Zmiana wersji w oknie zapisu nie zmienia wersji podglądu.

## Dane

Przygotowane lokalnie: `data/avi-ticket16/drift.mpp`, `anisotropic.mpp`
i `mixed.mpp`, każdy z towarzyszącym JSON. Odtworzenie:

```bash
PYTHONPATH=. python tests/stmviewer/make_aligned_avi_fixtures.py
```

Każdy film ma cztery klatki 80 × 80 z trzema rozpoznawalnymi obiektami,
przesunięciami i różną jasnością. Phase daje pełny obszar **92 × 87**.
Przesunięcia XY względem pierwszej: (0, 0), (7, −4), (−5, 3), (−2, −1).
`drift` ma kwadratowe piksele, `anisotropic` skalę X dwukrotnie większą od Y,
`mixed` brak kalibracji X pierwszej klatki. Po rejestracji `mixed` pozostaje
w pikselach również po usunięciu pierwszej klatki.

Dziesięć lokalnych filmów porównawczych ma nazwy zaczynające się od
`drift-black-frame`, `drift-gray-shared`, `drift-white-neutral`,
`anisotropic-gray-shared` i `mixed-gray-shared`, każdy w MJPG oraz FFV1.
Powstały po usunięciu odniesienia, z trzech pozostałych aligned, przy 1 FPS.
Wariant szary ma gamma 2 i wspólny kontrast; czarny/biały gamma 1 i kontrast
osobny. Wykonaj także własny eksport przez GUI.

## Próba ręczna

1. Otwórz `drift.mpp`. **Zapisz AVI…** oferuje tylko original; anuluj okno.
   Uruchom Phase. Podgląd przejdzie na aligned, informacja poda 92 × 87 px.
2. Przybliż i przesuń podgląd. Otwórz eksport: domyślna wersja to aligned,
   podsumowanie podaje **92 × 88 px** (jeden wiersz dopełnienia u dołu).
   Przełączenie na original zmienia rozmiar na **80 × 80**, a powrót
   na aligned przywraca 92 × 88. Oba wybory dotyczą pełnego obrazu.
3. Anuluj, wybierz klatkę 1 i usuń ją. Bez ponownej rejestracji wybierz
   w AVI aligned, zakres **1–2**, **1 FPS**, FFV1. Zapisz film i odtwórz
   w VLC. Są dwie klatki, nadal 92 × 88; położenia pól pomiaru odpowiadają
   podglądowi, tło nie jest obcinane. Plik ma domyślny sufiks `-aligned.avi`.
4. Powtórz eksport w MJPG. Rozmiar, kolejność, FPS i położenia są takie same;
   kompresja może zmieniać szczegóły pikseli. Nie ma obrysu pola z podglądu,
   paneli aplikacji ani opisów na filmie.
5. Porównaj gamma z podglądu (ustaw 2) i neutralną 1, oba kontrasty oraz
   czarne/szare/białe tło. Wspólny kontrast zachowuje różnice jasności
   pomiarów, osobny je normalizuje. Tło braków i dopełnienia nie zmienia się
   od gamma. Kontrast obejmuje tylko ważne próbki wybranego zakresu.
6. Ponownie otwórz `drift.mpp`, wykonaj Phase i usuń klatkę **2**, która
   wyznacza skrajny zasięg. Eksport choćby jednej pozostałej klatki nadal
   ma **92 × 88**, bez zmiany położenia. Tylko kolejne „Rejestruj” może
   wyznaczyć inny obszar; sam eksport nie przelicza dopasowania.
7. Otwórz `anisotropic.mpp` i wykonaj Phase: aligned AVI ma **184 × 88**,
   a po zaznaczeniu **Proporcje pikselowe** — **92 × 88**. Dla `mixed.mpp`
   po Phase oczekuj **92 × 88**, także po usunięciu pierwszej klatki.
8. Przełącz podgląd na original. Nowe okno eksportu domyślnie pokazuje
   original, ale pozwala wybrać aligned. Sprawdź oba filmy i zgodny sufiks
   proponowanej nazwy. Zapis nie zmienia bieżącej klatki ani podglądu.
9. Podczas dłuższego eksportu zmień podgląd original/aligned, klatkę, gamma
   i zoom. Rozpoczęty film zachowuje wybrane obrazy i ustawienia. Rejestracja,
   usuwanie, import, Play i drugi eksport są niedostępne do zakończenia.
   Anuluj zapis zastępujący istniejący AVI: poprzedni plik pozostaje.
   Po zakończeniu lub anulowaniu można uruchomić nową rejestrację.

Do kroku 9 można wygenerować większy, skończony wzorzec do Phase:

```bash
PYTHONPATH=. python tests/stmviewer/make_aligned_avi_fixtures.py --long
```

`long.mpp` ma 256 klatek 512 × 512, około 537 MB, z powtarzalnym dryfem
zamiast rosnącego przesunięcia. Po otwarciu wykonaj Phase; przy zapisie
wybierz wspólny kontrast i anuluj podczas liczenia poziomów lub kodowania.
Dane i filmy pozostają lokalne, poza Git.

Lokalna tymczasowa kopia VLC z poprzednich etapów:

```bash
/tmp/stmviewer-avi-vlc/vlc data/avi-ticket16/drift-gray-shared-FFV1.avi
```

Wyniki prób automatycznych oraz VLC są zapisane w [przekazaniu](handoff.md).
Akceptacja użytkownika pozostaje do wykonania; odbiory platform Ubuntu
oraz Windows pozostają osobnymi ticketami 20 i 21.
