# Domain Analysis — migracja i troubleshooting (draft)

**Status:** procedury docelowe; nazwy komunikatów wymagają potwierdzenia w finalnym UI

**Formaty:** [DOMAIN_ANALYSIS_FORMATS_DRAFT.md](DOMAIN_ANALYSIS_FORMATS_DRAFT.md)

**Instrukcja:** [DOMAIN_ANALYSIS_USER_GUIDE_DRAFT.md](DOMAIN_ANALYSIS_USER_GUIDE_DRAFT.md)

## Zasada bezpieczeństwa

Nie naprawiaj problemu przez edycję pliku sesji, usunięcie historii korekt ani
nadpisanie źródeł. Zachowaj oryginalny plik i diagnostykę. Gdy system nie potrafi
jednoznacznie udowodnić zgodności, ma zatrzymać aktywację, Apply, publikację lub
Validation i pozostawić dane audytowalne.

## Migracja session v2 → v3

Docelowy loader:

1. waliduje outer session v2 przed migracją;
2. zachowuje source/working-series identity, draft, kompatybilny automatic
   `published_result`, classifier evidence i diagnostykę;
3. tworzy Orientation Class Catalog tylko z rozpoznanych wbudowanych A/B/C;
4. tworzy pusty correction set zakotwiczony w automatic fingerprint;
5. ustawia osobne M6 i Orientation review jako `draft/unreviewed`;
6. przelicza Effective Domain Projection bez wymyślania korekt;
7. zapisuje dopiero pełny, zwalidowany envelope v3.

Migracja nie może tworzyć D–Z, `accepted_automatic`, sign-off ani readiness na
podstawie obecności wyniku automatycznego. Oryginalna sesja v2 pozostaje dostępna
do odzyskania.

## Regresja `abc_orientation` po restore

### Objaw

Po Open draftu zapisanego bez aktywnej konfiguracji A/B/C użytkownik ponownie
włącza `abc_orientation`, a późniejszy Save kończy się błędem lub nie potrafi
odtworzyć konfiguracji.

### Przyczyna

Restore traktuje listę aktywnych konfiguracji z sesji jak katalog możliwości
runtime i usuwa z niego nieaktywny w drafcie adapter. Późniejsze włączenie ma ID,
ale nie ma już pełnej capability/configuration potrzebnej do zapisu.

### Docelowa naprawa

Runtime capability catalog jest niemutowalną własnością kompozycji aplikacji.
Open rozwiązuje zapisane active classifier IDs względem tego katalogu, ale go nie
zastępuje. Regresja musi przechodzić ścieżkę: Open bez A/B/C → enable
`abc_orientation` → Save → ponowny Open.

### Obejście przed wdrożeniem

Nie polegaj na edycji starego draftu jako jedynej kopii pracy. Zachowaj oryginał,
uruchom świeżą sesję z wymaganym classifierem aktywnym i odtwórz analizę. Nie
modyfikuj JSON ręcznie, ponieważ można utracić provenance lub fingerprinty.

## Tabela diagnostyczna

| Stan / komunikat | Znaczenie | Bezpieczne działanie |
| --- | --- | --- |
| `missing capability` / niedostępny backend | Sesja lub preset wskazuje adapter, którego nie ma w runtime | Zainstaluj/udostępnij właściwy adapter albo otwórz audit-only; nie zamieniaj backendu automatycznie |
| `stale correction` | Automatic fingerprint lub efektywny scope zmienił się od utworzenia korekty/review | Otwórz porównanie, wykonaj jawny rebase lub ponów review |
| `conflicted rebase` | Nie można jednoznacznie przenieść decyzji, np. brak `source_id`, changed geometry, split/merge | Rozstrzygnij wszystkie konflikty; nie stosuj częściowego Apply |
| `quarantined checkpoint` | Przeliczona projekcja nie zgadza się z zapisanym checkpointem/fingerprintiem | Zachowaj plik, wyeksportuj diagnostykę, pracuj na ponownie przeliczonej bazie dopiero po jawnej decyzji |
| `source drift` | Zawartość źródła różni się od przypiętego content fingerprintu | Utwórz nową source revision albo wskaż identyczny oryginał; nie podmieniaj starej rewizji |
| `leakage` | Ten sam measurement group/acquisition/lineage występuje w Calibration i Validation | Przenieś całą grupę do jednego splitu i opublikuj nową wersję datasetu |
| sign-off blocked | Scope jest niekompletny, stale albo nie ma obowiązkowego reason | Uzupełnij każdą decyzję targetu, reason i ponów kontrolę kompletności |
| dataset not ready | Brakuje kompletnego review, obu splitów, provenance albo występuje leakage/drift | Otwórz raport readiness i usuń każdą przyczynę; nie ustawiaj flagi ręcznie |
| Validation epoch already consumed | Istnieje receipt dla zamrożonej shortlisty/epoch | Nie otwieraj Validation ponownie; rozpocznij nową kampanię lub jawnie nowy epoch |
| preset incompatible | Nieznana schema, brak parametru lub niedostępny backend | Importuj w zgodnej wersji, migruj jako working copy i użyj `Save As`; nie uzupełniaj defaultami |
| prepared preview stale | Selection lub workspace revision zmieniły się po Preview | Anuluj preview, ponownie przygotuj batch i przeczytaj aktualne skutki |

