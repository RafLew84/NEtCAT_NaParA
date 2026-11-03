# SD-V4-13 — zapis i otwieranie projektu

Data: **2026-11-03**. Baza `5b2ddc8`, implementacja `4f40c28`, poprawki `1c9c221`.
Gałąź `domains/interactive-v04-ui`, worktree `/home/rlew/projekty/NEtCAT-domains`.
[Ticket](13-save-open-project.md), [format 1](project-format-v1.md).
Status implementacji `done`; **odbiór ręczny użytkownika potwierdzony 2026-11-03 dla wersji `21fd906` („testy manualne ok”)**.
Potwierdzenie zmienia dokumentację; nie ponawiano testów aplikacji ani GUI.

## Działanie

**Plik → Zapisz projekt…** (`Ctrl+S`) i **Zapisz projekt jako…**
(`Ctrl+Shift+S`) zapisują `.stmdomains`. **Otwórz projekt / MolTrack…**
(`Ctrl+O`) czyta projekt lub wejściowy JSON. Zapis przed analizą jest prawidłowy.
Gdy istnieje wynik, wybierasz wyświetlany przebieg, ostatni przebieg, jeśli jest
inny, albo brak analizy. Wybór dotyczy dostępnego zakresu tego przebiegu,
a nie wyłącznie oglądanej klatki. Inne warianty zachowaj w osobnych plikach.

Projekt zawiera cały przyjęty MPP, oznaczenia i geometrię, wybrany wynik,
bezpieczny stan jego katalogu, widok oraz osobny szkic następnej próby.
Nie wymaga v0.4. Otwieranie nie oblicza nowych klas/domen. Zmiana parametrów
nie zmienia zapisanych metadanych wykonania. Zapis/odczyt działa w tle, ma
postęp i **Anuluj**. Zamknięcie lub otwarcie innej pracy daje
**Zapisz / Odrzuć zmiany / Anuluj**. Zapis przed opuszczeniem pracy musi się
powieść; anulowanie wyboru pliku albo błąd pozostawia okno i dane.

## Wykonane sprawdzenia

Środowisko **netcat**, bez instalacji. TDD na publicznych granicach IO,
kontrolera i okna: najpierw testy czerwone dla zapisu, przywracania analizy,
walidacji i menu, potem implementacja. Testy obejmują:

- brak analizy, utratę testowych MPP/JSON, identyczne bajty źródła i mapę klatek;
- częściowy przebieg, jawne niewykonane klatki, osobny zapis wcześniejszego
  wyniku i późniejszej odmowy Auto, zachowane ID, parametry, przypisania i maski;
- podgląd bez modelu i zakaz dopasowania PCA/KMeans przy otwieraniu;
- atomowe anulowanie, błąd publikacji, zmieniony MPP, błędną wersję, sumy,
  odwołania, stan wykonania i ustawienia widoku;
- zapis/otwarcie/Save As przez okno, oddzielny szkic, zoom/gammę/warstwy,
  anulowanie zamknięcia, zapis przed zamknięciem i zachowanie pracy po błędzie.

Pełny zestaw **490 testów PASS w 189,37 s**, uruchomiony raz na końcu
po poprawkach (14 nowych testów projektu). Mypy **82 pliki PASS**.
Kontrola długości: **25 plików, maksimum 661 linii**, bez przekroczeń celu
1000 ani limitu 1500. `git diff --check` PASS. Kontrola lokalnych odnośników,
26 ticketów, tabeli zależności i braku cykli PASS.
[Przegląd Standards / Spec](review-13.md): Standards 0 ustaleń;
Spec 2 uwagi P2 poprawione w `1c9c221`, ponowny przegląd 0 otwartych uwag.
Regresje obejmują odrzucenie pustego/błędnego stanu widoku przed publikacją,
typy tekstów renderera, weryfikację rastrów blokami bez materializacji całej
serii masek oraz potwierdzenie nadpisania końcowej nazwy pliku.

Polecenia weryfikacji (w aktywnym `netcat`):

```bash
QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q tests/stmdomains
python -m mypy --follow-imports=silent --ignore-missing-imports stmdomains/analysis stmdomains/core stmdomains/io stmdomains/ui stmdomains/tools
python -m stmdomains.tools.check_code_size --base 5b2ddc8
```

