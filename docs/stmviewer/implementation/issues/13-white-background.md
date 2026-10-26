# Poprawka 13: jeden zapis MPP i białe tło brakujących pikseli

Status: in-progress. Baza przeglądu: `7123d1b`.
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
