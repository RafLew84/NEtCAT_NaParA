# Wspólny protokół ręcznej oceny rejestracji

Dotyczy każdego [ticketu REG](README.md). Próba jest wykonywana w rzeczywistej
aplikacji, po testach automatycznych i przed kolejnym etapem.

**Odłożenie REG-06 — 2026-10-31:** na życzenie użytkownika pomijamy na razie
wydzielanie fragmentów kontrolnych w aplikacji. Nie jest to warunek odbioru
REG-07 ani dalszych etapów. Zachowujemy oględziny struktur i zapis ograniczeń;
brak niezależnej kontroli oznacza brak takiej oceny, a nie zerowy błąd.

## Uruchomienie i materiały

Z katalogu `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Przygotowanie środowiska na obu systemach: [instrukcja](../README.md#uruchomienie).
Dane pomiarowe pozostają lokalne. Realizujący ticket zapewnia wszystkie
dodatkowe wzorce/generatory; użytkownik nie tworzy binarnego MPP ręcznie.

| Dane | Stałe pary źródłowe, numerowane od 1 | Cel |
| --- | --- | --- |
| `data/MOVIE_4.mpp` po usunięciu źródłowych 1 i 2 | 3→4, 33→34, 120→121 | Początek właściwej serii i pary z rozbieżnymi estymatami |
| `data/MOVIE_8.mpp` | 1→2, 16→17, 56→57 | Znany reproduktor, inny przebieg przesunięcia, trudna para |
| `tests/stmviewer/fixtures/registration/cpu.mpp` | 1→2, 2→3 | Łatwy wzorzec, znane przesunięcia w różnych kierunkach |

**Korekta wejścia MOVIE_4 — 2026-10-31:** użytkownik potwierdził, że pierwsze
dwie klatki należą do późniejszej części eksperymentu i błędnie dołączono je do
filmu. Po otwarciu MOVIE_4 usuń w aplikacji pierwszą klatkę, a następnie ponownie
pierwszą, **przed rejestracją**. Zostają 362 klatki: źródłowe 3–364.
Źródłowy MPP pozostaje bez zmian. Przy braku innych usunięć bieżąca pozycja i
odpowiada źródłowej i+2; np. źródłowa para 33→34 jest bieżącą parą 31→32.
Nowe Rejestruj wyznacza odniesienie na źródłowej klatce 3. Samo usunięcie klatek
z gotowego aligned zachowuje jego dawną geometrię, więc nie zastępuje przeliczenia.

Do porównań metod używaj identycznego składu serii. Historyczne wyniki pełnych
364 klatek nie są bezpośrednią bazą poprawionej serii. Miejsca dodatkowej kontroli
Deep Matcher wskazane przez użytkownika są w [karcie REG-02](reviews/REG-02.md#movie_4--obserwacje-użytkownika);
użytkownik potwierdził numerację po usunięciu dwóch klatek. Pary źródłowe
do dodatkowej kontroli: **31→32, 37→38, 46→47→48, 63→64, 96→97→98→99**.
Oględziny pierwszych 100 obejmują źródłowe 3–102; granica bieżącej 150 to źródłowa 152.

Kontrola wejść: SHA-256 MOVIE_4 i MOVIE_8 są w
[raporcie rozpoznania](../registration-difficult-movies.md#dane).
Dodatkowo źródłowa para 2→3 MOVIE_8 dla ECC sprawdza zachowanie po znanym
błędzie backendu; nowe metody nie muszą go powielać. Dawny przypadek Deep Matcher
MOVIE_4 2→3 dotyczy błędnie dołączonej klatki i nie należy do poprawionej serii.
Wyniki wzorca cpu: do nałożenia na kolejną klatkę względem poprzedniej
(+2,−1) oraz (−3,+2); skumulowane względem pierwszej: (0,0), (+2,−1), (−1,+1).
Opis i generator: [próba CPU](../cpu-registration-manual.md).

## Warunki porównania

1. Otwórz oryginał. Zapisz commit, film/SHA, pary źródłowe i metodę.
   Dla przyjętego wcześniej wyniku kliknij **Zachowaj do porównania**.
   Nowy wariant będzie **Wynikiem bieżącym**, poprzedni — **Wynikiem zachowanym**.
   Zmieniaj jedną badaną rzecz; zanotuj różnice ustawień.
2. W podglądzie pary ustaw gamma 1 i proporcje pikselowe. Zakres jasności
   ustal wspólnie z oryginalnej pary i zachowaj dla obu wyników, nie przeliczaj osobno
   po dopasowaniu. Późniejsza zmiana gamma działa jednakowo na oba warianty.
3. Porównuj w układzie tej samej źródłowej klatki odniesienia, z tym samym
   zoomem i punktem zakotwiczenia. Nie dopasowuj każdego wariantu osobno do
   okna. Padding i białe marginesy nie są strukturami próbki.
4. W każdej parze wybierz co najmniej trzy rozpoznawalne fragmenty w różnych
   częściach obrazu, jeśli takie istnieją. Zapisz prostokąty w pikselach
   original oraz krótki opis struktury w karcie próby. Nie wymaga to edytora
   kontroli w aplikacji; jego dodanie pozostaje w odłożonym REG-06.
5. Zapisz, czy oglądane fragmenty uczestniczyły w dopasowaniu. Jeżeli
   aktualny algorytm używa całego obrazu, ocena tych struktur jest zależna.
   Bez wydzielonej kontroli zapisujemy brak niezależnej oceny; nie wymagamy
   wdrożenia REG-06 w ramach bieżącego ticketu. Trzy znane cropy MOVIE_8 1→2
   służą regresji rozpoznanego przypadku; nie są nowym niezależnym zbiorem
   walidacyjnym.
   W kolejnych ticketach algorytmicznych dodaj także pary/fragmenty
   niewykorzystane wcześniej do wyboru ustawień. Wielokrotne oglądanie tej samej checklisty jest kontrolą regresji,
   ale samo nie stanowi końcowej walidacji na niewidzianych danych.
6. Przełączaj **Klatkę bazową** i **Klatkę przesuwaną** albo użyj nakładki. Oceniaj
   położenie tych samych konturów/szczegółów we wspólnej ważnej części.
   Jeśli nie można rozpoznać tej samej struktury, zapisz „niejednoznacznie”.
7. Oddziel globalne XY od resztkowej różnicy góra/środek/dół. Molekuła może
   rzeczywiście się przemieścić, a domena zmienić. Nie uznajemy automatycznie
   każdej zmiany próbki za błąd rejestracji. Kierunek dryfu może się zmieniać.
8. Dla ticketów algorytmicznych wykonaj też rejestrację całych obu filmów,
   odtwórz wynik i zatrzymaj się w dodatkowych podejrzanych miejscach.
   Jeżeli metoda nie daje pełnego wyniku, zapisz parę i przyczynę; nie pomijaj
   jej po cichu. Zapis „nie udało się” jest wynikiem próby, nie jej zaliczeniem.
9. Sprawdź anulowanie i zachowanie poprzedniego aligned. Dla nowej metody
   sprawdź również zapis małego kompletnego wyniku MPP+metadane i AVI oraz
   powrót do podglądu. Nakładki diagnostyczne nie trafiają do filmu pomiarowego.

**Odbiór REG-07:** zapis i odczyt sesji sprawdzamy przez ponowne uruchomienie
programu, otwarcie samego `.stmsession` bez źródeł i modelu oraz kontynuowanie
ręcznej korekty i eksportu. Wymagamy zachowania próbek, geometrii, zastosowanych
nadpisań i widoku; nie oczekujemy zmiany jakości XY ani tworzenia prób A/B.

**Wyjątek zakresu REG-08a/08b:** te dwa etapy dodają podgląd kandydata grafu,
porównanie z bazą i rozszerzenie zapisu sesji, lecz jeszcze nie stosują go do filmu.
W ich odbiorze
MPP/AVI muszą zachować wcześniejszy aktywny aligned, także podczas oglądania
nowej próby. Otwarcie całej sesji przywraca jej zapisany aktywny aligned;
nie promuje niezastosowanego kandydata grafu. Eksport grafu i jego ręczne korekty
należą do REG-08c. Pozostałe nowe metody REG-10–12 korzystają już z tego zastosowania.

**Braki w grafie:** lokalny brak dopasowania jest zapisaną brakującą relacją.
Pełny graf może mieć wynik przez inne połączenia; rozłączny pozostaje diagnozą.
Odmowy, mosty i brak nadmiarowej weryfikacji pozostają w raporcie. Błąd systemu,
zasobów/solvera lub anulowanie nie udają braków lokalnych. Ta polityka dotyczy
nowej metody grafowej i nie zmienia zachowania obecnego łańcucha po błędzie.

Sam status backendu, liczba pasujących fragmentów, gładkość trajektorii,
wielkość aligned albo zgodność pętli klatek nie dowodzą poprawności.
Próg 3 px dotyczy istniejącego reproduktora MOVIE_8 1→2; nie przenosimy go
na ocenę całej klatki ani całych filmów. Dokładność fizyczna nie jest znana.

## Porównania wieloklatkowe i nowe modele

Stosujemy [rozszerzony plan](README.md) i zapisane relacje REG-08a.
Każda para wyników porównywanych w danej próbie zmienia jeden element:

| Porównanie | Stałe elementy | Badana zmiana |
| --- | --- | --- |
| Łańcuch Deep / okno 3 albo 5, LS | Model, ustawienia, dostępne pomiary sąsiednie | Dodatkowe relacje i wspólne XY |
| Graf LS / Huber | Dokładnie ten sam zapisany zbiór relacji i kotwica | Odporność solvera |
| Okno / okno+dalsze odniesienia (REG-08d) | Stare pomiary, model, solver i progi | Nowe jawnie wybrane pary |
| Historyczny Deep / EfficientLoFTR | Lista kandydatów par, solver, widok | Cały estymator pary, jeśli agregacja jest różna |
| EfficientLoFTR / RoMa v2 | Agregacja korespondencji REG-10, pary, solver, widok | Model pary |
| EfficientLoFTR / MatchAnything-ELoFTR | Wspólna agregacja, pary, graf, widok | Wariant modelu i jego trening |

W porównaniu okna 3 z 5 zachowujemy wspólne pomiary. Nie liczymy ponownie
innych wartości dla tych samych par bez jawnego utworzenia nowego zestawu.
Jeśli łańcuch nie jest kompletny, nie uzupełniamy braków, aby uzyskać film A;
raport wskazuje ograniczenie porównania. Dla modeli niezbędne różnice
przygotowania wejścia i kwalifikacji punktów są jawne. Historyczny Deep i nowy
model z inną agregacją są porównaniem całych wariantów, nie izolacją samego modelu.

Pierwszy graf używa obecnego Deep bez ECC; nie przyznajemy wyższego poparcia
hybrydzie tylko dlatego, że zakończyła doprecyzowanie. Próba REG-05 porównuje
przestrzenne poparcie z bazowym Deep przez wyszukiwanie lokalnych wycinków.
REG-10 ustala odrębną wspólną agregację wektorów korespondencji nowych modeli,
z przestrzenną oceną poparcia według tych zasad. Nie uruchamia po cichu metody
wycinków REG-05. REG-11/12 zachowują agregację REG-10 i jej ustawienia.

REG-06 pozostaje odłożony. Jeśli zostanie wznowiony, kontrola obrazowa
oznaczona jako niezależna nie może wpływać na dobór krawędzi, ich wag, progów
ani modelu w tej samej próbie. Już teraz nie przypisujemy niezależności
ocenie danych użytych przez model, również przez jego globalne cechy.
Do końcowej oceny dodajemy nowe przypadki. Znane problematyczne pary służą
rozwojowi i regresji, nie zastępują nowych danych walidacyjnych.

W REG-08a oprócz `cpu.mpp` realizujący dostarcza sesje testowe ze znanymi
grafami: poprawny ruch z nawrotami, pojedyncza zła relacja, brak z obejściem,
most, rozłączenie i spójny alias okresowy. Oddzielamy wzorce testujące model
na obrazach od prób testujących solver na podanych relacjach. Dodajemy
nieruchome pasy oraz różny ruch góry/dół; globalne XY nie ma udawać ich korekcji.

Przy rzeczywistych wagach zapisujemy wersję kodu i bibliotek, wariant/SHA-256
modelu, urządzenie i przygotowanie wejścia. Osobno mierzymy czas modelu,
solvera/renderowania, RAM i VRAM. Docelowe 16 GB wolnego RAM i NVIDIA CUDA
z 8 GB VRAM nie są zaliczone przez samą próbę na większym komputerze.
Metoda niedostępna lub odrzucona jakościowo pozostaje jawnym wynikiem próby;
nie przełączamy jej automatycznie na inną.

W REG-08c dodatkowo sprawdzamy ręczne nadpisanie różnicy globalnych XY grafu,
powtórzenie, dwie korekty i cofnięcie do bazy grafowej. Surowy d_ij i różnica
rozwiązania nie muszą być takie same. Ręczne poprawki nie uruchamiają solvera;
wcześniejsze diagnozy grafu odnoszą się do niezmienionej bazy.

## Ręczne dopasowanie — REG-01a

Wynik ręczny dotyczy sąsiedniej pary w oknie porównania. Wybierz **Ustaw ręcznie
od zera** albo **Popraw wybrany wynik ręcznie**, wykonaj ruchy i kliknij **Zakończ
korektę**. Ręczne XY staje się wynikiem bieżącym. Porównywanie dwóch wyników
jest opcjonalne: przed korektą można użyć **Zachowaj do porównania**, aby zachować
wynik początkowy. Następnie wybieraj karty **Wynik bieżący / Wynik zachowany**.
Obrazy nazywamy **Klatką bazową** i **Klatką przesuwaną**; karty oznaczają wyniki
dopasowania. Szczegóły są pod **Szczegóły wybranego wyniku**.

Zapisz początkowe XY, sumę korekt, końcowe XY oraz oglądane struktury. Krok
wynosi 1 piksel oryginału niezależnie od zoomu; +X w prawo, +Y w dół.
Przeciąganie przesuwa wspólny widok. Pełny aligned zachowuje swój wynik.
Przy braku zgodności różnych części obrazu zanotuj rozbieżność. Ręczny wybór
nie stanowi samodzielnego dowodu fizycznego dryfu ani niezależnej walidacji.
Szczegółowe próby, cofnięcie ruchów i anulowanie korekty opisuje [REG-01a](issues/01a-manual-alignment.md).

## Zastosowanie korekty do filmu — REG-02a

Funkcja jest wdrożona i odebrana: użytkownik potwierdził „testy manualne ok”
2026-10-31. Poniższy opis pozostaje protokołem kolejnych prób.
[Instrukcja próby](manual-movie-corrections-manual.md), [wyniki](reviews/REG-02a.md).
[REG-02a](issues/02a-manual-movie-corrections.md) rozdziela zakończenie próby pary
od jawnego **Zastosuj do filmu**. Punktem startu jest różnica skumulowanych XY
sąsiednich klatek z aktywnego pełnego wyniku. Zastąpienie przesunięcia pary zmienia
położenie jej klatki przesuwanej i dalszych klatek. Porównuj XY względem odniesienia;
nowy padding może zmienić położenie wszystkich obrazów w powiększonym płótnie.

Próbę zaczynamy na cpu.mpp z liczbami podanymi w tickecie. Potem stosujemy ją
na MOVIE_4, po usunięciu źródłowych 1 i 2 przed rejestracją. Pierwszy przypadek
użytkownika: bieżąca para 29→30, źródłowa 31→32. Po zastosowaniu sprawdzamy
sąsiedztwo pary, dalsze klatki, pochodzenie ręczne, brak oceny pewności,
cofnięcie korekty, anulowanie oraz mały eksport MPP/AVI z ponownym odczytem.
Zapis poprawionego filmu należy do REG-02a, samowystarczalna sesja z obrazami
i stanem zastosowanych korekt do REG-07.

## Karta odbioru każdego ticketu

Realizujący tworzy kartę w `docs/stmviewer/registration/reviews/REG-XX.md`.
Ścieżki do dużych wyników i zrzutów mogą wskazywać lokalne `data/`; nie dodajemy
filmów pomiarowych do Git. Nie wpisujemy rezultatów przed wykonaniem próby.

```text
Ticket / data / osoba / system:
Commit wyniku zachowanego / bieżącego:
Film + SHA / numery źródłowe par:
Metoda i ustawienia wyniku zachowanego / bieżącego:
Dla modeli: wersje / wariant i SHA-256 wag / urządzenie / przygotowanie wejścia:
Dla grafu: źródła i zbiór par / okno / kotwica / solver i próg / zakończenie:
Brakujące relacje / mosty / rozłączenie / niepewność:
Dla próby ręcznej: pochodzenie / początkowe XY / korekta / końcowe XY:
Gamma / zakres jasności / proporcje / zoom:
Oglądane fragmenty / udział w estymacji / dostępna kontrola lub brak niezależnej oceny:
Funkcja: działa | usterka | niewykonane
Jakość XY dla każdej pary i fragmentu: lepiej | podobnie | gorzej | niejednoznacznie
Resztkowy tearing: opis osobno
Pełny film / przerwanie / czas / obserwowane zasoby:
Czas modelu / solvera / renderowania / RAM / VRAM / status próby 8 GB:
Uwagi i ścieżki zrzutów:
Decyzja użytkownika: przyjęte | poprawić | odrzucić wariant | odłożyć
Ograniczenia i warunki przejścia dalej:
```

Ticket narzędziowy może mieć wynik „bez zmiany jakości danych”: jego celem
jest wierny podgląd lub zapis, nie nowy algorytm. Dla ticketów metodycznych
akceptacja wymaga rzeczywistej oceny jakości; po braku poprawy wybór kolejnego
kroku należy do użytkownika. Puste pole decyzji pozostawia `ready-for-review`.
