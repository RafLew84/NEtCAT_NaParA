# Rejestracja i życie wyniku aligned

Type: grilling
Label: wayfinder:grilling
Status: resolved
Assignee: rlew
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 01

Zależy od: [Seria wejściowa i usuwanie klatek](01-frame-series.md).

## Question

Jak uruchamiać i prezentować istniejącą rejestrację NanoTrack oraz kiedy jej
wynik pozostaje ważny po zmianie serii?

Do ustalenia: punkt odniesienia i ponowna rejestracja, usunięcie klatki po
dopasowaniu (w tym pierwszej), nieudane dopasowanie, postęp i anulowanie,
zachowanie przy niedostępnym modelu oraz przejście na aligned po sukcesie.
Trzeba ustalić kontrakt powiększonego obszaru i brakujących danych dla eksportu.

## Comments

### 2026-10-14 — wymagania i odpowiedź użytkownika

Użytkownik wybrał jedną metodę z listy i przycisk „Rejestruj”, tak jak
w NanoTrack, domyślnie Phase i obecne ustawienia. Nie uruchamiamy wszystkich
metod jednocześnie. Lista obecnego UI: Phase, Tile+RANSAC, ECC, Optical Flow,
Deep Matcher. Rozwijanie metod i strojenie parametrów jest późniejszym etapem.

Po rejestracji potrzebny jest wspólny powiększony obszar bez obcięcia przesuniętych
klatek i przełączanie original/aligned. Dostępne API oraz ograniczenia wejścia
opisuje [Rozpoznanie istniejącego kodu](../reconnaissance.md).

### 2026-10-16 — konsekwencje kontraktu serii

[Seria wejściowa i usuwanie klatek](01-frame-series.md) dopuszcza przy imporcie
różne skale fizyczne i kanały przy jednakowych wymiarach w pikselach.
W tym tickecie trzeba ustalić zachowanie rejestracji dla takich danych oraz
ważność wyniku po odwróceniu kolejności, obok już wskazanego usuwania klatek.
To pytania otwarte; kontrakt importu nie narzuca odpowiedzi.

### 2026-10-19 — kontrakt podglądu

[Podgląd, gamma i odtwarzanie serii](02-preview-playback.md) ustala jeden
główny obraz, osobny zapamiętany zoom original/aligned, szachownicę poza
pomiarem i obrys oryginalnego pola klatki. Wynik rejestracji musi dostarczyć
geometrię i informację o brakujących pikselach potrzebne do tej prezentacji.
Ważność wyniku po zmianie serii nadal rozstrzyga niniejszy ticket.

### 2026-10-19 — pierwsza runda ustaleń

Użytkownik potwierdził ponowną rejestrację z oryginałów i podmianę poprzedniego
wyniku dopiero po sukcesie. Podczas obliczeń Play jest zatrzymane, dostępne są
postęp i Anuluj oraz podgląd/zoom/gamma; zmiany składu i kolejności serii są
zablokowane. Sukces przełącza na aligned tej samej klatki, dopasowuje nowy
obszar i zachowuje gamma.

### 2026-10-19 — druga runda i korekta zakresu

Użytkownik potwierdził sposób NanoTrack, zachowanie gotowego dopasowania po
usuwaniu, prezentację niepewnych wyników, zgodność wymiarów jako wystarczające
kryterium łączenia klatek do rejestracji oraz brak automatycznego pobierania
wag i zastępowania metody. Jednocześnie wycofał odwracanie kolejności z programu,
potwierdzając zachowanie gotowego dopasowania.
Ta korekta zastępuje wcześniejsze ustalenia o odwracaniu w kontrakcie serii
i podglądu. Ich odpowiedzi i prototyp zaktualizowano.

## Answer

### Uruchomienie i odniesienie

- Jedna metoda z listy i przycisk „Rejestruj”; domyślnie Phase. Zachowujemy
  obecne metody NanoTrack: Phase, Tile+RANSAC, ECC, Optical Flow, Deep Matcher
  i ich obecne ustawienia. Bez porównywania wszystkich metod ani strojenia
  algorytmów w pierwszej wersji.
- Każda próba korzysta z oryginalnych obrazów wszystkich klatek bieżącej serii.
  Nie rejestrujemy ponownie już interpolowanych obrazów aligned; gamma i zoom
  nie wpływają na obliczenia ani oryginalne dane.
- Dopasowujemy każdą kolejną klatkę do poprzedniej i sumujemy przesunięcia
  względem pierwszej w bieżącej serii. Pierwsza jest odniesieniem z przesunięciem
  zerowym. Nie ma wyboru innej klatki odniesienia ani innej kolejności par.
  Pojedyncza klatka jest własnym odniesieniem; pusta seria nie uruchamia obliczeń.
