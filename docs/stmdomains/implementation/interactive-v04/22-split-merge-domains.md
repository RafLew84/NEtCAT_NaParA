# 22: Dziel i łącz domeny na obrazie

**ID:** SD-V4-22

**What to build:** Użytkownik wydziela zaznaczone molekuły do osobnej domeny albo łączy sąsiadujące domeny. Przed zatwierdzeniem widzi wynik, a całą zmianę może cofnąć jednym krokiem.

**Blocked by:** [21: Twórz domeny ręcznie i zmieniaj ich skład](21-manual-domain-membership.md).

**Status:** ready-for-agent — dodanie do planu zlecone przez użytkownika 2026-11-03; wykonanie po zależności.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady edycji ręcznej](README.md#edycja-ręczna-klas-i-domen).

## Kryteria akceptacji

- [ ] Podziel domenę wydziela zaznaczony niepusty podzbiór członków do nowej domeny. Pozostała część zachowuje swój identyfikator; nowa dostaje odrębny. Zaznaczenie całej domeny lub punktów z kilku domen daje czytelne wyjaśnienie i nie wykonuje przypadkowego podziału.
- [ ] Połącz domeny pokazuje listę wybranych domen, ich członków oraz docelowy identyfikator. Po zatwierdzeniu powstaje ich suma bez duplikatów. Wybór jednej domeny nie jest operacją scalenia; anulowanie podglądu niczego nie zmienia.
- [ ] Podział zachowuje klasę źródła. Scalenie domen jednej klasy zachowuje tę klasę; przy różnych klasach UI jawnie pokazuje wynik z klasą nieustaloną. Źródłowe klasy pozostają w bazowym wyniku. Nadanie wspólnej klasy należy do 23, nie zachodzi przez sam wybór koloru.
- [ ] Maski i obrysy są zgodne z nowym członkostwem i nie nakładają się. Scalenie nie dorysowuje mostu przez rzeczywistą przerwę; jeśli według opisanej reguły geometrii fragmenty nie tworzą spójnej domeny, program wyjaśnia odmowę. Wspólna klasa kilku osobnych domen pozostaje możliwa w 23.
- [ ] Obie operacje aktualizują etykiety, liczniki i legendę, zachowują sumę przypisanych molekuł oraz stanowią jeden krok Cofnij/Ponów. Historia wiąże źródłowe i docelowe domeny; nie renumeruje domen niezwiązanych z operacją i nie zmienia innych klatek.
- [ ] Automatyczny/Po korektach działa po podziale, scaleniu i cofnięciu. Ponowna analiza zachowuje poprawiony wariant zgodnie z 21. Kontrole automatyczne i GUI obejmują podział/scalenie, konflikt klas, przerwę, anulowanie oraz undo/redo; raport potwierdza netcat i limit 1000/1500 linii.

## Test ręczny użytkownika

1. W netcat uruchom aplikację, otwórz TTMAPP i oblicz klatkę 259. Zaznacz lassem część jednej domeny i wybierz Podziel; obejrzyj podgląd, zatwierdź i sprawdź dwa ID przy tej samej sumie członków.
2. Cofnij i ponów podział. Połącz powstałe sąsiadujące domeny i sprawdź powrót do pierwotnego członkostwa oraz obszaru. Oryginalny wariant automatyczny pozostaje dostępny.
3. Na dostarczonym przykładzie połącz domeny o różnych klasach: podgląd ma uprzedzić o klasie nieustalonej. Sprawdź anulowanie i cofnięcie.
4. Na przykładzie dwóch fragmentów rozdzielonych przerwą sprawdź odmowę scalenia bez narysowania mostu. Zaznaczenie całej domeny do podziału nie tworzy pustej domeny.
5. Przejdź na sąsiednią klatkę i wróć; zmieniła się wyłącznie edytowana klatka. Sprawdź zgodność obrysów w raw/aligned.

## Granice zadania

Operacje na istniejących oznaczeniach jednej klatki. Bez śledzenia domen między klatkami, automatycznej propagacji poprawek, nowej metody segmentacji ani edytora swobodnie rysowanych granic. Działają mechanizmy historii i ochrony pracy z 21.
