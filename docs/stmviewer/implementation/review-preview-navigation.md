# Przegląd dodatku: zoom i przesuwanie — 2026-10-21

Baza: `7a437151e9c3bdf2a48b316fdfce15203087bf87`.
Commit implementacji: `75f419d` — zoom pod kursorem i przesuwanie bez zmiany skali.
Komenda: `git diff 7a43715...75f419d`. Dwie niezależne osie skilla `code-review`.
Źródło zakresu: wyraźne zlecenie użytkownika po ręcznym odbiorze STP,
zapisane w [tickecie 05](issues/05-preview-controls.md#wcześniej-dostarczony-zakres--zoom-i-przeciąganie).

## Standards

0 naruszeń standardów, 0 istotnych uwag heurystycznych. Źródła: główne
`AGENTS.md`, `stmviewer/AGENTS.md`, instrukcja współpracy i indeks implementacji.
Zmiany obejmują wyłącznie aplikację, testy i dokumentację Viewera.

Nawigacja należy do widgetu podglądu, a przycisk okna korzysta z jego
publicznej operacji. Testy sprawdzają widoczny rezultat gestów bez dostępu
do prywatnego stanu. Rozmiar i odpowiedzialność widgetu nie uzasadniają
kolejnego podziału. Dokumentacja odróżnia ręczny odbiór wcześniejszego STP
od niewykonanej próby nowej nawigacji i nie zamyka całego ticketu 05.

## Spec

0 usterek, 0 nieuzasadnionych rozszerzeń zakresu. Przesunięcie obliczane przy
zoomie zachowuje punkt pod kursorem także po wcześniejszym przesunięciu.
Ruch i zwolnienie lewego przycisku aktualizują tylko położenie obrazu.
Dopasuj przywraca cały obraz na środku; poprawny import resetuje widok,
a anulowanie i błąd zachowują jego ustawienia.

Pięć testów sprawdza publiczne gesty, kontrolki i widoczny obraz. Serie,
gamma i szachownica pozostają na później, zgodnie ze zleceniem dodatku.

Łącznie: Standards — 0 ustaleń; Spec — 0 ustaleń; bez uwag wymagających poprawki.
