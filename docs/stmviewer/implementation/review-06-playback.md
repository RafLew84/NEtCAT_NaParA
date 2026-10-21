# Przegląd ticketu 06 — Play, Pause i tempo odtwarzania

Data: 2026-10-21. Baza zgodnie z zatwierdzonymi zasadami implementacji:
`0d57200d4d606292f95fe56cca831c78e437673f`.
Commit implementacji: `83c20a9`.
Diff: `git diff 0d57200d4d606292f95fe56cca831c78e437673f...83c20a9`.

Dwie osie sprawdzili równolegle niezależni agenci zgodnie ze skillem
`code-review`. Przegląd tylko do odczytu, bez ponawiania testów przez agentów.
Końcowe wyniki i status dokumentacji uzupełniono po otrzymaniu obu raportów.

## Standards

**0 naruszeń udokumentowanych zasad; 0 uwag heurystycznych wymagających działania.**

Zmiana mieści się w zakresie Viewera określonym przez `stmviewer/AGENTS.md`
i nie ingeruje we współdzielone moduły. Testy korzystają z publicznych
kontrolek oraz obserwowalnych obrazów; spowolnienie importu odbywa się
na granicy I/O. Instrukcja manualna podaje dostępne dane, uruchomienie,
czynności i oczekiwane wyniki. Pomiar ekranu, Qt offscreen oraz niewykonany
odbiór ręczny/Windows są rozdzielone zgodnie z zasadami odbioru.

Nowa logika odtwarzania jest niewielka i skupiona w oknie; wyodrębnienie
`_display_frame` oddziela zmianę obrazu od ręcznej nawigacji zatrzymującej
Play. Nie znaleziono uzasadnienia dla dodatkowej abstrakcji ani refaktoru
w tym tickecie. Sprawdzono wszystkie siedem zmienionych plików.

Źródła: `AGENTS.md`, `stmviewer/AGENTS.md`, `docs/PARALLEL_DEVELOPMENT.md`,
indeks implementacji, słownik oraz pełny katalog heurystyk Fowler ze skillu.
Nie znaleziono odrębnych CODING_STANDARDS/CONTRIBUTING.

## Spec

**0 uwag do implementacji; 0 rozszerzeń zakresu. Otwarty warunek odbioru płynności.**

- Play/Pause, sześć temp, domyślne 5 kl./s, pętla, zakończenie na ostatniej
  i ponowny start od pierwszej odpowiadają specyfikacji.
- „Ręczny wybór […] zatrzymuje Play” obejmuje również bieżącą miniaturę,
  uchwyt suwaka i ponowne wpisanie numeru. Synchronizacja miniatur przez
  odtwarzanie nie zatrzymuje filmu.
- „Przy przeciążeniu program zwalnia bez pomijania klatek”: przejście zawsze
  dotyczy następnego indeksu; synchroniczne malowanie kończy się przed
  ponownym zaplanowaniem timera. Test przeciążenia sprawdza kolejne obrazy.
- Gamma, zoom, przesunięcie i tempo pozostają dostępne podczas odtwarzania.
  Zmiana klatki zachowuje ustawienia podglądu.
- Udany import zatrzymuje film na pierwszej klatce i resetuje podgląd.
  Błąd lub anulowanie pozostawia starą serię i jej bieżący stan odtwarzania.

W chwili przeglądu trwał jeszcze pomiar, zgodnie z wymaganiem „5 kl./s oraz
reakcja wyboru/Pause do 250 ms w co najmniej 95% prób”. Przygotowany skrypt
mierzy zmiany pikseli, a dokumentacja poprawnie odróżnia bufor Qt offscreen
od fizycznego ekranu. Ręczny odbiór, Windows, duża seria i aligned pozostają
jawnie niewykonane lub przypisane późniejszym etapom; nie są brakami
implementacji tego ticketu.

Uzupełnienie po przeglądzie: pomiar 84 klatek 512 × 512 przez 30 s w Qt
offscreen dał 4,956 kl./s, p95 odstępu 204,34 ms, bez pominięć; po 50 prób
Pause i wyboru dało p95 5,40 / 10,70 ms i 100% prób poniżej 250 ms.
Pomiar fizycznego ekranu został zakłócony zasłonięciem okna. Nie deklarujemy
zaliczenia płynności na monitorze; ticket ma `ready-for-review` do odbioru
użytkownika. Wyniki i odtwarzalna komenda są w [przekazaniu](../handoff.md).

Źródła: [ticket 06](issues/06-playback.md), [decyzja 02](../issues/02-preview-playback.md#answer),
[decyzja 06](../issues/06-acceptance.md#answer), [słownik](../GLOSSARY.md).

Łącznie: Standards — 0 ustaleń; Spec — 0 usterek kodu, 1 otwarty warunek odbioru płynności na monitorze.
