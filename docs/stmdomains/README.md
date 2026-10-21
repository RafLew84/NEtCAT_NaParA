# STM Domains

Program do wykrywania i analizy domen pól molekularnych na obrazach STM.
Katalog aplikacji: `stmdomains/`.

## Stan początkowy

Gotowe są osobny punkt uruchomienia, podstawowe okno PyQt6 i akcja zakończenia.
Pierwszy etap rozwoju ma dać działający szkielet: import zapisu z gotowymi
oznaczeniami, doczytanie obrazów, przeglądanie klatek, zoom/gamma i podgląd
zapisanej rejestracji. Kod nie implementuje jeszcze tych funkcji.

2026-10-19 uzgodniono
[kontrakt importu MolTrack z jednym MPP](issues/01-import-and-geometry.md)
i wykonano [audyt na danych TTMAPP](import-geometry-audit.md).
Po obejrzeniu trzech wariantów prototypu HTML na danych TTMAPP użytkownik
[wybrał podstawowy podgląd](issues/07-browsing-and-comparison.md): jeden obraz
z przełączaniem oryginał/wyrównany, dolny pasek miniatur i nawigacja z play/pauzą.
Instrukcja otwarcia i odtworzenia szkicu jest w tickecie; to nie implementacja
natywnego okna aplikacji. Zakończono także
[przekazanie do implementacji](issues/09-implementation-handoff.md): pierwsza
mapa decyzji jest zamknięta, a [trzy zadania budowy i odbioru](implementation/README.md)
czekają ze statusem `todo`. Następny krok to
[import, model serii i geometria](implementation/01-import-model.md).
Przyjęto automatyczny kontrast każdej klatki i odtwarzanie bez pomijania klatek.
Etap 1 będzie wykonany dopiero po budowie oraz odbiorze programu.

Na polecenie użytkownika tego samego dnia rozstrzygnięto też wcześniej
[definicje wysp, typów i domen](issues/02-order-types-and-domains.md) z etapu 2.
Ustalenia pojęciowe nie zastępują implementacji i odbioru szkieletu ani prób metod.

Następnie, także na bezpośrednie polecenie użytkownika, wykonano
[pilotaż wspólnego katalogu i porównania metod](issues/05-stable-types-across-frames.md).
[Raport](method-comparison-pilot.md) opisuje osiem klatek TTMAPP, kontrole
syntetyczne i lokalny prototyp HTML. Wyniki ujawniły braki; użytkownik polecił
dodać dalsze tickety o pokryciu, typach, granicach i odbiorze metod. Nie wybrano
algorytmu do aplikacji. Źródła prototypu pozostają na osobnej gałęzi, a dane
i wygenerowany HTML lokalnie poza Git.

Na kolejne polecenie użytkownika uzgodniono
[definicje statystyk klatek](issues/06-frame-statistics.md): dwa mianowniki
udziału powierzchni, przypisywanie molekuł według środka oznaczenia, wyniki
częściowe i ręczne rozstrzyganie konkretnych konfliktów domen. Tabela i wykres
dotyczą osobnych klatek; sumy i średnie serii są poza obecnym zakresem.
Dołączono przykład rachunkowy i schemat. Statystyki ani ich UI nie są jeszcze
zaimplementowane w aplikacji.

Na bezpośrednie polecenie użytkownika uzgodniono także
[zapis i eksport](issues/08-save-and-export.md): samowystarczalny plik
`.stmdomains` z MPP, oznaczeniami, podglądem i opcjonalnie jednym wynikiem.
Otwarcie odtwarza wynik oraz korekty bez uruchamiania metod. Eksport obejmuje
CSV zbiorcze/szczegółowe i PNG całego widoku lub wycinka, także wykresy.
To kontrakt do implementacji; odbiór metod sprawdzi jego realizację na danych.
Nie powstał jeszcze serializer ani interfejs zapisu.

2026-10-21 wykonano [wstępną próbę pokrycia i skali](issues/10-coverage-and-scale.md).
[Raport](coverage-and-scale-pilot.md) i lokalny HTML dokumentują wpływ braków
centrów, skali, kontrastu i szumu. Użytkownik potwierdził dalszą próbę
z referencjami; nie wybrano metody. Pokrycie dotyczy rozpoznanego materiału
na dowolnym widocznym poziomie warstwy, z osobnym nierozstrzygnięciem dla
ciemnych miejsc bez wystarczających danych. Po wstępnej próbie ticket pozostawał `claimed`.
Następnie [przyjęto częściowe referencje wybranych domen](partial-domain-reference-audit.md)
z klatek 250–268: 18 par PNG, zweryfikowana geometria, przygotowane robocze
wnętrza ramek. Pozostałe obszary nie są oznaczone; pełna ocena pokrycia
wymaga dodatkowych referencji podłoża i niepewności. Obecny zbiór został
zaakceptowany do lokalnych prób bez oczekiwania na kolejne oznaczenia.
[Wykonano porównanie na częściowej referencji](coverage-partial-reference-trial.md):
10 wariantów, 18 klatek i cztery kontrolowane ubytki centrów. Wyniki ujawniły
utratę znanego materiału przez proste warianty obrazowe oraz silną zależność
masek z centrów od kompletności detekcji. Interaktywny wynik jest w
`.scratch/coverage-partial-trial/index.html`; nie wybrano metody produkcyjnej.
Po omówieniu wyników krok 10 ma status `resolved` jako zakończona próba badawcza.
Nie czeka na krok 11; pełny odbiór metody pokrycia nadal pozostaje otwarty.

