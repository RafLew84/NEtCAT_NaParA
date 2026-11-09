# SD-V4-22 — dzielenie i scalanie domen

2026-11-09. Gałąź `domains/interactive-v04-ui`, baza `128bcef`.
Implementacja w obecnym Panelu A z 21. Odbiór ręczny użytkownika pozostaje otwarty.

## Obsługa

W **netcat** uruchom `python -m stmdomains.main`, otwórz serię/projekt
i wynik klatki. **Edytuj domeny** otwiera panel boczny.

- **Podziel domenę**: lassem lub kliknięciami wybierz część jednej domeny,
  **Pokaż podgląd**, potem **Zastosuj**. Pozostała część zachowuje ID;
  wybrana otrzymuje nowe. Cała domena, kilka domen, puste zaznaczenie
  lub molekuły nieprzypisane nie tworzą podziału.
- **Połącz domeny**: wskaż przynajmniej jedną molekułę z każdej łączonej
  domeny. Operacja obejmuje **wszystkich** ich członków. Lista w panelu
  zawiera ID, klasy i pełne listy molekuł; można ją przewijać.
  W polu **Domena** wybierz ID, które ma pozostać. Podgląd pokazuje liczby
  przed/po; **Anuluj podgląd** nie zmienia wyniku.
- Podział zachowuje bieżącą klasę źródła. Scalenie wspólnej klasy zachowuje
  ją, a różnych klas daje **klasę nieustaloną** z jawnym ostrzeżeniem.
  Przypisywanie własnej klasy należy do 23. Klasy oryginału są zachowane.
- **Cofnij/Ponów** traktuje podział/scalenie jako pojedynczy krok.
  **Automatyczny przed korektą** pokazuje źródło wariantu. Kolejna analiza
  nie usuwa korekty ani jej oryginału. Sąsiednia klatka pozostaje bez zmian.

Przycisk podglądu, komunikat i zatwierdzanie są poza przewijaną listą,
także w oknie 1024×768. **Zakończ edycję** chowa panel, zachowując wynik.

## Reguła obszarów

22 operuje na **istniejącym obszarze** domeny w pikselach raw. Nie jest
nową metodą wykrywania domen ani potwierdzeniem porządku sieci.

Podział przypisuje każdy piksel dotychczasowej domeny do najbliższego
centrum jej członka: wybrane centra dostają nowy ID, reszta zachowuje
stary. Suma obszarów jest dokładnie równa źródłu, łącznie z jego dziurami;
inne domeny i tło nie zmieniają się. Pojedynczy członek może odziedziczyć
część już istniejącego obszaru. Nie tworzymy dla niego nowego wsparcia
regułą „minimum 3” z operacji tworzenia domeny w 21. Źródło bez obszaru
pozostawia obie części bez obszaru, z komunikatem i oznaczeniami punktowymi.

Scalenie jest dokładną sumą istniejących masek. Wymaga, aby wszystkie
wybrane domeny miały obszar, suma była **jedną składową 8-spójną**
(styk krawędzią lub rogiem pikseli), a każde centrum członka po zaokrągleniu
do piksela leżało we własnej masce źródłowej. Brak obszaru, przerwa lub
niewspierane centra dają odmowę. Nie wypełniamy dziur, nie poszerzamy
obszarów i nie dorysowujemy mostów. To konserwatywna reguła rastrowa,
zależna od rozdzielczości, a nie fizyczny test ciągłości molekularnej.
Ponowne scalenie części spójnego źródła z wyborem jego ID odtwarza
dokładnie obszar i członkostwo sprzed podziału.

Metadane historii zawierają źródłowe/docelowe ID, listy członków, klasy,
regułę geometrii i powiązanie z oryginalnym wynikiem. Nie zmieniają
innych klatek i nie renumerują pozostałych domen. Mechanizmy ochrony
pracy z 21 pozostają aktywne: **korekty tylko w pamięci sesji**,
zapis/eksport czeka na 24/25, zamknięcie wymaga decyzji o porzuceniu.

## Test ręczny użytkownika

1. Otwórz TTMAPP, oblicz klatkę 259 i wejdź w **Edytuj domeny**.
   Włącz centra i obszary; w razie potrzeby powiększ obraz. Lassem wybierz
   część jednej domeny, ustaw **Podziel domenę**, pokaż podgląd.
   Sprawdź dwa ID, niezmienioną sumę przypisań i klasę. Anuluj, następnie
   ponownie pokaż podgląd i zastosuj. Cofnij i ponów.
2. Ustaw **Połącz domeny**, wybierz po jednym członku obu części.
   W polu **Domena** jawnie wybierz ID oryginału. Lista ma obejmować
   wszystkich członków. Po zatwierdzeniu obszar i przypisania wracają
   do źródła. Sprawdź porównanie automatu, Cofnij/Ponów, raw/aligned,
   przejście na 260 i powrót. Inne domeny i klatki pozostają bez zmian.
3. W netcat utwórz dostarczony przykład:

   ```bash
   python -m stmdomains.tools.manual_partition_demo
   ```

   Otwórz `.scratch/stmdomains-ui-22/demo/partition-controls.stmdomains`.
   To **syntetyczna kontrola z zadanymi przypisaniami**, nie wynik detektora.
   Zawiera 3 klatki po 57 molekuł i instrukcję obok projektu.
4. Klatka 1: D7 ma 48 członków klasy A, oddzielna D11 ma 9 klasy B.
   Podziel część D7, następnie połącz ją z resztą, wybierając D7 jako cel.
   Suma pozostaje 57. Wybór całej D7 do podziału daje wyjaśnienie odmowy.
5. Klatka 2: stykające się D7/A i D9/B mają po 24 członków. Wskaż po
   jednym punkcie z lewej/prawej połowy sieci, wybierz scalenie i ID celu.
   Podgląd ma pokazać 48 członków i ostrzeżenie o klasie nieustalonej.
   Anuluj, powtórz, zastosuj, porównaj automat i cofnij.
6. Klatka 3: D7 i D9 rozdziela przerwa. Ta sama operacja ma dać odmowę,
   pozostawić 3 domeny i wyłączyć **Zastosuj**. Żaden most nie powstaje.

## Wykonane sprawdzenia autora

Interpreter: `/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python`.
Testy operacji i UI obejmują obszary, klasy, historię, anulowanie, odmowy,
izolację klatek, ponowną analizę oraz prawdziwe zdarzenia myszy Qt.
Końcowe wyniki regresji i przeglądu zostaną zapisane po ich zakończeniu.

Natywne Qt/X11 w netcat, **1024×768**, PASS: syntetyczna kontrola
57 przypisań, lasso 4 członków, podgląd/anulowanie/zastosowanie,
dokładne odtworzenie maski, mieszane klasy i odmowa połączenia przez przerwę.
TTMAPP259: **105/312 przypisań, 5 domen**, podział 4 członków D2
(62 członków) do D6 daje 6 domen; scalenie D2+D6→D2 odtwarza maskę
dokładnie. Cofnij/Ponów, porównanie, raw/aligned i izolacja klatki 260 PASS.
Obejrzano zrzuty; poprawiono widoczność ostrzeżeń w małym oknie.
Artefakty lokalne: `.scratch/stmdomains-ui-22/` (skrypt, zrzuty, raport JSON).

To sprawdzenie autora, **nie odbiór użytkownika ani ocena skuteczności
detekcji**. Źródłowe dane tylko odczytano. Bez nowych zależności,
wspólnych zmian i potrzeb integracyjnych poza scaleniem gotowych commitów.
