# REG-07 — zapis prób i porównanie pełnych filmów

Odbiór ręczny jest do wykonania przez użytkownika. Próby Qt offscreen i pomiary
opisane w [raporcie](full-trial-results.md) nie zastępują oglądania filmów ani VLC.

## Uruchomienie i dane

Z katalogu `NEtCAT-viewer`:

```bash
conda activate netcat
python -m stmviewer
```

Dane: `data/MOVIE_4.mpp`, `data/MOVIE_8.mpp`; krótka próba obsługi:
`tests/stmviewer/fixtures/registration/cpu.mpp`.
Dla MOVIE_4 **usuń pierwsze dwie klatki przed każdą rejestracją i odczytem próby**.
Zapisane numery odnoszą się do serii po tych usunięciach. MOVIE_8 pozostaje cały.
Baza porównań: Deep Matcher z lokalnym checkpointem Outdoor.

## Zapis i odczyt

1. Otwórz oryginalny film i wykonaj rejestrację. W sekcji **Próby rejestracji**
   wynik automatycznie pojawi się na liście **B**. Próby są lekkimi rekordami,
   bez kolejnych stosów obrazów. Nie są jeszcze zapisane na dysku.
2. Kliknij **Zapisz B…** i wybierz plik `*.stmtrial.json`. Zapis obejmuje
   ustawienia, wersję kodu, źródła, przesunięcia i dostępną diagnostykę.
   Oblicz drugą metodę i zapisz drugą próbę. Listy A/B pozwalają wybrać
   dowolne zachowane wyniki, również po ręcznej korekcie całego filmu.
3. Zamknij i uruchom program ponownie. Otwórz te same oryginały, wykonaj
   te same usunięcia, następnie **Otwórz próbę…** dla obu dokumentów.
   Wagi ani GPU nie są potrzebne do odtwarzania zapisanych wyników.
4. Wybierz pełne próby na listach **A** i **B**, następnie **Próba A** / **Próba B**
   w przełączniku pod nimi. Widok używa wspólnego obszaru i pierwszej
   pozostałej klatki jako odniesienia. Sprawdź suwak, miniatury, Play/Pause,
   zoom, przeciąganie i gamma. Zmiana A/B zachowuje powiększenie.
5. **Aktualny film** przywraca bieżący original/aligned. Wczytanie dokumentu
   nigdy nie zastępuje aktywnego aligned. **MPP/AVI eksportują aktywny wynik**,
   nawet podczas oglądania próby A/B. Aby eksportować wariant, wykonaj jego
   rejestrację w tej sesji; odczyt dokumentu służy porównaniu.

## Pary, ręczne poprawki i przerwania

- Ustaw klatkę w głównym oknie i kliknij **Porównaj parę z prób A/B…**.
  Otwiera się dotychczasowe okno pary: **wynik zachowany** oznacza A,
  **wynik bieżący** oznacza B. Dla zapisanej próby jednej pary wybór jest
  związany z jej źródłowymi klatkami. Innych par nie dopasowujemy przez zmianę numerów.
- Zatwierdź ręczne dopasowanie przez **Zakończ korektę**. Próba trafia do listy B
  w głównym oknie; zapisz ją i ponownie otwórz. Sprawdź XY, punkt startu,
  łączną korektę i komunikat o braku oceny jakości. Niezatwierdzone ruchy
  nie trafiają do dokumentu; samo zakończenie próby pary nie zmienia filmu.
- Wykonaj dwie korekty przez **Popraw dopasowanie z filmu** → ruchy XY →
  **Zakończ korektę** → **Zastosuj do filmu**. Zapisz ostatnią próbę filmu.
  Po ponownym odczycie obejrzyj odtworzone B i **Szczegóły prób A/B…**:
  bazę, nadpisane pary, pochodzenie, wynikowe XY i brak automatycznej jakości.
- Błąd lub anulowanie rejestracji także pozostawia próbę diagnostyczną na liście.
  Zapisz i otwórz ją. **Szczegóły prób A/B…** pokazują przyczynę i tylko uzyskane
  wyniki. Pełny podgląd odmówi utworzenia filmu z niekompletnej próby.
  Można porównywać obliczone pary. Gdy po Deep odmówił ECC lub lokalne fragmenty,
  dostępny start Deep ma wyraźną etykietę przerwanej próby; nie jest wynikiem hybrydy.

## Zgodność źródeł i bezpieczeństwo

- Skopiuj oryginał do innego katalogu, otwórz kopię i dokument próby — powinien
  zostać przyjęty. Jeśli źródło ma towarzyszące metadane, przenieś także je.
- Spróbuj otworzyć dokument przy innym filmie albo z inną kolejnością/usunięciami.
  Program ma odmówić, zachowując dotychczasowe próby i aligned.
- Anuluj zapis/odczyt podczas sprawdzania dużego filmu. Wcześniejszy dokument
  powinien pozostać poprawny. Podczas operacji nie można zmienić składu serii.
- Usunięcie klatki lub poprawne otwarcie nowej serii czyści listę prób z pamięci;
  zapisane pliki pozostają. Nie przypisujemy dawnych XY do nowych numerów.

## Ocena pomiarów i decyzja

Obejrzyj oba pełne filmy, gdy metoda dała komplet wyników. Stałe pary i trudne
przejścia są w [protokole](manual-protocol.md). Dla MOVIE_4 sprawdź szczególnie
29→30, 35→36, 44→45→46, 61→62, 94→95→96→97 i odcinek po klatce 150;
numery po usunięciu dwóch początkowych. Dodaj przypadki spoza wcześniejszego doboru.
Nie pomijaj odmów; zapisz parę, przyczynę i dostępne wyniki.

Powtórz odczyty i A/B, porównaj zużycie RAM z raportem. Dla kompletnego aktywnego
wyniku zapisz MPP+metadane i AVI, odczytaj MPP w aplikacji, AVI w VLC.
Sprawdź krawędzie, brakujące próbki i liczbę klatek. Przy odmowie pomiaru
sprawdź sam eksport na `cpu.mpp`, bez deklaracji sukcesu pełnej rejestracji.

Na końcu zanotuj ocenę wizualną: zachować wariant eksperymentalny, poprawić go
czy zakończyć na obecnym wyniku. REG-06 pozostaje odłożony; brak niezależnej
kontroli nie oznacza zerowego błędu. REG-08 wymaga osobnego zlecenia po odbiorze.
