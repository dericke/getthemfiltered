"""
---------------------------------------------------------------------------
 Get them filtered
                              -------------------
        begin                : 2019-09-01
        copyright            : Pedro Camargo
        email                : c@margo.co

"""
import os
import sys
from ast import literal_eval
from typing import Optional, Union

import qgis
from qgis.core import QgsMapLayer, QgsProject
from qgis.PyQt import QtCore, QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal

sys.modules["qgsfieldcombobox"] = qgis.gui
sys.modules["qgsmaplayercombobox"] = qgis.gui

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "forms/ui_filter.ui")
)


class GetThemFilteredDialog(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()
    plugin_id = "get_em_filtered"

    def __init__(self, iface, parent=None):
        QtWidgets.QDockWidget.__init__(self, None, QtCore.Qt.WindowStaysOnTopHint)

        self.setupUi(self)
        self.iface = iface

        self.rdo_single.toggled.connect(self.single_or_multi)
        # self.rdo_multi.toggled.connect(self.single_or_multi)

        self.cob_layer.layerChanged.connect(self.add_fields_to_cboxes)

        self.cob_field.fieldChanged.connect(self.changed_field)

        self.list_values.itemSelectionChanged.connect(self.selected_value)
        self.chb_zoom.toggled.connect(self.do_zooming)

        self.but_deselect_all.clicked.connect(self.deselect_all)
        self.but_select_all.clicked.connect(self.select_all)

        # Extra attributes
        self.layer = None
        self.field = None
        self.load_saved_filter()

        self.add_fields_to_cboxes()

    @staticmethod
    def load_from_subset_string(
        subset_string: str,
    ) -> Union[tuple[str, list], tuple[None, None]]:
        """
        Attempt to convert an existing subset string to this tool's settings
        """
        #  "Jurisdiction" = 'Ashford' OR "Jurisdiction" = 'Ansonia'
        split_selectors = subset_string.split(" OR ")
        values = set()
        for count, item in enumerate(split_selectors):
            new_field, separator, value = item.partition(" = ")
            new_field = literal_eval(new_field)
            if count == 0:
                field = new_field
            elif new_field != field:
                # If this plugin created the saved filter, there should only be one value for field
                return None, None
            value = literal_eval(value)
            values.add(value)
        return field, values

    def load_saved_filter(self) -> None:
        """
        Loads any saved filters from the project file
        """
        self.layer = self.layer_saved
        if self.layer:
            field, values = self.load_from_subset_string(self.layer.subsetString())
            if field and values:
                self.field = field
            elif loaded_field := self.field_saved:
                self.field = loaded_field
        if self.filtering_saved:
            self.chb_go.setChecked(True)
        if self.zoom_saved:
            self.chb_zoom.setChecked(True)
        if self.single_saved:
            self.rdo_single.setChecked(True)

    @property
    def layer_saved(self) -> Optional[QgsMapLayer]:
        proj = QgsProject.instance()
        layer_id, type_conversion_ok = proj.readEntry(
            self.plugin_id,
            "layer",
        )
        return proj.mapLayer(layer_id)

    @layer_saved.setter
    def layer_saved(self, layer: QgsMapLayer) -> None:
        QgsProject.instance().writeEntry(
            self.plugin_id,
            "layer",
            layer.id(),
        )

    @property
    def field_saved(self) -> str:
        loaded_field, type_conversion_ok = QgsProject.instance().readEntry(
            self.plugin_id,
            "field",
            "",
        )
        return loaded_field

    @field_saved.setter
    def field_saved(self, field: str) -> None:
        QgsProject.instance().writeEntry(
            self.plugin_id,
            "field",
            field,
        )

    @property
    def filtering_saved(self) -> bool:
        filtering_enabled, type_conversion_ok = QgsProject.instance().readBoolEntry(
            self.plugin_id, "filtering_enabled"
        )
        return filtering_enabled

    @filtering_saved.setter
    def filtering_saved(self, value: bool) -> None:
        QgsProject.instance().writeEntryBool(
            self.plugin_id,
            "filtering_enabled",
            value,
        )

    @property
    def zoom_saved(self) -> bool:
        zoom_enabled, type_conversion_ok = QgsProject.instance().readBoolEntry(
            self.plugin_id, "zoom_to_results"
        )
        return zoom_enabled

    @zoom_saved.setter
    def zoom_saved(self, value: bool) -> None:
        QgsProject.instance().writeEntryBool(
            self.plugin_id,
            "zoom_to_results",
            value,
        )

    @property
    def single_saved(self) -> bool:
        single_enabled, type_conversion_ok = QgsProject.instance().readBoolEntry(
            self.plugin_id, "single_select"
        )
        return single_enabled

    @single_saved.setter
    def single_saved(self, value: bool) -> None:
        QgsProject.instance().writeEntryBool(
            self.plugin_id,
            "single_select",
            value,
        )

    def save_filter(self) -> None:
        """
        Saves the current filter settings to the project file
        """
        self.layer_saved = self.layer
        self.field_saved = self.field
        self.filtering_saved = self.chb_go.isChecked()
        self.zoom_saved = self.chb_zoom.isChecked()
        self.single_saved = self.rdo_single.isChecked()

    def check_layer(self) -> bool:
        if self.layer is None:
            self.list_values.clear()
            return False
        if self.layer not in QgsProject.instance().mapLayers().values():
            self.list_values.clear()
            return False
        return isinstance(self.layer, qgis.core.QgsVectorLayer)

    def single_or_multi(self) -> None:
        if self.rdo_single.isChecked():
            self.deselect_all()
            self.list_values.setSelectionMode(
                QtWidgets.QAbstractItemView.SingleSelection
            )
        else:
            self.list_values.setSelectionMode(
                QtWidgets.QAbstractItemView.MultiSelection
            )

    def add_fields_to_cboxes(self) -> None:
        self.reset_filter()
        self.layer = self.cob_layer.currentLayer()
        self.field = None
        if self.check_layer():
            self.cob_field.setLayer(self.layer)
            self.changed_field()
        elif not isinstance(self.layer, qgis.core.QgsVectorLayer):
            self.layer = None

    def changed_field(self) -> None:
        self.reset_filter()
        self.field = self.cob_field.currentField()
        self.do_filtering()

    def reset_filter(self) -> None:
        if self.check_layer():
            self.layer.setSubsetString("")

    def do_filtering(self) -> None:
        if not self.check_layer():
            return
        table = self.list_values
        table.clear()

        idx = self.layer.dataProvider().fieldNameIndex(self.field)
        values = sorted(str(value) for value in self.layer.uniqueValues(idx))
        table.addItems(values)
        self.select_all()

    def do_zooming(self) -> None:
        if self.chb_zoom.isChecked():
            self.iface.setActiveLayer(self.layer)
            self.iface.zoomToActiveLayer()

    def selected_value(self) -> None:
        if self.chb_go.isChecked():
            if l := [i.text() for i in self.list_values.selectedItems()]:
                self.apply_filter(l)

    def apply_filter(self, list_of_values) -> None:
        if not self.check_layer():
            return

        filter_expression = " OR ".join(
            f"\"{self.field}\" = '{value}'" for value in list_of_values
        )
        self.layer.setSubsetString(filter_expression)

        self.do_zooming()

    def deselect_all(self) -> None:
        self.list_values.clearSelection()

    def select_all(self) -> None:
        self.list_values.selectAll()

    def closeEvent(self, event) -> None:
        self.save_filter()
        self.closingPlugin.emit()
        event.accept()
