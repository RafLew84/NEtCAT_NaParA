# REG-05: Zgodność lokalnych fragmentów

**What to build:** Użytkownik widzi, jak kilka części obrazu popiera wybrane
globalne XY, a metoda wyznacza je odpornie na lokalne błędne dopasowania.
**Blocked by:** [REG-04](04-multiscale-translation.md), w tym odbiór manualny — spełnione 2026-10-31.
**Status:** done
**Manualny odbiór:** zaakceptowany przez użytkownika 2026-10-31: „testy manualne 05 ok”.
**Wykonawca:** Codex; baza przeglądu `a59029d`.
**Granice TDD:** para → XY i dowody lokalne, GUI → mapa i wynik, seria/eksport; zgodnie z poniższym zakresem ticketu.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).

**Doprecyzowanie po research — 2026-10-31:** obecny Deep już wybiera grupę
zgodnych wektorów i ważoną medianę. Nowością tego ticketu jest rozmieszczenie
poparcia po obrazie, niezależność fragmentów i ocena konkurujących grup,
a nie samo dodanie pierwszego odpornego konsensusu.
Źródło: [przegląd](../../registration-multiframe-research.md#co-wiemy-lokalnie).

## Zakres i kryteria odbioru

- [x] Po początkowym globalnym XY metoda wybiera przestrzennie rozdzielone fragmenty
  z dostateczną teksturą i szuka ich odpowiedników w rozszerzonym otoczeniu
  drugiej klatki. Nie koreluje wyłącznie wycinków o tych samych współrzędnych.
- [x] Podstawowe porównanie startuje z dokładnego wyniku obecnego Deep bez ECC.
  Bazowe XY, jego konfiguracja i nowy wynik są zachowane oddzielnie; nie liczymy
  ponownie innego startu dla wyniku A. Deep→ECC z REG-04 jest osobnym wariantem
  porównawczym, a nie obowiązkowym inicjalizatorem REG-05 ani późniejszego grafu.
- [x] Fragmenty obejmują wyłącznie ważne próbki obu obrazów w rzeczywistych
  miejscach dopasowania. Braki danych i padding nie są teksturą.
  Wielkości fragmentów, obszar poszukiwania i reguły konsensusu są zapisane
  w wersjonowanym zestawie ustawień; nie dobieramy ich po cichu osobno do filmu.
- [x] Agregacja odrzuca odstające dopasowania, uwzględnia niejednoznaczne
  maksima i wymaga przestrzennego rozłożenia poparcia. Wiele nakładających
  się fragmentów z jednego pasa nie jest traktowane jako niezależna większość.
- [x] Nakładka pokazuje miejsca fragmentów, ich XY oraz stan: zgodny,
  odrzucony lub bez dopasowania. Wyjaśnienie wyniku nie opiera się wyłącznie
  na jednym pozornie precyzyjnym procencie pewności.
- [x] Przy konkurencyjnych grupach przesunięć lub braku poparcia metoda
  pokazuje niepewność/odmawia zgodnie z kontraktem. Nie zastępuje wyniku zerem
  ani nie ukrywa problemu wybierając inne narzędzie.
- [x] Wariant działa dla par i całej serii, zachowując zwykłe aligned i eksporty.
  Mapa fragmentów jest diagnostyką i nie trafia do wartości MPP ani zwykłego AVI.

Poza zakresem: niezależna walidacja na niewykorzystanych danych, korekcja
poszczególnych fragmentów. Wszystkie piksele klatki nadal otrzymują jedno XY.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Para → globalne XY i dowody lokalne:** wzorzec ze znanym ruchem,
  silnym nieruchomym artefaktem, częścią odstających fragmentów i konkurującymi
  grupami. Liczy się odzyskanie właściwego XY lub jawna odmowa, nie identyczne
  numery wewnętrznie wybranych fragmentów.
- **GUI → mapa i wynik:** prawidłowe współrzędne przy zoom/pan, zgodność
  pokazywanych wektorów z wynikiem i integralność przypiętej próby A.
- **Seria/eksport:** jedno XY na klatkę, brak lokalnej deformacji,
  poprawne źródłowe próbki, anulowanie i brak dopisywania diagnostyki do obrazu.

## Próba manualna

1. Na wzorcu z przesuniętą strukturą i nieruchomym pasem obejrzyj fragmenty
   zgodne/odrzucone. Sprawdź, czy wynik wynika z kilku części próbki.
2. Na obu filmach porównaj bazowy Deep jako wynik A z REG-05 jako wynik B,
   z tym samym startem, oryginałami i ustawieniami podglądu. Osobno porównaj
   Deep→ECC z REG-04; nie zmieniaj inicjalizacji i konsensusu w jednej próbie.
   Dla każdej stałej pary sprawdź poparcie w różnych miejscach, nie tylko jego liczbę.
3. Obejrzyj dostarczony wzorzec, w którym góra i dół mają różne XY. Wynik
   nie może udawać korekcji obu części; rozbieżność ma być widoczna.
   Na pomiarach wykonaj tę próbę, jeśli taki przypadek rozpoznano.
4. Uruchom całe filmy, sprawdź stałe i dodatkowe pary, potem wykonaj
   kontrole anulowania i małego eksportu z protokołu.

**Oczekiwany wynik:** weryfikowalny konsensus i rzeczywista ocena jego jakości.
Zgodność fragmentów użytych do estymacji nie jest jeszcze niezależną walidacją.

## Wykonanie — 2026-10-31

Implementacja: `303e401`; poprawka po przeglądzie: `75eb70f`.
[Instrukcja ręczna](../local-consensus-manual.md),
[wyniki prób](../local-consensus-results.md),
[karta testów i przeglądu](../reviews/REG-05.md).

Dostępna metoda **Deep Matcher + lokalne fragmenty (v1)** dla pary i całej
serii, mapa fragmentów oraz dokładny start Deep. Testy Viewera: 474 PASS,
2 SKIP; mypy 49 plików PASS. Standards i Spec: 0 otwartych uwag.

Rzeczywiste próby dały wynik lokalny dla 2/14 wskazanych par; pełne MOVIE_4
i MOVIE_8 kończą się jawną odmową. Udane wzorce i odmowy są możliwe do
obejrzenia w GUI. Nie potwierdzono poprawy jakości STM względem Deep.
Użytkownik potwierdził „testy manualne 05 ok” 2026-10-31. Etap zamknięto
jako odebrany wariant eksperymentalny z opisanymi ograniczeniami; nie oznacza
to przewagi konsensusu lokalnego nad Deep. Osobno użytkownik ocenił checkpoint
Outdoor jako znacznie lepszy w obejrzanym porównaniu wag. Nie dopisano odbioru
Windows, VLC ani GPU 8 GB. Zależność REG-06 jest spełniona; implementacja
REG-06 pozostaje nierozpoczęta.
