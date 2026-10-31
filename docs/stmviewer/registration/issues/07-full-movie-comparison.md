# REG-07: Zapis prób i odbiór pełnych filmów

**What to build:** Użytkownik zapisuje lekką próbę rejestracji, ponownie ją
otwiera przy tych samych źródłach i porównuje pełne wyniki A/B bez dwóch
dodatkowych stosów obrazów w pamięci. Kończymy ocenę podstawowego wariantu XY.
**Blocked by:** [REG-06](06-independent-validation.md), w tym odbiór manualny.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).
W chwili realizacji REG-07 warianty z REG-02, REG-04 i REG-05 oraz ręczne korekty REG-02a
mają już działać na pełnej serii i współpracować z eksportem.
Porównanie wykorzystuje podgląd i renderowanie z REG-01 oraz istniejącą
nawigację. Ten ticket nie buduje osobnego odtwarzacza dwóch filmów.

## Zakres i kryteria odbioru

- [ ] Z GUI można zapisać/otworzyć dokument próby: wersję formatu, tożsamość
  źródeł i kolejność klatek, wersję kodu/commit, metodę i pełne ustawienia,
  fragmenty kontroli,
  XY par/skumulowane, statusy i uzyskane diagnozy. Dokument nie zawiera obrazów.
- [ ] Próby ręczne z REG-01a zachowują oznaczenie pochodzenia, początkowe XY,
  opis próby użytej jako punkt startu (jeśli była), łączną korektę, końcowe XY
  i jawny brak automatycznej oceny jakości. Odtwarzane są zatwierdzone próby,
  bez historii kliknięć ani niezastosowanego szkicu. Odczyt nie promuje ręcznej
  próby pary do pełnego aligned i nie nadaje jej pewności backendu.
- [ ] Dokument kompletnego wyniku po REG-02a zachowuje bazową metodę i wersję,
  XY bazowe, zastosowane nadpisania par, ręczne pochodzenie i końcowe XY oraz brak
  oceny jakości. Nie utożsamia zastosowanych korekt filmu z diagnostycznymi próbami
  par. Odtwarza poprawiony wynik do porównania przy właściwych oryginalnych źródłach;
  samo wczytanie dokumentu nie podmienia aktywnego aligned ani eksportu.
- [ ] Źródła są identyfikowane zawartością i pochodzeniem, nie wyłącznie nazwą.
  Tożsamość obejmuje również metadane mające wpływ na geometrię.
  Przy ponownym otwarciu można wskazać przeniesiony plik. Inna zawartość,
  kolejność, wymiary lub nieobsługiwana wersja są odrzucane z wyjaśnieniem.
- [ ] Po ponownym otwarciu właściwego filmu można porównywać dwa kompletne
  wyniki we wspólnym układzie odniesienia, przechodzić przez klatki i oglądać
  stałe pary. Obrazy A/B są odtwarzane na żądanie z oryginałów i transformacji.
- [ ] Dokument zachowuje także próby par oraz przerwane/niekompletne próby,
  z błędem i faktycznie dostępnymi wynikami. Takie dane otwierają się jako
  diagnostyka; nie tworzymy brakujących XY ani pełnego aligned z częściowego przebiegu.
- [ ] Próba diagnostyczna jest odrębna od aktywnego aligned. Samo otwarcie
  zapisu do porównania nie podmienia wyniku do MPP/AVI. Dokument nie udaje MPP
  ani nie zmienia jego dotychczasowego schematu metadanych.
- [ ] Zapis/odczyt ma walidację, postęp/anulowanie dla długich operacji i
  ochronę wcześniejszego pliku oraz prób po błędzie. Zmiana składu serii
  nie przypisuje starych transformacji do nowych numerów klatek.
- [ ] Pełne MOVIE_4 i MOVIE_8 są porównane z bazą według protokołu. Raport
  obejmuje sukcesy, przerwania, niejednoznaczne pary, czas i szczyt RAM.
  Nie pomijamy trudnych par, aby uzyskać pozornie kompletny wynik.
- [ ] Sprawdzono dotychczasowe Play/zoom/gamma, usuwanie, anulowanie oraz
  zapis/odczyt kompletnego MPP i odtworzenie AVI wybranego nowego wariantu.
  Nowe porównanie nie wymaga GPU i mieści się na stanowisku z 16 GB wolnego RAM.

Poza zakresem: automatyczne promowanie metody, zapisywanie dużych danych
w Git, zamknięcie wcześniejszych ticketów odbioru platform lub dużych eksportów.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Próba → dokument → odczyt przy źródłach:** zachowanie ustawień i wyników,
  weryfikacja zawartości, przeniesiona ścieżka, zła wersja, niezgodna seria,
  uszkodzenie i atomowe zachowanie poprzedniego pliku po błędzie/anulowaniu.
  Dla ręcznej próby: to samo XY, pochodzenie i brak oceny jakości po odczycie.
- **Pełne wyniki A/B → oglądane klatki:** wspólne odniesienie, prawidłowe
  wartości po interpolacji i ograniczona pamięć renderera, bez pełnych kopii.
- **Nowy wariant → MPP/AVI:** wartości, geometria, maski ważności i pochodzenie.
  Rzeczywisty odczyt filmu uzupełnia test jednostkowy; VLC i GUI są osobnym odbiorem.

## Próba manualna

1. Dla obu filmów zapisz bazową próbę A i wybrany nowy wariant B z wszystkimi
   ustawieniami. Uruchom program ponownie i otwórz zapisy przy właściwym źródle.
2. Obejrzyj pełne sekwencje, jeśli obie próby je wytworzyły, stałe pary oraz
   wskazane problemy. Po odmowie zapisz miejsce/przyczynę i porównaj dostępne
   próby par. Przełączaj A/B przy wspólnym widoku. Dodaj przypadki niewykorzystane
   do wyboru ustawień; zapisz decyzje i ograniczenia dla każdego filmu.
3. Przenieś kopię źródła do innego katalogu i wskaż ją. Następnie sprawdź
   przygotowany niezgodny plik: program ma odmówić przypisania do niego wyników.
4. Powtórz otwieranie/przełączanie prób i obserwuj pomiar RAM dostarczony
   przez realizującego. Nie powinny narastać pełne kopie kolejnych filmów.
5. Zapisz kompletny aligned przyjętego wariantu do MPP+metadane oraz AVI,
   jeśli został uzyskany. Otwórz MPP w programie, AVI w VLC; sprawdź próbki
   kontrolne, obraz i krawędzie. W razie odmowy na pomiarze sprawdź sam eksport
   na `cpu.mpp`, a brak pełnego wyniku pomiarowego pozostaw jawnym ograniczeniem.
6. Zapisz także ręczną próbę z REG-01a, ponownie ją otwórz i porównaj
   z algorytmem. Sprawdź początkowe XY, korektę, wynik końcowy, pochodzenie
   i zachowanie pełnego aligned.
7. Powtórz zapis/odczyt dla pełnego wyniku z dwiema zastosowanymi korektami
   REG-02a. Sprawdź pary źródłowe, bazę, nadpisania i skumulowane XY, porównanie
   odtworzonego filmu oraz zachowanie aktywnego aligned po samym wczytaniu zapisu.
8. Podejmij jawną decyzję: zachować wariant eksperymentalny, poprawić go albo
   zakończyć na obecnym wyniku. Dopiero osobno zdecyduj o REG-08 i REG-09.

**Oczekiwany wynik:** odtwarzalna, udokumentowana ocena całych filmów.
Nie wymagamy deklaracji skuteczności na każdym obrazie, jeśli dowody jej nie wspierają.
