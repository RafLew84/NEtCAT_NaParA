# SD-V4-26 — obsługa i odbiór Level set

**Odbiór ręczny użytkownika otwarty.** Funkcja eksperymentalna; jej działanie
jest oddzielne od [wyników porównania metod](results-26.md).

## Uruchomienie i gotowe dane

```bash
conda activate netcat
python -m stmdomains.main
```

W Plik → Otwórz projekt / MolTrack wybierz:

- `.scratch/stmdomains-ui-26/demo/shared/domain-geometry.moltrack.json` — 9 kontroli:
  1 regularna sieć, 2 dwie orientacje, 3 płynne zgięcie, 4 skok fazy,
  5 brakujące centra, 6 luka, 7 szum, 8 rzędy 1D, 9 trzy centra.
- `.scratch/stmdomains-ui-26/demo/extra.moltrack.json` — 1 duża sieć i mała
  wyspa 25 centrów, 2 regularna sieć z artefaktem liniowym skanu.
- `data/TTMAPP/detection_full.moltrack.json` — obecne dane z molekułami;
  do porównania klatki 259–266.

Generowanie kontroli w innym worktree:
`python -m stmdomains.tools.levelset_demo .scratch/stmdomains-ui-26/demo`.
Dane i duże artefakty pozostają lokalne, poza Git.

## Parametry i interpretacja

**Analiza → Analiza… → Metoda domen → Level set (eksperymentalna)**.
Zakładka Level set: siła regularyzacji 0–2 (domyślnie 0,25), limit 1–500
iteracji (domyślnie 120). Siła 0 wyłącza regularyzację krzywizną.
Duża siła może usuwać małe obszary. Wynik pokazuje rzeczywistą liczbę
iteracji, limit, powód zatrzymania i liczbę regionów modelu.

Zakładka Geometria: skale kąta i rozstawu służą do inicjalizacji oraz kosztu
cech; nie są gwarancją maksymalnej rozbieżności całej domeny. Domyślnie
12°, 16%, koherencja 0,75, minimum lokalnych punktów 10, domena ≥8 molekuł,
zasięg maski 0,85 NN. Łączenie krawędzi grafu jest nieaktywne.
Zaawansowane: bariery obrazu. Ustawienie minimum długości **100 NN**
wyłącza bariery dla dostarczonych danych; wariant domyślny ma **3 NN**.

Obliczanie dotyczy bieżącej klatki. Przełącznik **Geometria / Level set**
nad obrazem pokazuje zachowane wyniki bez przeliczania. Domena jest
spójnym obszarem z rzeczywistymi centrami, a region modelu może dać wiele
domen. Nie powstaje katalog klas ani zwalidowana nazwa struktury.
Widok Klasy pokazuje typ nieznany; do oceny wybierz Domeny.
Szare centra pozostają nieprzypisane; kliknięcie podaje przyczynę.

## Test ręczny

1. Otwórz wspólne kontrole, klatkę 1. Oblicz Geometrię i Level set przy
   domyślnych ustawieniach. W obu oczekujemy **7 domen / 63 przypisania**;
   referencja to jedna sieć, więc jest to rozdrobnienie, nie sukces metody.
   Powiększ obraz, przełącz wyniki: klatka i zoom pozostają bez zmian.
2. W Zaawansowane zmień minimum długości barier na 100 NN. Samo wpisanie
   nie zmienia obrazu. Oblicz ponownie obie metody: **1 domena / 63 przypisania**.
   Włącz/wyłącz wypełnienia, obrysy i numery w Obszary…; centra pasują do maski.
3. Wróć do barier 3 NN; sprawdź klatki 2, 4, 5 i 6 oraz oba dodatkowe
   przykłady. Porównaj oczekiwania generatora i faktyczne wyniki z tabelą
   raportu. Skok fazy daje **0 domen** z barierami — obie domeny pominięte.
   Szum i rzędy 1D dają zero domen; nieobliczona klatka pokazuje brak analizy.
4. W Level set zmień siłę na 1 i limit na 1. Przed Analizuj dotychczasowy
   wynik pozostaje. Po obliczeniu na danych z kilkoma regionami modelu
   status to „osiągnięto limit”. Jeden region nie wymaga ewolucji. Przywróć
   0,25 / 120, oblicz: powtarzalne przypisania i maska. Zmiana siły nie musi
   zmienić obrazu, zwłaszcza gdy istnieje tylko jeden region modelu.
5. Otwórz TTMAPP, kolejno oblicz Geometrię i Level set na klatkach 259–266.
   Domyślne ustawienia: po jednej domenie, przypisania kolejno
   **32, 38, 33, 40, 40, 35, 41, 35**. Suwak i miniatury przywracają właściwy
   wynik klatki; 258 bez obliczeń nie dziedziczy 259.
6. Anuluj przeliczanie, przejdź na inną klatkę w trakcie pracy, następnie
   wróć. Zachowany wynik nie zmienia się. Zamknij aplikację podczas zadania;
   nie powinno być wyjątku ani podmiany wyniku spóźnionym zadaniem.
7. Zapisz wybrany Level set i otwórz projekt. Przypisania, maska, metoda,
   parametry i szkic ustawień odtwarzają się bez przeliczania. Projekt
   przechowuje wybrany wynik, nie pełną historię porównań metod.
8. Utwórz ręczną klasę lub poprawkę domeny na kopii wyniku; przelicz automat.
   Wybierz wcześniejszy wariant korekty: pozostaje niezależny. Zapis Po korektach
   odtwarza Cofnij/Ponów. Eksport PNG/CSV obejmuje wybrany wariant oraz
   bazowe/końcowe przypisania. Sprawdź obraz oryginalny i wyrównany.

## Wykonane sprawdzenia

Protokół `d949bfe` poprzedził pomiary. Wykonano 152 warianty kontroli/TTMAPP
bez błędów; szczegóły i ograniczenia w [raporcie](results-26.md).
Testy publicznego API: dwie orientacje, okresowość osi i wspólne dopasowanie
kierunek–rozstaw, luka/brak pomiaru, bariery, kalibracja anizotropowa,
wpływ regularyzacji na rzeczywistą maskę, spójność centrum–maska,
powtarzalność, limit, anulowanie i brak danych.
Testy Qt: porównanie bez utraty zoomu, szkic, anulowanie, nawigacja,
zapis/odczyt/eksport oraz zachowanie osobnych ręcznych korekt.
Końcowe wyniki regresji, przeglądu i natywnego GUI zostaną dopisane po ich zakończeniu.
