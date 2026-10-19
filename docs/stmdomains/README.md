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
