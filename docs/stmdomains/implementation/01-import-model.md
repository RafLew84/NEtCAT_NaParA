# Import, model serii i geometria

ID: SD-IMPL-01
Type: implementation
Status: todo
Assignee:
Depends on: [gotowa specyfikacja](../issues/09-implementation-handoff.md)

## Cel

Otworzyć podstawowe sekcje zapisu MolTrack i jeden MPP do lokalnego modelu
serii. Udostępnić dane pojedynczej klatki w original/aligned, zachowując
geometrię, oznaczenia i jawne braki, bez tworzenia widgetów lub wykonywania analizy.

## Zakres

- Lokalne moduły `core/series.py`, `io/moltrack_import.py`, `io/mask_codec.py`
  oraz `core/geometry.py`, według [przekazania](../issues/09-implementation-handoff.md).
  Model zachowuje nieznane confidence/jakość i kodowane maski; nie wymusza
  dostarczenia masek ani kompletnej rejestracji.
- Kontrakt importu jest w [pytaniu o import i geometrię](../issues/01-import-and-geometry.md).
  Obsłużyć podstawowy podzbiór schema 1/2/3, nieznaną wersję, mapę klatek,
  opcjonalne oznaczenia i rejestrację. Nie migrować analizy M6 ani modeli.
- Importer zwraca wyniki walidacji i kompletnego kandydata; żądanie nowej ścieżki
  i potwierdzenie mtime są jawne. Nie wyświetla dialogów, nie zastępuje globalnego
  stanu i nie zapisuje do źródeł. Potwierdzenie dotyczy ocenionego konkretnego MPP.
- Czytać MPP publicznym loaderem, bez odwracania kolejności; raz zastosować
  `source_frame_indices` do obrazów i czasów. Zachować orientację loadera.
- Ustalać padding z całej kompletnej rejestracji. Przygotowywać obraz jednej
  klatki bez budowania całego wyrównanego stosu. Bboxów nie przycinać w modelu;
  maski źródłowe pozostają niezmienione, a widok jest odtwarzany z nich.
- Dekodować maski na potrzeby klatki, kontrolować shape i powiązania,
  ograniczyć cache. Wadliwa opcjonalna maska nie blokuje poprawnego bboxa.
- Zachować diagnostykę importu wystarczającą do komunikatów UI. Błąd kluczowej
  mapy/źródła odrzuca kandydaturę, błąd opcjonalnego rekordu izoluje jego brak.

## Kryteria zakończenia

1. Testy przez interfejs importera/modelu odtwarzają schema 1/2/3 i odrzucają
   nieobsługiwaną wersję. Rozróżniają braki, pustą listę oraz uszkodzony rekord.
2. Przypadek źródłowej mapy `[4,2]` zachowuje obrazy, czasy i oznaczenia
   we właściwej kolejności przy obu wartościach starej flagi reverse.
3. Testy obejmują jedną klatkę, duplikaty/niecałkowite indeksy, naprawę źródła,
   zgodny/odrzucony/zaakceptowany mtime oraz niezgodny MPP. Nie omijają walidacji
   przez samo istnienie ścieżki lub zgodność nazwy pliku.
4. Na niesymetrycznych, niekwadratowych obrazach sprawdzono geometrię raw/aligned,
   całkowite/ułamkowe przesunięcia, wszystkie brzegi, globalny padding,
   bbox poza FoV, nieznany source_view, brak/failed/niepełną rejestrację.
5. Fixture'y wszystkich uzgodnionych kodowań masek obejmują `same-as-mask`,
   uszkodzenie danych i full shape. Otwarcie nie dekoduje wszystkich masek;
   poruszanie się po serii nie zwiększa cache bez ograniczenia.
6. Wielokrotne zmiany widoku nie mutują oryginału/bboxów/masek i nie kumulują
   interpolacji. Nie wymagamy bezstratnego raster round-trip po dwóch resamplingach.
7. Mały test rzeczywistego czytnika MPP wraz z importerem uzupełnia fixture'y
   parsera. Testy wzorców MolTrack/NanoTrack nie zastępują testów nowego interfejsu.

Dodatkowe istniejące punkty odniesienia: `tests/nanotrack/test_mpp_loader.py`,
`tests/moltrack/test_registered_coordinates.py`,
`tests/nanotrack/test_registration_aligned.py`. Jeden dawny test MPP wymaga
lokalnego `data/MOVIE_3.MPP`; brak tych danych należy jawnie odnotować.
Nie importować ciężkiego `session_store` w produkcji wyłącznie dla prywatnego
pomocnika; ewentualną wspólną ekstrakcję zgłosić integratorowi.

## Przekazanie

Commit, uruchomione testy, mapa błędów/diagnostyki, limity cache i sposób
odczytu klatki. To gotowy moduł dla UI, nie zakończenie całego szkieletu.
