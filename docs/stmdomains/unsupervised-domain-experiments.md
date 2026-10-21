# Próby samodzielnego wykrywania domen

Plan z 2026-10-21 przeniesiono na polecenie użytkownika do ticketów
[istniejącej mapy metod i zapisu](map-methods-and-save.md).
**Eksperymenty nie zostały jeszcze wykonane.** Zakres, zależności i warunki
zakończenia utrzymujemy w ticketach, zamiast w dwóch równoległych planach.
[Rejestr pytań](issues/README.md#próby-samodzielnego-znajdowania-domen)
zawiera ich kolejność i diagram zależności.

| Oznaczenie pierwotnego planu | Aktualne zadanie/pytanie |
| --- | --- |
| E0 — wspólne wejście i kontrole | [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](issues/14-unsupervised-input-and-controls.md) |
| E1 — lokalne otoczenie molekuł | [Czy otoczenie zaznaczonych molekuł pozwala samodzielnie znaleźć domeny?](issues/15-local-neighborhood-domains.md) |
| E2 — odtwarzanie komórki | [Czy SBC/MatID odtwarza domeny z niepełnych centrów molekuł?](issues/16-sbc-matid-domains.md) |
| E3 — lokalna struktura obrazu | [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](issues/17-image-texture-domains.md) |
| Wspólne porównanie i wybór | [Które metody i warunki odmowy wyniku przyjmujemy po próbach?](issues/13-method-acceptance.md) |

Najpierw przygotowujemy wspólne wejście; pierwszą zalecaną próbą jest
otoczenie zaznaczonych molekuł. Trzy porównania metod korzystają z tego
samego zestawu, ale nie zależą od powodzenia pozostałych kandydatów.
Otwarte [pytanie o pełną jakość](issues/04-reference-and-quality.md)
pozostaje warunkiem odbioru metody, a nie rozpoczęcia wstępnych prób.

Wspólny kontrakt, hashe danych, zakres pełnych klatek, oddzielenie referencji,
przypadki zero/jedna/wiele domen i miary porównania znajdują się w zadaniu
przygotowania wejścia. Ramki nie wyznaczają miejsc poszukiwania ani liczby
klas. Nowa seria prób zachowuje zakończone wyniki badań pokrycia, typów
oraz granic; nie oznacza jeszcze przyjęcia metody produkcyjnej.

Uzasadnienie kandydatów: [przegląd STM/AFM](research-stm-afm-unsupervised-domain-discovery.md)
oraz [przegląd grupowania obiektów](research-domain-discovery-and-object-clustering.md).
