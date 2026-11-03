# STM Domains

Program do wykrywania i analizy domen pól molekularnych na obrazach STM.
Katalog aplikacji: `stmdomains/`.

## Aktualny stan — 2026-11-03

**Dodano do planu SD-V4-21–25 — ręczną edycję klas i domen:**
21 tworzenie/rozszerzanie domen i Cofnij/Ponów, 22 podział/scalanie,
23 własne klasy i przypisania, 24 zapis korekt z historią, 25 eksport CSV/PNG.
[Zakres i kolejność](implementation/interactive-v04/README.md#edycja-ręczna-klas-i-domen).
Każdy ticket ma test ręczny. Plan ma **24 tickety**; nowe zadania są
`ready-for-agent` po zależnościach, **bez rozpoczęcia implementacji**.
21 można wykonać po ukończonym 05a; 24 wymaga również 13, a 25 również 14.
Następny rekomendowany ticket głównej ścieżki pozostaje **12 — Auto**.

**Wykonano SD-V4-08 (`1c39ae2`, poprawka `46c274f`):** menu
**Analiza → Analiza serii…** ma zakładki **Zakres i klasy** oraz
**Tworzenie domen**. Jeden przycisk stosuje wspólne klasy i parametry domen
do całego zakresu lub serii. Można użyć innego zakresu dopasowania albo
katalogu z 07; tabela pokazuje stan każdej klatki, a anulowanie zachowuje
ukończone wyniki. [Raport i test ręczny 08](implementation/interactive-v04/acceptance-08.md).
**409 testów PASS**, mypy 59 modułów PASS, największy zmieniony plik 527 linii.
GUI X11: pełne **268 klatek bez błędów**, nawigacja i częściowe anulowanie.
**Odbiór ręczny użytkownika 08 potwierdzony 2026-11-03** dla wersji
`a3a5316` („testy manualne ok”). **Następny rekomendowany ticket: 12 — Auto.**

**Wykonano SD-V4-07 (`dedd8b8`, poprawki `65e9d2a`):** menu
**Analiza → Klasy i zakres…** udostępnia ręczne K1–8 i dane do dopasowania:
bieżącą klatkę, wybrany zakres lub całą serię. Program tworzy własny katalog,
analizuje bieżącą klatkę i pozwala wrócić do wcześniejszego wyniku z jego
katalogiem. Wspólnego katalogu można użyć na kolejnej klatce bez ponownego
dopasowania. [Raport i test ręczny 07](implementation/interactive-v04/acceptance-07.md).
**396 testów PASS**, mypy 54 moduły PASS, największy zmieniony plik 469 linii.
GUI X11 sprawdzone przez agenta; **odbiór ręczny użytkownika 07 potwierdzony
2026-11-02** dla wersji `7f79362` („testy manualne ok”).
Kolejny etap 08 wykonano zgodnie z wpisem powyżej.

**Wykonano SD-V4-06 (`98ca8ff`, poprawka `36aea1f`):** parametry są
w niemodalnym oknie **Analiza → Tworzenie domen…**. Działa jawne przeliczenie,
porównanie poprzedni/nowy na tej samej klatce oraz przywrócenie bazowych
ustawień, przy zachowanych klasach i ich modelu.
[Raport i instrukcja testu ręcznego 06](implementation/interactive-v04/acceptance-06.md).
**Odbiór ręczny 06 potwierdzony przez użytkownika 2026-11-02** dla wersji
`a4dcace` („testy manualne ok”). Kolejny etap 07 wykonano zgodnie z wpisem powyżej.

**Dodano i wykonano SD-V4-05a (`dfcf392`):** obliczone domeny są widoczne
jako półprzezroczyste obszary z obrysami i numerami. **Obszary…** przy
legendzie pozwala niezależnie przełączać warstwy i regulować krycie.
Można wyłączyć centra i ramki. Dotychczasowe maski wejściowe mają nazwę
**Maski molekuł**; ich brak nie blokuje obszarów domen.
[Raport i test ręczny 05a](implementation/interactive-v04/acceptance-05a.md).
**Odbiór ręczny 05a potwierdzony przez użytkownika 2026-11-02** dla wersji
`617b006` („testy manualn ok”). Plan ma obecnie **24 tickety**, następny rekomendowany **12**.

**Wykonano SD-V4-05 (`fb37431`):** po otwarciu MPP z oznaczeniami MolTrack
przycisk **Analizuj klatkę · K5** oblicza pięć lokalnych klas i końcowe domeny
z bieżących danych. Działają kolory domen/klas, legenda, liczniki, przyczyny
odmów, postęp i anulowanie. Program nie wczytuje modelu ani wyniku v0.4.
[Uruchomienie, wykonane sprawdzenia i test ręczny 05](implementation/interactive-v04/acceptance-05.md).
**Odbiór ręczny użytkownika 05 oczekuje.** W aktualnym planie
01–03, 05, 05a, 06, 07 i 08 mają status `done`,
09–10, 12–18 oraz 21–25 — `ready-for-agent` po spełnieniu zależności, 19–20 — `deferred`.
To wdrożenie eksperymentalnej metody, bez potwierdzenia trafności detektora.

**Wcześniejsza zmiana kierunku na polecenie użytkownika:** usunięto ticket SD-V4-04
i wycofano jego funkcję wczytywania paczek wyników v0.4. Kod oraz testy
aplikacji przywrócono wtedy do odebranego stanu po 03 (`24625f2`), z poprawkami
układu i wyjścia. **308 testów PASS**, mypy **27 plików PASS**; największy
przywrócony plik ma **341 linii**. Lokalnych danych i paczek nie usuwano.

[Aktualny plan](implementation/interactive-v04/README.md) przewiduje
obliczenia od danych: **05 — klasy i domeny jednej klatki**, **06 — strojenie**,
**07 — ręczne K i zakres odkrywania**, **08 — seria**, **12 — Auto**.
V0.4 jest wzorem kodu metody; nie wczytujemy jego modeli ani wyników.
05 obejmuje bazowe K5 i czytelny wynik na molekułach; model powstaje wewnętrznie.
Dawny 11 wchłonięto w 05/07, bez renumeracji pozostałych zadań.
Obliczenia z 05 są już wdrożone zgodnie z aktualizacją powyżej.
Odbiory 01–03 są zachowane; badawcze 04/13 pozostają
otwarte. Wpisy poniżej zachowują historię wcześniejszych etapów i planów.

**Odbiór 03 potwierdzony; poprawiono także błąd wyjścia:** po potwierdzeniu
testów ręcznych wersji `0745e4e` użytkownik zgłosił crash `TaskSignals has
been deleted`. Program kończy teraz pracę obu pul przed usunięciem obiektów Qt.
25 celowanych testów PASS, w tym 4 regresje osobnych procesów; 4 próby X11
PASS, mypy PASS. [Raport i ręczne sprawdzenie zamknięcia](implementation/interactive-v04/acceptance-03.md#poprawka-wyjścia-z-programu).
**Ręczny odbiór poprawki wyjścia `3dd8b47` potwierdzony przez użytkownika
2026-11-02: „testy manualne ok”. SD-V4-03 wraz z obiema poprawkami jest odebrany.**

**Poprawka UI po sprawdzeniu 03:** usunięto skakanie obrazu i nawigacji
podczas pojawiania się postępu ładowania. Miejsce na pasek postępu i Anuluj
pozostaje zarezerwowane. **13 testów okna PASS**, mypy PASS, rzeczywiste GUI
TTMAPP sprawdzone w dwóch rozmiarach okna; **odbiór poprawki `0745e4e`
potwierdzony przez użytkownika**. [Szczegóły i test ręczny](implementation/interactive-v04/acceptance-03.md#poprawka-po-zgłoszeniu-użytkownika--stabilny-układ-okna).

**Wykonano SD-V4-03:** pasek miniatur, play/pauza, od początku, tempa
1/2/5/10/20 kl./s i gamma 0,2–5. Odtwarzanie zachowuje kolejność wszystkich
klatek i zatrzymuje się bez spóźnionego kroku. Zapisany tryb widoku jest
przywracany przy otwarciu. [Uruchomienie i test ręczny 03](implementation/interactive-v04/acceptance-03.md).
W `netcat`: **300 testów PASS**, mypy **27 plików PASS**, największy zmieniony
plik ma **327 linii**. Przegląd kodu zakończony po poprawkach. Rzeczywiste GUI:
wszystkie 268 klatek TTMAPP, bez pomijania. Planowany wtedy SD-V4-04 został
później wycofany zgodnie z aktualizacją powyżej;
uwagę z ręcznego sprawdzenia 03 i poprawkę opisano powyżej. Implementacja `93701af`,
poprawki i raport `c5deb59`. Historyczne wpisy poniżej
zachowują wyniki wcześniejszych etapów.

**Wykonano SD-V4-02:** podgląd zapisanych centrów, ramek, masek i obrysów,
krycie masek, ID/metadane po kliknięciu oraz oryginał/wyrównany z zapisaną
rejestracją. Braki danych i jakość są jawne; maski mają ograniczony cache.
[Uruchomienie i test ręczny](implementation/interactive-v04/acceptance-02.md).
W `netcat`: **279 testów PASS**, mypy **23 pliki PASS**, przegląd Standards/Spec
bez uwag. GUI sprawdzono na siedmiu klatkach TTMAPP w obu widokach i pięciu
kontrolach; użytkownik potwierdził pomyślny ręczny odbiór 02 (`3572b6d`).
Implementacja `df5c48b`; kolejny etap 03 opisano powyżej.

**Wykonano SD-V4-01:** aplikacja otwiera zapis MolTrack z MPP i pokazuje
obrazy oryginalne, nawigację, wybór numeru oraz zoom/dopasowanie.
Po pomyślnym odbiorze ręcznym użytkownika dodano suwak pod obrazem,
który zmienia klatki podczas przeciągania.
Import działa w tle; anulowanie, błąd i niezgodne źródło zachowują poprzednią
serię. [Instrukcja uruchomienia i ręcznego odbioru](implementation/interactive-v04/acceptance-01.md).
W `netcat`: 230 testów STM Domains PASS, mypy PASS i próba rzeczywistego GUI
na TTMAPP 268 klatek. Pierwotny zakres 01 odebrano ręcznie; dodatek z suwakiem
sprawdzono osobno: 9 testów widoku/nawigacji PASS, mypy PASS i przeciąganie
w rzeczywistym GUI. Użytkownik potwierdził również pomyślny odbiór ręczny
suwaka z commita `ee54638`.
Gałąź `domains/interactive-v04-ui`; oznaczenia i geometrię dodano następnie w 02.
Poniższe wpisy zachowują historię przygotowania planu i badań.

**Rozszerzenia planu UI — 2026-11-02:** dodano
[SD-V4-16–20](implementation/interactive-v04/README.md#rozszerzenia):
pomiary geometrii na obrazie, tolerancje tworzenia domen, ograniczona próba
freud, a jako dalsze warunkowe kroki FFT/NMF i wspólny katalog typów.
16–18 mają przygotowany zakres `ready-for-agent`, 19–20 status `deferred`.
Każdy ticket ma zależności i test ręczny; nadal obowiązuje limit 1000/1500
linii. Nie wykonano implementacji, instalacji ani nowych badań.
Wcześniejsze 01–15 pozostają `draft`, a badawcze 04/13 otwarte.

**Tickety interaktywnego UI v0.4 — 2026-11-02:**
[indeks 15 ticketów SD-V4](implementation/interactive-v04/README.md)
prowadzi od otwarcia obrazów do analizy, regulacji parametrów, ręcznego K,
Auto i zapisu. Każde zadanie dostarcza funkcję do ręcznego sprawdzenia
w uruchomionej aplikacji. Status `draft`: podział czeka na zatwierdzenie.
W instrukcji aplikacji zapisano cel 1000 i twardy limit 1500 linii kodu
na plik. Nie rozpoczęto implementacji ani nie zamknięto dawnych ticketów.

**Interaktywne UI na bazie v0.4 — 2026-11-02:**
[ocena wykonalności](v04-interactive-ui-feasibility.md) potwierdza możliwość
analizy serii lub jednej klatki z regulacją parametrów, ręcznym K i Auto.
Kod ma statystyczny wybór K, ale wymaga podłączenia przez cały przebieg
i obsługi jednej klasy/małych danych. Odróżniono stosowanie wspólnego modelu
od odkrywania klas na jednej klatce. To proponowany zakres rozwoju;
UI i nowe ścieżki obliczeń nie są jeszcze zaimplementowane.

**Przegląd dostarczonych paczek v0.4 — 2026-11-02:**
[podsumowanie kodu i wyników](new-code-v04-review.md) opisuje dwa ZIP z
`data/new_code`. Klasyczna geometria centrów, PCA/KMeans K5 i segmentacja
dają zapisane 4190 przypisań w 122 domenach na 56 klatkach naszego TTMAPP.
To udział przypisań, bez niezależnej oceny trafności; metoda dopuszcza jeden
kierunek periodyczności. Gotowy HTML wymaga uproszczenia do końcowych
przypisań molekuł. Zweryfikowano zawartość i eksporty, bez ponownego
uruchamiania analizy lub przyjęcia detektora. Rozpakowane pliki są lokalnie
w `.scratch/new-code-v04-review/`; 04 i 13 pozostają otwarte.

**Prezentacja przyszłych prób — 2026-11-02:** użytkownik wybrał
[prostą przeglądarkę wyników](trial-result-browser.md): kolejne obrazy STM,
oznaczenia rzeczywistych molekuł, kolory domen i szare molekuły nieprzypisane.
To podstawowy widok do odbioru; szczegółowa diagnostyka pozostaje osobno.
Zapisano wymaganie dla przyszłych prób, bez implementacji przeglądarki
lub uruchomienia nowego badania.

**Wnioski po 21–26 — 2026-11-01:** [synteza wyników i przegląd dalszych kierunków](research-after-training-pilot.md)
porównują wariant bez etykiet treningowych z małym nadzorowaniem, zgodnie
z prośbą użytkownika. Rekomendacja: ograniczona próba przestrzennego odczytu
granic z istniejących cech, a następnie ewentualne uczenie bezpośrednich relacji
między obszarami. Uwzględniono wcześniejsze próby fazy z 12 i diagnozy z 19.
To materiał do decyzji, bez wyboru kolejnego eksperymentu lub zmiany zasad
używania referencji. Nie przyjęto detektora; 04 i 13 pozostają otwarte.

**Wykonano 26 — 2026-11-01:** [adaptacja DINOv2](issues/26-pretrained-self-supervised-adaptation.md)
ma status `resolved` jako eksperyment. [Raport](pretrained-self-supervised-trial.md):
6/6 fitów, 6000 kroków, 14 040 predykcji; bez wymaganej poprawy względem
oryginalnych wag. Cztery główne granice mają F1 0 także przed odmowami.
TTMAPP po odmowach: transfer 0/174, transdukcja FH 4/782, MWS 0/782.
Częściowy zysk MWS względem FFT w transferze nie wystarcza: większość
przewagi była już w oryginalnym DINO. Oba osobne werdykty 26 są negatywne.
Galeria: `.scratch/pretrained-ssl-26/index.html`. Nie przyjęto detektora;
13 i 04 pozostają otwarte, dodatkowe MPP/STP nadal odłożone.
Poniższe wpisy zachowują historię wcześniejszych decyzji.

**Wykonano 25 — 2026-11-01:** [maskowane odtwarzanie obrazu](issues/25-masked-autoencoder-domains.md)
ma status `resolved` jako eksperyment. [Raport](masked-autoencoder-trial.md): 12/12 fitów,
44 928 predykcji. Mask50 zmniejsza błąd zakrytych pikseli o około 59%,
ale końcowe domeny TTMAPP pozostają bez poprawy: transfer 0/174,
transdukcja FH 4/782, MWS 0/782. F1 czterech głównych granic kontrolnych
wynosi 0 także przed odmowami. Częściowy zysk względem AE na syntetykach
nie spełnia całych kryteriów. Galeria: `.scratch/masked-ae-25/index.html`.
Nie przyjęto detektora; 13 i 04 pozostają otwarte, 26 i dodatkowe MPP/STP
nadal niewybrane/odłożone. Poniższe wpisy zachowują wcześniejsze decyzje.

**Wykonano 24a — 2026-11-01:** [diagnoza opisu otoczenia](issues/24a-graph-context-boundaries.md)
ma status `resolved` jako zakończona próba. [Raport](graph-context-boundary-trial.md):
3534 wyniki na 93 znanych kontrolach, 0 treningów. Jednolita konwencja
brzegu usuwa sztuczny podział jednej sieci: 121/121 centrów w jednej domenie
przed i po odmowach. Rzeczywiste granice nadal nie spełniają kryteriów,
a część przypadków się pogarsza. Nie przyjęto detektora. Galeria:
`.scratch/graph-context-24a/index.html`. Odbiór 13 pozostaje otwarty;
25/26 i nowe dane odłożone, wyniki 24 zachowane.

**Wykonano 24 — 2026-11-01:** na późniejsze polecenie użytkownika zakończono
[próbę grafów otoczeń molekuł](issues/24-graph-self-supervised-domains.md),
`resolved` jako eksperyment. [Raport](graph-self-supervised-trial.md):
9/9 fitów, 4212 wyników i galeria `.scratch/graph-ssl-24/index.html`.
Główny FH przypisuje 178–183/204 centrów testowych, ale scala wszystkie
oceniane pary różnych referencji; MWS daje 0/204. Nie wykazano przewagi
nad geometrią i własną inicjalizacją. Wykazano także wpływ brzegu pola
na kontekst grafu. 13 otrzymał wynik, lecz pozostaje otwarty; 25/26
oraz dodatkowe MPP/STP pozostają niewybrane/odłożone.
Poniższa decyzja 23 zachowuje wynik wcześniejszego pilota.

**Wcześniejsza decyzja 23 — 2026-11-01:**
[porównanie](training-comparison-and-next-step.md) zestawia istniejące
wyniki 19/21/21a/22, bez nowych fitów. Nie wykazano poprawy końcowych domen.
Użytkownik przyjął decyzję o zakończeniu pilota bez wyboru detektora;
ticket 23 jest **`resolved`**. Wtedy 24–26 pozostawiono niewybrane
i warunkowe; późniejsze polecenie wybrało 24 zgodnie z aktualnym stanem
powyżej. Dodatkowe dane pozostają odłożone, a 04 i 13 otwarte.

Na polecenie użytkownika [ticket 19](issues/19-frozen-feature-domains.md)
zamknięto jako zakończoną serię badań (`resolved`). Nie wybrano detektora
domen do aplikacji. Podsumowanie ustaleń i ograniczeń znajduje się na
początku ticketu. Zachowujemy prototypy i wyniki jako punkty odniesienia.
[Krok 20](issues/20-self-supervised-training-preparation.md) wykonano, `resolved`:
[dane, protokół i techniczna próba GPU](self-supervised-training-preparation.md).
38 622 rekordy wycinków, 81 nowych kontroli, 78 testów i bitowo identyczne
wznowienie dla trzech ziaren.
[Próbę 21](autoencoder-domains-trial.md) wykonano (`resolved`): 18/18 fitów,
25 200 predykcji, 143 testy i galeria `.scratch/autoencoder-21/index.html`.
Nie wykazano poprawy domen: końcowe coverage częściowych referencji TTMAPP
0% w transferze, najwyżej 0,51% w transdukcji. Nie przyjęto detektora.
[21a — dekoder i regularyzacja rVAE](issues/21a-rvae-decoder-and-kl.md)
wykonano (`resolved`): dwa runy diagnostyczne i dziewięć nowych fitów,
3360 predykcji, 161 testów. [Raport](rvae-decoder-kl-trial.md): słabsze KL
zmniejsza błąd rekonstrukcji o około 14%, lecz nie poprawia końcowego
wykrywania domen; transfer nadal 0/174 przypisań. Galeria lokalna:
`.scratch/rvae-21a/index.html`. Wyniki 21 pozostają zachowane.
[22 — lokalny SSL](local-self-supervised-trial.md) wykonano (`resolved`):
9/9 fitów, 21 420 predykcji, 181 testów. Końcowy transfer 0/174; transdukcja
najwyżej 4/782 (0,51%), bez przewagi nad FFT. Zachowana bramka ze spójnością
ma te same geometryczne limity, a SSL nie rozdziela granic także przed nią.
Galeria: `.scratch/local-ssl-22/index.html`, 89 sprawdzonych interakcji.
**23 zakończono** — porównanie i decyzja są zapisane. Pierwotny budżet
27 fitów 21/22 został wykorzystany. Jakość 04, odbiór 13 i druga mapa
pozostają otwarte; dodatkowe MPP/STP nadal są odłożone zgodnie z decyzją 23.

**Decyzja użytkownika — 2026-10-31:** najpierw wykonujemy 21/22 na obecnym
TTMAPP i przygotowanych kontrolach według protokołu 20. Przygotowanie
dodatkowych MPP/STP odkładamy; nie jest warunkiem rozpoczęcia tych prób.
Zestawienie 23 nie wskazuje jeszcze uzasadnienia przygotowania całego
archiwum. Obecny pilot nie ocenia przenoszenia na inne molekuły lub podłoża.

[Galeria zapisanych propozycji domen](saved-domain-examples.md) udostępnia
trzy klatki TTMAPP oraz kontrolę syntetyczną: PNG, porównanie metod 15/16
i przypisania CSV. To częściowe propozycje grup molekuł, bez zatwierdzonych
konturów domen; eksport nie uruchamia kolejnej próby badawczej.

[Przegląd usprawnień kolejnych prób](research-domain-plan-improvements.md)
został 2026-10-31 przyjęty do [planu 20–23](issues/README.md#trening-bez-etykiet-domen).
20 przygotowało protokół i kryteria; 21/22 łączą trening z ograniczoną próbą
relacji/granic oraz porównaniem 2 × 2 cech i podziału, przed/po odmowach.
W tym planie 23 miało rozstrzygnąć dalszy zakres, a 24–26 były warunkowe.
Późniejszy wybór 24 opisano powyżej. Nie dodano 20a,
przy samym przyjęciu planu nie rozpoczęto treningu ani nowego eksperymentu.

Poniższy opis zachowuje historię projektu; wcześniejsze statusy `claimed`
i odłożenie 20 dotyczą ówczesnych decyzji, zastąpionych powyższym zamknięciem.

## Stan początkowy i historia

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

Po przeglądzie MolTrack i literatury STM/AFM dodano do istniejącej mapy
[cykl samodzielnego znajdowania domen](issues/README.md#próby-samodzielnego-znajdowania-domen).
Plan zaczyna się od [wspólnego wejścia i kontroli](issues/14-unsupervised-input-and-controls.md),
następnie porównuje otoczenie molekuł, SBC/MatID oraz klasyczną teksturę
obrazu. Po przeglądzie ML dodano
[przygotowanie gotowych cech sieci](issues/18-frozen-feature-preparation.md)
i [porównanie domen z tych cech](issues/19-frozen-feature-domains.md).
Próba ML korzysta z wyniku klasycznej tekstury jako punktu odniesienia;
wszystkie wyniki trafiają do istniejącego odbioru metod.
Zakres obejmuje całe klatki, bez przykładów domen i zadanej liczby grup;
ramki służą wyłącznie późniejszej ocenie. Przy dodaniu ticketów próby
nie były wykonane; bieżący stan opisano poniżej. Ten tok badawczy może poprzedzać odbiór szkieletu;
następny krok aplikacyjny nadal dotyczy jego importu i geometrii.

Po dopuszczeniu treningu bez etykiet i ostatnim badaniu dodano
[punkty 20–26](issues/README.md#trening-bez-etykiet-domen): przygotowanie
treningu, AE/rVAE, lokalne SSL, porównanie z wcześniejszymi metodami oraz
warunkowe próby grafów, maskowania i adaptacji gotowego modelu.
Pierwsze próby dotyczą RTX 5090; przejście na 96 GB lub Colab wymaga
uzasadnienia wynikiem i pomiarem. Odbiór 13 ma już zestawienie 23;
po kolejnych poleceniach z 2026-11-01 otrzymał także wyniki 24, 24a, 25
i 26, ale nadal pozostaje otwarty.
Samo dodanie tych zadań nie uruchamiało
treningu; ówczesnym następnym krokiem było przygotowanie wejścia 14.

2026-10-23 [zakończono przygotowanie 14](issues/14-unsupervised-input-and-controls.md).
Gotowy [pakiet i raport](unsupervised-input-preparation.md) obejmuje 24 pełne
klatki, 132 kontrole i osobne referencje; [protokół](experiment-input-protocol.md)
określa format wejścia/wyniku i ocenę. Przeszło 35 testów oraz sprawdzenia
realnych danych i niezależności wejścia od referencji. Podgląd lokalny:
`.scratch/unsupervised-input/index.html`.

Następnie wykonano [pierwszą próbę 15 — otoczenie molekuł](local-neighborhood-domains-trial.md).
Prosty opis/SOAP, dwa promienie i osobna ocena powtarzalności nie dały
jeszcze ogólnego wykrywania. Największe przypisanie na częściowych
referencjach TTMAPP: 31%, tylko BLACK. RED/YELLOW odpadają na kryterium
powtarzalności. Podgląd: `.scratch/local-neighborhood-domains/index.html`.
Użytkownik wybrał dalsze omówienie lub rozwinięcie próby, a następnie
polecił zbadać kryterium powtarzalności. [Kontynuacja](recurrence-criterion-trial.md)
porównuje 38 konfiguracji na 204 próbkach przy zamrożonym katalogu.
Warunek przechodzi 90.9% oznaczeń w referencjach, domenę otrzymuje 62.5%,
lecz występują scalenia i liczne odmowy RED/YELLOW przy łączeniu składowych.
Podgląd tej próby: `.scratch/recurrence-criterion/index.html`.

Na kolejne polecenie wykonano [badanie orientacji i łączenia](orientation-and-joining-trial.md):
31 wariantów, 228 próbek. Komórka sieci ze zgodnością wobec startu obszaru
poprawia kontrolę braków i część TTMAPP: 70.7% przypisań, 0/3801 scaleń
ocenianych par różnych regionów. RED jednak spada do 14/101, a granica
przesunięcia z błędem centrów jest niemal całkowicie scalana. Podgląd:
`.scratch/orientation-and-joining/index.html`. Użytkownik polecił następnie
przejść do 16; issue 15 jest zakończone jako eksperyment i punkt odniesienia,
bez wdrażania metody.

[Próba 16 — SBC/MatID](sbc-matid-domains-trial.md) obejmuje 228 próbek,
6 ustawień i 3 polityki wyniku. Pomaga przy brakach centrów, deformacji
i granicy przesunięcia z szumem. Nie spełnia jednak warunku samodzielnego
wyszukiwania: tworzy pozorne obszary na losowych punktach, scala różnicę
orientacji 8° i zależy od ziarna wyszukiwania. W referencjach adaptacja
przypisuje 63.5% centrów, przy 5.5% scaleń ocenianych par różnych regionów.
Podgląd: `.scratch/sbc-matid-domains/index.html`. Issue 16 ma status `resolved`: użytkownik
zatwierdził zachowanie porównania i przejście do tekstury w 17. [Audyt API](research-sbc-adaptation-audit.md)
i raport opisują poprawki modelu punktowego oraz ograniczenia biblioteki.

Wykonano [próbę tekstury 17](image-texture-domains-trial.md): lokalne widmo
oraz EWT, 32 konfiguracje, siatka i centra na 228 próbkach. Wariant obrazowy
pozostaje identyczny bez oznaczeń, ale wybrane ustawienia przypisują tylko
0.3–5.8% centrów w referencjach TTMAPP, bez RED/YELLOW. EWT scala małe
orientacje, widmo na siatce nadmiernie dzieli jedną sieć, a bramka porządku
odrzuca większość rzeczywistych wzorów. Użytkownik zaakceptował porównanie:
17 jest `resolved` jako klasyczny punkt odniesienia dla ML, bez wdrożenia.
Podgląd: `.scratch/image-texture-domains/index.html`.

2026-10-26 [zakończono przygotowanie 18](frozen-feature-preparation.md):
FCN–ResNet101 i DINOv2 ViT-S/14, 16 konfiguracji na 12 obrazach, siatka
oraz wszystkie centra molekuł. Zachowano geometrię, maski i cache;
192/192 powtórzenia siatki są identyczne bez oznaczeń i niezależne od
referencji. Przeszło 41 testów i 19 kontroli podglądu. Modele pracują
bez aktualizacji wag. Podgląd `.scratch/frozen-features/index.html`
pokazuje miejsca pobierania cech, nie znalezione domeny. Issue 18 jest
`resolved`; wykonanie porównania 19 opisano poniżej.
Niezależne przygotowanie treningu 20 również pozostaje do wykonania.

2026-10-26 wykonano [porównanie gotowych cech 19](frozen-feature-domains-trial.md):
FCN/DINO, FFT/EWT i dwa kryteria porządku, 160 konfiguracji na 228 obrazach.
Nie uzyskano poprawy: wybrane sieci przypisują 0–5.1% centrów we wnętrzach
TTMAPP, bez RED/YELLOW; pozostają błędy podziałów i scaleń. Oddzielono
problemy grupowania (zwykle jedna grupa wyglądu) i odmów kryterium porządku.
Podgląd: `.scratch/frozen-feature-domains/index.html`. Użytkownik wybrał
**dalsze omówienie/rozwinięcie**, więc 19 pozostaje `claimed`. Proponowane
kolejne badanie dotyczyło utraty różnic w cechach, PCA i grupowaniu;
zostało wykonane i jest opisane poniżej. Nie wybrano metody ani nie rozpoczęto treningu.

Następnie wykonano [diagnozę cech i grupowania](feature-separation-trial.md):
32 warianty na tych samych 228 obrazach. Cechy obu sieci rozróżniają
syntetyczne orientacje/rozstaw, PCA prawie nie zmienia tego wyniku,
lecz epsilon=0 ani pełne cechy nie naprawiają podziału domen na TTMAPP.
Żaden wariant nie spełnia wszystkich warunków. Nowy podgląd:
`.scratch/feature-separation/index.html`; 1824 dokładne odtworzenia
starego wyniku i 68 kontroli HTML. Issue 19 pozostaje `claimed`.
Zaproponowaną próbę lokalnych granic wykonano poniżej; ocena kryterium
porządku pozostaje osobnym kierunkiem, bez narzucania K lub wzorców domen.

[Lokalny graf i położenie siatki](local-feature-graph-trial.md): 32 nowe
konfiguracje na 228 obrazach, dodatkowo świeże cechy przesuniętych okien
na 53 obrazach. Graf zmniejsza część scaleń orientacji, ale nadmiernie
dzieli jedną sieć i zależy od początku siatki. Żaden wariant nie spełnia
wszystkich warunków; obecna bramka dopuszcza najwyżej 2.0–5.8% molekuł
w częściach TTMAPP z referencjami. Podgląd:
`.scratch/local-feature-graph/index.html`; 107 kontroli HTML, odtworzenia
cech i grafów oraz niezależne sprawdzenie małych grafów. **19 nadal
`claimed`**, bez przyjęcia metody. Próbę skali i podparcia ACF przy stałych
cechach/podziałach wykonano następnie.

[Skala i podparcie kryterium ACF](acf-scale-support-trial.md): 32 warianty
bramki na 228 obrazach. Większe okno odzyskuje część RED/YELLOW,
ale może łączyć rozłączne płaty przez pustą przerwę; żaden z 512 wariantów
detektora nie spełnia wszystkich warunków. Widmowy warunek drugiego
kierunku odrzuca około połowy miejsc w znanych wnętrzach i został zbadany
w osobnej próbie poniżej. Podgląd `.scratch/acf-scale-support/index.html`,
92 sprawdzenia HTML, odtworzenia ACF/progów/wyników oraz niezależna kontrola
korelacji z maską pomiaru. **19 nadal `claimed`**, bez wyboru metody.

[Warunek drugiego kierunku](second-direction-trial.md): 228 znanych obrazów
i 63 nowe kontrole rzędów/pasów/przerw. Przy r24/`windowed` wyłączenie warunku
podnosi limit przypisań z 98 do 636/1678 w TTMAPP, lecz przyjmuje także
756/768 miejsc rzędów o losowych fazach jako jedną sieć. Krzywizna ACF
odrzuca słabsze spójne rzędy i TTMAPP; 0/384 zmienionych konfiguracji
detektora spełnia komplet warunków. Predykcje identyczne po zablokowaniu
odczytu referencji, 170 kontroli HTML. Podgląd `.scratch/second-direction/index.html`.
**19 pozostaje `claimed`**, do omówienia. Następna hipoteza dotyczy
zgodności przesunięć między rzędami i lokalnego wsparcia sygnału, bez
wzorca domeny i zadanej symetrii; zbadano ją poniżej.

2026-10-28 wykonano [zgodność przesunięć i lokalny sygnał](translation-consistency-trial.md)
na 372 obrazach, w tym 81 nowych kontrolach. Zgodność zachowuje około
80% słabszej syntetycznej sieci i ogranicza przypisania niezależnych
rzędów z 98.4% do 3.1% względem wariantu bez drugiego kierunku, ale
odrzuca wszystkie wnętrza TTMAPP. Lokalny sygnał usuwa także poprawne
płaty, gdy małe okno siatki wypada między molekułami. 0/256 zmienionych
konfiguracji detektora spełnia komplet warunków. Podgląd:
`.scratch/translation-consistency/index.html`, 187 kontroli HTML oraz
87840 wyników identycznych po ponowieniu bez dostępu do referencji.
Po tej próbie proponowano 20, następnie 21/22. Użytkownik wybrał jednak
pozostanie przy 19 i [audyt odmów](vector-refusal-audit.md), wykonany na
78 znanych obrazach. Podmiana wektorów obrazu na wektory centrów daje
17/1916 przyjętych miejsc siatki r24, ale nadal 0/1678 przypisań TTMAPP.
Odmowy utrzymują się we wnętrzach; część zmian decyzji wynika z wyboru
równoważnej bazy sieci. Podgląd `.scratch/vector-refusal-audit/index.html`,
125 kontroli HTML, 3816 wyników odtworzonych bez dostępu do referencji.
Następnie wykonano [ocenę rodziny przesunięć](translation-family-trial.md)
na 165 obrazach, w tym 42 nowych syntetykach. Ocena jest niezależna od
równoważnej bazy, lecz agregacje obrazu nadal dają 0/1678 przypisań TTMAPP.
Zgodność centrów odzyskuje do 296/1678, tylko BLACK, kosztem błędów granic
i niezależnych rzędów. Podgląd `.scratch/translation-family/index.html`;
24804 wyników odtworzonych bez referencji, 343 kontrole HTML.
Następnie wykonano [tolerancję pozycji i zgodność fazy](tolerant-fit-phase-trial.md):
210 obrazów, 84 warianty, 45 nowych syntetyków. Miękkie dopasowanie pomaga
przy niewielkich błędach i brakach oznaczeń, ale korekta sieci pochłania
część granic. Faza odcina 132/138 połączeń przez kontrolną granicę 3 px,
lecz pozostawione mostki nadal scalają fragmenty. TTMAPP najwyżej 125/1678,
tylko BLACK. Podgląd `.scratch/tolerant-fit-phase/index.html`; 17640 wyników
odtworzonych bez referencji, 217 kontroli HTML.
Wykonano też [rozłączne modele i podparcie materiału](disjoint-models-material-trial.md):
261 obrazów, 96 wariantów, 51 nowych kontroli. Prosta granica 3 px została
rozdzielona przy centrach (138/138 połączeń usuniętych, bez spadku przypisań).
Osobny sygnał obrazu odróżnia szeroką przerwę od pasa brakujących oznaczeń.
Granice ukośne, lokalny szum i jakość TTMAPP pozostają nierozwiązane;
zero porównań TTMAPP osiąga próg jakości. Podgląd
`.scratch/disjoint-models-material/index.html`; 25056 wyników odtworzonych
bez referencji, 212 kontroli HTML.
2026-10-31 wykonano [diagnostykę jakości dopasowania](fit-quality-diagnosis.md):
97 obrazów, 54 nowe kontrole, 68184 oceny. Wysoki próg wynikał z kilku
niezależnych rzędów wspólnych dla treningu i oceny. Naprzemienny podział
potrafi sugerować podwojony okres nawet idealnej sieci. Nowa ocena
tolerancji/liczebności nie daje ogólnej poprawy; bardziej złożony motyw
ujawnia kolejne ograniczenie pojedynczej sieci. Podgląd
`.scratch/fit-quality-diagnosis/index.html`; 272736 decyzji odtworzonych
bez referencji. Następnie wykonano [próbę kandydatów baz i nowych powtórzeń](basis-candidates-trial.md):
97 obrazów, 54 nowe syntetyki, 15152 otoczenia. Dzielniki baz odzyskują
prawidłowy okres w 9/9 celowanych kontrolach R64, ale na TTMAPP przy
wspólnym progu nie ma poprawy. Podgląd `.scratch/basis-candidates/index.html`;
90912 decyzji odtworzonych bez referencji, 86 kontroli HTML.
Następnie wykonano [próbę motywu i kompletności](motif-completeness-trial.md):
103 obrazy, 60 nowych kontroli, 7960 otoczeń. Oddzielna ocena pozycji
pomaga przy brakach oznaczeń; model dwóch pozycji poprawia przewidywania
kontrolnych par, ale dodaje fałszywe akceptacje niezależnych rzędów.
TTMAPP: jedna pozycja i motyw mają te same 7 akceptacji całego pierścienia
oraz 5 nowych rzędów; w znanych wnętrzach po jednej. Nie przyjęto metody.
Podgląd `.scratch/motif-completeness/index.html`. Po omówieniu użytkownik
zakończył serię: **19 `resolved`**, bez przyjęcia metody. Zachowujemy składniki
badawcze; przygotowanie 20 pozostaje otwarte i nierozpoczęte.


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

Z katalogu głównego worktree, w środowisku **`netcat`**:

```bash
python -m stmdomains.main
```

To samo środowisko służy do testów i prób. Zweryfikowany interpreter oraz
polecenia opisuje [instrukcja uruchomienia](implementation/README.md#uruchomienie-i-środowisko).
[Ogólne przygotowanie środowiska](../../README.md) i
[praca równoległa](../PARALLEL_DEVELOPMENT.md).

## Kod do oceny i testy

- Istniejąca analiza molekularna: `moltrack/analysis/` oraz `tests/moltrack/`.
- Czytniki i model obrazu: `napara/io/`, `napara/core/data_models.py`.
- Viewer: `napara/gui/widgets/viewer_widget.py`.
- Testy nowych funkcji: `tests/stmdomains/` (na razie katalog startowy).

Współdzielony kod i modele mogą wymagać dodatkowych zależności poza PyQt6 szkieletu.
Nowe metody będą oceniane na danych i kryteriach rozstrzygniętych przez pytania mapy.

## Materiały do decyzji

- [Wnioski po treningach 21–26 i dalsze kierunki](research-after-training-pilot.md)
  — przestrzenne cechy, lokalna struktura, uczenie granic oraz porównanie
  braku etykiet treningowych z niewielkim nadzorowaniem. Źródła pierwotne
  i ograniczenia transferu na molekularne STM; propozycje nie są nowym planem prób.
- [Dane do treningu z wielu MPP/STP](research-training-data-requirements.md)
  — wymagane metadane, skala, jakość i podział niezależnych akwizycji.
  Użytkownik ma dane różnych molekuł/podłoży z rozmiarami skanów w nagłówkach.
  To zalecenia do inwentaryzacji, bez importu nowego archiwum lub zmiany protokołu 20.
- [Trening bez etykiet do odkrywania domen](research-self-supervised-domain-learning.md)
  — rVAE, lokalne uczenie cech, maskowane obrazy i grafy oznaczonych molekuł;
  precedensy STM/AFM oraz propozycja prób na RTX 5090. Własny trening
  jest dopuszczony, ale ramki domen pozostają wyłącznie referencją oceny.
  Drugi komputer z 96 GB VRAM i Colab są opcjami późniejszego rozszerzenia.
- [ML i deep learning bez własnego treningu](research-training-free-ml-domain-discovery.md)
  — gotowe cechy CNN/DINO, bezpośrednie precedensy STM/SPM oraz różnica
  między grupowaniem bez etykiet a treningiem sieci. Propozycję rozwinięto
  w zadania przygotowania i porównania ML; nie uruchomiono modeli
  ani nie wybrano metody.
- [Samodzielne wyszukiwanie domen w STM/AFM](research-stm-afm-unsupervised-domain-discovery.md)
  — bezpośrednie precedensy, ich ograniczenia oraz rozróżnienie braku
  przykładów treningowych od narzucania liczby grup.
- [Domeny i grupowanie oznaczonych obiektów](research-domain-discovery-and-object-clustering.md)
  — kandydaci dla centrów molekuł, ich otoczeń i tekstury obrazu.
- [Plan nowych prób i odpowiadające mu tickety](unsupervised-domain-experiments.md)
  — wejście, kontrole oraz porównania klasyczne i ML prowadzące do odbioru metod.
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
