# Warunek drugiego kierunku: rzędy molekuł, pasy i wspólna sieć

Data: 2026-10-26. Kontynuacja [issue 19](issues/19-frozen-feature-domains.md),
po [badaniu skali i podparcia ACF](acf-scale-support-trial.md).
Źródło: **`prototype/stmdomains-second-direction`, `f648afe`**, baza `2ccf9ad`.
Dokumentacja: `domains/second-direction-trial`, baza `4241af9`.
Prototyp pozostaje poza gałęzią aplikacji.

**Warunek drugiego kierunku rzeczywiście odrzuca część regularnych rzędów.
Jego usunięcie odzyskuje przypisania, ale dopuszcza też rzędy bez wspólnej
sieci dwuwymiarowej. Badana krzywizna ACF nie rozwiązuje tego kompromisu.**
Żadna z 384 zmienionych konfiguracji detektora nie spełnia wszystkich
dotychczasowych warunków rozwojowych. Issue 19 pozostaje `claimed`, do omówienia.

Podgląd: [samowystarczalny HTML](../../.scratch/second-direction/index.html).
[Wykres PNG](../../.scratch/second-direction/second-direction-comparison.png),
[PDF](../../.scratch/second-direction/second-direction-comparison.pdf),
[tabela CSV](../../.scratch/second-direction/controls.csv),
[manifest](second-direction-manifest.json).

## Pytanie i zakres

W poprzedniej próbie widmowy warunek drugiego kierunku odrzucał około połowy
miejsc w dostępnych wnętrzach TTMAPP. Ta próba zmienia wyłącznie jego
wymagania, przy zachowanych cechach wyglądu, PCA, podziałach HDBSCAN/FH4,
podparciu cech, łączności i regułach minimalnego fragmentu.

Obliczenia obejmują 24 pełne klatki TTMAPP, 204 znane kontrole i **63 nowe
obrazy syntetyczne**. Częściowe referencje istnieją dla 18 klatek; 1678
oznaczeń w ich wnętrzach jest mianownikiem oceny przypisań. To oznaczenia
z kolejnych klatek, nie liczba unikalnych fizycznych molekuł. Obszary poza
referencjami pozostają nieznane, a nie negatywne.

Metody nadal pracują bez przykładów domen, zadanego K i treningu sieci.
Ramki TTMAPP służą dopiero ocenie zamrożonych wyników. Progi wykorzystują
znane syntetyczne kontrole negatywne, nie ręczne domeny. Nie przeliczano
cech FCN/DINO ani grupowania; nowe obrazy sprawdzają tylko kryterium
porządku z łącznością, bez dopasowania dla nich nowych grup wyglądu.

## Protokół zapisany przed obliczeniami

Promienie 24, 36 i 48 pikseli odniesienia; ACF `windowed` oraz `overlap`;
co najmniej 50% zmierzonego okna i dodatnia energia. Pięć wariantów:

| Wariant | Drugi kierunek | Próg ACF |
| --- | --- | --- |
| `original` | dotychczasowy wskaźnik ≥0.25 | zachowany |
| `soft10` | wskaźnik ≥0.10 | zachowany |
| `off_fixed` | wyłączony | zachowany |
| `off_recalibrated` | wyłączony | ta sama reguła kalibracji, bez filtrowania kierunku |
| `peak_curvature` | krzywizna obu maksimów ACF | zachowany, dodatkowy próg krzywizny |

30 kryteriów × 18 zapisanych podziałów/kontroli daje **540 konfiguracji**
na starym zestawie: 108 dokładnych powtórzeń poprzednich ustawień,
384 zmienione konfiguracje detektorów oraz 48 zmienionych kontroli limitu
przypisań. Na nowych obrazach stosujemy 60 konfiguracji samego kryterium
i łączności, na siatce oraz przy centrach. Ten limit nie jest detektorem
domen: zakłada jedną grupę wyglądu, aby ujawnić ograniczenia kryterium.

