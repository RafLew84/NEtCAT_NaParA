# Przygotowanie treningu bez etykiet — issue 20

Data: **2026-10-31**. Wykonano przygotowanie
[20](issues/20-self-supervised-training-preparation.md), status `resolved`.
Powstały generator wycinków, rozdzielone protokoły transferu i transdukcji,
nowe realizacje kontroli, checkpoint oraz techniczna próba GPU.
Właściwe modele i porównania domen pozostają w 21/22.

[Protokół](self-supervised-training-protocol.md) i
[konfiguracja](../../stmdomains/experiments/training/experiment-plan.json)
zamykają zakres porównania. [Manifest wykonania](self-supervised-training-manifest.json)
zawiera hashe, liczebności i pomiary. Kod przygotowania znajduje się w
[stmdomains/experiments/training](../../stmdomains/experiments/training/README.md).
Kod jest osobnym modułem badawczym, bez podłączania detektora do aplikacji.

## Dane i geometria

Lokalny wynik: `/home/rlew/projekty/NEtCAT-domains/.scratch/training-20/`.
Odtworzono obrazy i bieżące centra wszystkich 24 klatek pilota z raw MPP
oraz audytowanego zapisu. Hashe źródeł i tablic zgadzają się z krokiem 14.
Referencje domen nie są wejściem przygotowania; nie wycinają obszaru analizy.

Rejestr ma **38 622 wiersze**: 18 432 siatki i 20 190 centrów, po trzy skale
32/48/64 px. **25 530 wycinków** ma pełne wsparcie, a 13 092 zachowano
z jawnym powodem niedostępności. Są to nakładające się widoki, nie tyle
niezależnych przykładów. Siatka ma krok 16 px, tensor 64 × 64. Pełne
wsparcie uwzględnia przesunięcie augmentacji do 2 px i 1 px na interpolację;
nie wprowadza paddingu lub gamma.

Transfer rozdziela czas i obszar wspólnego płótna:

| Część | Klatki pilota | Pas X expanded przed buforem | Siatka 32 / 48 / 64 px |
| --- | --- | --- | --- |
| train | 1, 50, 100 | 320–480 | 182 / 96 / 84 |
| validation | 150, 200 | 160–320 | 126 / 84 / 60 |
| test | 250–268 | 0–160 | 1456 / 912 / 792 |

Bloki 101–149 i 201–249 są buforami czasu. Po 8 px po obu stronach
granic pasów i pełnym wsparciu rzeczywiste minimalne odstępy między
wsparciami różnych części wynoszą **16,22 i 44,65 px**. Sprawdzenie dotyczy
wszystkich klatek razem, także zmienionych zapisanym przesunięciem.

Normalizacja percentylami 2–98 jest dopasowana do 79 872 pikseli dozwolonej
części train, każdy raz, bez ważenia nakładającymi się oknami. Progi to
−239,486154 i 219,362191; validation/test używają tych samych wartości.
Transdukcja ma oddzielny fit na 1 572 864 pikselach wszystkich 24 pól.
Stałe odwzorowanie intensywności syntetyków daje po normalizacji
`clip(0.5 + 0.4 * renderer_signal, 0, 1)`: zachowuje odwrócenie kontrastu
i nie dopasowuje niczego na odłożonych kontrolach.

Obejrzano [rysunek geometrii](../../.scratch/training-20/geometry.png):
pełne obrazy 1/150/250, dozwolone pasy, miejsca siatki i przykład efektywnego
wsparcia. To inspekcja danych, bez propozycji domen lub referencji.

## Kontrole i zamknięty plan

Przygotowano **81 realizacji**, 27 przypadków × 3 nowe ziarna
920001–920003. Zachowano 22 rodziny z kroku 14; dodano niezależne rzędy,
pustą przerwę, same braki oznaczeń w tym samym pasie, niedostateczne pole
i orientację 8°. Prawda jest w osobnym `evaluation/`. Para przerwa/braki
ma identyczne centra, bboxy i ID, ale inny obraz. Małe pole nie jest
negatywnym przykładem zerowej domeny. Nie obliczano predykcji na tym zestawie.

Plan przewiduje najwyżej **27 fitów** w 21/22: 18 transferowych i 9
transdukcyjnych, AE/rVAE/SSL, po trzy ziarna. Maksimum 2000 kroków,
batch 64, float32; administracyjnie 15 minut na fit, łącznie 6 h 45 min,
8 GiB tensorów GPU i 12 GiB RSS. To pułapy, nie obietnica czasu docelowych
modeli. Wybór checkpointu nie używa ręcznych domen. Nieudane runy nie
otwierają dodatkowego strojenia.

