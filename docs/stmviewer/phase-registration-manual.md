# Próba ręczna — rejestracja Phase (ticket 08)

Z katalogu `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Dodatkowe zależności Phase: SciPy 1.15.2 i scikit-image 0.25.2, zapisane
w `stmviewer/requirements.txt`. Pozostałe metody będą w ticketach 09–10.

## Dane

Małe filmy są w `tests/stmviewer/fixtures/registration/`. Generator:

```bash
python tests/stmviewer/make_registration_fixtures.py
```

| Plik | Oczekiwany wynik |
| --- | --- |
| `integer.mpp` | 3 klatki 48 × 32; przesunięcia XY: (0,0), (3,−2), (−2,−1); aligned 53 × 34 px. Czasy 10/20/35 s. |
| `subpixel.mpp` | 2 klatki 64 × 64; druga około (3,25,−2,4); aligned 68 × 67 px. |
| `uncertain.mpp` | Wzór powtarzalny; kompletne aligned i ostrzeżenia na klatkach 2/3, odziedziczona niepewność trzeciej. |
| `flat.mpp` | Brak tekstury: odmowa dla pary 1 → 2. |
| `missing.mpp` | NaN w drugiej klatce: czytelna odmowa, original pozostaje. |

Wzorce mają znaną skalę z nagłówka (8 × 9 nm). Opcja **Proporcje pikselowe**
pozwala oglądać je zgodnie z wymiarami pikselowymi. Przy różnej lub nieznanej
skali klatek aligned automatycznie używa proporcji pikselowych. Panel
„Parametry z pliku” zawsze opisuje źródło, a „Aligned” — wspólny wynik.

Rzeczywiste pomiary: `data/MOVIE_3.MPP` (17 klatek) oraz dłuższy
`data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP` (268 klatek) do próby anulowania.
Metadane zastępcze w tym drugim filmie nie potwierdzają rzeczywistej kalibracji.

## Kroki i oczekiwane wyniki

1. Otwórz `integer.mpp`, wybierz klatkę 2, ustaw gamma 1,5, przybliż
   i przesuń obraz. Uruchom Play, następnie **Rejestruj**. Play zatrzymuje się.
   Po sukcesie widać aligned aktualnie wybranej klatki, cały nowy obszar
   i gamma 1,5. Play mogło przejść dalej przed kliknięciem Rejestruj.
   Wybierz teraz klatkę 2: oczekuj ΔX 3 px i ΔY −2 px; panel podaje 53 × 34 px.
2. Przejdź przez klatki: znaczniki obrazu powinny pozostawać na wspólnej
   pozycji. Żółty przerywany obrys wskazuje pełne pole źródła; szachownica
   oznacza brak próbek, również przy gamma innej niż 1.
3. Zmień zoom i przesunięcie aligned. Przełącz na original i z powrotem:
   każdy widok przywraca własny kadr. Gamma jest wspólna. Zmiana widoku
   podczas Play zatrzymuje film. Miniatury pozostają original przy gamma 1.
4. W aligned obejrzyj klatkę 2, następnie wybierz 1 i usuń ją. Obraz dawnej
   drugiej klatki ma to samo położenie, kadr i obrys, teraz jest 1 z 2.
   Odniesienie nadal wskazuje MPP 1. Usuń również tę klatkę skrajną:
   pozostaje dawna trzecia, nadal w obszarze 53 × 34 i z przesunięciem (−2,−1).
5. Uruchom Rejestruj dla jednej pozostałej klatki. Nowy wynik ma 48 × 32 px,
   przesunięcie zerowe i odniesienie MPP 3. Usuń jedyną: pusty program,
   brak starego wyniku. Ponowne otwarcie źródła przywraca wszystkie klatki.
6. Otwórz `subpixel.mpp` i zarejestruj. Obrys drugiej klatki nadal odpowiada
   polu 64 × 64, choć brzeg ważnych próbek po interpolacji jest węższy.
   Powiększenie pomaga rozpoznać szachownicę pomiędzy obrysem a próbkami.
7. Otwórz `uncertain.mpp`, zarejestruj i obejrzyj klatki 2/3. Wynik pozostaje
   dostępny; panel i miniatury ostrzegają o niepewności. Trzecia dziedziczy
   niepewność. Usunięcie drugiej jej nie usuwa.
8. Sprawdź `flat.mpp` i `missing.mpp`. Komunikat podaje przyczynę i klatkę/parę;
   nie powstaje częściowe aligned. Dostępne są nadal original i nawigacja.
9. Na rzeczywistym filmie wykonaj rejestrację i uruchom ją ponownie.
   Podczas obliczeń zmień klatkę, gamma i zoom; przełączaj oba dostępne widoki.
   Otwieranie, usuwanie, Play i kolejna rejestracja są zablokowane. Po sukcesie
   widać aligned aktualnie oglądanej klatki, z dopasowaniem i zachowaną gamma.
10. Na dłuższym filmie ponów próbę i kliknij **Anuluj rejestrację**.
    Do najbliższego bezpiecznego punktu widać stan anulowania i blokady.
    Po zakończeniu poprzednie aligned, geometria oraz bieżący kadr/klatka/gamma
    pozostają. Szybki wzorzec może skończyć się przed kliknięciem — użyj dłuższego
    pomiaru. Zakończenie okna podczas obliczeń także najpierw anuluje zadanie.

Źródła nie są modyfikowane. Ponowienie zawsze korzysta z oryginałów bieżącej
serii. Niska pewność nie gwarantuje poprawnego dopasowania; w tym etapie
zachowujemy algorytm i progi NanoTrack bez strojenia dla pomiaru.

## Wykonane sprawdzenia

- 123 testy Viewera przechodzą (20 nowych), mypy strict: 17 plików bez błędów.
- Testy obejmują również błąd alokacji podczas tworzenia aligned oraz
  anulowanie przy ostatnim kroku; poprzedni wynik pozostaje kompletny.
- Automatyczna próba rzeczywistego okna Qt xcb przeszła na wzorcach i
  `data/MOVIE_3.MPP`: widoki, zoom/gamma, usuwanie odniesienia, subpiksele,
  niepewność, NaN/brak tekstury i zachowanie bajtów źródeł.
  Obejrzano zrzuty. To próba automatyczna, odrębna od odbioru użytkownika.
- Lokalny MOVIE_3 dał 398 × 398 px i 16 klatek z niską/odziedziczoną pewnością.
  Nie deklarujemy poprawności fizycznego dopasowania wszystkich jego klatek.

Ręczny odbiór użytkownika i Windows pozostają do wykonania. Pełny zestaw repo
oraz przegląd kodu: [przekazanie](handoff.md).
