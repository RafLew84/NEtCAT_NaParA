# SD-V4-25 — eksport ręcznych klas i domen

2026-11-09. Gałąź `domains/interactive-v04-ui`, baza `4555908`.
Implementacja `03dfece`, poprawki przeglądu `bf243a0`.
**Odbiór ręczny użytkownika 25 potwierdzony 2026-11-09 dla wersji `bacd68b` („testy manualne ok”).**

## Obsługa

Wybierz **Plik → Eksportuj PNG/CSV…**. Domyślne **Po korektach** obejmuje
zatwierdzony stan wskazanego wariantu. Można wybrać **Bazowy automat — przed
korektami**, dostępny wcześniejszy przebieg lub same oznaczenia wejściowe.
Gdy istnieje kilka rodzin korekt, lista pozwala wskazać ich listę klas.
W pracy wyłącznie ręcznej okno informuje o braku automatu.

Wskaż bieżącą klatkę lub zakres, formaty, pełny obraz albo wycinek i nowy
podkatalog eksportu. PNG zachowuje aktualny tryb **Klasy/Domeny**, widok
oryginalny/wyrównany, gammę i warstwy. Przy wyborze zakresu współrzędne
wycinka są wspólne; liczniki dotyczą całych klatek.

Eksport działa przed zapisaniem projektu. Podgląd korekty trzeba wcześniej
zatwierdzić albo anulować. Eksport utrwala bieżące przypisania i wersję
wspólnej listy klas, również na klatkach jeszcze nieodwiedzonych. Nie wykonuje
analizy. Cofnięta operacja nie trafia do eksportu; Ponów ją przywraca.
Pliki nie zmieniają historii ani stanu niezapisanych korekt. Do wznowienia
pracy nadal służy projekt `.stmdomains`.

## Co zawierają pliki

- `frames.csv`: status każdej wybranej klatki, liczby członków domen i klas,
  osobne liczniki przypisań ręcznych i automatycznych, przybliżona powierzchnia.
- `molecules.csv`: ID klatki i molekuły, przypisania bazowe `base_*`, końcowe
  `class_id` / `domain_local_id`, nazwa/kolor klasy, pochodzenie, rodzaj zmiany
  i zastosowane operacje. Klasa bez domeny ma klasę i domenę 0.
- `domains.csv` i `classes.csv`: członkostwo i liczniki wybranego wariantu,
  aktualne nazwy klas oraz domen, np. A, A1, A2. Puste klasy pozostają widoczne.
- `frame-*.png`: obraz, legenda i podpis wariantu, jawna informacja o korektach
  lub braku analizy. Automat otrzymuje własne pierwotne nazwy i kolory.
- `frame-*.json`: faktyczne parametry, źródłowy automat, lista klas ręcznych,
  zastosowane operacje, zakresy scalenia/podziału klas i ustawienia obrazu.
- `manifest.json` i `README.md`: wersja 2 formatu, zakres, sumy kontrolne
  plików oraz opis kolumn i ograniczeń.

`assignment_origin` dotyczy zastosowanej zmiany klasy lub domeny. Same
metadane klasy nie zmieniają pochodzenia członkostwa. Liczniki `manual_*`
i `automatic_*` rozdzielają tak określone pochodzenie, bez podwójnego
liczenia molekuł. `class_origin` mówi, czy sama etykieta pochodzi z modelu
czy została utworzona ręcznie. `confidence` nadal opisuje wejściowe oznaczenie
MolTrack; ręczne wskazania nie otrzymują ufności modelu.

Brak automatu pozostaje brakiem, a nie zerem detekcji. Domena z niewystarczającą
geometrią ma niedostępną powierzchnię i kontakt z brzegiem. Suma znanych
fragmentów przy innych brakach ma status `partial`. Obszary są przybliżone;
udział przypisań nie jest miarą trafności modelu. Eksport nie stanowi
automatycznie referencji naukowej ani zbioru treningowego.

## Gotowe przykłady i test ręczny

Uruchom z katalogu tego worktree:

```bash
conda activate netcat
python -m stmdomains.main
```

Gotowe pliki lokalne, bez potrzeby przygotowywania danych:

- `.scratch/stmdomains-ui-25/gui-final/control-corrected.stmdomains`:
  klatka 1 ma 7 członków domen i 9 członków klas, w tym 2 ręczne klasy bez
  domeny. Klasy A/B mają 6/3 członków; automat ma 4/3. Klatka 2 korzysta
  z tego samego katalogu; klatka 3 z innego.
- `.scratch/stmdomains-ui-25/gui-final/manual-only.stmdomains`:
  jedna molekuła z ręczną klasą i domeną, bez modelu i automatu. Domena
  nie ma wystarczającego wsparcia do wyznaczenia obszaru.