Jeden jawnie dostosowany punkt odniesienia FFT/FH i MWS tworzą z cechami
uczonymi porównanie 2 × 2. Protokół ustala m.in. limity scaleń/podziałów,
użyteczny udział przypisań, kontrolę zerowej/jednej domeny i korzyść
względem bazy. Wyniki przed odmowami i po nich pozostają osobne.
F1 granic dotyczy kontaktów dodatnich domen na syntezie; przerw nie ocenia
jako dokładnych konturów materiału. Transfer TTMAPP używa tylko swojej
części testowej; brak ocenialnego regionu daje brak miary.

## GPU i wznowienie

`netcat`: Python 3.12.12, Torch 2.9.1+cu128, RTX 5090. Nie instalowano
pakietów ani wag. GPU był dostępny poza sandboxem; w sandboxie sterownik
nie był widoczny. Lokalne `.venv` nie jest środowiskiem tej próby.

Próba użyła **84 rzeczywistych wycinków** train i 99 krótkich kroków małego
AE (wznowienia, warmup i pomiar). Dla trzech ziaren porównano sześć kroków
z wariantem trzy kroki + checkpoint + nowy proces + trzy kroki. Wagi,
Adam, scheduler, RNG Python/NumPy/Torch CPU/CUDA, osobny generator
augmentacji, sampler, ID batchy i straty są **bitowo identyczne**.
Zadana tolerancja wynosiła 1e-6, zmierzona różnica 0.

| Batch | Zakres czasu kroku proxy | Maks. VRAM tensorów / rezerwy |
| --- | --- | --- |
| 32 | 2,24–2,76 ms | 75 / 96 MiB |
| 64 | 3,13–3,18 ms | 91 / 96 MiB |
| 128 | 4,68–4,93 ms | 115 / 136 MiB |

Cały końcowy probe z procesami: **13,16 s**. Szczyt RSS procesu pomiarowego
około 1627 MiB. Przygotowanie wycinków: 3,51 s / 181 908 KiB RSS.
VRAM obejmuje alokator tensorów, bez całego kontekstu sterownika;
RSS jest maksimum pojedynczego procesu, nie sumą jednoczesnych procesów.
To koszt proxy i przygotowania, nie pomiar skuteczności ani pełnego rVAE/SSL.

Gradienty reparametryzacji, lokalnej wariancji/kowariancji i deterministycznego
obrotu współrzędnych przed dekoderem MLP działają. CUDA `grid_sample`
backward działa tylko bez ścisłego wymogu deterministyczności. Dlatego
plan rVAE używa dekodera współrzędnych; rzeczywisty model wymaga własnego
sprawdzenia wznowienia w 21. Checkpoint obsługuje ukończone kroki float32,
bez AMP, akumulacji lub kolejek workerów, zgodnie z planem.

## Wykonane sprawdzenia i odtworzenie

- **78 testów** `python -m pytest -q tests/stmdomains` przeszło: dotychczasowe
  wejście/cechy oraz nowe dane, kontrole i checkpoint.
- 24 wejścia odtworzone z MPP/sesji, także geometria zapisanej rejestracji.
- 25 530 wycinków odtworzonych z identycznym hashem; 18 432 rekordy siatki
  i wszystkie ich dostępne piksele identyczne bez centrów molekuł.
- Powtórzenie całego przygotowania z blokadą otwierania referencji daje
  identyczne split, normalizację, okna, batch oraz manifest przygotowania.
- Testy analitycznej rampy, ułamkowych centrów, przesunięć, braków pomiaru,
  zakresu normalizacji, korespondencji widoków i odrzucenia błędnej geometrii.
- Pełny wrapper wykonany od początku do końca; podgląd geometrii obejrzany.

```bash
bash stmdomains/experiments/training/run_preparation.sh \
  .scratch/unsupervised-input/analysis \
  data/TTMAPP/MOVIE_23raw_TTMAPP_I_AU111.MPP \
  data/TTMAPP/detection_full.moltrack.json \
  .scratch/training-20-repeat
```

Kod/protokół i mały manifest są wersjonowane; około 118 MB danych, kopii
weryfikacyjnej i checkpointów pozostaje lokalnie. Pierwszy pomiar kalibracyjny
w `experiment-plan.json` pochodzi z `.scratch/training-gpu-20/gpu-probe.json`;
końcowy pełny wrapper ma własny pomiar i hashe w manifeście wykonania.

## Ograniczenia i następny krok

Mało okien transferu — tylko 96 w głównej skali train — oraz ich nakładanie
ograniczają wnioskowanie. Rejestracja jest przeważnie niskiej jakości;
bufor 8 px nie gwarantuje fizycznej niezależności. Nowe ziarna syntetyczne
nie zastępują nowej akwizycji. Częściowe referencje nie dają prawdy poza
wnętrzami ani dokładnych granic.

Nie uruchomiono porównań domen, właściwych treningów 21/22 ani testów GUI.
Sprawdzenie przygotowania nie zatwierdza detektora. Następne są niezależne
21 i 22, potem 23; 04/13 pozostają otwarte. Nie potrzeba zmian wspólnych
modułów, wymagań aplikacji lub Viewer.
