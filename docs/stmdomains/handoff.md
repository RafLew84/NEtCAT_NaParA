# STM Domains — przekazanie podziału na dwa etapy

Data: 2026-10-16.
Gałąź docelowa: `domains/start`.
Gałąź przygotowania: `domains/staged-plan`, na bazie `0dab344`.
Commit zmiany: identyfikator w końcowej wiadomości sesji.

## Zakres i wynik

Na polecenie użytkownika rozdzielono dotychczasową mapę całego programu:

- [Etap 1: działający szkielet](map.md) obejmuje import, podstawowy podgląd
  i przygotowanie implementacji oraz odbioru na rzeczywistych danych.
- [Etap 2: metody i zapis wyników](map-methods-and-save.md) obejmuje definicje
  wysp i domen sieci, referencje, próby metod, statystyki i zapis/eksport.
  Zaczyna się po implementacji i odbiorze szkieletu.

Zachowano ID i ścieżki dziewięciu ticketów. Trzy otwarte pytania należą do
pierwszej mapy, pięć do drugiej. Pytanie o pomiar orientacji pojedynczej molekuły
zamknięto jako odłożone poza oba etapy, bez rozstrzygnięcia naukowego.
Żaden otwarty ticket nie zależy od tego zamkniętego pytania.

Przekazanie szkieletu do implementacji zależy teraz tylko od importu i podglądu.
Wybór metod, ich skuteczność, statystyki i własny format wyników nie blokują
budowy szkieletu. Nie uznano żadnej decyzji technicznej za rozstrzygniętą
ani żadnego fragmentu aplikacji za wdrożony.

Zaktualizowano [rejestr i diagram zależności](issues/README.md), README i słownik.
Dołączono [wcześniejszy raport o level set](research-domain-detection-level-sets.md)
z gałęzi Viewer jako materiał drugiego etapu; nie wykonywano nowego researchu.

## Kolejny krok

Aktywna jest pierwsza mapa. Następne pytanie:
[Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](issues/01-import-and-geometry.md).
Po nim podstawowy podgląd i przekazanie szkieletu do implementacji. Samo
zamknięcie tych decyzji nie zastępuje wykonania oraz odbioru aplikacji.

## Sprawdzenia

- Kontrola statusów, rodziców i zależności ticketów oraz zgodności z diagramem.
- Sprawdzenie braku cykli i zależności pierwszej mapy od drugiego etapu.
- Kontrola odnośników zmienianej dokumentacji i `git diff --check`.
- Brak zmian kodu; nie uruchamiano testów aplikacji, GUI ani metod detekcji.

## Zachowany kontekst importu i integracji

Poprzednie przekazanie oraz audyt są zachowane w historii `0dab344`.
Przed implementacją importu przeczytaj
[notatkę o orientacji obrazu i danych](research-molecular-orientation.md):
loader MPP obraca obraz o 180 stopni, co musi być zgodne z oznaczeniami.
Kalibracja fizyczna i czasy przykładowego eksportu są niewiarygodne; nie wolno
traktować zastępczych wartości jako pomiaru.

Wcześniejsza sesja zgłosiła też podwójne odwrócenie kolejności serii wielu
STP/S94 podczas odtwarzania w NanoTrack. Pozostaje to zgłoszeniem dla integracji,
bez naprawy w tym zadaniu; obecne wejście oparte na jednym MPP nie wymaga tego
wariantu loadera. Nie zmieniono wspólnych modułów ani konfiguracji środowiska.

Zmiany przygotowano w worktree przypisanym do bieżącej sesji. Aktualizacja
docelowego worktree odbywa się commitem i scaleniem, zgodnie z instrukcją
współpracy; nie przenosimy zmian roboczych między worktree.
