# Jak przeglądać obrazy i oznaczenia w szkielecie?

ID: 07
Type: prototype
Labels: wayfinder:prototype
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 1: działający szkielet](../map.md)
Blocked by: 01

## Question

Jaki minimalny układ okna pozwala otworzyć zapis, sprawdzić zgodność oznaczeń
z obrazem i przejrzeć klatki bez wdrażania analizy domen?

Przygotujmy szkic do reakcji użytkownika: wybór zapisu, naprawa ścieżki do
obrazu, nawigacja serii, obraz z gotowymi oznaczeniami, zoom i gamma,
przełączanie original/aligned z użyciem zapisanej rejestracji oraz granica
oryginalnego pola pomiarowego. Ustalmy zachowanie przy pojedynczej klatce,
brakujących oznaczeniach, brakującej rejestracji i niewiarygodnej kalibracji.

Rozstrzygnięcie opisuje podstawowy ekran i przejścia zaakceptowane na szkicu.
Interfejs ma umożliwić wizualne sprawdzenie importu na rzeczywistych danych.
Wyniki metod, warstwy domen, wykresy i statystyki należą do etapu 2; ich brak
nie blokuje tego pytania. Wejściowe oznaczenia pozostają danymi do podglądu.

## Dependencies

- [Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?](01-import-and-geometry.md)

## Comments

### 2026-10-16 — podział zakresu zatwierdzony przez użytkownika

Zawężono wcześniejsze pytanie o kompletny interfejs analizy do podglądu
szkieletu. Prezentację prób metod przeniesiono do
[Jak porównać metody wykrywania wysp i domen w serii?](05-stable-types-across-frames.md), a interakcje
z trwałymi wynikami do [Co zapisujemy i eksportujemy po próbach metod?](08-save-and-export.md).
