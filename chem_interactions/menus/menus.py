import tempfile
from os import environ, path
from utils.complex_utils import ComplexUtils
from Bio.PDB.Residue import Residue as BioResidue

import nanome
from utils import extract_ligands
from nanome.api.structure import Complex
from nanome.api.ui import Dropdown, DropdownItem, Button, Label
from nanome.util.asyncio import async_callback
from .forms import InteractionsForm, color_map

PDBOPTIONS = Complex.io.PDBSaveOptions()
PDBOPTIONS.write_bonds = True

BASE_PATH = path.dirname(f'{path.realpath(__file__)}')
MENU_PATH = path.join(BASE_PATH, 'json', 'menu.json')


class ChemInteractionsMenu():

    def __init__(self, plugin):
        self.plugin = plugin
        self.interactions_url = environ.get('INTERACTIONS_URL')
        self._menu = nanome.ui.Menu.io.from_json(MENU_PATH)

        self.ls_complexes = self._menu.root.find_node('Complex List').get_content()
        self.ls_ligands = self._menu.root.find_node('Ligands List').get_content()
        self.ls_interactions = self._menu.root.find_node('Interaction Settings List').get_content()
        self.btn_calculate = self._menu.root.find_node('Button').get_content()
        self.btn_calculate.register_pressed_callback(self.submit_form)

        self.btn_toggle_interactions = self._menu.root.find_node('ln_btn_toggle_interactions').get_content()
        self.btn_toggle_interactions.register_pressed_callback(self.toggle_all_interactions)
        self.complex_indices = set()

    @async_callback
    async def render(self, complexes=None):
        complexes = complexes or []
        self.complexes = complexes

        for comp in self.complexes:
            comp.register_complex_updated_callback(self.on_complex_updated) 

        self.render_interaction_form()
        self.display_structures(complexes, self.ls_complexes)
        self.display_structures(complexes, self.ls_ligands)

        for ln_btn in self.ls_complexes.items:
            btn = ln_btn.get_content()
            btn.register_pressed_callback(self.toggle_complex)

        for ln_btn in self.ls_ligands.items:
            btn = ln_btn.get_content()
            btn.register_pressed_callback(self.toggle_ligand)

        self.plugin.update_menu(self._menu)

    def display_structures(self, complexes, ui_list):
        btns = self.create_structure_btns(complexes)
        ui_list.items = btns
        self.plugin.update_content(ui_list)

    def create_structure_btns(self, structures):
        """Generate list of buttons corresponding to provided complexes."""
        complex_btns = []
        btn_labels = []

        for struct in structures:
            struct_name = ''
            if isinstance(struct, Complex):
                struct_name = struct.name
            elif isinstance(struct, BioResidue):
                struct_name = struct.resname

            if struct_name not in btn_labels:
                btn_label = struct_name
            else:
                # Find unique struct name.
                letter = 'a'
                while btn_label in btn_labels:
                    btn_label = f'{struct_name} {{{letter}}}'
                    letter = self.next_alpha(letter)
            btn_labels.append(struct_name)
            ln_btn = nanome.ui.LayoutNode()
            btn = ln_btn.add_new_button(btn_label)

            if isinstance(struct, Complex):
                btn.complex = struct
                btn.complex_index = struct.index
            elif isinstance(struct, BioResidue):
                btn.ligand = struct

            btn.ln = ln_btn
            complex_btns.append(ln_btn)
        return complex_btns

    @async_callback
    async def toggle_all_interactions(self, btn):
        btn.selected = not btn.selected
        txt_selected = 'Hide All'
        txt_unselected = 'Show all'
        btn_text = txt_selected if btn.selected else txt_unselected
        btn.text.value.set_all(btn_text)

        # Find all the interaction buttons and disable them
        selected_value = btn.selected
        for row in self.ls_interactions.items:
            content = [ch.get_content() for ch in row.get_children()]
            btn = next(c for c in content if isinstance(c, Button))
            btn.selected = selected_value
        self.plugin.update_menu(self._menu)
        await self.update_interaction_lines()

    def collect_interaction_data(self):
        """Collect Interaction data from various content widgets."""
        interaction_data = {}
        for row in self.ls_interactions.items:
            line_data = row.line_data

            content = [ch.get_content() for ch in row.get_children()]
            btn_visibility = next(c for c in content if isinstance(c, Button))
            dd_color = next(c for c in content if isinstance(c, Dropdown))
            lb_name = next(c for c in content if isinstance(c, Label))
            ddi_color = next(item for item in dd_color.items if item.selected)

            name = lb_name.field_name
            visible = True if btn_visibility.selected else False
            color = ddi_color.rgb

            interaction_data[name] = {
                **line_data,
                'visible': visible,
                'color': color,
            }
        return interaction_data

    @async_callback
    async def submit_form(self, btn):
        selected_complexes = [
            item.get_content().complex
            for item in self.ls_complexes.items
            if item.get_content().selected
        ]

        btn.unusable = True
        btn.text.value.set_all('Calculating...')
        self.plugin.update_content(btn)
        if len(selected_complexes) != 1:
            raise Exception("Too many selected complexes.")

        selected_complex = selected_complexes[0]
        selected_residue = getattr(self, 'residue', None)
        residue_complex = getattr(self, 'residue_complex', None)

        error_msg = ''
        if not selected_complexes:
            error_msg = 'Please Select a Complex'
        if selected_complexes and not (selected_residue or residue_complex):
            error_msg = 'Please Select a Ligand'
        if error_msg:
            self.plugin.send_notification(nanome.util.enums.NotificationTypes.error, error_msg)
            return

        # Get deep residue complex
        if len(list(residue_complex.molecules)) ==  0:
            residue_complex = next(iter(await self.plugin.request_complexes([residue_complex.index])))
            # Update self.complexes with deep complex
            self.update_complex_data(residue_complex)

        interaction_data = self.collect_interaction_data()
        await self.plugin.get_interactions(selected_complex, residue_complex, interaction_data, self.residue)
        
        btn.unusable = False
        btn.text.value.set_all('Calculate')
        self.plugin.update_content(btn)

    def color_dropdown(self):
        dropdown_items = []
        for name, color_rgb in color_map.items():
            color_hex = '#%02x%02x%02x' % color_rgb
            colored_name = f'<mark={color_hex}>    </mark> {name}'
            dd_item = DropdownItem(colored_name)
            dd_item.rgb = color_rgb
            dropdown_items.append(dd_item)
        dropdown = Dropdown()
        dropdown.max_displayed_items = 12
        dropdown.items = dropdown_items
        return dropdown

    def render_interaction_form(self):
        """Populate the interaction type form."""
        form = InteractionsForm()
        interactions = []
        self.ls_interactions.display_rows = 7
        for name, field in form._fields.items():
            ln = nanome.ui.LayoutNode()
            ln.sizing_type = ln.SizingTypes.ratio.value
            ln.layout_orientation = nanome.ui.LayoutNode.LayoutTypes.horizontal.value

            list_item_ln = nanome.ui.LayoutNode()
            ln_btn = list_item_ln.clone()
            ln_btn.set_padding(left=0.01)
            ln_btn.add_new_button("")
            ln_btn.set_size_ratio(0.07)
            ln_btn.toggle_on_press = True

            btn = ln_btn.get_content()
            btn.mesh.active = True
            btn.mesh.enabled.set_all(False)
            btn.mesh.enabled.set_each(selected=True)
            btn.mesh.color.set_each(selected=btn.outline.color.selected)
            ln.line_data = field.default
            is_visible = field.default.get('visible', True)
            btn.selected = is_visible
            btn.register_pressed_callback(self.toggle_visibility)

            ln_label = list_item_ln.clone()
            ln_label.add_new_label(field.label.text)
            ln_label.get_content().field_name = name
            ln_label.set_padding(left=0.03)
            ln_label.set_size_ratio(0.5)

            ln_dropdown = list_item_ln.clone()
            dropdown = self.color_dropdown()
            dropdown.register_item_clicked_callback(self.change_interaction_color)
            ln_dropdown.set_content(dropdown)
            ln_dropdown.set_size_ratio(0.4)
            ln_dropdown.forward_dist = .001

            # Select default color in dropdown
            if field.default and field.default.get('color'):
                default_rgb = field.default['color']
                selected_item = next(iter(
                    ddi for ddi in dropdown.items
                    if ddi.rgb == default_rgb
                ), None)
                selected_item.selected = True

            ln.add_child(ln_btn)
            ln.add_child(ln_label)
            ln.add_child(ln_dropdown)
            interactions.append(ln)
        self.ls_interactions.items = interactions
        self.plugin.update_content(self.ls_interactions)

    def change_interaction_color(self, dropdown, item):
        self.update_interaction_lines()

    @async_callback
    async def toggle_visibility(self, btn):
        btn.selected = not btn.selected
        self.plugin.update_content(btn)
        await self.update_interaction_lines()

    @async_callback
    async def update_interaction_lines(self):
        interaction_data = self.collect_interaction_data()
        await self.plugin.update_interaction_lines(interaction_data, self.complexes)

    @property
    def index(self):
        return self._menu.index

    @index.setter
    def index(self, value):
        self._menu.index = value

    @property
    def enabled(self):
        return self._menu.enabled

    @enabled.setter
    def enabled(self, value):
        self._menu.enabled = value

    @staticmethod
    def next_alpha(s):
        """return next letter alphabetically."""
        return chr((ord(s.upper()) + 1 - 65) % 26 + 65).lower()

    @async_callback
    async def toggle_complex(self, btn):
        # toggle the complex
        btn.selected = not btn.selected
        # deselect everything else
        for item in (set(self.ls_complexes.items) - {btn.ln}):
            item.get_content().selected = False
        self.plugin.update_content(self.ls_complexes)

        # Reset ligands list to default if nothing is selected
        ligand_btns = []
        if btn.selected:
            # Pull out ligands from complex and add them to ligands list
            self.btn_calculate.unusable = True
            self.btn_calculate.text.value.set_all('Extracting Ligands...')
            self.plugin.update_content(self.btn_calculate)
            ligand_btns = self.create_structure_btns(self.complexes)
            comp = btn.complex
            deep_complex = next(iter(await self.plugin.request_complexes([comp.index])))
            self.update_complex_data(deep_complex)
            btn.complex = deep_complex

            # Remove selected complex from ligands list
            for ln in ligand_btns:
                if ln.get_content().complex.index == comp.index:
                    ligand_btns.remove(ln)

            # Find ligands nested inside of complex, and add buttons for them.
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdb')
            deep_complex.io.to_pdb(temp_file.name, PDBOPTIONS)
            ligands = extract_ligands(temp_file)
            new_ligand_btns = self.create_structure_btns(ligands)
            for ln_btn in new_ligand_btns:
                lig_btn = ln_btn.get_content()
                lig_btn.complex = deep_complex
            ligand_btns.extend(new_ligand_btns)
        else:
            ligand_btns = self.create_structure_btns(self.complexes)

        for ln in ligand_btns:
            ln.get_content().register_pressed_callback(self.toggle_ligand)

        self.ls_ligands.items = ligand_btns
        self.btn_calculate.unusable = False
        self.btn_calculate.text.value.set_all('Calculate')
        self.plugin.update_content(self.btn_calculate)
        self.plugin.update_content(self.ls_ligands)

    def toggle_ligand(self, btn_ligand):
        # toggle button
        btn_ligand.selected = not btn_ligand.selected

        # deselect everything else
        for ln in set(self.ls_ligands.items) - {btn_ligand.ln}:
            ln.get_content().selected = False

        # Add residue data to button
        if btn_ligand.selected:
            self.residue = getattr(btn_ligand, 'ligand', None)
            self.residue_complex = btn_ligand.complex
        else:
            self.residue = ''

        # update ui
        self.plugin.update_content(self.ls_ligands)

    def on_complex_updated(self, complex):
        # Update complex in self.complexes, and redraw lines
        self.update_complex_data(complex)
        self.update_interaction_lines()

    def update_complex_data(self, new_complex):
        """Replace complex self.complexes with updated data."""
        for i, comp in enumerate(self.complexes):
            if comp.index == new_complex.index:
                self.complexes[i] = new_complex
                self.complexes[i].register_complex_updated_callback(self.on_complex_updated)
                return