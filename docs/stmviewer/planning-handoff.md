# Przekazanie — tickety implementacyjne STM Viewer

Data: 2026-10-19
Gałąź: `viewer/start`
Baza bieżącej zmiany: `f394eba`
Commit zamykający: identyfikator w końcowej wiadomości sesji.

## Wynik

Użytkownik zatwierdził [21 ticketów implementacyjnych](implementation/README.md),
ich zależności i publiczne granice testowania TDD. Podział dostosowano do
pracy skillem `implement`: realizacja funkcji, testy, kontrola typów,
code-review i commit mieszczą się w jednym etapie. Każdy ticket zawiera
konkretny ręczny scenariusz w działającym programie i oczekiwane wyniki.

Pierwszy dostępny etap to [Pierwszy obraz STP w działającym oknie](implementation/issues/01-single-stp.md).
Pozostałe mają jawne blokady; status `ready-for-agent` nie pozwala pomijać
nieukończonych zależności. Zapisano też przebieg `in-progress` →
`ready-for-review` → `done` i rozróżnienie prób wykonanych/niewykonanych.

Oddzielono otwarcie obrazu od serii, podgląd od Play/Pause, odczyt dodatku
MPP od zapisu, podstawowy AVI od wyborów prezentacji, duży podgląd od
pełnych eksportów oraz odbiór Ubuntu od Windows. Gotowy wynik Phase nadal
jest jednym kompletnym etapem z GUI, postępem, anulowaniem i geometrią.
Nie utworzono osobnych ticketów niepodłączonego modelu, renderera lub workera.

[Instrukcja aplikacji](../../stmviewer/AGENTS.md) określa cel do **1000 linii**
i twardy limit **1500 linii fizycznych** pliku kodu, z komentarzami i pustymi
wierszami. Podział ma wynikać z odpowiedzialności. Każdy etap wymaga także
instrukcji uruchomienia i ręcznej próby; wynik Qt offscreen jest osobnym
sprawdzeniem automatycznym.

Uzgodnione granice testowania i domyślna baza przeglądu (HEAD przed rozpoczęciem
ticketu) są zapisane w trackerze. Nie trzeba ponawiać tych samych pytań przy
każdym tickecie; nowa, nieuzgodniona granica testów wymaga uzgodnienia.
Pierwszy etap ustala komendę typecheckingu; kolejne uruchamiają ją regularnie,
pojedyncze testy w toku pracy, a pełny zestaw na końcu.

Zamknięta [mapa decyzji](map.md) i jej sześć ticketów pozostają niezmienione.
Specyfikacja nadal obowiązuje, a kod aplikacji pozostaje szkieletem. Ten
commit publikuje plan wykonania i reguły pracy; nie wdraża funkcji programu.

## Weryfikacja i granice tej zmiany

- Odczytano instrukcje `to-tickets`, `implement` oraz wymagania jego przebiegu
  TDD/code-review; przy zmianie AGENTS zastosowano `writing-for-agents`.
- Sprawdzono istniejący szkielet, publiczne wejścia i rozmiary współdzielonych
  czytników/runnera/materializatora. Przygotowane funkcje wykorzystują ten kod,
  a wymagane wspólne zmiany pozostają przypisane sesji integracyjnej.
- Sprawdzono 294 lokalne odnośniki/kotwice, 21 osobnych ticketów, statusy,
  topologiczne uporządkowanie bez cykli i zbędnych blokad przechodnich oraz
  kompletność scenariuszy ręcznych i publicznych granic testów. Tylko pierwszy
  ticket jest odblokowany, a oba odbiory platform obejmują wszystkie wcześniejsze etapy.
- Mapa i sześć decyzji są identyczne bajtowo względem `f394eba`. Zmiany
  obejmują wyłącznie instrukcję aplikacji i dokumentację Viewera. Pięć obecnych
  plików Python aplikacji/testów mieści się w limicie (największy: 29 linii).
  `git diff --check` przeszedł poprawnie.

Nie uruchamiano testów aplikacji, modeli, GUI, Windows ani VLC. Nie wdrożono
żadnego ticketu i nie zaliczono jego przyszłych prób. Wcześniejsze dowody
z rozpoznania nadal są w [raporcie danych](acceptance-reconnaissance.md),
[raporcie kodu](reconnaissance.md) oraz raportach [MPP](wsxm-mpp-compatibility.md)
i [AVI](avi-export-reconnaissance.md).

## Podział pracy z sesją integracyjną

Własna implementacja należy do `stmviewer/` i `tests/stmviewer/`. Zmiany
`napara/`, `nanotrack/`, `moltrack/`, `stmbrowser/` oraz konfiguracji głównej
prowadzi sesja integracyjna. Poniższe punkty są wymaganiami wobec wspólnego
kodu lub granicy adaptera; nie oznaczają zgody na zmianę innych worktree
w trakcie ich pracy. Nie należy kopiować niezgodnego zachowania starych
aplikacji do Viewera tylko dlatego, że istnieje już helper.

