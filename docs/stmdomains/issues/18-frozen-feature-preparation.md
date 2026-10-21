# Jak przygotować cechy gotowych sieci bez treningu na naszych danych?

ID: 18
Type: task
Labels: wayfinder:task
Mode: AFK
Status: open
Assignee:
Parent: [STM Domains — etap 2: metody i zapis wyników](../map-methods-and-save.md)
Blocked by: 14

## Question

Przygotować odtwarzalne pobieranie lokalnych cech z gotowych modeli dla
porównania domen STM. Zadanie usuwa przeszkody techniczne przed próbą;
nie wybiera skutecznej metody ani nie ocenia jeszcze detekcji domen.

## Zakres przygotowania

- Wczesne cechy gotowej FCN–ResNet101, zgodnie z opisem modułu STM
  w przeglądzie, oraz zamrożony DINOv2 ViT-S/14. Ustalić dokładny wariant
  wag i pobierane warstwy/tokeny; nie przenosić dalszych etapów treningu
  z pracy źródłowej. DINOv3 ViT-S/16 jest opcjonalny i nie blokuje zadania.
- Sprawdzić środowisko `netcat`, dostępny sprzęt, zgodność bibliotek oraz
  dostęp do oficjalnych wag. Ewentualne dodatkowe środowisko i zależności
  opisać lokalnie; nie zmieniać wymagań wspólnych aplikacji w tej sesji.
- Udostępnić lokalne mapy cech na regularnej siatce oraz osobny wariant
  otoczeń wszystkich poprawnych centrów molekuł. Zapisać powiązanie
  wektora z klatką, pozycją w oryginalnym polu i zakresem obrazu, z którego
  pochodzi. Pojedynczy wektor całego obrazu nie zastępuje cech lokalnych.
- Przygotować jawne warianty skali okna, normalizacji i rozdzielczości
  wejścia. Obraz pochodzi z MPP, bez gamma podglądu. Nie dopasowywać
  rozmiaru okna do ręcznych domen ani nie normalizować każdego otoczenia
  do jego rozstawu. Rozróżniać zmianę rozstawu molekuł od technicznego
  przeskalowania obrazu do wejścia modelu.
- Zachować maskę rzeczywistego pomiaru. Padding po rejestracji i dopełnienie
  wymagane przez model nie stają się pomiarem; zapisać wsparcie cechy przy
  brzegu. Skalowanie i przycinanie nie mogą niezauważenie zmienić geometrii.
- Przygotować ponownie używalny zapis cech, z kluczem obejmującym wejście,
  konfigurację modelu i preprocessing. Wagi, dane i duże tablice cech
  pozostają lokalnie poza Git; wersjonowane są kod, manifest i instrukcja.

Sieci pracują z ustalonymi wagami i statystykami, bez aktualizacji parametrów,
treningu głowicy, adapterów ani dopasowywania modelu do pojedynczego obrazu.
Późniejsze PCA i grupowanie nieoznaczonych cech są dozwolone, lecz należy
je jawnie odróżnić od użycia niezmienionego ekstraktora.

## Warunek zakończenia zadania

- Dla każdego podstawowego ekstraktora zapisane: źródło kodu i wag,
  wersja, SHA-256 wag, warstwy/tokeny, preprocessing, skale, urządzenie
  i wersje bibliotek. Brak dostępu lub niezgodność mają konkretny opis.
- Na jawnie wskazanej części wspólnego zestawu wykonano ekstrakcję,
  sprawdzenie współrzędnych, obsługi brzegu i powtarzalności w zapisanej
  tolerancji. Zmiana samych referencji nie wpływa na wynik; usunięcie
  centrów nie zmienia wariantu korzystającego wyłącznie z siatki obrazu.
- Wykazano brak aktualizacji modelu podczas ekstrakcji. Zapisano czas,
  szczytową pamięć i wielkość cech dla reprezentatywnego wejścia, bez
  utożsamiania tego pomiaru z kosztem analizy całej serii.
- Jest polecenie odtworzenia i gotowy co najmniej jeden z dwóch podstawowych
  ekstraktorów. Jeżeli drugi nie działa, raport określa przyczynę i zakres
  ograniczonego porównania; nie zastępuje go po cichu innym modelem.

Zakończenie oznacza gotowość do próby, nie zaliczenie jakości. Jeżeli żaden
podstawowy ekstraktor nie jest dostępny, zadanie pozostaje niezakończone;
wynik techniczny służy ustaleniu dalszego zakresu, nie udawanej predykcji.
Brak opcjonalnego DINOv3 nie wstrzymuje pozostałych badań.

## Dependencies

- [Jak przygotować wspólne wejście i kontrole bez narzucania domen?](14-unsupervised-input-and-controls.md)

## Następne pytanie

- [Czy gotowe cechy sieci pomagają odkrywać domeny bez przykładów?](19-frozen-feature-domains.md)

## Kontekst

- [ML i deep learning bez własnego treningu](../research-training-free-ml-domain-discovery.md)
