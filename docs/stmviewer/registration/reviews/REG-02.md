# REG-02 — karta odbioru

Data sprawdzeń: 2026-10-31, Linux, środowisko `netcat`.
Status: **ready-for-review**; odbiór manualny użytkownika oczekuje.
Baza przeglądu: `e1d42d4315280d74a2c5494be93c29687909189b`.
Implementacja: `d85ba1b`; wersja ustawień i poprawka importu testów: `bcf0e70`.
Gałąź: `viewer/registration-difficult-movies`.

[Ticket](../issues/02-unnormalized-correlation.md) ·
[Instrukcja manualna](../unnormalized-correlation-manual.md)

## Wynik

Nowa metoda **Korelacja bez normalizacji (v1)** (`phase_no_normalization`)
działa w oknie pary i pełnej rejestracji. Korzysta z publicznego backendu NanoTrack
z `normalization=None`, bez zmian kodu współdzielonego. Konfiguracja v1 jest jawnie
ustalona: upsample 20, próg tekstury 1e-8; pozostałe ustawienia piku pozostają 3/3,
ale jego wskaźnik nie jest używany do oceny nowego wariantu. Pozostaje konwersja
float32 i odjęcie średniej, wykonywane wcześniej przez ten sam backend.
Nie dodano filtrów ani masek. Domyślna metoda to nadal Phase.

Estymowane wyniki mają `manual_review` i `quality_score=None`, widoczne jako
„pewność niezweryfikowana”; dotyczy to pary, serii i historii po ponownym otwarciu
MPP. Klatka odniesienia zachowuje znane XY=(0,0), `ok` i 1. Brak zweryfikowanej
oceny przechodzi na kolejne skumulowane XY. Błędy estymacji nadal przerywają
próbę. Poprzedni pełny aligned jest podmieniany dopiero po sukcesie.

MPP zachowuje nazwę wraz z v1, geometrię, próbki, braki i jawny brak oceny jakości.
Nullable `quality_score` przy `manual_review` wymaga nowego czytnika Viewera;
starsze wydania mogą odrzucić cały dodatek. Szczegóły:
[format metadanych](../../mpp-metadata-format.md). Bieżący czytnik nadal przyjmuje
wcześniejsze dodatki z liczbową pewnością. AVI pozostaje prezentacją aktywnego aligned.

## Automatyczne sprawdzenia

- TDD: para bez fałszywej pewności → seria z geometrią i propagacją braku oceny →
  GUI porównania/pełnej rejestracji → MPP/AVI i ponowny odczyt. Przed implementacją
  kolejnych kroków testy kończyły się oczekiwanym RED. Uwaga o wersji również
  odtworzona testami przed poprawką. Łącznie 5 nowych scenariuszy testowych.
- Istniejące testy GUI rozszerzono o nowy wariant: podmiana po sukcesie,
  anulowanie, wyjątek, brak/failed/niefinitywny wynik, niepewność, brak bibliotek.
  Kontrolowane backendy służą wyłącznie sprawdzeniu cyklu zadania.
- Końcowy zestaw zmienionych scenariuszy i wcześniejszych rejestracji:
  **48 passed**. Osobny zestaw par/modelu/MPP wcześniej: **34 passed**.
- Mypy strict: **38 plików**. Ruff oraz `git diff --check`: bez uwag.
  Największy zmieniony plik kodu: **856 linii**, poniżej celu 1000 i limitu 1500.
- Pełne repo na `bcf0e70`: **2196 passed, 14 failed, 16 skipped**, 263,52 s.
  Zestaw 14 nazw błędów identyczny z poprzednim odbiorem: 11 MolTrack/SAM2
  i 3 NanoTrack. Nie są to błędy Viewera ani zaliczenie całego repo.
  Pierwsza próba przerwała zbieranie przez kolizję importu `test_registration`
  z MolTrack. Wspólny generator danych przeniesiono do modułu fixture Viewera;
  poprawka przeszła zestaw 48 testów także z importowaniem całego repo.

## Reproduktor MOVIE_8 1→2

CLI `tests/stmviewer/diagnostics/repro_movie8_phase.py` korzysta teraz z publicznego
`estimate_pair`, także dla `--normalization none`. Sprawdza SHA256 oryginalnego
MOVIE_8 i niezależnie dopasowuje trzy fragmenty obrazu.

