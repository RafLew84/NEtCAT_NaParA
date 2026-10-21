# Jak wyznaczać pokrycie bez mylenia luk oznaczeń z podłożem?

ID: 10
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: claimed
Assignee: Codex — domains/coverage-and-scale
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 04, 05

## Question

Jak wyznaczać cały płat warstwy, zachowując zwykłe odstępy między molekułami,
ale wykluczając większe obszary podłoża, przy niepełnych oznaczeniach i zmiennym
kontraście obrazu? Kiedy należy odmówić wyznaczenia maski?

[Pilotaż](../method-comparison-pilot.md) pokazał m.in. pokrycie 45,5–78,8%
klatki 68 wyznaczone z zaledwie trzech centrów oraz silną zależność Chan–Vese
od wygładzania. Sprawdźmy dobór skali przy rzadkich oznaczeniach, osobno wpływ
poszczególnych parametrów oraz założenie jaśniejszej warstwy. Brak detekcji
nie jest referencją pustego podłoża.

Porównanie ma korzystać z niezależnie oznaczonych granic płata i niepewności
z pytania o referencje. Obejmuje luki oznaczeń, małe wyspy, odsłonięte podłoże,
zwykłe odstępy oraz brzeg obrazu; padding nie jest pomiarem. Dobór kolejnego
wariantu regionowego lub level set wynika z obserwowanych błędów. Jeśli
porównujemy Gibou–Fedkiwa, potrzebna jest jego rzeczywista implementacja;
obecny Chan–Vese nie rozstrzyga jego przydatności.

Wynik: obejrzane przez użytkownika maski, parametry, błędy granic/pokrycia,
błędne scalenia i podziały wysp oraz warunki braku wyniku. Zapisujemy również
koszt, pamięć i ograniczenia. Nie wybieramy wariantu wyłącznie po liczbie wysp.

## Dependencies

- [Jakie referencje i kryteria potwierdzą wiarygodność analizy?](04-reference-and-quality.md)
- [Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md)

## Work started — 2026-10-21

Na bezpośrednie polecenie użytkownika przygotowujemy próbę przed zamknięciem
pytania o referencje. Kontrole syntetyczne i rozbieżności na TTMAPP nie
zastępują niezależnego oznaczenia granic warstwy. Zakres końcowego wniosku
zależy od dostępności referencji i reakcji użytkownika na maski.

## Answer — 2026-10-21, wynik wstępny

**Zakończono i omówiono porównanie wstępne. Pełne pytanie pozostaje `claimed`**:
w chwili tej próby nie dostarczono niezależnych referencji pokrycia TTMAPP,
więc nie oceniono trafności ani nie wybrano metody. Zależność od pytania o referencje pozostaje.
Użytkownik najpierw polecił porównanie wstępne, zaznaczając, że może posiadać
klatki referencyjne. Następnie po otrzymaniu prototypu potwierdził:
„Tak — dalsza próba z referencjami”. Nie jest to akceptacja gotowego algorytmu.

### Przyjęte znaczenie pokrycia

Użytkownik opisał ciemne pasma w pierwszej klatce jako prawdopodobne odstępy
w warstwie wierzchniej, odsłaniające warstwę poniżej. To wskazówka interpretacji,
nie niezależna maska referencyjna ani potwierdzony pomiar wysokości.
Na pytanie o cel pierwszej maski odpowiedział: materiał na dowolnym poziomie,
jeżeli widoczne są molekuły; niższe warstwy bywają ciemne i molekuł nie widać.

Pokrycie obejmuje zatem rozpoznany materiał na dowolnym **widocznym** poziomie
warstwy wraz z normalnymi odstępami. Nie sumujemy zakrytych powierzchni warstw
ani nie ograniczamy maski do najwyższej warstwy. Ciemne miejsca bez widocznych
molekuł i bez innych wystarczających przesłanek pozostają nierozstrzygnięte;
nie stają się automatycznie podłożem ani materiałem. Doprecyzowano
[słownik](../GLOSSARY.md) i wejścia do przyszłych referencji. Zasady wyników
częściowych i nieznanego mianownika z
[decyzji o statystykach](06-frame-statistics.md) pozostają w mocy.

