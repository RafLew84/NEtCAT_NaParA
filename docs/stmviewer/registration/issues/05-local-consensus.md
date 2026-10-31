# REG-05: Zgodność lokalnych fragmentów

**What to build:** Użytkownik widzi, jak kilka części obrazu popiera wybrane
globalne XY, a metoda wyznacza je odpornie na lokalne błędne dopasowania.
**Blocked by:** [REG-04](04-multiscale-translation.md), w tym odbiór manualny.
**Status:** ready-for-agent
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).

## Zakres i kryteria odbioru

- [ ] Po początkowym globalnym XY metoda wybiera przestrzennie rozdzielone fragmenty
  z dostateczną teksturą i szuka ich odpowiedników w rozszerzonym otoczeniu
  drugiej klatki. Nie koreluje wyłącznie wycinków o tych samych współrzędnych.
- [ ] Fragmenty obejmują wyłącznie ważne próbki obu obrazów w rzeczywistych
  miejscach dopasowania. Braki danych i padding nie są teksturą.
  Wielkości fragmentów, obszar poszukiwania i reguły konsensusu są zapisane
  w wersjonowanym zestawie ustawień; nie dobieramy ich po cichu osobno do filmu.
- [ ] Agregacja odrzuca odstające dopasowania, uwzględnia niejednoznaczne
  maksima i wymaga przestrzennego rozłożenia poparcia. Wiele nakładających
  się fragmentów z jednego pasa nie jest traktowane jako niezależna większość.
- [ ] Nakładka pokazuje miejsca fragmentów, ich XY oraz stan: zgodny,
  odrzucony lub bez dopasowania. Wyjaśnienie wyniku nie opiera się wyłącznie
  na jednym pozornie precyzyjnym procencie pewności.
- [ ] Przy konkurencyjnych grupach przesunięć lub braku poparcia metoda
  pokazuje niepewność/odmawia zgodnie z kontraktem. Nie zastępuje wyniku zerem
  ani nie ukrywa problemu wybierając inne narzędzie.
- [ ] Wariant działa dla par i całej serii, zachowując zwykłe aligned i eksporty.
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
2. Na obu filmach porównaj hybrydę Deep Matcher + ECC z REG-04 jako wynik A
   z REG-05 jako wynik B przy tych samych oryginałach
   i ustawieniach podglądu.
   Dla każdej stałej pary sprawdź poparcie w różnych miejscach, nie tylko jego liczbę.
3. Obejrzyj dostarczony wzorzec, w którym góra i dół mają różne XY. Wynik
   nie może udawać korekcji obu części; rozbieżność ma być widoczna.
   Na pomiarach wykonaj tę próbę, jeśli taki przypadek rozpoznano.
4. Uruchom całe filmy, sprawdź stałe i dodatkowe pary, potem wykonaj
   kontrole anulowania i małego eksportu z protokołu.

**Oczekiwany wynik:** weryfikowalny konsensus i rzeczywista ocena jego jakości.
Zgodność fragmentów użytych do estymacji nie jest jeszcze niezależną walidacją.
