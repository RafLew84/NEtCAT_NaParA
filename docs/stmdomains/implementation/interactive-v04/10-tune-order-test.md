# 10: Reguluj test porządku z prawidłową kalibracją

**ID:** SD-V4-10

**What to build:** Użytkownik zmienia wymagania lokalnego porządku, przelicza ocenę i ogląda wpływ na domeny przy zachowanym słowniku klas.

**Blocked by:** [05: Oblicz domeny na bieżącej klatce](05-analyze-current-frame.md).

**Status:** draft — podział oczekuje na zatwierdzenie użytkownika.

Obowiązują [wspólne kryteria odbioru](README.md#wspólne-kryteria-odbioru).

## Kryteria akceptacji

- [ ] UI udostępnia kwantyl kontroli, minimum punktów lokalnych i efektywnych oraz promień i sigma otoczenia. Wartości faktycznie trafiają do obliczeń.
- [ ] Zmiana ustawień unieważnia tylko zależne wyniki i odpowiednio przelicza kalibrację na kontrolach. Stare progi nie są bezwarunkowo stosowane do innego okna.
- [ ] Słownik pozostaje zamrożony w tym trybie. Jeśli użytkownik później odkrywa klasy ponownie, aktualna ocena porządku wpływa na zakres próbek zgodnie z zapisaną konfiguracją.
- [ ] UI pokazuje przyczynę odmowy i parametry użyte w wyniku; kwantyl nie jest opisywany jako pewność poprawności domeny.
- [ ] Kalibracja i analiza działają w tle, z anulowaniem i zachowaniem wcześniejszego poprawnego wyniku.
- [ ] Testy obejmują zależności cache/kalibracji, słabe wsparcie, kontrolę regularną i losową. Rzędy pozostają jawnie przypadkiem metody v0.4, bez zmiany definicji sieci 2D.
- [ ] Działającą funkcję sprawdzono automatycznie i ręcznie zgodnie z zakresem; przekazanie rozróżnia wykonane sprawdzenia od niewykonanych.
- [ ] Sprawdzono długość nowego i zmienianego kodu oraz testów według wspólnej zasady 1000/1500 linii.

## Test ręczny użytkownika

1. Z zachowanym modelem K5 przelicz kwantyl 0,95 i 0,925; porównaj wynik i powody odmowy.
2. Zmień parę promień/sigma z 36/16 na 30/13; UI pokazuje etap nowej oceny/kalibracji i właściwe ustawienia wyniku.
3. Anuluj przeliczenie, potem wróć do ustawień bazowych. Sprawdź dostarczone przykłady regularnego i losowego układu bez utożsamiania braku wyniku z brakiem materiału.

## Granice zadania

Złagodzenie testu nie jest samo w sobie poprawą naukowej jakości. Kontrola przyjętych i odrzuconych przypadków jest częścią odbioru.
