# REG-15 — ręczne sprawdzenie parametrów metod

Status: ready-for-review, 2026-11-03. Odbiór użytkownika jeszcze niewykonany.
[Ticket](issues/15-method-parameters.md), [wyniki prób](method-parameters-results.md),
[testy i przeglądy](reviews/REG-15.md).

## Uruchomienie i dane

W katalogu NEtCAT-viewer:

```bash
conda activate netcat
python -m stmviewer.main
```

Menu **Rejestracja → Parametry metod…** działa również bez otwartego filmu.
W tym etapie edytuje AKAZE oraz LightGlue + SuperPoint. Zmiana metody
w edytorze wybiera formularz; metodę obliczeń nadal wybierasz osobno
w głównym oknie, parze lub dopasowaniu wieloklatkowym.

Nie są potrzebne nowe instalacje. AKAZE działa na CPU bez wag;
LightGlue korzysta z [dotychczasowych lokalnych zasobów](lightglue-environment.md).
Sam edytor oraz odczyt zapisanego wyniku nie uruchamiają modeli.

Lokalne wzorce: data/registration-reg15/known-akaze.mpp oraz
data/registration-reg15/known-lightglue.mpp. Każdy ma trzy klatki.
Jeśli ich brakuje, wygeneruj je bez uruchamiania modeli:

```bash
PYTHONPATH=.:tests/stmviewer python tests/stmviewer/diagnostics/method_parameters_trial.py --fixtures-only
```

Na obu wzorcach oczekiwane przesunięcia w pikselach original względem
pierwszej klatki to (0, 0), (−7, +5), (+3, −4), z niewielkim błędem estymacji.
Druga para sąsiednia ma przesunięcie (+10, −9). Wzorzec AKAZE ma 288 × 192 px,
LightGlue 219 × 137 px; nie należy utożsamiać ich skali nagłówka z kalibracją STM.

## Formularz

1. Bez filmu otwórz menu parametrów. Zobacz AKAZE, następnie LightGlue.
   Rozwiń **Przygotowanie kontrastu** i, dla LightGlue,
   **Ustawienia zaawansowane**. Podpowiedzi pól wyjaśniają ich wpływ.
2. Wpisz próg AKAZE 0,0001, następnie próg LightGlue 0,05.
   Przełącz formularze: robocze wartości mają pozostać.
   **Anuluj** lub krzyżyk odrzucają obie zmiany.
3. Powtórz i kliknij **OK**. Ponowne otwarcie odtwarza obie konfiguracje.
   **Przywróć domyślne** dotyczy tylko widocznej metody; wymaga OK.
4. Wpisz mały próg, np. 1e-6; po ponownym otwarciu nie może być zerem.
   Sprawdź odrzucenie NaN, zera dla tolerancji oraz percentyli 99/1.
   Błąd nie może częściowo zatwierdzić drugiego formularza.
5. Przy rozpoczętym obliczeniu otwórz edytor: OK pozostaje niedostępne
   do końca zadania. Anulowanie edycji nadal jest możliwe.

Tolerancja zgodności dotyczy wektorów w jednej parze i ma jednostkę
px original. Nie jest progiem Hubera. Min–max zachowuje dotychczasowe
przygotowanie. Percentyle obcinają skrajne jasności; CLAHE zwiększa lokalny
kontrast. Oba mogą również wzmacniać wpływ zakłóceń.

## Para, film i graf

1. Otwórz known-akaze.mpp, wybierz AKAZE, ustaw próg 0,0001 i tolerancję 1,5.
   Oblicz parę 1→2 przez **Dopasuj automatycznie**, następnie rejestrację
   całego filmu i **Oblicz kandydata grafu**. Sprawdź znane XY oraz opisy
   parametrów. Powtórz na known-lightglue.mpp z LightGlue:
   maksymalnie 1024 punkty, próg SuperPoint 0,001, próg dopasowań 0,05.
2. Zostaw otwarte okna pary i grafu. Zmień parametry w menu głównym.
   Gotowy obraz, ręczne korekty i kandydat pozostają; opis informuje
   o różnicy między wynikiem i ustawieniami następnego obliczenia.
3. Ponownie oblicz parę i graf. Oba mają użyć nowej konfiguracji.
   Graf nie może wykorzystać starych pomiarów jako nowych po zmianie
   parametrów. Zapisany wcześniejszy graf nadal można zastosować.
4. Osobno przelicz wariant Hubera wcześniejszego grafu. Korzysta on
   z zapisanych krawędzi i ich konfiguracji, bez nowych dopasowań obrazów.
   Zastosuj wynik do filmu i wykonaj ręczną korektę jednej pary.
5. Powtórz rejestrację i anuluj albo sprowokuj odmowę bardzo wysokim
   progiem detektora. Wcześniejszy aligned ma pozostać dostępny.

## Zapis i odczyt

1. Przy wyniku obliczonym wcześniejszymi parametrami zmień oba formularze,
   a w głównym oknie wybierz Phase. Zapisz sesję i otwórz ją ponownie.
   Obie nieaktywne konfiguracje mają wrócić; stary wynik zachowuje swoje.
   Niezastosowany kandydat grafu nie staje się automatycznie aligned.
2. Otwórz również własną sesję sprzed REG-15. Nowe formularze otrzymują
   domyślne wartości, wcześniejsze wyniki zachowują swój zapis.
3. Zapisz aligned do MPP i odczytaj MPP wraz z dodatkiem metadanych.
   Sprawdź opis parametrów także na pierwszej klatce oraz dla wyniku
   grafu i filmu po ręcznej korekcie. Obecne ustawienia edytora nie mogą
   zastąpić opisu wcześniejszego wyniku.
4. Zapisz original i aligned po użyciu percentyli/CLAHE: wartości pomiarowe
   nie są zastępowane obrazem przygotowanym dla detektora. W aligned
   pozostaje dotychczasowa interpolacja i obsługa brakujących pikseli.
5. Wyeksportuj AVI i obejrzyj go w VLC. Nadal obowiązują wybrane ustawienia
   prezentacji i gamma; kontrast detektora nie staje się kontrastem filmu.

## Próby na STM

MOVIE_4: najpierw usuń dwie pierwsze klatki. W bieżącej numeracji sprawdź
1→2, 29→30 i 160→161; w oryginalnym MPP są to 3→4, 31→32 i 162→163.
MOVIE_8: sprawdź 1→2.

Zacznij od domyślnych ustawień, potem zmieniaj jedno ustawienie naraz:
próg AKAZE na 0,0001; próg LightGlue na 0,05; osobno percentyle 1/99.
Porównuj nakładkę i przełączanie klatek. Zanotuj XY, poparcie, czas i ocenę
wizualną, również odmowy oraz pogorszenia. Więcej dopasowań albo zniknięcie
odmowy nie wystarcza do uznania XY za poprawne.

[Wykonane próby automatyczne](method-parameters-results.md) nadal odrzucają
dwie trudne pary MOVIE_4. Ticket zapewnia kontrolę parametrów, nie gwarancję
skuteczności tych metod na całym filmie.

Do odbioru pozostaje przejście tej instrukcji w interaktywnym GUI,
ocena STM i AVI/VLC przez użytkownika. Qt offscreen jest osobnym testem
automatycznym.
