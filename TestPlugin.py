import nanome
from nanome.util.enums import NotificationTypes
from nanome.util import async_callback
from nanome.api.structure import Complex, Workspace


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

    # @async_callback
    # async def on_run(self):
    #     shallow = await self.request_complex_list()
    #     index = shallow[0].index

    #     deep = await self.request_complexes([index])
    #     complex = deep[0]
    #     complex.position.x += 1

    #     await self.update_structures_deep([complex])
    #     Logs.message('done')


nanome.Plugin.setup(NAME, DESCRIPTION, CATEGORY, False, ChemInteractionsTestPlugin)
