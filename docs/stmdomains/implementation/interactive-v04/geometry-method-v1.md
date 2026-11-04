# Pomiar geometrii 16 — zamrożony protokół próby

2026-11-04, ustalony przed oceną TTMAPP. Wariant UI C wybrany przez użytkownika.
Metoda `geometry-fourier-1`: lokalna koherencja położeń centrów, wzorowana na
finite-count Fourier z v0.4 / obecnego `analysis/order.py`. Nowe są jawne
kierunki rzędów, rozstawy, metryka X/Y, dwa niezależne kierunki i stabilność
względem otoczenia. Nie dopasowujemy klas i nie zmieniamy segmentacji.

- Dane: oryginalne centra jednej klatki; obraz ustala granice i identyfikację
  wejścia. To pomiar położeń, nie FFT intensywności obrazu. Punkty poza polem
  i bliskie duplikaty są pomijane. Tłumienie duplikatów w metryce pomiaru,
  próg 0,4 mediany odległości do trzeciego sąsiada, jak w metodzie bazowej.
- Skala: mediana NN po odrzuceniu duplikatów. R=3 skale NN, sigma=4/3 skali.
  Wagi Gaussa, n≥10 (łącznie z centrum), Neff=(Σw)²/Σw²≥8.
- Koherencja: (|Σw exp(2πi q·r)|²−Σw²)/((Σw)²−Σw²).
  61 częstości 0,5–2 cykle / skalę NN; 90 kątów normalnej w [0,180).
  Do 24 lokalnych maksimów ≥0,70; preferencja mniejszej częstości,
  doprecyzowanie L-BFGS-B (±0,04 składowej q, 30 iteracji).
  Przyjmujemy koherencję ≥0,75, z dala o 0,005 od krańców zakresu;
  co najmniej 3 zajęte płaszczyzny fazowe i rozpiętość ≥1,8 okresu.
- Do dwóch normalnych różniących się o ≥25°. Kierunek rzędu = normalna+90°,
  okres poprzeczny = 1/f (częstość w cyklach, bez dodatkowego 2π).
  Dwa kierunki oznaczają lokalną dwukierunkową periodyczność centrów;
  nie są pełną bazą krystalograficzną ani identyfikacją fazy chemicznej.
  Okres wzdłuż rzędu nie jest wyznaczany z drugiego piku.
- Stabilność: powtarzamy pomiar przy R×0,9 i R×1,1 ze stałym sigma.
  Oś musi znaleźć odpowiednik w obu pomiarach: Δθ≤5° modulo180,
  |f/f′−1|≤0,10. Raportujemy największe zmiany. Brak stabilnej osi
  nie daje kreski kierunku. To nie przedział ufności ani prawdopodobieństwo.
- nm tylko gdy obie amplitudy X/Y mają jawne rozpoznane jednostki,
  są dodatnie, a wymiary z nagłówka zgadzają się z obrazem. Skala=amplituda/N,
  nie /(N−1). Brak jednej osi → px dla obu. To kalibracja według nagłówka,
  bez niezależnego potwierdzenia metrologicznego. Kąt od osi X obrazu,
  przeciwnie do wskazówek zegara; przesunięcia rejestracji nie obracają osi.
- Podsumowanie domeny: niezważona średnia exp(2iθ), rozrzut osiowy
  sqrt(−2 ln R)/2; R<0,5 → średni kierunek niejednoznaczny. Rodziny osi
  dopasowane do pierwszej molekuły z największą liczbą osi przez najmniejszą
  różnicę osiową. Każda rodzina ma własne n, medianę i zakres rozstawu.
  Jest to opis heterogeniczności, nie test jednorodności domeny.
- Limity: 3000 oznaczeń, 4 194 304 piksele. Anulowanie między otoczeniami
  i doprecyzowaniami. Ustawienia stałe w 16; edycja tolerancji dotyczy 17.

Kontrole: sieć 17°/47°, anizotropowa skala, dwie orientacje, granica fazy,
brakujące centra, przerwa, szum, losowe położenia w rzędach i mało punktów.
Znane kąty/okresy sprawdzamy w środku regularnego pola. Granica przesunięcia
nie musi zmieniać kąta/rozstawu: pomiar nie jest nowym detektorem granic.
TTMAPP: klatki 259–266, te same wejścia, bazowy K5 z 259–268. Raportujemy
odmowy i zakres pomiarów; przypisania domen przed/po muszą być identyczne.
Bez referencji pomiarowej nie podajemy accuracy. Kontrole nie kalibrują
ogólnego poziomu fałszywych rozpoznań na danych eksperymentalnych.
