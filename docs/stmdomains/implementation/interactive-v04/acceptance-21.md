# 21 — ręczna edycja domen, Panel A

2026-11-05. Implementacja `a61e1b2`, poprawki `47bafe0`, baza `4d32fbe`.
Gałąź `domains/interactive-v04-ui`, środowisko **netcat**.
**Odbiór ręczny użytkownika pozostaje otwarty.**

## Obsługa

**Edytuj domeny** nad obrazem otwiera panel po prawej. **Zakończ edycję**
chowa panel, przywraca miejsce przeglądarce i pozostawia korekty widoczne.
Panel obejmuje pionowo także część obok miniatur i liczników, dzięki czemu
w oknie 1024×768 dostępne są narzędzia, operacja i podgląd. Treść może się
przewijać; Zastosuj, Anuluj podgląd i historia pozostają na dole.

- **Lasso:** przytrzymaj lewy przycisk i obrysuj centra molekuł.
- **Kliknięcia:** wskazuj centra. Zastąp/Dodaj/Odejmij dotyczą zaznaczenia;
  Shift dodaje, Alt odejmuje, Ctrl przełącza zaznaczenie pojedynczego punktu.
- **Nowa domena / Dodaj / Usuń / Przenieś:** wybierz operację, ewentualnie
  domenę docelową, następnie **Pokaż podgląd → Zastosuj**. Podgląd pokazuje
  liczbę członków przed i po, docelową domenę i klasę. Anuluj przywraca wynik.
- **Cofnij/Ponów:** wspólna chronologiczna historia ręcznych operacji w sesji.
  Przycisk wskazuje klatkę i przechodzi do niej. Ctrl+Z / Ctrl+Shift+Z.
- Lista nad obrazem wybiera bieżący automat lub zachowaną korektę.
  **Automatyczny przed korektą** porównuje z dokładnym źródłem tej korekty,
  także gdy nowsza analiza już zastąpiła automat. Przy pracy bez analizy
  przełącznik pokazuje jawny brak wyniku automatycznego.

Wybór zachowuje ID przy zmianie zoomu i raw/aligned, a zmiana klatki go
czyści. Przeciąganie z wciśniętą Spacją oraz narzędzie Przesuwanie służą
nawigacji; odtwarzanie kończy edycję. Powrót do klatki zachowuje korekty.
Nowa analiza, katalog lub metoda nie przenosi korekt do nowego wyniku ani
nie nadpisuje ich. Kliknięcie Bazowa/Geometria/freud pokazuje wybrany automat;
poprawiony wariant pozostaje na liście.

## Pochodzenie i obszary

Edytujemy istniejące oznaczenia, bez dodawania lub przesuwania molekuł.
Każda należy najwyżej do jednej domeny. Przeniesienie z innej domeny jest
jawną operacją; pusta selekcja niczego nie tworzy. Usunięcie ostatniego
członka usuwa domenę, a Cofnij przywraca całość. Oznaczenia poza polem oraz
duplikaty są wyłączone także wtedy, gdy automat odmówił przed sprawdzeniem
geometrii. Wariant zachowuje źródłowe klasy, członkostwa i odmowy do porównania.
Wspólna źródłowa klasa zostaje tylko dla zgodnych członków; przy mieszaniu
lub nieustalonej klasie członka cała domena ma **klasę nieustaloną**.

Geometria ręczna nie uruchamia testu porządku. Domena potrzebuje co najmniej
trzech niewspółliniowych członków, aby otrzymać obszar. W przeciwnym razie
pozostają punkty i jawny komunikat o braku wsparcia. Obszar składa się
z komórek najbliższych centrów, ograniczonych do **0,8 mediany odległości NN**
aktywnych oznaczeń w pikselach oryginalnej klatki. Każdy aktywny punkt,
także nieprzypisany, rezerwuje swoją komórkę. Zapobiega to zajęciu centrów
sąsiedniej domeny albo dopisaniu sąsiadów. Raster jest przycięty do pola,
jednoznaczny i nie zmienia członkostw; brak domykania otworów i mostów przez
dalekie przerwy. Wybrane rozłączne grupy mogą mieć osobne fragmenty obszaru
tego samego ręcznego ID. Rozdzielenie domen jest zakresem 22.
Obrysy, centra, kolory i liczniki korzystają z tego samego wyniku/podglądu.

**Korekty są tylko w sesji.** Do wykonania 24/25 zapis i eksport są blokowane
przy obecności korekt lub podglądu; także publiczne API odmawia cichego
zapisania samego automatu. Zamknięcie/otwarcie innych danych pyta o utratę
korekt i pozwala anulować. Nie zmieniono formatów projektu ani eksportu.
Limit edycji: obraz 2D do 4 mln pikseli i do 3000 oznaczeń, jak wejście analizy.