Krzywizna to eksperymentalny pomiar własny, nie zwalidowana metoda.
Dla **tej samej** wybranej wcześniej pary niekolinearnych maksimów ACF
liczymy najmniejszą wartość własną ujemnej macierzy drugich pochodnych,
różnicami centralnymi co 2 px. Wynik jest przemnożony przez 2² i pozostaje
w jednostkach ACF; przyjmujemy słabsze z obu maksimów i obcinamy do zera.
Grzbiet powinien mieć małą krzywiznę wzdłuż grzbietu, a izolowane maksimum
— dodatnią w obu kierunkach. Nie zmieniamy wyboru pary, opóźnień 6–24 px,
24 kandydatów, filtra maksimów 5 ani warunku niekolinearności.

Kalibracja używa tych samych 18 negatywnych obrazów rozwojowych co wcześniej,
wyłącznie próbek siatki. Nowy próg ACF to kwantyl 0.999 wszystkich wspartych
miejsc; próg krzywizny — kwantyl 0.999 wśród miejsc przechodzących zachowaną
ACF i energię. Nowe obrazy, dodatnie kontrole i TTMAPP nie dobierają progów.
W `windowed` do kalibracji krzywizny pozostają tylko **cztery miejsca**
dla każdego promienia; to istotne ograniczenie tej reguły.

## Nowe obrazy: co faktycznie sprawdzają

21 przypadków × ziarna 4101–4103, obrazy 192×192. Przy obrocie 0° i 27°:

- regularne rzędy o tej samej fazie i rozstawie 12 px, przy modulacji
  molekuł 1.0, 0.35 i 0.10;
- rzędy z niezależnym losowym przesunięciem fazy, przy tych samych
  trzech modulacjach, z zachowanymi oznaczeniami molekuł;
- regularne rzędy z przyciemnieniem co drugiego rzędu do 20%;
- same pasy, bez molekuł;
- dwa regularne płaty z pionową przerwą 36 px, modulacje 1.0 i 0.35.

Dodatkowo czysty szum. Zachowano ten sam szum przy zmianach modulacji;
kontrolne etykiety zapisano osobno. Rzędy z niezależną fazą są negatywne
**dla wspólnej sieci 2D**, choć każdy rząd pozostaje okresowy. Mogą też
zawierać lokalne przypadkowe zgodności, więc nie utożsamiamy każdego
dodatniego lokalnego pomiaru z błędem fizycznym. Złożenie niemal całego
takiego obrazu w jeden uporządkowany płat jest jednak wyraźną porażką
sprawdzanej interpretacji. Słaba modulacja bada granicę widoczności;
teoretyczne istnienie punktów nie gwarantuje ich rozpoznawalności w obrazie.

## Wynik na TTMAPP

Sama ocena porządku i łączność, siatka, `windowed`, promień 24:

| Wariant | Przypisane oznaczenia / 1678 | Udział | BLACK / RED / YELLOW |
| --- | ---: | ---: | --- |
| Dotychczasowy | 98 | 5.8% | 98 / 0 / 0 |
| Próg 0.10 | 592 | 35.3% | 592 / 0 / 0 |
| Wyłączony | 636 | 37.9% | 636 / 0 / 0 |
| Wyłączony, nowy próg ACF | 637 | 38.0% | 637 / 0 / 0 |
| Krzywizna ACF | 0 | 0.0% | 0 / 0 / 0 |

Znane miejsca siatki przechodzące bramkę rosną z **165/1916 do 724/1916**
po wyłączeniu warunku przy stałym progu ACF. Jest to bezpośredni efekt
tego warunku, nie zmiany cech ani dopasowania do ramek. Przy centrach
limit przypisań rośnie z 34 do 570/1678. Nadal odzyskujemy wyłącznie BLACK.

Dla FCN i DINO na siatce z HDBSCAN końcowe przypisania wynoszą również
636/1678; graf FH4 daje odpowiednio 631 i 628. Nie jest to poprawa cech
sieci: zmieniono wspólną bramkę. DINO/centra z zachowanym HDBSCAN nadal
odmawia wszystkim, niezależnie od rozluźnienia bramki.

