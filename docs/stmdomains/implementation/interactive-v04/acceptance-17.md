# 17 — domeny geometryczne, Panel A

Implementacja 2026-11-04. Wybrany przez użytkownika wariant A: wspólne okno Analiza i przełącznik nad obrazem. Odbiór ręczny użytkownika oczekuje.

## Działanie

Analiza → Analiza… → Metoda domen → Geometria. Obliczana jest bieżąca klatka. Parametry mają jednostki i dotyczą całego regionu: kąt osiowy, względny rozstaw, minimalna koherencja obu osi i liczba punktów lokalnych. Dodatkowe ograniczenia to wielkość domeny, odległość krawędzi, promień maski i bariery w Zaawansowanych. Nie trzeba dopasowywać klas. Typ pozostaje nieznany.

Edycja jest szkicem. Analizuj zamyka okno i liczy w tle. Pasek Bazowa/Geometria przełącza zachowane wyniki tej klatki, zachowując zoom. Anulowanie, zmiana klatki/serii i zamknięcie programu nie publikują nieaktualnej pracy. Karta C pomiarów z 16 pozostaje dostępna.

Zapis projektu i eksport dotyczą **jednego wybranego wyniku**, jak w 13/14. Nie zapisują historii porównania obu metod. Wynik geometryczny zapisuje przypisania, maski, parametry i pomiary użyte do decyzji; typ/klasa jest pusta. Po otwarciu można przeliczyć bazową i ponownie porównywać. Samodzielne pomiary karty 16 nadal są sesyjne. Szkic geometrii jest zapisywany niezależnie od użytych wartości.

## Protokół i dane

[Zamrożony zestaw i definicje](experiment-17.md). Trzy zestawy ustawień, bez doboru pod TTMAPP. Bazowa metoda: lokalne K5 na każdej tej samej klatce, domyślne pozostałe parametry. To inne dopasowanie niż wcześniejsze wspólne K5 z 259–268 (105/312 na 259).

Wejście: `data/TTMAPP/detection_full.moltrack.json`, `MOVIE_23raw_TTMAPP_I_AU111.MPP`. Indeksy robocze 258–265, numery prezentowane 259–266. SHA256 źródeł i każdej klatki zapisane lokalnie w `gui-report.json` / `report.json`. Kod nie odczytuje modeli ani przypisań z historycznych ZIP. Kalibracja z nagłówka: 3,90625 nm/px w obu osiach; poprawność metrologiczna nagłówka nie została niezależnie potwierdzona.

## TTMAPP

Liczby mają postać **przypisane molekuły / liczba domen**. Bez referencji ręcznej błędne scalenia, podziały i położenie granic na TTMAPP pozostają nieocenione. Udział przypisań nie jest accuracy.

| Klatka | Aktywne | Bazowa K5 | Geometria bazowa | Ścisła | Łagodna |
|---|---:|---:|---:|---:|---:|
| 259 | 312 | 120 / 6 | 32 / 1 | 19 / 1 | 32 / 1 |
| 260 | 301 | 118 / 6 | 38 / 1 | 20 / 1 | 38 / 1 |
| 261 | 300 | 127 / 5 | 33 / 1 | 21 / 1 | 33 / 1 |
| 262 | 300 | 115 / 6 | 40 / 1 | 30 / 1 | 40 / 1 |
| 263 | 308 | 115 / 5 | 40 / 1 | 21 / 1 | 40 / 1 |
| 264 | 298 | 146 / 7 | 35 / 1 | 23 / 1 | 35 / 1 |
| 265 | 300 | 155 / 7 | 41 / 1 | 25 / 1 | 41 / 1 |
| 266 | 309 | 147 / 6 | 35 / 1 | 20 / 1 | 35 / 1 |

## Kontrole i porażki

Generator dostarcza obrazy, centra oraz jawne etykiety regionów w `reference.json`. Nazwy i kolejność poniżej odpowiadają klatkom gotowego pliku. Tabela pokazuje ustawienia geometryczne bazowe; pełne trzy zestawy i metodę bazową zawiera `report.json`.

| Klatka / kontrola | Przypisane / aktywne | Domeny | Błędne scalenia | Rozdrobnione regiony referencji | Pominięte regiony |
|---|---:|---:|---:|---:|---:|
| 1: sieć 17° | 63 / 99 | 7 | 0 | 1 | 0 |
| 2: dwie orientacje | 19 / 99 | 1 | 0 | 0 | 1 |
| 3: stopniowa deformacja | 0 / 99 | 0 | — | — | — |
| 4: skok fazy | 0 / 99 | 0 | 0 | 0 | 2 |
| 5: brakujące centra | 27 / 92 | 3 | 0 | 1 | 0 |
| 6: luka | 0 / 78 | 0 | 0 | 0 | 2 |
| 7: szum | 0 / 98 | 0 | 0 | 0 | 0 |
| 8: rzędy 1D | 0 / 228 | 0 | 0 | 0 | 0 |
| 9: trzy centra | 0 / 3 | 0 | — | — | — |

