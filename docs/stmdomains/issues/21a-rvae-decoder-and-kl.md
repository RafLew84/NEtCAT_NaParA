# Czy zmiana dekodera i regularyzacji pozwoli rVAE odtworzyć strukturę sieci?

ID: 21a
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 20, 21

## Question

Czy słaby wynik rVAE z [21](21-autoencoder-domains.md) wynika częściowo
z uproszczonego dekodera lub wagi regularyzacji KL? Sprawdzić te dwa czynniki
w małej, zamkniętej próbie na obecnych danych, bez ponownego strojenia
bramki porządku i bez rozszerzania zbioru MPP/STP.

**Decyzja użytkownika — 2026-10-31:** utworzyć osobny ticket z rekomendacją
uzupełnienia 21 przed lokalnym SSL. Kolejność: **21a → 22 → 23**.
Dodanie zadania nie uruchamia treningu. Pierwsza próba 21 pozostaje
`resolved`; jej raport, konfiguracje, wagi i predykcje są zamrożonym
punktem odniesienia. Niniejszy ticket określa dodatkowy budżet, osobny od
27 fitów [protokołu 20](../self-supervised-training-protocol.md).

## Uzasadnienie i hipotezy

[Raport 21](../autoencoder-domains-trial.md) pokazuje rekonstrukcje rVAE
zdominowane przez łagodny gradient, mały efektywny rząd kodu i silny związek
z jasnością. Surowy kąt nie odtwarza znanych różnic orientacji. Dekoder ma
dwie warstwy po 64 jednostki `Tanh` i otrzymuje surowe współrzędne pikseli;
jest inną, znacznie mniejszą częścią modelu niż dekoder konwolucyjnego AE.
Nie jest to dowód błędu implementacji ani nieskuteczności całej rodziny rVAE.

