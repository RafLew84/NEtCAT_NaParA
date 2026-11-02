# REG-11: RoMa v2 — próba ręczna

**Status:** instrukcja do odbioru; nie oznacza zaliczonych prób ręcznych.
Próby automatyczne, ocena użytkownika w GUI i odtworzenie AVI w VLC są
odrębnymi sprawdzeniami. Data przygotowania: 2026-11-02.
Zakres: [REG-11](issues/11-roma-v2.md), wspólny [protokół](manual-protocol.md).

## Uruchomienie i zasoby

Uruchom STM Viewer w dotychczasowym środowisku **`netcat`**, z katalogu repo:

```bash
cd /home/rlew/projekty/NEtCAT-viewer
/home/rlew/projekty/conda-migration-ubuntu-20261008/envs/netcat/bin/python -m stmviewer.main
```

W polu metody wybierz **RoMa v2**. Wybór jest dostępny w głównym oknie,
**Porównaj parę…** oraz **Dopasowanie wieloklatkowe…**.
Domyślne ścieżki przygotowanego stanowiska:

| Pole | Wartość |
| --- | --- |
| Python środowiska RoMa | `/home/rlew/miniconda3/envs/netcat-romav2/bin/python` |
| Lokalne wagi RoMa v2 | `/home/rlew/.cache/stmviewer/romav2/weights/romav2.0.1.pt` |
| Lokalny katalog kodu DINOv3 | `/home/rlew/.cache/stmviewer/romav2/dinov3` |

Jeśli pole nie odpowiada lokalizacji na komputerze, użyj **Wybierz…**,
**Wybierz wagi…** lub **Wybierz katalog kodu…** przy odpowiednim polu.
Główny program nadal działa w `netcat`. Osobny proces uruchamiany wskazanym
Pythonem obsługuje tylko model RoMa. Szczegóły wersji, sum i zależności:
[przygotowanie środowiska](roma-environment.md).

Rozpocznij od **Turbo — 320 px**, **Limit punktów: 1000** i
**Ziarno losowania: 20261102**. Dostępne warianty: Turbo 320, Fast 512,
Base 640 i Precise 1280 px. Limit punktów ma zakres 8–10000; ziarno
0–2147483647. Limit jest górnym ograniczeniem, a liczba użytych punktów
może być mniejsza po próbkowaniu przestrzennym i odrzuceniu punktów.
Każda zmiana wariantu lub próbkowania oznacza osobną konfigurację próby.

**Urządzenie: Auto** wybiera CUDA dostępne w środowisku RoMa, a w razie
braku CUDA — CPU. Dla porównania na jednym urządzeniu wybierz jawnie
**CPU** lub **CUDA**. Błąd CUDA lub brak pamięci nie przełącza obliczeń na
CPU ani na mniejszy wariant. Faktyczne urządzenie sprawdzaj w wyniku.

1. Kliknij **Sprawdź model** w głównym oknie. Oczekuj potwierdzenia RoMa
   i urządzenia; sprawdzenie ładuje lokalny model w osobnym procesie.
2. Wpisz chwilowo nieistniejącą ścieżkę interpretera, a potem wag lub kodu.
   Oczekuj konkretnej informacji o brakującym zasobie i blokady nowego
   obliczenia. Przywróć poprawne ścieżki i sprawdź model ponownie.
3. Sam wybór metody lub otwarcie sesji nie powinien uruchamiać modelu.
   Program nie pobiera brakujących wag lub kodu.

## Para i znaczenie diagnostyki

1. Otwórz `tests/stmviewer/fixtures/registration/cpu.mpp`.
   W **Porównaj parę…** wybierz klatki 1→2 i **RoMa v2**, potem
   **Dopasuj automatycznie**. Znane przesunięcie do wyrównania wynosi
   X = +2, Y = −1 px. Dla pary 2→3 wynosi X = −3, Y = +2 px.
2. Przełączaj klatkę bazową, przesuwaną i nakładkę, używając wspólnego
   zoomu i gamma. Oceń położenie struktur oraz krawędzie oryginalnego pola.
3. Zapisz XY i obejrzyj liczbę zgodnych punktów, rozrzut oraz siatki 4 × 4
   obu oryginałów. Górny wiersz siatki odpowiada górze obrazu. To liczniki
   przestrzennego poparcia; nie są mapą deformacji ani oceną poprawności STM.
4. Otwórz **Szczegóły wybranego wyniku**. Sprawdź nazwę modelu, urządzenie
   i przygotowanie wejść. Szarość jest powielana do RGB, jasność jest
   normalizowana osobno dla obu oryginałów, a punkty modelu są przeliczane
   na piksele oryginałów. Gamma podglądu nie zmienia wejścia obliczeń.
