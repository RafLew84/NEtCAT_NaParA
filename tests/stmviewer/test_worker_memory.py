"""Memory reporting must preserve native handles and never truncate SIZE_T counters."""
import ctypes
import math
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from stmviewer import roma_worker


class WorkerMemoryTests(unittest.TestCase):
    def test_native_peak_memory_query_succeeds(self):
        # On Win64 this exercises the actual (HANDLE)-1 argument conversion.
        value = roma_worker._peak_rss_mib()
        self.assertTrue(math.isfinite(value))
        self.assertGreater(value, 0.)

    def test_windows_api_failure_preserves_nonfatal_zero_sentinel(self):
        kernel = SimpleNamespace(GetCurrentProcess=Mock(return_value=ctypes.c_void_p(-1).value))
        psapi = SimpleNamespace(GetProcessMemoryInfo=Mock(return_value=0))
        with patch.object(roma_worker, 'sys', SimpleNamespace(platform='win32')):
            with patch.object(ctypes, 'WinDLL', create=True, side_effect=[kernel, psapi]):
                self.assertEqual(roma_worker._peak_rss_mib(), 0.)

    def test_windows_counter_above_four_gib_is_not_truncated(self):
        kernel = SimpleNamespace(GetCurrentProcess=Mock(return_value=ctypes.c_void_p(-1).value))
        def fill_counter(handle, pointer, size):
            pointer._obj.PeakWorkingSetSize = 6 * 2**30
            return 1
        psapi = SimpleNamespace(GetProcessMemoryInfo=Mock(side_effect=fill_counter))
        with patch.object(roma_worker, 'sys', SimpleNamespace(platform='win32')):
            with patch.object(ctypes, 'WinDLL', create=True, side_effect=[kernel, psapi]):
                self.assertEqual(roma_worker._peak_rss_mib(), 6144.)


if __name__ == '__main__':
    unittest.main()
