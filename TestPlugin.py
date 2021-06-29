import os
import tempfile
# import time
# import unittest

import nanome
from nanome.api import Plugin
from nanome.api.structure import Complex, Workspace
from nanome.util.enums import NotificationTypes
from nanome.util import async_callback

from chem_interactions.ChemicalInteractions import ChemicalInteractions
from chem_interactions.forms import line_settings
from chem_interactions.utils import extract_ligands


NAME = "Chem Tests"
DESCRIPTION = "Tests ChemInteractions Plugin."
CATEGORY = "testing"
HAS_ADVANCED_OPTIONS = False


class ChemInteractionsTestPlugin(nanome.AsyncPluginInstance):
    """Run key aspects of the ChemInteractions Plugin"""

    @async_callback
    async def start(self):
        # Load Test Molecule into Workspace.
        response = await self.setup_workspace()
        if not response:
            self.send_notification(NotificationTypes.error, 'response is None')
        else:
            self.send_notification(NotificationTypes.success, 'Test Pass')

    async def setup_workspace(self):
        filepath = '1tyl.pdb'
        comp = None
        with open(filepath, 'r') as f:
            comp = Complex.io.from_pdb(file=f)

        workspace = Workspace()
        workspace.add_complex(comp)
        workspace = await self.update_workspace(workspace)
        print(workspace)
        return workspace

    @async_callback
    async def on_run(self):
        # Create new plugin instance, and connect it to ChemInteractions PluginInstance
        os.environ["INTERACTIONS_URL"] = 'http://127.0.0.1:8000'
        plugin = Plugin('temp', 'Integration Test', [], False)
        plugin.set_plugin_class(ChemicalInteractions)

        new_plugin = ChemicalInteractions()
        new_plugin._network = self._network

        complex_list = await self.request_complex_list()
        comp = (await self.request_complexes([complex_list[0].index]))[0]

        ligand = None
        tmp = tempfile.NamedTemporaryFile()
        comp.io.to_pdb(path=tmp.name)
        ligand = extract_ligands(tmp)[0]

        interaction_data = line_settings

        await new_plugin.calculate_interactions(comp, comp, interaction_data, ligand)
        expected_line_count = 28
        line_count = len(new_plugin._interaction_lines)
        try:
            assert line_count == expected_line_count
        except AssertionError:
            self.send_notification(NotificationTypes.error, f"Assertion Failed, {line_count} != {expected_line_count}")
        else:
            self.send_notification(NotificationTypes.success, 'Tests Completed Successfully!')
        pass


nanome.Plugin.setup(NAME, DESCRIPTION, CATEGORY, False, ChemInteractionsTestPlugin)
