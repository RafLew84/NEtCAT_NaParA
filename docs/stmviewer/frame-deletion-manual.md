# Próba ręczna — usuwanie klatek (ticket 07)

Z katalogu `NEtCAT-viewer`, w środowisku `netcat`, uruchom:

```bash
python -m stmviewer.main
```

Przycisk **Usuń klatkę** znajduje się pod obrazem, po prawej od sterowania
odtwarzaniem. Usuwa bieżącą klatkę tylko z otwartej serii. Pliki na dysku
pozostają bez zmian. Operacja nie ma cofania; ponowne otwarcie źródła
przywraca jego pełną zawartość.

## Dane

- `tests/stmviewer/fixtures/mpp/known-times.mpp`: trzy obrazy, źródłowe
  numery 1/2/3 i czasy **10/20/35 s**. Obrazy: L po lewej, gradient, L po prawej.
- `tests/stmviewer/fixtures/mpp/timed.MPP`: te same obrazy, czasy
  **1,5 s / nieznany / 4,25 s**.
- `tests/stmviewer/fixtures/series/klatka1.stp`, `klatka2.stp`, `klatka10.stp`:
  różne obrazy, parametry i jednostki, kolejność naturalna 1–2–10.
- Mieszana seria: `tests/stmviewer/fixtures/series/klatka1.stp` oraz
  `tests/stmviewer/fixtures/s94/frame2.s94`, `frame10.S94`.
  Kolejność naturalna: frame2, frame10, klatka1.
- `tests/stmviewer/fixtures/mpp/truncated.mpp`: błędny import.
- Rzeczywisty pomiar: `data/MOVIE_3.MPP` — 17 klatek; można też użyć własnych
  danych w lokalnym `data/`.

Małe wzorce są w Git. Filmy MPP można odtworzyć:

```bash
python tests/stmviewer/make_mpp_fixtures.py
```

## Kroki i oczekiwane wyniki

1. W pustym programie Usuń klatkę jest nieaktywne. Otwórz `known-times.mpp`.
   Wybierz klatkę 2, ustaw 1 kl./s, uruchom Play i od razu kliknij Usuń klatkę.
   Odtwarzanie zatrzymuje się. Pozostają obrazy 1 i 3; oglądasz **2 z 2**,
   ale panel źródła podaje **Klatka źródłowa MPP: 3**, **Czas pomiaru: 35 s**.
   Obraz odpowiada dawnej trzeciej klatce; zaznaczona jest tylko jej miniatura.
2. Poprzednia pokazuje dawną pierwszą klatkę z czasem **10 s**, Następna —
   dawną trzecią z **35 s**. Nie dopisujemy czasu 20 s ani nie skracamy przerwy.
   Wznowienie Play obejmuje tylko dwa pozostałe obrazy.
3. Zatrzymaj Play i wybierz 2 z 2. Usuń klatkę: widać poprzednią, teraz
   **1 z 1**, źródłowy numer 1 i 10 s. Play jest nieaktywne; gamma, zoom
   oraz Usuń klatkę pozostają dostępne.
4. Usuń jedyną klatkę. Oczekuj pustego podglądu „Brak otwartego obrazu”,
   pustych miniatur, numeru **0 z 0**, źródła „—” i „Brak danych.”.
   Nawigacja, Play, Usuń klatkę i ustawienia obrazu są nieaktywne.
5. Otwórz ponownie `known-times.mpp`: wracają wszystkie trzy klatki i czasy
   10/20/35 s. Nowa seria zaczyna od pierwszej klatki w pauzie, gamma 1,
   z dopasowanym obrazem. Otwieranie działa również po opróżnieniu programu.
6. Otwórz `timed.MPP`. Usuń pierwszą klatkę: zostaje obraz o źródłowym
   numerze 2 i **nieznanym** czasie. Następna ma źródłowy numer 3 i **4,25 s**.
   Nieznany czas nie jest uzupełniany na podstawie FPS ani sąsiednich klatek.
7. Otwórz serię STP lub mieszaną STP/S94. Ustaw gamma, zoom, przesunięcie
   i Proporcje pikselowe; zanotuj pochodzenie i parametry kolejnej klatki.
   Usuń środkową: ustawienia podglądu pozostają, a obraz i miniatura zachowują
   swoje parametry oraz pochodzenie. Zmienia się pozycja w serii.
8. Po usunięciu spróbuj otworzyć `truncated.mpp`, a następnie anuluj wybór
   pliku. Poprzednia skrócona seria pozostaje; usunięte klatki nie wracają.
   Podczas dłuższego importu można usuwać klatki starej serii. Anulowanie
   zachowuje jej aktualny stan; poprawne zakończenie zastępuje go nową serią.
9. Powtórz usunięcie środka i ponowne otwarcie na `data/MOVIE_3.MPP`.
   Po usunięciu klatki 2 widać pozycję **2 z 16**, źródłowy numer **3**.
   Po ponownym otwarciu film nadal ma **17** klatek.

Nie dodano odwracania kolejności ani cofania. Zachowanie wyniku aligned po
usuwaniu zostanie podłączone w tickecie rejestracji; obecnie próba dotyczy original.

## Sprawdzenia i status odbioru

103 testy Viewera przechodzą, w tym 10 nowych przypadków usuwania.
Mypy strict: 15 plików bez błędów. Testy porównują widoczne obrazy, miniatury,
metadane, czasy z brakami i lukami oraz niezmienność plików. Obejmują też
usunięcie starej serii podczas importu i jego późniejszy sukces/anulowanie.

Automatyczna próba Qt xcb użyła rzeczywistego dialogu, wzorca 10/20/35 s
oraz lokalnego `data/MOVIE_3.MPP`. Zaliczyła usunięcie podczas Play, wybór
następnej/poprzedniej, stan pusty i ponowne otwarcie; źródła pozostały
bajtowo niezmienione. Zrzuty obejrzano. To próba automatyczna, odrębna od
ręcznego odbioru użytkownika i odbioru Windows — te pozostają do wykonania.
Pełny wynik testów repo i przegląd: [przekazanie](handoff.md).