Kodowanie Fouriera współrzędnych jest hipotezą poprawy odtwarzania drobnych
wzorów: [Tancik i in., 2020](https://arxiv.org/abs/2006.10739) pokazują jego
przydatność dla sieci MLP reprezentujących funkcje o wysokich częstotliwościach.
Praca nie potwierdza skuteczności naszego modelu na domenach STM.
Wpływ KL trzeba zbadać osobno; nie wykazano, że ten składnik dominuje stratę.
Samo wydłużenie treningu nie jest wybraną poprawką: w 21 walidacja pogarszała
się po najlepszym checkpointcie zarówno dla AE, jak i rVAE.

## 1. Diagnostyka na małym zbiorze treningowym

1. Wybrać deterministycznie 16 dostępnych wycinków wyłącznie z części
   `transfer_split=train`, bez ramek domen lub doboru po rekonstrukcji.
   Przed uruchomieniem zapisać regułę wyboru, ID, skalę i hashe wejść.
2. Dla oryginalnego rVAE z32 porównać `beta=1e-3` i `beta=0`, po jednym
   uruchomieniu z ziarnem 20261101. Te same inicjalizacje, wycinki i batche;
   brak augmentacji w tej próbie zapamiętania. Zachować ten sam sposób
   losowania posteriora: jednoczesne wyłączenie losowania mieszałoby wpływy.
3. Limit: **dwa runy po najwyżej 2000 kroków i 5 minut**, bez restartów.
   Raportować MSE, KL, obrazy wejścia/rekonstrukcji i zachowanie szczegółów,
   oddzielnie od wyniku na danych nieużytych w treningu. Niefinite strata
   lub błąd wykonania są wynikiem technicznym, nie oceną skuteczności metody.

To sprawdzenie zdolności odtwarzania kilku obrazów, bez wniosku o domenach
lub uogólnianiu. Wagi diagnostyczne nie inicjalizują pełnych fitów i nie
trafiają do oceny domen. Wynik nie otwiera przeszukiwania kolejnych ustawień.

## 2. Zamknięta macierz dekoder × KL

Wszystkie pełne fity dotyczą **rVAE z32 w transferze**. Zachować podział,
normalizację, trzy skale treningowe, sampler, augmentacje, encoder,
optimizer i regułę wyboru checkpointu z 20/21. Używać tych samych trzech
ziaren: **20261101, 20261102, 20261103**. Nowe modele trenować od początku.

| Dekoder | Docelowe beta KL | Rola i liczba nowych fitów |
| --- | --- | --- |
| Oryginalny MLP | 1e-3 | Trzy zachowane modele z 21; bez retreningu |
| Oryginalny MLP | 1e-4 | Wpływ słabszej regularyzacji; 3 fity |
| MLP z kodowaniem Fouriera współrzędnych | 1e-3 | Wpływ zmiany dekodera; 3 fity |
| Ten sam dekoder Fouriera | 1e-4 | Współdziałanie obu zmian; 3 fity |

Kodowanie sinus/cosinus nakładać **po obrocie i przesunięciu współrzędnych**.
Wejściem oraz celem pozostaje obraz przestrzenny; nie zastępować go modułem
FFT tracącym fazę. Przed pierwszym fitem zamrozić częstotliwości, sposób
łączenia kodowania z latentem, dokładne warstwy, parametry i hash kodu.
Wprowadzić jedną wersję kodowania, bez przeszukiwania pasm lub rozmiarów.
Pozostałe warstwy dekodera zachować; ujawnić zmianę liczby parametrów.

KL narasta przez te same 200 kroków do docelowego beta danej konfiguracji.
Walidacja od początku używa jej stałego docelowego beta, tych samych
wycinków i zapisanych transformacji. MSE i KL pokazywać osobno; różne
ważone straty nie są wspólną miarą jakości domen ani rankingiem modeli.
Dodatkowo porównać MSE, KL i efektywny rząd kodu przy wspólnym kroku 2000,
korzystając z zapisanych checkpointów, bez nowych treningów. Brak tego
checkpointu po przerwaniu oznacza niedostępną diagnostykę, nie zastępczy
krok. Wynik domen dla wybranych checkpointów dotyczy całej procedury:
zmiany beta wraz z walidacyjnym wyborem modelu. Nie przypisywać go wyłącznie
wpływowi KL przy identycznym czasie uczenia ani wybierać ponownie modelu
po obejrzeniu wyników kroku 2000.

**Budżet dodatkowy:** najwyżej dziewięć pełnych fitów po 2000 kroków,
15 minut, batch64 i float32, z limitami 8 GiB tensorów GPU i 12 GiB RSS.
Łącznie z diagnostyką: do 22 000 kroków i 2 h 25 min treningu; najwyżej
4 GiB dodatkowych checkpointów oraz 2 h CPU przygotowania i oceny.
Są to limity, nie prognozy czasu. Przekroczenie lub nieudany run zużywa
swój budżet; bez zastępczego ziarna, restartu lub zwiększania limitu.
Dziewięć fitów SSL w 22 zachowuje własny budżet z 20.

## 3. Ocena i niezależność danych

- Obecne 81 kontroli ujawnionych w 21 traktować jako materiał rozwojowy.
  Po zamrożeniu planu odłożyć nowe, nieużywane ziarna tych samych 27 przypadków,
  po trzy realizacje. Nie używać ich do treningu, wyboru wariantów lub progów.
  Zamrozić komplet predykcji przed odczytem prawdy nowych kontroli.
- Zachowane modele transferowe z32 rVAE/AE (po trzy ziarna) oraz bazę FFT
  transferu z 21 uruchomić na nowych kontrolach
  bez retreningu i ponownego dopasowania adapterów lub bramki. Porównywać
  modele na identycznych obrazach, a nie wyniki ze starych i nowych ziaren.
- TTMAPP i jego ramki są już obejrzane: wynik jest oceną rozwojową,
  nie nowym niezależnym testem rzeczywistego STM. Zachować pasy i bufory
  transferu; pełne nakładki oddzielić od metryk na grafie części testowej.
- Główne porównanie: skala48, siatka16, FH i MWS, przed i po istniejących
  odmowach. Adaptery cech dopasować wyłącznie na dozwolonym treningu według
  tej samej reguły co w 21. Bramka, jej progi, reguły budowy grafu i algorytmy
  podziału pozostają te same; nowe cechy mogą zmienić relacje i przypisania.
- Oceniać rekonstrukcję, efektywny rząd kodu, związek cech z jasnością,
  znane różnice orientacji i przewidywalną reakcję kąta na obrót obrazu.
  Regułę prób obrotu i wspólne wsparcie obrazu zamrozić przed oceną;
  uwzględniać równoważne kierunki sieci, bez założenia symetrii M6.
- Pokazać scalenia, podziały, granice, pokrycie, fałszywe domeny i stabilność
  trzech ziaren, z zachowaniem definicji i progów kontynuacji z 20.
  Kontrole obejmują także niezależne rzędy, szum, pasy, przerwy i braki centrów.
  Brak mianownika pozostaje `null`; puste przypisanie nie oznacza sukcesu.

Nie zmniejszać progów jakości, aby zaliczyć nowy wariant. Poprawa wyłącznie
rekonstrukcji, kąta albo relacji przed odmowami jest wynikiem częściowym.
Stała bramka nadal może ograniczać końcowe pokrycie wszystkich modeli;
nie nazywać poprawy reprezentacji działającym detektorem domen.

## Wynik i granice zakresu

Raport ma oddzielić wpływ dekodera, KL i ich współdziałania oraz wskazać,
czy poprawa dochodzi do relacji i końcowych domen. Zachować wszystkie
trzy ziarna, koszty, przyczyny przerwania i nieudane konfiguracje. Wynik
negatywny również zamyka próbę i pozwala przejść do 22, następnie do 23.

W Git zapisać kod badawczy, raport, manifest konfiguracji i hashy oraz
polecenie odtworzenia. Wagi, obrazy, predykcje i galeria porównawcza pozostają
lokalnie w osobnym katalogu, np. `.scratch/rvae-21a/`. Zachować artefakty 21
i źródło jego prototypu. Sprawdzić odtwarzalność, poprawność nowych
transformacji i niezależność od referencji; rozróżnić testy kodu i ocenę naukową.

Poza zakresem: z16, nowe treningi transdukcyjne, inne architektury, strojenie
jasności, zwykły VAE, kolejne progi/wersje bramki z 19 oraz rozszerzenie danych.
Obecne PyTorch i dane wystarczają do tej próby; nie wymaga nowej instalacji.
Przyjęcie metody do aplikacji nadal należy do odbioru 13.

## Dependencies

- [Wykonana próba AE/rVAE](21-autoencoder-domains.md).
- [Protokół i przygotowanie treningu](20-self-supervised-training-preparation.md).
