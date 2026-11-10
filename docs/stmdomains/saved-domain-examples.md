# Przykłady zapisanych propozycji domen

2026-10-31. Na prośbę użytkownika przygotowano galerię istniejących wyników
prób 15 i 16. Nie wykonywano nowej predykcji, wyboru parametrów ani treningu.
Ticket 19 pozostaje zakończony, a 20 nierozpoczęty.

Galeria lokalna:
`/home/rlew/projekty/NEtCAT-domains/.scratch/domain-examples/index.html`.
Obok są porównania PNG, osobne PNG metod, obrazy bez nakładek, `assignments.csv`,
niezmienione kopie JSON przypisań, `manifest.json` i `export_examples.py`.
Materiały pomiarowe i wygenerowane pliki pozostają poza Git.

## Co pokazują obrazy

Klatki 250, 259 i 268 wybrano jako początek, środek i koniec zakresu,
bez wyboru najlepszego wyniku. Kontrola `control-0073` to pierwszy przykład
ewaluacyjny dwóch orientacji, seed 2701. Każde porównanie pokazuje obraz
źródłowy, komórkę lokalną i SBC.

| Przykład | Oznaczenia | Komórka: przypisane / grupy | SBC: przypisane / grupy |
| --- | ---: | ---: | ---: |
| TTMAPP 250 | 301 | 49 / 1 | 25 / 3 |
| TTMAPP 259 | 312 | 87 / 3 | 104 / 4 |
| TTMAPP 268 | 308 | 114 / 4 | 53 / 3 |
| Dwie orientacje, kontrola | 251 | 238 / 2 | 249 / 2 |

Kolorowe kółka oznaczają centra molekuł przypisanych do tej samej lokalnej
propozycji; szare krzyżyki — brak przypisania. Nie wyznaczono nowych konturów,
masek ani powierzchni. Numery i kolory są lokalne dla klatki oraz metody;
nie oznaczają trwałych typów ani zgodności z kolorami ręcznych referencji.
Odsetek przypisań nie jest miarą trafności.

Przewidywania powstały bez ręcznych ramek jako wejścia i bez zadanej liczby
domen. Referencje służyły późniejszej częściowej ocenie; nie są nakładane
w galerii. Obie metody pozostają eksperymentalne. SBC nie przeszło wszystkich
kontroli (`qualified=false`), żadnej metody nie przyjęto do aplikacji.
Najnowsza diagnostyka 19 dotyczyła składników regularności, nie dostarczyła
nowych gotowych konturów domen.

## Pochodzenie i odtworzenie

- [Orientacja i łączenie](orientation-and-joining-trial.md): źródła
  `2b70d0dda4ff8cd8c4469237d8c6e7fd6df19d1f`, zapisane przypisania
  `orientation-and-joining/assignments/cell-0.65-0.12-0.3-seed/`.
- [SBC/MatID](sbc-matid-domains-trial.md): źródła
  `e6d3fbc12f0b87b3a84d707a8e178289731ea2b3`, przypisania
  `sbc-matid-domains/assignments/points-merged/`, konfiguracja `t0.15-c3.5`.
- Współrzędne `raw_edge_xy`, jednostka px; bez wiarygodnej kalibracji nm.
  Kontrast 2.–98. percentyl, identyczny dla metod tej samej klatki, gamma 1.
  Nie użyto okien `support_xyxy` metody komórki jako ramek molekuł.

Eksport można odtworzyć w środowisku `netcat` przez:

```bash
python .scratch/domain-examples/export_examples.py \
  --source /home/rlew/projekty/NEtCAT-domains/.scratch \
  --output .scratch/domain-examples
```

Skrypt wyłącznie odczytuje wejścia i zamrożone wyniki oraz renderuje wykresy.
Łączy rekordy według ID, ponieważ kolejność predykcji i wejść jest różna.
Manifest zawiera hashe źródeł, eksportera i artefaktów. Sprawdzono zgodność
2344 przypisań z JSON oraz pierwotnymi predykcjami, centra, identyfikatory,
hash/zgodność obrazów obu metod i osiem identycznych kopii JSON. Niezależny
audyt potwierdził liczniki, geometrię i brak dorobionych granic. Obejrzano PNG
i sprawdzono odnośniki po publikacji lokalnej. Nie powtarzano algorytmów ani
testów aplikacji; jest to kontrola eksportu, nie nowa walidacja detektora.
