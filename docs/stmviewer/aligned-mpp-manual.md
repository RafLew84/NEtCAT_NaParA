# Próba ręczna: aligned do MPP

Ticket [13](implementation/issues/13-aligned-mpp.md). Z katalogu worktree:

```bash
conda activate netcat
python -m stmviewer.main
```

Na Windows użyj przygotowanego środowiska według [README](README.md#uruchomienie).
Wzorce poniżej są już w repo; ich odtworzenie: `python tests/stmviewer/make_registration_fixtures.py`.
Przed użyciem skryptów kontrolnych ustaw `export PYTHONPATH=.` (Linux)
albo `$env:PYTHONPATH = "."` (PowerShell).
Zapisuj wyniki pod nowymi nazwami, np. w lokalnym `data/`. Przenoś MPP wraz
z towarzyszącym `<nazwa>.mpp.stmviewer.json`.

1. Otwórz `tests/stmviewer/fixtures/registration/subpixel.mpp` (2 klatki).
   Wybierz Phase i Rejestruj. Zapisz widoczne w panelu przesunięcie oraz
   wymiary aligned; pokaże się powiększone pole z szachownicą i żółtym obrysem.
2. Wybierz klatkę 1 i Usuń klatkę. Zostaje dawna klatka 2; obszar oraz
   historyczne odniesienie nie zmieniają się. Ustaw gamma 2, powiększ obraz.
3. Kliknij **Zapisz MPP…** (również Plik / Ctrl+S). W oknie zapisu pole
   **Typ pliku** zawiera `MPP original` i `MPP aligned`. Domyślnie wybrane
   jest aligned, czyli oglądana wersja. Zapisz jako `data/subpixel-aligned.mpp`.
   Gamma, zoom i bieżąca klatka pozostają bez zmian.
4. Przed zmianą serii zapisz drugi plik, wybierając **MPP original**:
   `data/subpixel-original.mpp`. Ten plik zawiera tylko pozostałą oryginalną
   klatkę 64 × 64. Wybór wersji eksportu nie zmienia podglądu.
5. Sprawdź oba zapisy poza aplikacją:

```bash
python tests/stmviewer/check_aligned_mpp.py --source tests/stmviewer/fixtures/registration/subpixel.mpp --saved data/subpixel-aligned.mpp --keep 2
python tests/stmviewer/check_mpp_export.py --source tests/stmviewer/fixtures/registration/subpixel.mpp --saved data/subpixel-original.mpp --keep 2
```

Oczekiwany wynik: `OK` w obu raportach. Kontrola aligned sprawdza dokładne
bajty próbek, NaN, maskę, pełny obszar, padding, prostokąt, przesunięcia,
odniesienie, parametry i pochodzenie. Referencję wylicza ponownie z pełnej
serii źródłowej metodą Phase, a następnie uwzględnia usunięcie klatki 1.
Dla innych metod CPU można podać `--method` (`--help` pokazuje nazwy).

6. Otwórz `data/subpixel-aligned.mpp`. Nowy import ustawia gamma 1 i dopasowanie.
   Powinien mieć te same wymiary obszaru, szachownicę oraz źródłowy obrys.
   Panel **Historia aligned** pokazuje źródłowe 64 × 64, przesunięcie,
   odniesienie do dawnej klatki 1 i źródłowe pole/offsety.
   Plik otwarty i pochodzenie pozostają rozdzielone. Widok nazywa się
   **original**, ponieważ te zapisane piksele są wejściem nowej sesji;
   wcześniejszych obrazów sprzed interpolacji nie ma w tym pliku.
7. Kliknij Rejestruj. Oczekuj czytelnego komunikatu o NaN/Inf, bez zmiany
   obrazu. Zapisz ponownie jako original pod trzecią nazwą i otwórz: historia
   i obrys nadal powinny być dostępne. Bez nowej rejestracji okno zapisu
   oferuje tylko original.
8. Otwórz `tests/stmviewer/fixtures/registration/integer.mpp`, wykonaj Phase,
   usuń klatkę 2 (skrajną), zapisz aligned jako `data/integer-aligned.mpp`.
   Obszar pozostaje **53 × 34**,
   choć klatka wyznaczająca jego prawą krawędź została usunięta. Sprawdź:

```bash
python tests/stmviewer/check_aligned_mpp.py --source tests/stmviewer/fixtures/registration/integer.mpp --saved data/integer-aligned.mpp --keep 1 3
```

9. Dodatkowa próba rejestracji skończonych danych ze znacznikiem aligned:
   otwórz `tests/stmviewer/fixtures/asymmetric.stp`, wykonaj Phase jednej
   klatki, zapisz aligned. Otwórz ten plik i ponownie Rejestruj. Operacja
   jest dozwolona, bo próbki są skończone. Po kolejnym zapisie aligned
   i otwarciu panel pokaże jeden wcześniejszy etap rejestracji.
10. Anuluj okno zapisu, a następnie odmów zastąpienia istniejącej pary:
    wcześniejsze pliki powinny pozostać bez zmian. Przy dłuższym zapisie
    dostępne są postęp i Anuluj; nawigacja/gamma działają, import/usuwanie/
    rejestracja są chwilowo zablokowane. Własny większy pomiar można wykorzystać
    do próby anulowania po rejestracji. Dokładne próby błędu między podmianami
    obu plików wykonuje automatyczny zestaw testów.

Odbiór ręczny użytkownika: oczekuje. Testy Qt sterowane skryptem są
odrębnym sprawdzeniem automatycznym. Ten scenariusz nie wymaga WSxM ani AVI.

Dodatkowa próba WSxM: [diagnoza MOVIE_3-aligned.mpp](wsxm-aligned-investigation.md)
wykazała czarny obraz przy NaN w WSxM 5.0 Develop 12.0 pod Wine.
Weryfikator danych potwierdza poprawny zapis; kopia ze sztucznym tłem
służy wyłącznie do oglądania. Nie zmienia to wymogu zachowania NaN w MPP.
