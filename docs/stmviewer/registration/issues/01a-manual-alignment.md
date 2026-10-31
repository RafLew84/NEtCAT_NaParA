# REG-01a: Ręczne dopasowanie pary

**What to build:** W istniejącym oknie porównania użytkownik przesuwa klatkę
dopasowywaną względem nieruchomej klatki odniesienia przyciskami ±1 piksel X/Y,
ogląda nakładkę lub przełącza obrazy i zachowuje wynik jako ręczną próbę.
**Blocked by:** [REG-01](01-pair-comparison.md), w tym odbiór manualny — spełnione.
**Status:** ready-for-review
**Manualny odbiór:** oczekuje na użytkownika; implementacja i sprawdzenia wykonane 2026-10-31.
**Wykonawca:** Codex; baza przeglądu `c5ec70a8b7efc2d0892fc56b8b63c315b79d3b64`.
**Dodano do planu:** 2026-10-30, na zlecenie użytkownika.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).
Realizujemy po REG-01, przed REG-02, bez zmiany numerów istniejących ticketów.
REG-01 pozostaje zamknięty; nowe sterowanie ma własny odbiór.

## Zakres i kryteria odbioru

- [x] W tym samym oknie „Porównaj parę…” jest tryb dopasowania ręcznego.
  Klatka odniesienia pozostaje nieruchoma; przesuwamy kolejną klatkę względem
  poprzedniej. Nazwy „Odniesienie” i „Dopasowywana” oznaczają obrazy, natomiast
  A/B nadal oznaczają dwie próby dopasowania. UI nie miesza tych znaczeń.
- [x] Przyciski **X−, X+, Y−, Y+** zmieniają przesunięcie o dokładnie **1 piksel
  oryginału** na kliknięcie. +X oznacza ruch obrazu w prawo, +Y w dół;
  znaki odnoszą się do obrazu, nie fizycznego kierunku dryfu. Widoczne są
  bieżące całkowite ΔX/ΔY i jednostka px. Zoom oraz proporcje nie zmieniają kroku.
- [x] Dostępne są „Zacznij od zera” i „Koryguj wybraną próbę”. Druga opcja
  kopiuje XY i opis pochodzenia aktualnie wybranej próby A/B tej samej pary;
  jest niedostępna, jeśli tej próby brak. Można korygować wynik automatyczny
  lub wcześniejszy ręczny. Nie kopiujemy skumulowanego XY z pełnego aligned.
  Zachowujemy ułamkową część punktu startu: np. 2,4 → 3,4 po X+.
- [x] Podgląd reaguje na każdy krok. Działają nakładka 50/50 i przełączanie
  odniesienie/dopasowywana. Rozpoczęcie edycji i każdy ruch pokazują stan
  „Po dopasowaniu”; podejrzenie „Przed” pokazuje XY=(0,0) bez kasowania edycji.
  Zoom, punkt zakotwiczenia, gamma, proporcje i kontrast pary są zachowane.
- [x] Przeciąganie nadal przesuwa wspólny widok, a kółko zmienia zoom;
  nie zmieniają ręcznego XY. Każde odświeżenie stosuje całkowite XY do
  oryginalnych próbek, bez wielokrotnego przesuwania/interpolowania poprzedniego
  podglądu. Obowiązują stały kadr i ważność próbek z REG-01.
- [x] Ręczna edycja jest szkicem, odrębnym od gotowych prób A/B.
  „Przywróć początek” cofa wszystkie kroki do skopiowanego XY albo do zera.
  „Odrzuć edycję” przywraca wcześniejszą wybraną próbę i jej obraz.
  „Zastosuj jako B” tworzy nową niezmienną próbę B, zachowując przypięte A.
  Jeżeli wcześniejsze B ma służyć porównaniu, użytkownik przypina je jako A
  przed rozpoczęciem edycji; nie nadpisujemy A automatycznie.
