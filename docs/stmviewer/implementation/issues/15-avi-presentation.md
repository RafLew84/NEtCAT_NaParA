# 15: Kontrast, gamma i tła filmu AVI

**What to build:** Użytkownik wybiera własną prezentację AVI: wspólny lub osobny kontrast, gamma z podglądu lub neutralną oraz czarne, szare lub białe tło.

**Blocked by:** [14: Pierwszy film AVI: zakres, FPS i oba kodeki](14-original-avi-basic.md)

**Status:** done

**Wykonawca:** Codex
**Baza przeglądu:** `d6a08e1a1f2f61b13b83f1ce3deb19ebadb74026`

**Specyfikacja:** [Opcje filmu AVI](../../issues/05-avi-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [x] Domyślne ustawienia pozostają takie jak w pierwszym eksporcie; nowe opcje obejmują gamma z podglądu/1, kontrast osobny/wspólny i trzy uzgodnione tła.
- [x] Wspólny kontrast jest liczony tylko z ważnych próbek wybranego zakresu; tło, opisy, padding i klatki spoza zakresu nie wpływają na poziomy.
- [x] Gamma ma tę samą konwencję co podgląd i nie wpływa na tło. Stały zakres daje u=0,5 przed gamma; klatka bez ważnych próbek nadal trafia do filmu.
- [x] Wybrane opcje są stałe dla całej rozpoczętej operacji, niezależnie od późniejszych zmian podglądu.
- [x] Oba kodeki zachowują te same zasady renderowania, proporcji, paddingu i bezpieczeństwa zapisu.
- [x] Opcje działają dla original i każdego już dostępnego aligned; ostateczne połączenie wariantów jest sprawdzone podczas odbioru dużych eksportów.

## Testy automatyczne

- Publiczny renderer: kontrast tylko z wybranego zakresu, gamma, niezależne tła, przypadki stałe/brak próbek.
- Wybór opcji eksportu w GUI oraz odczyt wyników z niezmiennymi opcjami rozpoczętej operacji.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Klatka i opcje prezentacji → raster filmu** — Sprawdza gamma, kontrast, maskę, geometrię i opisy; nie sprawdza kodeka ani VLC.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Wyeksportuj wzorzec z różnymi jasnościami klatek w obu trybach kontrastu; porównaj obraz w VLC.
2. Ogranicz zakres filmu i sprawdź, że skrajne wartości wyłączonej klatki nie wpływają na wspólny kontrast.
3. Porównaj gamma z podglądu i 1 na trzech tłach; tło pozostaje wybranego koloru.
4. Sprawdź stałą klatkę i klatkę bez ważnych próbek oraz obie wersje kodeka.

## Współpraca z integracją

Renderer i opcje należą do Viewera. Wspólne zmiany prezentacji tylko po uzgodnieniu z integracją; nie zastępować wartości brakujących medianą przed obliczaniem kontrastu.

## Wynik implementacji — 2026-10-26

Commit `3e1fddf`; baza `d6a08e1`.
[Instrukcja manualna](../../avi-presentation-manual.md),
[przegląd Standards/Spec](../review-15-avi-presentation.md).
Implementacja i próby techniczne potwierdzają kryteria. Użytkownik potwierdził
2026-10-26: „testy manualne ok”; status **done**. Akceptacja obejmuje implementację
`3e1fddf` i przekazanie `e80a93d`. Osobne odbiory platform w ticketach 20 i 21
pozostają otwarte; potwierdzenie nie wskazuje systemu.

- 57 testów AVI: passed (12.83 s); 34 próby GUI Qt xcb: passed (9.69 s).
- Mypy strict: 31 plików bez błędów. Największy zmieniony plik kodu: 171 linii.
- Pełne repo: 2095 passed, 14 failed, 16 skipped, 259.60 s. Dokładnie te same
  14 niepowodzeń MolTrack/NanoTrack co przed zmianą; bez nowych identyfikatorów.
- VLC 3.0.20/Ubuntu/Xvfb: 10 filmów, oba kodeki, trzy tła, oba kontrasty,
  gamma 1/2 i różne zakresy; obraz i EOF, bez błędów. Obejrzano zrzuty filmu
  oraz rozszerzonego dialogu. Nie jest to ręczny odbiór użytkownika ani Windows.
- Obliczanie wspólnych poziomów działa w workerze, blokami, z postępem
  i anulowaniem. Zmiana gamma podglądu podczas zapisu nie zmienia filmu.
- Obecny eksporter wybiera original. Gotowy aligned wczytany z MPP korzysta
  z tego samego renderera; wybór bieżącego widoku aligned pozostaje w tickecie 16.
