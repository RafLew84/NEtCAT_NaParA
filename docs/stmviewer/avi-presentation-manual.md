# Ticket 15 — kontrast, gamma i tła AVI

Od ticketu 17 dostępne są [opcjonalne opisy AVI](avi-annotations-manual.md).
W poniższej próbie pozostaw je wyłączone, jeśli krok nie wymaga ich użycia.

Użytkownik potwierdził testy manualne 2026-10-26; ticket 15 ma status **done**.
Poniższy scenariusz służy do powtórzenia próby. Z katalogu repozytorium:

```bash
conda activate netcat
python -m stmviewer.main
```

W oknie **Zapisz AVI…** doszły trzy wybory:

- **Gamma**: z podglądu (widać pobraną wartość) lub neutralna 1.
- **Kontrast**: osobno dla każdej klatki lub wspólny dla wybranego zakresu filmu.
- **Tło braków**: czarne (0), szare (128) lub białe (255).

Domyślne ustawienia pozostały bez zmian: gamma podglądu, kontrast osobny,
czarne tło. Nowe otwarcie dialogu przywraca te wartości domyślne. Podgląd
nadal ma białe tło; wybory filmu nie zmieniają wyglądu podglądu ani MPP.

## Dane do próby

Gotowy lokalny plik: `data/avi-ticket15/presentation.mpp` wraz z JSON.
Odtworzenie małego wzorca:

```bash
PYTHONPATH=. python tests/stmviewer/make_avi_presentation_fixtures.py
```

Pięć klatek 65 × 49; wynik AVI 66 × 50. Klatki 1–3 mają dwa pasy pomiaru
(po 20 kolumn), a od kolumny 41 do prawej krawędzi brakujące próbki.

| Klatka | Lewy pas | Prawy pas / reszta obrazu |
| --- | --- | --- |
| 1 | −1000 | 1000, następnie brak próbek |
| 2 | 100 | 125, następnie brak próbek |
| 3 | 125 | 200, następnie brak próbek |
| 4 | Brak próbek | Brak próbek |
| 5 | 125 | Cały obraz stały 125 |

Gotowe lokalne AVI mają prefiksy `per-frame`, `shared-full`, `shared-range`,
`gray-gamma2` i `white-gamma1`, każdy w MJPG oraz FFV1. Służą do porównania;
poniższa próba wymaga też wykonania własnego zapisu z GUI.

## Scenariusz w programie

1. Otwórz wzorzec. Ustaw gamma podglądu 2. Wejdź w **Zapisz AVI…**.
   Początkowo wybór to „Z podglądu (2)”, kontrast osobny i czarne tło.
   Ustaw zakres **2–5**, FPS **1**, gamma **Neutralna (1)** oraz FFV1.
2. Zapisz z kontrastem **Osobno dla każdej klatki**. Na klatkach 2 i 3
   lewy pas jest czarny, prawy biały. Klatka 4 pozostaje czarna, klatka 5
   jest szara (127). Film trwa 4 s i zachowuje wszystkie cztery klatki.
3. Zapisz ten sam zakres z kontrastem **Wspólny dla filmu**. Poziomy są
   100–200: klatka 2 ma pasy 0 i 63, klatka 3 pasy 63 i 255. Wartość 125
   ma identyczną jasność we wszystkich klatkach, także w stałej klatce 5.
4. Zostaw wspólny kontrast, ale wybierz **Cała seria**. Klatka 1 rozszerza
   poziomy do −1000–1000; pozostałe pomiary stają się podobnie szare.
   Wróć do zakresu 2–5 — wykluczona pierwsza klatka nie wpływa na kontrast.
5. Dla zakresu 2–5 porównaj gamma neutralną i pobraną z podglądu. Przy gamma 2
   jasność wartości 125 we wspólnym kontraście zmienia się z 63 na 127.
   Sprawdź wszystkie trzy tła: brakujące próbki, cała pusta klatka oraz
   dopełnienie z prawej/dołu pozostają wybranym kolorem niezależnie od gamma.
6. Wybierz tylko klatkę 5. W obu trybach kontrastu stały zakres daje 127
   przy gamma 1 i 180 przy gamma 2. Wybierz tylko klatkę 4: cały film ma
   kolor wybranego tła, bez błędu i bez pominięcia klatki.
7. Powtórz porównanie w MJPG. Geometria i zasady są takie same, ale kompresja
   może zmieniać jasności przy krawędziach. FFV1 zachowuje dokładny raster.
8. Na dłuższym filmie zmień gamma podglądu podczas zapisu: rozpoczęty AVI
   zachowuje ustawienia z dialogu. Przy wspólnym kontraście najpierw widać
   postęp **Poziomy kontrastu**, potem kodowanie i sprawdzanie filmu.
   Anulowanie także w czasie liczenia poziomów zachowuje wcześniejszy plik.

Do dłuższej próby można użyć istniejącego `data/avi-ticket14/long.mpp`;
[poprzednia instrukcja](original-avi-manual.md) opisuje opcjonalny generator.
Zmiany poziomów liczy worker, bez układania całego filmu w dodatkowej tablicy.

Od ticketu 16 pole **Obrazy** pozwala wybrać original lub gotowy aligned,
domyślnie aktualny podgląd. Powyższy scenariusz wykonuj z original.
[Próba aligned](aligned-avi-manual.md) obejmuje geometrię rejestracji.
Gotowy aligned otwarty z MPP jest wejściowym original bieżącej serii.

Lokalna tymczasowa kopia VLC z poprzedniego etapu:

```bash
/tmp/stmviewer-avi-vlc/vlc data/avi-ticket15/shared-range-FFV1.avi
```

Dostępna do usunięcia katalogu `/tmp/stmviewer-avi-vlc/`. Windows i ręczne
potwierdzenie użytkownika są odrębne od automatycznych prób Qt i odtwarzania
VLC na ekranie testowym.

## Wyniki techniczne — 2026-10-26

- **57 passed**, 12.83 s: renderer, wszystkie 24 kombinacje opcji i kodeków
  przez GUI z odczytem filmu, zamrożenie opcji, anulowanie i regresje eksportu.
  Log: `/tmp/stmviewer-avi15-focused.log`.
- **34 passed**, 9.69 s: GUI na Qt xcb/Xvfb, w tym nowe opcje i cykl zapisu.
  Obejrzano dialog; log `/tmp/stmviewer-avi15-xcb.log`.
- **VLC 3.0.20** faktycznie odtworzył 10 przygotowanych AVI: oba kodeki,
  kontrasty, tła i gamma. Wszystkie filmy zakończyły się kodem 0 po EOF,
  z działającym wyjściem obrazu xcb_x11, bez błędów. Obejrzano zrzuty.
  Logi, obrazy i `results.json`: `/tmp/stmviewer-avi15-vlc/`.
- Mypy: 31 plików, 0 błędów. Przegląd Standards i Spec: bez uwag.
- Pełne repo: 2095 passed, 14 failed, 16 skipped (259.60 s), identyczne
  wcześniejsze niepowodzenia MolTrack/NanoTrack. Log:
  `/tmp/stmviewer-avi15-full-suite.log`.

Ręczna akceptacja użytkownika: **zaliczona**, 2026-10-26 („testy manualne ok”).
Potwierdzenie obejmuje implementację `3e1fddf` i przekazanie `e80a93d`.
Nie wskazano systemu; odrębne odbiory Ubuntu i Windows w ticketach 20 i 21
pozostają otwarte.