### Dowód i wynik próby

[Raport porównania](../coverage-and-scale-pilot.md) zawiera identyfikację
wejścia, parametry, kontrolowane ubytki oznaczeń, metryki błędów, koszt
i ograniczenia. Ostateczny prototyp obejmuje 25 obrazów i 10 wariantów:
osiem TTMAPP, trzy ubytki oznaczeń pierwszej klatki i czternaście kontroli.
Dwie kontrole celu maski przy wielu poziomach dodano po uwadze użytkownika;
nie przedstawiamy ich jako osobno zaakceptowanych przez niego masek.

- Trzy centra dają 45,53–78,78% pola przy skali z tej klatki, a 1,34–2,41%
  przy skali wspólnej. Usunięcie rozrostu nie odtwarza brakującej warstwy.
- Luka oznaczeń rozcina niezmieniony płat; zwiększenie skali potrafi błędnie
  połączyć dwa płaty przez odsłonięte podłoże.
- Wybór jasnej fazy zawodzi przy odwróceniu kontrastu. Cecha lokalnych zmian
  jasności zachowuje maskę po odwróceniu, lecz reaguje także na defekty i szum.
- Na kontrolnym pustym podłożu warianty obrazu proponują około połowy pola
  jako materiał. Samo działanie segmentacji nie jest podstawą pomiaru.
- Rozmycie obrazu i wygładzanie konturu porównano osobno. Nie dobierano
  parametrów wyłącznie do liczby wysp. Chan–Vese nie jest próbą Gibou–Fedkiwa.

Źródła: `prototype/stmdomains-coverage`, commit `3f2dee6`;
`stmdomains/prototypes/coverage_scale.py`, `.html`, `README-coverage-scale.md`.
Kod pozostaje na gałęzi prototypu. Polecenie odtworzenia jest w raporcie.
Lokalny HTML: `/home/rlew/projekty/NEtCAT-domains/.scratch/coverage-and-scale/index.html`.
Ostateczny generator: 28,91 s, 589,81 MiB szczytowego RSS wraz z odczytem
MPP/JSON, HTML 2,38 MiB. Pierwotne 230 wariantów zachowało identyczne maski
i metryki po ponownym obliczeniu. Sprawdzono interakcje i zrzuty HTML
w QtWebEngine; nie zmieniano ani nie testowano aplikacji produkcyjnej.
Obok są metryki, parametry, inspekcja oraz `reference-candidates/` z ośmioma
podglądami bez nakładek — nie z referencjami.

### Plan próby z przyjętą referencją — wykonanie opisano poniżej

1. Wykorzystać przygotowane wnętrza do porównania zachowania masek pokrycia
   na znanym materiale. Zapisać utracone fragmenty, parametry i koszt;
   zachowanie całego wnętrza samo nie świadczy o poprawności całej maski.
2. Rozbieżności i ograniczenia pokazać na konkretnych fragmentach obecnych
   klatek. Porównanie cech rozróżniających oznaczone domeny może korzystać
   z tej samej referencji, z zachowaniem jej częściowego zakresu.
3. O dodatkowe oznaczenia poprosić dopiero, gdy konkretna próba ujawni pytanie,
   którego ten zbiór nie rozstrzyga. Wskazać wtedy potrzebny fragment i rodzaj
   oznaczenia, np. pewne podłoże lub niepewną granicę.

Pełna ocena pokrycia, scaleń/podziałów i odmów pozostaje związana z
[protokołem jakości](04-reference-and-quality.md). Jego otwarty status nie
blokuje powyższych prób na obecnej referencji, zgodnie z decyzją poniżej.
Progi pomocnicze prototypu nie są zaakceptowanymi regułami odmowy pomiaru.
Nie utworzono kolejnego ticketu powielającego ten zakres.

## Uzupełnienie — częściowe referencje dostarczone 2026-10-21

Użytkownik wskazał `data/ttmapp_frames_250_268_domain_review` i potwierdził:
ramki opisują przybliżone granice całych wybranych widocznych domen; podobne
skupiska mogą istnieć poza nimi. Referencja obejmuje tylko te fragmenty,
nie całą górną część ani całą klatkę. Reszta jest nieoznaczona, nigdy
negatywna tylko z powodu braku ramki.

