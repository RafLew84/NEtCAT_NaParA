# REG-02a — wykonanie, sprawdzenia i przegląd

Data: 2026-10-31. Gałąź `viewer/registration-difficult-movies`.
Baza: `c2c8f1f`; implementacja `976386c`; poprawka po przeglądzie `f94b0a8`.
Status: `ready-for-review`, ręczny odbiór użytkownika niewykonany.
[Ticket](../issues/02a-manual-movie-corrections.md),
[instrukcja GUI](../manual-movie-corrections-manual.md).

## Wynik

Okno pary pobiera aktualne względne XY z pełnego filmu. Zakończenie próby
pozostaje diagnostyczne, **Zastosuj do filmu** jawnie podmienia aligned po
przeliczeniu z original. Różnica przesunięcia pary wpływa na jej drugą klatkę
oraz dalsze; korekty różnych par współistnieją, cofnięcie dotyczy jednej pary.

Nowy wynik powstaje w tle i trafia do programu dopiero po sukcesie. Błąd lub
anulowanie zachowują wcześniejszy film i korekty. Postęp oraz anulowanie są
w głównym oknie i oknie pary. Próba jest związana z wersją wyniku; po ponownej
rejestracji starej próby nie można zastosować. Usunięcie klatki zachowuje gotowe
obrazy i eksport, lecz dalsze korekty wymagają nowej pełnej rejestracji.

MPP/AVI korzystają z aktywnego poprawionego filmu. V4 dodatku MPP przechowuje
wspólną lekką historię bazy i ręcznych nadpisań; źródła usuniętych klatek
pozostają w historii, bez zachowywania ich obrazów. Starsze V1–V3 są czytane.
Czytnik starszy od tej implementacji odrzuci dodatek V4: otworzy sam MPP, ale
nie odzyska metadanych/braków z JSON. Szczegóły:
[format metadanych](../../mpp-metadata-format.md).

## Automatyczne sprawdzenia

Granice TDD pochodzą z zatwierdzonego ticketu. RED poprzedziło odpowiednie
wdrożenia: brak API, cofnięcia pary, ręcznego pochodzenia, nowych kontrolek,
historii GUI i anulowania w oknie pary; później niepełna walidacja V4.
Testy obserwują publiczny wynik, kontrolki GUI i odczyt zapisanych filmów.

- Rdzeń: 6 nowych przypadków i 9 dotychczasowej rejestracji — **15 PASS**.
  Liczby z ticketu, zastępowanie/nadpisania/cofnięcie, ułamkowe próbki (wzorzec
  z wartością 6,25), maski, geometria/skala, brak ponownej interpolacji aligned,
  anulowanie, błąd oraz nieaktualne lub usunięte źródła.
- Eksport: 13 przypadków nowego pliku i 32 dotychczasowych — **45 PASS**.
  MPP dokładny roundtrip NaN i białego wypełnienia, historia po usunięciu klatek,
  ponowny zapis original, FFV1/FPS, odrzucenie całego uszkodzonego dodatku V4.
- GUI: 5 nowych testów; końcowy zestaw powiązanych testów po refaktorze —
  **36 PASS**. Dwie korekty/cofnięcia, zapis i widoczna historia, prawdziwe
  anulowanie zadania, błąd/ponowienie, nieaktualny szkic, import i usuwanie.
- **mypy strict: 43 pliki PASS**, Ruff bez uwag, diff bez błędów whitespace.
  Największy zmieniony plik kodu: 893 linie (`main_window.py`), następny 532.
- Pełne repozytorium: **2220 passed, 14 failed, 16 skipped**, 271,36 s.
  Wszystkie 14 identyfikatorów błędów są identyczne z poprzednim REG-02:
  11 w MolTrack (SAM2) i 3 w NanoTrack. Brak nowych błędów Viewera.
  Pierwsza próba została przerwana sygnałem SIGTERM przed podsumowaniem;
  brak podsumowania nie jest wynikiem PASS. Przebieg ponowiono z trwałym logiem.

