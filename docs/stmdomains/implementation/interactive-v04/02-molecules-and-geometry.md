# 02: Pokaż molekuły i poprawną geometrię obrazu

**ID:** SD-V4-02

**What to build:** Na obrazie pojawiają się zapisane oznaczenia molekuł. Użytkownik włącza warstwy, sprawdza molekułę i przełącza oryginał/wyrównany bez rozjeżdżania się obrazu i oznaczeń.

**Blocked by:** [01: Otwórz zapis i przeglądaj obrazy](01-open-images.md).

**Status:** done — implementacja, sprawdzenia techniczne i odbiór ręczny zakończone.

Baza implementacji i przeglądu: `152146a`, gałąź `domains/interactive-v04-ui`.
Środowisko aplikacji i sprawdzeń: `netcat`. Testy przez publiczne interfejsy
importu/modelu/geometrii oraz pełną ścieżkę import–widok, zgodnie z poniższymi
kryteriami i istniejącym kontraktem importu.
Implementacja: `df5c48b`. [Raport i instrukcja testu ręcznego](acceptance-02.md).
Użytkownik potwierdził pomyślny ręczny odbiór 02 (`3572b6d`) 2026-11-02:
„testy manualne ok”.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [x] Centra i bboxy są powiązane po ID z właściwą klatką; dostępne maski można pokazać z regulowanym kryciem. Błędna opcjonalna maska nie ukrywa poprawnego bboxa.
- [x] Oryginał i wyrównany widok odtwarzają zapisaną rejestrację. Padding jest odrębny od obrazu; brak lub niska pewność rejestracji zachowują uzgodnione znaczenie.
- [x] Zoom, pan, zmiana rozmiaru okna i przełączenie widoku zachowują zgodność oznaczeń, bez ponownego odbijania osi lub kumulowania interpolacji.
- [x] Kliknięcie oznaczenia pokazuje ID i dostępne metadane bez zmiany źródła. Brak oznaczeń różni się od potwierdzonej pustej listy.
- [x] Dekodowanie masek i przygotowanie wyrównania dotyczą potrzebnych klatek, z ograniczonym cache. Testy obejmują niekwadratowy obraz, ułamkową translację oraz braki.
- [x] Działającą funkcję sprawdzono automatycznie, w rzeczywistym GUI sterowanym Qt i przez ogląd zrzutów; użytkownik następnie potwierdził pomyślny odbiór ręczny.
- [x] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz klatki 1, 40, 41, 64, 68, 69 i 268; sprawdź powrót ramek po odcinku bez oznaczeń i zachowane ramki po utracie masek.
2. Powiększ molekułę i przełącz oryginał/wyrównany oraz nakładki; oznaczenie ma pozostawać na tej samej molekule.
3. Kliknij oznaczenie, zmień krycie masek i otwórz kontrolną serię bez rejestracji; komunikaty i dostępne warstwy muszą odpowiadać danym.

## Granice zadania

To podgląd istniejących oznaczeń, bez ponownej detekcji molekuł lub rejestracji.