[Audyt i zasady wykorzystania](../partial-domain-reference-audit.md):
18 par PNG (bez klatki 255), wszystkie czyste obrazy odtworzone piksel w piksel
z MPP i zapisanej geometrii. Przygotowano 54 ostrożne wnętrza regionów,
manifest/hashy i maski raw/PNG. Kreski i pas przybliżonych granic są wyłączone
z roboczych wnętrz. Kolory pozostają etykietami zbioru, nie automatycznie typami
uporządkowania. Automatyczne predykcje ze starego katalogu nie są referencją.

Prototyp przygotowania: `prototype/stmdomains-coverage`, commit `4e7a757`.
Lokalny podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/partial-domain-reference/index.html`.
Na etapie przygotowania nie przeliczono metod na tych wnętrzach. Umożliwiają
ocenę lokalnego rozróżniania domen oraz zachowania materiału, ale nie pełnego pokrycia,
fałszywych wykryć poza ramkami ani całkowitej liczby domen. Nie wystarczają
samodzielnie do zamknięcia tego pytania; status nadal `claimed`.

### Decyzja użytkownika — korzystamy z obecnego zbioru

2026-10-21 użytkownik zaakceptował tę referencję na najbliższe próby;
kolejne przygotuje później, jeśli okażą się konieczne. Zaczynamy od obecnych
18 par i oznaczonych fragmentów, bez wymagania nowych anotacji przed próbą.
To zgoda na dalsze lokalne porównania mimo otwartego pytania 04, a nie
zatwierdzenie skuteczności metody ani kompletności referencji całych klatek.

## Próba na dostarczonej referencji — wykonana 2026-10-21

Na polecenie użytkownika **uruchomiono porównanie**, opisane w
[raporcie próby](../coverage-partial-reference-trial.md). Wszystkie 18 klatek,
54 robocze wnętrza, 10 niezmienionych wariantów oraz kontrola całego pola.
Dodano cztery ubytki centrów klatki 250 przy niezmienionym obrazie i referencji.
Obszary poza oznaczeniami pozostały wyłączone z oceny.

- Mediana zachowania oznaczonych wnętrz: wspólna skala ×0,45 **97,71%**,
  ×0,65 **99,51%**, jasna faza 3 px **45,00%**, lokalne zmiany jasności 3 px
  **23,87%**. Nie są to miary trafności całej maski.
- Klatka 250: po pozostawieniu 25% centrów fixed45 spada z **97,63% do 26,30%**.
  Przy trzech centrach auto65 obejmuje całe pole; wysoki wynik we wnętrzach
  nie potwierdza poprawności maski. Brak centrów daje jawny brak propozycji.
- Jasna i ciemna faza wybiórczo odrzucają różne oznaczone regiony.
  Prosta cecha amplitudy także nie odzyskuje całego materiału.

Źródła: `prototype/stmdomains-coverage`, **`e67ca93`**.
Podgląd: `/home/rlew/projekty/NEtCAT-domains/.scratch/coverage-partial-trial/index.html`.
Obok CSV, NPZ, hashe, parametry, zestawienia i inspekcja. Zweryfikowano miary
238 masek, zgodność 10 masek klatki 268 z pierwszą próbą oraz HTML w QtWebEngine
(22 przypadki, 15 kroków scenariuszy, bez błędów JS). Koszt: 28,49 s,
590,40 MiB RSS wraz z odczytem danych i generowaniem. Bez zmian aplikacji.

**Ta próba jest wykonana; ticket pozostaje `claimed` do omówienia wyniku
i dalszego zakresu.** Nie wybrano metody produkcyjnej. Obecny zbiór wystarcza
do kolejnych lokalnych porównań; nie poproszono o nowe referencje. Konkretny
nieoceniony aspekt to nadmiar maski poza ramkami: jeśli celem będzie wybór
rozrostu według błędów w otoczeniu, potrzebne będą oznaczenia właśnie tych
fragmentów. Przygotowanie pełnej anotacji klatek nie jest teraz wymagane.
