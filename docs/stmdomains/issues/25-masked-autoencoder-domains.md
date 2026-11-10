# Czy maskowane odtwarzanie obrazu uczy relacji potrzebnych do domen?

ID: 25
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: resolved
Assignee: Codex — domains/start
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 23

## Answer — 2026-11-01

Wykonano [próbę 25](../masked-autoencoder-trial.md) zgodnie z przypiętym
[protokołem](../masked-autoencoder-protocol.md); [manifest](../masked-autoencoder-manifest.json)
zachowuje źródła, koszty i dowody. **12/12 fitów, 19 800 kroków, 44 928 predykcji.**
Mask50 zmniejsza błąd zakrytych pikseli względem AE21 o medianę 58,80%
na tych samych wejściach walidacyjnych, ale nie poprawia końcowych domen:
TTMAPP transfer 0/174, transdukcja FH 4/782, MWS 0/782.
F1 czterech głównych granic kontrolnych wynosi 0, przed i po odmowach.
Częściowy zysk zbiorczego błędu par względem AE21 na syntetykach nie daje
przewagi nad pozostałymi bazami w łącznej ocenie rodzin ani spełnienia
pełnych kryteriów. Izolowane korzyści, także względem FFT, opisuje raport.

Zakończono eksperyment; **nie przyjęto detektora**. Wynik otrzymuje otwarty
odbiór 13. 26 i dodatkowe MPP/STP nadal niewybrane/odłożone.
Porównanie transdukcyjne ma ograniczenie: masked AE trenowano 1300 kroków,
a zapisany AE21 600. Rekonstrukcja nie zastępuje pomiaru, a przypisanie
okien nie jest wykrywalnością molekuł. Pełne ograniczenia są w raporcie.

Galeria: `.scratch/masked-ae-25/index.html`; 143 interakcje QtWebEngine,
zero błędów JS, pięć zrzutów obejrzanych. Audyt metryk niezależnie odtworzył
7488 głównych wyników i 22 464 porównania; stare bazy zachowano bitowo.
Pierwszą ocenę przerwał SIGTERM; niezmieniony etap ukończono poza sandboxem,
bez restartu fitów. Koszt przerwania ujęto konserwatywnie i jawnie.

Podjęcie `36d5cb1`, źródła/protokół `b8fdc9a`; commit zakończenia w przekazaniu
i odpowiedzi końcowej. Prototyp: `prototype/stmdomains-masked-autoencoder`.
[Instrukcja odtworzenia](../../../stmdomains/experiments/training/masked_ae/README.md).

## Podjęcie — 2026-11-01

Użytkownik po omówieniu 24a wydał bezpośrednie polecenie „wykonaj 25”.
To wybiera rozszerzenie niezależnie od wcześniejszej decyzji 23.
[Protokół 25](../masked-autoencoder-protocol.md) ustala osobny budżet:
12 nowych fitów (maskowanie25/50%, trzy ziarna, transfer/transdukcja),
mały AE32 identyczny z 21 oraz zapisane AE/SSL/FFT i własne inicjalizacje
jako odniesienia. Dane TTMAPP pozostają obecne; nowe realizacje kontroli
nie są nowymi pomiarami. 26 i przygotowanie dodatkowych MPP/STP niewybrane.
Próba ocenia maskowanie, bez rozszerzania modelu lub kontekstu.

## Warunek podjęcia

Rozszerzenie warunkowe: krok 23 wskazuje konkretną lukę w reprezentacji
otoczenia i wybiera tę próbę. Późniejsze bezpośrednie polecenie użytkownika wybrało próbę, jak powyżej.

**Decyzja 23 — 2026-11-01:** użytkownik zakończył obecny pilot bez wyboru
tej próby. Ticket pozostaje `open`, niewybrany i warunkowy; nie ma nowego
budżetu ani zgody na rozpoczęcie treningu przez samo zakończenie 23.

## Question

Czy przewidywanie zakrytych fragmentów zmusza model do uczenia układu
molekuł skuteczniej niż zwykły AE lub lokalne SSL? Sprawdzić mały model
maskowany inspirowany MAE z [przeglądu](../research-self-supervised-domain-learning.md),
bez rozpoczynania od dużego treningu modelu podstawowego.

## Porównanie

- Zacząć od małego encodera i masek obejmujących fragmenty otoczenia,
  nie tylko pojedyncze piksele. W protokole zapisać skalę okien, rozmiar,
  udział i sposób losowania masek; sprawdzić kilka wariantów w budżecie
  wybranym w kroku 23. Wszystkie skale mają znaczenie w geometrii pomiaru.
- Oddzielić maskowanie zadania uczenia od braku pomiaru i paddingu.
  Stratę liczyć wyłącznie dla rzeczywiście zmierzonych danych; wartości
  poza polem nie są prawdą do rekonstrukcji. Rekonstrukcja nigdy nie
  zastępuje oryginalnego MPP ani dowodu istnienia molekuły.
- Porównać ze zwykłym AE o zbliżonej pojemności oraz lokalnym SSL
  z pierwszych prób. Sprawdzić, czy zysk pochodzi z maskowania, większego
  kontekstu czy samej wielkości modelu. Zwiększenie sprzętu wymaga pomiaru
  uzasadniającego daną hipotezę, a nie tylko mniejszej straty treningowej.
- Cechy lokalne przekazać do wspólnego grupowania, oceny porządku i granic.
  Zachować rozstaw, osobną orientację, zero/jedną/wiele domen i katalog
  wspólny dla zakresu. Dobra interpolacja jasności nie jest wynikiem domen.

## Wynik do omówienia

Obowiązują dane, podział, kontrola przecieku i powtórzenia kroku 20 oraz
miary kroku 14. Oprócz straty zapisać pełne nakładki, błędy i odmowy,
kontrole granic/rozstawu/orientacji, stabilność oraz koszty treningu
i zastosowania. Referencje służą tylko ocenie zapisanego wyniku.

Wynik to odtwarzalna próba i decyzja, czy maskowanie daje korzyść względem
wcześniejszych modeli. Wynik negatywny może zamknąć zadanie po omówieniu.
Wniosek trafia do odbioru 13 po uzupełnieniu jego zależności przy wyborze
rozszerzenia; nie wymaga automatycznego przejścia na większą kartę.

## Dependencies

- [Czy trening daje poprawę i które rozszerzenie warto wykonać?](23-training-comparison-and-next-step.md)