## Stale correction i rebase

Nie próbuj przywracać zgodności przez zmianę fingerprintu w pliku. Zachowaj stary
automat jako aktywny, otwórz pending candidate i uruchom Preview rebase. Potwierdź
zgodne mapowania po `source_id`; changed geometry, brak źródła i split/merge muszą
pozostać konfliktami do ręcznej decyzji. Apply rebase jest atomowy.

Po udanym rebase sprawdź, które M6/Orientation review scopes zostały
unieważnione, i wykonaj ich review ponownie.

## Quarantine po Open

Quarantine oznacza, że dane zostały zachowane do audytu, ale korekty nie są
aktywnym wynikiem naukowym. Zbierz:

- ścieżkę i kopię oryginalnej sesji;
- outer/session/workspace schema versions;
- automatic, correction revision i checkpoint fingerprinty;
- listę naruszonych invariants i pierwszy pełny komunikat;
- wersję aplikacji, backend identity i algorithm version;
- source revision oraz content fingerprinty.

Nie publikuj exportu reference-ready. Audit export może być dozwolony tylko jeśli
manifest jawnie podaje `readiness=false` i stan quarantine.

## Source drift i leakage

Ścieżka pliku nie jest identity. Rename identycznych bytes jest relokacją, ale
konwersja lub zmiana bytes tworzy nową source revision. Jeżeli wykryto drift,
porównaj content i metadata fingerprints oraz lineage przed zaakceptowaniem nowej
rewizji.

Splituj całe measurement groups. Losowe rozdzielenie molekuł lub sąsiednich
klatek tego samego filmu jest leakage nawet wtedy, gdy pliki mają inne nazwy.
M6 i Orientation mogą mieć inne splity, lecz każdy target musi być wewnętrznie
izolowany.

## Brak capability

Komunikat ma podać brakujące backend/classifier ID i zapisaną schema/algorithm
version. Otwieranie audit-only nie oznacza, że wynik jest odtwarzalny. Nie wybieraj
innego dostępnego backendu jako cichego fallbacku; nowy backend wymaga jawnego
rerun i tworzy inny automatic fingerprint.

## Sign-off i gotowość datasetu

Sprawdź osobno M6 i Orientation. Każdy `source_id` zamrożonego scope musi mieć
jedną disposition. `Unresolvable`, abstention i rejection wymagają reason.
Zmiana efektywnego wyniku po sign-off unieważnia odpowiedni scope.

Readiness wymaga również niepustych Calibration i Validation, target-specific
sign-offs, source provenance, zgodnych fingerprintów i braku aktywnego conflict,
stale, quarantine, leakage oraz drift.

## Zużyty Validation epoch

Validation receipt wiąże dataset version/epoch, objective, geometrię i zamrożoną
shortlistę po jednym kandydacie każdego backendu. Po jego utworzeniu nie wolno
zmieniać tych danych ani uruchamiać Validation ponownie. Dalszy eksperyment używa
Calibration albo rozpoczyna jawnie nową kampanię; zmiana Validation wymaga nowego
epoch i nie udaje kontynuacji starego rankingu.

## Checklist zgłoszenia problemu

Przekaż maintainerowi:

- dokładne kroki od świeżego uruchomienia;
- wersję aplikacji i systemu;
- nazwy stage/action oraz pełny komunikat;
- schema versions i package kind;
- backend/classifier identity, preset/configuration fingerprint;
- measurement group, source revision i Validation epoch bez danych wrażliwych;
- informację, czy stan był draft, reviewed, stale, conflicted lub quarantined;
- minimalny zanonimizowany plik albo deterministyczny fixture, jeżeli można go
  bezpiecznie udostępnić.

Nie dołączaj screenshotów lub źródłowych obrazów zawierających dane poza zakresem
zgłoszenia.
