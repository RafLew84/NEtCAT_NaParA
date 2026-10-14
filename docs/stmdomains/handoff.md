# STM Domains — przekazanie

Data: 2026-10-14. Gałąź: `domains/start`.

## Zakres i wynik

Przygotowano [notatkę badawczą o ogólnym wykrywaniu domen](research-general-domain-detection.md)
na podstawie kodu MolTrack i źródeł pierwotnych. Użytkownik określił, że interesuje
go zarówno regularność rozmieszczenia, jak i orientacja samych molekuł.
Pozycje molekuł będą dostarczone przez YOLO lub oznaczenia ręczne; wykrywanie
centrów nie jest przedmiotem tego badania. Obraz przy znanych centrach pozostaje
potrzebny do niezależnego pomiaru orientacji samych molekuł.

Notatka rozróżnia założenia obecnego MolTrack, wyniki opublikowanych badań,
propozycje do eksperymentalnego sprawdzenia oraz ograniczenia interpretacji.
Na prośbę użytkownika rozszerzono przegląd o nowsze rozwiązania z lat 2024–2026:
SBC/MatID, porównanie metod odkrywania lokalnych środowisk Ulugöl i in.,
reprezentacje łączące położenie i orientację molekuł oraz segmentację STM
Koleva i in. Uwzględniono też adaptacyjne sąsiedztwo mSANN i ograniczenia
rozpoznawania molekuł przez UniMR. Zaktualizowano propozycję porównania metod;
przeniesienie wyników z modeli atomowych i koloidów na molekuły STM pozostaje
hipotezą do sprawdzenia.
Dodano odnośnik w README. Zgodnie ze zleceniem mapa i tickety powstaną później;
nie ma jeszcze decyzji o metodzie ani implementacji nowych funkcji.

## Commit

Pierwszy przegląd zapisano w `a5d6601`. Bieżące przekazanie rozszerza go commitem
dokumentacji na `domains/start`, obejmującym notatkę, README i niniejszy plik.
Identyfikator nowego commita znajduje się w końcowej wiadomości sesji.

## Wykonane sprawdzenia

- Odczyt kontraktów, ustawień i integracji Domain Analysis w MolTrack.
- Przegląd oryginalnych publikacji oraz dokumentacji i kodu autorów metod.
- Kontrola lokalnych odnośników dokumentacji i `git diff --check`.

## Ograniczenia i dalszy odbiór

Nie uruchamiano algorytmów, testów aplikacji ani GUI. Lokalne `.venv` ma PyQt6,
ale brakuje m.in. NumPy, SciPy i pytest. Nie przeprowadzono oceny skuteczności
żadnej proponowanej metody na danych użytkownika. Notatka opisuje potrzebne
wejścia, parametry, przygotowanie referencji oraz mierzalne kryteria takiej oceny.

Nie ma obecnie zmian wspólnych modułów do scalenia ani nowych wymagań wobec
sesji integracyjnej. Ewentualne wydzielenie kodu MolTrack lub rozszerzenie
zależności wymaga ustalenia zakresu po eksperymencie i przygotowaniu mapy.
