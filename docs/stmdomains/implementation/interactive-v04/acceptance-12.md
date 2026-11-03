# SD-V4-12 — automatyczny wybór liczby klas

Data **2026-11-03**, gałąź `domains/interactive-v04-ui`, worktree
`/home/rlew/projekty/NEtCAT-domains`. Baza `3297b98`, implementacja `274f348`, poprawka `88006c1`.
[Ticket 12](12-automatic-class-count.md), [reguła Auto v1](auto-class-count-rule.md).
**Odbiór ręczny użytkownika potwierdzony 2026-11-03 dla wersji `7edd8de`**
słowami „testy manualne ok”. Ticket 12 jest wykonany i odebrany.
Poniżej wcześniejsze sprawdzenia agenta oraz instrukcja do ponownego testu.
Zapis potwierdzenia zmienia tylko dokumentację; nie ponawiano testów aplikacji ani GUI.

## Obsługa

W **netcat**, w tym worktree:

```bash
python -m stmdomains.main
```

**Analiza → Analiza… → Klasy → Dopasuj nowe klasy → Auto — wybierz z danych**.
Pole **Maksimum dla Auto** ogranicza poszukiwanie do K1–8 (domyślnie 8).
Zakres domen wybiera zakładka **Zakres**, a dane do wyboru klas — osobne pole
w **Klasy**. Przycisk **Analizuj** stosuje także progi akceptacji, porządku
oraz tworzenia domen. Auto nie wczytuje modelu ani wyników v0.4.

Auto może zwrócić **K1**, **kilka klas** lub **nierozstrzygnięcie**. Wybrana
liczba klas nie jest liczbą domen. Opis katalogu wskazuje np. **Auto: K2**.
Podsumowanie pod przyciskiem wskazuje decyzję, a **Ranking Auto…** pokazuje
wyniki dla K, liczności, zwartość i rozdzielenie oraz przyczyny odmów.
Pełne uzasadnienie jest także w podpowiedzi; długi tekst w małym oknie
ma wielokropek zamiast zmieniać wysokość układu.

Tabela dotyczy ostatniego przebiegu. Przy oglądaniu poprzedniego wyniku Auto
opis i ranking jawnie dotyczą **wyświetlanego wyniku**. Samo porównanie nie
zmienia szkicu kolejnej analizy. **Z wyświetlanego wyniku** wybiera jego
istniejący katalog i kopiuje progi; ponowne zastosowanie katalogu nie
wybiera K ani nie dopasowuje PCA/KMeans ponownie.

Nierozstrzygnięcie nie przełącza programu na K5. W analizie lokalnej zapisuje
stan „brak dopasowania”, bez katalogu i bez wybranego K. Wspólne dopasowanie
kończy przebieg przed segmentacją; klatki mają stan **Niewykonana**, bez
liczników udających zerową detekcję. Wcześniejszy kompletny wynik pozostaje
na obrazie, opisany jako wynik spoza tego przebiegu. Jego K5 nie oznacza,
że Auto wybrało K5.

## Kontrole do testu ręcznego

Gotowy zapis: `.scratch/stmdomains-ui-12/demo/auto-controls.moltrack.json`
razem z `auto-controls.mpp`. Odtworzenie:

```bash
python -m stmdomains.tools.auto_classes_demo
```

To wygenerowane obrazy i centra, bez zapisanych klas i domen. Klatka 2
różni orientacje sieci; nie jest kontrolą dwóch chemicznych typów molekuł.

1. Otwórz zapis kontrolny. Wybierz **Bieżąca klatka**, nowe klasy **Auto**,
   maksimum **8**, odkrywanie **Ten sam zakres co analiza**, bazowe progi.
2. Kolejno przelicz pięć klatek. Sprawdź ranking i oznaczenia:

| Klatka | Wejście | Wybór Auto | Użyteczne/aktywne | Przypisane do domen | Domeny |
| --- | --- | --- | ---: | ---: | ---: |
| 1 | sieć 11×11, 45° | K1 | 117/121 | 117 | 1 |
| 2 | dwie oddzielne sieci, 45° i 0° | K2 | 234/242 | 234 | 12 |
| 3 | losowe centra | nierozstrzygnięte | 10/98 | — | — |
| 4 | cztery centra | nierozstrzygnięte | 0/4 | — | — |
| 5 | brak zapisanych oznaczeń | nierozstrzygnięte | 0/0 | — | — |

