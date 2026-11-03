# 25: Eksportuj poprawione klasy i domeny do CSV oraz PNG

**ID:** SD-V4-25

**What to build:** Użytkownik eksportuje oglądany wynik po ręcznych korektach, a opcjonalnie wynik bazowy. CSV i PNG pokazują te same klasy, domeny i liczniki co aplikacja oraz jasno odróżniają wskazania ręczne od wyniku algorytmu.

**Blocked by:** [14: Wyeksportuj przypisania i widok do CSV oraz PNG](14-export-csv-png.md), [23a: Scalaj i dziel klasy ręcznie](23a-split-merge-classes.md).

**Status:** ready-for-agent — dodanie do planu zlecone przez użytkownika 2026-11-03; wykonanie po zależnościach.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru) oraz [zasady edycji ręcznej](README.md#edycja-ręczna-klas-i-domen).

## Kryteria akceptacji

- [ ] Eksport domyślnie dotyczy stanu Po korektach; przed zapisem jawnie wskazuje wariant i zakres. Można wybrać bazowy automat, o ile istnieje. Dla pracy wyłącznie ręcznej aplikacja informuje o braku automatycznego wyniku, bez eksportowania fikcyjnego zera.
- [ ] CSV zachowuje ID molekuł/klatek, klasy i domeny bazowe oraz końcowe, pochodzenie i rodzaj zmiany, identyfikator wyniku/katalogu i rewizję korekt. Nowa ręczna klasa ma ID, nazwę i kolor; brak modelu lub automatycznej ufności pozostaje brakiem. Klasa przypisana bez domeny jest zapisana poprawnie. Po scaleniu/podziale klas z 23a metadane rozróżniają źródłowe i końcowe klasy oraz zakres operacji; nie przedstawiają ręcznej zmiany jako nowego wyniku modelu.
- [ ] Liczniki wynikają z wybranego wariantu, bez podwójnego liczenia molekuł. Liczba ręcznych przypisań jest odróżniona od liczby przypisań algorytmu; nie opisuje się wzrostu pokrycia po korekcie jako poprawy trafności modelu. Powierzchnie zachowują ograniczenia przybliżonej geometrii z 05a/21.
- [ ] PNG odwzorowuje kolory, nazwy, legendę, obrysy oraz ustawienia oglądanego wariantu Klasy/Domeny. Podpis wskazuje wariant i obecność korekt; wynik bazowy zachowuje własną legendę. Eksport zakresu nie miesza rewizji podczas zapisywania ani nie uruchamia analizy.
- [ ] Eksport działa z bieżącej sesji bez zapisywania projektu. Dla klatek bez zmian, bez analizy i z samymi ręcznymi oznaczeniami zachowuje ich odrębne statusy. Błąd lub anulowanie nie zmienia pracy, historii ani stanu niezapisanych korekt.
- [ ] Testy porównują CSV/PNG ze stanem po tworzeniu, rozszerzeniu, podziale/scaleniu domen oraz klas (23a), zmianie klasy i Cofnij/Ponów. Obejmują również operację klas na kilku klatkach i zachowanie odrębnych domen po scaleniu klas. Odbiór GUI obejmuje TTMAPP i mały opisany przykład w netcat; raport zawiera sprawdzenie limitu 1000/1500 linii.

## Test ręczny użytkownika

1. W netcat otwórz TTMAPP, oblicz klatkę 259 i wykonaj korekty domen oraz klas. Wyeksportuj Po korektach do CSV/PNG i otwórz oba pliki poza aplikacją; porównaj ID, kolory, nazwy oraz liczniki z obrazem.
2. Wyeksportuj bazowy automat do osobnych plików. Molekuły zmienione ręcznie mają pierwotne przypisania, a podpis i metadane rozróżniają warianty.
3. Cofnij ostatnią korektę i powtórz eksport. Pliki mają odzwierciedlać bieżący stan, nie ostatni zapis projektu ani ukrytą wersję z cache.
4. Wyeksportuj zakres zawierający klatkę poprawioną, automatyczną i nieanalizowaną. Sprawdź scalenie klas na kilku klatkach, następnie ich podział: pliki zachowują docelowe klasy i osobne domeny, a klatki poza zakresem operacji pozostają bez zmian. Na osobnym przykładzie sprawdź klasę bez domeny oraz ręczną domenę bez analizy. Braki pozostają jawne.
5. Anuluj eksport i sprawdź błąd miejsca zapisu. Korekty oraz historia muszą pozostać bez zmian.

## Granice zadania

Rozszerzenie eksportera z 14, bez zależności od zapisu projektu w 24. CSV/PNG nie zastępują projektu z historią i nie są automatycznie zbiorem treningowym ani referencją naukową.
