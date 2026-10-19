import os
from qgis.PyQt.QtGui import QIcon
try:  # Qt6 / QGIS 4
    from qgis.PyQt.QtGui import QAction
except ImportError:  # Qt5 / QGIS 3
    from qgis.PyQt.QtWidgets import QAction

from .dialog import EditorDialog

MENU = "&GeoMDB - Metadata Editor"
ICON_PATH = os.path.join(os.path.dirname(__file__), "icon.png")


class MetadataEditorPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dlg = None

    def initGui(self):
        self.action = QAction(QIcon(ICON_PATH), "GeoMDB - Metadata Editor", self.iface.mainWindow())
        self.action.setToolTip("GeoMDB - Metadata Editor (ISO 19115-3 / ISO 19139)")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(MENU, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu(MENU, self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        if self.dlg is None:
            self.dlg = EditorDialog(self.iface, self.iface.mainWindow())
        self.dlg.show()
        self.dlg.raise_()
