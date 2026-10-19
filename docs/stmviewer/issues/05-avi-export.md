# Opcje filmu AVI

Type: grilling
Label: wayfinder:grilling
Status: open
Assignee: none
Parent: [STM Viewer — mapa pierwszej wersji](../map.md)
Blocked by: 02, 03

Zależy od: [Podgląd, gamma i odtwarzanie serii](02-preview-playback.md)
oraz [Rejestracja i życie wyniku aligned](03-registration.md).

## Question

Jakie wybory przy zapisie AVI ma otrzymać użytkownik i co dokładnie znajdzie się
w wyeksportowanym filmie?

Do ustalenia: pełne klatki lub wycinek podglądu; gamma i poziomy obrazu;
original/aligned; FPS i jego relacja do prędkości Play; wszystkie klatki lub
zakres; osie/podziałka/opisy; wygląd pustych obszarów; zgodność odtwarzania
i domyślny kodek. Wybrany wycinek musi mieć jednoznaczne znaczenie dla całej serii.

## Comments

### 2026-10-14 — odpowiedź użytkownika

Na propozycję filmu z gamma i zadanym FPS, z pełnych klatek niezależnie od
zoomu, użytkownik odpowiedział: „przy zapisie avi do wyboru dla użytkownika”.
Wymagany jest zatem wybór przy eksporcie; dokładny zestaw opcji pozostaje
otwarty. Nie przyjmujemy jeszcze automatycznie jednego sposobu kadrowania.

W repo nie znaleziono eksportera AVI. Lokalny netcat zawiera OpenCV
z deklarowaną obsługą FFmpeg; dostępność konkretnego kodeka wymaga sprawdzenia
zapisu i odczytu. Zobacz [rozpoznanie środowiska](../reconnaissance.md).

### 2026-10-19 — kontrakt podglądu

[Podgląd, gamma i odtwarzanie serii](02-preview-playback.md) ustala tempo Play,
wspólną gamma, osobne obszary podglądu original/aligned oraz szachownicę poza
pomiarem. Ich przeniesienie do filmu, w tym wybór FPS i kadrowania, pozostaje
decyzją tego ticketu; nie wynika automatycznie z ustawień podglądu.

### 2026-10-19 — geometria rejestracji

[Rejestracja i życie wyniku aligned](03-registration.md#answer) zachowuje
rozmiar wspólnego obszaru po usuwaniu klatek, również skrajnych. Nowa udana
próba może zmienić ten rozmiar. Geometria pola oryginalnej klatki i maska
ważności próbek są osobne; opcje kadrowania oraz wygląd braków w filmie
powinny korzystać z właściwej informacji. Ich eksport nadal rozstrzyga ten ticket.
