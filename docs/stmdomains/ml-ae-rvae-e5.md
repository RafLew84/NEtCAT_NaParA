# E5 — lokalność, skala i centrowanie AE/rVAE

Próba z 11 listopada 2026, `ml_domain`, baza `8168349`, środowisko `netcat`.
[Protokół ustalony przed obliczeniami](ml-ae-rvae-e5-protocol.md),
[manifest](ml-ae-rvae-e5-manifest.json), [plan](ml-ae-rvae-experiments.md).

## Wynik i dalszy kierunek

**E5 wykonane. Zmiana odczytu, skali i centrowania zmienia domeny, ale nie
dała ogólnej poprawy wystarczającej do wyboru detektora.** Pełna mapa AE
nie usuwa nadmiernego scalania. Wiele skal zwiększa część przypisań rVAE
kosztem błędów podziału lub scalania. Centrowanie na siatce bywa korzystne
dla jednej miary, ale pogarsza inne oraz kontrole granicy przesunięcia.
Nie zmieniono ustawień produkcyjnej aplikacji ani wag modeli.

Następny kierunek pozostaje zgodny z planem: **mały E7, uczony odczyt
relacji na zamrożonych cechach, po przeglądzie etykiet i audycie grup**.
Obecne wyniki nie dowodzą, że reprezentacje nie zawierają użytecznej
informacji; pokazują ograniczenia konkretnych odczytów i odległości.
Nie uzasadniają szerokiego treningu nowych modeli. E4/E6 pozostają warunkowe;
E3 nadal uzasadnia rozdzielenie wpływu fotometrii i normalizacji cech.
Nie rozpoczęto E4, E6 ani E7.

### Trzy porównania na rzeczywistych centrach

Poniżej transdukcja, FH, H_M1, wspólne wsparcie `common`. Każda liczba
to mediana trzech ziaren po zsumowaniu liczników 24 klatek w każdym ziarnie.
Pokrycie ma stały mianownik wewnątrz kontrastu: mapa 1354, skala 1202,
centrowanie 1258 miejsc znanych wnętrz. Mianowniki błędów par obejmują tylko
przypisane pary i mogą się zmieniać; pełne liczniki są w `readout-domain-seeds.csv`.

| Kontrast / odczyt | Warunek | Pokrycie ↑ | Scalenia par ↓ | Podziały par ↓ |
|---|---|---:|---:|---:|
| Mapa AE | Kod 32, baza | 98.74% | 91.20% | 14.53% |
| Mapa AE | Pełna mapa | 98.45% | 93.40% | 10.92% |
| Skala, pełne rVAE | 48, baza | 94.26% | 31.97% | 41.07% |
| Skala, pełne rVAE | 32+48+64 | 95.84% | 68.96% | 27.38% |
| Skala, treść rVAE | 48, baza | 87.94% | 14.10% | 54.23% |
| Skala, treść rVAE | 32+48+64 | 94.01% | 16.22% | 64.32% |
| Centrowanie, treść rVAE | Centrum molekuły | 89.03% | 13.73% | 57.92% |
| Centrowanie, treść rVAE | Najbliższa siatka | 80.05% | 12.02% | 55.25% |

Pogorszenie scalania pełnego rVAE po połączeniu skal występuje we wszystkich
trzech ziarnach: 45.35 → 82.22%, 31.97 → 68.96% i 19.79 → 25.26%.
Zwiększenie pokrycia nie jest równie stałe: trzecie ziarno nieznacznie je traci.

Są lokalne korzyści. Przy MWS pełna mapa AE zmniejsza medianę scalania
63.01 → 36.67%, ale zwiększa podziały 12.05 → 21.90% przy pokryciu 58.35 → 57.83%.
Skala 64 pełnego rVAE/FH daje mniejsze scalenia 31.97 → 25.04%, lecz podziały
41.07 → 43.90%, przy tej samej medianie pokrycia 94.26%. Nie jest to jednoznaczny
zwycięzca ani dowód poprawnych rzeczywistych granic.

