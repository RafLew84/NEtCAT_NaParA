# Przegląd ticketu 11 — MPP z metadanymi towarzyszącymi

Data: 2026-10-23. Baza zgodnie z zasadami implementacji:
`b71305bfb2886d734cc087708780f22ea12fd30d`. Implementacja: `137655d`.
Diff: `git diff b71305bfb2886d734cc087708780f22ea12fd30d...137655d`.

Raport zachowuje stan z chwili przeglądu. Następnie użytkownik potwierdził
pozytywny wynik testów manualnych 2026-10-23; [ticket 11](issues/11-mpp-metadata-import.md)
ma status `done`. Potwierdzenie nie zamyka odrębnych odbiorów platform.

Dwie osie sprawdzili równolegle niezależni agenci zgodnie ze skillem
`code-review`, tylko do odczytu i bez uruchamiania testów. Końcowe statusy,
wyniki testów i przekazanie uzupełniono po przeglądzie; kod się nie zmienił.

## Standards

Brak naruszeń reguł repozytorium. Zmiany pozostają w zakresie Viewera
określonym w `stmviewer/AGENTS.md`; nie modyfikują wspólnych czytników
ani konfiguracji. Podział odpowiedzialności jest czytelny: walidacja dodatku
w `mpp_metadata.py`, pochodzenie w `frame.py`, wspólna prezentacja źródła
w `ui/frame_source.py`. Testy korzystają z publicznego importu i kontrolek
GUI, zgodnie z zatwierdzonymi granicami. Dokumentacja zawiera gotowe wzorce,
generator, instrukcję ręcznej próby i rozróżnienie dowodów automatycznych
od odbioru użytkownika.

Heurystyki projektowe: brak uwag wymagających zmiany. Oddzielenie faktycznie
otwartego pliku od historycznego pochodzenia jest uzasadnione przenoszeniem
par MPP–JSON. Jawne przypisywanie pól podczas walidacji nie wymaga abstrakcji;
ułatwia sprawdzenie typów i znaczenia poszczególnych metadanych. Wydzielenie
formatowania źródła usuwa duplikację pomiędzy panelem a miniaturami.

Źródła: `AGENTS.md`, `stmviewer/AGENTS.md`, `docs/PARALLEL_DEVELOPMENT.md`,
indeks implementacji, słownik i pełny katalog heurystyk Fowlera ze skillu.
Nie znaleziono odrębnych CODING_STANDARDS/CONTRIBUTING.

**Standards: 0 naruszeń, 0 zgłoszonych heurystyk.**

## Spec

Brak ustaleń wymagających poprawy. Automatyczne odnajdywanie dodatku,
wersjonowanie i powiązanie przez SHA-256 całego MPP oraz liczbę i kształt
klatek odpowiadają ticketowi 11. Skrót powstaje podczas odczytu tych samych
bajtów, z których dekodowane są obrazy.

Walidacja obejmuje cały dodatek przed zastosowaniem metadanych. Błędne,
nieobsługiwane lub brakujące dane pozostawiają metadane nagłówka filmu
i widoczny komunikat; anulowanie propaguje się do dotychczasowego mechanizmu
importu. Zachowane są indywidualne parametry, źródłowe nagłówki, zera, braki
czasu i przerwy. Historyczne pochodzenie jest oddzielone od otwartego pliku
i bieżącej pozycji; przeniesienie pary nie wymaga rozwiązywania historycznych
ścieżek.

Małe wzorce oraz instrukcja pozwalają ręcznie sprawdzić poprawną parę
i odrzucenia. Ograniczenie do original jest zgodne z ticketem; eksport
i geometria aligned pozostają w etapach 12–13. Kod testów automatycznych
nie stanowi potwierdzenia ręcznego odbioru ani działania na Windows;
dokumentacja zachowuje to rozróżnienie.

Źródła: [ticket 11](issues/11-mpp-metadata-import.md),
[decyzja 04](../issues/04-mpp-export.md#answer),
[decyzja 06](../issues/06-acceptance.md#answer), [słownik](../GLOSSARY.md),
[kontrakt V1](../mpp-metadata-format.md) i zasady odbioru w indeksie implementacji.

**Spec: 0 ustaleń.**

Wyniki testów i status ręcznego odbioru: [przekazanie](../handoff.md).
