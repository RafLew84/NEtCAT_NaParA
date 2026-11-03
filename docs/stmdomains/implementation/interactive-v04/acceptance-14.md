# SD-V4-14 — eksport CSV i PNG

Data **2026-11-03**, baza `0288aa7`, implementacja `a20e14b`, poprawka `361a7d0`.
Gałąź `domains/interactive-v04-ui`, worktree `/home/rlew/projekty/NEtCAT-domains`.
[Ticket](14-export-csv-png.md), [format eksportu](export-format-v1.md).
**Odbiór ręczny użytkownika potwierdzony 2026-11-03 dla wersji `4e9f1d9`
(„testy manualne ok”).** Zapis potwierdzenia zmienia wyłącznie dokumentację;
nie ponawiano testów aplikacji ani GUI. Poniżej zachowano wcześniejsze
wyniki automatycznych testów i sprawdzeń natywnego GUI wykonanych przez agenta.

## Działanie

**Plik → Eksportuj PNG/CSV…** pozwala wybrać wynik, bieżącą klatkę lub zakres,
tabele CSV, obrazy PNG albo oba formaty, pełny obraz lub widoczny wycinek
oraz szerokość PNG. Nowy podkatalog zawiera tabele klatek, molekuł, domen
i klas oraz opis i metadane. Postęp i anulowanie są dostępne w oknie eksportu.
Istniejący katalog jest odrzucany, bez nadpisania wcześniejszych plików.

Eksport zachowuje wybrany przebieg i jego rzeczywiste parametry. Nie uruchamia
analizy brakujących klatek. W tabelach brak wyniku pozostaje pustą wartością
z jawnym statusem, a kompletny wynik bez domen ma liczbę 0. PNG zachowuje
tryb, gammę, warstwy i legendę. Wycinek nie zmienia mianowników tabel.
Pełna praca i rastry do ponownego otwarcia nadal wymagają `.stmdomains`.

## Sprawdzenia

Środowisko **netcat**, bez instalacji. TDD na publicznych granicach zapisu,
renderera i okna. Nowe testy sprawdzają:

- zgodność przypisań, ID, katalogu, parametrów, liczników i powodów odmowy
  z istniejącym wynikiem oraz eksport zakresu z jedną obliczoną klatką;
- odróżnienie kompletnego wyniku zerowego, odmowy i braku analizy;
- anulowanie, błąd publikacji i ochronę istniejącego katalogu;
- piksele obrazu z gammą, wycinek, kolory klas/domen i metadane PNG;
- regresję nakładek wychodzących poza wycinek na podpis/legendę;
- menu i okno eksportu, niezależność szkicu od parametrów wyniku,
  zgodność statusów PNG/CSV oraz zamknięcie aplikacji podczas zapisu;
- domyślny eksport pojedynczego wyniku po przejściu do innej klatki.

**Pełny zestaw 499 testów PASS**, w tym 9 nowych testów eksportu.
Pierwszy końcowy przebieg został przerwany SIGTERM (kod 143) po około
180 s, bez raportu błędu asercji; przyczyna sygnału nie została ustalona.
Ponowiono wszystkie **67 plików testów w dwóch rozłącznych grupach**:
**230 PASS w 101,44 s** i **269 PASS w 102,16 s**. Logi i dokładne listy
plików: `.scratch/stmdomains-ui-14/full-tests-part-{1,2}.log` oraz
`test-files-{1,2}.json`. Po tych wynikach nie zmieniano kodu ani testów.
Kontrola **441 lokalnych odnośników/kotwic w 9 dokumentach**, 26 ticketów,
zgodności zależności i braku cykli PASS; `git diff --check` PASS.
Kontrola długości: **12 plików kodu/testów, maksimum 691 linii**, bez
przekroczeń celu 1000 ani limitu 1500. [Przegląd](review-14.md):
Standards 0; Spec 1 P2 poprawione, recheck 0 otwartych uwag.
Mypy w zakresie aplikacji **88 plików PASS**. Dodatkowe, zbyt szerokie
wywołanie `mypy stmdomains` objęło również historyczne eksperymenty
i importy wspólne, zgłaszając 125 błędów w 31 plikach. Nie jest przyjętym
zakresem kontroli typów tej implementacji; tych plików nie zmieniano.

Polecenia końcowej weryfikacji w aktywnym `netcat`:

```bash
QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
python -m stmdomains.tools.check_code_size --base 0288aa7
```

