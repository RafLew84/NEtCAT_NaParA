# Przeglądarka wyników przyszłych prób

Data: **2026-11-02**. Użytkownik wybrał prosty sposób oglądania wyników:
kolejne obrazy STM z oznaczonymi molekułami i ich przynależnością do domen.
Dotychczasowe rozbudowane galerie diagnostyczne są dla niego nieczytelne.
Ten dokument ustala prezentację przyszłych prób. **Aktualizacja SD-V4-04:**
działa natywna przeglądarka istniejącego wyniku v0.4 z końcowymi przypisaniami
molekuł — [uruchomienie i test ręczny](implementation/interactive-v04/acceptance-04.md).
Nie uruchomiono nowego eksperymentu. Obsługa wyników kolejnych metod będzie
korzystać z poniższych zasad.

## Podstawowy widok

- Jeden duży obraz STM, poprzednia/następna klatka oraz numer i wybór klatki.
  Wszystkie klatki zakresu próby są dostępne w kolejności, również bez wyniku.
- Małe, czytelne oznaczenia w rzeczywistych centrach zapisanych molekuł.
  Ten sam kolor oznacza tę samą domenę w danej klatce; szare oznaczenie
  oznacza molekułę bez przypisania. Oznaczenia nie zasłaniają obrazu.
- Krótka legenda domen i liczebności, np. „3 domeny · przypisano 87 z 312”.
  Liczebność dotyczy poprawnych oznaczeń w polu klatki, nie punktów siatki,
  i nie jest miarą trafności detektora.
- Powiększanie obrazu i włączanie/wyłączanie oznaczeń do sprawdzenia
  ich zgodności z molekułami. Widok zaczyna się od końcowego wyniku próby.

Dobór metody do pokazanego wyniku jest jawny. Jeżeli porównujemy metody,
prosty przełącznik zachowuje bieżącą klatkę i powiększenie. Wybór ziaren,
warstw, parametrów grafu, wykresy i porównanie przed/po odmowach należą do
osobnej diagnostyki. Otwierając wynik, użytkownik od razu widzi obraz
z przynależnością molekuł, bez konfigurowania eksperymentu.

## Znaczenie oznaczeń

Oznaczenia pochodzą z wejściowego zapisu molekuł; ten widok nie uruchamia
nowej detekcji. Współrzędne i ID muszą odpowiadać danej klatce, a obraz
i oznaczenia korzystać z tego samego przekształcenia geometrii.
Kolor odnosi się do konkretnej domeny, nie klasy wyglądu lub typu sieci.
Numery i kolory są lokalne dla klatki oraz wyniku; nie oznaczają śledzenia
tej samej domeny między klatkami. Wynik próby jest opisany jako eksperymentalny.

Przypisania bezpośrednio do molekuł odczytujemy po ID. Dla wyniku obszarowego
obowiązuje [reguła środka bboxa](issues/06-frame-statistics.md): środek
w niepewnej granicy lub konflikcie pozostawia molekułę nieprzypisaną.
Metoda pracująca na siatce musi dostarczyć jawną, sprawdzoną regułę przejścia
do przypisań molekuł, opisaną w protokole przyszłej próby. Sama zamiana
położeń punktów albo kolorowanie według najbliższego węzła nie wystarcza.
Istniejące mapowanie `nearest_grid_center_diagnostic` z 25/26 pozostaje
diagnostyką; zmiana prezentacji nie czyni go końcowym wynikiem.

Jeśli metoda nie przypisała żadnej molekuły, pokazujemy szare oznaczenia
i informację o zerowym wyniku. Gdy analizy lub mapowania nie wykonano,
pokazujemy „brak wyniku”, nie zero wykrytych domen. Przy częściowym zakresie
analizy oznaczenia poza nim pozostają widoczne, a zakres jest jawny;
braku wyniku nie przedstawiamy jako stwierdzenia braku domeny.
Przyczyna nieprzypisania może być dostępna po wskazaniu molekuły.

## Zastosowanie w przyszłych próbach

Przeglądarka jest podstawowym materiałem do obejrzenia wyniku. Raport
techniczny i metryki pozostają osobnym materiałem do oceny skuteczności.
Kontrola prezentacji obejmie zgodność ID i położeń, kolorów z zachowanymi
przypisaniami, liczników, nawigacji oraz stanów zero/brak/częściowy wynik.
Sprawdzenie przeglądarki nie zastępuje oceny poprawności znalezionych domen.

Precedensem są [zapisane przykłady z 15/16](saved-domain-examples.md),
które pokazują rzeczywiste centra molekuł. Wymaganie dotyczy kolejnych prób;
nie zmienia zamrożonych wyników 21–26 ani nie wybiera kolejnej metody.
Nie wymaga teraz przebudowy historycznych galerii lub implementacji
natywnego szkieletu aplikacji. Uwzględnia je [odbiór metod 13](issues/13-method-acceptance.md).
