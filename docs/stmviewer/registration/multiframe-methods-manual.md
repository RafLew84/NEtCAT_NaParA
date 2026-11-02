# REG-08e — wybór metody w dopasowaniu wieloklatkowym

Status: **done**; użytkownik potwierdził „testy manualne ok” 2026-11-02.
[Ticket](issues/08e-multiframe-methods.md), [wyniki automatyczne](multiframe-methods-results.md).

Z katalogu `/home/rlew/projekty/NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Przed ponownym uruchomieniem programu zapisz własną sesję.

## Gotowe dane

- Mały wzorzec: `/tmp/reg08e-cpu-known-v4/known.mpp`.
- MOVIE_4, Optical Flow: `/tmp/reg08e-movie4-v1/optical_flow_median-window3/candidate.stmsession`.
- MOVIE_4, Deep: `/tmp/reg08e-movie4-v1/deep_matcher_translation-window3/candidate.stmsession`.
- MOVIE_8: analogiczne pliki w `/tmp/reg08e-movie8-v1/`.

Sesje MOVIE_4 mają już usunięte dwie pierwsze klatki. Otwórz je przez
**Otwórz sesję…**, następnie **Dopasowanie wieloklatkowe…**.
Wyniki są zapisane; ich oglądanie i zastosowanie nie wymagają ponownego pomiaru.
W próbach z domyślnym limitem 200 Huber pozostał niekompletny dla Deep/MOVIE_4
i Optical Flow/MOVIE_8. LS jest kompletny we wszystkich czterech sesjach.

## Podstawowa próba

1. Wczytaj film albo dotychczasową sesję i otwórz **Dopasowanie wieloklatkowe…**.
2. W polu **Metoda dopasowania par** wybierz np. **Optical Flow**. Ustaw
   okno 3 lub 5 i kliknij **Oblicz kandydata grafu**. Zmiana samego wyboru
   nie zmienia poprzedniego wyniku; po obliczeniu podpis musi podawać nową metodę.
3. Obejrzyj film ze wspólnymi położeniami LS. Oblicz **nowy wariant Hubera**
   na zapisanych pomiarach i porównaj wynik. Huber nie uruchamia ponownie
   Optical Flow ani innego algorytmu dopasowania par.
4. Jawnie wybierz kompletny LS/Huber i kliknij **Zastosuj wynik do filmu**.
   Gotowy aligned jest dostępny w głównym oknie, do korekt i eksportu.
   Niekompletny Huber pozostaje diagnostyką z powodem odmowy zastosowania.
5. Powtórz z Phase, ECC, Tile+RANSAC i korelacją bez normalizacji.
   Dla CPU wagi modelu nie są wymagane, a kontrolki Deep są ukryte.
6. Dla Deep, Deep+ECC i Deep+lokalnych fragmentów wskaż lokalne wagi
   oraz urządzenie. Brak wag lub biblioteki wyjaśnia niedostępność tej metody.
   Program niczego nie pobiera i nie podstawia innego algorytmu po błędzie.

Wybrana metoda w głównym oknie dotyczy rejestracji sąsiednich klatek.
W oknie wieloklatkowym obowiązuje widoczny tam wybór. Dotychczasowy graf
Deep otwiera się nadal jako Deep, niezależnie od późniejszej zmiany wyboru.

## Sesja, korekta i przerwanie

- Zapisz sesję z aktywnym aligned oraz nowym niezastosowanym kandydatem innej
  metody. Po ponownym otwarciu oba mają zachować właściwe opisy i położenia.
- Zastosuj wynik, wykonaj korektę ręczną i sprawdź **Przywróć zachowany wynik**.
  Mały MPP i AVI mają odpowiadać aktywnemu filmowi. MPP z towarzyszącymi
  metadanymi zachowuje metodę, solver, geometrię i korekty.
- Uruchom pomiar i kliknij Anuluj. Sprawdź też brak wag oraz obraz bez tekstury.
  Awaria/anulowanie pozostawia wcześniejszy film i kandydata. Lokalna odmowa
  jednej pary może pozostawić spójny graf przez inne relacje; rozłączenie
  nie tworzy kompletnego filmu. Brak pomiaru ma przyczynę i nie daje zerowego XY.
- Korelacja bez normalizacji i metody złożone mogą mieć poprawne XY bez
  oceny pewności. Taki wynik może wejść do LS/Hubera; brak wskaźnika nie
  powinien być przedstawiony jako pewne dopasowanie ani jako brak pomiaru.

## Ocena na filmach STM

Na MOVIE_4 usuń pierwsze dwie źródłowe klatki przed obliczeniami; gotowe sesje
odbioru mogą już mieć ten krok wykonany. Zachowaj ten sam skład serii i okno
przy porównaniu Optical Flow oraz Deep. Obejrzyj pierwsze 150 bieżących klatek,
szczególnie 29→30, 35→36, 44–46, 61→62 oraz 94–97. Porównaj osobno LS/Huber.
Powtórz porównanie na MOVIE_8. Poszczególne wyniki można zachować w osobnych
sesjach; okno nie wprowadza biblioteki prób A/B ani dalszych odniesień REG-08d.

Zapisz **lepiej / podobnie / gorzej / niejednoznacznie** dla widocznych struktur.
Tearing oceń osobno. Zbieżność Hubera, mniejszy obszar aligned lub mniej ruchu
filmu nie są samodzielnym dowodem poprawności fizycznej.

Generator i skrypt automatycznej próby (tworzą nowy katalog wyników):

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/graph_methods_trial.py /tmp/reg08e-cpu-known-new --windows 3 5
```

Bez `--source` skrypt tworzy osiem klatek 256×256 ze znanym ruchem, wyciętych
z większego obrazu. Domyślnie sprawdza pięć metod CPU z zablokowanym importem
Torch/Kornia, zapisuje sesje, MPP, AVI oraz `report.json`. Metody modelowe
wybieramy jawnie przez `--methods`, z lokalnymi `--weights` i `--device`.
Rzeczywisty film podajemy przez `--source`, a dla MOVIE_4 również `--drop-first 2`.
