# REG-09: Rozpoznanie deformacji w pasach — etap warunkowy

**What to build:** Użytkownik ogląda pozostałe przesunięcia różnych pasów
obrazu po globalnym XY, aby rozstrzygnąć potrzebę osobnej korekcji tearingu.
**Blocked by:** [REG-07](07-full-movie-comparison.md) i decyzja użytkownika
o uruchomieniu etapu. REG-08 nie jest wymagany.
**Status:** planned
**Manualny odbiór:** niewykonany; implementacja nierozpoczęta.

Obowiązują [plan](../README.md) i [protokół odbioru](../manual-protocol.md).
Przed startem zapisujemy wynik REG-07 i przykłady problemów wewnątrz klatki.

## Zakres i kryteria odbioru

- [ ] Na parze po globalnym XY użytkownik może obejrzeć pasy oraz ich
  lokalne pozostałe przesunięcia, z podziałem na wynik i brak wiarygodnego pomiaru.
- [ ] Orientacja pasów jest opisana względem obrazu; nie zgadujemy kierunku
  skanowania ani trace/retrace. Jeśli użytkownik zna kierunki i czasy skanu,
  zapisujemy je jako dodatkową informację wraz z pochodzeniem.
- [ ] Mapa pokazuje, czy rozbieżność jest podobna w całym obrazie, narasta
  między pasami, czy ma skok. Nie interpretuje automatycznie każdego wzoru
  jako artefaktu: możliwy jest rzeczywisty ruch lub zmiana struktury.
- [ ] Wykres i nakładka odnoszą się do tych samych oryginalnych współrzędnych,
  uwzględniają wspólny obszar ważnych próbek. Brak danych nie jest zerem.
- [ ] Diagnostyka zapisuje ustawienia i wyniki w dokumencie próby, ale nie
  deformuje pikseli, nie zmienia aktywnego aligned i nie modyfikuje MPP/AVI.
- [ ] Odbiór kończy się udokumentowaną decyzją o dalszej korekcji: przykłady,
  wymagany model, brakujące dane i ryzyko usunięcia rzeczywistego ruchu próbki.
  Negatywny wynik rozpoznania jest dopuszczalny i również musi być zapisany.

Poza zakresem: gotowa korekcja tearingu. Jej ewentualny osobny plan musi
określić transformację, dziury/nakładanie próbek, geometrię i metadane;
nie wolno zapisać deformacji jako zwykłego pojedynczego XY.

## Publiczne granice TDD i automatyczne sprawdzenia

- **Para po globalnym XY → przesunięcia pasów:** syntetyczna czysta
  translacja, znana różnica góra/dół i lokalny brak tekstury, z zachowaniem
  źródłowych wartości. Test nie orzeka o fizycznej przyczynie deformacji.
- **GUI/dokument → nakładka i diagnoza:** oś obrazu, właściwe jednostki,
  dane nieznane, anulowanie, zapis/odczyt i niezmienny aktywny wynik.

## Próba manualna

1. Na `cpu.mpp` i wzorcu czystego XY sprawdź, że diagnostyka nie sugeruje
   dużego tearingu tam, gdzie wszystkie struktury dopasowują się jednakowo.
2. Na przygotowanym wzorcu z różnym przesunięciem góry/dół porównaj mapę
   z widoczną rozbieżnością, bez zmiany oryginalnych pikseli.
3. Na obu filmach obejrzyj wskazane po REG-07 pary. Porównaj górę, środek
   i dół; zapisz wiarygodne struktury i miejsca, gdzie ocena jest niemożliwa.
4. Zapisz/otwórz próbę i potwierdź, że żaden obraz nie został zdeformowany.
   Podejmij decyzję, czy i jaki prototyp korekcji pasmowej ma sens.

**Oczekiwany wynik:** rozdzielenie błędnego globalnego XY od możliwej
deformacji wewnętrznej, z jawną niepewnością i zakresem dalszego eksperymentu.