- `data/TTMAPP/detection_full.moltrack.json`: rzeczywista seria wejściowa;
  do próby wybierz klatkę 259, oblicz wynik i wykonaj własne korekty.

1. Otwórz kontrolę, ustaw **Klasy**, wyeksportuj **Po korektach** do nowego
   katalogu. Otwórz PNG i CSV poza programem: A ma 6, B ma 3, liczba domen
   wynosi 2. Te same wartości są w legendzie programu.
2. Wyeksportuj **Bazowy automat** osobno: A ma 4, B ma 3; ręcznych przypisań
   jest 0. Wróć do ręcznej edycji, użyj Cofnij i ponów eksport. Następnie
   Ponów i sprawdź powrót wcześniejszych wartości.
3. Zmień nazwę i kolor A. Wyeksportuj zakres 1–3 bez wcześniejszego otwierania
   klatki 2: nowa nazwa/kolor obowiązują na 1–2, trzecia klatka zachowuje
   własny katalog. Wyeksportowany automat zachowuje pierwotną nazwę A.
4. W **Klasy ręczne → Scal klasy…** wybierz A i B, zakres 1–2 i nową klasę.
   Po zastosowaniu wyeksportuj zakres. Końcowe liczebności wynoszą 9/7,
   a domeny pozostają osobne: po 2 na klatkę. Podziel klasę, wskazując
   jedną molekułę z domeny w każdej klatce: po 3 domeny, nowa klasa ma
   po 1 członku. Cofnij/Ponów zmienia eksport obu klatek razem.
5. Otwórz przykład bez modelu i eksportuj zakres 1–2. Pierwsza klatka ma
   stan `manual_only`, pusty katalog i dane bazowe; powierzchnia pozostaje
   pusta. Druga jest nieanalizowana, z pustymi licznikami. Automat nie jest
   dostępny na liście.
6. Na TTMAPP 259 sprawdź Klasy i Domeny, oryginalny/wyrównany obraz, zmianę
   gammy i wycinek. Porównaj członków, etykiety, obrysy, kolory i liczniki
   z aplikacją. Eksport zakresu 259–260 zachowuje brak analizy 260, jeżeli
   jej nie obliczono.
7. Rozpocznij eksport większego zakresu i anuluj. Spróbuj katalogu docelowego,
   którego rodzic nie istnieje. Korekty, Cofnij/Ponów i informacja o niezapisanej
   pracy muszą pozostać bez zmian; nie powstaje częściowy katalog wynikowy.

## Wykonane sprawdzenia

- Netcat, 32 powiązane testy PASS; 7 nowych testów eksportu korekt obejmuje
  klasy bez domeny, wszystkie podstawowe operacje domen, klasy wieloklatkowe,
  Cofnij/Ponów, brak modelu, anulowanie/błąd, zamrożenie stanu i wspólne nazwy.
- Mypy: **127 modułów PASS**, zakres `core`, `analysis`, `ui`, `io`.
- Końcowa pełna regresja: **659 testów PASS / 295,49 s** dla `bf243a0`.
- Natywne Qt/X11 w netcat po `bf243a0`: kontrole i TTMAPP 259 PASS. CSV
  porównano z każdym członkiem wyniku, legendę PNG z legendą aplikacji,
  kolory pełnych masek również przez piksele PNG. Otwarto PNG w osobnym
  oknie. Sprawdzono wspólną nazwę na nieodwiedzonej klatce, brak analizy,
  eksport przed zapisem, Cofnij/Ponów, widok wyrównany i gammę 1,4.
- TTMAPP 259: automat K5 ma 6 domen / 120 członków; wydzielenie jednego
  członka do nowej klasy daje 7 domen / 120 członków. To kontrola eksportu,
  nie pomiar poprawy detekcji. Klatka 260 pozostaje nieanalizowana.
- [Przegląd Standards i Spec](review-25.md): 0 otwartych uwag po poprawkach.
- 16 zmienionych plików Python; maksimum **911 linii** (`session_controller.py`).
  Wszystkie poniżej 1000; bez nowych zależności i zmian współdzielonych.

Sprawdzono sumy kontrolne wszystkich **89 wyeksportowanych plików** końcowej próby
GUI oraz 525 lokalnych odnośników i zgodność zależności 27 ticketów.

Artefakty lokalne: `.scratch/stmdomains-ui-25/`, końcowe GUI i eksporty
w `gui-final/`, raport `gui-final/gui-report.json`, regresja `regression.xml`.
Sprawdzenia agenta nie zastępują odbioru ręcznego użytkownika.