K2 i 12 domen na klatce 2 to rozdzielone etapy klasyfikacji i geometrii
przy bazowych progach, a nie obietnica dwóch końcowych domen. Kontrola
sprawdza wybór klas; nie potwierdza jakości granic domen.

3. Na klatce 2 ogranicz maksimum do **1** i przelicz: odmowa, stary K2
   pozostaje na obrazie. Następnie przełącz na **Ręczna liczba klas, K5**
   i przelicz. **Poprzedni wynik** wraca do Auto K2 z jego rankingiem,
   zachowując ręczne K5 w szkicu.
4. Wróć do Auto, maksimum 8. Ustaw margines **0,060**, promień **0,80**,
   kwantyl porządku **0,925**, minimum domeny **6**. Analizuj zakres **1–2**
   i odkrywaj z tego samego zakresu. Oczekiwany wspólny **K2**, obie klatki
   mają wyniki i identyczny katalog. Użyteczne **351/363**.
5. Wybierz **Użyj istniejących klas** i powtórz: katalog pozostaje ten sam.
   Następnie **Dopasuj nowe**, **Cała seria**, odkrywanie **Ten sam zakres**:
   oczekiwana odmowa, ponieważ do dopasowania dochodzi szum. To działanie
   zapisanej reguły, nie błąd ścieżki całej serii.
6. Pozostaw całą serię jako cel, ale odkrywaj z **Inny wybrany zakres 1–2**.
   Oczekiwane **K2**, pięć obsłużonych klatek; słabe/puste wejścia nie
   udają nowych dopasowań. Sprawdź nawigację, małe okno, ranking i anulowanie
   kolejnego przebiegu. Po anulowaniu wcześniej ukończone wyniki pozostają.

## Próba TTMAPP i oczekiwane wyniki

Otwórz `data/TTMAPP/detection_full.moltrack.json`, źródło
`data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP`. Nowa seria resetuje szkic.
Regułę zapisano **przed pierwszym uruchomieniem Auto na TTMAPP**.
Nie zmieniano progów po tej próbie.

1. Klatka **259**, Auto maksimum 8, odkrywanie z bieżącej klatki,
   wszystkie progi bazowe: **nierozstrzygnięte**, **159/312** użytecznych.
   K1 ma promień 95% **0,394** (próg 0,15); najlepsze silhouette dla K≥2
   wynosi **0,368** przy K4 (próg 0,50). Również promienie grup przekraczają
   próg 0,20. Nie ma uzasadnionego wyboru K według tej reguły.
2. Zachowaj cel 259, odkrywanie **259–268**: **nierozstrzygnięte**,
   **1715/3054** użytecznych. Ranking korzysta z **1200** próbek, dopasowanie
   ma dostępne 1715. Najlepsze silhouette **0,335** dla K2; promień K1
   **0,423**. Wybór K1–8 nie spełnia warunków.
3. Analizuj cały zakres **259–268**, zachowując ten zakres odkrywania:
   ta sama decyzja i ranking; wszystkie klatki **Niewykonana**. Ranking
   nie zależy od wyboru klatki wyświetlanej w przeglądarce.
4. Dla bieżącej 259 przełącz na ręczne **K5**, odkrywanie **259–268**,
   progi bazowe: **105/312**, **5 domen**, katalog `9d3b7286`.
   Powrót do Auto daje odmowę i zachowuje ten ręczny wynik z jawną informacją,
   że pochodzi spoza bieżącego przebiegu.

Te obserwacje sprawdzają zachowanie funkcji. Nie są pomiarem wykrywalności
ani wnioskiem o braku domen w TTMAPP. Auto v1 jest konserwatywną regułą dla
obecnych opisów otoczeń; rzeczywiste dane nie tworzą według jej progów
wystarczająco zwartych i rozdzielonych klas. Ręczny wybór nadal pozwala
prowadzić eksplorację. Auto nie gwarantuje liczby faz, nie jest testem
istotności i może pomijać małe populacje; otoczenia/klatki nie są
niezależnymi pomiarami.

## Sprawdzenia wykonane przez agenta

- TDD: brak modułu Auto → testy wyboru; brak parametrów API → integracja;
  brak kontrolek → działające wspólne okno. **20 nowych testów** pokrywa
  kontrole, powtarzalność, ograniczenie rankingu, odmowę po końcowej
  walidacji, anulowanie, lokalne/wspólne dopasowanie i osobny zakres celu,
  parametry wszystkich zakładek, porównanie oraz zachowanie wcześniejszych wyników.
