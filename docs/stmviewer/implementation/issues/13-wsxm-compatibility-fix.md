# Poprawka 13: eksport MPP czytelny w WSxM z odtwarzaniem braków

Status: in-progress. Baza przeglądu: `01259e1`.
Zlecenie użytkownika 2026-10-26: poprawić program po potwierdzeniu czarnego
obrazu `MOVIE_3-aligned.mpp` w WSxM. [Diagnoza](../../wsxm-aligned-investigation.md).

- Okno zapisu oferuje original/aligned w wariancie WSxM (domyślnym)
  oraz dotychczasowym wariancie zachowującym NaN bezpośrednio w MPP.
- Wariant WSxM zastępuje tylko nieskończone/brakujące próbki minimum
  skończonych wartości każdej klatki, a dla pustej klatki zerem.
  Wszystkie skończone próbki, wymiary, kolejność i geometria pozostają.
- Dodatek V3 przechowuje dokładne pozycje i bity zastąpionych próbek.
  Ponowne otwarcie pary przywraca NaN/Inf, maskę, metadane i historię.
  Resave original działa także po otwarciu starego aligned z NaN.
- Dotychczasowe V1/V2 i eksport bez zgodności WSxM zachowują kontrakt.
  Czytniki bez obsługi V3 widzą sztuczne tło; do analizy potrzebna jest para.
- Błędny dodatek jest odrzucany w całości, bez częściowej zmiany pikseli.
  Zapis zachowuje anulowanie, postęp i rollback obu plików.

Testy na wcześniej zatwierdzonych granicach: publiczny zapis/odczyt pary
(w tym niezależny czytnik MPP) i publiczne kontrolki GUI. Osobno rzeczywisty
WSxM pod Wine na zgłoszonym pomiarze; nie zastępuje próby Windows.
Przegląd Standards/Spec oraz pełne testy repo na końcu zgodnie z implement.