- [x] Podczas szkicu wybór/przypinanie prób oraz start obliczeń automatycznych tej pary
  są zablokowane; przełączanie samych obrazów i warstw pozostaje dostępne.
  Po zastosowaniu lub odrzuceniu można znów przełączać A/B. Zmiana pary lub
  zamknięcie okna odrzucają szkic; nowy udany import/usunięcie klatki czyści
  porównanie jak w REG-01. Nieudany import zachowuje pasującą edycję.
- [x] Sterowanie ręczne działa bez uruchamiania estymatora i bez wag/GPU,
  także gdy wybrana metoda automatyczna jest niedostępna albo wcześniej
  zakończyła się błędem. Blokady podczas importu i pracujących zadań nadal
  obowiązują. Brak wspólnego ważnego obszaru jest wyraźnie komunikowany;
  można wrócić przyciskami albo zachować taką próbę diagnostyczną z tym opisem.
- [x] Próba ma jawne pochodzenie „ręczne”, początkowe XY, opis skopiowanej
  próby (jeśli była), sumę korekt i końcowe XY oraz wersję ustawień.
  Oznaczenie jakości mówi „ustawione ręcznie — jakość nieoceniona”. Nie
  dziedziczymy pewności algorytmu, nie dopisujemy procentu ani „OK backendu”.
  Nowa korekta zachowuje opis źródła, bez bezterminowego łańcucha kopii prób.
- [x] Ręczny wynik można przypiąć i porównywać z algorytmem. To lekka próba
  tej pary w sesji okna; oryginały, pełny aligned i aktywny wynik eksportu
  zachowują wartości. Zapis/odczyt prób ręcznych na dysk obejmuje REG-07.

Poza zakresem: ręczne składanie całej serii, podmiana przesunięć aktywnego
aligned i przeliczanie następnych klatek, obroty, zmiana skali, deformacje,
sterowanie ruchem obrazu przez przeciąganie, kroki mniejsze niż 1 px oraz
historia pojedynczych kliknięć. Ręczne dopasowanie jest oceną operatora;
nie staje się automatycznie prawdą odniesienia ani niezależną walidacją.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Punkt startu + ruchy → ręczna próba:** znaki i jednostki, start z zera
  i skopiowanej próby, zachowanie części ułamkowej, reset/odrzucenie/zastosowanie,
  pochodzenie i jawny brak oceny jakości. Powrót do tego samego XY daje ten sam
  podgląd; przypięta próba i źródłowe dane pozostają niezmienne.
- **Kontrolki GUI → obraz i A/B:** krok niezależny od zoom/pan/proporcji,
  wspólny kadr/kontrast, warstwy, przed/po, brak pokrycia, niedostępny backend,
  zmiana pary/import/usunięcie/zamknięcie oraz ochrona pełnego aligned.
  Przypadek z ułamkowym startem zapewnia realizujący, bez polegania na
  przypadkowym wyniku backendu na lokalnym filmie.
- Testy nie orzekają, czy ręcznie wybrane XY odpowiada fizycznemu dryfowi.
  Obowiązują limity plików i sprawdzenia z instrukcji aplikacji.

## Próba manualna

