# Czy AE i rVAE uczą się cech przydatnych do odkrywania domen?

ID: 21
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
Assignee: domains/start
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 17, 20

## Dalszy plan — 2026-10-31

Na polecenie użytkownika dodano osobny
[21a — dekoder i regularyzacja rVAE](21a-rvae-decoder-and-kl.md).
To ograniczona próba diagnostyczna i dziewięć dodatkowych fitów,
z własnym budżetem, przed 22 i wspólną decyzją 23. Niniejszy ticket
pozostaje `resolved`; jego raport, wagi, predykcje i ocena nie są zastępowane.
Poniższy Answer opisuje pierwszą zakończoną próbę i ówczesną kolejność.

## Answer — 2026-10-31

Wykonano pełną zamkniętą próbę: [raport](../autoencoder-domains-trial.md),
[manifest](../autoencoder-domains-manifest.json). Status `resolved` oznacza
zakończony eksperyment, bez przyjęcia detektora do aplikacji.

18/18 fitów AE/rVAE, 29 700 kroków, trzy ziarna, osobny transfer i transdukcja.
Porównano FFT/uczone cechy × FH/MWS przed i po odmowach, trzy skale oraz
siatkę i centra. Zapisano 25 200 predykcji i 26 160 rekordów oceny.
Żadna z ośmiu głównych konfiguracji z32 nie spełnia kryteriów kontynuacji.

Na częściowych referencjach TTMAPP transfer daje 0/174 końcowych przypisań;
transdukcja najwyżej 4/782 (0,51%). Wspólna bramka odrzuca niemal wszystko,
a przed odmowami pozostają scalenia i rozdrobnienie. rVAE nie wydzielił
wiarygodnej orientacji sieci; jego kod silnie wiąże się z jasnością.
Zawodzą także niezależne rzędy i kontrole granic. Siatka pozostaje niezależna
od braków centrów: 1800/1800 zgodnych porównań całej próby.

143 testy przeszły; oba wznowienia GPU są bitowo identyczne. Audyt
100 299 artefaktów poprzedzał odczyt referencji. Galeria HTML przeszła
15 sprawdzeń interakcji, bez błędów JS; nie jest to odbiór natywnego GUI.
Kod badawczy znajduje się w `stmdomains/experiments/training/`, źródło
prototypu zachowuje gałąź `prototype/stmdomains-autoencoder-domains`.
Artefakty lokalne: `.scratch/autoencoder-21/`, w tym `index.html`.

Nie zmieniano parametrów po ocenie. Wynik dotyczy tej konfiguracji i jednej
akwizycji; nie rozstrzyga skuteczności na szerszych danych. Następny krok
to niezależne 22, potem wspólna decyzja 23. Nie rozpoczęto 22 ani 24–26.

## Question

Czy mały autoenkoder oraz rVAE z ciągłymi zmiennymi pozwalają znaleźć
strukturę domen lepiej niż klasyczna tekstura? Sprawdzić korzyść z oddzielania
obrotu od treści, bez zadanej liczby kategorii. Przykład STM opisany
w [przeglądzie](../research-self-supervised-domain-learning.md) jest precedensem,
a nie gotowym rozwiązaniem: jego część dyskretna miała zadaną liczbę składowych.

