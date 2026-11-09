# SD-V4-24 — zapis korekt i wznowienie edycji

2026-11-09. Gałąź `domains/interactive-v04-ui`; baza `6b5820c`.
Odbiór ręczny użytkownika pozostaje otwarty.

## Obsługa

**Plik → Zapisz projekt… / Zapisz projekt jako…** pozwala wybrać:

- **Po korektach** — wynik bazowy (albo brak analizy), ręczne przypisania,
  maski, nazwy/kolory i ID klas oraz pełna historia Cofnij/Ponów.
- **Automatyczny** — wybrany przebieg bez ręcznych korekt.
- **Bez analizy i korekt** — obrazy, oznaczenia, widok i szkic parametrów.

Wynik po korektach obejmuje powiązane klatki i wspólne listy klas. Dotyczy to
również gotowej części przerwanego przebiegu. Zapis zachowuje cofnięte kroki,
które po otwarciu można ponowić. Wspólne scalenie klas pozostaje jednym
krokiem historii na wszystkich objętych klatkach. Oryginał jest dostępny
przez **Automatyczny przed korektą**. Przy pracy bez analizy ten widok
pozostaje bez wyniku automatycznego.

Przed zapisem trzeba zatwierdzić lub anulować podgląd. Zapisz jako zachowuje
poprzedni plik. Komunikat po zapisie podaje wybrany wynik i informuje o
pozostałych niezapisanych wariantach; w takim przypadku zamykanie po zapisie
nie następuje automatycznie. Zapisz pozostałą pracę osobno lub jawnie ją
odrzuć. Zamknięcie i otwarcie innych danych mają wybór Zapisz/Odrzuć/Anuluj.
Eksport ręcznych korekt nadal należy do ticketu 25.

## Test ręczny

Uruchom w środowisku `netcat`:

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz projekt z korektami albo utwórz własne domeny/klasy. Zmień nazwę
   klasy i cofnij zmianę. Zapisz z opcją **Po korektach**.
2. Zamknij i otwórz zapis. Obszary, członkostwo i legenda mają odpowiadać
   zapisanemu stanowi. **Ponów** odtwarza zmianę nazwy; **Cofnij** ją cofa.
3. Sprawdź obie klatki po wspólnym scaleniu klas. Jedno Cofnij przywraca
   wcześniejsze przypisania na obu. Porównaj wynik automatyczny.
4. Użyj Zapisz jako do drugiego pliku. Pierwszy ma nadal poprzedni stan.
5. Zrób korektę i zamknij okno: Anuluj zachowuje pracę, Zapisz zachowuje ją
   w projekcie, Odrzuć kończy bez zapisu. Anulowanie okna pliku nie zamyka
   programu. Błąd zapisu nie usuwa edycji ani historii.

Gotowe lokalne pliki próby agenta w `.scratch/stmdomains-ui-24/`:

- `control-after-undo.stmdomains`: wspólna klasa 9/7 członków w klatkach 1/2;
  Ponów wydziela jednego członka i daje 3 domeny na klatce 1. Cofnij podział,
  następnie Cofnij scalenie: A/B = 6/3 i 4/3.
- `ttmapp-259-260.stmdomains`: rzeczywiste klatki 259–260, K5, zapis po
  cofnięciu podziału klasy. Ponów odtwarza wydzielenie jednej molekuły.
- `without-analysis.stmdomains`: ręczna klasa i domena bez modelu;
  Automatyczny przed korektą pokazuje brak analizy.
- `corrupt.stmdomains`: celowo uszkodzony przykład. Otwarcie ma zgłosić błąd
  i zachować bieżącą pracę.

To lokalne artefakty, nie dane wersjonowane w Git.

## Wykonane sprawdzenia

- Netcat/offscreen: 19 testów interfejsu zapisu, historii i okna PASS.
- Walidacja pliku: błędne ID molekuł/klas/klatek, konflikt domeny, zakres
  i rewizje transakcji, pozycja historii; kontrola działa także przy
  prawidłowych sumach kontrolnych uszkodzonych danych.
- Natywne Qt/X11/netcat: rzeczywisty wybór wyniku w oknie zapisu, zapis,
  ponowne otwarcie, Cofnij/Ponów i Zapisz jako PASS. Kontrola 9/7 otwiera się
  po usunięciu wyłącznie wygenerowanych źródeł testowych. TTMAPP259–260:
  dokładna zgodność przypisań i rastrów, bazowo 7/5 domen; odczyt z zablokowanym
  dopasowaniem KMeans. Osobny przykład bez analizy i odmowa uszkodzonego
  projektu bez utraty otwartej pracy PASS. Źródeł użytkownika nie usuwano.
- Zrzuty GUI oraz `gui-report.json` w lokalnym katalogu próby. To kontrola
  trwałości i edycji, nie ocena jakości detekcji domen.

Pełna regresja, końcowe sprawdzenie typów, limitów plików i przegląd zostaną
uzupełnione po ich zakończeniu. Potwierdzenie użytkownika jest osobnym etapem.

## Format i ograniczenia

Kontener `.stmdomains` ma wersję 2; wersja 1 otwiera się z pustą historią.
Zawiera źródłowy MPP, oznaczenia, wybrany automat oraz niezależne stany
ręczne, rewizje list i globalną kolejność operacji. Identyczne rastry są
współdzielone po SHA-256. Nie stosuje pickle ani ponownego dopasowania.
Sumy kontrolne obejmują wszystkie części, zapis podmienia plik atomowo.

Odczyt wiąże korekty z osadzoną serią, zachowując ID i wersje. Uszkodzonego
członkostwa ani historii nie naprawia automatycznie. Nowa analiza nadal
nie dziedziczy korekt po numerach. Historia zwiększa wielkość projektu;
nie jest to archiwum wszystkich niezależnych prób ani eksport CSV/PNG.
