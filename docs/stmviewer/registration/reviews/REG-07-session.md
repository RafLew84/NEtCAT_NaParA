# REG-07 — sesje: przegląd i sprawdzenia

Baza: `750c474`. Zakres: [zapis i odczyt sesji](../issues/07-session-save-load.md).
Status: weryfikacja w toku. Po implementacji dwa niezależne przeglądy:
Standards oraz Spec. Ręczny odbiór użytkownika pozostaje osobnym krokiem.

## Granice testów

Stan → zapis → odczyt, odmowa/anulowanie → zachowanie pracy/pliku, GUI →
wznowienie korekt i eksport. Format bez pickle, z walidacją struktury, rozmiaru
oraz geometrii. Testy sprawdzają zachowanie i dane, nie szczegóły wywołań.