Przy r48 i `windowed` wyłączenie warunku zwiększa limit z 430 do
**1313/1678** (78.2%; BLACK/RED/YELLOW: 1132/62/119). Ten promień nadal
łączy rozłączne płaty: 96/96 ocenianych miejsc pustej przerwy zostaje
przypisanych, a dwa płaty tworzą jeden fragment we wszystkich trzech
ziarnach. Także wariant krzywizny nie naprawia tej przerwy. Duża liczba
przypisań nie dowodzi poprawnych domen ani poprawnej powierzchni.

## Nowe kontrole ujawniają koszt odzyskania rzędów

Wyniki poniżej: siatka, `windowed`, r24, łącznie trzy nowe ziarna.

| Przypadek | Dotychczasowy | Próg 0.10 | Wyłączony | Krzywizna |
| --- | ---: | ---: | ---: | ---: |
| Spójne rzędy 0°, modulacja 1: przypisane molekuły | 78.5% | 98.8% | 98.8% | 95.2% |
| Spójne rzędy 0°, modulacja 0.35 | 0% | 0% | 98.8% | 0% |
| Spójne rzędy 27°, modulacja 0.35 | 2.3% | 3.1% | 85.9% | 0% |
| Losowe fazy rzędów 0°, modulacja 1: przypisane miejsca / 768 | 0 | 756 | 756 | 0 |
| Losowe fazy rzędów 0°, modulacja 0.35: miejsca / 768 | 0 | 0 | 745 | 0 |
| Losowe fazy rzędów 27°, modulacja 1: miejsca / 768 | 16 | 640 | 640 | 61 |

W słabszych rzędach wyłączenie warunku przywraca wysokie przypisanie,
ale w rzędach z losową fazą łączy **98.4% miejsc w jedną sieć** dla każdego
ziarna (modulacja 1, 0°). Krzywizna nie jest uniwersalnym rozwiązaniem:
odrzuca regularne słabsze rzędy i TTMAPP, a obrócone losowe rzędy nadal
dają 61/768 przypisanych miejsc oraz 1/3/1 fragmentów.

Przy modulacji 0.10 i naprzemiennie przyciemnionych rzędach żaden z pięciu
wariantów r24/`windowed` nie daje końcowych przypisań, dla obu orientacji.
Przy r24 pustą przerwę nowych dwupłatowych kontroli zachowano; odzyskanie
słabszych rzędów nie wymagało tutaj powiększania okna do r48.

`windowed` w r24 odrzuca same pasy i czysty szum także bez warunku
drugiego kierunku. **Nie wystarcza więc test „sieć kontra same pasy”**:
niezależne fazy rzędów wykazały błąd mimo dobrego wyniku na pasach.
Wariant `overlap` bez warunku i przy starym progu dodatkowo przyjmuje
756/768 miejsc prostych pasów i 749/768 obróconych. Ponowna kalibracja
podnosi jego próg ACF z 0.5124 do 0.9871, odrzuca pasy, ale daje zero
przypisań we wnętrzach TTMAPP. Globalny próg nie usuwa tego kompromisu.

## Zachowane podziały nadal wymagają pracy

**0/384 zmienionych konfiguracji detektora** przechodzi cały wcześniej
zapisany zestaw warunków; także żaden ze 108 powtórzonych wariantów
i 48 zmienionych limitów nie spełnia całego zestawu. Limity służą
diagnostyce i nie podlegają przyjęciu jako detektor.

Przykładowo FCN/siatka, r24/`windowed`, wyłączony drugi kierunek:
HDBSCAN dzieli pojedynczą sieć na 2/2/2 fragmenty i scala obrót 8°.
FH4 zmniejsza udział scaleń par przy 8° do 1.1%, lecz pojedynczą sieć
dzieli na 5/3/3 fragmenty. Wartości podziałów/scaleń są warunkowe wobec
przypisanych par; komplet danych wraz z przypisaniem jest w CSV/JSON.
Sama naprawa bramki nie zapewni prawidłowych granic i typów.

## Weryfikacja i odtworzenie

