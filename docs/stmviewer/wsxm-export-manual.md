# Próba ręczna: jeden zapis MPP i białe tło

[Ujednolicenie ticketu 13](implementation/issues/13-white-background.md).
Z worktree Viewera: `conda activate netcat`, `python -m stmviewer.main`.

1. Otwórz `data/MOVIE_3.MPP`, wybierz Optical Flow i wykonaj rejestrację.
   Alternatywa bez lokalnych pomiarów: `tests/stmviewer/fixtures/registration/subpixel.mpp`
   i Phase. Powiększony obraz ma białe tło poza pomiarem. Zmiana gamma
   zmienia obraz, ale nie biel tła; to samo dotyczy miniatur.
2. Kliknij **Zapisz MPP…**. Typ pliku oferuje wyłącznie **MPP original**
   i **MPP aligned**, domyślnie aligned. Zapisz np. jako `data/manual-white.mpp`.
   Obok ma powstać `manual-white.mpp.stmviewer.json`. Nie ma dodatkowych
   wariantów WSxM/NaN ani pytania o sposób zapisu braków.
3. Otwórz MPP w WSxM. Oczekuj szczegółów pomiaru i jasnego dodatkowego
   obszaru. MPP zawiera w tle maksimum danej klatki: jego kolor zależy
   od palety WSxM. Dla bieli użyj skali szarości i zakresu każdej klatki:
   Settings → Movie Settings → Palette range → Fit to frame Max/Min values.
   Klatka stała/pusta nie ma rozpiętości; zewnętrzny program ustala jej wygląd.
4. Otwórz parę w STM Viewerze. Oczekuj tego samego białego tła, obrysu
   i historii co przed zapisem, również na środkowej i ostatniej klatce.
   Informacja o brakach nadal jest zachowana. Rejestracja takiego wejścia
   nadal zgłasza dotychczasowe ograniczenie NaN/Inf; nie rejestruje sztucznego tła.
5. Dla MOVIE_3 sprawdź numerycznie (Python w `netcat`):

```bash
PYTHONPATH=. python tests/stmviewer/check_aligned_mpp.py --source data/MOVIE_3.MPP --saved data/manual-white.mpp --method optical_flow_median
```

Oczekiwane: wszystkie 17 klatek, próbki, NaN i geometria zgodne dokładnie.
Dla wzorca subpixel podaj jego ścieżkę jako `--source` i pomiń `--method`.

6. Otwórz stary `data/MOVIE_3-aligned.mpp`. Wybierz **MPP original** i nową
   nazwę. Nie wykonuj kolejnej rejestracji. Zapis używa nowego jasnego tła
   i zachowuje wcześniejszą historię. Brak nowego wyniku rejestracji oznacza,
   że okno oferuje tylko original.
7. Skopiuj wyłącznie nowy MPP pod inną nazwę, bez JSON, i otwórz w Viewerze.
   Komunikat wskaże brak możliwości odtworzenia braków. Sztuczne tło pozostaje
   wtedy zwykłymi liczbami. Do analizy przenoś zawsze kompletną parę.

Lokalny plik do próby: `data/MOVIE_3-aligned-white.mpp` + `.stmviewer.json`.
Wszystkie 17 klatek odzyskuje dokładne próbki i historię; w samym MPP
wyłącznie braki zostały zastąpione maksimum klatki. Oryginałów nie nadpisano.
Stare V1/V2 oraz V3 z ciemnym tłem nadal są odczytywane.

Odbiór ręczny użytkownika potwierdzono 2026-10-26: „teraz jest ok. testy manualne ok”.
Systemu nie wskazano; końcowe odbiory platform pozostają osobnymi ticketami.
Próby automatyczne Qt/Wine są raportowane osobno w przekazaniu.