| Obszar | Potrzeba do uzgodnienia lub wykonania przez integrację |
| --- | --- |
| Czytniki STP/S94 i jednostki | Rozpoznać rzeczywiste pola kanału/offsetów STP; zachować surowe liczby i jednostki sygnału niezależnie od skali X/Y. Zweryfikować kalibrację i kolejność bajtów S94, w tym nieznane wzmocnienie. Nie normalizować double według samego Z Amplitude. |
| MPP: orientacja i czasy | Ustalić jawną granicę obrotu między czytnikiem i loaderem, aby ścieżki STP/S94/MPP zachowały orientację po zapisie. Poprawić interpretację jednostek czasu i częściowych braków; nie tworzyć czasu z FPS. Sprawdzić dotychczasowych odbiorców. |
| MPP: duże nagłówki i metadane | Usunąć/dostosować ukryty limit 1000 linii, aby obsłużyć przyjęte duże serie. Zachować parametry per klatka i nieznane wartości; ustalić adapter wersjonowanego dodatku powiązanego z treścią filmu. Nie przypisywać metadanych pierwszej klatki całej serii. |
| Rejestracja i zadania w tle | Udostępnić kontrolowane anulowanie na bezpiecznych granicach, postęp i kompletne wyniki bez wiązania obliczeń z UI. Stary wynik musi przetrwać błąd nowego. Nie kopiować synchronicznego dialogu NanoTrack, który kasuje wynik po błędzie. |
| Deep Matcher | Zapewnić sprawdzenie lokalnych zależności/wag i ich wczytanie bez pobierania. Obecne LoFTR pretrained może pobrać brakujący plik. Jawnie sprawdzać dostępność urządzenia i raportować błędy; sam test FakeMatcher nie wystarcza. |
| Expanded aligned | Zachować pełny obszar, NaN, translacje i historyczne odniesienie oraz osobny prostokąt źródła i maskę ważności. Obecne wspólne metadane materializatora wymagają adaptera dla różnych kalibracji. Nie używać preview, który obcina obraz i powiela brzeg. |
| Zależności i platformy | Minimalny plik wymagań zawiera tylko PyQt6. Potrzebny sprawdzony zestaw NumPy/SciPy/scikit-image/pyqtgraph/OpenCV, a opcjonalnie Torch/Kornia/CUDA i lokalne wagi, z instrukcją obu systemów. Uruchomić rzeczywiste próby kodeków na obu platformach. |
| Testy odbiorców | Zmiana wspólnego modułu wymaga testów jego odbiorców. Istniejące loadery mockują czytniki, test MPP wymaga nieobecnego tutaj data/MOVIE_3.MPP, a testy MolTrack zakładają kasowanie rejestracji po usunięciu. Zachować ich odrębne kontrakty; dodać rzeczywiste próby wejścia/wyjścia. |

Źródła ograniczeń i odnośniki do kodu: [rozpoznanie](reconnaissance.md).
Wybranie miejsca adaptera i szczegółów API jest pracą implementacyjną;
nie trzeba otwierać kolejnej mapy, aby rozstrzygać rutynowe szczegóły kodu.
Jeżeli wspólna zmiana nie jest jeszcze dostępna, kontynuować niezależne
prace Viewera i zgłosić konkretną zależność w kolejnym przekazaniu.

## Własne moduły i odbiór do wykonania

- Model serii z trwałym powiązaniem klatek, pochodzenia, czasów i kalibracji;
  import wymienia stan dopiero po sukcesie. Usuwanie zachowuje gotowe aligned,
  jego obszar i historyczne odniesienie; brak odwracania kolejności.
- Podgląd wybranego układu B, Play/Pause, filmstrip, gamma/zoom i prezentacja
  maski. Oddzielić zadane tempo od rzeczywiście uzyskanego; podczas Play
  nie pomijać klatek. Nie generować wszystkich dużych rastrów filmu w pamięci
  wyłącznie na potrzeby miniatur lub odtwarzania.
- Stan zadań importu/rejestracji/eksportu, postęp i anulowanie; spójny zestaw
  klatek/parametrów dla eksportu oraz publikacja po sukcesie. Kontrolowane
  błędy muszą obejmować też etap budowy aligned i zapis dodatku MPP.
- MPP float64/NaN i powiązany dodatek: wartości niezależne od prezentacji,
  kompletna geometria i metadane, walidacja zgodności pary po odczycie.
  Dwa pliki nie są jedną atomową operacją; błędnego dodatku nie stosować.
- Renderer AVI pełnych klatek, kontrast tylko z ważnych próbek, gamma,
  proporcje, maska, tła i opisy; dopełniać nieparzyste wymiary zamiast obcinać.
  FFV1 zachowuje raster uint8, a nie wartości pomiarowe. Nie przechwytywać okna.
- Przeprowadzić pełny [odbiór](issues/06-acceptance.md#answer), z manifestem
  danych i osobnymi wynikami Ubuntu/Windows. Zanotować faktyczne zużycie
  zasobów oraz dostępność metod, a niewykonane próby oznaczyć jawnie.


Dalsza praca prowadzi przez zatwierdzone tickety implementacyjne. Odbiór całej
pierwszej wersji wymaga obu zaliczonych ticketów platformowych na zgodnym
zestawie zintegrowanych zmian.
