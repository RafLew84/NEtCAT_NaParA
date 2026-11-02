# 20: Zachowaj wspólny katalog typów struktury w serii

**ID:** SD-V4-20

**What to build:** Użytkownik tworzy katalog z wybranego zakresu serii, stosuje go do kolejnych klatek i widzi te same identyfikatory typów dla tej samej struktury, przy osobnych orientacjach i lokalnych domenach. Katalog oraz wynik można zapisać w projekcie.

**Blocked by:** [08: Przelicz zakres lub całą serię](08-analyze-series.md), [13: Zapisz projekt i otwórz wynik bez ponownych obliczeń](13-save-open-project.md), [16: Zobacz kierunek, rozstaw i jakość geometrii na obrazie](16-inspect-local-geometry.md).

**Status:** deferred — dalszy etap po ocenie stabilności opisu; obecnie niewybrany do wykonania.

**Warunek wyboru:** Wskazać jedną metodę opisu i porównania, która zachowuje typ przy obrocie/przesunięciu i powtarzalnych małych zaburzeniach oraz rozróżnia wybrane różne struktury. Przed wykonaniem zapisać wyniki tych sprawdzeń i tolerancje. Nie trzeba kończyć wszystkich prób 17–19.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady rozszerzeń](README.md#rozszerzenia).

## Kryteria akceptacji

- [ ] Użytkownik jawnie wybiera zakres budowy katalogu; model jest następnie zamrożony podczas analizy kolejnych klatek. Przełączenie obrazu nie dopasowuje katalogu ponownie ani nie zmienia znaczenia kolorów.
- [ ] Typ jest niezależny od obrotu i jednolitego przesunięcia, zgodnie ze słownikiem projektu. Orientacja, robocza klasa v0.4, typ struktury i lokalny identyfikator domeny są osobnymi polami; dawnych q/w/e/r/t nie przemianowuje się automatycznie na fizyczne typy.
- [ ] Widok Typy używa wspólnej legendy serii, a Domeny zachowuje lokalne instancje. Dwie domeny o tym samym typie mogą być rozdzielone przerwą lub granicą niedopasowania. Kolor typu nie oznacza śledzenia konkretnej domeny w czasie.
- [ ] Rozpoznany porządek bez zgodnego wzorca ma status nieznanego typu/kandydata; szum i brak danych nie tworzą nowych typów. Kryterium zgodności i minimalne poparcie są jawne i zapisane w katalogu.
- [ ] Jawne Rozszerz katalog analizuje wskazany zakres i tworzy nową wersję dopiero po spełnieniu kryteriów dla kandydatów. Dotychczasowe typy zachowują identyfikatory, a historyczne wyniki wersję katalogu. Nie wykonuje się ukrytego scalenia lub przenumerowania; nierozstrzygnięty konflikt pozostaje opisany.
- [ ] Projekt z 13 przechowuje wybrany katalog, jego opis metody i wersję wraz z przypisaniami. Ponowne otwarcie odtwarza wynik bez dopasowania lub modelu zewnętrznego; wymagania kontynuowania obliczeń są odrębne od podglądu.
- [ ] Testy sprawdzają obrót, jednolite przesunięcie, odrębną strukturę, słabe dane, zmianę kolejności klatek przy zamrożonym katalogu, rozszerzenie bez przenumerowania i zapis/odczyt. Ocena wspólnych typów nie zastępuje oceny granic domen.
- [ ] Instrukcja zawiera rzeczywiście wykonany zakres testu GUI, testy automatyczne i przypadki wymagające dalszego odbioru. Sprawdzono limit kodu i testów 1000/1500 linii.

## Test ręczny użytkownika

1. Wybierz zakres budowy katalogu w dostarczonym przykładzie, utwórz go i przeanalizuj kolejne klatki. Obrócone oraz przesunięte kopie tej samej struktury mają zachować typ przy osobnej informacji o orientacji.
2. Przełącz Typy/Domeny na dwóch rozdzielonych fragmentach tej samej struktury. Typ jest wspólny, identyfikatory domen lokalne; nie ma sugestii śledzenia obiektów.
3. Otwórz przykład nowej struktury i szumu. Pierwszy może zostać kandydatem, drugi nie powinien tworzyć typu. Wykonaj jawne rozszerzenie i sprawdź zachowanie wcześniejszych identyfikatorów oraz wyników.
4. Zapisz projekt, zamknij aplikację i otwórz zapis bez oryginalnych źródeł. Katalog, kolory i przypisania mają odtworzyć się bez nowych obliczeń.

## Granice zadania

Jeden wybrany opis i katalog w obrębie projektu. Nie obejmuje automatycznego uzgadniania katalogów między różnymi materiałami, śledzenia domen w czasie ani dowodzenia fizycznej tożsamości faz. To rozszerzenie wspólnego modelu serii, nie ponowna implementacja ręcznego K lub Auto z 07/12.