- Testy celowane istniejącej ścieżki ręcznej i wspólnego okna: PASS.
- Mypy: **70 plików źródłowych PASS**.
- Dokumentacja: **409 lokalnych linków/kotwic w 8 dokumentach PASS**, 26 ticketów,
  zgodność tabeli zależności i brak cykli. `git diff --check` PASS.
- Pełny zestaw `tests/stmdomains`: **476 PASS w 173,61 s**. Pierwszy proces
  przerwano sygnałem SIGTERM (kod 143), bez raportu błędu asercji; przyczyny
  zewnętrznego przerwania nie ustalono. Powtórne pełne uruchomienie z nazwami
  testów zakończyło się poprawnie. Log: `pytest-full-retry.txt` w katalogu dowodów.
  Polecenie: `QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -v tests/stmdomains` (netcat).
- GUI **X11/xcb**, w `netcat`: wykonano powyższe scenariusze kontrolne
  i TTMAPP, ranking, ręczne K5 ↔ Auto, użycie katalogu bez PCA/KMeans,
  anulowanie, zamknięcie podczas pracy i małe okno. Interakcje wymuszał
  skrypt Qt; to odbiór agenta, nie potwierdzenie użytkownika.
- Natywne GUI ujawniło zmianę wysokości etykiety przez znak strzałki
  w opisie Auto. Zmieniono napis na `Auto: K…`; ponowny pomiar geometrii PASS.
  Długie uzasadnienie jest skracane w stałym wierszu, pełne w rankingu/podpowiedzi.
- Zmienione pliki kodu/testów mieszczą się w celu 1000 i limicie 1500 linii;
  17 plików, największy: `analysis_dialog.py`, **302 linie**.
- Przegląd `code-review`: **Spec 0**; **Standards 0 naruszeń** i jedna
  sugestia wydzielenia wspólnego przypisania centroidów — uwzględniona.
  Recheck: Standards 0 otwartych; Spec wskazał pominięcie 12 w jednej
  zbiorczej liście statusów dokumentacji — poprawiono na 06–12.
- Natywne czasy orientacyjne: lokalne Auto TTMAPP 259 **0,77 s**, wspólne
  259–268 **6,84 s**, ręczne K5 tego zakresu i domeny 259 **7,05 s**.
  Maksymalny odstęp sygnału GUI 20 ms: **0,232 s**, RSS procesu **681 MiB**;
  po zamknięciu wszystkie trzy pule miały **0 aktywnych pracowników**.
  Małe okno główne **900×650**, dialog **620×622**, pola przewijane.
- Audyt odczytów: **0 odczytów historycznych modeli/paczek**. Źródłowe MPP
  i JSON mają identyczne SHA-256 przed/po. Bez instalacji i zmian wspólnych.

Lokalne dowody: `.scratch/stmdomains-ui-12/gui_smoke.py`, `gui-smoke.json`,
`gui-log.txt`, zrzuty `control-*.png`, `small-tab-*.png`, `ttmapp-*.png`.
Nie są wersjonowane. Testy, generator kontroli i dokumentacja są w Git.

SHA-256 wejść:

- JSON: `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.
- MPP: `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`.

Nie wykonano nowej oceny skuteczności z ręczną referencją ani pełnej próby
Auto na wszystkich 268 klatkach TTMAPP. Całą serię sprawdzono na kontrolach,
TTMAPP na 259 i zakresie 259–268. Zapis projektu pozostaje zakresem 13;
wyniki i decyzje są obecnie w pamięci aplikacji.

## Standards

Przegląd `3297b98...274f348`: **0 naruszeń udokumentowanych zasad**.
Jedna niewiążąca uwaga „możliwe Duplicated Code”: projekcja i przypisanie
najbliższego centroidu powtarzały się w rankingu oraz walidacji końcowej.
W `88006c1` wydzielono `_partition`; reviewer potwierdził zamknięcie uwagi.
Granice aplikacji, testy na publicznych granicach obliczeń/UI i oddzielenie
kontroli technicznych od oceny naukowej zostały zachowane.

## Spec

Przegląd kodu `3297b98...274f348`: **0 uwag**, bez brakujących wymagań,
niezamówionych rozszerzeń lub wskazanych błędów realizacji reguły.
Recheck `88006c1` i raportu potwierdził zgodność zachowania i zapisanych dowodów.
Jedyna uwaga dokumentacyjna dotyczyła listy ukończonych etapów 06–11
w indeksie implementacji; poprawiono na 06–12.

**Otwarte uwagi: Standards 0, Spec 0; brak wskazanego problemu w obu osiach.**
