import os
import tempfile
# import time
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


class NanomeIntegrationTestLoader(unittest.TestLoader):
    """A test loader which allows to parse keyword arguments to the test case class."""

    def loadTestsFromTestCase(self, testCaseClass, plugin):
        """Return a suite of all test cases contained in testCaseClass"""
        if issubclass(testCaseClass, unittest.TestSuite):
            raise TypeError("Test cases should not be derived from "
                            "TestSuite. Maybe you meant to derive from "
                            "TestCase?")
        testCaseNames = self.getTestCaseNames(testCaseClass)
        if not testCaseNames and hasattr(testCaseClass, 'runTest'):
            testCaseNames = ['runTest']

        loaded_suite = unittest.TestSuite()

        testcase_instance = testCaseClass()
        for test_name in testCaseNames:
            loaded_suite.addTest(testcase_instance)
        # loaded_suite = self.suiteClass(
        #     map(testCaseClass, testCaseNames, [plugin for i in range(0, len(testCaseNames))]))
        return loaded_suite


class ChemInteractionsTestCase(unittest.TestCase):
    """Integration Tests for the Chemical Interactions Plugin."""

    @property
    def plugin(self):
        return self._plugin

    @plugin.setter
    def plugin(self, value):
        self._plugin = value

    def test_tests_being_loaded(self):
        self.assertEqual(1, 1)

    async def test_calculate_integrations_1tyl(self, plugin):
        # Collect data to populate calculate_interactions method.
        self.plugin = plugin
        self.setup_1tyl_workspace()
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
        self.update_workspace(workspace)


class IntegrationTestPlugin(nanome.AsyncPluginInstance):
    """Run TestCases for ChemicalInteractionsPlugin."""

    plugin_class = ChemicalInteractionsPlugin

    @async_callback
    async def on_run(self):
        # Create new plugin instance, and connect it to ChemInteractions PluginInstance
        os.environ["INTERACTIONS_URL"] = 'http://127.0.0.1:8000'

        plugin_instance = self.plugin_class()
        plugin_instance._network = self._network

        # loader = unittest.TestLoader()
        loader = NanomeIntegrationTestLoader()
        suite = loader.loadTestsFromTestCase(ChemInteractionsTestCase, plugin_instance)
        # add tests to the test suite
        # suite.addTest(ChemInteractionsTestCase(plugin_instance))
        runner = unittest.TextTestRunner(verbosity=3)
        runner.run(suite)
        print('DOne!')


nanome.Plugin.setup(NAME, DESCRIPTION, CATEGORY, False, IntegrationTestPlugin)
