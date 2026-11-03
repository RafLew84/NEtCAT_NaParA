# 24: Zapisz korekty i wznów ręczną edycję projektu

**ID:** SD-V4-24

**What to build:** Użytkownik zapisuje poprawiony wynik do projektu STM Domains, zamyka aplikację i odzyskuje własne klasy, domeny, poprawki oraz historię Cofnij/Ponów. Może nadal porównać wynik automatyczny z ręcznie poprawionym.

**Blocked by:** [13: Zapisz projekt i otwórz wynik bez ponownych obliczeń](13-save-open-project.md), [23: Twórz klasy ręcznie i poprawiaj ich przypisania](23-manual-classes.md).

**Status:** ready-for-agent — dodanie do planu zlecone przez użytkownika 2026-11-03; wykonanie po zależnościach.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady edycji ręcznej](README.md#edycja-ręczna-klas-i-domen).

## Kryteria akceptacji

- [ ] Zapis zachowuje wybrany wynik bazowy lub jawny brak analizy, stan po korektach, własne klasy z ID/nazwą/kolorem/wersją oraz domeny i geometrię. Oba stany odnoszą się do tych samych źródeł, klatek i ID oznaczeń; zapis obejmuje wszystkie klatki wybranego wyniku, także częściowego.
- [ ] Historia operacji 21–23 i bieżąca pozycja Cofnij/Ponów są częścią projektu. Po ponownym otwarciu można cofnąć/ponowić wcześniejszą zmianę, również gdy zapisano projekt po cofnięciu operacji. Zmiana nazwy wspólnej klasy odtwarza się spójnie we wszystkich odwołujących się do niej klatkach.
- [ ] Projekt otwiera się bez źródłowych MPP/JSON, modeli v0.4 i ponownej analizy. Podgląd odtwarza zapisane przypisania, obszary, legendy oraz liczniki w wariantach Automatyczny/Po korektach. Ręczna praca bez analizy nie staje się automatycznym wynikiem z zerem domen.
- [ ] Zapisz jako tworzy osobny wariant pracy; nie nadpisuje starego projektu ani bazowego wyniku. Nie wymaga się archiwum wszystkich prób obliczeń w jednym pliku. UI pokazuje, jaki wynik zapisuje i czy pozostają niezapisane warianty w sesji.
- [ ] Starszy projekt bez korekt otwiera się z pustą historią. Walidacja odrzuca błędne odwołania do klatek/molekuł/klas, konflikt członkostwa i niespójny stan historii, bez cichej naprawy zmieniającej wynik. Format ma wersję i kontrolę integralności; zapis jest atomowy.
- [ ] Stan niezapisanych zmian uwzględnia edycje, cofanie, ponawianie oraz metadane klas. Zamknięcie lub otwarcie innego projektu pozwala zapisać, jawnie odrzucić albo anulować. Błąd/anulowanie zapisu zachowuje plik oraz bieżące poprawki i historię; nie resetuje znacznika niezapisanej pracy.
- [ ] Testy round-trip obejmują wszystkie rodzaje korekt, kilka klatek, zapis po Cofnij, pracę bez analizy, starszy projekt i uszkodzenie. Wykonano opisany odbiór GUI w netcat oraz kontrolę 1000/1500 linii; wynik sprawdzeń użytkownika raportuje się oddzielnie.

## Test ręczny użytkownika

1. W netcat otwórz TTMAPP, oblicz 259–260. Na 259 utwórz/rozszerz domenę, podziel lub połącz domeny i nadaj ręczną klasę. Na 260 przypisz tę samą klasę wskazanej domenie.
2. Cofnij ostatnią operację, zapisz projekt, zamknij aplikację i otwórz zapis przy niedostępnych źródłowych MPP/JSON. Przypisania, kolory, obrysy i liczniki mają odpowiadać stanowi przed zamknięciem bez nowego obliczenia.
3. Wykonaj Ponów, potem Cofnij. Porównaj Automatyczny/Po korektach na obu klatkach. Zapisz jako drugi projekt i sprawdź, że pierwszy nadal odtwarza poprzedni wariant.
4. Zapisz i otwórz osobny przykład ręcznej pracy bez analizy oraz starszy projekt bez korekt. Sprawdź jawny brak analizy i pustą historię starszego projektu.
5. Sprawdź anulowanie zamknięcia, anulowanie/błąd zapisu oraz dostarczony uszkodzony projekt. Bieżąca praca i istniejący poprawny plik mają przetrwać.

## Granice zadania

Rozszerzenie własnego formatu z 13 o korekty i historię wybranego wyniku. Bez synchronizacji między użytkownikami, archiwum wszystkich prób, automatycznej migracji korekt na nowy katalog lub uczenia. Eksport do CSV/PNG jest osobnym ticketem 25.
