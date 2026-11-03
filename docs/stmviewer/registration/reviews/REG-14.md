# REG-14: karta sprawdzeń i przeglądu

Data: 2026-11-02. Baza cc8dfcd, implementacja a9abf0f,
poprawka po przeglądzie 9dd0337. Status **ready-for-review**;
odbiór manualny użytkownika niewykonany.
[Instrukcja GUI](../akaze-manual.md), [wyniki](../akaze-results.md),
[środowisko](../akaze-environment.md).

## TDD i sprawdzenia automatyczne

Uzgodnione granice: obrazy/konfiguracja → korespondencje/XY/odmowa;
dostępność/zadanie → CPU/anulowanie/błąd;
para/seria/graf/sesja → zastosowanie/korekta/eksport.

Cykle RED/GREEN obejmowały brak adaptera, natywne niekwadratowe XY,
stały obraz 1 × 1, podłączenie pary/łańcucha/grafu, sesję ze snapshotem,
wersjonowanie dodatku MPP i wybór AKAZE dla grafu z głównego okna.
Po przeglądzie dwa dodatkowe czerwone testy jednego wiersza/kolumny
wykazały rzeczywistą asercję OpenCV; wprowadzono lokalną odmowę.

- **Cały STM Viewer po poprawce: 840 passed, 36 skipped, 77,14 s.**
  Log: /tmp/stmviewer-reg14-viewer-complete.log. W tym 26 nowych testów
  AKAZE, rzeczywisty OpenCV i automatyczne GUI Qt offscreen.
- **Pełne repo przed poprawką skrajnego wymiaru: 2624 passed, 14 failed,
  50 skipped, 294,26 s.** Log: /tmp/stmviewer-reg14-full.log.
  Wszystkie 14 identyfikatorów awarii jest identycznych z REG-12:
  11 MolTrack/SAM2, dwa okna/sesje NanoTrack i jedna ścieżka checkpointu
  SAM2 w NanoTrack. Potwierdzenie: data/registration-reg14/baseline-test-failures.json.
  Nie zmieniano tych modułów. Pełne repo nie jest opisane jako zaliczone.
  Po poprawce uruchomiono cały Viewer, bez powtarzania niepowiązanych testów.
- Pierwsza próba końcowego zestawu Viewera została zakończona sygnałem
  SIGTERM, bez raportu końcowego (/tmp/stmviewer-reg14-viewer-final.log).
  Nie ustalono przyczyny sygnału i nie zaliczono tej próby. Ponowne pełne
  wykonanie zakończyło się wynikiem 840/36 powyżej.
- **Mypy: brak błędów w 100 plikach źródłowych**:
  python -m mypy --config-file stmviewer/mypy.ini.
- Jawna izolacja CPU: pary/łańcuch/graf bez Torch, Kornia, torchvision,
  LightGlue i sieci; odczyt sesji bez cv2/modeli; kontrolowana niedostępność
  detektora, błąd OpenCV i anulowanie bez utraty wcześniejszego aligned.
- Realne MLDB/Hamming, wzajemne dopasowanie, mała liczba cech, zachowanie
  diagnostyki, v9 sesji/grafu i v12 MPP, odrzucenie błędnej konfiguracji,
  zachowanie nieaktywnych ustawień i wcześniej zastosowanego wyniku.
- MPP: ponowny odczyt po łańcuchu/grafie i ręcznej korekcie, zarówno NaN,
  jak i skończone wypełnienie; zgodne dane, przesunięcia i pochodzenie.
- Pilotaż: 18 nowych prób STM + 54 historyczne o potwierdzonych wejściach;
  dziewięć wspólnych wzorców, oba pełne filmy, graf LS/Huber oraz kompletny
  cykl na known.mpp. Szczegóły i ograniczenia w raporcie wyników.
- AVI z poprawionych sesji LS/Hubera: MJPG/FFV1, osiem klatek, 262 × 262,
  5 kl./s; dekodowanie w save_avi, dla FFV1 zgodność rasterów.

Sprawdzono lokalne odnośniki, git diff --check i długości zmienionych plików.
Największy zmieniony plik kodu ma 987 linii; limit 1500 zachowany.
Dane i sesje pozostają lokalne; żaden model ani pakiet nie został pobrany.

## Standards

Niezależny agent sprawdził git diff cc8dfcd...a9abf0f względem AGENTS,
instrukcji Viewera i zasad implementacji; uwzględnił heurystyki Fowlera.

Brak stwierdzonych naruszeń udokumentowanych standardów. Zmiany pozostają
w zakresie Viewera; adapter ma osobny moduł, a testy obejmują publiczne
granice oraz rzeczywisty OpenCV.

**Jedna uwaga nieblokująca — możliwe Duplicated Code:** konfiguracja AKAZE
ma ręcznie synchronizowane reprezentacje: DETECTOR_CONFIG oraz parametry
konstruktora, a stała tożsamość adaptera jest powtórzona w walidatorze
metadanych. Obecne wartości są zgodne. Przy zmianie detektora łatwo jednak
zapisać konfigurację inną od wykonanej; warto rozważyć jedno niezmienne
źródło parametrów i tożsamości. To ocena utrzymywalności, nie naruszenie
reguły ani powód do szerokiego refaktoru.

Decyzja: pozostawiono jako nieblokującą uwagę do utrzymywania wersjonowanego
formatu. Parametry REG-14 są stałe, zachowane w provenance i sprawdzane
testami; ticket nie dodaje edytora ich ustawień.

## Spec

Niezależny agent sprawdził tę samą bazę wobec REG-14.

**P2, przypadek skrajnego wejścia:** niestałe obrazy z jednym wierszem albo
kolumną przechodziły przygotowanie, po czym detektor zwracał asercję OpenCV.
Graf przerywał całe zadanie zamiast zapisać lokalną odmowę.
Wymaganie: „Brak punktów/deskryptorów […] dają kontrolowaną odmowę”.

Naprawiono w 9dd0337: przed detektorem wymagane są oba wymiary co najmniej
dwa; brak użytecznych cech zachowuje przygotowanie/provenance i trafia
do istniejącej odmowy konsensusu. Rzeczywiste błędy OpenCV nadal przerywają
zadanie. Agent ponownie sprawdził poprawkę i wykonał dwa testy regresji,
obejmujące następnie ponowne użycie backendu na poprawnym obrazie.
**Uwaga zamknięta; pozostałe uwagi Spec: 0.**

Nie stwierdzono innego odstępstwa ani rozszerzenia zakresu. Słaby wynik
metody na STM jest udokumentowanym wynikiem pilotażu, dopuszczonym w specyfikacji.

Standards: 0 naruszeń, 1 nieblokująca uwaga o duplikacji.
Spec: 1 naprawiony P2, 0 pozostałych uwag.

## Odbiór ręczny i ograniczenia

Qt offscreen i korekty przez API są testami automatycznymi.
Użytkownik nie potwierdził jeszcze GUI ani jakości AKAZE.
Nie wykonano odbioru Windows 11, VLC na obu systemach ani stanowiska
referencyjnego. AKAZE nie wymaga GPU. Progi/algorytm innych metod są bez zmian.
