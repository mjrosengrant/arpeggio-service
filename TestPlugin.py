import asyncio
import os
import tempfile
import unittest

import nanome
# from nanome._internal._plugin import _Plugin
# from nanome._internal._process import _ProcessManager, _LogsManager
from nanome.api import Plugin
from nanome.api.structure import Complex, Workspace
from nanome.util import async_callback, Logs
from nanome.util.enums import NotificationTypes
from chem_interactions.ChemicalInteractions import ChemicalInteractionsPlugin
from chem_interactions.forms import default_line_settings
from chem_interactions.utils import extract_ligands


NAME = "Integration Tests"
DESCRIPTION = "Integration Tests for ChemInteractions Plugin."
CATEGORY = "testing"
HAS_ADVANCED_OPTIONS = False


class ChemInteractionsTestCase(unittest.TestCase):
    """Integration Tests for the Chemical Interactions Plugin."""

    plugin_class = ChemicalInteractionsPlugin

    def __init__(self, plugin_instance):
        super().__init__()
        self.plugin_instance = plugin_instance

    @classmethod
    def setUpClass(cls):
        # cls.loop = asyncio.get_event_loop()
        # cls.plugin_instance = cls.plugin_class()
        cls.loop = asyncio.get_event_loop()

        # Instantiate plugin to get Network connection, and add to plugin instance
        name = "ChemInterIntegrationTests"
        description = 'Integration Tests'
        plugin = Plugin(name, description, [], False, [], [])
        plugin.set_plugin_class(cls.plugin_class)
        host = os.environ['NTS_HOST']
        port = os.environ['NTS_PORT']
        plugin.__host = host
        plugin.__port = port
        plugin.__run()
        # plugin._process_manager = _ProcessManager()
        # plugin._logs_manager = _LogsManager(cls.plugin_class.__name__ + ".log")
        # plugin.__connect()

    @classmethod
    def tearDownClass(cls):
        cls.loop.create_task(cls.clear_workspace())
        pass

    def test_tests_being_loaded(self):
        self.assertEqual(1, 1)

    @classmethod
    async def clear_workspace(cls):
        workspace = Workspace()
        cls.plugin.update_workspace(workspace)


class IntegrationTestPlugin(nanome.AsyncPluginInstance):
    """Run TestCases for ChemicalInteractionsPlugin."""

    testcase_class = ChemInteractionsTestCase

    @async_callback
    async def on_run(self):
        self.plugin_instance = ChemicalInteractionsPlugin()
        self.plugin_instance._network = self._network
        await self.test_calculate_interactions_1tyl()

    async def setup_1tyl_workspace(self):
        filepath = '1tyl.pdb'
        comp = Complex.io.from_pdb(path=filepath)
        workspace = Workspace()
        workspace.add_complex(comp)
        self.plugin_instance.update_workspace(workspace)

    async def test_calculate_interactions_1tyl(self):
        # Collect data to populate calculate_interactions method.
        await self.setup_1tyl_workspace()
        complex_list = await self.plugin_instance.request_complex_list()
        comp = (await self.plugin_instance.request_complexes([complex_list[0].index]))[0]
        ligand = None
        tmp = tempfile.NamedTemporaryFile()
        comp.io.to_pdb(path=tmp.name)
        ligand = extract_ligands(tmp)[0]
        line_settings = default_line_settings
        await self.plugin_instance.calculate_interactions(comp, [comp], line_settings, [ligand])

        expected_line_count = 85
        line_count = len(self.plugin_instance.line_manager.all_lines())
        try:
            assert line_count == expected_line_count
        except AssertionError:
            msg = f"Assertion Failed, {line_count} != {expected_line_count}"
            self.send_notification(NotificationTypes.error, msg)
            raise AssertionError(msg)
        else:
            msg = 'Tests Completed Successfully!'
            Logs.message(msg)
            self.send_notification(NotificationTypes.success, msg)


if __name__ == "__main__":
    os.environ['INTERACTIONS_URL'] = 'http://127.0.0.1:8000'
    nanome.Plugin.setup(NAME, DESCRIPTION, CATEGORY, False, IntegrationTestPlugin)