2026-10-21 wykonano również [próbę katalogu typów](structural-type-catalogue-trial.md):
9 wariantów, 18 klatek TTMAPP i 19 kontroli syntetycznych. Kolory referencji
opisują głównie różne orientacje tej samej sieci, zgodnie z doprecyzowaniem
użytkownika. Cechy rozstawu i różnic odległości poprawiają rozróżnianie kontroli,
ale katalog TTMAPP pozostaje rozdrobniony i zależny od zakresu. [Krok 11](issues/11-structural-type-catalogue.md)
ma status `resolved` jako zakończony eksperyment, bez wyboru gotowej metody.
Wynik jest gotowy do obejrzenia w `.scratch/type-catalogue-trial/index.html`;
odbiór metod 13 nadal pozostaje otwarty.

2026-10-21 wykonano [próbę granic przesunięcia](phase-boundaries-trial.md):
7 wariantów, 19 kontroli i 18 klatek TTMAPP. Niedopasowanie wektorów centrów
rozdziela proste kontrolne domeny o tym samym typie i kącie, zachowując
pojedyncze defekty wewnątrz domeny. Wiarygodna estymata sieci, braki detekcji
i wpływ kontrastu na fazę pozostają ograniczeniami. [Krok 12](issues/12-phase-boundaries.md)
jest `resolved` jako wykonany eksperyment, bez zatwierdzenia metody.
Podgląd: `.scratch/phase-boundaries-trial/index.html`. Próby 10–12 są zakończone;
protokół jakości 04 oraz odbiór metod 13 pozostają otwarte.

## Dwa etapy

- [Etap 1: działający szkielet](map.md) — import, podstawowy podgląd oraz
  przygotowanie implementacji i jej odbioru na rzeczywistych danych.
- [Etap 2: metody i zapis wyników](map-methods-and-save.md) — po odbiorze
  szkieletu: próby wykrywania wysp i domen sieci, ocena jakości, statystyki
  oraz zapis/eksport wyników.

Podział zatwierdził użytkownik 2026-10-16. Wybór metody i formatu wyników
nie blokuje budowy szkieletu. Pomiar orientacji pojedynczej molekuły odłożono
poza oba etapy; orientacja sieci pozostaje w drugim etapie.

[Rejestr pytań i zależności](issues/README.md) prowadzi do kolejnych rozmów
i prototypów; [słownik](GLOSSARY.md) ustala nazwy. To mapy decyzji `wayfinder`:
pierwsza jest zamknięta, a implementacja szkieletu może ruszyć bez czekania
na drugą. Aktualizacja dokumentacji nie oznacza wykonania programu.
Pliki wersjonujemy na gałęzi `domains/*`; [przekazanie](handoff.md) opisuje stan
gotowy do odbioru w sesji integracyjnej.

## Uruchomienie

Z katalogu głównego worktree, w jego środowisku:

```bash
python -m stmdomains.main
```

[Przygotowanie środowiska](../../README.md) i
[praca równoległa](../PARALLEL_DEVELOPMENT.md).

## Kod do oceny i testy

- Istniejąca analiza molekularna: `moltrack/analysis/` oraz `tests/moltrack/`.
- Czytniki i model obrazu: `napara/io/`, `napara/core/data_models.py`.
- Viewer: `napara/gui/widgets/viewer_widget.py`.
- Testy nowych funkcji: `tests/stmdomains/` (na razie katalog startowy).

Współdzielony kod i modele mogą wymagać dodatkowych zależności poza PyQt6 szkieletu.
Nowe metody będą oceniane na danych i kryteriach rozstrzygniętych przez pytania mapy.

## Materiały do decyzji

- [Ogólne wykrywanie domen molekularnych](research-general-domain-detection.md)
  — przegląd metod wykrywania regularności rozmieszczenia i uporządkowania
  orientacji molekuł, założeń MolTrack oraz propozycja porównania metod na danych.
  Notatka badawcza z 2026-10-14, rozszerzona o rozwiązania z lat 2024–2026,
  w tym SBC/MatID, odkrywanie lokalnych środowisk i analizę obrazów STM.
  Wybór rozwiązania pozostaje otwarty.
- [Pomiar orientacji pojedynczej molekuły](research-molecular-orientation.md)
  — wymagane dane wejściowe, znaczenie kąta, porównanie metod oraz inspekcja
  przykładowego zapisu TTMAPP i wycinków obrazu. Parametry fizyczne eksportu
  są nieznane; definicja orientacji pozostaje do ustalenia na przykładach.
  Audyt importu pozostaje potrzebny w etapie 1; sam pomiar kąta jest odłożony.
- [Wyspy, orientacja sieci i level set](research-domain-detection-level-sets.md)
  — materiał do drugiego etapu: osobne warstwy pokrycia i sieci, ocena
  podejścia Gibou–Fedkiwa oraz propozycja porównania metod na referencjach.
