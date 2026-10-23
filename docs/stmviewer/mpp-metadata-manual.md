# Próba ręczna — MPP z metadanymi towarzyszącymi (ticket 11)

Z katalogu `NEtCAT-viewer`, w środowisku `netcat`:

```bash
python -m stmviewer.main
```

Nie są potrzebne nowe biblioteki ani wagi. Wzorce znajdują się w
`tests/stmviewer/fixtures/mpp-metadata/`. Zawierają po trzy klatki 4 × 3 px,
z celowo różnymi parametrami i wyraźnymi znacznikami obrazu. Ich historyczne
ścieżki są przykładowe — te pliki nie muszą istnieć. Generator, niezależny
od kodu importu i przyszłego eksportera:

```bash
python tests/stmviewer/make_mpp_metadata_fixtures.py
```

## Poprawna para

1. Otwórz **mixed.MPP**. Dodatek zostaje odnaleziony automatycznie; nie
   wybieraj JSON w dialogu. Panel podaje „Metadane towarzyszące: wczytano…”.
2. Przejdź przez klatki przyciskami, numerem i miniaturami. Jeśli panel
   parametrów nie mieści się w oknie, przewiń jego prawą część.

| Klatka w filmie | Historyczne źródło | Czas | Kanał / jednostka | Pole X × Y | Napięcie |
| --- | --- | --- | --- | --- | --- |
| 1 | `/pomiary/first.stp` | 10 s; opis `10000 ms` | Topo / nm | 8 × 9 nm | 0 V |
| 2 | `C:\pomiary\movie.MPP`, klatka źródłowa **8** | nieznany | Current / nA | 16 × 6 nm | −0,2 V |
| 3 | `archive/third.s94` | 35 s | nieznane | X nieznane, Y 12 nm | nieznane |

Wszystkie klatki mają offset X = 0 nm, Y = −1 nm, prąd 0 nA i kąt 37°.
Klatka 3 dodatkowo pokazuje „Nieznana kalibracja”. Brak danych pozostaje
brakiem pomimo znanych wartości wspólnego nagłówka. Proporcje podglądu
wynikają z indywidualnej kalibracji; „Proporcje pikselowe” pokazuje wspólne 4:3.

3. Pierwszy obraz ma białe L wzdłuż lewej i dolnej krawędzi; drugi gradient,
   trzeci L wzdłuż górnej i prawej krawędzi. Gamma i zoom działają jak wcześniej.
4. Usuń pierwszą klatkę: poprzednia druga staje się pierwszą w serii, lecz
   nadal pokazuje klatkę w otwartym MPP **2** i klatkę historycznego źródła **8**.
   Ponowne otwarcie pliku przywraca wszystkie trzy klatki.
5. Skopiuj **oba** pliki `mixed.MPP` i `mixed.MPP.stmviewer.json` do innego
   katalogu. Otwórz kopię: zmieni się ścieżka „Plik otwarty”, a pochodzenie
   i wszystkie parametry pozostaną identyczne. Można również zmienić nazwy
   obu plików na `nowy.MPP` i `nowy.MPP.stmviewer.json`.

## Brak lub odrzucony dodatek

Gotowe przykłady nie wymagają ręcznej edycji plików:

| Otwarty film | Oczekiwany komunikat |
| --- | --- |
| `without-addon.MPP` | Brak metadanych towarzyszących; dane z nagłówka MPP. |
| `wrong-content.MPP` | Dodatek pominięty: niezgodna zawartość, SHA-256. Jeden piksel filmu ma wartość 999, a dodatek nadal dotyczy wcześniejszych bajtów. |
| `wrong-shape.MPP` | Dodatek pominięty: niezgodne wymiary klatek. |
| `wrong-count.MPP` | Dodatek pominięty: niezgodna liczba klatek. |
| `unsupported.MPP` | Dodatek pominięty: nieobsługiwana wersja 999. |
| `broken.MPP` | Dodatek pominięty: nieprawidłowy JSON. |

W każdym przypadku film otwiera wszystkie trzy obrazy. Panel nie pokazuje
historycznych źródeł z odrzuconego dodatku. Używa nagłówka MPP: kanał Current,
jednostka nA, pole 8 × 9 nm, napięcie −0,2 V, prąd 0,4 nA; czasy
**1,5 s / nieznany / 4,25 s**, źródłowe numery MPP 1–3. Komunikat pozostaje
przy zmianie klatki. Nie ma blokującego błędu odczytu obrazu.

Na kopii można dodatkowo podmienić JSON na dodatek dowolnego innego filmu:
niezgodne metadane mają zostać pominięte. Po otwarciu `mixed.MPP` poprawna
historia wraca. Otwarcie STP/S94 albo usunięcie wszystkich klatek czyści
komunikat o dodatku. Lokalne `data/MOVIE_3.MPP` otwiera się jak dotychczas
z informacją o braku dodatku, jeśli nie ma go obok filmu.

## Zakres odbioru

[Kontrakt V1](mpp-metadata-format.md) opisuje walidację i pochodzenie.
Ten etap nie dodaje eksportu MPP ani odtwarzania historii aligned; będą
w ticketach 12–13. Rzeczywiste wczytane piksele nadal stanowią wejście do
rejestracji, z dotychczasowym odrzucaniem NaN przez backendy.

Testy Qt offscreen i sterowane skryptem okno są próbami automatycznymi.
Użytkownik potwierdził pozytywny wynik testów manualnych 2026-10-23.
Nie wskazał systemu; potwierdzenie nie zamyka odrębnych odbiorów platform,
w tym Windows.
Wyniki wykonanych sprawdzeń: [przekazanie](handoff.md).