**Aktualizacja przyjęta — 2026-10-31:** zgodnie z
[badaniem usprawnień](../research-domain-plan-improvements.md) głównym
sprawdzianem cech są lokalne relacje i zachowanie granic. Obowiązuje
[wspólny protokół 20](20-self-supervised-training-preparation.md#wspólny-protokół-relacji-i-podziału).
Pilot jest częścią tego ticketu, bez osobnego 20a. Przy przyjęciu planu
zadanie pozostawało `open`; późniejsze wykonanie opisuje Answer powyżej.

## Porównanie

1. Zacząć od małego konwolucyjnego AE jako punktu odniesienia. Ciągły rVAE
   sprawdza celowo korzyść z oddzielenia obrotu od struktury na identycznym
   zakresie nieoznaczonych danych według kroku 20. Zwykły VAE jest dodatkowym
   wariantem, jeśli pomaga oddzielić wpływ regularyzacji od wydzielania obrotu.
   Zapisać architekturę i wymiar cech; wymiar ten nie oznacza liczby domen.
2. Zacząć od wycinków obrazu w kilku skalach. Lokalna FFT może być osobnym
   wariantem w ustalonym budżecie; sam moduł widma nie zachowuje informacji
   o fazie potrzebnej do granic przesunięcia. Nie zastępować nim po cichu
   informacji przestrzennej ani surowych pomiarów.
3. Zachować kąt jako osobny wynik. Na kontrolach sprawdzić, czy opisuje
   orientację sieci, a nie kształt jednej molekuły, brzeg lub pas skanowania.
   Uwzględnić równoważne kierunki sieci; nie zakładać z góry symetrii M6.
   Typ ma zachować rozstaw i strukturę, a obrót może rozdzielać domeny.
4. Ciągłe cechy poddać grupowaniu bez zadanego `K`, z możliwością jednej
   grupy, oraz osobnej ocenie porządku i łączności. Dopuścić zero domen,
   brak danych i niejednoznaczność. Nie nazywać klastra domeną tylko dlatego,
   że ma podobną rekonstrukcję. Katalog jest wspólny dla badanego zakresu.
5. Porównać z wynikiem klasycznej tekstury z kroku 17 przy wspólnej procedurze
   oceny i możliwie tych samych etapach grupowania oraz łączenia. Ujawnić
   konieczne różnice; sukces tekstury nie jest warunkiem próby AE.
6. Wykonać ograniczone porównanie 2 × 2 z protokołu 20: zachowane/uczone
   cechy i zachowany/nowy sposób wykorzystania relacji oraz podziału, z MWS
   jako kandydatem. Jakość relacji sprawdzić na sąsiadach wewnątrz domen
   i przez granice, także gdy okna częściowo się pokrywają. Zachować osobno
   opis typu/rozstawu, orientację i informację o przesunięciu wzoru.
   Brak rozpoznanego typu nie blokuje propozycji domeny. Nie odtwarzać
   szerokiego przeszukiwania konfiguracji 19; warianty mieszczą się w budżecie 20.

## Dane i kryteria porównania

Obowiązują miary i kontrole kroku 14 oraz podział, budżet i powtórzenia
z kroku 20. Ocenić rozstaw, orientację, granicę przesunięcia, pojedyncze
defekty, pas nieuporządkowany, szum, pasy skanowania i niepełne centra.
Raportować fałszywe domeny, scalenia/podziały, odmowy i stabilność katalogu
przy zmianie ziarna i zakresu; nie wybierać modelu tylko po błędzie rekonstrukcji.
Sprawdzić, czy cechy nie dzielą danych głównie według jasności lub numeru klatki.
W każdym polu porównania pokazać wynik przed filtrem wiarygodności i po nim,
z błędami scaleń/podziałów zestawionymi z udziałem przypisanych elementów.
Odrzucenie niemal wszystkiego ani poprawa rekonstrukcji nie spełnia kryterium
poprawy domen. Stosować ustalone w 20 warunki zakończenia i kontynuacji;
nie dopasowywać ich do korzystnego checkpointu lub częściowej referencji.

Po zamrożeniu konfiguracji i predykcji pokazać pełne klatki oraz częściowe
referencje TTMAPP. Ich kolory opisują głównie orientacje, a nie trzy typy.
Zmiana samych referencji nie wpływa na model ani predykcję. Wcześniej
używane ramki pozostają oceną częściową, nie niezależnym testem.

## Wynik do omówienia

Odtwarzalny prototyp, tabela kontroli, nakładki pełnych pól i porównanie
AE/rVAE z teksturą, z kosztem treningu, inferencji, pamięci i checkpointów.
Pokazać cztery pola porównania i wskazać, czy błąd pochodzi z cech, relacji,
podziału czy odmów; ujawnić, gdy zmiana wejściowej informacji uniemożliwia
przypisanie poprawy samemu solverowi.
Rozdzielić wynik transdukcyjny od próby przenoszenia oraz brak uruchomienia
od nieskuteczności uruchomionej metody. Udokumentowany wynik negatywny
może zakończyć badanie po omówieniu; niska strata sama go nie zalicza.

Wnioski trafiają do kroku 23. Zastosowanie modelu w aplikacji i przyjęcie
warunków odmowy pozostają zakresem odbioru 13.

## Dependencies

- [Czy lokalna tekstura STM pozwala znaleźć domeny bez przykładów?](17-image-texture-domains.md)
- [Jak przygotować odtwarzalny trening bez etykiet domen?](20-self-supervised-training-preparation.md)