**Natywne GUI X11, rzeczywisty TTMAPP — PASS, wykonane przez agenta**
sterującego widocznym oknem. Klatka 259, ręczne K5, dopasowanie 259–268:
**105/312, 5 domen**, katalog `9d3b7286`. Po zapisie i otwarciu przy zakazie
odczytu obu oryginalnych źródeł i zakazie PCA/KMeans: identyczne przypisania,
maski, parametry, metadane i piksele wyrównanego obrazu z gammą 1,6.
Przywrócono klatkę, zoom, warstwy i szkic K7, niezależny od wyniku K5.
Klatka 260 pozostała bez analizy. Dalsze jawne **Użyj istniejących klas**
dało te same przypisania bez ponownego dopasowania.

Sprawdzono menu, dialog wyboru wyniku, niezależną kopię przez Save As,
anulowanie zapisu, odrzucenie uszkodzonego projektu oraz zamknięcie z dołączeniem
pracowników. Zapis około **4,25 s**, odczyt **1,43 s**, plik **142 121 164 B**;
puls GUI 924 zdarzenia, największa przerwa około 0,215 s w tej próbie.
Źródła pozostały niezmienione:

- MPP SHA-256 `8fbbfa5d515a90552c13cee2dbd289ff5cc16f000315547185c2a57bfe9f7c66`;
- JSON SHA-256 `d0c4cb999bede28edb5dfd18ddbe146054711382f1c78363055be2330b3cdd2e`.

Lokalne dowody: `.scratch/stmdomains-ui-13/` (`report.json`, `native-final.log`,
`before-save.png`, `reopened-offline.png`, `save-choice.png`, dwa projekty).
Nie zapisano tych dużych artefaktów w Git. Kontrole anulowanego zakresu i
Auto wykonano automatycznie na małych danych. Nie wykonywano oceny naukowej,
próby zapisu pełnej analizy 268 klatek ani testów awarii zasilania.

## Test ręczny użytkownika

Uruchom w używanym środowisku:

```bash
conda activate netcat
python -m stmdomains.main
```

1. Otwórz `data/TTMAPP/detection_full.moltrack.json`. **Plik → Zapisz projekt…**
   zapisz jako `bez-analizy.stmdomains`. Otwórz go: obrazy i oznaczenia są,
   analizy nadal brak; nie powinno rozpoczynać się dopasowanie.
2. Na klatce 259 otwórz **Analiza…**. W Klasy wybierz ręczne K5 i dopasowanie
   z wybranego zakresu 259–268, w Zakres bieżącą klatkę. Kliknij **Analizuj**.
   Zmień szkic na K7, bez analizy; ustaw gammę, powiększenie i warstwy.
3. **Zapisz projekt jako… → Wyświetlany wynik** zapisz `wariant-a.stmdomains`.
   Otwórz kopię tego pliku w nowym miejscu, najlepiej na komputerze bez źródeł.
   Nie usuwaj oryginałów pomiaru. Wynik, kolory, liczniki, widok i szkic mają
   wrócić; wynik nadal K5, szkic K7. Przejdź do 260: wynik nie jest dorabiany.
4. Wybierz istniejący katalog i jawnie uruchom analizę; nie ma pytania o model
   v0.4. Zapisz nowy wariant przez **Zapisz jako…**. Pierwszy plik ma zachować
   wcześniejszy wynik i szkic po ponownym otwarciu.
5. Oblicz zakres 259–268 i przerwij po kilku klatkach. Zapisz ostatni przebieg.
   Po otwarciu ukończone wyniki i niewykonane klatki są rozróżnione w Analiza.
   Gdy nieudana próba zostawia wcześniejszy wynik na obrazie, dialog zapisu
   pozwala oddzielnie wybrać ten wynik lub ostatnią próbę.
6. Zmień szkic/gammę, spróbuj zamknąć: **Anuluj** pozostawia okno.
   **Zapisz…** z anulowanym wyborem pliku także pozostawia okno.
   Udany zapis pozwala zakończyć; **Odrzuć zmiany** zamyka bez zapisu.
7. Spróbuj otworzyć celowo uszkodzoną **kopię** projektu i zapisać do miejsca
   bez uprawnień. Oczekiwany komunikat błędu, dotychczasowa praca pozostaje.
   Przy dużym zapisie kliknij **Anuluj** przed jego zakończeniem: stary plik
   nadal powinien otworzyć się poprawnie.

Wynik 105/312 opisuje tę konfigurację programu, nie zwalidowaną wykrywalność
molekuł ani pełne pokrycie powierzchni. Zapis zachowuje dostępne miary,
nie dopisuje brakujących obszarów i jednostek fizycznych.
