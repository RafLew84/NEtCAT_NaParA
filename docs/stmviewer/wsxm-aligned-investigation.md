# WSxM: czarny film aligned z NaN — 2026-10-26

## Wynik

`data/MOVIE_3-aligned.mpp` jest poprawnym zapisem wyniku Optical Flow.
Całkowicie czarny obraz odtworzono w WSxM 5.0 Develop 12.0 pod Wine na
Ubuntu. Przyczyną objawu jest obsługa NaN w tej konfiguracji WSxM:
**identyczny nagłówek i te same skończone próbki dają widoczny obraz po
zastąpieniu wyłącznie NaN skończonym tłem**. Wyłączenie Plane ani wybór
zakresu palety całego filmu zamiast pojedynczej klatki nie usuwają objawu.

To odrębne ograniczenie od [wcześniejszego błędu nagłówka i kontrastu](wsxm-investigation.md).
Nie zmieniono eksportera: zachowanie NaN jest uzgodnionym wymaganiem
[ticketu 13](implementation/issues/13-aligned-mpp.md). Nie ustalono,
która wewnętrzna operacja WSxM błędnie obsługuje NaN; nie mamy jego kodu.
Nie wykonano tej próby na Windows ani w innych wersjach WSxM.

## Kontrola danych

- 17 klatek, szerokość 274 × wysokość 281; źródła 256 × 256.
- Nagłówek: 912 B, natywny układ CRLF; deklarowany i rzeczywisty początek
  próbek są zgodne. Rozmiar: 10 472 096 B = 912 + 17 × 274 × 281 × 8.
- Zakres skończonego sygnału: −8.99993833242739…0.9753411600709058 nA.
- 1 105 936 skończonych próbek, 202 962 NaN, brak nieskończoności.
  NaN obejmują dodany obszar i brak wsparcia interpolacji przy krawędziach.
- Dodatek V2 przechodzi walidację i opisuje Optical Flow. Ponowne obliczenie
  ze źródła potwierdza dokładną zgodność wszystkich 17 klatek: wartości,
  NaN, geometrii, odniesienia i metadanych.

Z katalogu repo, Python w środowisku `netcat`:

```bash
PYTHONPATH=. python tests/stmviewer/check_aligned_mpp.py --source data/MOVIE_3.MPP --saved data/MOVIE_3-aligned.mpp --method optical_flow_median
```

Oryginał nie był nadpisywany. SHA-256:
`f8166f2dfa398ec58ef45dfcef83ada4425f2249aeabe611d8bad120b1415c18`.

## Odtworzenie w rzeczywistym WSxM

Użyto oddzielnej kopii prefiksu Wine i wirtualnego ekranu. Nie zmieniano
ustawień ani otwartych okien instalacji użytkownika. Skrypt ocenia wycinek
wewnątrz obrazu; ponad 16 kolorów obecnych w co najmniej 20 pikselach jest
warunkiem diagnostycznym tego konkretnego pomiaru, nie ogólnym testem STM.
Zrzuty oceniono także wizualnie.

| Próba | Wynik |
| --- | --- |
| Oryginalny film z NaN | Całkowicie czarny wycinek, 1 kolor |
| Minimalny przykład: jedna klatka z NaN | Tak samo czarny |
| Wyłączony Plane, dane nadal z NaN | Nadal czarny |
| Wyłączony Plane i zakres palety całego filmu, dane z NaN | Nadal czarny |
| Ta sama pojedyncza klatka i identyczny nagłówek; tylko NaN zastąpione minimum | 128 kolorów spełniających próg, widoczne szczegóły |
| Pełna kopia 17 klatek z takim wypełnieniem | Trzy zrzuty różnych pozycji filmu: 167/210/123 kolorów, widoczne szczegóły |

Automatyzacja nawigacji nie ustaliła żądanych indeksów 0/8/16: pasek WSxM
na zrzutach pokazuje inne pozycje. Nazwy tych trzech zrzutów są etykietami
prób, nie dowodem sprawdzenia konkretnych indeksów. Wniosek dotyczy
widoczności filmu; numeryczna kontrola wszystkich 17 klatek jest osobna.

W minimalnej parze A/B nagłówek ma 543 B i jest bajtowo identyczny;
zastąpiono tylko 11 458 NaN pierwszej klatki. Ten eksperyment rozdziela
obsługę braków od interpretacji metadanych. Oryginał z NaN nadal odtwarza
błąd WSxM. Nie dodano pozornego testu eksportera, który udawałby test
zamkniętego programu; istniejący publiczny weryfikator potwierdza dane.

## Kopia do podglądu

Przygotowano lokalny `data/MOVIE_3-aligned-wsxm-preview.mpp` i sąsiadujący
`MOVIE_3-aligned-wsxm-preview.README.txt`. W każdej klatce NaN zastąpiono
jej minimalną skończoną wartością. Wszystkie skończone próbki i 912 bajtów
nagłówka są identyczne z oryginałem. Nie przycięto ani nie przeskalowano
obrazu. SHA-256 kopii:
`dfc7013b984eb05a101070f13a930893e451320bbb6f4b5dc624746e253d6fc4`.

To kopia prezentacyjna: tło jest sztuczne. **Do analizy służy oryginalny
MPP wraz z jego JSON**. Nie przeniesiono dodatku V2 na kopię podglądową:
zmienił się SHA-256, a reguła ważności `isfinite(samples)` oznaczyłaby
wypełnione tło jako pomiar. Nie dodano nowego trybu eksportu do aplikacji
ani nie zmieniono uzgodnionego zachowania NaN.

Artefakty pozostają lokalne w `/tmp/wsxm-aligned-investigation/`:
`run_case.py`, `value-check.log`, `preview-manifest.json`,
`full-preview-result.log` oraz zrzuty PNG. To narzędzia tej diagnozy,
zależne od lokalnego WSxM/Wine i geometrii okien, nie przenośne testy CI.
Próby GUI sterowane skryptem nie zastępują ręcznego odbioru ticketu 13.
Zmiany repo obejmują tylko dokumentację; nie ponawiano pełnych testów kodu.
