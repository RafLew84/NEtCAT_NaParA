# Przekazanie — zapis MPP STM Viewer

Data: 2026-10-19
Gałąź: `viewer/start`
Baza bieżącej kontynuacji: `777351b`
Poprzedni checkpoint rozpoznania: `777351b` (na bazie `5412dbb`).
Commit zamykający: identyfikator w końcowej wiadomości sesji.

## Wynik

Rozstrzygnięto [Zapis MPP z wartościami i metadanymi](issues/04-mpp-export.md#answer).
Zapis obejmuje całą pozostałą serię, wybór original/aligned, wartości niezależne
od podglądu, MPP z towarzyszącymi metadanymi, NaN, pełną geometrię, pochodzenie
i czasy. Różne skale/kanały nie blokują zapisu; wspólny nagłówek nie udaje
kalibracji wszystkich klatek. Ponowne dopasowanie zależy od danych, nie
znacznika aligned; brakujące próbki pozostają nieobsługiwane przez backendy.

Użytkownik doprecyzował, że chodzi o zwykłe utworzenie MPP, bez osobnego trybu
„eksport do WSxM”. WSxM pozostaje programem, w którym chce otwierać wynik.
Zgodność NaN i interpretacji filmu nie została potwierdzona. Nie zatwierdzono
zerowania braków ani przycinania obrazu w celu poprawienia kompatybilności.

Zaktualizowano mapę, słownik, powiązanie z decyzją rejestracji i komentarz
w tickecie odbioru. Wszystkie zmiany są dokumentacją; eksporter i wspólne
czytniki nie zostały zaimplementowane/zmienione. Aplikacja pozostaje szkieletem.

Następny dostępny ticket: [Opcje filmu AVI](issues/05-avi-export.md).
[Dane i kryteria odbioru](issues/06-acceptance.md) oczekują jeszcze na AVI.
Wcześniejsze ustalenia rejestracji są w [jej tickecie](issues/03-registration.md)
i historii `5412dbb`; prototyp podglądu nadal ma wersję `efb7e50`.

## Wykonane sprawdzenia i ograniczenia

- Poprzedni checkpoint obejmował przegląd lokalnych readerów i małą próbę
  dwóch klatek MPP: wartości, NaN, obrót, skala/offset, dodatkowe pole nagłówka,
  kompletne i niepełne czasy, nieciągłe indeksy, jednostki oraz limit linii.
  Przeczytano też nagłówki i wybrane wartości STP/S94/MPP z lokalnego `data/`
  worktree Domains. [Szczegóły](reconnaissance.md#uzupełnienie-kontrakt-odczytu-mpp).
- W tej kontynuacji przejrzano źródła pierwotne UAM, dyskusję z autorem
  Gwyddion oraz wersjonowany kod SciFiReaders. [Notatka](wsxm-mpp-compatibility.md)
  oddziela sprawdzone fakty od niezweryfikowanych zachowań WSxM.
- Potwierdzono ustawienie row-major w punktach startowych NaPara/NanoTrack.
  Nie testowano ich końcowego wyświetlania ani zapisu w WSxM.
- Sprawdzono 111 lokalnych odnośników i kotwic, statusy i brak cykli zależności
  sześciu ticketów oraz zachowanie pierwotnego pytania. Jedynym dostępnym
  otwartym ticketem jest teraz AVI. `git diff --check` przeszedł poprawnie.

Nie uruchamiano w tej kontynuacji zestawu testów aplikacji, GUI ani nowego
próbnego eksportera. Nie znaleziono WSxM/Wine w sprawdzonych lokalizacjach;
nie instalowano programu. Pełny test MPP → aplikacje repo/WSxM i z powrotem
pozostaje do wykonania przy implementacji/odbiorze. Rozpoznanie kodu innych
czytników nie stanowi testu WSxM.

## Potrzeby implementacji i integracji

- Dodać zapis obsługiwanego wariantu double MPP oraz wersjonowanych metadanych
  towarzyszących, ich powiązanie z zawartością filmu, walidację i spójny zapis.
  Brak dodatku pozwala oglądać film; nie wolno używać dodatku należącego do
  innych danych. Eksport nie jest zapisem kompletnej sesji.
- Zachować metadane każdej klatki, źródłowe numery i czasy, geometrię pola
  pomiaru osobno od maski próbek, historyczne odniesienie i pełny obszar aligned.
  Nie kopiować metadanych pierwszej klatki jako prawdy o całej serii.
- Uzgodnić orientację STP/S94/MPP we wspólnej warstwie. Czytnik MPP i loader
  NanoTrack mają różne miejsca obrotu; odbiór powinien obejmować asymetryczne
  dane i wszystkich wskazanych odbiorców.
- Jawnie modelować jednostkę wartości, nieznaną kalibrację oraz jednostki
  umowne. Obecny parser skali nie zapewnia tego kontraktu. Poprawić warianty
  nazw offsetu/kanału STP; nie normalizować próbki według liczby w Z Amplitude.
- Poprawić obsługę niepełnych czasów i jednostek synchronizacji; usunięcie
  klatki nie może pozostawiać niepasującej osi czasu. Numery wyjściowe i
  pochodzenie są odrębne.
- Rozwiązać limit 1000 linii nagłówka, uwzględnić rzeczywisty rozmiar nagłówka
  w bajtach i poprawny binarny wariant zapisu. Sam test lokalnego czytnika,
  który ignoruje niektóre deklaracje nagłówka, nie potwierdza zgodności MPP.
- Sprawdzić w WSxM wartości double, orientację, skalę, NaN, brak fizycznej
  kalibracji dla mieszanej serii i zachowanie po ponownym zapisaniu filmu.
  Metadane STM Viewer nie zapewniają WSxM interpretacji indywidualnych masek
  lub kalibracji. Zmiana zawartości MPP może unieważnić jego dodatek.

Zmiany współdzielonych modułów i konfiguracji są do sesji integracyjnej,
z testami ich odbiorców. W tej sesji nie zmieniono wspólnego kodu.
