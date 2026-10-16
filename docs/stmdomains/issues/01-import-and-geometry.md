# Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?

ID: 01
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — etap 1: działający szkielet](../map.md)
Blocked by:

## Question

Jak zdefiniować kontrakt importu gotowego zapisu, tak aby obraz, oznaczenia
molekuł i zapisana rejestracja opisywały te same klatki i współrzędne?

Punktem odniesienia jest podany zapis MolTrack. Ustalmy:

- wymagane i opcjonalne dane: obrazy lub ich odnośniki, identyfikatory i kolejność
  klatek, centra/bboxy, opcjonalne maski, rozmiary, transformacje i ich jakość;
- minimalny zestaw obsługiwanych zapisów MolTrack i dane przekazywane do
  podglądu, bez projektowania teraz formatu własnych wyników;
- odtwarzanie ścieżek po przeniesieniu danych między komputerami, sprawdzanie
  zgodności źródła oraz zachowanie przy brakującym lub niezgodnym obrazie;
- rozróżnienie orientacji macierzy w pliku, obrazu po imporcie i obrazu wyrównanego;
  `original_bbox_xyxy` nie jest automatycznie bboxem raw;
- zachowanie zapisanych przesunięć i oryginalnego pola klatki oraz obsługę braków
  lub niskiej jakości zapisanej rejestracji; szkielet jej ponownie nie oblicza;
- reprezentację brakujących czasów i kalibracji, pustej listy oznaczeń oraz braku
  danych o oznaczeniach — brak rekordu nie musi oznaczać braku molekuł.

Jaka minimalna próba otwarcia istniejącego zapisu potwierdzi zgodność obrazu
z oznaczeniami, również po poprawieniu ścieżki i przy nawigacji między klatkami?
Rozstrzygnięciem jest kontrakt danych i zachowania przy niespójnościach.
Zapis własnych wyników pozostaje w drugim etapie i nie blokuje importu.

Kontekst: [audyt zapisu i orientacji importera](../research-molecular-orientation.md),
[odtwarzanie sesji](../../../moltrack/persistence/session_store.py),
[loader MPP](../../../nanotrack/io/mpp_loader.py).
