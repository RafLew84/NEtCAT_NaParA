# Lokalny SSL — prototyp badawczy 22

Pytanie: czy lokalna zgodność dwóch widoków tego samego wycinka daje cechy
pomagające rozdzielać domeny? Źródłem parametrów jest
[protokół 20](../../../../docs/stmdomains/self-supervised-training-protocol.md).
To eksperyment na jednej akwizycji, bez przyjęcia metody do aplikacji.
[Wynik wykonanej próby](../../../../docs/stmdomains/local-self-supervised-trial.md):
brak poprawy końcowych domen; oddzielono ograniczenie bramki od błędów
granic przed odmowami. Źródło zachowuje gałąź
`prototype/stmdomains-local-self-supervised`.

Encoder 16/32/64 (konwolucje 3×3, krok 2, bez paddingu, GELU) zachowuje
mapę 7×7. Głowa 1×1 daje 16 lub 32 kanały. Graf otrzymuje spłaszczoną
mapę w ustalonej kolejności; nie ma globalnego uśrednienia. Nie ma dekodera
obrazu ani głowy przewidującej fizyczny kąt lub typ struktury.

Dwa widoki mają niezależne znane przesunięcia ±2 px, gain 0,9–1,1,
offset ±0,1 i szum o sigma 0–0,03. Porównujemy 25 centralnych pozycji
lokalnych po odwróceniu przesunięcia. Gęste wagi interpolacji liniowej
zachowują deterministyczne gradienty CUDA; wszystkie użyte sąsiednie
tokeny mają pełne wsparcie pomiarowe. To przybliżona zgodność cech
konwolucyjnych po przesunięciu, nie matematyczny dowód niezmienniczości.
Wagi zgodności/wariancji/kowariancji to 25/25/1.

Zakres: sześć transferowych fitów z16/z32 × trzy ziarna i trzy
transdukcyjne z32. Czas transdukcji wynika wyłącznie z mediany wybranych
kroków walidacyjnych transferu. Początkowe wagi z32 tych samych ziaren
są kontrolą bez uczenia. FFT, FH, MWS, bramka i przygotowanie danych
pozostają zgodne z 20/21. Wersjonowane źródła 21 oraz 21a pozostają zachowane.
Główna ocena używa siatki 48 px; 32/64 px i centra są diagnostyką.

## Odtworzenie

Wymagane są lokalne artefakty przygotowania 20 i zamrożonej próby 21,
PyTorch z CUDA oraz dotychczasowe środowisko `netcat`. Nie potrzeba
nowych bibliotek, danych ani pobierania wag. Duże pliki pozostają w `.scratch/`.
Skrypt wymaga świeżego katalogu docelowego i wykonuje wszystkie etapy:

```bash
bash stmdomains/experiments/training/local_ssl/run_trial.sh \
  .scratch/training-20 .scratch/autoencoder-21 .scratch/local-ssl-22-repeat
```

`NETCAT_PYTHON` pozwala wskazać interpreter. Etapy można też uruchamiać
oddzielnie poleceniami zapisanymi w skrypcie. Ponowne pełne wykonanie
jest odtworzeniem eksperymentu, a nie dodatkowym wariantem pierwotnego
budżetu. Właściwy przebieg 22 zapisano w `.scratch/local-ssl-22/`.

Wyniki obejmują konfiguracje i pełne checkpointy, początkowe wagi,
przekształcenia cech dopasowane wyłącznie do train, pełne nakładki,
graf ograniczony do części testowej transferu, wyniki przed/po odmowach,
ocenę sąsiadów i granic oraz samodzielny `index.html`.
Referencje odczytuje się dopiero po zamrożeniu predykcji. Kontrole
syntetyczne przygotowane w 20 były już oglądane w 21; są materiałem
rozwojowym. Częściowe referencje TTMAPP nie określają jakości całego obrazu.

Każdy etap zapisuje koszt CPU w `*.resources.json`; wspólny limit 7200 s
uwzględnia także pomierzone etapy 21. Dodatek 21a ma osobny budżet.
Fit ma limit 900 s, pamięć tensorów 8 GiB i RSS 12 GiB. Nieudane próby
również zużywają budżet; brak automatycznego strojenia, restartów lub
zastępowania ziaren.
