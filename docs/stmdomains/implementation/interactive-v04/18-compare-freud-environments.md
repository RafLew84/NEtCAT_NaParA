# 18: Porównaj otoczenia molekuł metodą freud bez zadawania K

**ID:** SD-V4-18

**What to build:** Użytkownik wybiera próbę freud.EnvironmentCluster, ustawia tolerancję porównania otoczeń, uruchamia bieżącą klatkę i ogląda klasy oraz końcowe domeny na molekułach obok zachowanego wyniku metody bazowej aplikacji.

**Blocked by:** [06: Strojenie tworzenia domen i porównanie wyniku](06-tune-domain-formation.md), [16: Zobacz kierunek, rozstaw i jakość geometrii na obrazie](16-inspect-local-geometry.md).

**Status:** ready-for-agent — dodanie ograniczonej próby do planu zlecone przez użytkownika; wykonanie po zależnościach.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady rozszerzeń](README.md#rozszerzenia).

## Kryteria akceptacji

- [ ] Jeden wariant EnvironmentCluster działa od ustawienia w UI do wyniku na rzeczywistych oznaczeniach. Liczba klas wynika z tolerancji; nie jest po drodze wymuszana przez KMeans ani Auto z 12. Nową hipotezą jest porównanie otoczeń tą metodą, nie samo zastąpienie obliczeń NumPy biblioteką.
- [ ] Wybór sąsiadów, zasięg i jednostki tolerancji są jawne. Przeciwległe brzegi obrazu STM nie są łączone przez okresowe warunki brzegowe. Nie dobiera się dowolnie dalekich punktów tylko po to, aby uzupełnić liczbę sąsiadów.
- [ ] Wymóg jednakowej liczby sąsiadów jest obsłużony jawnie: nieporównywalne lub niepełne otoczenie dostaje status i powód odmowy. Brzegi oraz brakujące detekcje mają oddzielne sprawdzenie; stała liczba najbliższych sąsiadów nie ukrywa braków.
- [ ] Jawnie wybrano i zapisano sposób traktowania obrotu. Orientacja jest osobnym pomiarem; klasa zależna od obrotu nie jest nazywana typem struktury. Jeżeli dopasowanie usuwa obrót, tworzenie domen nadal uwzględnia różnice orientacji z 16.
- [ ] Klaster podobnych otoczeń nie staje się automatycznie jedną domeną. Osobny etap zachowuje spójność przestrzenną, przerwy/bariery i lokalne identyfikatory domen. Widok Klasy/Domeny wyraźnie pokazuje różnicę; porównywane warianty mają opisane różnice etapów.
- [ ] Zakres próby jest ograniczony do bieżącej klatki, małego zapisanego zestawu tolerancji, wspólnych kontroli i TTMAPP259–266. Te same ustawienia oraz powtarzalne warunki są użyte do oceny; raport pokazuje także porażki na przesunięciu sieci, szumie i brakujących centrach.
- [ ] Zmiana tolerancji, postęp i anulowanie działają w aplikacji. Użytkownik wraca do identycznego, zachowanego wyniku metody bazowej, wcześniej obliczonego z tych samych wejść. Żaden wariant nie wymaga gotowych modeli lub przypisań v0.4. Raport porównuje trafność podziału i odmowy, oddzielnie od samej liczby klas i pokolorowanych molekuł.
- [ ] Wykonawca sprawdza dostępność i wersję zależności w środowisku lokalnym, bez zmiany wspólnej konfiguracji poza sesją integracyjną. Brak opcjonalnej biblioteki nie blokuje dotychczasowego UI. Raport testów i limit 1000/1500 linii obowiązują również adapter i testy tej metody.

## Test ręczny użytkownika

1. Uruchom aplikację w środowisku netcat, otwórz MPP/JSON i oblicz klatkę 259 metodą bazową. Wybierz freud, ustaw tolerancję z instrukcji próby, przelicz i zobacz wynik bez podawania K.
2. Przełącz Klasy/Domeny oraz wynik metody bazowej/freud. Sprawdź obszary rozdzielone przerwą i kilka szarych molekuł z powodami odmowy.
3. Zmień tolerancję i sprawdź faktycznie użyte ustawienia. Na kontrolach obrotu oraz przeciwległych brzegów obrazu upewnij się, że orientacja i sąsiedztwo mają zadeklarowane znaczenie.
4. Przejdź przez jedną sieć, dwie orientacje, przesunięcie przy tym samym kącie i brakujące centra. Porównaj wynik z opisem kontroli, także gdy metoda nie spełnia oczekiwanego podziału.

## Granice zadania

Nie obejmuje równoległego wdrożenia EnvironmentMotifMatch, dużego przeszukiwania ustawień ani stabilnego nazewnictwa klas między niezależnymi uruchomieniami. Negatywny wynik oceny jest dopuszczalnym zakończeniem próby. Nie wymaga ukończenia 17 ani wczytania paczki v0.4; jej kod pozostaje materiałem źródłowym metody bazowej.
