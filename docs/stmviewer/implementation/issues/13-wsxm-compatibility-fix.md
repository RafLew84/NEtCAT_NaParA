# Poprawka 13: eksport MPP czytelny w WSxM z odtwarzaniem braków

Późniejsze uproszczenie użytkownika: [tylko original/aligned i białe tło](13-white-background.md).
Poniżej zakres oraz wyniki wcześniejszego etapu z czterema opcjami zapisu.

Status: done. Baza przeglądu: `01259e1`.
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


## Wynik

Implementacja `2343bd6`, poprawka przeglądu `e013d73`.
[Instrukcja ręczna](../../wsxm-export-manual.md),
[przegląd Standards/Spec](../review-13-wsxm-compatibility.md).

- Dwa pionowe przebiegi TDD red → green: publiczny zapis/odczyt oraz
  domyślny wariant w publicznym oknie zapisu i odtworzenie szachownicy.
- Viewer: **252 passed, 2 skipped**, 26.74 s; mypy strict **26 plików**, bez błędów.
- Pełne repo: **2038 passed, 14 failed, 16 skipped**, 235.44 s.
  Zestaw 14 niepowodzeń MolTrack/NanoTrack identyczny z poprzednim raportem;
  brak nowych identyfikatorów błędów. Nie jest to zielony odbiór całego repo.
- Dodatkowe rzeczywiste Qt xcb: **4 passed**, 0.96 s.
- Nowy MPP otwarto w rzeczywistym WSxM pod Wine: szczegóły widoczne,
  207 kolorów spełniających próg diagnostyczny zamiast jednolitej czerni.
- Wszystkie 17 klatek MOVIE_3 odzyskuje dokładne bajty, NaN, geometrię i
  metadane z V3. MPP jest bajtowo identyczny z poprzednią działającą kopią
  podglądową. Próbę wykonano zarówno dla nowej rejestracji, jak i resave original.
- Największy zmieniony plik kodu: 766 linii. Przegląd: 0 otwartych uwag.

Ręczny odbiór końcowego rozwiązania potwierdzono 2026-10-26. Osobny odbiór
Windows pozostaje do wykonania; automatyczne Qt/Wine go nie zastępują. Kod starszych czytników repo nie zmieniony: dla zachowania
braków bez V3 należy wybrać wariant NaN. Do analizy w nowym Viewerze
przenosić MPP i JSON razem. Szczegółowe logi: [handoff](../../handoff.md).


## Potwierdzenie odbioru — 2026-10-26

Użytkownik potwierdził: „teraz jest ok. testy manualne ok”.
Odbiór obejmuje końcowy stan ticketu 13: zapis aligned, zgodność MPP
oraz uproszczony zapis original/aligned i białe tło. Status: **done**.
Systemu nie wskazano; końcowe odbiory Ubuntu i Windows pozostają osobnymi
zadaniami 20 i 21. Nie ponawiano testów kodu przy aktualizacji dokumentacji.
