# Poprawka 13: jeden zapis MPP i białe tło brakujących pikseli

Status: ready-for-review. Baza przeglądu: `7123d1b`.
Zlecenie użytkownika: ujednolicić obsługę dodanego obszaru poprzez białe tło.

- W GUI wracają tylko MPP original i MPP aligned; domyślna jest oglądana wersja.
- Podgląd i miniatury pokazują braki jako biel, niezależnie od gamma.
- Zapis z GUI zawsze używa skończonego tła i dodatku V3. Wartość tła to
  maksimum skończonych próbek klatki (zero, jeśli ich nie ma). MPP zapisuje
  liczby, więc kolor w zewnętrznym programie zależy od palety i kontrastu;
  nie obiecujemy bieli przy każdej konfiguracji WSxM.
- Braki w pamięci nadal są NaN/Inf, a maska odtwarza się dokładnie z JSON.
  Rejestracja, interpolacja, wartości skończone, geometria i czasy bez zmian.
- Stare V1/V2 i V3 wypełnione minimum nadal się otwierają. API zachowuje
  dotychczasową możliwość zapisu NaN; nie jest ona osobnym wyborem w GUI.

Sprawdzenia na zatwierdzonych granicach: publiczny zapis/odczyt pary i
publiczne kontrolki/piksele GUI, także zapis już otwartego starego aligned.
Ręczna próba obejmie podgląd, dwa wybory zapisu, ponowne otwarcie i WSxM.


## Wynik

Implementacja: **`2175cfe`**. [Próba ręczna](../../wsxm-export-manual.md).
[Przegląd Standards/Spec](../review-13-white-background.md): 0 uwag w obu osiach.

- TDD red → green: maksimum w publicznym eksporcie, białe widoczne piksele
  i miniatury niezależnie od gamma, następnie tylko dwa wybory zapisu.
- Zestaw dotyczący zmiany: **32 passed**, 3.49 s. Rzeczywiste Qt xcb:
  **13 passed**, 1.22 s. Mypy strict: **26 plików**, bez błędów.
- Pełne repo: **2038 passed, 14 failed, 16 skipped**, 239.13 s.
  Dokładnie te same 14 niepowodzeń innych aplikacji co przed zmianą.
- Nowy `data/MOVIE_3-aligned-white.mpp` z JSON: wszystkie 17 klatek
  odtwarza dokładne wartości i historię; tylko braki w MPP otrzymały maksimum.
- Rzeczywisty WSxM pod Wine pokazuje jasny dodatkowy obszar i szczegóły;
  wycinek pomiaru ma 167 kolorów spełniających próg diagnostyczny.
- Największy zmieniony plik kodu: 765 linii. Oryginalny pomiar bez zmian.

Odbiór ręczny użytkownika i Windows pozostają do wykonania. Nie zmieniano
rejestracji ani wspólnych czytników. MPP z JSON przenosić razem do analizy.