Komenda pełnego zestawu (środowisko `netcat`):

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=.:tests/moltrack:tests/stmviewer \
python -m pytest --import-mode=importlib -q -p no:cacheprovider
```

## Rzeczywiste pomiary — automatyczna próba funkcji

MOVIE_4 otwarto jako źródłowe 3–364, razem 362 klatki 256×256. Deep Matcher
z lokalnym `loftr_outdoor.ckpt` i CUDA na RTX 5090 ukończył serię w 6,13 s;
nie użyto zastępstwa innej metody ani pobierania modelu.

Dla bieżącej pary 29→30 (źródłowe 31→32) bazowe XY wyniosło
`(0,6786041259765625; 7,234718322753906)`. Celowe +1 px X służyło sprawdzeniu
propagacji — **nie jest oceną poprawy dopasowania struktur**. Przeliczenie
zajęło 0,60 s; obszar wzrósł z 400×346 do 401×346 px. XY wcześniejszych
29 klatek zostały, dalsze otrzymały +1 X i jawną niezweryfikowaną pewność.

Anulowanie po 10 z 362 wyrenderowanych klatek zachowało wcześniejszy wynik.
Usunięcie korekty przywróciło dokładne próbki, maski i pewność (0,74 s).
Pełny MPP+V4 zapisano i odczytano z dokładną zgodnością wszystkich klatek.
Końcowy walidator V4 również przyjął ten zapis. AVI FFV1 bieżących klatek
27–33: 7 klatek, 7 FPS, zgodne piksele po dekodowaniu. Nie sprawdzano go
ręcznie w VLC. SHA-256 pliku źródłowego pozostał bez zmian:
`9d066676a3f947ed53610438051537eb3b30288aadc11d774ec52e509f31f961`.

Reproduktor: `tests/stmviewer/diagnostics/manual_movie_trial.py`.
Duże wyniki i komendy pozostają lokalnie w `data/registration-reg02a-review/`.
Czasy opisują to stanowisko i ten przebieg, nie gwarancję wydajności.

## Rzeczywiste Qt i oględziny zrzutów

Wykonano sterowane skryptem GUI Qt/xcb na `DISPLAY=:1`:

- CPU: zastosowanie dwóch korekt, usunięcie jednej, zamknięcie okna,
  eksport MPP z GUI i odczyt historii.
- MOVIE_4: usunięcie pierwszych dwóch klatek w GUI, pełny Deep Matcher,
  zastosowanie +1 X i anulowanie kolejnej korekty przyciskiem po 30 ms.
  Blokady operacji i zachowanie poprzedniego filmu poprawne.
- Końcowy komunikat „Ta korekta została zastosowana do filmu” sprawdzony
  po zmianie nazewnictwa statusu; podglądy 1180×820 i 1080×760 obejrzane,
  bez poziomego przewijania i uciętych nowych przycisków.
- Diagnostyczny `manual_movie_gui_fault.py --delay 0.3 --fail-at 2`:
  sprawdzono dokładny mechanizm w widocznym GUI, zastępując tylko uruchomienie
  głównej pętli skryptem sterującym. Błąd alokacji drugiej klatki zachował film,
  ponowienie zadziałało; kolejne anulowanie po 50 ms także zachowało wynik.

Są to automatyczne próby rzeczywistego GUI i oględziny zrzutów, odrębne od
ręcznego odbioru użytkownika oraz jakości wizualnej filmu. Nie wykonano odbioru
Windows, VLC ani nowych testów całego MOVIE_8 w tym tickecie.

## Standards

Końcowy zakres `c2c8f1f…f94b0a8`: **0 otwartych uwag**.

Pierwotna uwaga heurystyczna P3 dotyczyła powtórzenia uruchamiania zadania
w głównym oknie. Naprawiono ją w `f94b0a8`: `_start_registration_job()` wspólnie
obsługuje zatrzymanie odtwarzania, postęp, blokowanie kontrolek i sygnały.
Różnice ręcznej korekty pozostają jawne. Osobny `ManualMovieJob` jest uzasadnioną
granicą wątku Qt. Brak naruszeń udokumentowanych zasad i nowych uwag po poprawce.

## Spec

Końcowy zakres `c2c8f1f…f94b0a8`: **0 uwag**.

Przegląd potwierdza względne XY pary, jawne zastosowanie do filmu, przeliczenie
z oryginałów, cofnięcie jednej korekty, ochronę przy błędzie/anulowaniu,
aktualność próby, blokadę po usunięciu klatki i eksport V4 z walidacją.
Refaktor uruchamiania zadania zachował kontrakt. Nie znaleziono nieuzgodnionego
rozszerzenia zakresu. Przegląd nie zastępuje oceny jakości przez użytkownika.

Standards: 1 uwaga naprawiona, 0 otwartych. Spec: 0 uwag. REG-03 pozostaje
zablokowany do ręcznego odbioru REG-02a.