- 130 sprawdzeń krzywizny na analitycznych maksimach, grzbietach,
  siodłach i płaszczyznach, także obróconych; błąd do 6.67e-16.
- 63 dokładne odtworzenia nowych obrazów; **2736/2736** zachowanych
  tablic ACF odtworzonych bez różnicy.
- **24624/24624** wyników początkowych zgodnych w tablicach bramki,
  fragmentów i przypisań molekuł.
- 528 tablic siatki i 6480 par wyników identycznych przy brakach samych
  oznaczeń. Nie powtarzano badania początku siatki.
- Ponowiono wszystkie **291 plików / 126900 wyników konfiguracji**
  w tymczasowym drzewie bez linków do referencji, z blokadą odczytów
  ścieżek `evaluation`/`reference` przez Python. Identyczne hashe zawartości.
  To kontrola predykcji; nie ponowna ekstrakcja wszystkich cech.
- 291 nowych i 228 poprzednich plików predykcji zgodnych z hashami;
  parametry, protokół i kod analizy niezmienione po ocenie.
- **170 kontroli QtWebEngine**, 79 obrazów i 540 ustawień dostępnych
  w podglądzie; brak błędów JS i przepełnienia poziomego. Obejrzano
  podgląd oraz wykres. Sprawdzono składnię Python/Bash i dokumentację.

CPU, cztery procesy, po jednym wątku BLAS/OpenMP. Pomiary ACF i krzywizny
440.43 s, predykcje 14.87 s, ocena 24.87 s, powtórzenie bez referencji
15.42 s. Największy RSS pojedynczego procesu przygotowania 115892 KiB
(około 113 MiB); łącznego szczytu nie mierzono. Bez GPU, nowych pakietów
i pobierania wag. Wersje oraz hashe w manifeście.

Artefakty: **732 pliki / 414795835 B**, wszystkie kopie zgodne SHA-256
(liczba nie obejmuje dopisanego potwierdzenia kopii). Względne linki
wymagają poprzednich katalogów ACF/grafu i ich zależności; HTML, PNG,
PDF oraz CSV można otwierać osobno. Runner na gałęzi prototypu:
`bash stmdomains/prototypes/run_second_direction.sh`. Etapy wykonano
osobno, wrapper sprawdzono składniowo. Nie testowano natywnej aplikacji
ani pełnych 268 klatek; nie wyznaczano powierzchni i katalogu typów.

Znane ziarna i częściowe referencje pozostają diagnozą rozwojową.
Nowe ziarna są świeżą kontrolą syntetyczną; nie stanowią niezależnej
walidacji na pomiarach STM. Nie stroiliśmy parametrów po tych wynikach.

## Następny krok

Proponowana kolejna ograniczona próba: **spójność przesunięć między
rzędami i lokalne potwierdzenie sieci**, zamiast kolejnego obniżenia
jednego progu. Z obrazu można wyznaczyć kandydatów wektorów powtarzalności,
a następnie sprawdzić ich zgodność w oddzielnych częściach okna oraz
obecność wspierającego sygnału przy ocenianym miejscu. Kandydaci mają
wynikać z danych, bez zadanej symetrii, wzorca domeny i liczby grup.
To hipoteza eksperymentu, nie potwierdzona już metoda.

Kontrole tej próby powinny wymagać jednocześnie odzyskania słabszych
spójnych rzędów, odmowy na losowych fazach/pasach i zachowania pustej
przerwy. Obecne 63 obrazy stają się materiałem rozwojowym; kolejne
ustalenia trzeba sprawdzić na nowych realizacjach. Podziały wyglądu
pozostają zamrożone dla rozdzielenia przyczyn, a poprawność granic
oceniana osobno. Przygotowanie treningu 20 może pozostać niezależnym
kierunkiem, ale nowa reprezentacja nie naprawia automatycznie tej bramki.
Następną próbę wykonano 2026-10-28:
[zgodność przesunięć i lokalny sygnał](translation-consistency-trial.md).
Treningu 20–23 ani odbioru 13 nie rozpoczęto.
