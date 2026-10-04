"""
Tests for Plugin System v2: Lifecycle, Error Isolation, and Health Checks.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from plugin_system.base import Plugin, PluginManifest, PluginStatus
from plugin_system.manager import PluginManager


class SampleWorkingPlugin(Plugin):
    name = "SampleWorking"
    version = "1.0"

    def __init__(self, editor):
        super().__init__(editor)
        self.enabled = False
        self.events_received = []

    def on_enable(self):
        self.enabled = True

    def on_event(self, event_type, data=None):
        self.events_received.append((event_type, data))


class FaultyPlugin(Plugin):
    name = "Faulty"
    version = "1.0"

    def on_event(self, event_type, data=None):
        raise RuntimeError("Simulated crash in plugin!")


class TestPluginSystemV2(unittest.TestCase):
    def test_plugin_lifecycle_and_events(self):
        manager = PluginManager(editor=None)
        plugin = manager.register(SampleWorkingPlugin)

        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.status, PluginStatus.ACTIVE)
        self.assertTrue(plugin.enabled)

        manager.notify("custom_event", {"val": 42})
        self.assertEqual(len(plugin.events_received), 1)
        self.assertEqual(plugin.events_received[0], ("custom_event", {"val": 42}))

    def test_error_isolation_and_auto_disable(self):
        manager = PluginManager(editor=None, max_errors_before_disable=2)
        working_plugin = manager.register(SampleWorkingPlugin)
        faulty_plugin = manager.register(FaultyPlugin)

        # Dispatching event should NOT crash the manager, and working plugin should receive it
        manager.notify("test_step_1", None)
        self.assertEqual(len(working_plugin.events_received), 1)
        self.assertEqual(faulty_plugin.error_count, 1)
        self.assertEqual(faulty_plugin.status, PluginStatus.ACTIVE)

        # Second error should trigger auto-disable of the faulty plugin
        manager.notify("test_step_2", None)
        self.assertEqual(len(working_plugin.events_received), 2)
        self.assertEqual(faulty_plugin.error_count, 2)
        self.assertEqual(faulty_plugin.status, PluginStatus.ERROR)

    def test_health_report(self):
        manager = PluginManager(editor=None)
        manager.register(SampleWorkingPlugin)
        report = manager.get_health_report()
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["name"], "SampleWorking")
        self.assertEqual(report[0]["status"], "active")
        self.assertEqual(report[0]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
