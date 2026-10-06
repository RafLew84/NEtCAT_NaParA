# NanoTrack — nawigacja

- **Rejestracja, wygląd, Play i eksport:** przed zmianą przeczytaj lokalną
  [zaakceptowaną specyfikację](../.scratch/nanotrack-registration-export/spec.md),
  jeśli jest dostępna; [mapa](../.scratch/nanotrack-registration-export/map.md)
  prowadzi do szczegółowych decyzji. Plan jest ignorowany przez Git i opisuje
  docelowe zachowanie. Gdy go brakuje, odnotuj brak i oprzyj zakres na zleceniu.
- **Modele danych:** [core/data_models.py](core/data_models.py).
- **Rejestracja:** [registration/](registration/); preprocessing: [processing/](processing/).
- **Sesje:** [persistence/session_store.py](persistence/session_store.py);
  wczytywanie obrazów: [io/](io/).
- **GUI:** [ui/main_window.py](ui/main_window.py), [widgety](ui/widgets/)
  i [dialogi](ui/dialogs/).
- **Wspólny viewer:** [ViewerWidget](../napara/gui/widgets/viewer_widget.py)
  obsługuje NanoTrack, MolTrack i NaParA. Przy jego zmianie uwzględnij wszystkich
  odbiorców i wykonaj kontrole opisane w instrukcji rozwoju.
- **Uruchamianie i sprawdzanie:** [DEVELOPMENT.md](../docs/nanotrack/DEVELOPMENT.md)
  zawiera komendy startu, testów, kontroli viewera i walidacji lokalnego planu.
