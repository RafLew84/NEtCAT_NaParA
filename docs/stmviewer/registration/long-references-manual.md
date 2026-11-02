# REG-08d — dalsze klatki odniesienia

Status: **done** — użytkownik potwierdził „testy manualne ok” 2026-11-02.
Poniższy scenariusz pozostaje instrukcją dalszych prób. Potwierdzenie nie określa
systemu, sprzętu ani szczegółowej porównawczej jakości filmów.
[Ticket](issues/08d-long-range-references.md), [wyniki](long-references-results.md).

Z katalogu `/home/rlew/projekty/NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Po zapisaniu własnej sesji uruchom ponownie aplikację, aby wczytać nowy kod.

## Własny film

1. Otwórz sesję zawierającą kompletny wynik okna 3/5 albo oblicz go przez
   **Dopasowanie wieloklatkowe…**. Dalsze odniesienia wymagają zachowanych
   oryginałów i grafu; sam aligned MPP nie odtwarza tych pomiarów.
2. Wejdź w zakładkę **Dalsze odniesienia**. Wybierz bazę **Samo okno — LS**
   albo kompletny wynik Hubera. Wpisz numery klatek odniesienia rozdzielone
   przecinkami i zakres **od–do**. To numery bieżącej serii; tabela pokazuje
   także nazwy źródeł i pierwotne numery MPP.
3. Sprawdź listę i liczbę nowych par. Powtórzenia, pary samej klatki ze sobą
   i wszystkie relacje istniejącego okna są pomijane, również wcześniejsze
   odmowy. Wybranie wszystkich klatek i całego zakresu jest odrzucane;
   limit wynosi 10 000 nowych par.
4. W lewym panelu wskaż lokalne wagi i urządzenie zgodne z bazowym pomiarem.
   Nazwa pliku może być inna, lecz SHA wag, kod estymatora, biblioteki,
   rzeczywiste urządzenie i ustawienia muszą odpowiadać bazie. Nic nie jest
   pobierane. Zmiana pola okna po lewej nie zmienia zachowanej bazy rozszerzenia.
5. Kliknij **Oblicz okno + dalsze odniesienia**. Model zmierzy tylko nowe pary.
   Bazowe pomiary zostaną zachowane. Przy Huberze również próg, limit iteracji
   i pozostałe ustawienia pozostają takie same. Anulowanie/błąd pozostawia
   poprzedniego kandydata i aktywny film.
6. W zakładce **Film** przełączaj **Samo okno** i rozszerzony wynik z tym
   samym solverem. Kadr, gamma i zoom są wspólne. Odczytaj zmianę X/Y,
   obejrzyj cały wskazany odcinek oraz struktury, które nie pasują. W relacjach
   zobaczysz pochodzenie „okno” lub „dalsze odniesienie”, XY, brak i przyczynę.
7. Gdy chcesz użyć wyniku, jawnie wybierz kompletny rozszerzony LS/Huber
   i **Zastosuj wynik do filmu**. Sam podgląd bazy ani zakończenie obliczeń
   nie zastępuje aktywnego aligned. Niekompletny Huber pozostaje niedostępny;
   dialog po jego obliczeniu podaje powód. LS można wybrać samodzielnie.
8. Zamknij okno dopasowań i zapisz sesję. Otwórz ją ponownie: baza, dodatkowe
   relacje, aktywny film i kandydat mają pozostać odrębne. Sprawdź ręczną
   korektę, **Przywróć zachowany wynik** oraz mały eksport aligned MPP/AVI.

Kolejne rozszerzenie znów wychodzi od zachowanej bazy samego okna.
Nie kumuluje rekurencyjnie poprzednich rozszerzeń. Inny próg Hubera można
później sprawdzić istniejącymi kontrolkami, ale nie jest to już porównanie
wpływu samych dalszych relacji przy identycznym solverze.

## Gotowe lokalne materiały

Wyniki testowe są poza Git i nie zastępują własnych sesji.

| Plik sesji | Próba |
| --- | --- |
| `/tmp/reg08d-known-v2/correct-long-links-extended.stmsession` | Znany ruch; aktywna baza okna i kandydat z 12 poprawnymi dalekimi relacjami. |
| `/tmp/reg08d-known-v2/periodic-alias-extended.stmsession` | Spójny, ale błędny skok o okres 24 px. Małe reszty nie oznaczają poprawnego ruchu. |
| `/tmp/reg08d-known-v2/missing-long-links-extended.stmsession` | Wszystkie 12 dodatkowych relacji odmówione; położenia bazy pozostają. |
| `/tmp/reg08d-movie4-v1/ls-candidate.stmsession` | MOVIE_4, okno 5, odniesienia 20 i 110, zakres 25–100. |
| `/tmp/reg08d-movie4-v1/huber-candidate.stmsession` | Te same pomiary, Huber 2 px/200 iteracji, kompletny. |
| `/tmp/reg08d-movie8-v1/ls-candidate.stmsession` | MOVIE_8, okno 3, odniesienia 1 i 50, zakres 17–40. |
| `/tmp/reg08d-movie8-v1/huber-candidate.stmsession` | Ten sam plan, Huber 2 px/200 iteracji bez zbieżności; odmowa zastosowania. |

MOVIE_4 ma już usunięte pierwsze dwie błędnie przypisane klatki.
Numery bieżące 20/110 odpowiadają źródłowym 22/112; zakres 25–100 to
źródłowe 27–102. Nie usuwaj ich ponownie. Obejrzyj szczególnie 29→30,
35→36, 44–46, 61→62 i 94–97 oraz cały odcinek między nimi.
Wybrane odniesienia są jawną próbą, nie automatyczną rekomendacją jakości.

W katalogach MOVIE są również filmy `ls-window.avi`, `ls-extended.avi`
i analogiczne filmy Hubera, jeśli uzyskał kompletny wynik. Mają identyczny
zakres, 5 kl./s, gamma 1, proporcje pikselowe i białe tło. Sesje
`*-applied-corrected.stmsession` zawierają demonstracyjne +1 px w Y,
które sprawdza obsługę korekt — nie jest proponowaną poprawką fizyczną.

Generator wzorców oraz odtwarzalny pomiar realny:

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/long_reference_fixtures.py /tmp/reg08d-known-new
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/long_reference_trial.py /tmp/reg08b-movie4-window5-long/comparison.stmsession /tmp/reg08d-movie4-new --references 20,110 --start 25 --end 100
```

Wzorce mają podane relacje i nie uruchamiają modelu. Do ponownego pomiaru
realnego potrzebne są zgodne biblioteki, CUDA i lokalne wagi z bazowej sesji.
Oglądanie, zastosowanie i odczyt zapisanych wyników nie wymagają modelu.

Zapisz ocenę **lepiej / podobnie / gorzej / niejednoznacznie** dla struktur
w całym odcinku; tearing oceń osobno. Mniejszy ruch filmu, mniejsze reszty
lub zbieżność solvera same nie rozstrzygają jakości.