5. Użyj **Zachowaj do porównania**, przełącz na EfficientLoFTR i oblicz tę
   samą parę. Porównaj obrazy i XY. Następnie wykonaj osobne porównanie ze
   starym Deep Matcher z wagami outdoor.

RoMa i EfficientLoFTR używają tego samego konsensusu w pikselach oryginału.
Różnią się modelem, przygotowaniem obrazu i sposobem pozyskania punktów.
Porównanie ze starym Deep obejmuje także inną agregację. Duża liczba
zgodnych punktów nie potwierdza poprawności fizycznego dryfu.

Wynik `low_confidence` pozostaje widoczny z przyczyną ostrzeżenia.
`manual_review` oznacza potrzebę obejrzenia wyniku, nie zaliczoną ocenę
obrazu. Przy rzeczywistym braku wystarczających punktów występuje odmowa:
**Pokaż poparcie odrzuconej próby** pokazuje diagnozę, a poprzedni wynik
zostaje. Odmowa nie wprowadza nowego przesunięcia do filmu.

## Te same dane dla porównania

Przygotowane lokalne wzorce znajdują się w `/tmp/reg10-patterns-v2/`:

- `translation.mpp` — znane przesunięcia, także subpikselowe;
- `stationary-artifact.mpp` — nieruchomy pas przy ruchu struktur;
- `one-band.mpp` — tekstura tylko w jednym pasie;
- `split-motion.mpp` — różne ruchy części obrazu;
- `periodic.mpp` i `noisy.mpp` — powtarzalność i silne zakłócenia.

Znane ruchy i przeznaczenie są w `manifest.json`. Oglądaj struktury poza
pasem zakłócenia: dopasowanie samego pasa może dać atrakcyjną diagnostykę
przy błędnym XY. Przy różnym ruchu dwóch części pojedyncza translacja
nie wyrówna obu części jednocześnie.

Gdy katalog tymczasowy już nie istnieje, odtwórz wzorce w nowym katalogu:

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/make_local_consensus_fixtures.py \
  --output /tmp/reg11-patterns
