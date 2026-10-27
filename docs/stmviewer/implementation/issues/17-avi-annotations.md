# 17: Podziałka, numer i czas w AVI

**What to build:** Użytkownik może dodać do filmu podziałkę długości oraz numer klatki i dostępny czas pomiaru, zachowując czysty obraz jako ustawienie domyślne.

**Blocked by:** [15: Kontrast, gamma i tła filmu AVI](15-avi-presentation.md)

**Status:** in-progress

**Wykonawca:** Codex
**Baza przeglądu:** `f051a14303d3ed6bd344aada63d4408cfb1887d3`

**Specyfikacja:** [Opcje filmu AVI](../../issues/05-avi-export.md#answer), [Dane i kryteria odbioru pierwszej wersji](../../issues/06-acceptance.md#answer).

Przed realizacją przeczytaj [zasady wykonania i odbioru](../README.md#zasady-wykonania-i-odbioru).

## Kryteria odbioru

- [ ] Opisy są opcjonalne, domyślnie wyłączone i tworzone przez renderer filmu, niezależnie od okna oraz gamma.
- [ ] Podziałka korzysta ze wspólnej wiarygodnej kalibracji i geometrii filmu; w pozostałych przypadkach jawnie podaje px, bez fikcyjnych nm.
- [ ] Numer odnosi się do bieżącej serii: zakres 5–10 z 20 pokazuje 5/20…10/20. Czas pochodzi z pomiaru z zachowanymi przerwami, a brak czasu jest jawny.
- [ ] Opisy są czytelne na każdym tle; zbyt mały obraz daje informację przed zapisem zamiast cichego obcięcia obrazu lub pominięcia opisu.
- [ ] Opisy działają dla original oraz każdego już dostępnego wariantu aligned; techniczne dopełnienie nie zmienia skali.
- [ ] Połączenie tego etapu z eksportem aligned podlega wspólnemu odbiorowi; oba etapy mogą powstawać niezależnie na tym samym kontrakcie renderowania.

## Testy automatyczne

- Znaczenie numeru/czasu po usuwaniu i dla zakresu, przelicznik podziałki po zmianie proporcji/paddingu.
- Nieznana/niejednorodna kalibracja, czytelność i minimalny rozmiar, niezależność opisów od gamma.

## Publiczne granice testów dla TDD

Zatwierdzenie zestawu obejmuje poniższe granice. Testuj zachowanie przez te interfejsy; prywatne metody i przypadkowy podział klas nie są kontraktem.

- **Klatka i opcje prezentacji → raster filmu** — Sprawdza gamma, kontrast, maskę, geometrię i opisy; nie sprawdza kodeka ani VLC.
- **Publiczne kontrolki GUI → widoczny wynik** — Sprawdza połączenie przycisków, etykiet i podglądu; Qt offscreen nie zastępuje ręcznej oceny ani zewnętrznego odtwarzacza.

Baza code-review: HEAD zapisany przed rozpoczęciem tego ticketu. Specyfikacja przeglądu: ten ticket i wskazane decyzje; standardy: instrukcje repo/aplikacji, w tym limit plików.

## Test manualny programu

Dane i sposób przygotowania nietypowych wzorców dostarcza realizujący ticket. Próba korzysta z rzeczywistej aplikacji oraz funkcji dostępnych po tym etapie.

1. Otwórz serię z kalibracją i czasami, wyeksportuj zakres 5–10 z podziałką/numerem/czasem i obejrzyj w VLC.
2. Powtórz dla brakującej kalibracji i jednego nieznanego czasu; oczekuj px i jawnego braku czasu.
3. Sprawdź opisy na trzech tłach oraz fizyczne proporcje przy anizotropii.
4. Wybierz opisy dla przygotowanego zbyt małego obrazu; program wyjaśnia problem przed zapisem. Przy dostępnym aligned sprawdź również jego podziałkę.

## Współpraca z integracją

Źródłem kalibracji/czasu są per-klatkowe dane już wprowadzone w imporcie; nowe braki wspólnego modelu zgłaszać integracji, bez zgadywania parametrów.

## Doprecyzowanie użytkownika — 2026-10-27

Napisy i podziałka mają być bez czarnych prostokątnych pól. Białe znaki
z cienkim ciemnym obrysem zachowują czytelność na jasnym i ciemnym obrazie.
