# 02: Pokaż molekuły i poprawną geometrię obrazu

**ID:** SD-V4-02

**What to build:** Na obrazie pojawiają się zapisane oznaczenia molekuł. Użytkownik włącza warstwy, sprawdza molekułę i przełącza oryginał/wyrównany bez rozjeżdżania się obrazu i oznaczeń.

**Blocked by:** [01: Otwórz zapis i przeglądaj obrazy](01-open-images.md).

**Status:** in_progress — realizacja na polecenie użytkownika `implement 02`.

Baza implementacji i przeglądu: `152146a`, gałąź `domains/interactive-v04-ui`.
Środowisko aplikacji i sprawdzeń: `netcat`. Testy przez publiczne interfejsy
importu/modelu/geometrii oraz pełną ścieżkę import–widok, zgodnie z poniższymi
kryteriami i istniejącym kontraktem importu.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] Centra i bboxy są powiązane po ID z właściwą klatką; dostępne maski można pokazać z regulowanym kryciem. Błędna opcjonalna maska nie ukrywa poprawnego bboxa.
- [ ] Oryginał i wyrównany widok odtwarzają zapisaną rejestrację. Padding jest odrębny od obrazu; brak lub niska pewność rejestracji zachowują uzgodnione znaczenie.
- [ ] Zoom, pan, zmiana rozmiaru okna i przełączenie widoku zachowują zgodność oznaczeń, bez ponownego odbijania osi lub kumulowania interpolacji.
- [ ] Kliknięcie oznaczenia pokazuje ID i dostępne metadane bez zmiany źródła. Brak oznaczeń różni się od potwierdzonej pustej listy.
- [ ] Dekodowanie masek i przygotowanie wyrównania dotyczą potrzebnych klatek, z ograniczonym cache. Testy obejmują niekwadratowy obraz, ułamkową translację oraz braki.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz klatki 1, 40, 41, 64, 68, 69 i 268; sprawdź powrót ramek po odcinku bez oznaczeń i zachowane ramki po utracie masek.
2. Powiększ molekułę i przełącz oryginał/wyrównany oraz nakładki; oznaczenie ma pozostawać na tej samej molekule.
3. Kliknij oznaczenie, zmień krycie masek i otwórz kontrolną serię bez rejestracji; komunikaty i dostępne warstwy muszą odpowiadać danym.

## Granice zadania

To podgląd istniejących oznaczeń, bez ponownej detekcji molekuł lub rejestracji.
