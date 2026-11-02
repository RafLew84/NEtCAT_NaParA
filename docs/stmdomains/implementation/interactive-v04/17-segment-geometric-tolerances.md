# 17: Porównaj domeny tworzone według tolerancji geometrycznych

**ID:** SD-V4-17

**What to build:** Użytkownik wybiera eksperymentalny sposób tworzenia domen, reguluje dopuszczalną różnicę kąta i rozstawu oraz jakość pomiaru, a następnie porównuje przypisania molekuł z wynikiem metody bazowej aplikacji na tym samym obrazie.

**Blocked by:** [06: Strojenie tworzenia domen i porównanie wyniku](06-tune-domain-formation.md), [16: Zobacz kierunek, rozstaw i jakość geometrii na obrazie](16-inspect-local-geometry.md).

**Status:** ready-for-agent — dodanie rozszerzenia do planu zlecone przez użytkownika; wykonanie po zależnościach.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady rozszerzeń](README.md#rozszerzenia).

## Kryteria akceptacji

- [ ] Alternatywny tryb tworzy konkretne, przestrzennie spójne domeny z poprawnych pomiarów 16. Nie wymaga ustalenia liczby domen ani bezwarunkowej zgodności wstępnych etykiet KMeans. Nieznany typ może pozostać nieznany.
- [ ] Kontrolki mają jawne jednostki: różnica kąta w stopniach z uwzględnieniem symetrii, względna różnica rozstawu w procentach, jakość pomiaru i minimum wsparcia. Każda wpływa na obliczenia, a użyte wartości są związane z wynikiem.
- [ ] Kontrolowana jest zgodność całego regionu, a nie tylko kolejnych par sąsiadów. Przykład stopniowo zmieniającej się orientacji nie może połączyć końców przekraczających zadany limit regionu. To rozwinięcie kontroli opisanej już w kodzie v0.4, nie deklaracja jej braku.
- [ ] Zachowane są ograniczenia odległości i jawne bariery/przerwy. Brak pomiaru, usunięte centra i lokalny defekt nie są automatycznie dowodem fizycznej granicy ani zgodności obszarów.
- [ ] Osobny przypadek z jednakowym kątem i rozstawem, lecz przesunięciem sieci, ma jawny wynik oceny. Sam podobny kąt nie jest testem zgodności fazy. Nierozdzielona granica jest raportowaną porażką próby, a metoda pozostaje eksperymentalna; nie zmienia się definicji domeny, by uznać ją za sukces.
- [ ] Działa przełączanie metoda bazowa/nowy wynik z zachowaniem klatki i powiększenia, szarych nieprzypisanych molekuł oraz powodów odmów. Oba wyniki są obliczone przez aplikację z tych samych wejść; powrót do metody bazowej pokazuje zachowane przypisania, bez odczytywania paczki v0.4.
- [ ] Mały, zadeklarowany zestaw ustawień jest porównany na wspólnych kontrolach i TTMAPP259–266. Raport pokazuje błędne scalenia, podziały i granice, a udział przypisań osobno. Nie wymaga pozornej poprawy dla zamknięcia rzetelnie wykonanej próby.
- [ ] Testy obejmują wpływ każdej kontrolki, symetrię kątów, cały region, przerwę, brakujące centra i powtarzalność. Przekazanie rozróżnia test GUI od automatycznych oraz potwierdza zasadę 1000/1500 linii.

## Test ręczny użytkownika

1. Otwórz MPP/JSON i na klatce 259 uruchom metodę bazową aplikacji oraz nowy tryb przy zapisanych ustawieniach. Przełączaj wyniki bez zmiany pozycji obrazu; porównaj konkretne molekuły i domeny.
2. Osobno zmień tolerancję kąta, rozstawu i minimum wsparcia. Sprawdź faktyczne ustawienia wyniku oraz przyczynę przyjęcia lub odmowy wskazanej molekuły.
3. Otwórz dostarczone kontrole: jedna sieć, dwie orientacje, stopniowy obrót, przesunięcie sieci, brakujące centra i rzeczywista przerwa. Porównaj oznaczenia z jawnym oczekiwanym podziałem; porażki muszą pozostać widoczne w raporcie.
4. Wróć do zachowanego wyniku metody bazowej i anuluj nowe przeliczenie. Wcześniejszy poprawny wynik ma pozostać dostępny.

## Granice zadania

Jeden alternatywny sposób tworzenia domen. Nie obejmuje nowej rodziny estymatorów fazy, treningu sieci ani katalogu typów. Pełny detektor domen 2D nadal wymaga osobnego naukowego odbioru. Historyczne raporty v0.4 są materiałem porównawczym, a nie źródłem przypisań wyświetlanych w aplikacji.