Transfer nie potwierdza uniwersalnej korzyści wielu skal: treść rVAE/FH
ma medianę pokrycia 77.93 → 64.79% na wspólnej referencji 213 miejsc;
spadek występuje we wszystkich trzech ziarnach. Błąd scalania można porównać
w obu warunkach tylko w ziarnie 20261101: rośnie z 10/38 = 26.32% do
24/57 = 42.11%. W pozostałych ziarnach baza nie ma przypisanych par różnych
domen, więc błąd scalania jest niedostępny, a nie zerowy. Własne wsparcie
`own` i inny kontrast mają inne mianowniki;
nie należy porównywać tych procentów jak wyników na identycznym teście.

### Kontrole i bramka

Na kontrolach dwóch orientacji AE/FH scala różne domeny w 100% par zarówno
dla kodu 32, jak i mapy. Na granicy przesunięcia mapa pogarsza medianę
scalania 33.33 → 100%. Treść rVAE z wieloma skalami poprawia podział na granicy
przesunięcia, ale zwiększa medianę scalania dwóch orientacji 46.67 → 73.33%.
Centrowanie rVAE na siatce może zniszczyć rozdzielenie granicy przesunięcia:
dla pełnego rVAE scalenia rosną 0 → 100%. To wyniki transdukcji/centrów/FH/H_M1
na odpowiednim wspólnym wsparciu, a nie ranking wszystkich metod.

Kontrola niezależnych rzędów nadal otrzymuje 100% fałszywych przypisań
dla baz i wariantów mapy, wielu skal i snapu w powyższym ustawieniu.
Większa liczba kolorowych molekuł nie oznacza więc poprawnej domeny 2D.
Pełna bramka A_fixed_M1 nadal daje **0% pokrycia znanych wnętrz na centrach**
w obu reżimach i wszystkich wariantach. W transferze także na siatce 0%;
maksimum transdukcyjnej siatki to 0.51%. Nie jest to wykrywalność molekuł.

Referencyjnych krawędzi rzeczywistych granic jest bardzo mało: na centrach
transdukcji 4 w kontrastach mapy/centrowania i 3 w kontrastach skali.
Nie można na tej podstawie ogłosić walidacji lokalizacji granic.

### Dostępność i mieszanie kontekstu

Na 24 klatkach STM dostępne wejście wokół centrów ma 5395 miejsc dla 32 px,
4629 dla 48 px i 3890 dla 64 px. Mniejsze okno rzeczywiście odzyskuje kontekst
przy brzegu. Po uwzględnieniu marginesu całe okno mieści się w znanym
wnętrzu odpowiednio w 322, 129 i 26 miejscach. Są to własne zakresy wsparcia,
a referencja opisuje tylko części wnętrz: brak zawierania nie dowodzi
przekroczenia fizycznej granicy domeny.

W eksploracyjnym ROI B z paczki `data/temp`, klatki 259–266, dostępnych jest
65/27/9 centrów dla 32/48/64, lecz żadnego całego okna zawartego w ROI,
także bez marginesu. Te prostokąty nie wystarczają do oceny skuteczności
klasyfikacji domen. Audyt potwierdza koszt kontekstu, nie nową etykietę.

## Wykonane sprawdzenia

- **36 testów E5 PASS** w `netcat`, w tym ekstrakcja technicznie powiększonych
  obrazów, filtrowanie ID/krawędzi, osobne maski cech i geometrii oraz
  zachowanie braków bramki 48 i mianowników jakości.
- 4200 porównań nowych bazowych cech z E2 w tolerancji, maksymalna różnica
  8.11×10⁻⁶. Bazowe wejścia 48 identyczne bitowo. To kontrola cech, a nie
  deklaracja identycznych dawnych podziałów po nowym dopasowaniu adapterów.
- Niezależny audyt: 9131 zamrożonych artefaktów, 12 checkpointów, kod i protokół
  zgodne; 2100 kontroli geometrii, 304 adaptery i kalibracje poprawne.
  Tożsamościowy snap siatki: 2100 zestawów cech i 42000 tablic predykcji zgodnych.
- Audyt jakości: 255360 ocen, 68096 unikalnych agregatów, 544768 kontroli
  ilorazów licznik/mianownik i 336 grup wspólnej geometrii PASS. Potwierdzono
  liczby raportu oraz jawny brak miar przy zerowych mianownikach transferu.
