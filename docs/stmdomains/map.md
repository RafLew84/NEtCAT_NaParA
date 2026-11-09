# STM Domains — etap 1: działający szkielet

**2026-11-09 — wykonano SD-V4-23a: scalanie i dzielenie klas (`5ca2e6f`, poprawka `5de0d7f`).**
**Edytuj domeny → Klasy ręczne… → Scal klasy… / Podziel klasę…**:
wybór źródeł i celu, jawny zakres klatek, utrwalone warianty/lista klas,
podgląd liczników i obrazu oraz wspólne Cofnij/Ponów. Scalenie zachowuje
osobne domeny; podział części domeny wydziela ją zgodnie z 22/23.
[Obsługa, gotowy przykład i sprawdzenia](implementation/interactive-v04/acceptance-23a.md).
Próba natywnego GUI/netcat: kontrola 9/7, podziały 5/4 i 1/8, wariant bez
modelu oraz TTMAPP259–260 PASS. Przegląd: Standards 0; Spec 1 uwaga poprawiona, 0 otwartych.
Pełna regresja: **624 testy PASS / 280,46 s**, mypy **119 modułów PASS**.
**Odbiór ręczny użytkownika 23a otwarty**. Korekty tylko w sesji;
następny **24 → 25 → 26**, 19–20 odłożone. Poniżej historia wcześniejszych etapów.

ID: stmdomains-map
Labels: wayfinder:map
Status: resolved
Assignee:

## Destination

Uzgodniona specyfikacja szkieletu STM Domains, który otwiera istniejący zapis
z oznaczeniami molekuł, doczytuje obrazy i pozwala sprawdzić je na kolejnych
klatkach. Mapa kończy się przygotowaniem implementacji i kryteriów odbioru
tego zakresu, bez oczekiwania na wybór metod analizy ani formatu wyników.

## Notes