```

Starszy `report.json` w `/tmp/reg10-patterns-v2/` zawiera EfficientLoFTR
z konsensusem v1. Do porównania z aktualnym RoMa wykonaj EfficientLoFTR
ponownie na tych samych oryginałach, używając obecnego konsensusu v2.

## Cały film i dopasowanie wieloklatkowe

1. Otwórz `data/MOVIE_4.mpp`. Usuń klatkę 1, a następnie ponownie bieżącą
   klatkę 1. W ten sposób usuniesz źródłowe 1 i 2; zostaje **362 klatek**.
   Wszystkie dalsze numery odnoszą się do tej skróconej serii.
2. Wybierz RoMa, ustal urządzenie, wariant i próbkowanie, kliknij
   **Rejestruj**. Ta ścieżka dopasowuje 2→1, 3→2 itd. i sumuje przesunięcia
   względem pierwszej klatki serii. Wybór klatki podglądu nie zmienia kotwicy.
3. Po sukcesie obejrzyj aligned, zwłaszcza pierwsze 150 klatek i dalszą
   część osobno. Sprawdź pary **29→30, 35→36, 44→45→46, 61→62 oraz
   94→95→96→97**. Bieżące 29→30 to źródłowe 31→32.
4. Otwórz **Dopasowanie wieloklatkowe…**. Wybierz RoMa i **okno 3** do
   pierwszego porównania z wcześniejszymi raportami. Kliknij
   **Oblicz kandydata grafu**. Powtórzenie z oknem 5 jest osobną próbą.
5. W **Relacje i rozbieżności** zaznacz parę i kliknij
   **Obejrzyj wybraną parę**. Sprawdź też relacje niesąsiednie i ewentualne
   odmowy. Model jest ładowany raz na zadanie; graf używa tych samych
   reguł dopasowania pojedynczej pary co rejestracja sąsiednia.
6. Dla kompletnego grafu obejrzyj LS. Możesz użyć
   **Oblicz nowy wariant Hubera** — korzysta z już zmierzonych relacji,
   bez ponownego uruchamiania modelu. Zachowaj te same ustawienia solvera
   przy porównaniu metod. Rozłączny graf lub niezbieżny wariant nie daje
   kompletnego filmu do zastosowania.
7. Wybierz kompletny wynik i kliknij **Zastosuj wynik do filmu**.
   Samo obliczenie kandydata nie zmienia aktywnego aligned.
8. Powtórz próby na `data/MOVIE_8.mpp`, zachowując wszystkie **84 klatki**.
   Przy identycznej liście klatek, oknie i solverze porównaj z EfficientLoFTR
   oraz Deep outdoor. Zanotuj odmowy i miejsca, w których struktury skaczą
   lub pozostają niedopasowane, nawet gdy film jest kompletny.

Pełny aligned powstaje z oryginalnych obrazów przez jedną translację na
klatkę. Gęste pole RoMa nie deformuje pomiaru. Rozmiar wspólnego obszaru
może wzrosnąć; oryginalne obrazy zachowują rozmiar w pikselach.

## Anulowanie, sesja i ręczna korekta

1. Przy istniejącym aligned rozpocznij nowe obliczenie RoMa i użyj
   **Anuluj rejestrację**. W oknie pary użyj **Przerwij obliczanie**,
   a w grafie **Anuluj obliczenia**. Poprzedni wynik i jego możliwość
   eksportu mają zostać. Po zakończeniu anulowania nie powinno pozostać
   zadanie RoMa działające w tle.
2. Na krótkim, kompletnym wyniku kliknij **Porównaj parę…**, wybierz
   sąsiednie klatki, następnie **Popraw dopasowanie z filmu**.
   Wykonaj ruch o +1 px X i kliknij **Zakończ korektę**.
   To kończy edycję pary; aby zmienić film, kliknij jeszcze
   **Zastosuj do filmu** w sekcji **Korekta całego filmu**.
3. Obejrzyj kolejne klatki: korekta obejmuje klatkę przesuwaną i wszystkie
   późniejsze, zachowując ich dalsze względne dopasowania. Dla filmu z
   grafu nie uruchamia to ponownie solvera. Historyczna diagnoza modelu
   pozostaje zapisana, a ręczna zmiana ma osobne pochodzenie.
4. Zapisz `.stmsession`, zamknij program i otwórz sesję ponownie.
   Sprawdź active aligned, ręczną korektę, ustawienia RoMa oraz osobny,
   ewentualnie jeszcze niezastosowany kandydat grafu. Odczyt nie powinien
   sam zastosować kandydata ani ponownie wykonywać rejestracji.
5. Dla próby bez modelu zapisz **osobną kopię sesji** po wpisaniu w polach
   RoMa nieistniejących ścieżek, np. `/absent/roma/python`,
   `/absent/roma/weights.pt`, `/absent/roma/dinov3`. Zamknij i otwórz tę
   kopię. Obrazy, zapisane XY i diagnostyka mają być dostępne; nowe obliczenie
   ma podać brak zasobów. Potem przywróć poprawne ścieżki. Nie trzeba
   usuwać ani przenosić przygotowanego środowiska i wag.

## MPP i AVI z aktywnego wyniku

1. Do krótkiej próby wykorzystaj kompletny wynik `cpu.mpp`, z zastosowaną
   korektą. **Zapisz MPP…**, w polu typu pliku wybierz **MPP aligned**.
   Zapis obejmuje całą bieżącą serię; ten dialog nie wybiera zakresu.
2. Otwórz zapisany MPP w drugim oknie lub po zapisaniu sesji. Przenieś
   razem MPP i towarzyszący `.stmviewer.json`. Sprawdź geometrię, tło poza
   ważnym obszarem, źródłowe wymiary oraz poprawione położenia. Zapis z GUI
   używa wariantu z białym wypełnieniem dla WSxM; Viewer odtwarza braki
   próbek z dodatku. Wartości pomiaru nie zależą od gamma podglądu.
3. **Zapisz AVI…**: wybierz aligned, całą krótką serię lub zakres od–do,
   np. 1–3, oraz jawne FPS. Zapisz osobno **MJPG** i **FFV1**.
   Wybierz tło i gamma, pozostaw opisy wyłączone do pierwszego porównania.
4. Otwórz oba AVI w **VLC**. Sprawdź kolejność, tempo, położenia, pełne pole
   obrazu i tło. Film nie ma nakładek diagnostyki ani gęstego warpu.
   Zaznacz odtworzenie w VLC osobno od automatycznego sprawdzenia kodeka.

## Zapis wyniku odbioru

Dla każdej próby zanotuj: plik i liczbę klatek, usunięte klatki, urządzenie,
preset, limit punktów, ziarno, okno grafu i solver. Osobno zapisz czas
obliczeń, zasoby z raportu, odmowy/ostrzeżenia oraz ocenę struktur na obrazie.
Zaliczenie technicznego obliczenia nie jest oceną jakości dopasowania.

Próba na RTX 5090 nie potwierdza pracy na karcie 8 GB VRAM. Odbiór
stanowiska z 8 GB, Windows 11 i VLC oznacz jako niewykonany, jeżeli nie
został rzeczywiście przeprowadzony. REG-06 pozostaje odłożony; brak
niezależnej kontroli obrazu pozostaje brakiem takiej oceny.