1. Uruchom `python -m stmviewer.main` w `netcat` z katalogu Viewera.
   Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp`, wykonaj pełne Phase,
   następnie otwórz porównanie pary 1→2 i ręczny start od zera.
2. Kliknij dwa razy X+ i raz Y−. Oczekuj XY=(+2,−1) i pokrycia znaczników
   w nakładce. Przełącz odniesienie/dopasowywana; sprawdź także przed/po.
   Powtórz dla 2→3 z trzema X− i dwoma Y+: XY=(−3,+2).
3. Przybliż obraz i przesuń wspólny widok. Powtórz jeden krok i jego odwrotność,
   także z innymi proporcjami: przywrócone XY, obraz i kadr mają być takie same.
   Samo przeciąganie/kółko nie zmienia liczb XY.
4. Zakończ szkic z poprzedniego kroku przez zastosowanie lub odrzucenie.
   Oblicz automatyczny wynik i przypnij jako A. Rozpocznij jego korektę,
   dodaj celowo 1 px, przywróć początek i odrzuć edycję. A/B pozostają jak były.
   Ponów korektę, zastosuj jako B, porównaj z A. Sprawdź pochodzenie, wartości
   i brak automatycznej oceny jakości. Na dostarczonym przykładzie ułamkowym
   sprawdź, że krok ±1 zachowuje ułamek początkowego przesunięcia.
5. Na MOVIE_4 i MOVIE_8 wykonaj ręczną próbę dla stałych par z protokołu.
   Można zacząć od zera mimo błędu ECC/Deep; lokalne wagi nie są potrzebne.
   Obejrzyj kilka struktur w różnych miejscach i zapisz, gdzie jedno XY
   poprawia nakładanie, a gdzie pozostaje rozbieżność lub tearing.
6. Przesuń wzorzec poza wspólne pole i sprawdź komunikat, potem wróć resetem.
   Zmień parę podczas niezastosowanej edycji, zamknij/otwórz porównanie,
   sprawdź zachowanie po imporcie/usunięciu. Powtórz podstawowe blokady
   przy trwającej automatycznej rejestracji.
7. Ponownie otwórz cpu.mpp i wykonaj pełne Phase; zanotuj wynik. Następnie
   zastosuj celowo inne ręczne XY w porównaniu pary. W głównym oknie obejrzyj
   aligned i wykonaj mały eksport MPP/AVI: korzystają z pełnego wyniku Phase
   sprzed ręcznej próby. Zapisz kartę REG-01a.

**Oczekiwany wynik:** użytkownik może sam ustawić przesunięcie pary, natychmiast
ocenić je wzrokowo i porównać z algorytmem w tych samych warunkach podglądu.
Po implementacji status `ready-for-review`; ręczny odbiór blokuje REG-02.


## Wykonanie — 2026-10-31

Implementacja `846a479`, poprawki przeglądu `2276755`; baza `c5ec70a`.
Kontrolki ręczne w oknie porównania, szkic od zera/próby i wynik B z pochodzeniem
oraz bez automatycznej pewności. Kroki 1 px nie zależą od widoku; skopiowany ułamek
pozostaje. Reset/odrzucenie, blokady zadań, ochrona A oraz pełnego aligned i eksportów.
Opis pochodzenia kolejnej ręcznej korekty obejmuje bezpośrednią próbę źródłową,
bez rekurencyjnego przechowywania całej historii.

14 nowych testów, po przeglądzie 28 testów par zaliczonych; mypy strict 38 plików,
Ruff oraz limit długości bez uwag. Pełne wyniki, ograniczenia i niezależny przegląd:
[karta REG-01a](../reviews/REG-01a.md). [Instrukcja manualna](../manual-alignment-manual.md)
zawiera zwykłą aplikację, stałe pary MOVIE i dostarczony ułamkowy wzorzec.

Rzeczywiste Qt xcb sterowane skryptem: 6 stałych par, ręczna próba po błędzie ECC
MOVIE_8 2→3, ułamkowy start oraz układ panelu sprawdzone. To automatyczna kontrola
funkcji, nie ocena jakości dopasowania przez użytkownika. REG-02 pozostaje zablokowany
przez ręczny odbiór REG-01a. Kod współdzielony nie wymaga zmiany.


## Propozycja zmiany nazw — 2026-10-31

Użytkownik zgłosił niejasne nazewnictwo i poprosił o prototyp zachowujący funkcje.
[Trzy warianty okna i źródło decyzji](../pair-window-prototype.md): osobna gałąź
`prototype/stmviewer-pair-naming`, commit `dd8b48f`. Użytkownik wybrał układ C
2026-10-31; implementacja `b7aaf37`. Karty „Wynik zachowany” / „Wynik bieżący”
zastępują listę A/B, „Zakończ korektę” zastępuje „Zastosuj jako B”. Porównywanie
jest opcjonalne, obliczenia i zakres ręcznej próby pozostają bez zmian.
Aktualne kroki GUI: [instrukcja manualna](../manual-alignment-manual.md).
Historyczne nazwy A/B w kontrakcie ticketu oznaczają odpowiednio wynik zachowany
oraz bieżący. REG-01a nadal wymaga odbioru manualnego nowego okna.