- Wynik jest związany z pochodzeniem klatek i metodą, którą go obliczono.
  Zmiana wyboru metody nie modyfikuje starego wyniku; nową próbę uruchamia
  dopiero „Rejestruj”. Program nie oferuje odwracania kolejności klatek.

### Przebieg, sukces i anulowanie

- Start zatrzymuje Play. Okno pozostaje responsywne: można przeglądać klatki,
  używać dostępnych widoków original/aligned oraz regulować zoom i gamma.
  Niedostępne są zmiany serii, wczytanie innej serii i uruchomienie drugiej próby.
  Ustawienia trwającego obliczenia pozostają stałe.
- Pokazujemy postęp i „Anuluj”. Anulowanie jest przyjmowane także podczas
  pojedynczego dłuższego kroku; zatrzymanie następuje w najbliższym bezpiecznym
  punkcie. Do zakończenia pracy pokazujemy stan anulowania i utrzymujemy blokadę
  zmian serii. Nie obiecujemy natychmiastowego przerwania wnętrza backendu.
- Poprzedni wynik i jego geometria pozostają dostępne do chwili przygotowania
  kompletnego nowego wyniku, włącznie z aligned. Błąd lub anulowanie na dowolnym
  etapie odrzuca nową próbę w całości; nie publikuje częściowego wyniku.
  Jeśli poprzedniego wyniku nie było, nadal dostępny jest tylko original.
- Sukces zastępuje poprzedni wynik. Automatycznie pokazujemy aligned aktualnie
  oglądanej klatki, dopasowujemy cały nowy obszar i zachowujemy gamma.
  Play pozostaje zatrzymane. Dotychczasowy obszar podglądu original pozostaje
  zapamiętany; do original można wrócić przełącznikiem.
- Błąd/anulowanie nie cofa zmian wyboru klatki, zoomu i gamma dokonanych przez
  użytkownika w trakcie obliczeń. Nie usuwa poprzedniego wyniku.

### Pewność i dostępność metod

- Niska pewność dopasowania nie odrzuca kompletnego wyniku: pokazujemy aligned
  i oznaczamy klatki wymagające sprawdzenia, również te z niepewnością odziedziczoną
  przez sumowanie przesunięć. Zachowujemy istniejące kryteria jakości backendu;
  nie dodajemy nowych progów ani automatycznych poprawek.
- Wyjątek, status nieudanego dopasowania (`failed`), brak wyniku klatki,
  nieprawidłowe przesunięcie lub błąd tworzenia aligned oznacza nieudaną próbę.
  Wskazujemy przyczynę i klatkę/parę, jeśli jest znana. Poprzedni wynik zostaje.
  `low_confidence` i `manual_review` z kompletnymi, poprawnymi przesunięciami
  oznaczają wynik do obejrzenia, a nie awarię obliczenia.
- Metoda bez potrzebnych bibliotek lub lokalnych wag jest widoczna jako
  niedostępna z podaniem przyczyny. Sprawdzenie dostępności ani „Rejestruj”
  nie pobierają automatycznie wag. Nie przełączamy samoczynnie na inną metodę;
  użytkownik wybiera dostępną, np. Phase. Pobieranie wag z aplikacji jest poza
  zakresem tej wersji. Błąd ładowania obecnych wag jest błędem próby.

### Usuwanie i ważność istniejącego wyniku

Usunięcie klatki usuwa odpowiadający jej obraz, wynik, geometrię i metadane
z bieżącej serii. **Gotowe dopasowanie pozostałych klatek zachowujemy.**
Nie zmieniamy ich położenia, próbek aligned, statusów jakości ani wspólnego
rozmiaru obszaru. Nie wykonujemy ponownej interpolacji i nie przycinamy pustych
marginesów po usunięciu klatki wyznaczającej skrajny zasięg.

Dotyczy to również usunięcia pierwszej klatki: wynik zachowuje dotychczasowy
układ odniesienia. Pochodzenie dawnej klatki odniesienia pozostaje informacją
o tym wyniku, niezależną od numerów w aktualnej serii. Usunięcie klatki
z niską pewnością nie usuwa niepewności już wyliczonej dla pozostałych.
Przełączanie widoku, zoom i gamma również nie unieważniają wyniku.

Dopiero ponowne „Rejestruj” oblicza dopasowanie dla pozostałych oryginałów,
względem pierwszej z nich, i może wyznaczyć inny rozmiar obszaru aligned.
Zachowanie wyboru klatki po usunięciu określa [kontrakt serii](01-frame-series.md).
Usunięcie jedynej klatki usuwa również ostatni wynik i zostawia pusty program.
Udane otwarcie innej serii zastępuje serię i jej wynik; nieudany import
pozostawia dotychczasowy stan.

