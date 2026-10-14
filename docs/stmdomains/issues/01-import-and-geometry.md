# Jak zapis wejściowy odtwarza obrazy, oznaczenia i rejestrację?

ID: 01
Type: grilling
Labels: wayfinder:grilling
Mode: HITL
Status: open
Assignee:
Parent: [STM Domains — specyfikacja analizy typów uporządkowania w serii](../map.md)
Blocked by:

## Question

Jak zdefiniować kontrakt importu gotowego zapisu, tak aby obraz, oznaczenia
molekuł i zapisana rejestracja opisywały te same klatki i współrzędne?

Punktem odniesienia jest podany zapis MolTrack. Ustalmy:

- wymagane i opcjonalne dane: obrazy lub ich odnośniki, identyfikatory i kolejność
  klatek, centra/bboxy, opcjonalne maski, rozmiary, transformacje i ich jakość;
- granicę wsparcia konkretnego formatu oraz kontrakt pozwalający później dodać
  inny adapter, bez uzależnienia analizy od nazw pól MolTrack;
- odtwarzanie ścieżek po przeniesieniu danych między komputerami, sprawdzanie
  zgodności źródła oraz zachowanie przy brakującym lub niezgodnym obrazie;
- rozróżnienie orientacji macierzy w pliku, obrazu po imporcie i obrazu wyrównanego;
  `original_bbox_xyxy` nie jest automatycznie bboxem raw;
- zachowanie zapisanych przesunięć i oryginalnego pola klatki, obsługę braków lub
  niskiej jakości rejestracji oraz to, czy potrzebna jest opcja jej ponownego liczenia;
- reprezentację brakujących czasów i kalibracji, pustej listy oznaczeń oraz braku
  danych o oznaczeniach — brak rekordu nie musi oznaczać braku molekuł.

Jaka minimalna próba odtworzenia potwierdzi zgodność obrazu z oznaczeniami po
zapisie i ponownym otwarciu, również po zmianie ścieżki i kolejności klatek?
Rozstrzygnięciem jest kontrakt danych i zachowania przy niespójnościach.

Kontekst: [audyt zapisu i orientacji importera](../research-molecular-orientation.md),
[odtwarzanie sesji](../../../moltrack/persistence/session_store.py),
[loader MPP](../../../nanotrack/io/mpp_loader.py).
