# Próby samodzielnego wykrywania domen

Plan z 2026-10-21 przeniesiono na polecenie użytkownika do ticketów
[istniejącej mapy metod i zapisu](map-methods-and-save.md).
**Eksperymenty nie zostały jeszcze wykonane.** Zakres, zależności i warunki
zakończenia utrzymujemy w ticketach, zamiast w dwóch równoległych planach.
[Rejestr pytań](issues/README.md#próby-samodzielnego-znajdowania-domen)
zawiera ich kolejność i diagram zależności.

| Obszar planu | Aktualne zadanie/pytanie |
| --- | --- |
| E0 — wspólne wejście i kontrole | [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](issues/14-unsupervised-input-and-controls.md) |
| E1 — lokalne otoczenie molekuł | [Czy otoczenie zaznaczonych molekuł pozwala samodzielnie znaleźć domeny?](issues/15-local-neighborhood-domains.md) |
| E2 — odtwarzanie komórki | [Czy SBC/MatID odtwarza domeny z niepełnych centrów molekuł?](issues/16-sbc-matid-domains.md) |
| E3 — lokalna struktura obrazu | [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](issues/17-image-texture-domains.md) |
| Przygotowanie ML | [Jak przygotować cechy gotowych sieci bez treningu na naszych danych?](issues/18-frozen-feature-preparation.md) |
| Porównanie ML | [Czy gotowe cechy sieci pomagają odkrywać domeny bez przykładów?](issues/19-frozen-feature-domains.md) |
| Przygotowanie treningu | [Jak przygotować odtwarzalny trening bez etykiet domen?](issues/20-self-supervised-training-preparation.md) |
| Autoenkodery | [Czy AE i rVAE uczą się cech przydatnych do odkrywania domen?](issues/21-autoencoder-domains.md) |
| Lokalne SSL | [Czy lokalne uczenie podobieństwa poprawia wykrywanie domen?](issues/22-local-self-supervised-domains.md) |
| Ocena treningu i dalszy zakres | [Czy trening daje poprawę i które rozszerzenie warto wykonać?](issues/23-training-comparison-and-next-step.md) |
| Warunkowo: grafy | [Czy uczenie grafu otoczeń molekuł poprawia wykrywanie domen?](issues/24-graph-self-supervised-domains.md) |
| Warunkowo: maskowanie | [Czy maskowane odtwarzanie obrazu uczy relacji potrzebnych do domen?](issues/25-masked-autoencoder-domains.md) |
| Warunkowo: adaptacja | [Czy dalsze uczenie gotowego modelu na STM poprawia odkrywanie domen?](issues/26-pretrained-self-supervised-adaptation.md) |
| Wspólne porównanie i wybór | [Które metody i warunki odmowy wyniku przyjmujemy po próbach?](issues/13-method-acceptance.md) |

Najpierw przygotowujemy wspólne wejście; pierwszą zalecaną próbą jest
otoczenie zaznaczonych molekuł. Próby geometrii, SBC/MatID i klasycznej
tekstury korzystają z tego samego zestawu, niezależnie od siebie.
Gotowe cechy sieci przygotowujemy po przygotowaniu wspólnego wejścia; porównanie ML
korzysta z nich i z wyniku klasycznej tekstury. Nie wymaga powodzenia
tej metody. DINOv3 jest opcjonalny. Te tickety zachowują porównanie bez
własnego treningu; na późniejsze polecenie użytkownika zbadano również
[możliwości uczenia bez etykiet](research-self-supervised-domain-learning.md).
Na kolejne polecenie użytkownika przegląd rozwinięto w zadania 20–26.
Podstawowy zakres to przygotowanie, AE/rVAE i lokalne SSL oraz decyzja
o dalszym badaniu. Grafy, maskowanie i adaptacja są warunkowe; ich
uruchomienie wybieramy w kroku 23. Pełna kolejność i zależności pozostają
w [indeksie](issues/README.md#trening-bez-etykiet-domen) oraz ticketach.
Nie zastępuje to dotychczasowych prób ani nie oznacza uruchomienia treningu.
Otwarte [pytanie o pełną jakość](issues/04-reference-and-quality.md)
pozostaje warunkiem odbioru metody, a nie rozpoczęcia wstępnych prób.

Wspólny kontrakt, hashe danych, zakres pełnych klatek, oddzielenie referencji,
przypadki zero/jedna/wiele domen i miary porównania znajdują się w zadaniu
przygotowania wejścia. Ramki nie wyznaczają miejsc poszukiwania ani liczby
klas. Nowa seria prób zachowuje zakończone wyniki badań pokrycia, typów
oraz granic; nie oznacza jeszcze przyjęcia metody produkcyjnej.

Uzasadnienie kandydatów: [przegląd STM/AFM](research-stm-afm-unsupervised-domain-discovery.md)
oraz [przegląd grupowania obiektów](research-domain-discovery-and-object-clustering.md),
uzupełnione o [ML bez własnego treningu](research-training-free-ml-domain-discovery.md).
