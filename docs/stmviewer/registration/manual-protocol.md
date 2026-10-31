# Wspólny protokół ręcznej oceny rejestracji

Dotyczy każdego [ticketu REG](README.md). Próba jest wykonywana w rzeczywistej
aplikacji, po testach automatycznych i przed kolejnym etapem.

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
| `data/MOVIE_4.mpp` | 1→2, 33→34, 120→121 | Początek i pary z rozbieżnymi estymatami w rozpoznaniu |
| `data/MOVIE_8.mpp` | 1→2, 16→17, 56→57 | Znany reproduktor, inny przebieg przesunięcia, trudna para |
| `tests/stmviewer/fixtures/registration/cpu.mpp` | 1→2, 2→3 | Łatwy wzorzec, znane przesunięcia w różnych kierunkach |

Kontrola wejść: SHA-256 MOVIE_4 i MOVIE_8 są w
[raporcie rozpoznania](../registration-difficult-movies.md#dane).
Dodatkowo para 2→3 MOVIE_4 dla Deep Matcher i MOVIE_8 dla ECC sprawdza
zachowanie po znanym błędzie obecnych backendów; nowe metody nie muszą go powielać.
Wyniki wzorca cpu: do nałożenia na kolejną klatkę względem poprzedniej
(+2,−1) oraz (−3,+2); skumulowane względem pierwszej: (0,0), (+2,−1), (−1,+1).
Opis i generator: [próba CPU](../cpu-registration-manual.md).

## Warunki porównania

1. Otwórz oryginał. Zapisz commit, film/SHA, pary źródłowe i metodę.
   Dla przyjętego wcześniej wyniku kliknij **Zachowaj do porównania**.
   Nowy wariant będzie **Wynikiem bieżącym**, poprzedni — **Wynikiem zachowanym**.
   Zmieniaj jedną badaną rzecz; zanotuj różnice ustawień i masek.
2. W podglądzie pary ustaw gamma 1 i proporcje pikselowe. Zakres jasności
   ustal wspólnie z oryginalnej pary i zachowaj dla obu wyników, nie przeliczaj osobno
   po dopasowaniu. Późniejsza zmiana gamma działa jednakowo na oba warianty.
3. Porównuj w układzie tej samej źródłowej klatki odniesienia, z tym samym
   zoomem i punktem zakotwiczenia. Nie dopasowuj każdego wariantu osobno do
   okna. Padding i białe marginesy nie są strukturami próbki.
4. W każdej parze wybierz co najmniej trzy rozpoznawalne fragmenty w różnych
   częściach obrazu, jeśli takie istnieją. Zapisz prostokąty w pikselach
   original oraz krótki opis struktury. Do REG-06 zapis może być ręczny
   w karcie próby; REG-06 umożliwi wydzielenie ich w aplikacji.
5. Oddziel fragmenty użyte do dopasowania od fragmentów kontrolnych.
   Jeżeli aktualny algorytm używa całego obrazu, zapisz, że kontrola nie jest
   niezależna. Trzy znane cropy MOVIE_8 1→2 służą regresji rozpoznanego
   przypadku; nie są nowym niezależnym zbiorem walidacyjnym.
   W REG-07 dodaj także pary/fragmenty niewykorzystane wcześniej do wyboru
   ustawień. Wielokrotne oglądanie tej samej checklisty jest kontrolą regresji,
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

Sam status backendu, liczba pasujących fragmentów, gładkość trajektorii,
wielkość aligned albo zgodność pętli klatek nie dowodzą poprawności.
Próg 3 px dotyczy istniejącego reproduktora MOVIE_8 1→2; nie przenosimy go
na ocenę całej klatki ani całych filmów. Dokładność fizyczna nie jest znana.

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

## Karta odbioru każdego ticketu

Realizujący tworzy kartę w `docs/stmviewer/registration/reviews/REG-XX.md`.
Ścieżki do dużych wyników i zrzutów mogą wskazywać lokalne `data/`; nie dodajemy
filmów pomiarowych do Git. Nie wpisujemy rezultatów przed wykonaniem próby.

```text
Ticket / data / osoba / system:
Commit wyniku zachowanego / bieżącego:
Film + SHA / numery źródłowe par:
Metoda i ustawienia wyniku zachowanego / bieżącego / maski:
Dla próby ręcznej: pochodzenie / początkowe XY / korekta / końcowe XY:
Gamma / zakres jasności / proporcje / zoom:
Fragmenty estymacji / fragmenty kontroli / czy kontrola niezależna:
Funkcja: działa | usterka | niewykonane
Jakość XY dla każdej pary i fragmentu: lepiej | podobnie | gorzej | niejednoznacznie
Resztkowy tearing: opis osobno
Pełny film / przerwanie / czas / obserwowane zasoby:
Uwagi i ścieżki zrzutów:
Decyzja użytkownika: przyjęte | poprawić | odrzucić wariant | odłożyć
Ograniczenia i warunki przejścia dalej:
```

Ticket narzędziowy może mieć wynik „bez zmiany jakości danych”: jego celem
jest wierny podgląd lub zapis, nie nowy algorytm. Dla ticketów metodycznych
akceptacja wymaga rzeczywistej oceny jakości; po braku poprawy wybór kolejnego
kroku należy do użytkownika. Puste pole decyzji pozostawia `ready-for-review`.
