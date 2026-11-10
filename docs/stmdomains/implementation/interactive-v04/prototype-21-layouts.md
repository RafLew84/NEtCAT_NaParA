# Propozycje UI 21 — ręczne zaznaczanie i edycja domen

2026-11-05. Prototyp odpowiada na pytanie: **gdzie umieścić zaznaczanie
molekuł, wybór operacji i jej podgląd?** Zakres dotyczy
[SD-V4-21](21-manual-domain-membership.md). Implementacja produkcyjna
została później wykonana w `a61e1b2` / `47bafe0` po wyborze **A** przez
użytkownika 2026-11-05. Panel jest widoczny wyłącznie podczas edycji;
po jego schowaniu korekty pozostają. [Wykonanie i test ręczny](acceptance-21.md).
Poniżej zapis pierwotnego porównania propozycji.

## Trzy układy

| Wariant | Układ | Ocena autora |
| --- | --- | --- |
| A | Stały panel po prawej: narzędzia, operacja, cel, podgląd i historia | Rekomendowany: pełny proces obok obrazu, bez zasłaniania centrów. |
| B | Narzędzia przy lewej krawędzi, trzy etapy edycji pod obrazem | Szeroki obraz, ale w oknie 1024×768 zostaje mu niewiele wysokości. |
| C | Pasek narzędzi i zwijana karta na obrazie, przestawiana lewo/prawo | Więcej miejsca na obraz; karta może zasłaniać molekuły i wymagać przewijania. |

Wszystkie warianty używają tych samych danych i zachowują wybór, podgląd
oraz korekty przy przełączaniu. Rekomendacja A jest opinią autora po
obejrzeniu demo. Użytkownik następnie potwierdził A z panelem widocznym tylko podczas edycji.

## Uruchomienie

Z katalogu `/home/rlew/projekty/NEtCAT-domains`, w środowisku **netcat**:

```bash
python .scratch/stmdomains-manual-ui/serve.py
```

Adresy: [A](http://127.0.0.1:8879/?variant=A),
[B](http://127.0.0.1:8879/?variant=B),
[C](http://127.0.0.1:8879/?variant=C).
Dolny przełącznik lub strzałki klawiatury zmieniają wariant. Strzałki
w polach formularza zachowują swoje zwykłe działanie.
`--no-browser` uruchamia sam serwer, Ctrl+C go kończy.

Samowystarczalny `.scratch/stmdomains-manual-ui/prototype.html` można
otworzyć bez serwera. Lokalne artefakty nie są wersjonowane.
Źródło pierwotne: gałąź **`prototype/stmdomains-manual-domains-ui`**,
commit **`f2db201`**, baza **`65b22f0`**,
katalog `stmdomains/ui/prototype_manual/`. Na tej gałęzi polecenie to
`python stmdomains/ui/prototype_manual/serve.py`.
Wrócono na `domains/interactive-v04-ui`; tutaj pozostaje tylko dokumentacja.
Przy implementacji właściwe UI Qt należy napisać zgodnie z wybranym
wariantem, bez scalania kodu demo.

## Co wypróbować

1. Początkowo wybrano przykładowo 12 nieprzypisanych molekuł. Wyczyść
   wybór, włącz Lasso i obrysuj środki molekuł lewym przyciskiem myszy.
   Narzędzie Kliknięcia pozwala wskazywać pojedyncze centra. Zastąp,
   Dodaj i Odejmij mają osobne przyciski; Shift dodaje, Alt odejmuje.
2. Wybierz Nowa domena → Pokaż podgląd → Zastosuj. Sam podgląd nie
   zmienia członkostwa. Esc anuluje podgląd albo czyści zaznaczenie.
3. Wypróbuj Dodaj do domeny, Usuń z domeny oraz jawne Przenieś.
   Dodawanie punktów należących do innej domeny wskazuje konflikt;
   przeniesienie wymaga osobnego wyboru operacji.
4. Cofnij/Ponów odtwarza całą operację. Porównaj Automatyczny i Po
   korektach, przejdź suwakiem do innej klatki i wróć.
5. Zmień powiększenie i raw/aligned; wybór zachowuje ID. Spacja pozwala
   przesuwać obraz. Przełącz A/B/C z zachowaniem bieżącego zaznaczenia.
6. Sprawdź scenariusze Bez analizy i Zero domen oraz rozwijany Stan
   prototypu. W C zwiń kartę i przenieś ją na drugą stronę obrazu.

## Dane i ograniczenia

Rzeczywiste obrazy i centra MolTrack: TTMAPP258–260. Jeśli dostępny jest
`.scratch/stmdomains-ui-13/real.stmdomains`, przypisania początkowe 259
pochodzą z jego wyniku bazowego: **105/312 molekuł, 5 domen**. Dla 258/260
brak zapisanego wyniku jest jawny. Bez tego projektu demo odczytuje
`data/TTMAPP/detection_full.moltrack.json` i źródłowy MPP.

Korekty istnieją tylko w pamięci przeglądarki. Obszary są poglądowymi
komórkami najbliższych centrów w skończonym zasięgu, a nie docelową
regułą budowania geometrii z ticketu 21. Demo nie wyznacza skuteczności
detektora. Nie prowadzi analizy, treningu, zapisu ani eksportu korekt;
nie dodaje detekcji, własnych klas ani podziału/scalania domen.
Scenariusz zerowy jest demonstracyjny. Dane źródłowe są tylko odczytywane.

## Wykonane sprawdzenie

Natywne QtWebEngine/X11 w **netcat**, warianty A/B/C przy 1440×1000
i 1024×768; obejrzano zrzuty. Przejście GUI objęło rzeczywiste zdarzenia
myszy: kliknięcie, lasso (7 centrów) i przeciąganie suwaka klatek.
Sprawdzono podgląd/anulowanie, zastosowanie, Cofnij/Ponów, zachowanie
automatu, powrót do klatki, raw/aligned i zoom, zachowanie wyboru między
wariantami, tworzenie bez analizy, konflikt i jawne przeniesienie,
usunięcie pustej domeny i jej przywrócenie, scenariusz zerowy oraz
klawiaturę formularzy. Wszystkie sprawdzenia przeszły, brak błędów JS.

To sprawdzenie autora, nie odbiór ręczny użytkownika. Zgodnie z zakresem
prototypu nie dodawano testów demo i nie powtarzano regresji aplikacji.
Raport, zrzuty i lokalny skrypt przejścia GUI:
`.scratch/stmdomains-manual-ui/`. Maksymalny plik kodu: 663 linie.
Brak nowych zależności i potrzeb zmian we wspólnym kodzie.
