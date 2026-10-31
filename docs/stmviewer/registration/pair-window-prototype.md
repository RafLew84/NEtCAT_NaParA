# Okno dopasowania pary — prototyp nazw i układu

Data: 2026-10-31. Dotyczy [REG-01a](issues/01a-manual-alignment.md).
Status decyzji: **oczekuje na wybór użytkownika**; interfejs aplikacji niezmieniony.
Użytkownik uznał nazewnictwo A/B i „Zastosuj jako B” za niejasne oraz poprosił
skillem `prototype` o bardziej intuicyjną propozycję bez utraty funkcjonalności.

## Źródło prototypu

Osobna gałąź `prototype/stmviewer-pair-naming`, commit **`dd8b48f`**, baza `b0ef173`.
Kod i opis: `stmviewer/ui/pair_naming_prototype/` na tej gałęzi.
To lokalny prototyp HTML przyszłego okna PyQt6, nie zmiana technologii aplikacji.
Gałęzi prototypu nie scalać do produkcyjnej.

Bieżący podgląd: http://127.0.0.1:8783/?variant=C . Dolny pasek A/B/C i strzałki
przełączają układy bez resetowania pracy. Stan wyników jest tylko w pamięci.
Jedno polecenie w przygotowanym lokalnym worktree:

```bash
python /tmp/netcat-stmviewer-pair-naming-prototype/stmviewer/ui/pair_naming_prototype/serve.py
```

Serwer używa wyłącznie 127.0.0.1:8783 i otwiera przeglądarkę; zatrzymanie Ctrl+C.
Można również otworzyć index.html dwuklikiem. Jeśli lokalny katalog zostanie usunięty,
odtwórz worktree z gałęzi prototypu lub wyeksportuj sześć plików z commita `dd8b48f`.
Prototyp nie wymaga pakietów JS, instalacji przeglądarki ani zewnętrznych usług.

## Trzy warianty

| Wariant | Układ i pytanie |
| --- | --- |
| A — panel obok obrazu | Obraz i przewijane narzędzia po prawej. Czy wystarczy uporządkowanie bliskie obecnemu oknu? |
| B — narzędzia pod obrazem | Podgląd powyżej trzech obszarów: automatycznie, ręcznie, porównanie. Czy czynności są łatwiejsze do odnalezienia obok siebie? |
| C — porównywanie wyników | Karty wyników/metoda po lewej, ręczne sterowanie pod obrazem. Czy widoczne nazwy i XY wyjaśniają, co jest porównywane? |

Rekomendacja agenta: **C**, ze względu na problem rozumienia A/B.
To rekomendacja, nie zatwierdzona decyzja użytkownika; można łączyć elementy wariantów.

## Wspólna propozycja nazw

- A/B → **Wynik zachowany / Wynik bieżący**, z nazwą metody i przesunięciem.
- Przypnij B jako A → **Zachowaj bieżący do porównania**.
- Zastosuj jako B → **Zakończ korektę**; obok opis, że ustawia wynik bieżący
  do porównania i pozostawia film bez zmian.
- Odniesienie/Dopasowywana → **Klatka bazowa / Klatka przesuwana**, z numerami.
- Oblicz parę → **Dopasuj automatycznie**; Anuluj próbę → **Przerwij obliczanie**.
- Koryguj wybraną próbę → **Popraw wybrany wynik ręcznie**.
- Przywróć początek → **Cofnij wszystkie ruchy**, z widocznym początkowym XY.
- Odrzuć edycję → **Anuluj korektę**.
- Przed/Po → **Bez przesunięcia / Z dopasowaniem**.
- Przełącz obrazy → **Pokaż klatkę bazową / Pokaż klatkę przesuwaną**.
- Dopasuj (zoom) → **Pokaż cały obraz**.

Oba wyniki mogą być ręczne albo automatyczne. Zachowanie bieżącego kopiuje go
w miejsce wyniku zachowanego. Zakończenie korekty ustawia nowy bieżący, nie
nadpisuje zachowanego. Szczegóły metody, źródła i jakości pozostają dostępne.

Zachowano kontrolki pary, pięciu metod, Deep/wag/urządzenia, przerwania i błędu,
ręcznego startu/kopii/kroku/resetu/anulowania/zakończenia, wyboru obu wyników,
warstw, nakładki, przesunięcia, zoomu/przesuwania, gamma/proporcji i części wspólnej.
Nie dodano funkcji zastosowania do całego filmu: wymaga osobnej decyzji zakresowej.

## Oględziny i ograniczenia

W Qt WebEngine otwarto wszystkie warianty przy 1360 × 1000 oraz B przy 980 × 850.
Obejrzano zrzuty; wykonano obliczenie demonstracyjne, zachowanie wyniku, ręczne
kroki, zakończenie i wybór wcześniejszego wyniku. Brak błędów JavaScript i poziomego
przepełnienia w sprawdzonych rozmiarach. Po oględzinach poprawiono rozmiar płótna;
audyt odczytowy funkcjonalności doprecyzował nazwy przełączania obrazów i opis
zakończenia korekty. Uruchomiono lokalny serwer i otwarto stronę w przeglądarce.

Obrazy to syntetyczny cpu.mpp, wspólnie przeskalowany do uint8. Algorytmy, błędy,
czas pracy i dostępność urządzenia są symulowane; przesuwanie i prezentacja obrazu
działają. To sprawdzenie interfejsu, nie jakości rejestracji ani produkcyjnego Qt.
Nie dodawano testów prototypu ani nie uruchamiano pełnego zestawu aplikacji.
Zrzuty i raport oględzin pozostają lokalnie w `data/registration-pair-ui-prototype/`.

REG-01a nadal oczekuje na odbiór, REG-02 pozostaje zablokowany. Kolejna zmiana
produkcyjnego okna powinna wynikać z wyboru użytkownika i zachować istniejące kontrakty.