| Metoda | XY [px] | Odległość od lokalnego (+14,0) |
| --- | --- | --- |
| Phase | (−0,10; +0,05) | 14,10 px — oczekiwany RED reproduktora |
| Korelacja bez normalizacji v1 | (+13,55; +0,25) | 0,51 px — PASS, próg ≤3 px |

Trzy fragmenty wskazują (+14,0), (+15,0), (+14,0). Jest to lokalna kontrola tej
pary, nie niezależny pomiar dryfu ani ocena całego filmu.

## Rzeczywiste GUI Qt xcb — sterowane skryptem

cpu.mpp: Phase → zachowanie → nowy wariant → wybór obu kart. Zachowane obraz,
zoom/pan/gamma; pełny aligned z nową metodą. Eksport przez GUI i ponowne otwarcie
MPP+JSON: 3 klatki, 83×82, znane XY i pewność [1,null,null]. AVI FFV1: 3 klatki,
7 FPS, 84×92 (proporcje fizyczne źródła). Końcowe v1 ponownie sprawdzone w GUI,
metadanych i eksporcie. Obejrzane okna 1180×820 i 1080×760: nazwa mieści się,
brak poziomego przewijania pary. Pionowe przewijanie szczegółów działa.

| Film | Pełne klatki | Aligned W×H | Czas lokalnej próby |
| --- | ---: | --- | ---: |
| MOVIE_8 | 84 | 780×754 | około 1,55 s |
| MOVIE_4 | 364 | 368×1213 | około 2,26 s |

Czasy są pojedynczą obserwacją stanowiska, bez gwarancji wydajności. Pełne filmy
sprawdzono na `d85ba1b`; końcowa poprawka v1 nie zmienia obliczeń. W obu filmach
rzeczywiście anulowano kolejną rejestrację w trakcie estymacji, zachowując wcześniejszy
obraz i opis aligned. SHA256 źródeł bez zmian. Szczyt RSS procesu po obu filmach
około 1,91 GiB obejmuje całą próbę GUI, nie izolowany algorytm.

To automatyczna kontrola rzeczywistego GUI. Windows, zewnętrzny VLC i wizualna
ocena jakości wszystkich par przez użytkownika pozostają niewykonane w tej sesji.
Lokalne artefakty: `data/registration-reg02-review/` — logi, raporty, skrypty,
zrzuty i małe eksporty. Pliki pomiarowe i artefakty pozostają poza Git.

## Standards

**0 uwag** dla końcowego zakresu `e1d42d4…bcf0e70`.
Jawne ustawienia wariantu v1 i wersjonowana nazwa zapewniają jego rozpoznawalność
w parze, serii oraz MPP. Przeniesienie wspólnego generatora klatek do modułu fixture
usuwa kolizję importów bez zmiany testowanych zachowań. Zakres aplikacji, publiczne
granice testów i limity plików pozostają zachowane. Nie stwierdzono naruszeń standardów
ani istotnych problemów projektowych. Przegląd odczytowy i niezależny od osi Spec.

## Spec

**0 pozostałych uwag** dla `e1d42d4…bcf0e70`.
Pierwotna uwaga dotyczyła braku wersji ustawień wymaganej przez plan. Naprawiono ją:
konfiguracja v1 jest jawna, a oznaczenie przechodzi przez wynik pary, serię i historię
MPP. Test GUI ponownego odczytu sprawdza zachowanie nazwy. Produkcyjne None,
wspólny estymator, zachowany Phase, niezweryfikowana pewność, ochrona poprzedniego
wyniku, MPP/AVI i reproduktor są zgodne ze specyfikacją.

Standards: 0 uwag; Spec: 1 naprawiona, 0 otwartych.

## Ręczny odbiór użytkownika

Oczekuje zgodnie z [instrukcją](../unnormalized-correlation-manual.md).
Należy ocenić pokrycie struktur na stałych parach obu filmów i odnotować
poprawę, pogorszenie albo niejednoznaczność. Pełne zakończenie obliczeń i mniejszy
obszar aligned nie potwierdzają fizycznej poprawności przesunięć. REG-03 czeka
na odbiór REG-02 i osobne zlecenie.
