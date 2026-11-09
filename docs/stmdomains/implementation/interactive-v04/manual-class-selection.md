# Wiele zaznaczeń i łączenie fragmentów klasy

2026-11-09. Poprawka po zgłoszeniu do ręcznej edycji klas, baza `648aa4d`.
Odbiór ręczny użytkownika 24 wraz z poprawką zaznaczania i łączenia fragmentów potwierdzony 2026-11-09 dla wersji `1eb0356` („temty manualne ok”).

## Przyczyna i wynik

Każde zatwierdzenie zmiany klasy części domeny wydzielało nową domenę.
Kilka takich przypisań dawało kilka fragmentów tej samej klasy. Reguła
chroniła osobne domeny, ale brak narzędzi zaznaczania w oknie klas utrudniał
zebranie wyboru przed przypisaniem. Panel boczny był zasłonięty przez dialog.

W oknie **Klasy ręczne** są teraz **Kliknięcia / Lasso / Przesuwanie** oraz
**Dodaj / Odejmij / Zastąp wybór**. Przy pierwszym otwarciu okna klas wybierane
jest Dodaj do wyboru. Kilka kliknięć lub obrysów gromadzi jeden wybór;
nie zmienia to przypisań przed podglądem i zatwierdzeniem. Narzędzia są
zsynchronizowane z panelem bocznym i oknem podziału klasy.

**Przypisz do klasy — podgląd** zmienia klasę wskazanych molekuł. **Scal
klasy…** nadal służy połączeniu całych klas w zadanym zakresie klatek.

Opcja **Połącz stykające się domeny tej klasy** jest domyślnie wyłączona.
Po włączeniu łączy spójne grupy domen docelowej klasy osiągalne od
zaznaczenia. Działa również dla wcześniejszych fragmentów, których molekuły
już mają docelową klasę. To jawna korekta z podglądem, nie ponowne dopasowanie
modelu ani ponowna detekcja całej klatki.

Geometria korzysta z istniejących obszarów i tego samego kryterium styku
co Połącz domeny: 8-sąsiedztwo pikseli, spójna suma i wsparcie centrów.
Zachowywane jest najmniejsze ID grupy. Operacja nie dorysowuje mostów,
nie zmienia sumy obszarów i nie łączy przez przerwę. Rozdzielone obszary
tej samej klasy pozostają osobnymi domenami. Wybór może też przyłączyć
stykające się domeny tej klasy, których nie zaznaczono bezpośrednio — wynik
jest widoczny w podglądzie. Molekuły bez domeny zachowują ten stan po
przypisaniu klasy; nie powstaje dla nich obszar przez samo łączenie klas.

Całe przypisanie i opcjonalne połączenie to jeden krok Cofnij/Ponów.
Zapis projektu z 24 odtwarza ten krok i jego geometrię.

## Test ręczny

Przed restartem aplikacji zapisz bieżącą pracę jako projekt **Po korektach**.
Uruchamiaj i testuj w `netcat`: `python -m stmdomains.main`.

1. Otwórz **Edytuj domeny → Klasy ręczne…**. Wybierz **Kliknięcia** oraz
   **Dodaj do wyboru**. Kliknij kilka molekuł w głównym obrazie. Licznik
   powinien rosnąć; przypisania i liczba domen nie zmieniają się.
2. Przełącz na Lasso i dodaj obrys. Wcześniejsze punkty pozostają wybrane.
   Odejmij z wyboru usuwa wskazane punkty, Wyczyść wybór zeruje licznik.
3. Wybierz istniejącą klasę docelową. Kliknij **Przypisz do klasy — podgląd**,
   obejrzyj obraz i użyj **Zastosuj** tylko raz po zebraniu całego wyboru.
4. Dla wcześniej utworzonych małych fragmentów, np. C2–C7, wybierz ich
   molekuły, klasę C i zaznacz **Połącz stykające się domeny tej klasy**.
   Podgląd pokazuje liczbę domen przed/po. Styki mogą dać wspólną domenę,
   ale przerwy mają pozostać; nie wymuszaj jednej domeny dla całej klasy.
5. Zastosuj, Cofnij, Ponów. Zapisz projekt, otwórz go ponownie i sprawdź
   cofnięcie/ponowienie po otwarciu. Automat pozostaje dostępny do porównania.

## Wykonane sprawdzenia

- Minimalna reprodukcja: kolejne przypisania do B dawały różne domeny,
  a wspólne zaznaczenie jedną. Potwierdzono faktyczny podział członkostwa,
  nie jedynie problem podpisów. Testy nowego UI i łączenia były RED przed
  zmianą i GREEN po zmianie.
- **54 testy PASS / 34,44 s** w netcat/offscreen: ręczne klasy, domeny,
  kliknięcia i lasso, wspólne narzędzia, Cofnij/Ponów, okna 23a i zapis/odczyt.
- **mypy: 124 moduły PASS** (core/analysis/ui/io), `git diff --check` PASS.
- Natywne Qt/X11/netcat: kontrola 2 kliknięć z jednym przypisaniem; naprawa
  4→3 domen, zapis/odczyt i atomowe Cofnij/Ponów PASS. Rzeczywista klatka
  **TTMAPP268 K5**: 3 kolejno przypisane fragmenty połączone w jeden,
  **8→6 domen**, dokładnie zachowana suma obszarów i historia PASS.
  Sprawdzono czytelność dialogu po dodaniu narzędzi.
- 9 zmienionych/nowych plików Python; maksimum **384 linie**. Bez nowych
  zależności i zmian współdzielonych. Pełnej regresji nie powtarzano;
  wcześniejsze 645 PASS dotyczy wersji ticketu 24 przed tą poprawką.

Artefakty lokalne: `.scratch/stmdomains-class-selection/`, w tym
`gui-report.json`, zrzuty i `repaired.stmdomains`. To kontrola ręcznej edycji
i trwałości wyniku, nie ocena naukowej skuteczności wykrywania domen.