- **177 sprawdzeń finalnej galerii QtWebEngine PASS**, zero błędów JS,
  105 obrazów załadowanych, pięć zrzutów sprawdzonych wizualnie. Indeks
  zawiera 8400 zestawów, nie otwierano każdego osobno. Fixture: 78 PASS.
  Odbiór ręczny użytkownika pozostaje otwarty. Poprawiono jedynie nazwę
  `resample_2x` rozpoznawaną przez checker po przebiegu; HTML, obliczenia
  i pierwotny snapshot zachowane. Osobny zapis `gallery-render.json`.

Przebieg główny: 921.55 s wall, 922.16 s CPU, szczyt RSS 2.10 GiB. CPU, jeden
wątek, CUDA niedostępna w tym środowisku. Wszystkie 304 adaptery dostępne;
255360 ocen wariantów, 68096 agregatów, 63840 zapisów dostępności oraz 4200
audytów kontekstu. To liczby obliczeń, nie niezależnych obserwacji.
Artefakty po postprocessingu i audytach zajmują około 4.8 GiB; budżety
60 minut CPU, 8 GiB RAM i 16 GiB artefaktów zachowane.
Nie uruchamiano pełnej regresji aplikacji; dodano izolowany eksperyment.
Największy nowy moduł ma 418 linii, poniżej celu 1000 i limitu 1500.

## Zakres próby

105 obrazów: 24 STM z jednej akwizycji oraz 81 syntetycznych kontroli.
Siatka i centra molekuł, transfer i transdukcja, trzy ziarna istniejących
AE/rVAE z32. Bez treningu enkoderów. Odczyty: AE, rVAE z treścią i kątem,
treść rVAE oraz FFT. Nowe adaptery dopasowano wyłącznie na dozwolonych
danych treningowych; historyczne adaptery i checkpointy nie są nadpisywane.

Trzy oddzielne porównania:

1. Ten sam wycinek 48 i AE: kod 32 kontra pełna mapa 64×7×7, spłaszczona
   do 3136 cech. Oba odczyty mają PCA do maksymalnie 24 wymiarów.
   Nie jest to gęsta segmentacja pikseli ani wybór fragmentu mapy.
2. Skala 48 kontra 32, 64 i połączenie 32/48/64 z równą wagą bloków.
   Każda skala jest od nowa pobierana z rastra źródłowego.
3. Wycinek wokół oryginalnego centrum kontra najbliższy punkt siatki 16
   i siatki przesuniętej o 8. Molekuły, referencja i graf pozostają na
   oryginalnych współrzędnych, zmienia się tylko miejsce ekstrakcji obrazu.

Skale i margines 3 są w pikselach odniesienia. Dla STM odpowiadają raw,
natomiast kontrola technicznie powiększona 2× wymaga dwukrotnie większego
okna raw. Globalny rekord `map_geometry` w `feature-provenance.json` ma
historyczne nazwy pól `*_raw_px`, lecz opisuje spacing=1; dla pozostałych
obrazów należy podzielić wartości przez `pixel_spacing_xy`. Ekstrakcja,
audyt kontekstu i kontury przeglądarki wykonują to przeliczenie.

Główne porównanie `common` używa przecięcia geometrii wszystkich warunków
danego kontrastu. `own` pokazuje własną dostępność i jej koszt; jego różnice
nie są czystym efektem cech przy stałych mianownikach. Brak cechy nie usuwa
miejsca z mianownika jakości. Nowe treningowe przecięcie uwzględnia również
większe lub przesunięte okna i historyczny bufor między obszarami danych.

Stały graf pełnej klatki pochodzi z transdukcyjnego FFT48, także w transferze.
Ograniczanie zakresu usuwa węzły i krawędzie bez przeliczania promienia.
To pozwala porównywać warianty E5, ale różni się od dawnego grafu transferu
budowanego na podzbiorze; nie deklarujemy replay historycznych podziałów.

FH k=4 i MWS. Minimum 4 na siatce, 8 na centrach. Bramka H_M1 i pełna
A_fixed_M1 pozostają z wejścia 48: nie zmieniają się razem ze skalą.
Mniejsze okno może odzyskać wejście poza dostępnością bramki 48, lecz takie
miejsce dostaje po odmowach stan braku bazowej bramki. E5 nie testuje nowej
bramki dla 32 ani nie uznaje tego przypadku za dowód braku uporządkowania.