### Geometria, brakujące piksele i metadane

- Rejestracja pracuje w pikselach, a wynikiem są przesunięcia XY. Wystarcza
  zgodność wymiarów; różnice kanału lub skali fizycznej nie blokują obliczeń.
  Nie przeskalowujemy automatycznie obrazów, aby uzgodnić ich metadane.
- Wszystkie aligned danej próby mają wspólny, powiększony obszar obejmujący
  przesunięte klatki. Nie obcinamy ich do pierwotnych wymiarów ani do wspólnej
  części pomiaru. Zachowujemy rozmiar i położenie pola każdej oryginalnej klatki.
- Stosujemy istniejące próbkowanie liniowe bez ekstrapolacji poza pomiar.
  Brakujące próbki są oznaczone jako niedostępne (obecny materializator używa NaN),
  a podgląd pokazuje szachownicę. Nie wypełniamy ich zerem, medianą ani
  powielonym brzegiem w danych wyniku. Original pozostaje bez zmian.
- **Pole oryginalnej klatki i maska ważności aligned są osobnymi informacjami.**
  Pole ma oryginalne wymiary i jest przesunięte; maska wskazuje, gdzie w wyniku
  istnieją ważne próbki po interpolacji. Liczenie tych próbek nie wyznacza
  rozmiaru pola. Obrys pochodzi z geometrii, a szachownica z ważności próbek.
- Wynik zachowuje powiązanie z pochodzeniem, oryginalnymi wymiarami, przesunięciem,
  położeniem w powiększonym obszarze i dostępnymi metadanymi każdej klatki.
  Nie przypisujemy metadanych pierwszej klatki wszystkim pozostałym.
- Przy nieznanej lub niespójnej skali aligned prezentujemy w pikselach.
  Nie deklarujemy wspólnej skali fizycznej na podstawie jednej klatki.
  Zachowanie źródłowych metadanych nie oznacza przeskalowania wynikowych obrazów.

### Przykłady do odbioru implementacji

| Sytuacja | Oczekiwany wynik |
| --- | --- |
| Ponowna rejestracja kończy się błędem lub anulowaniem | Poprzedni kompletny wynik nadal dostępny. |
| Błąd tworzenia powiększonego aligned po wyznaczeniu przesunięć | Cała nowa próba odrzucona; stary wynik pozostaje. |
| Sukces, użytkownik w trakcie przeszedł na inną klatkę | Aligned tej aktualnie oglądanej klatki, zachowana gamma, nowy obszar dopasowany, Pause. |
| Komplet przesunięć z niską pewnością | Aligned dostępne; odpowiednie klatki oznaczone do sprawdzenia. |
| Usunięcie pierwszej lub skrajnie przesuniętej klatki | Pozostałe aligned zachowują próbki, położenie i rozmiar obszaru. |
| Ponowna rejestracja po usunięciu pierwszej | Nowe odniesienie to pierwsza pozostała klatka; nowy wynik publikowany dopiero po sukcesie. |
| Różne skale lub kanały, te same wymiary | Rejestracja dopuszczona; przy niespójnej skali widok w pikselach i osobne metadane. |
| Przesunięcie subpikselowe | Obrys zachowuje wymiary oryginału; maska próbek może mieć węższy ważny brzeg. |
| Brak wag lub biblioteki wybranej metody | Metoda niedostępna z powodem; bez pobierania i automatycznej zamiany. |

### Ograniczenia istniejącego kodu i dalsze decyzje

Wynik ticketu jest specyfikacją, nie implementacją. Różnice wobec obecnego
NanoTrack/MolTrack opisuje [rozpoznanie](../reconnaissance.md#uzupełnienie-rejestracja-i-geometria-wyniku).
Obecny backend wymaga skończonych wartości wejścia; nie obsługuje bezpośrednio
ponownej rejestracji wczytanego aligned zawierającego NaN. Taka próba musi
zakończyć się czytelnym błędem bez utraty starego wyniku, dopóki nie zostanie
uzgodniona i zapewniona obsługa takich danych.

[Zapis MPP z wartościami i metadanymi](04-mpp-export.md#answer) rozstrzyga zapis
geometrii, metadanych, brakujących danych i ponowny odczyt. Ponowna rejestracja
zależy od faktycznie wczytanych danych, nie znacznika original/aligned;
obecne metody nadal odrzucają brakujące próbki.
[Opcje filmu AVI](05-avi-export.md) określą sposób przeniesienia podglądu do filmu.
Wielkości serii i kryteria jakości należą do [odbioru pierwszej wersji](06-acceptance.md).