**Natywne GUI X11 na TTMAPP — PASS, agent sterujący widocznym oknem.**
Klatka 259, ręczne K5 dopasowane z 259–268: **105/312, 5 domen**, katalog
`9d3b7286`. Eksport zakresu 259–260 sprawdzony dla surowych Domen,
wyrównanych Klas i wycinka przy gammie 1,6. Tabele były identyczne między
widokami, a przypisania i maski pozostały bez zmian. 260 zachowała
`not_in_analysis` i puste statystyki. Eksport odbywał się przy zablokowanym
dopasowaniu PCA/KMeans, bez odczytu dawnych modeli/wyników v0.4.

Obejrzano okno eksportu i gotowe PNG, w tym podpis/legendę wycinka po
poprawieniu ograniczania nakładek do obrazu. Sprawdzono anulowanie,
odrzucenie istniejącego katalogu i zakończenie pracowników. Na syntetycznej
kontroli K4 z minimalną domeną 500: `complete`, 0 domen, 0 przypisanych.
Czas eksportu dwóch klatek z CSV/PNG wynosił około 0,19–0,28 s;
484 zdarzenia pulsu GUI, największa przerwa około 0,20 s w tej próbie.
Nie jest to pomiar wydajności dla dowolnych danych ani całych 268 klatek.

Źródłowe pliki pozostały niezmienione:

- MPP SHA-256 `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`;
- JSON SHA-256 `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.

Dowody lokalne: `.scratch/stmdomains-ui-14/report.json`, `native-final.log`,
`run-20261103-211511/` z PNG, CSV, metadanymi i zrzutami dialogu.
Dużych artefaktów nie dodano do Git. **Natywny recheck po poprawce PASS**:
otwarcie projektu z 13, przejście z 259 do 260 i domyślny eksport ostatniego
wyniku zapisały tylko 259 z 105 przypisaniami, bez zmiany oglądanej 260.
Nie dopasowano modeli. Potwierdzono również pola czasu, katalogów i stanu
przebiegu w metadanych. Dowody `native-recheck.json`, `native-recheck.log`,
`navigation-recheck-dialog.png` i `navigation-recheck-20261103-212454/`.
Nie wykonano naukowej oceny detekcji ani testu awarii zasilania.

## Test ręczny użytkownika

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json` lub zapisany projekt.
   Na 259 wybierz **Analiza… → Klasy**, ręczne K5, dopasowanie 259–268;
   w **Zakres** wybierz bieżącą klatkę i kliknij **Analizuj**.
2. **Plik → Eksportuj PNG/CSV…**: wybierz wyświetlany wynik, zakres 259–260,
   oba formaty, istniejący katalog docelowy i nową nazwę podkatalogu.
   Kliknij **Eksportuj**. Otwórz PNG i CSV poza aplikacją.
   259 powinna mieć te same ID, przypisania, kolory i liczniki;
   260 powinna być bez analizy, z pustymi liczbami zamiast zer.
3. Przełącz podgląd Domeny/Klasy, widok surowy/wyrównany, gammę i warstwy.
   Wyeksportuj każdy wariant pod inną nazwą. PNG ma zachować wygląd,
   a tabele te same przypisania i mianowniki. Powiększ obraz i wybierz
   **Aktualnie widoczny wycinek**: podpis i legenda pozostają czytelne,
   zakres widoku jest podany, liczniki nadal dotyczą całej klatki.
4. Zmień szkic K na 7 bez przeliczania. Eksport nadal ma parametry istniejącego
   wyniku K5. Wybór **Tylko oznaczenia wejściowe — bez analizy** daje jawny
   brak analizy, bez dorabiania klas/domen.
5. Sprawdź zero: wygeneruj kontrolę poleceniem
   `python -m stmdomains.tools.analysis_demo .scratch/stmdomains-ui-14/manual-demo`.
   Otwórz jej `single.moltrack.json`, wybierz ręczne K4, dopasowanie bieżącej
   klatki i minimum 500 molekuł w domenie. Po analizie i eksporcie
   `frames.csv` powinno mieć `complete` i zera przypisań/domen, odmiennie
   od braków w kroku 2.
6. Ponów eksport do istniejącego podkatalogu i wskaż nieistniejący katalog
   nadrzędny: czytelny błąd, poprzednie pliki i otwarta praca bez zmian.
   Przy większym zakresie użyj **Anuluj eksport** przed zakończeniem:
   nie powstaje ukończony podkatalog. Aplikacja powinna zamknąć się bez błędu.

To odbiór funkcji zapisu i zgodności z widokiem. Udział przypisanych
molekuł oraz przybliżone obszary nie są zwalidowaną wykrywalnością
ani fizyczną powierzchnią domen.
