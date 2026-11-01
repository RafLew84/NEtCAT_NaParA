# Próba 26 — adaptacja gotowego DINOv2

Osobny prototyp badawczy, bez zmian aplikacji i poprzednich eksperymentów.
Zakres oraz kryteria: [protokół](../../../../docs/stmdomains/pretrained-self-supervised-protocol.md).
Wymaga istniejących danych20, zamrożonego FFT21 i lokalnych oficjalnych
wag/źródeł DINOv2 z18. Środowisko `netcat` zawiera wszystkie zależności;
nie potrzeba timm, transformers, peft ani nowych instalacji.

Sześć niezależnych prób po1000 kroków adaptuje ostatni blok i końcową
normalizację, z małą głowicą samodestylacji. Główny odczyt to średnia384
końcowych tokenów nauczyciela EMA. Wyjścia głowicy nie są klasami domen.
Trening nie czyta referencji. Wybrany jest ostatni krok, bez wyboru minimum
straty względem zmieniającego się nauczyciela. Nieudane próby pozostają
zapisane; nie zastępujemy ich nowymi ziarnami.

Wykonanie w katalogu repozytorium (`python` z istniejącego środowiska):

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
trial26=.scratch/pretrained-ssl-26
module26=stmdomains.experiments.training.pretrained_ssl

python -m "$module26.process" --output "$trial26" --stage preflight-cuda -- python -m "$module26.fit" preflight --data .scratch/training-20/data --output "$trial26/preflight-cuda.json" --device cuda --resume-check
python -m "$module26.process" --output "$trial26" --stage technical --ledger-stage audit-technical -- python -m "$module26.audit_predictions" technical --output "$trial26"
python -m "$module26.process" --output "$trial26" --stage controls -- python -m "$module26.prepare" controls --output "$trial26"
# Po ukończeniu i zapisaniu źródeł, przed jakimkolwiek jakościowym fitem:
python -m "$module26.process" --output "$trial26" --stage plan -- python -m "$module26.prepare" plan --output "$trial26"
python -m "$module26.process" --output "$trial26" --stage fit-suite --fit-suite -- python -m "$module26.run_fits" --output "$trial26" --device cuda
python -m "$module26.process" --output "$trial26" --stage training-audit -- python -m "$module26.audit_training" --output "$trial26"
python -m "$module26.process" --output "$trial26" --stage cache -- python -m "$module26.prepare" cache --output "$trial26"
python -m "$module26.process" --output "$trial26" --stage encode -- python -m "$module26.predict" encode --output "$trial26" --device cuda
python -m "$module26.process" --output "$trial26" --stage partition -- python -m "$module26.predict" partition --output "$trial26"
python -m "$module26.process" --output "$trial26" --stage export-audit --ledger-stage audit-exports -- python -m "$module26.audit_predictions" exports --output "$trial26"
python -m "$module26.process" --output "$trial26" --stage freeze -- python -m "$module26.predict" freeze --output "$trial26"
# Dopiero teraz można połączyć predykcje z referencjami:
python -m "$module26.process" --output "$trial26" --stage evaluation -- python -m "$module26.evaluate" --output "$trial26"
python -m "$module26.process" --output "$trial26" --stage diagnostics -- python -m "$module26.diagnostics" --output "$trial26"
python -m "$module26.process" --output "$trial26" --stage gallery -- python -m "$module26.gallery" --output "$trial26"
python -m "$module26.process" --output "$trial26" --stage browser -- python -m "$module26.check_browser" "$trial26/index.html" --out "$trial26/browser"
python -m "$module26.process" --output "$trial26" --stage summarize -- python -m "$module26.summarize" --output "$trial26" --manifest docs/stmdomains/pretrained-self-supervised-manifest.json
```

Każdy katalog wyników i nazwa procesu są jednokrotne. Odtworzenie wymaga
nowego katalogu; polecenia odmawiają nadpisania dowodów. CUDA i QtWebEngine
mogą wymagać uruchomienia poza sandboxem. Wyniki i modele pozostają lokalne.
Źródła obliczeniowe są przypięte przed treningiem; po zamrożeniu nie wolno
ich edytować. Logi `.execution` są wyłączone z zamrożenia predykcji, ponieważ
zapis procesu kończy się dopiero po wyjściu jego wewnętrznego etapu.
Osobne hashe logów trafiają do końcowej ewidencji.

Główne porównanie: grid48, FHk4/MWS, identyczne wejście przed/po adaptacji,
niezmienione FFT i bramka20. Tylko nowe realizacje znanych rodzin kontroli;
TTMAPP pozostaje jedną znaną akwizycją z częściowymi referencjami.
Oddzielamy dowód poprawy reprezentacji **przed odmowami** od kwalifikacji
całego detektora **po odmowach**. Znany limit bramki nie zależy od cech.
Zielone środki okien w galerii nie są wykrytymi środkami molekuł.
