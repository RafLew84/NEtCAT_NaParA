# 05: Zoom, gamma i brakujące próbki

**What to build:** Użytkownik reguluje gamma, przybliża i przesuwa obraz oraz rozpoznaje brakujące próbki podczas ręcznego przeglądania serii.

**Blocked by:** [02: Otwarcie i przeglądanie serii STP](02-stp-series.md)

**Status:** ready-for-agent

**Specyfikacja:** [Podgląd, gamma i odtwarzanie serii](../../issues/02-preview-playback.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Układ B zachowuje główny obraz, ustawienia po prawej i dolny pasek miniatur; ręczny wybór synchronizuje suwak, numer i miniatury.
- [ ] Gamma 0,1–4 jest wspólna dla serii, domyślnie 1; zmienia wyłącznie prezentację. Miniatury pozostają original z gamma 1.
- [ ] Zoom pod kursorem, przesuwanie i Dopasuj działają. Zmiana klatki zachowuje powiększenie i położenie widoku.
- [ ] NaN pokazuje szachownica niezależna od gamma; prawidłowe czarne piksele są od niej odróżnione. Obsłużony jest obraz stały i całkowicie brakujące próbki.
- [ ] Nowy poprawny import resetuje gamma i dopasowuje widok; nieudany import zachowuje poprzednie ustawienia.
- [ ] Obrazy zachowują właściwe proporcje z wiarygodnej skali X/Y, a przy jej braku używają pikseli; znane wartości zastępcze nie stają się potwierdzoną kalibracją.

## Testy automatyczne

- Niemutowanie danych pomiarowych przez podgląd, gamma/maska i obsługa danych stałych lub brakujących.
- Zmiana klatki i import przez publiczne akcje GUI: zachowanie albo reset ustawień zgodnie z kontraktem.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Działanie na serii → obserwowalny stan** — Sprawdza wybór, odtwarzanie, usuwanie i transakcyjną podmianę; nie mierzy fizycznej płynności ekranu.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Otwórz serię STP i zmień gamma, zoom oraz przesunięcie. Wybierz kolejne klatki; ustawienia pozostają.
2. Sprawdź przybliżenie pod kursorem, przyciski powiększania i Dopasuj.
3. Otwórz przygotowane wzorce z NaN, stałą klatką i bez ważnych próbek. Zmiana gamma nie zmienia szachownicy.
4. Wczytaj nową poprawną serię i sprawdź reset, a następnie wadliwą i sprawdź zachowanie obecnego stanu.

## Współpraca z integracją

Jeśli używany wspólny viewer zastępuje NaN medianą, dostosować adapter/prezentację Viewera; modyfikacje wspólnego widgetu prowadzi integracja. Nie przejmować funkcji ROI/trackingu innych aplikacji.


## Wcześniej dostarczony zakres — zoom i przeciąganie

Na wyraźne zlecenie użytkownika z 2026-10-21, po ręcznym odbiorze ticketu 01,
przyspieszono podstawową nawigację pojedynczego obrazu. Baza zmiany: `7a43715`.
Kółko przybliża/oddala pod kursorem; przeciąganie lewym przyciskiem przesuwa
obraz bez zmiany powiększenia. „Dopasuj” przywraca cały obraz na środku.
Nowy poprawny import resetuje widok, anulowanie i błąd zachowują go.
Krok kółka zmienia skalę o czynnik 1.2, zakres to 0.1–64 razy dopasowanie.
Testy działają na uzgodnionej granicy publicznych kontrolek GUI.

Ten dodatek nie zamyka ticketu 05 ani jego zależności. Ticket 02 dostarczył
miniatury, synchronizację kontrolek i zachowanie zoomu oraz przesunięcia przy
zmianie klatki. Nowy poprawny import dopasowuje obraz. Gamma, szachownica
i pozostałe kryteria tego ticketu nadal czekają na realizację.
Ręczna próba dodatku: [nawigacja obrazu](../../single-stp-manual.md#zoom-i-przesuwanie).


Commit dodatku: `75f419d`. [Przegląd](../review-preview-navigation.md): bez uwag.
19 testów Viewera i mypy strict przechodzi; automatyczna próba na ekranie
Linuksa potwierdziła zoom, przesuwanie i Dopasuj na rzeczywistym STP.
Użytkownik potwierdził ręczny odbiór dodatku 2026-10-21: „testy manualne ok”.
Dotyczy to zoomu i przeciągania dostarczonych w `75f419d` (raport `df4bbc5`);
pozostałe wymagania całego ticketu 05 nadal czekają na realizację.