**Regularna sieć została nadmiernie podzielona (7 domen zamiast jednej).** Na obrazach generatora istniejący detektor barier kontrastu tnie także regularne rzędy molekuł. To porażka całego zestawu ustawień. Test samej segmentacji z poprawnymi pomiarami i bez barier daje jedną domenę; nie zastępuje to oceny pełnego wejścia obrazowego.

**Skok fazy nie został poprawnie rozpoznany:** żadna molekuła nie otrzymała domeny, oba oczekiwane regiony pominięto. Zero błędnych scaleń przy pełnej odmowie nie jest sukcesem detekcji granicy. Dodatkowa kontrola na analitycznych pomiarach o identycznym kącie i rozstawie scala obie przesunięte części — jawny błąd wynikający z braku testu fazy.

Przy stopniowej deformacji pełny pomiar i bariery prowadzą do zerowego wyniku. Niezależny test publicznej segmentacji na analitycznych pomiarach stopniowego obrotu potwierdza, że żadna domena nie przekracza limitu całego regionu. Brakujące centra nie są same w sobie barierą; analityczna kontrola pojedynczego braku zachowuje jedną domenę, duża luka rozdziela dwie. Same rzędy i szum nie tworzą domen 2D w tej próbie.

Raport liczy domeny zawierające >1 region referencji, regiony rozdzielone na >1 domenę, regiony pominięte i pary przy znanej granicy: połączone / rozdzielone / z odmową. Każda kategoria jest osobna. Nie utożsamiamy odmowy z poprawnym wyznaczeniem granicy.

**Wniosek:** funkcja nadaje się do porównywania hipotez i strojenia. Nie ma podstaw do uznania tej metody za gotowy detektor domen 2D ani do zastąpienia nią metody bazowej. Łagodniejszy zestaw nie poprawił wyników na TTMAPP; ograniczeniem są również pomiary i bariery, nie tylko tolerancje.

## Sprawdzenia

Testy publicznych obliczeń, parametrów, całego regionu, symetrii, barier, braków, powtarzalności, anulowania i zapisu/odczytu; regresje okna Analiza i karty C. Pełny wynik zestawu i przeglądu zostanie uzupełniony po zakończeniu.

Natywne GUI X11 w netcat: kontrole 1–9 i TTMAPP259–266, rzeczywiste wyniki obu metod, przełączanie z niezmiennym zoomem, raw/aligned, karta C, okno 1024×768, anulowanie, zapis/otwarcie i zamknięcie w trakcie pracy. Artefakty: `.scratch/stmdomains-ui-17/` (raport, log, PNG, projekt, skrypty). To wykonane sprawdzenie automatyczne GUI; nie jest odbiorem użytkownika.

## Test ręczny użytkownika

1. W środowisku `netcat` uruchom `python -m stmdomains.main`, otwórz TTMAPP i klatkę 259.
2. Analiza → Analiza… → Bazowa, zakres bieżąca klatka, nowe K5 z bieżącej klatki. Analizuj.
3. W tym samym oknie wybierz Geometria. Zostaw 12°, 16%, 0,75 i 10. Analizuj. Powinna powstać 1 domena z 32/312 molekułami przy domyślnych pozostałych ustawieniach.
4. Powiększ obraz. Przełącz Bazowa/Geometria nad nim: klatka i zoom pozostają, zmieniają się przypisania. Szare molekuły mają przyczyny w Danych oznaczenia; Dane… wyniku pokazują faktycznie użyte parametry.
5. Zmień parametry bez Analizuj: obraz nie zmienia się. Oblicz ścisłe 6°, 8%, 0,85 i 12: 19/312 na klatce 259. Anuluj kolejną próbę; zachowany wynik nadal dostępny.
6. Otwórz `.scratch/stmdomains-ui-17/demo/domain-geometry.moltrack.json`. Sprawdź kontrole według tabeli, także udokumentowane porażki. Nie oczekuj rozdzielenia skoku fazy.
7. Zapisz wyświetlany wynik do nowego `.stmdomains`, otwórz i porównaj. W pliku pozostaje jeden wybrany wynik; drugą metodę można ponownie obliczyć.

Powtórzenie próby: `python -m stmdomains.tools.geometry_domain_trial .scratch/stmdomains-ui-17-repeat --source data/TTMAPP/detection_full.moltrack.json` w środowisku netcat.