## Przeglądarka i odbiór ręczny

Lokalny plik: `.scratch/ml-e5-20261111/index.html`.

```bash
xdg-open .scratch/ml-e5-20261111/index.html
```

Oba panele pokazują ten sam obraz i oryginalne miejsca molekuł. Lewy panel
zawiera bazę wybranego kontrastu, prawy wybrany wariant. Kolory przedstawiają
instancje domen na danej klatce; nie śledzą ich tożsamości w czasie.
Centra są danymi wejściowymi, a nie nowo wykrytymi molekułami.

1. Zacząć od TTMAPP 259, centrów, transdukcji, AE, ziarna 20261101, FH, H_M1.
   W porównaniu mapy przełączać bazę i pełną mapę. Baza po obu stronach
   ma dawać dokładnie ten sam podział.
2. Przełączyć porównanie skali oraz 32/48/64/wiele skal. Porównać `common`
   z `own`, obserwując liczniki dostępnych wejść i przypisanych molekuł.
3. Kliknąć punkt: porównać jego oryginalne centrum, centrum wycinka i obrys
   wymaganych okien. W centrowaniu na siatce obrys się przesuwa, molekuła nie.
4. Obejrzeć wynik przed odmowami, H_M1 i pełną bramkę. Brak wejścia,
   brak bramki 48, niepoprawna cecha i odmowa nie oznaczają tego samego.
5. Sprawdzić kontrolę jednej sieci, zmianę orientacji, granicę przesunięcia,
   niezależne rzędy oraz techniczne powiększenie 2×. Nie oceniać metody
   wyłącznie po liczbie kolorowych miejsc na STM.

Odbiór ręczny przez użytkownika pozostaje osobny od technicznych testów galerii.

## Ograniczenia interpretacji

Referencja STM obejmuje konserwatywne wnętrza, nie pełne rzeczywiste granice.
Nieoznaczone miejsca nie są negatywami. Pomocnicze prostokąty A/B z `data/temp`
służą wyłącznie do audytu zawartości okna; nie stały się nowymi klasami.
Zawieranie okna w tym prostokącie nie jest równoważne zawieraniu w domenie.

Pokrycie oznacza udział przypisanych miejsc znanej referencji, a nie odsetek
wykrytych molekuł. Scalenia/podziały par są warunkowe na przypisaniu i mają
zmienne mianowniki. Cięcia grafu na centrach nie są pełną granicą pikselową;
odmowa na końcu krawędzi nie liczy się jako poprawne wykrycie granicy.
Metryki granic rastrowych dotyczą tylko syntetyków próbkowanych siatką.

Wyniki każdego ziarna zachowano osobno. Mediana i zakres trzech ziaren
opisują te konkretne modele, nie przedział ufności generalizacji. Okna,
klatki tej samej akwizycji i syntetyki nie tworzą niezależnych pomiarów STM.
Materiał rozwojowy był wcześniej znany; zamrożenie predykcji przed odczytem
referencji w tym przebiegu nie zmienia go w niezależny ślepy test.

## Odtworzenie

```bash
conda activate netcat
python -m stmdomains.experiments.e5_run --out .scratch/ml-e5-nowy-przebieg
python -m stmdomains.experiments.e5_readout .scratch/ml-e5-nowy-przebieg
python -m stmdomains.experiments.e5_check_gallery .scratch/ml-e5-nowy-przebieg/index.html --out .scratch/ml-e5-nowy-przebieg/browser-check
```

Potrzebne są lokalne wejścia/cache E1/E2, dane źródłowe i istniejące checkpointy
issue21. Nowy katalog chroni poprzednie wyniki. Cechy, adaptery, predykcje,
snapshot kodu i audyty pozostają lokalnie; duże artefakty nie trafiają do Git.

Procedury: `experimental-design` i `scientific-critical-thinking`.
Źródło procedur: Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M.
(2026), *Scientific Agent Skills: A Library of Procedural Knowledge for Research
Agents*, [doi: 10.48550/arXiv.2609.00065](https://doi.org/10.48550/arXiv.2609.00065).
Metadane zweryfikowano podczas E3; cytowanie opisuje pochodzenie procedur,
nie jest dowodem skuteczności metod STM.
