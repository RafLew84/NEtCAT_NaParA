# REG-12: ręczna próba MatchAnything-ELoFTR

Status odbioru: **zaliczony przez użytkownika** — „testy manualne ok”,
2026-11-02. REG-12 ma status `done`; poniżej pozostaje scenariusz odtworzenia prób.
Próby automatyczne oraz Qt offscreen są raportowane osobno
w [wynikach](matchanything-results.md).
[Przygotowane zasoby i środowisko](matchanything-environment.md).

## Uruchomienie i wybór metody

```bash
cd /home/rlew/projekty/NEtCAT-viewer
conda activate netcat
python -m stmviewer.main
```

Wybierz **MatchAnything-ELoFTR** z listy metod. Pole kodu wskazuje
`/home/rlew/.cache/stmviewer/matchanything/source`, a pole wag
`/home/rlew/.cache/stmviewer/matchanything/weights/matchanything_eloftr.ckpt`.
Wybierz CPU albo CUDA i użyj **Sprawdź model**. Program korzysta z tych
lokalnych plików; nie wymaga uruchamiania środowiska RoMa.

Najpierw otwórz `tests/stmviewer/fixtures/registration/cpu.mpp`.
Zarejestruj film i sprawdź wynik aligned. Oczekiwane XY kolejnych klatek
względem pierwszej to (0,0), (+2,−1), (−1,+1) px. W rzeczywistej próbie
MatchAnything miał na tym prostym wzorcu około 1 px błędu Y; odnotuj go,
nie traktuj samego utworzenia aligned jako zaliczenia dokładności.
Przełącz original/aligned, zmień gamma i zoom; zmiany podglądu nie
uruchamiają modelu ani nie zmieniają zapisanych XY.

## Porównanie z EfficientLoFTR

1. W porównaniu pary oblicz EfficientLoFTR i zachowaj wynik do porównania.
   Następnie oblicz MatchAnything-ELoFTR na tej samej parze. Sprawdź nazwę,
   urządzenie, przesunięcie, przestrzenne poparcie i ewentualne ostrzeżenie.
2. Powtórz na `MOVIE_4.mpp`, usuwając przed rejestracją dwie pierwsze klatki.
   Bieżące pary do sprawdzenia: 29→30, 35→36, 44→45→46, 61→62,
   94→95→96→97. Obejrzyj także pierwszych 150 klatek i dalszą część filmu.
3. W `MOVIE_8.mpp` sprawdź m.in. 1→2, 16→17 i 56→57 oraz cały film.
   Dla obu metod użyj tych samych wejść, widoku i ustawień grafu.
4. W **Dopasowaniu wieloklatkowym** wybierz MatchAnything-ELoFTR i okno 3.
   Oblicz kandydata. Huber korzysta z tych samych zapisanych relacji co LS.
   **Zastosuj wynik do filmu** zmienia aktywny aligned dopiero po jawnym
   użyciu przycisku i wymaga kompletnego rozwiązania.

Duża liczba punktów lub spójny graf nie dowodzą poprawności dryfu STM.
Sprawdź te same rozpoznawalne kontury w różnych częściach obrazu, szczególnie
przy pasach i tearingu. Zapisz też miejsca, gdzie wynik jest gorszy albo
niejednoznaczny. Nie trzeba oznaczać masek ani uruchamiać odłożonego REG-06.

## Zachowanie pracy i eksport

- Zapisz sesję z aktywnym wynikiem, otwórz ją ponownie i sprawdź XY,
  ostrzeżenia, parametry modelu i niezastosowanego kandydata grafu.
  Otwarcie sesji działa również bez dostępnych wag; dopiero nowa estymacja
  wymaga modelu. Zapisz także po przełączeniu na Phase i sprawdź, czy powrót
  do MatchAnything zachowuje wcześniej wskazane pliki i urządzenie.
- Przy istniejącym aligned ponów obliczenie i anuluj. Poprzedni film ma
  pozostać. Wskaż nieistniejące wagi albo nieprawidłowy checkpoint:
  komunikat ma podać przyczynę, bez zamiany metody lub urządzenia.
- Zastosuj poprawkę ręczną jednej pary, cofnij ją i porównaj wynik z bazą.
  Zapisz krótki aligned jako MPP z metadanymi, otwórz ponownie i porównaj
  geometrię oraz pochodzenie. Wyeksportuj MJPG i FFV1, sprawdź w VLC.
  Opisy diagnostyczne pary nie powinny trafiać do MPP ani czystego AVI.

W [karcie REG-12](reviews/REG-12.md) zapisz ocenę obrazu, platformę,
urządzenie i decyzję. Windows oraz rzeczywista karta 8 GB wymagają
oddzielnej próby; test na lokalnej RTX 5090 nie zalicza tych punktów.