## Test ręczny użytkownika

Uruchom z katalogu repozytorium:

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`, przejdź do klatki 259
   i kliknij Dopasuj. Włącz Centra, następnie Edytuj domeny. Panel pojawia
   się tylko w edycji; w razie potrzeby wypróbuj rozmiar okna 1024×768.
2. Bez analizy zaznacz kilka molekuł kliknięciami i lassem. Zmień tryb
   Dodaj/Odejmij. Sprawdź licznik oraz zachowanie wyboru po zoomie i zmianie
   Oryginał/Wyrównany. Nowa domena → Pokaż podgląd; Anuluj usuwa podgląd.
   Powtórz i Zastosuj: domena ma oznaczenie ręczne, a automat pozostaje nieobecny.
3. Zakończ edycję: panel znika, domena pozostaje widoczna. Otwórz ponownie,
   dodaj sąsiednich członków i usuń jednego. Cofnij/Ponów przywraca członkostwa,
   obszar, klasę oraz liczniki. Dla pojedynczego członka brak obszaru jest jawny.
4. Utwórz drugą domenę. Dodaj do pierwszej członka drugiej: pojawia się
   wyjaśnienie wymagające Przenieś. Przenieś i zatwierdź; nie ma podwójnego
   członkostwa. Usuń ostatnich członków jednej domeny, a następnie Cofnij.
5. Edytuj klatkę 260, wróć do 259 i sprawdź opis przycisku Cofnij. Najpierw
   cofa operację 260 i przechodzi tam, potem operację 259. Ponów zachowuje
   kolejność. Klatki bez operacji nie otrzymują automatycznie korekt.
6. Uruchom analizę. Zachowana ręczna praca pozostaje dostępna na liście;
   wybierz bieżący automat i utwórz jego osobną korektę. Porównaj z
   Automatyczny przed korektą. Nowa analiza nie usuwa starych wariantów.
7. Z korektą spróbuj zamknąć program lub otworzyć inne dane. Anuluj zachowuje
   pracę. Zapis/eksport wskazuje ograniczenie; nie zapisuje mylącego automatu.

Kontrole dodatkowe można wygenerować w netcat:

```bash
python -m stmdomains.tools.analysis_demo .scratch/stmdomains-ui-21/demo
```

Otwórz `series.moltrack.json` z tego katalogu. Klatka 1 ma bliski duplikat;
po analizie 2 ma zero domen; 3 nie ma oznaczeń; 4 ma cztery punkty, za mało
do klas K5, lecz można z nich utworzyć domenę ręczną. Sprawdź pracę bez
analizy, po odmowie i przy wyniku zerowym. Nie jest to ocena skuteczności.

## Wykonane sprawdzenia autora

Testy publicznych operacji, historii i GUI: **17 celowanych PASS / 3,85 s**
po poprawkach, mypy **110 modułów PASS**. Końcowa pełna regresja: **572 testy PASS / 262,28 s**.
Pierwsza pełna regresja: 569 PASS / 1 FAIL / 263,52 s. Pozostały test obrysu
trafiał o jeden piksel obok kosmetycznej linii przy nowej skali widoku.
Diagnoza pokazała poprawny obrys w sąsiednim pikselu, bez ruchu obrazu;
sprawdzanie ograniczono do tolerancji jednego piksela rasteryzacji.
Renderer nie wymagał zmiany. Test nadal sprawdza widoczność i wybór obrysu.

Natywne GUI Qt/X11 w **netcat** na TTMAPP259–260, okno **1024×768**, po
poprawkach: zapisany automat 105/312 i 5 domen; 8 rzeczywistych kliknięć
utworzyło D6, 113/312 i 6 domen. Lasso wybrało 3 centra. Sprawdzono
podgląd/anulowanie, zastosowanie, chowanie panelu, dokładny powrót do
automatu, Cofnij/Ponów, izolację klatek, zoom i raw/aligned oraz anulowanie
zamknięcia. Brak błędów. Obejrzano zrzuty małego okna. To sprawdzenie autora,
**nie odbiór użytkownika i nie pomiar wykrywalności domen**.

Lokalne raporty i zrzuty: `.scratch/stmdomains-ui-21/`.
[Przegląd Standards/Spec](review-21.md). Zmieniono 16 plików kodu/testów;
maksimum 874 linie, wszystkie poniżej 1000. Bez nowych zależności,
zmian we wspólnych aplikacjach i potrzeb integracyjnych z tego zadania.
