import asyncio
import os
import tempfile
import unittest

import nanome
from nanome.api.structure import Complex, Workspace
from nanome.util.enums import NotificationTypes
from nanome.util import async_callback

from chem_interactions.ChemicalInteractions import ChemicalInteractionsPlugin
from chem_interactions.forms import line_settings
from chem_interactions.utils import extract_ligands


NAME = "Integration Tests"
DESCRIPTION = "Integration Tests for ChemInteractions Plugin."
CATEGORY = "testing"
HAS_ADVANCED_OPTIONS = False


class ChemInteractionsTestCase(unittest.TestCase):
    """Integration Tests for the Chemical Interactions Plugin."""

    def __init__(self, testName, plugin=None):
        super().__init__(testName)
        self.plugin = plugin

    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        self.loop.create_task(self.clear_workspace())

    def test_tests_being_loaded(self):
        self.assertEqual(1, 1)

    def test_calculate_interactions_1tyl(self):
        # Collect data to populate calculate_interactions method.
        self.loop.run_until_complete(self.calculate_interactions_1tyl(self.plugin))

    async def calculate_interactions_1tyl(self, plugin):
        await self.setup_1tyl_workspace()
        complex_list = await self.plugin.request_complex_list()
        comp = (await self.plugin.request_complexes([complex_list[0].index]))[0]
        ligand = None
        tmp = tempfile.NamedTemporaryFile()
        comp.io.to_pdb(path=tmp.name)
        ligand = extract_ligands(tmp)[0]

        interaction_data = line_settings
        await self.plugin.calculate_interactions(comp, comp, interaction_data, ligand)

        expected_line_count = 28
        line_count = len(self.plugin._interaction_lines)
        try:
            assert line_count == expected_line_count
        except AssertionError:
            self.send_notification(NotificationTypes.error, f"Assertion Failed, {line_count} != {expected_line_count}")
        else:
            self.send_notification(NotificationTypes.success, 'Tests Completed Successfully!')

    async def setup_1tyl_workspace(self):
        filepath = '1tyl.pdb'
        comp = Complex.io.from_pdb(path=filepath)
        workspace = Workspace()
        workspace.add_complex(comp)
        self.plugin.update_workspace(workspace)

    async def clear_workspace(self):
        workspace = Workspace()
        self.plugin.update_workspace(workspace)


class IntegrationTestPlugin(nanome.AsyncPluginInstance):
    """Run TestCases for ChemicalInteractionsPlugin."""

    plugin_class = ChemicalInteractionsPlugin

    @async_callback
    async def on_run(self):
        # Create new plugin instance, and connect it to ChemInteractions PluginInstance
        os.environ["INTERACTIONS_URL"] = 'http://127.0.0.1:8000'

        plugin_instance = self.plugin_class()
        plugin_instance._network = self._network

        suite = unittest.TestSuite()
        suite.addTest(ChemInteractionsTestCase('test_calculate_interactions_1tyl', plugin_instance))
        unittest.TextTestRunner(verbosity=2).run(suite)
        # add tests to the test suite
        # suite.addTest(ChemInteractionsTestCase(plugin_instance))
        # runner = unittest.TextTestRunner(verbosity=3)
        # runner.run(suite)


nanome.Plugin.setup(NAME, DESCRIPTION, CATEGORY, False, IntegrationTestPlugin)