**2026-11-09 — poprawka nazewnictwa po zgłoszeniu do 23 (`8d4ec04`).**
Klasy: `A, B, C…`; osobne domeny klasy D: `D1, D2…`.
Podpisy na obrazie zależą od widoku Klasy/Domeny i zgadzają się z legendą.
[Reguły i test ręczny](implementation/interactive-v04/acceptance-23.md#poprawka-podpisów-po-zgłoszeniu-użytkownika--2026-11-09).
Odbiór 23 potwierdzony 2026-11-09 dla wersji `14f39d6` („testy manualne ok”); następny 23a, potem 24 → 25 → 26.

**2026-11-09 — wykonano SD-V4-23: ręczne klasy (`94d5a94`, poprawka `b11d09a`).**
**Edytuj domeny → Klasy ręczne…**: nowa/pusta klasa, nazwa/kolor,
przypisanie molekuł lub całych domen i usuwanie pustych klas ręcznych.
Częściowa zmiana klasy pokazuje atomowy podział domeny; klasa bez domeny
nie tworzy obszaru. Wersjonowane listy współdzielą metadane tylko w swoim
katalogu; przypisania pozostają na bieżącej klatce, model/K bez zmian.
[Obsługa i test ręczny](implementation/interactive-v04/acceptance-23.md), [przegląd](implementation/interactive-v04/review-23.md).
GUI X11/netcat na kontrolach oraz TTMAPP259–260 PASS. Cofnij/Ponów,
porównanie oryginału i ochrona pracy z 21–22 pozostają aktywne.
**596 testów PASS**, mypy 114 modułów PASS, Standards/Spec 0 otwartych uwag.
**Odbiór ręczny użytkownika 23 potwierdzony 2026-11-09 dla wersji `14f39d6` („testy manualne ok”)**; odbiór 22 potwierdzony.
Korekty tylko w sesji, zapis/eksport w 24/25. Następny: **23a — scalanie
i dzielenie klas**, potem 24 → 25 → 26; 19–20 odłożone.
Poniżej historia wcześniejszych prac.

**2026-11-09 — wykonano SD-V4-22 (`0910c97`, poprawka `62644eb`): podział i scalanie domen.**
W **Edytuj domeny** dostępne są **Podziel domenę** i **Połącz domeny**,
z podglądem, wyborem docelowego ID, pełną listą członków i Cofnij/Ponów.
Podział zachowuje klasę; scalenie różnych klas jawnie daje klasę nieustaloną.
Obszary dziedziczą istniejące wsparcie; scalenie nie dorysowuje mostów.
[Obsługa, geometria i test ręczny](implementation/interactive-v04/acceptance-22.md),
[przegląd](implementation/interactive-v04/review-22.md). Natywne GUI X11/netcat na kontrolach
oraz TTMAPP259–260 PASS; po podziale/scaleniu maska wraca dokładnie do źródła.
**586 testów PASS**, mypy 112 modułów PASS, Standards/Spec 0 otwartych uwag.
**Odbiór ręczny użytkownika 22 potwierdzony 2026-11-09 dla wersji `f37714f` („testy manualne ok”)**; odbiór 21 potwierdzony.
Korekty nadal tylko w sesji, zapis/eksport w 24/25. Następny: **23 — ręczne
klasy**, potem 23a → 24 → 25 → 26; 19–20 odłożone.
Poniżej historia wcześniejszych prac.

**2026-11-05 — wykonano SD-V4-21, Panel A (`a61e1b2`, poprawki `47bafe0`).**
**Edytuj domeny** otwiera panel, **Zakończ edycję** go chowa, pozostawiając
korekty widoczne. Kliknięcia/lasso, podgląd, nowe domeny, dodawanie/usuwanie
członków, jawne przenoszenie i chronologiczne Cofnij/Ponów między klatkami.
Osobne warianty zachowują automat; korekty tylko w sesji, zapis/eksport
czeka na 24/25. [Raport i test ręczny](implementation/interactive-v04/acceptance-21.md),
[przegląd](implementation/interactive-v04/review-21.md). **572 testy PASS**, mypy 110 modułów PASS,
natywne GUI X11/netcat na TTMAPP PASS. **Odbiór ręczny użytkownika 21 potwierdzony 2026-11-05 dla wersji `e58393c` („testy manualne ok”).**
Następny rekomendowany: **22 — dzielenie i scalanie domen**; 19–20 odłożone.
Poniżej historia wcześniejszych prac.

**2026-11-05 — [prototyp UI ręcznej edycji domen, ticket 21](implementation/interactive-v04/prototype-21-layouts.md).**
A — panel boczny (rekomendacja autora), B — pasek pod obrazem,
C — karta na obrazie. Później użytkownik wybrał A i zlecił 21; wykonanie opisano powyżej.
Kod demo: `prototype/stmdomains-manual-domains-ui`, `f2db201`.
Odbiór 18 pozostaje potwierdzony; następny ticket 21, 19–20 odłożone.

**2026-11-04 — Wykonano SD-V4-18, wybrany Panel A (`85a90e0`, poprawki `d7ea7b2`).**
Analiza → Analiza… → freud: tolerancja, sąsiedzi, zasięg i obrót; bez K.
Przełącznik Bazowa / Geometria / freud, Klasy/Domeny i podgląd sąsiadów.
[Raport i test ręczny](implementation/interactive-v04/acceptance-18.md),
[protokół](implementation/interactive-v04/experiment-18.md). W netcat dodano freud-analysis 3.6.1.
TTMAPP259–266: 0–25 przypisań do domen; brak wykazanej poprawy detekcji.
557 testów pełnej regresji PASS, 28 testów po poprawkach PASS, mypy 105 modułów PASS.
Natywne GUI X11 PASS; **odbiór ręczny użytkownika 18 potwierdzony 2026-11-05 dla wersji `f2e0cbc` („testy manualne ok”)**.
Dalsza dostępna ścieżka: 21 → 22 → 23 → 23a → 24 → 25 → 26;
19–20 nadal odłożone. Poniżej historia wcześniejszych prac.

**2026-11-04 — użytkownik zlecił dopisanie próby Fedkiwa:**
[SD-V4-26](implementation/interactive-v04/26-compare-fedkiw-level-set.md)
jest ostatni w planie, po 25; status `ready-for-agent`, zależności 17, 13 i 14.
Porównanie Geometria / Level set na tych samych cechach obejmuje przypisania
molekuł, obszary domen, ustawienia oraz test ręczny w UI. Bez implementacji
i nowych prób w tej zmianie. Następny rekomendowany ticket nadal 18.

**2026-11-04 — przegląd Fedkiwa po odbiorze SD-V4-17:**
[Notatka badawcza](research-fedkiw-after-ticket-17.md) rozróżnia level set,
hybrydę Gibou–Fedkiwa i dawną próbę Chan–Vese do pokrycia. Obecny program
nie używa tej hybrydy; w chwili przeglądu plan UI nie miał ticketu level set.
18 nadal dotyczy biblioteki freud. Zalecenie ograniczonego porównania
na tych samych cechach jest propozycją, bez dodawania ticketów ani zmiany
kolejności. Odbiór 17 pozostaje potwierdzony.

**Wykonano SD-V4-17 — domeny geometryczne, wybrany Panel A (`25252b2`, poprawki `4c3f3c8`).**
**Analiza → Analiza… → Metoda domen → Geometria**: kąt, rozstaw,
koherencja i wsparcie w bieżącej klatce; bez dopasowania klas.
Przełącznik **Bazowa / Geometria** nad obrazem zachowuje wynik i zoom.
Zapis/eksport obejmuje jeden wybrany wynik, typ pozostaje nieznany.
[Raport i test ręczny](implementation/interactive-v04/acceptance-17.md),
[protokół porównania](implementation/interactive-v04/experiment-17.md),
[przegląd](implementation/interactive-v04/review-17.md).
TTMAPP259–266: geometria bazowa 32–41 przypisań i 1 domena na klatkę;
bez referencji nie oznacza to poprawy. Kontrole wykazały nadmierne
podziały i nierozstrzygnięty skok fazy. Metoda pozostaje eksperymentalna.
**543 testy PASS**, mypy 109 modułów PASS, natywne GUI X11 PASS,
Standards/Spec 0 otwartych uwag; kod maks. 821 linii.
**Odbiór ręczny użytkownika 17 potwierdzony 2026-11-04 dla wersji `b58e69d` („testy manualn ok”).** Następny rekomendowany ticket: **18**;
21 (edycja ręczna) jest również dostępny po swoich zależnościach.
Poniżej historia wcześniejszych etapów.

**2026-11-04 — prototyp UI ticketu 17:** A — wspólne okno Analiza,
B — dwa wyniki obok siebie, C — stały panel ustawień.
[Uruchomienie i źródło](implementation/interactive-v04/prototype-17-layouts.md).
Gałąź `prototype/stmdomains-domain-method-ui`, commit `621ce71`.
Później użytkownik wybrał A i zlecił implementację 17 (podsumowanie powyżej).
Nowe domeny historycznego prototypu były demonstracyjne.
Odbiór użytkownika 16 pozostaje potwierdzony.

**Wykonano SD-V4-16 — geometria w wybranej karcie C (`c4b6c70`, poprawki `009f38f`, `97988c2`).**
**Analiza → Geometria… → Pomierz geometrię** oblicza bieżącą klatkę w tle.
Karta pokazuje kierunki rzędów, rozstaw, wsparcie i stabilność, a zakładka
Domena — podsumowanie osiowe. Nakładka respektuje X/Y i raw/aligned;
pomiary nie zmieniają klas/domen. Dane są sesyjne, poza zapisem/eksportem
13/14. [Raport i test ręczny](implementation/interactive-v04/acceptance-16.md),
[protokół](implementation/interactive-v04/geometry-method-v1.md),
[przegląd](implementation/interactive-v04/review-16.md).
**530 testów PASS**, mypy 101 modułów PASS, natywne GUI X11 na kontrolach
i TTMAPP 259–266 PASS; maksymalny zmieniony kod/test 736 linii.
Standards/Spec: 0 otwartych uwag. Status `done`, **odbiór ręczny użytkownika
16 potwierdzony 2026-11-04 dla wersji `420f196` („testy manualne ok”)**. Następny rekomendowany: **17 — domeny według tolerancji**;
18 jest niezależnie dostępny. Poniżej historia poprzednich etapów.

**Wykonano SD-V4-15 — opis otoczenia i bariery (`1b0c1de`, poprawki `9fe24a6`, `9bf767a`).**
**Analiza → Analiza… → Zaawansowane**: sigma, histogram, zakres par i PCA,
progi/długości/nachylenie/poszerzenie barier oraz pomarańczowy podgląd.
Zmiana opisu wymaga nowego dopasowania; **Użyj istniejących klas** zachowuje
model przy zmianie barier. Projekt i PNG zachowują nową diagnostykę.
[Raport i test ręczny](implementation/interactive-v04/acceptance-15.md), [znaczenie parametrów](implementation/interactive-v04/advanced-settings.md),
[przegląd](implementation/interactive-v04/review-15.md). GUI X11 TTMAPP i kontrola syntetyczna PASS;
przywrócenie bazowych parametrów odtwarza dokładnie katalog, przypisania
oraz maskę. **510 testów PASS**, mypy 92 modułów PASS; maks. 474 linie
w 32 plikach kodu/testów. Standards/Spec: 0 otwartych uwag.
Status `done`; **odbiór ręczny użytkownika 15 potwierdzony 2026-11-03 dla wersji `f129ac2` („testy manualne ok”)**.
Następny rekomendowany ticket: **16 — kierunek, rozstaw i jakość geometrii**.
Poniżej historia wcześniejszych etapów.

**Wykonano SD-V4-14 — eksport PNG i CSV (`a20e14b`, poprawka `361a7d0`).**
**Plik → Eksportuj PNG/CSV…**: wybrany wynik, klatka lub zakres, pełny obraz
albo widoczny wycinek, aktualne Klasy/Domeny, gamma i warstwy. CSV zachowuje
ID, przypisania, powody odmów i mianowniki; brak analizy pozostaje brakiem.
Eksport nie uruchamia obliczeń. Nowy katalog zawiera opis i metadane;
postęp/anulowanie oraz odmowa nadpisania chronią wcześniejsze pliki.
[Raport i test ręczny](implementation/interactive-v04/acceptance-14.md), [format eksportu](implementation/interactive-v04/export-format-v1.md).
GUI X11 TTMAPP i kontrola wyniku zerowego PASS; kontrola typów 88 plików
PASS, Standards/Spec 0 otwartych uwag; 12 plików kodu/testów do 691 linii.
**499 testów PASS**. Status `done`; **odbiór ręczny użytkownika 14 potwierdzony 2026-11-03 dla wersji `4e9f1d9` („testy manualne ok”)**.
Następny rekomendowany ticket: **15 — opis otoczenia i bariery obrazu**.
Poniżej historia wcześniejszych etapów.

**Wykonano SD-V4-13 — zapis projektu (`4f40c28`, poprawki `1c9c221`).**
**Plik → Zapisz projekt… / Zapisz projekt jako…** zapisuje jeden plik
`.stmdomains`: cały MPP, oznaczenia, geometria, widok, szkic i jeden wybrany
przebieg lub brak analizy. Otwieranie odtwarza wynik bez źródeł i obliczeń.
Obsługiwane są wyniki częściowe, osobny wybór ostatniej odmowy i poprzedniego
wyniku, kontrola integralności, anulowanie oraz ochrona niezapisanej pracy.
[Raport i test ręczny](implementation/interactive-v04/acceptance-13.md), [format 1](implementation/interactive-v04/project-format-v1.md).
GUI X11 na TTMAPP: identyczne 105/312 i 5 domen po odtworzeniu, także dalsza
analiza z zapisanym katalogiem bez dopasowania. **490 testów PASS**, mypy
82 pliki PASS, Standards/Spec 0 otwartych uwag; maks. 661 linii. Status `done`;
**odbiór ręczny użytkownika 13 potwierdzony 2026-11-03 dla wersji `21fd906` („testy manualne ok”)**. Następny rekomendowany ticket:
**14 — eksport PNG i CSV**. Poniżej zachowano historię wcześniejszych etapów.

**Wykonano SD-V4-12 — Auto (`274f348`, poprawka `88006c1`).**
**Analiza → Analiza… → Klasy**: ręczne K albo Auto, maksimum 1–8,
jawne uzasadnienie i ranking bieżących danych. Jedna klatka, zakres lub
seria używa pełnego szkicu parametrów. Odmowa nie zastępuje wcześniejszego
kompletnego wyniku; istniejący katalog zachowuje decyzję Auto.
Kontrole: K1 dla jednej sieci, K2 dla dwóch orientacji, odmowa dla szumu
oraz słabych/pustych danych. TTMAPP 259 i 259–268: **nierozstrzygnięte**
według reguły zapisanej przed próbą, bez zastępowania ręcznym K5.
[Raport i test ręczny](implementation/interactive-v04/acceptance-12.md),
[reguła wyboru](implementation/interactive-v04/auto-class-count-rule.md).
Sprawdzenia: **476 testów PASS**, mypy 70 plików PASS, GUI X11 PASS;
Standards/Spec: 0 otwartych uwag; maks. zmieniony kod/test 302 linie.
Status `done`; **odbiór ręczny użytkownika 12 potwierdzony 2026-11-03 dla wersji `7edd8de` („testy manualne ok”)**.
Następny rekomendowany ticket: **13 — zapis i otwarcie projektu**.
Plan ma 26 ticketów; 23a pozostaje po 23. Poniżej historia wcześniejszych etapów.

**Rozszerzenie planu — 2026-11-03:** dodano
[SD-V4-23a — scalanie i dzielenie klas](implementation/interactive-v04/23a-split-merge-classes.md).
Zależność 23; nowe operacje z podglądem, zakresem klatek i Cofnij/Ponów.
Ścieżka ręczna **21 → 22 → 23 → 23a → 24 → 25**. 24/25 wymagają 23a,
żeby zapisywać/eksportować także te korekty. Plan ma 26 ticketów;
23a `ready-for-agent`, bez implementacji. Następny etap główny nadal 12;
odbiór ręczny użytkownika 11 potwierdzony 2026-11-03 dla wersji `76c8284`. Poniżej historia poprzednich etapów.

**Wykonano SD-V4-11 — 2026-11-03 (`d18048b`):**
[Wspólne okno analizy](implementation/interactive-v04/11-unified-analysis-window.md)
zastępuje pięć formularzy. **Analiza → Analiza…**: Zakres, Klasy, Porządek,
Domeny, wspólny szkic i kompletny przebieg klatki/serii. Są porównanie,
jawne kopiowanie, stany klatek i anulowanie. [Raport i test ręczny](implementation/interactive-v04/acceptance-11.md).
**456 testów PASS**, GUI X11/mypy PASS, Standards 0 / Spec 0;
status `done`; odbiór ręczny użytkownika potwierdzony 2026-11-03 dla wersji `76c8284` („testy manualne 11 ok”).
Plan ma 25 ticketów: 01–03, 05, 05a i 06–11 wykonane, następny **12 — Auto**.
**12 pozostaje niewykonany.** Brak nowej metody, instalacji i zmian wspólnych.
Poniżej historia wykonanych etapów i ich ówczesnych interfejsów/rekomendacji.

**Wykonano SD-V4-10 — 2026-11-03 (`aa7e039`):**
**Analiza → Test porządku…**, pięć parametrów, kalibracja zgodna z otoczeniem,
zamrożony katalog, porównanie i anulowanie. Zastosowany porządek wpływa
na dobór próbek przy jawnym ponownym odkrywaniu klas, także w serii.
[Ticket](implementation/interactive-v04/10-tune-order-test.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-10.md).
**449 testów PASS**, GUI X11 na TTMAPP i kontrolach PASS; mypy 67 modułów PASS, maks. 566 linii,
Standards 0 / Spec 0. Status `done`; **ręczny odbiór użytkownika 10
potwierdzony 2026-11-03** dla wersji `4b55727` („testy manualne ok”).
Plan ma 24 tickety: 01–03, 05, 05a i 06–10 wykonane; następny **12 — Auto**.

**Wykonano SD-V4-09 — 2026-11-03 (`494ab9d`):** menu
**Analiza → Akceptacja klasy…** pozwala regulować margines i promień,
przeliczać klatkę przy zachowanym katalogu oraz porównywać wyniki.
Szczegóły molekuły rozdzielają akceptację, porządek i końcową domenę;
K1 pomija margines. [Ticket](implementation/interactive-v04/09-tune-class-acceptance.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-09.md).
427 testów PASS, mypy 63 moduły PASS; 15 plików kodu/testów do 544 linii.
Rzeczywiste GUI X11 PASS, Standards 0 / Spec 0. Status `done`, **ręczny
odbiór użytkownika 09 potwierdzony 2026-11-03** dla `9dd934d`
(„testy manualne ok”). Późniejszy komunikat `inotify` zdiagnozowano jako
limit obserwacji systemowych; użytkownik potwierdził normalne zamknięcie.
[Diagnoza](implementation/interactive-v04/acceptance-09.md#komunikat-inotify-po-odbiorze).
Plan ma 24 tickety; 01–03, 05, 05a i 06–09
wykonane. Następny rekomendowany **12 — Auto**. Poniżej historia.

**Rozszerzenie planu — 2026-11-03, decyzja użytkownika:** dodano
[SD-V4-21–25](implementation/interactive-v04/README.md#edycja-ręczna-klas-i-domen):
tworzenie i rozszerzanie domen, podział/scalanie, ręczne klasy, zapis historii
korekt oraz eksport. Każdy etap ma scenariusz testu ręcznego w aplikacji.
Plan ma **24 tickety**; nowe zadania `ready-for-agent` po zależnościach,
bez rozpoczęcia implementacji. 21 wymaga ukończonego 05a; dalej 22 → 23,
24 z dodatkową zależnością 13 i 25 z 14. 25 nie wymaga 24.
Następny rekomendowany ticket głównej ścieżki pozostaje **12 — Auto**;
19–20 nadal odroczone. Korekty nie trenują modelu ani nie propagują się
automatycznie na pozostałe klatki. Poniżej historia wcześniejszych etapów.

**Wykonano SD-V4-08 — 2026-11-03 (`1c39ae2`, poprawka `46c274f`):**
menu **Analiza → Analiza serii…** łączy zakres, klasy i parametry domen;
oblicza domeny każdej wybranej klatki ze wspólnym katalogiem. Postęp,
statusy klatek i częściowe anulowanie działają podczas nawigacji.
[Ticket](implementation/interactive-v04/08-analyze-series.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-08.md).
409 testów PASS, mypy 59 modułów PASS; 14 plików kodu/testów do 527 linii.
Rzeczywiste GUI: 268 klatek TTMAPP bez błędów. **Odbiór ręczny użytkownika 08
potwierdzony 2026-11-03** dla wersji `a3a5316` („testy manualne ok”).
Status `done`; następny rekomendowany **12 — Auto**.
Plan nadal ma 19 ticketów; 01–03, 05, 05a, 06–08 wykonane. Poniżej historia.

**Wykonano SD-V4-07 — 2026-11-02 (`dedd8b8`, poprawki `65e9d2a`):**
menu **Analiza → Klasy i zakres…**, K1–8, lokalne/wspólne dopasowanie
z wybranych danych, wynik bieżącej klatki i porównanie wcześniejszego
katalogu. [Ticket](implementation/interactive-v04/07-fit-shared-classes.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-07.md).
396 testów PASS, mypy 54 moduły PASS, 23 pliki kodu/testów do 469 linii.
GUI X11 sprawdzone przez agenta; **odbiór ręczny użytkownika 07 potwierdzony
2026-11-02** dla wersji `7f79362` („testy manualne ok”).
Status `done`. Plan nadal ma 19 ticketów; następny **08 → 12**.
01–03, 05, 05a, 06 i 07 wykonane. Poniżej historia wcześniejszych etapów.

**Wykonano SD-V4-06 — 2026-11-02 (`98ca8ff`, poprawka `36aea1f`):**
menu **Analiza → Tworzenie domen…** otwiera okno sześciu parametrów.
Przeliczanie zachowuje model klas, porównanie pokazuje dwa ostatnie wyniki
na tej samej klatce, a bazowe ustawienia odtwarzają wynik aplikacji.
[Ticket](implementation/interactive-v04/06-tune-domain-formation.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-06.md).
Status `done`, odbiór ręczny użytkownika potwierdzony 2026-11-02 dla wersji
`a4dcace` („testy manualne ok”). Aktualnie 01–03, 05, 05a
i 06 wykonane; następny **07 → 08 → 12**. Plan nadal ma 19 ticketów.
Poniżej historia wcześniejszych etapów.

**Dodano i wykonano SD-V4-05a — 2026-11-02 (`dfcf392`):** na polecenie
użytkownika do planu wszedł widok obszarów domen z wypełnieniem, obrysami,
numerami i kryciem. Przypisania 05 są zachowane; kontrolka **Obszary…**
działa również bez wejściowych masek molekuł.
[Ticket](implementation/interactive-v04/05a-domain-regions.md),
[raport i test ręczny](implementation/interactive-v04/acceptance-05a.md).
Status `done`, odbiór ręczny 05a potwierdzony przez użytkownika 2026-11-02
dla wersji `617b006`. Aktualny plan ma **19 ticketów**,
następny jest **06 — strojenie tworzenia domen**. Poniżej historia.

**Implementacja SD-V4-05 — 2026-11-02 (`fb37431`):** aplikacja oblicza
lokalne klasy K5 i końcowe domeny bieżącej klatki z MPP i oznaczeń MolTrack,
bez importu modelu/wyniku v0.4. Widok pokazuje kolory, legendę i odmowy;
działają postęp i anulowanie. [Raport i test ręczny](implementation/interactive-v04/acceptance-05.md).
05 ma status `done`; ręczny odbiór użytkownika oczekuje. **Następny ticket:
SD-V4-06 — strojenie tworzenia domen.** 01–03 pozostają odebrane, a historyczny
odbiór całego szkieletu i badawcze 04/13 odrębne. Poniżej historia.

**Zmiana planu — 2026-11-02, decyzja użytkownika:** SD-V4-04 usunięto,
a jego implementację cofnięto do odebranego stanu po 03 (`24625f2`).
Kod v0.4 pozostaje wzorem metody. Aplikacja ma samodzielnie obliczać
klasy i domeny z obrazów i oznaczeń, bez importu paczki/modelu v0.4.
[Aktualny indeks](implementation/interactive-v04/README.md): 05 obliczenia
jednej klatki i podgląd, 06 strojenie, 07 ręczne K i wspólny zakres,
08 analiza serii, 12 Auto. Dawny 11 wchłonięto w 05/07; 04/11 nie mają
już aktywnych ticketów. Numerację pozostałych zachowano.
Po rollbacku: 308 testów PASS, mypy 27 plików PASS. Zaplanowane wtedy
własne obliczenia wdrożono następnie w 05, zgodnie z aktualizacją powyżej.

**Odbiór 03 i poprawka wyjścia — 2026-11-02:** użytkownik potwierdził
ręczne testy wersji `0745e4e`. Następnie zgłoszony crash przy zamykaniu
usunięto przez zakończenie pracy pul przed destrukcją Qt. 25 celowanych
testów PASS, 4 próby procesów na X11 PASS, mypy PASS.
[Raport i test wyjścia](implementation/interactive-v04/acceptance-03.md#poprawka-wyjścia-z-programu).
Użytkownik potwierdził również ręczny odbiór poprawki wyjścia `3dd8b47`:
„testy manualne ok”. Odbiór 03 z poprawkami jest zakończony;
planowany wtedy SD-V4-04 został później wycofany; aktualna kolejność powyżej.

**Poprawka SD-V4-03 po zgłoszeniu użytkownika — 2026-11-02:** usunięto
zmianę geometrii obrazu/nawigacji przy pokazywaniu postępu. 13 celowanych
testów PASS, mypy PASS i 12 przejść TTMAPP w dwóch rozmiarach okna bez skoków.
[Raport i test ręczny poprawki](implementation/interactive-v04/acceptance-03.md#poprawka-po-zgłoszeniu-użytkownika--stabilny-układ-okna).
Użytkownik potwierdził pomyślne ręczne sprawdzenie poprawki `0745e4e`.

**Implementacja SD-V4-03 — 2026-11-02:** wykonano miniatury, odtwarzanie
z pauzą/restartem i gamma. [Raport i test ręczny](implementation/interactive-v04/acceptance-03.md).
300 testów PASS, mypy PASS, pełna seria 268 klatek TTMAPP sprawdzona w GUI.
Odbiór ręczny użytkownika 03 potwierdzono dla `0745e4e`; historyczny odbiór
całego szkieletu pozostaje osobny. Aktualną kolejność nowego planu podano powyżej.

**Implementacja SD-V4-02 — 2026-11-02:** działają oznaczenia molekuł,
maski z regulacją krycia, kliknięcie metadanych i odtworzenie zapisanej
rejestracji w widokach raw/aligned. [Raport i test ręczny](implementation/interactive-v04/acceptance-02.md).
279 testów aplikacji PASS, GUI sprawdzone na TTMAPP; użytkownik potwierdził
ręczny odbiór 02 (`3572b6d`) 2026-11-02. Miniatury, gamma i odtwarzanie
dodano następnie w 03 zgodnie z aktualizacją powyżej.

**Implementacja SD-V4-01 — 2026-11-02:** wykonano pierwszy przekrój
obejmujący import MolTrack/MPP i przeglądanie oryginałów w działającym oknie.
[Raport i odbiór ręczny](implementation/interactive-v04/acceptance-01.md).
Użytkownik potwierdził testy ręczne 01; na jego kolejne zlecenie dodano
suwak pod obrazem do przełączania klatek podczas przeciągania.
Ręczny odbiór dodatku (`ee54638`) również potwierdzono 2026-11-02.
Oznaczenia i wyrównanie dodano następnie w 02, zgodnie z aktualizacją powyżej.

Specyfikację pierwszej mapy zakończono 2026-10-19.
[Zadania budowy i odbioru](implementation/README.md) są gotowe do podjęcia;
zakres budowy jest realizowany przez SD-V4-01–03, ale historyczny odbiór
całego szkieletu nie został zamknięty. Status mapy odnosi się do decyzji,
nie do gotowości programu.

Podział na dwa etapy zatwierdzony przez użytkownika 2026-10-16 zastępuje
wcześniejsze założenie jednej specyfikacji całego programu.

- Etap 1 obejmuje otwarcie zapisu MolTrack, automatyczne doczytanie obrazów
  z możliwością poprawienia ścieżki, nawigację klatek, zoom, gamma,
  oznaczenia molekuł oraz podgląd zapisanej rejestracji.
- Punktem odniesienia jest `data/TTMAPP/detection_full.moltrack.json`.
  Jedna analiza otwiera jeden zapis i należące do niego klatki; dopuszczona
  jest także seria z jedną klatką.
- Szkielet ma działać na rzeczywistych danych. Odbiór sprawdza zgodność obrazu,
  oznaczeń i współrzędnych; samo otwarcie pustego okna nie kończy etapu.
- Rejestrację odtwarzamy z wejścia. Oryginalny rozmiar klatki i zapisane
  przesunięcie wyznaczają pole pomiarowe po wyrównaniu; dopełnienie jest
  oddzielone od pomiaru. Zakres nie obejmuje ponownego liczenia rejestracji.
- Parametry fizyczne przykładowego MPP są zastępcze. Przy braku wiarygodnej
  kalibracji pokazujemy piksele, a przy braku czasu — numery klatek.
- Po uzgodnieniu tej mapy można przygotować i wykonać zadania implementacji
  szkieletu. Otwarte pytania drugiej mapy nie są warunkiem tego kroku.
- Po odbiorze działającego szkieletu przechodzimy do
  [etapu 2: metod i zapisu wyników](map-methods-and-save.md).
  Decyzji drugiego etapu nie rozstrzygamy przy projektowaniu szkieletu.

To mapa decyzji `wayfinder`; aktualizacja planu nie oznacza implementacji.
Przy rozstrzyganiu pytań używamy `grilling` i `domain-modeling`, a przy szkicu UI
`prototype`. [Rejestr pytań](issues/README.md) wskazuje aktywną mapę, zależności
i zasady wyboru ticketu. [Słownik](GLOSSARY.md) definiuje pojęcia.

Przed ustaleniem importu należy przeczytać
[audyt wejścia i orientacji obrazu](research-molecular-orientation.md).
Jego część o pomiarze kąta molekuły jest materiałem na późniejszą pracę.

## Decisions so far

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](issues/01-import-and-geometry.md):
  uzgodniono import MolTrack z jednym MPP, geometrię obu widoków i zachowanie
  przy przeniesionym źródle, brakach oznaczeń oraz słabej rejestracji.

- [Jak przeglądać obrazy i oznaczenia w szkielecie?](issues/07-browsing-and-comparison.md):
  po obejrzeniu prototypu TTMAPP wybrano jeden podgląd z paskiem miniatur,
  przełączaniem oryginał/wyrównany oraz nawigacją z play/pauzą.

- [Jak przekazać szkielet do implementacji i go odebrać?](issues/09-implementation-handoff.md):
  ustalono lokalne moduły, ponowne użycie czytnika, kontrast i pełne odtwarzanie
  klatek; trzy zadania wykonawcze rozdzielają kod, testy oraz odbiór danych i GUI.

## Not yet specified

Nie pozostały znane decyzje blokujące rozpoczęcie implementacji szkieletu.
Nowy przypadek niespójnego wejścia ujawniony podczas budowy wymaga opisania
w zadaniu wykonawczym; jeśli zmienia kontrakt, należy doprecyzować odpowiednią
decyzję albo dodać konkretne pytanie. Nie jest to warunek odkładania obecnej budowy.

## Out of scope

- Wykrywanie wysp i domen sieci, wybór metod, próby jakości, statystyki oraz
  własny zapis/eksport wyników — [osobna mapa etapu 2](map-methods-and-save.md).
- Pomiar orientacji pojedynczej molekuły — odłożony poza oba etapy;
  [wcześniejsze pytanie](issues/03-molecular-orientation.md) zamknięto jako
  odłożone, bez wyboru metody.
- Samodzielny import STP/MPP/S94 jako alternatywa dla zapisu z oznaczeniami.
  Doczytanie obrazu wskazanego w zapisie pozostaje częścią szkieletu.
- Detekcja YOLO, ręczne tworzenie oznaczeń i trenowanie detektora.
- Śledzenie tożsamości molekuł lub konkretnych domen między klatkami.
- Stały ROI dla całej serii oraz rozwój STM Viewer.
