"""Exercise real Qt destruction; pytest's shared QApplication would hide it."""

from pathlib import Path
import resource
import sys
from threading import Event, Timer

import numpy as np
from PyQt6.QtCore import QThreadPool, QTimer
from PyQt6.QtWidgets import QApplication

from stmdomains.io.moltrack_import import prepare_import
from stmdomains.ui.main_window import STMDomainsMainWindow


def main() -> int:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    session, work, exit_method = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    app = QApplication([])
    window = STMDomainsMainWindow()
    window.show()
    entered, release = Event(), Event()
    closed = []
    late_frames = []
    window.controller.frame_changed.connect(lambda frame: late_frames.append(frame) if closed else None)

    if work == "import":
        read_text = Path.read_text

        def delayed_read(path, *args, **kwargs):
            if path == session:
                entered.set()
                assert release.wait(5), "read not released"
            return read_text(path, *args, **kwargs)

        Path.read_text = delayed_read
        window.controller.open_session(session)
    else:
        series = prepare_import(session).series
        percentile = np.percentile

        def delayed_percentile(*args, **kwargs):
            entered.set()
            assert release.wait(5), "thumbnail calculation not released"
            return percentile(*args, **kwargs)

        np.percentile = delayed_percentile
        window.filmstrip.set_series(series)
        window.filmstrip.set_current_index(0)

    poll = QTimer()

    def close_when_working():
        if entered.is_set():
            poll.stop()
            closed.append(True)
            # Completion must not need the GUI event loop during shutdown.
            Timer(0.2, release.set).start()
            if exit_method == "window":
                window.close()
            else:
                app.quit()

    poll.timeout.connect(close_when_working)
    poll.start(5)
    QTimer.singleShot(3000, app.quit)
    result = app.exec()
    assert closed, "application exited without exercising active work"
    assert all(pool.activeThreadCount() == 0 for pool in app.findChildren(QThreadPool)), (
        "Qt teardown started while background work was still active"
    )
    assert not late_frames
    return result


if __name__ == "__main__":
    raise SystemExit(main())
