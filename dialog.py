import copy
import datetime
import json
import os
import re

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QListWidget,
    QStackedWidget, QScrollArea, QWidget, QFormLayout, QLabel, QComboBox,
    QPlainTextEdit, QFileDialog, QMessageBox, QSplitter, QToolButton, QMenu, QFrame,
    QCheckBox, QTabWidget, QButtonGroup, QRadioButton, QInputDialog, QListView,
    QCalendarWidget, QSizePolicy,
)
from qgis.PyQt.QtCore import Qt, QTimer, QDate, QPoint
from qgis.PyQt.QtGui import QPalette, QColor, QKeySequence, QIcon, QPixmap
try:  # Qt6 / QGIS 4
    from qgis.PyQt.QtGui import QShortcut
except ImportError:  # Qt5 / QGIS 3
    from qgis.PyQt.QtWidgets import QShortcut
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject

from . import model, layout, big_compat, gmd_exporter, gmd_importer

HERE = os.path.dirname(__file__)
ICON_PATH = os.path.join(HERE, "icon.png")
TEMPLATE = os.path.join(HERE, "template.xml")
SAMPLE = os.path.join(HERE, "contoh_lengkap.xml")
CONTACTS_FILE = os.path.join(HERE, "contacts_presets.json")
CHECK_ICON = os.path.join(HERE, "check.png").replace("\\", "/")
RADIO_ON_ICON = os.path.join(HERE, "radio_checked.png").replace("\\", "/")
RADIO_OFF_ICON = os.path.join(HERE, "radio_unchecked.png").replace("\\", "/")

TITLE = "GeoMDB - Metadata Editor"
HINT_CSS = "color:#64748b;font-size:11px;background:transparent;border:none;padding:0px;"
PLACEHOLDERS = {"DateTime": "YYYY-MM-DDThh:mm:ss", "Date": "YYYY-MM-DD", "beginPosition": "YYYY-MM-DD",
                "endPosition": "YYYY-MM-DD", "Distance": "meter", "Decimal": "angka desimal",
                "Integer": "bilangan bulat", "Real": "angka"}

DIALOG_STYLE = """
/* Base Dialog */
QDialog {
    background-color: #f8fafc;
    color: #1e293b;
    font-size: 12px;
}

QWidget {
    color: #1e293b;
    font-size: 12px;
}

/* Headings and Labels */
QLabel {
    color: #1e293b;
    background: transparent;
    border: none;
}

/* Radio buttons & Checkboxes */
QCheckBox {
    color: #1e293b;
    font-size: 12px;
    font-weight: 500;
    spacing: 8px;
    background: transparent;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    background-color: #ffffff;
    border: 1.5px solid #94a3b8;
    border-radius: 4px;
}
QCheckBox::indicator:hover {
    border-color: #0284c7;
    background-color: #f0f9ff;
}
QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #0284c7;
    image: url("__CHECK_ICON__");
}
QCheckBox::indicator:disabled {
    background-color: #f1f5f9;
    border-color: #cbd5e1;
}

QRadioButton {
    color: #1e293b;
    font-size: 12px;
    font-weight: 500;
    spacing: 8px;
    background: transparent;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    image: url("__RADIO_OFF_ICON__");
}
QRadioButton::indicator:hover {
    image: url("__RADIO_ON_ICON__");
}
QRadioButton::indicator:checked {
    image: url("__RADIO_ON_ICON__");
}

/* Text Inputs */
QLineEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 6px 8px;
    font-size: 12px;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border: 1px solid #0284c7;
    background-color: #ffffff;
}
QLineEdit:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPlainTextEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 6px 8px;
    font-size: 12px;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}
QPlainTextEdit:focus {
    border: 1px solid #0284c7;
    background-color: #ffffff;
}

/* Dropdown Comboboxes */
QComboBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 5px 10px;
    font-size: 12px;
    min-height: 22px;
}
QComboBox:focus {
    border: 1px solid #0284c7;
}
QComboBox:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}
QComboBox QAbstractItemView, QListView#comboPopup {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    selection-background-color: #e0f2fe;
    selection-color: #0369a1;
    outline: none;
    padding: 4px;
}
QComboBox QAbstractItemView::item, QListView#comboPopup::item {
    min-height: 24px;
    padding: 5px 8px;
    color: #0f172a;
    border-radius: 3px;
}
QComboBox QAbstractItemView::item:hover, QListView#comboPopup::item:hover {
    background-color: #f1f5f9;
    color: #0369a1;
}
QComboBox QAbstractItemView::item:selected, QListView#comboPopup::item:selected {
    background-color: #e0f2fe;
    color: #0369a1;
    font-weight: 600;
}

/* Standard Buttons */
QPushButton {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: 500;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
    color: #0f172a;
}
QPushButton:pressed {
    background-color: #e2e8f0;
}

QToolButton {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 5px 10px;
    font-size: 12px;
}
QToolButton:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background-color: #ffffff;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background-color: #f1f5f9;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    padding: 7px 16px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
    font-weight: 500;
    font-size: 12px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0284c7;
    font-weight: bold;
    border-bottom: 2px solid #0284c7;
}
QTabBar::tab:hover:!selected {
    background-color: #e2e8f0;
    color: #1e293b;
}

/* Right Stacked & Scroll Areas */
QStackedWidget {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
}

QScrollArea {
    background-color: #ffffff;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background-color: #ffffff;
}

/* Splitter */
QSplitter::handle {
    background-color: #f1f5f9;
}

/* ScrollBar */
QScrollBar:vertical {
    border: none;
    background: #f8fafc;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 25px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Menus */
QMenu {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 4px;
    color: #1e293b;
}
QMenu::item:selected {
    background-color: #e0f2fe;
    color: #0369a1;
}
QMenu::separator {
    height: 1px;
    background: #e2e8f0;
    margin: 4px 2px;
}

/* Tooltips */
QToolTip {
    background-color: #1e293b;
    color: #ffffff;
    border: 1px solid #334155;
    padding: 5px 8px;
    border-radius: 4px;
    font-size: 11px;
}
""".replace("__CHECK_ICON__", CHECK_ICON).replace("__RADIO_ON_ICON__", RADIO_ON_ICON).replace("__RADIO_OFF_ICON__", RADIO_OFF_ICON)


def setup_combo_styling(cb):
    view = QListView(cb)
    view.setObjectName("comboPopup")
    view.setStyleSheet("""
        QListView {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            outline: none;
            padding: 4px;
            font-size: 12px;
        }
        QListView::item {
            min-height: 24px;
            padding: 5px 8px;
            color: #0f172a;
            border-radius: 3px;
        }
        QListView::item:hover {
            background-color: #f1f5f9;
            color: #0369a1;
        }
        QListView::item:selected {
            background-color: #e0f2fe;
            color: #0369a1;
            font-weight: 600;
        }
    """)
    cb.setView(view)
    cb.setMaxVisibleItems(15)
    cb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    cb.setStyleSheet("""
        QComboBox {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 5px 10px;
            font-size: 12px;
            min-height: 22px;
        }
        QComboBox:focus {
            border: 1px solid #0284c7;
        }
        QComboBox:disabled {
            background-color: #f8fafc;
            color: #94a3b8;
            border: 1px solid #e2e8f0;
        }
    """)


class ChoiceCombo(QComboBox):
    """Dropdown berlabel (label tampil, nilai disimpan) dengan keterangan sebagai tooltip."""
    def __init__(self, options, value):
        super().__init__()
        setup_combo_styling(self)
        self.addItem("— pilih —", "")
        for lab, val, desc in options:
            self.addItem(lab, val)
            if desc:
                self.setItemData(self.count() - 1, desc, Qt.ItemDataRole.ToolTipRole)
        self.set_value(value)

    def showPopup(self):
        super().showPopup()
        win = self.view().window()
        if win:
            win.setStyleSheet("""
                QFrame, QWidget {
                    background-color: #ffffff;
                    color: #0f172a;
                }
                QListView {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    outline: none;
                    padding: 4px;
                }
                QListView::item {
                    min-height: 24px;
                    padding: 5px 8px;
                    color: #0f172a;
                    border-radius: 3px;
                }
                QListView::item:hover {
                    background-color: #f1f5f9;
                    color: #0369a1;
                }
                QListView::item:selected {
                    background-color: #e0f2fe;
                    color: #0369a1;
                    font-weight: 600;
                }
            """)
            CR = getattr(QPalette, 'ColorRole', QPalette)
            pal = win.palette()
            pal.setColor(CR.Window, QColor("#ffffff"))
            pal.setColor(CR.WindowText, QColor("#0f172a"))
            pal.setColor(CR.Base, QColor("#ffffff"))
            pal.setColor(CR.Text, QColor("#0f172a"))
            pal.setColor(CR.Button, QColor("#ffffff"))
            pal.setColor(CR.ButtonText, QColor("#0f172a"))
            win.setPalette(pal)

    def set_value(self, v):
        i = self.findData(v)
        if i < 0 and v:
            self.addItem(v, v)
            i = self.count() - 1
        self.setCurrentIndex(max(i, 0))

    def value(self):
        return self.currentData() or ""


class DatePickerWidget(QWidget):
    """Widget isian tanggal/waktu dengan tombol pemilih kalender interaktif."""
    def __init__(self, val="", is_datetime=False, parent=None):
        super().__init__(parent)
        self.is_datetime = is_datetime
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.line_edit = QLineEdit(val)
        self.line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.line_edit.setClearButtonEnabled(True)
        self.line_edit.setPlaceholderText("YYYY-MM-DD" if not is_datetime else "YYYY-MM-DDThh:mm:ss")
        self.line_edit.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #0284c7;
            }
        """)
        layout.addWidget(self.line_edit)

        self.btn_cal = QToolButton()
        self.btn_cal.setText("📅")
        self.btn_cal.setToolTip("Pilih tanggal dari kalender")
        self.btn_cal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cal.setStyleSheet("""
            QToolButton {
                background-color: #f0f9ff;
                border: 1px solid #7dd3fc;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
                color: #0284c7;
            }
            QToolButton:hover {
                background-color: #e0f2fe;
                border-color: #0284c7;
            }
            QToolButton:pressed {
                background-color: #bae6fd;
            }
        """)
        self.btn_cal.clicked.connect(self.show_calendar)
        layout.addWidget(self.btn_cal)

    def text(self):
        return self.line_edit.text()

    def setText(self, val):
        self.line_edit.setText(val)

    def value(self):
        return self.line_edit.text()

    def set_value(self, val):
        self.line_edit.setText(val)

    def setPlaceholderText(self, text):
        self.line_edit.setPlaceholderText(text)

    def setToolTip(self, text):
        super().setToolTip(text)
        self.line_edit.setToolTip(text)
        self.btn_cal.setToolTip(text)

    def show_calendar(self):
        dlg = QDialog(self, Qt.WindowType.Popup)
        dlg.setStyleSheet("QDialog { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; }")
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(8, 8, 8, 8)
        dlg_layout.setSpacing(6)

        cal = QCalendarWidget(dlg)
        cal.setGridVisible(True)
        cal.setStyleSheet("""
            QCalendarWidget {
                background-color: #ffffff;
                color: #0f172a;
            }
            QCalendarWidget QToolButton {
                color: #0f172a;
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                margin: 2px;
                padding: 3px 6px;
                font-size: 12px;
                font-weight: 500;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #e2e8f0;
            }
            QCalendarWidget QMenu {
                background-color: #ffffff;
                color: #0f172a;
            }
            QCalendarWidget QSpinBox {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
                font-size: 12px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #f8fafc;
                border-bottom: 1px solid #e2e8f0;
            }
        """)

        cur_text = self.line_edit.text().strip()
        time_part = "T00:00:00"
        if cur_text:
            d_str = cur_text.split("T")[0]
            if "T" in cur_text:
                time_part = "T" + cur_text.split("T")[1]
            qdate = QDate.fromString(d_str, "yyyy-MM-dd")
            if qdate.isValid():
                cal.setSelectedDate(qdate)

        def on_date_selected(date):
            d_str = date.toString("yyyy-MM-dd")
            if self.is_datetime:
                self.line_edit.setText(d_str + time_part)
            else:
                self.line_edit.setText(d_str)
            dlg.accept()

        cal.clicked.connect(on_date_selected)
        dlg_layout.addWidget(cal)

        btn_bar = QHBoxLayout()
        btn_today = QPushButton("Hari Ini")
        btn_today.setStyleSheet("""
            QPushButton {
                background-color: #f0fdf4;
                color: #15803d;
                border: 1px solid #86efac;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #dcfce7;
                border-color: #22c55e;
            }
        """)
        btn_today.clicked.connect(lambda: on_date_selected(QDate.currentDate()))

        btn_cancel = QPushButton("Batal")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        btn_cancel.clicked.connect(dlg.reject)

        btn_bar.addWidget(btn_today)
        btn_bar.addStretch()
        btn_bar.addWidget(btn_cancel)
        dlg_layout.addLayout(btn_bar)

        pt = self.mapToGlobal(QPoint(0, self.height()))
        dlg.move(pt)
        dlg.exec()


class EditorDialog(QDialog):
    def __init__(self, iface=None, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.root = None
        self.src = ""
        self.mode = "big"
        self.sections = []
        self.page_secs = []
        self.scrolls = []
        self.items = []          # (Field, widget)
        self.page_keys = []
        self.built_big_pages = set()
        self.setWindowTitle(TITLE)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(1150, 750)

        # Enforce high-contrast light palette regardless of QGIS / OS dark theme
        CR = getattr(QPalette, 'ColorRole', QPalette)
        pal = self.palette()
        pal.setColor(CR.Window, QColor("#f8fafc"))
        pal.setColor(CR.WindowText, QColor("#1e293b"))
        pal.setColor(CR.Base, QColor("#ffffff"))
        pal.setColor(CR.AlternateBase, QColor("#f1f5f9"))
        pal.setColor(CR.Text, QColor("#0f172a"))
        pal.setColor(CR.Button, QColor("#ffffff"))
        pal.setColor(CR.ButtonText, QColor("#1e293b"))
        pal.setColor(CR.Highlight, QColor("#0284c7"))
        pal.setColor(CR.HighlightedText, QColor("#ffffff"))
        self.setPalette(pal)

        self.setStyleSheet(DIALOG_STYLE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        if os.path.exists(ICON_PATH):
            lbl_logo = QLabel()
            pix = QPixmap(ICON_PATH)
            if not pix.isNull():
                lbl_logo.setPixmap(pix.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                lbl_logo.setStyleSheet("background: transparent; border: none; padding: 0px;")
                top.addWidget(lbl_logo)
        lbl_brand = QLabel(
            "<div style='line-height:1.15;'>"
            "<span style='font-size:13px;font-weight:800;color:#0f172a;'>GeoMDB</span><br>"
            "<span style='font-size:10px;font-weight:600;color:#0284c7;'>Metadata Editor</span>"
            "</div>"
        )
        lbl_brand.setStyleSheet("background: transparent; border: none; padding-right: 6px;")
        top.addWidget(lbl_brand)
        for text, fn, tip in (
            ("Template Kosong", lambda: self.load(TEMPLATE), "Muat struktur metadata standar BIG dengan isian kosong"),
            ("Contoh Metadata", lambda: self.load(SAMPLE), "Muat contoh metadata lengkap yang sudah divalidasi sistem BIG"),
            ("Buka XML Metadata...", self.open_file, "Buka berkas XML metadata dari penyimpanan"),
            ("Ambil Metadata dari Layer Aktif", self.fill_from_layer,
             "Ekstrak otomatis judul, batas wilayah (EPSG:4326), CRS, tipe geometri, dan jumlah fitur dari layer aktif"),
        ):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #1e293b;
                    border: 1px solid #cbd5e1;
                    border-radius: 5px;
                    padding: 6px 14px;
                    font-weight: 500;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                    border-color: #94a3b8;
                    color: #0284c7;
                }
                QPushButton:pressed {
                    background-color: #e2e8f0;
                }
            """)
            b.clicked.connect(lambda _=False, f=fn: f())
            top.addWidget(b)
        top.addStretch()
        lbl_mode = QLabel("Tampilan:")
        lbl_mode.setStyleSheet("font-weight: 600; color: #475569; background: transparent;")
        top.addWidget(lbl_mode)
        self.rb_big = QRadioButton("Form BIG")
        self.rb_all = QRadioButton("Semua elemen ISO")
        self.rb_big.setChecked(True)
        self.rb_big.setStyleSheet("color: #1e293b; font-weight: 500; background: transparent;")
        self.rb_all.setStyleSheet("color: #1e293b; font-weight: 500; background: transparent;")
        grp = QButtonGroup(self)
        for rb in (self.rb_big, self.rb_all):
            grp.addButton(rb)
            top.addWidget(rb)
            rb.toggled.connect(self.on_mode)
        lay.addLayout(top)
        self.lbl = QLabel("")
        self.lbl.setStyleSheet("background: #ffffff; color: #0f172a; padding: 7px 12px; border-radius: 5px; font-size: 11px; font-weight: 600; border: 1px solid #cbd5e1;")
        lay.addWidget(self.lbl)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setStyleSheet("QSplitter::handle { background-color: #f1f5f9; width: 4px; }")
        self.nav = QListWidget()
        self.nav.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                outline: none;
            }
            QListWidget::item {
                padding: 7px 10px;
                border-bottom: 1px solid #f1f5f9;
                font-weight: 500;
                color: #334155;
            }
            QListWidget::item:selected {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
            }
            QListWidget::item:hover:!selected {
                background-color: #e0f2fe;
                color: #0369a1;
            }
        """)
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; }")
        split.addWidget(self.nav)
        split.addWidget(self.stack)
        split.setStretchFactor(1, 1)
        split.setSizes([250, 900])
        self.nav.currentRowChanged.connect(self.on_nav_changed)
        lay.addWidget(split, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.cb_prune = QCheckBox("Hanya simpan isian yang terisi")
        self.cb_prune.setChecked(False)
        self.cb_prune.setStyleSheet("QCheckBox { color: #1e293b; font-weight: 500; background: transparent; padding-right: 16px; }")
        self.cb_prune.setToolTip("Jika dicentang, tag yang masih kosong akan dihapus dari XML saat disimpan. "
                                 "Biarkan tidak dicentang jika ingin menyimpan draft (pekerjaan sementara) agar seluruh struktur tetap tersimpan.")
        self.cb_big = QCheckBox("Kompatibel Sistem BIG")
        self.cb_big.setChecked(True)
        self.cb_big.setStyleSheet("QCheckBox { color: #1e293b; font-weight: 500; background: transparent; padding-right: 12px; }")
        self.cb_big.setToolTip("Sesuaikan struktur blok raster, band, dan proses lineage agar terbaca penuh saat "
                               "diimpor/divalidasi di sistem BIG.")

        b_val = QPushButton("✓ Validasi Isian")
        b_val.setToolTip("Periksa kelengkapan isian di setiap tahapan (1–13) dan tampilkan jumlah serta daftar kolom yang masih kosong")
        b_val.setStyleSheet("""
            QPushButton {
                background-color: #f0fdf4;
                color: #15803d;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 5px;
                border: 1px solid #86efac;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #dcfce7;
                border-color: #22c55e;
                color: #14532d;
            }
        """)
        b_val.clicked.connect(self.validate_form)

        self.b_save = QPushButton("💾 Simpan")
        self.b_save.setToolTip("Simpan langsung perubahan/draft ke berkas XML aktif (Ctrl+S). Jika belum ada berkas aktif, akan membuka dialog Simpan Sebagai...")
        self.b_save.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                padding: 7px 18px;
                border-radius: 5px;
                border: 1px solid #0284c7;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0369a1;
                border-color: #0369a1;
            }
        """)
        self.b_save.clicked.connect(self.save_file)

        self.b_save_as = QPushButton("📁 Simpan Sebagai...")
        self.b_save_as.setToolTip("Simpan metadata atau draft ke berkas XML baru (Save As / Ctrl+Shift+S)")
        self.b_save_as.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                color: #1d4ed8;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 5px;
                border: 1px solid #93c5fd;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #dbeafe;
                border-color: #3b82f6;
                color: #1e40af;
            }
        """)
        self.b_save_as.clicked.connect(self.save_file_as)

        b_export_gmd = QPushButton("🌐 Export ISO 19139 (gmd)...")
        b_export_gmd.setToolTip("Ekspor isian metadata saat ini ke berkas XML standar ISO 19139 (namespace http://www.isotc211.org/2005/gmd)")
        b_export_gmd.setStyleSheet("""
            QPushButton {
                background-color: #ecfdf5;
                color: #047857;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 5px;
                border: 1px solid #6ee7b7;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d1fae5;
                border-color: #10b981;
                color: #065f46;
            }
        """)
        b_export_gmd.clicked.connect(self.export_iso19139)

        b_close = QPushButton("Tutup")
        b_close.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                font-weight: 500;
                padding: 7px 16px;
                border-radius: 5px;
                border: 1px solid #cbd5e1;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
                color: #0f172a;
            }
        """)
        b_close.clicked.connect(self.close)

        sc_save = QShortcut(QKeySequence.StandardKey.Save, self)
        sc_save.activated.connect(self.save_file)
        sc_save_as = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        sc_save_as.activated.connect(self.save_file_as)

        bottom.addWidget(self.cb_prune)
        bottom.addWidget(self.cb_big)
        bottom.addStretch()
        bottom.addWidget(b_val)
        bottom.addWidget(self.b_save)
        bottom.addWidget(self.b_save_as)
        bottom.addWidget(b_export_gmd)
        bottom.addWidget(b_close)
        lay.addLayout(bottom)

        self.load(TEMPLATE)

    # ---------- muat ----------
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Buka XML Metadata", self.src, "XML (*.xml);;Semua file (*)")
        if path:
            self.load(path)

    def load(self, path):
        try:
            root, fixes = model.load(path)
        except Exception as e:
            QMessageBox.warning(self, TITLE, "Gagal membaca XML:\n%s" % e)
            return

        is_gmd_format = False
        if gmd_importer.is_gmd(root):
            try:
                root = gmd_importer.convert_gmd_to_iso3(root, TEMPLATE)
                is_gmd_format = True
                fixes.append("Berkas XML standar ISO 19139 (gmd) berhasil dideteksi dan diimpor penuh ke form GeoMDB.")
            except Exception as e:
                QMessageBox.warning(self, TITLE, "Gagal mengonversi XML ISO 19139 ke ISO 19115-3:\n%s" % e)
                return

        self.root = root
        self.src = path if path not in (TEMPLATE, SAMPLE) else ""
        label_text = {
            TEMPLATE: "Mode Aktif: Template Kosong (Standar BIG)",
            SAMPLE: "Mode Aktif: Contoh Metadata (Terisi & Sesuai Validasi Sistem BIG)",
        }.get(path, "Berkas Aktif: %s" % path)
        if is_gmd_format:
            label_text += "  [Format ISO 19139 (gmd) Diimpor]"
        self.lbl.setText(label_text)
        self.mode_rebuild()
        if fixes:
            QMessageBox.information(self, TITLE, "\n".join(fixes))

    def on_mode(self, checked):
        if not checked or self.root is None:
            return
        self.apply_values()
        self.mode = "big" if self.rb_big.isChecked() else "all"
        self.rebuild()

    def on_nav_changed(self, row):
        if row < 0 or row >= self.nav.count():
            return
        if self.mode == "big":
            self.ensure_big_page(row)
        self.stack.setCurrentIndex(row)

    # ---------- bangun ulang (mempertahankan posisi) ----------
    def mode_rebuild(self):
        self.mode = "big" if self.rb_big.isChecked() else "all"
        self.rebuild()

    def snapshot(self):
        cur = self.nav.currentRow()
        if not (0 <= cur < len(self.scrolls)):
            return None
        page = self.stack.widget(cur)
        if page is None:
            return None
        tabs = page.findChild(QTabWidget)
        cs = self.cur_scroll(cur)
        scroll_val = cs.verticalScrollBar().value() if (cs is not None and cs.verticalScrollBar() is not None) else 0
        return {"row": cur, "tab": tabs.currentIndex() if tabs else 0,
                "scroll": scroll_val,
                "key": self.page_keys[cur] if cur < len(self.page_keys) else None}

    def cur_scroll(self, row):
        if not (0 <= row < len(self.scrolls)):
            return None
        page = self.stack.widget(row)
        if page is None:
            return self.scrolls[row] if row < len(self.scrolls) else None
        tabs = page.findChild(QTabWidget)
        if tabs is not None:
            w = tabs.currentWidget()
            if w is not None:
                return w if isinstance(w, QScrollArea) else w.findChild(QScrollArea)
        return self.scrolls[row] if row < len(self.scrolls) else None

    def rebuild(self, select_el=None):
        snap = self.snapshot() if self.items else None
        if self.mode == "big":
            self.build_big()
        else:
            self.build_all()
        if not self.nav.count():
            return
        row = 0
        if snap:
            row = min(snap["row"], self.nav.count() - 1)
            if snap["key"] in self.page_keys:
                row = self.page_keys.index(snap["key"])
        if select_el is not None:
            for r, sec in enumerate(self.page_secs):
                if getattr(sec, "el", None) is select_el:
                    row, snap = r, None
        self.nav.setCurrentRow(row)
        if self.mode == "big":
            self.ensure_big_page(row)
            self.stack.setCurrentIndex(row)
        if snap and snap["row"] == row:
            page = self.stack.widget(row)
            if page is not None:
                tabs = page.findChild(QTabWidget)
                if tabs is not None:
                    tabs.setCurrentIndex(min(snap["tab"], tabs.count() - 1))
            cs = self.cur_scroll(row)
            if cs is not None and cs.verticalScrollBar() is not None:
                bar = cs.verticalScrollBar()
                v = snap["scroll"]
                QTimer.singleShot(0, lambda: bar.setValue(v))

    def reset_pages(self):
        self.nav.blockSignals(True)
        self.nav.clear()
        self.nav.blockSignals(False)
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.items, self.page_secs, self.scrolls, self.page_keys = [], [], [], []
        self.built_big_pages = set()

    # =====================================================================
    #  MODE FORM BIG (Lazy Loading: muat bertahap sesuai kebutuhan)
    # =====================================================================
    def build_big(self):
        self.reset_pages()
        secs, _missing = layout.build(self.root)
        for s in secs:
            placeholder = QWidget()
            placeholder.setStyleSheet("background-color: #ffffff;")
            self.stack.addWidget(placeholder)
            self.scrolls.append(None)
            self.page_secs.append(s)
            self.page_keys.append(("big", s.id))
            self.nav.addItem("%d. %s" % (s.id, s.label))
            self.nav.item(self.nav.count() - 1).setToolTip(s.caption)

    def ensure_big_page(self, row):
        if not (0 <= row < len(self.page_secs)):
            return
        if row in self.built_big_pages:
            return
        self.built_big_pages.add(row)
        s = self.page_secs[row]
        page, first_scroll = self._build_single_big_page(s)
        self.scrolls[row] = first_scroll
        old_w = self.stack.widget(row)
        self.stack.removeWidget(old_w)
        self.stack.insertWidget(row, page)
        old_w.deleteLater()
        if self.nav.currentRow() == row:
            self.stack.setCurrentIndex(row)

    def _build_single_big_page(self, s):
        page = QWidget()
        page.setStyleSheet("background-color: #ffffff;")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.setSpacing(10)
        head = QLabel("<b style='font-size:15px; color:#0f172a;'>%d. %s</b><br><span style='color:#64748b; font-size:12px;'>%s</span>"
                      % (s.id, s.label, s.caption))
        head.setStyleSheet("background: transparent; padding-bottom: 4px;")
        pl.addWidget(head)
        segments, cur_tab = [], None
        for n in s.nodes:
            if isinstance(n, layout.BTab):
                cur_tab = (n.label, [])
                segments.append(cur_tab)
            elif cur_tab is None:
                if not segments or segments[-1][0] is not None:
                    segments.append((None, []))
                segments[-1][1].append(n)
            else:
                cur_tab[1].append(n)
        first_scroll = None
        if len(segments) == 1 and segments[0][0] is None:
            first_scroll = self.scroll_for(segments[0][1])
            pl.addWidget(first_scroll, 1)
        else:
            tabs = QTabWidget()
            tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #cbd5e1;
                    background-color: #ffffff;
                    border-radius: 6px;
                    top: -1px;
                }
                QTabBar::tab {
                    background-color: #f1f5f9;
                    color: #475569;
                    border: 1px solid #cbd5e1;
                    border-bottom: none;
                    padding: 7px 16px;
                    border-top-left-radius: 5px;
                    border-top-right-radius: 5px;
                    margin-right: 2px;
                    font-weight: 500;
                    font-size: 12px;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    color: #0284c7;
                    font-weight: bold;
                    border-bottom: 2px solid #0284c7;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #e2e8f0;
                    color: #1e293b;
                }
            """)
            for label, nodes in segments:
                sc = self.scroll_for(nodes)
                first_scroll = first_scroll or sc
                tabs.addTab(sc, (label or "Umum").replace("&", "&&"))
            pl.addWidget(tabs, 1)
        return page, first_scroll

    def scroll_for(self, nodes):
        inner = QWidget()
        inner.setStyleSheet("background-color: #ffffff;")
        form = QFormLayout(inner)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setContentsMargins(4, 4, 12, 4)
        form.setSpacing(10)
        self.render(nodes, form)
        sc = QScrollArea()
        sc.setStyleSheet("QScrollArea { border: none; background-color: #ffffff; } QScrollArea > QWidget > QWidget { background-color: #ffffff; }")
        sc.setWidgetResizable(True)
        sc.setWidget(inner)
        return sc

    def render(self, nodes, form, widget_sink=None):
        for n in nodes:
            if isinstance(n, layout.BGroup):
                lab = QLabel("<b>%s</b>" % n.label)
                lab.setStyleSheet("color: #0369a1; font-size: 13px; font-weight: bold; background: transparent; border: none; padding-top: 10px; padding-bottom: 2px;")
                form.addRow(lab)
            elif isinstance(n, layout.BNote):
                lab = QLabel("<i>%s</i>" % n.text)
                lab.setStyleSheet("color: #64748b; font-size: 11px; background: transparent; border: none;")
                lab.setWordWrap(True)
                form.addRow(lab)
            elif isinstance(n, layout.BField):
                self.render_field(n, form, widget_sink)
            elif isinstance(n, layout.BList):
                self.render_list(n, form)
            elif isinstance(n, layout.BOptional):
                self.render_optional(n, form)

    @staticmethod
    def is_date_field(f, key=""):
        v = getattr(f, "value_name", "")
        if v in ("Date", "DateTime", "beginPosition", "endPosition", "timePosition"):
            return True
        k = (key or "").lower()
        if any(x in k for x in ("date", "datetime", "timebegin", "timeend", "stepdatetime")) and not any(x in k for x in ("type", "update", "candidate", "frequency")):
            return True
        return False

    def render_field(self, bf, form, widget_sink=None):
        lab = QLabel(bf.label)
        lab.setWordWrap(True)
        lab.setMinimumWidth(185)
        lab.setMaximumWidth(215)
        lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lab.setStyleSheet("color: #1e293b; font-weight: 600; background: transparent; border: none; padding-top: 4px;")
        f = bf.field
        if f is None:
            f = layout.VirtualField(self.root, getattr(bf, "spec", None) or layout.F(bf.key, bf.label, getattr(bf, "path", bf.key)), self.root)
            bf.field = f
        w = self.big_widget(bf)
        self.items.append((f, w))
        if widget_sink is not None and getattr(bf, "key", None):
            widget_sink[bf.key] = w
        box = QWidget()
        box.setObjectName("fieldBox")
        box.setStyleSheet("QWidget#fieldBox { background: transparent; }")
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        v.addWidget(w)
        if bf.desc:
            lab.setToolTip(bf.desc)
            w.setToolTip(bf.desc)
            hint = QLabel(bf.desc)
            hint.setStyleSheet(HINT_CSS)
            hint.setWordWrap(True)
            v.addWidget(hint)
        form.addRow(lab, box)

    def big_widget(self, bf):
        f = bf.field
        val = f.get()
        if bf.options:
            return ChoiceCombo(bf.options, val)
        if f.value_name == "Boolean":
            return ChoiceCombo([("Ya (true)", "true", ""), ("Tidak (false)", "false", "")], val)
        if self.is_date_field(f, getattr(bf, "key", "")):
            is_dt = (f.value_name == "DateTime") or ("time" in getattr(bf, "key", "").lower())
            return DatePickerWidget(val, is_datetime=is_dt)
        if f.multiline:
            w = QPlainTextEdit(val)
            w.setMinimumHeight(70)
            w.setMaximumHeight(130)
            return w
        w = QLineEdit(val)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if f.value_name in PLACEHOLDERS:
            w.setPlaceholderText(PLACEHOLDERS[f.value_name])
        return w

    def render_list(self, bl, form):
        for inst in bl.instances:
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setObjectName("cardFrame")
            card.setStyleSheet("""
                QFrame#cardFrame {
                    background-color: #f8fafc;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                }
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 12)
            cl.setSpacing(8)
            hd = QHBoxLayout()
            lbl_title = QLabel("<b style='font-size:12px;color:#0f172a;'>%s</b>" % inst.title)
            lbl_title.setStyleSheet("background: transparent; border: none;")
            hd.addWidget(lbl_title)
            hd.addStretch()

            is_contact = any(getattr(n, "key", "") == "organization" for n in inst.nodes)
            inst_widgets = {}

            inner = QWidget()
            inner.setObjectName("listInner")
            inner.setStyleSheet("QWidget#listInner { background: transparent; }")
            f2 = QFormLayout(inner)
            f2.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            f2.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            f2.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            f2.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            f2.setContentsMargins(0, 4, 0, 0)
            f2.setSpacing(8)
            self.render(inst.nodes, f2, widget_sink=inst_widgets if is_contact else None)

            if is_contact:
                btn_load = QToolButton()
                btn_load.setText("📋 Panggil Kontak ▾")
                btn_load.setToolTip("Pilih profil kontak tersimpan untuk mengisi form ini secara otomatis")
                btn_load.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                btn_load.setStyleSheet("""
                    QToolButton {
                        padding: 4px 10px;
                        font-weight: 600;
                        background-color: #f0fdf4;
                        color: #15803d;
                        border: 1px solid #86efac;
                        border-radius: 4px;
                        font-size: 11px;
                    }
                    QToolButton:hover {
                        background-color: #dcfce7;
                        border-color: #22c55e;
                        color: #14532d;
                    }
                """)
                menu = QMenu(btn_load)
                btn_load.setMenu(menu)
                menu.aboutToShow.connect(lambda m=menu, wmap=inst_widgets: self.populate_contact_menu(m, wmap))
                hd.addWidget(btn_load)

                btn_save = QPushButton("💾 Simpan Kontak")
                btn_save.setToolTip("Simpan isian kontak saat ini agar dapat digunakan kembali di bagian kontak lain")
                btn_save.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-weight: 600;
                        background-color: #eff6ff;
                        color: #1d4ed8;
                        border: 1px solid #93c5fd;
                        border-radius: 4px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #dbeafe;
                        border-color: #3b82f6;
                        color: #1e40af;
                    }
                """)
                btn_save.clicked.connect(lambda _=False, wmap=inst_widgets: self.save_contact_from_widgets(wmap))
                hd.addWidget(btn_save)

            if inst.removable:
                b = QPushButton("Hapus")
                b.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-weight: 500;
                        background-color: #fef2f2;
                        color: #dc2626;
                        border: 1px solid #fecaca;
                        border-radius: 4px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #fee2e2;
                        border-color: #f87171;
                        color: #991b1b;
                    }
                """)
                b.clicked.connect(lambda _=False, p=bl.container, e=inst.el: self.remove(p, e))
                hd.addWidget(b)

            cl.addLayout(hd)
            cl.addWidget(inner)
            form.addRow(card)
        if bl.can_add:
            form.addRow(self.add_button(bl.title, bl.container, bl.options, False))

    # ---------- manajemen preset kontak ----------
    def load_contact_presets(self):
        presets = {}
        if os.path.exists(CONTACTS_FILE):
            try:
                with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
                    presets = json.load(f)
            except Exception:
                presets = {}
        return presets

    def save_contact_preset(self, name, data):
        presets = self.load_contact_presets()
        presets[name] = data
        try:
            with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
                json.dump(presets, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, TITLE, "Gagal menyimpan berkas kontak:\n%s" % e)

    def delete_contact_preset(self, name):
        presets = self.load_contact_presets()
        if name in presets:
            del presets[name]
            try:
                with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(presets, f, ensure_ascii=False, indent=2)
            except Exception as e:
                QMessageBox.warning(self, TITLE, "Gagal menghapus kontak:\n%s" % e)

    def populate_contact_menu(self, menu, wmap):
        menu.clear()
        presets = self.load_contact_presets()
        if not presets:
            act = menu.addAction("(Belum ada kontak tersimpan)")
            act.setEnabled(False)
        else:
            for name, data in sorted(presets.items()):
                org = data.get("organization", "")
                ind = data.get("individual", "")
                detail = f"{org} — {ind}" if org and ind and org != name else (org or ind)
                text = f"{name} ({detail})" if detail and detail != name else name
                act = menu.addAction(text)
                act.triggered.connect(lambda _=False, d=data, w=wmap: self.apply_contact_data(w, d))
        menu.addSeparator()
        act_manage = menu.addAction("⚙ Kelola Kontak Tersimpan...")
        act_manage.triggered.connect(self.manage_contacts_dialog)

    def apply_contact_data(self, wmap, data):
        for key, val in data.items():
            if key in wmap:
                self.write(wmap[key], val)
        self.apply_values()
        org = data.get("organization") or data.get("individual") or "Profil kontak"
        if hasattr(self.iface, "messageBar"):
            self.iface.messageBar().pushInfo(TITLE, "Isian kontak berhasil diisi dari '%s'." % org)

    def save_contact_from_widgets(self, wmap):
        data = {}
        for key, w in wmap.items():
            val = self.read(w)
            if val:
                data[key] = val
        if not data:
            QMessageBox.warning(self, "Simpan Kontak", "Isian kontak masih kosong. Silakan isi terlebih dahulu.")
            return
        default_name = data.get("organization") or data.get("individual") or "Kontak Baru"
        name, ok = QInputDialog.getText(self, "Simpan Kontak", "Nama profil kontak:", text=default_name)
        if ok and name.strip():
            name = name.strip()
            self.save_contact_preset(name, data)
            if hasattr(self.iface, "messageBar"):
                self.iface.messageBar().pushSuccess(TITLE, "Profil kontak '%s' berhasil disimpan." % name)

    def manage_contacts_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Kelola Kontak Tersimpan")
        dlg.resize(460, 320)
        dlg.setStyleSheet(DIALOG_STYLE)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        lbl = QLabel("<b>Daftar Profil Kontak Tersimpan:</b>")
        lbl.setStyleSheet("color: #0f172a; font-size: 13px; background: transparent;")
        lay.addWidget(lbl)
        list_w = QListWidget()
        list_w.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                outline: none;
                padding: 4px;
            }
            QListWidget::item {
                padding: 7px 10px;
                border-bottom: 1px solid #f1f5f9;
                font-weight: 500;
                color: #334155;
            }
            QListWidget::item:selected {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
            }
            QListWidget::item:hover:!selected {
                background-color: #e0f2fe;
                color: #0369a1;
            }
        """)
        presets = self.load_contact_presets()
        for name in sorted(presets.keys()):
            list_w.addItem(name)
        lay.addWidget(list_w)
        btn_layout = QHBoxLayout()
        btn_del = QPushButton("Hapus Kontak Terpilih")
        btn_del.setStyleSheet("""
            QPushButton {
                padding: 6px 14px;
                font-weight: 500;
                background-color: #fef2f2;
                color: #dc2626;
                border: 1px solid #fecaca;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
                border-color: #f87171;
            }
        """)
        def delete_selected():
            cur = list_w.currentItem()
            if not cur:
                return
            cname = cur.text()
            if QMessageBox.question(dlg, "Hapus Kontak", "Hapus profil kontak '%s'?" % cname) == QMessageBox.StandardButton.Yes:
                self.delete_contact_preset(cname)
                list_w.takeItem(list_w.row(cur))
        btn_del.clicked.connect(delete_selected)
        btn_close = QPushButton("Tutup")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                font-weight: 500;
                padding: 6px 16px;
                border-radius: 4px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
                color: #0f172a;
            }
        """)
        btn_close.clicked.connect(dlg.accept)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        lay.addLayout(btn_layout)
        dlg.exec()

    def render_optional(self, bo, form):
        cb = QCheckBox(bo.label)
        cb.setChecked(bo.present)
        cb.setStyleSheet("QCheckBox { font-weight: bold; color: #0369a1; font-size: 13px; background: transparent; padding: 2px 0px; }")
        cb.clicked.connect(lambda checked, b=bo: self.toggle_optional(b, checked))
        form.addRow(cb)
        if bo.present and bo.nodes:
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setObjectName("optFrame")
            frame.setStyleSheet("""
                QFrame#optFrame {
                    background-color: #f8fafc;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                }
            """)
            fl = QFormLayout(frame)
            fl.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            fl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            fl.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            fl.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            fl.setContentsMargins(12, 10, 12, 12)
            fl.setSpacing(8)
            self.render(bo.nodes, fl)
            form.addRow(frame)

    def toggle_optional(self, bo, checked):
        self.apply_values()
        if checked:
            model.add_snippet(self.root, bo.container, bo.snippet)
        else:
            ans = QMessageBox.question(self, TITLE, "Hapus blok ini beserta seluruh isinya dari XML?")
            if ans != QMessageBox.StandardButton.Yes:
                self.rebuild()
                return
            model.remove_block(bo.container, bo.el)
        self.rebuild()

    # =====================================================================
    #  MODE SEMUA ELEMEN ISO
    # =====================================================================
    def build_all(self):
        self.reset_pages()
        self.sections = model.build_sections(self.root)
        for sec in self.sections:
            if not sec.fields:
                continue
            page = QWidget()
            page.setStyleSheet("background-color: #ffffff;")
            pl = QVBoxLayout(page)
            pl.setContentsMargins(14, 12, 14, 12)
            pl.setSpacing(10)
            pl.addLayout(self.section_header(sec))
            inner = QWidget()
            inner.setStyleSheet("background-color: #ffffff;")
            form = QFormLayout(inner)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            form.setSpacing(10)
            for it in sec.items:
                if isinstance(it, model.Field):
                    w = self.make_widget(it)
                    lab = QLabel(it.label)
                    lab.setWordWrap(True)
                    lab.setMinimumWidth(185)
                    lab.setMaximumWidth(215)
                    lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    lab.setStyleSheet("color: #1e293b; font-weight: 600; background: transparent; border: none; padding-top: 4px;")
                    form.addRow(lab, w)
                    self.items.append((it, w))
                elif isinstance(it, model.Block):
                    form.addRow(self.block_header(it))
                else:
                    lab = QLabel(" › ".join(it.trail))
                    lab.setWordWrap(True)
                    lab.setMinimumWidth(185)
                    lab.setMaximumWidth(215)
                    lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    lab.setStyleSheet("color: #475569; font-weight: 600; background: transparent; border: none;")
                    form.addRow(lab, self.add_button(it.name, it.parent, it.options, False))
            scroll = QScrollArea()
            scroll.setStyleSheet("QScrollArea { border: none; background-color: #ffffff; } QScrollArea > QWidget > QWidget { background-color: #ffffff; }")
            scroll.setWidgetResizable(True)
            scroll.setWidget(inner)
            pl.addWidget(scroll, 1)
            self.stack.addWidget(page)
            self.scrolls.append(scroll)
            self.page_secs.append(sec)
            self.page_keys.append(("all", sec.name, sec.idx))
            self.nav.addItem(sec.title)

    def section_header(self, sec):
        row = QHBoxLayout()
        lbl = QLabel("<b style='font-size:15px; color:#0f172a;'>%s</b>" % sec.title)
        lbl.setStyleSheet("background: transparent;")
        row.addWidget(lbl)
        row.addStretch()
        if sec.repeatable:
            row.addWidget(self.add_button(sec.base_title, sec.parent, sec.options, True))
            if sec.count > 1:
                b = QPushButton("Hapus bagian ini")
                b.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-weight: 500;
                        background-color: #fef2f2;
                        color: #dc2626;
                        border: 1px solid #fecaca;
                        border-radius: 4px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #fee2e2;
                        border-color: #f87171;
                        color: #991b1b;
                    }
                """)
                b.clicked.connect(lambda _=False, p=sec.parent, e=sec.el: self.remove(p, e))
                row.addWidget(b)
        return row

    def block_header(self, blk):
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 8, 0, 0)
        lbl = QLabel("<b style='font-size:13px; color:#0369a1;'>%s</b>" % blk.label)
        lbl.setStyleSheet("background: transparent;")
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #e2e8f0; background-color: #e2e8f0; max-height: 1px;")
        h.addWidget(lbl)
        h.addWidget(line, 1)
        b = QPushButton("Hapus blok")
        b.setStyleSheet("""
            QPushButton {
                padding: 4px 10px;
                font-weight: 500;
                background-color: #fef2f2;
                color: #dc2626;
                border: 1px solid #fecaca;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
                border-color: #f87171;
                color: #991b1b;
            }
        """)
        b.clicked.connect(lambda _=False, p=blk.parent, e=blk.el: self.remove(p, e))
        h.addWidget(b)
        return box

    def make_widget(self, f):
        val = f.get()
        if f.kind in ("code", "enum"):
            w = QComboBox()
            setup_combo_styling(w)
            w.setEditable(True)
            w.addItems([""] + f.options)
            w.setCurrentText(val)
        elif f.value_name == "Boolean":
            w = QComboBox()
            setup_combo_styling(w)
            w.addItems(["", "true", "false"])
            w.setCurrentText(val if val in ("true", "false") else "")
        elif self.is_date_field(f):
            is_dt = (f.value_name == "DateTime")
            w = DatePickerWidget(val, is_datetime=is_dt)
        elif f.multiline:
            w = QPlainTextEdit(val)
            w.setMinimumHeight(70)
            w.setMaximumHeight(130)
        else:
            w = QLineEdit(val)
            if f.value_name in PLACEHOLDERS:
                w.setPlaceholderText(PLACEHOLDERS[f.value_name])
        return w

    # =====================================================================
    #  UMUM
    # =====================================================================
    def add_button(self, name, parent, options, select_new):
        text = "+ Tambah %s" % name
        style = """
            QPushButton, QToolButton {
                background-color: #f0fdf4;
                color: #166534;
                border: 1px dashed #86efac;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #dcfce7;
                border: 1px solid #22c55e;
                color: #14532d;
            }
        """
        if len(options) > 1:
            btn = QToolButton()
            btn.setText(text + " ▾")
            btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            btn.setStyleSheet(style)
            menu = QMenu(btn)
            for cls, src in options:
                act = menu.addAction(cls or name)
                act.triggered.connect(lambda _=False, p=parent, s=src: self.add(p, s, select_new))
            btn.setMenu(menu)
        else:
            btn = QPushButton(text)
            btn.setStyleSheet(style)
            btn.clicked.connect(lambda _=False, p=parent, s=options[0][1]: self.add(p, s, select_new))
        return btn

    @staticmethod
    def read(w):
        if isinstance(w, ChoiceCombo):
            return w.value()
        if isinstance(w, QCheckBox):
            return "true" if w.isChecked() else "false"
        if isinstance(w, DatePickerWidget):
            return w.text()
        if isinstance(w, QComboBox):
            return w.currentText()
        if isinstance(w, QPlainTextEdit):
            return w.toPlainText()
        return w.text()

    @staticmethod
    def write(w, text):
        if isinstance(w, ChoiceCombo):
            w.set_value(text)
        elif isinstance(w, QCheckBox):
            w.setChecked(text == "true")
        elif isinstance(w, DatePickerWidget):
            w.setText(text)
        elif isinstance(w, QComboBox):
            w.setCurrentText(text)
        elif isinstance(w, QPlainTextEdit):
            w.setPlainText(text)
        else:
            w.setText(text)

    def apply_values(self):
        for f, w in self.items:
            f.set(self.read(w))

    def add(self, parent, src, select_new=False):
        self.apply_values()
        if isinstance(src, tuple):                      # ('snip', nama) = sisip dari template
            new = model.add_snippet(self.root, parent, src[1])
        else:
            new = model.add_block(self.root, parent, src)
        self.rebuild(select_el=new if (select_new and self.mode == "all") else None)

    def remove(self, parent, el):
        ans = QMessageBox.question(self, TITLE, "Hapus blok ini beserta seluruh isinya?")
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.apply_values()
        model.remove_block(parent, el)
        self.rebuild()

    # ---------- isi dari layer ----------
    def set_value(self, section, names, text):
        for f, w in self.items:
            if f.section == section and f.names == tuple(names):
                self.write(w, text)
                return True
        return False

    @staticmethod
    def _find_node(nodes, pred):
        """Cari simpul (BField/BList/BOptional) termasuk di dalam blok opsional aktif, tanpa masuk ke daftar."""
        for n in nodes:
            if pred(n):
                return n
            if isinstance(n, layout.BOptional) and n.present:
                r = EditorDialog._find_node(n.nodes, pred)
                if r is not None:
                    return r
        return None

    def _find_list(self, nodes, path):
        return self._find_node(nodes, lambda n: isinstance(n, layout.BList) and getattr(n, "path", None) == path)

    def _find_field(self, nodes, key):
        return self._find_node(nodes, lambda n: isinstance(n, layout.BField) and n.key == key and n.field is not None)

    def _stages(self):
        return {s.id: s for s in layout.build(self.root)[0]}

    def _ensure_count(self, bl, n):
        prop = bl.path.split("/")[-1]
        count = len(bl.instances)
        while count < n and bl.options and model.can_add(bl.container, prop, count):
            src = bl.options[0][1]
            if isinstance(src, tuple):
                model.add_snippet(self.root, bl.container, src[1])
            else:
                model.add_block(self.root, bl.container, src)
            count += 1

    @staticmethod
    def _fmt_value(field, val):
        if isinstance(val, datetime.date):
            if getattr(field, "value_name", "") == "DateTime":
                dt = val if isinstance(val, datetime.datetime) else datetime.datetime.combine(val, datetime.time())
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            return val.strftime("%Y-%m-%d")
        return str(val)

    def _apply_layer_plan(self, plan):
        filled = []  # (sid, label, nilai)

        # 1) aktifkan blok opsional
        for sid, snip in plan["optionals"]:
            st = self._stages().get(sid)
            bo = st and self._find_node(st.nodes, lambda n: isinstance(n, layout.BOptional) and n.snippet == snip)
            if bo is not None and not bo.present:
                model.add_snippet(self.root, bo.container, bo.snippet)

        # 2) tambah entri daftar berulang (tingkat atas), lalu 3) daftar bersarang
        for sid, path, insts in plan["lists"]:
            st = self._stages().get(sid)
            bl = st and self._find_list(st.nodes, path)
            if bl is not None:
                self._ensure_count(bl, len(insts))
        for sid, path, insts in plan["lists"]:
            st = self._stages().get(sid)
            bl = st and self._find_list(st.nodes, path)
            if bl is None:
                continue
            for ip, inst in zip(insts, bl.instances):
                for npath, sub in ip.get("__lists__", {}).items():
                    nbl = self._find_list(inst.nodes, npath)
                    if nbl is not None:
                        self._ensure_count(nbl, len(sub))

        # 4) tulis nilai (timpa)
        secs = self._stages()

        def put(sid, bf, val, label):
            txt = self._fmt_value(bf.field, val)
            if not txt.strip():
                return
            bf.field.set(txt)
            filled.append((sid, label, txt))

        for sid, key, val in plan["fields"]:
            st = secs.get(sid)
            bf = st and self._find_field(st.nodes, key)
            if bf is not None:
                put(sid, bf, val, bf.label)
        for sid, path, insts in plan["lists"]:
            st = secs.get(sid)
            bl = st and self._find_list(st.nodes, path)
            if bl is None:
                continue
            for i, (ip, inst) in enumerate(zip(insts, bl.instances), 1):
                for key, val in ip.items():
                    if key == "__lists__":
                        continue
                    bf = self._find_field(inst.nodes, key)
                    if bf is not None:
                        put(sid, bf, val, "%s %d › %s" % (bl.title, i, bf.label))
                for npath, sub in ip.get("__lists__", {}).items():
                    nbl = self._find_list(inst.nodes, npath)
                    if nbl is None:
                        continue
                    for j, (sp_, sinst) in enumerate(zip(sub, nbl.instances), 1):
                        for key, val in sp_.items():
                            bf = self._find_field(sinst.nodes, key)
                            if bf is not None:
                                put(sid, bf, val, "%s %d › %s %d" % (bl.title, i, nbl.title, j))
        return filled

    def fill_from_layer(self):
        from qgis.core import QgsVectorLayer
        from . import layer_extract
        layer = self.iface.activeLayer()
        if layer is None:
            QMessageBox.information(self, TITLE, "Pilih sebuah layer di panel Layers terlebih dahulu.")
            return
        if not isinstance(layer, QgsVectorLayer):
            QMessageBox.information(self, TITLE, "Saat ini pengambilan metadata otomatis baru mendukung layer vektor.\n"
                                                 "Layer '%s' bukan layer vektor." % layer.name())
            return
        if self.root is None:
            self.load(TEMPLATE)
        self.apply_values()
        try:
            plan = layer_extract.extract_vector(layer)
            filled = self._apply_layer_plan(plan)
        except Exception as e:
            QMessageBox.warning(self, TITLE, "Gagal mengambil metadata dari layer:\n%s" % e)
            self.rebuild()
            return

        saved = []
        for name, data in plan["contacts"]:
            if name:
                self.save_contact_preset(name, data)
                saved.append(name)

        self.rebuild()
        self.update_nav_validation_badges()
        self.show_fill_report(layer.name(), filled, saved, plan["notes"])

    def show_fill_report(self, layer_name, filled, saved_contacts, notes):
        import html
        stages = {s.id: s.label for s in layout.build(self.root)[0]}
        by_stage = {}
        for sid, label, val in filled:
            by_stage.setdefault(sid, []).append((label, val))

        dlg = QDialog(self)
        dlg.setWindowTitle("Metadata Terisi Otomatis dari Layer")
        dlg.resize(680, 560)
        dlg.setStyleSheet(DIALOG_STYLE)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        head = QLabel(
            "<b style='font-size:14px;color:#0f172a;'>%d isian terisi otomatis dari layer “%s”</b><br>"
            "<span style='color:#475569;'>Nilai lama pada field tersebut telah ditimpa. Semua isian tetap dapat "
            "diedit kembali di form.</span>" % (len(filled), html.escape(layer_name)))
        head.setWordWrap(True)
        head.setStyleSheet("background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;padding:10px;")
        lay.addWidget(head)

        parts = []
        for sid in sorted(by_stage):
            rows = "".join(
                "<tr><td style='padding:2px 10px 2px 0;color:#334155;vertical-align:top;'>%s</td>"
                "<td style='padding:2px 0;color:#0f172a;'>%s</td></tr>"
                % (html.escape(lbl), html.escape(val if len(val) <= 90 else val[:87] + "…").replace("\n", "<br>"))
                for lbl, val in by_stage[sid])
            parts.append("<p style='margin:10px 0 4px 0;'><b style='color:#0369a1;'>%d. %s</b> "
                         "<span style='color:#64748b;'>(%d isian)</span></p><table>%s</table>"
                         % (sid, html.escape(stages.get(sid, "")), len(by_stage[sid]), rows))
        if saved_contacts:
            parts.append("<p style='margin:12px 0 4px 0;'><b style='color:#15803d;'>Kontak tersimpan otomatis:</b> %s</p>"
                         % html.escape(", ".join(saved_contacts)))
        for n in notes:
            parts.append("<p style='color:#64748b;margin:8px 0 0 0;'>ℹ %s</p>" % html.escape(n))
        if not filled:
            parts.append("<p>Tidak ada properti yang dapat diambil dari layer ini.</p>")

        body = QLabel("".join(parts))
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.setStyleSheet("background:#ffffff;padding:6px;")
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(body)
        sc.setStyleSheet("QScrollArea{border:1px solid #cbd5e1;border-radius:6px;background:#ffffff;}")
        lay.addWidget(sc, 1)

        btns = QHBoxLayout()
        btns.addStretch()
        b = QPushButton("Tutup")
        b.clicked.connect(dlg.accept)
        btns.addWidget(b)
        lay.addLayout(btns)
        dlg.exec()

    # ---------- validasi kelengkapan per tahapan ----------
    @staticmethod
    def _collect_stage_fields(nodes, prefix=""):
        cur_prefix = prefix
        for n in nodes:
            if isinstance(n, layout.BTab):
                cur_prefix = f"{prefix} › {n.label}" if prefix else n.label
            elif isinstance(n, layout.BField) and n.field is not None:
                lbl = f"{cur_prefix} › {n.label}" if cur_prefix else n.label
                yield (lbl, n.field)
            elif isinstance(n, layout.BOptional):
                if n.present and n.nodes:
                    opt_prefix = f"{cur_prefix} › {n.label}" if cur_prefix else n.label
                    yield from EditorDialog._collect_stage_fields(n.nodes, opt_prefix)
            elif isinstance(n, layout.BList):
                for inst in n.instances:
                    inst_prefix = f"{cur_prefix} › {inst.title}" if cur_prefix else inst.title
                    yield from EditorDialog._collect_stage_fields(inst.nodes, inst_prefix)

    def compute_stage_validation(self):
        self.apply_values()
        secs = layout.build(self.root)[0]
        results = []
        for idx, s in enumerate(secs):
            fields = list(self._collect_stage_fields(s.nodes))
            total = len(fields)
            empty_labels = []
            for lbl, f in fields:
                val = (f.get() or "").strip()
                if not val:
                    empty_labels.append(lbl)
            empty_count = len(empty_labels)
            filled_count = total - empty_count
            results.append({
                "index": idx,
                "id": s.id,
                "label": s.label,
                "caption": s.caption,
                "total": total,
                "filled": filled_count,
                "empty": empty_count,
                "empty_labels": empty_labels,
            })
        return results

    def update_nav_validation_badges(self, stage_stats=None):
        if self.mode != "big":
            return
        if stage_stats is None:
            stage_stats = self.compute_stage_validation()
        for st in stage_stats:
            idx = st["index"]
            if 0 <= idx < self.nav.count():
                it = self.nav.item(idx)
                if st["empty"] == 0:
                    it.setText("%d. %s  ✓" % (st["id"], st["label"]))
                else:
                    it.setText("%d. %s  (%d kosong)" % (st["id"], st["label"], st["empty"]))

    def jump_to_stage(self, stage_index, dlg=None):
        if dlg is not None:
            dlg.accept()
        if self.mode != "big":
            self.rb_big.setChecked(True)
        if 0 <= stage_index < self.nav.count():
            self.nav.setCurrentRow(stage_index)

    def validate_form(self):
        if self.root is None:
            return
        stage_stats = self.compute_stage_validation()
        self.update_nav_validation_badges(stage_stats)
        all_fields = [f for s in layout.build(self.root)[0] for _, f in self._collect_stage_fields(s.nodes)]
        format_problems = model.validate(all_fields)

        total_fields = sum(s["total"] for s in stage_stats)
        total_filled = sum(s["filled"] for s in stage_stats)
        total_empty = sum(s["empty"] for s in stage_stats)
        stages_with_empty = sum(1 for s in stage_stats if s["empty"] > 0)

        dlg = QDialog(self)
        dlg.setWindowTitle("Hasil Validasi Kelengkapan Isian Metadata")
        dlg.resize(720, 620)
        dlg.setStyleSheet(DIALOG_STYLE)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Ringkasan Utama
        summary_card = QFrame()
        summary_card.setObjectName("summaryCard")
        if total_empty == 0 and not format_problems:
            summary_card.setStyleSheet("""
                QFrame#summaryCard {
                    background-color: #f0fdf4;
                    border: 1px solid #86efac;
                    border-radius: 6px;
                }
            """)
            status_title = "<b style='font-size:14px; color:#15803d;'>✓ Seluruh Tahapan Lengkap!</b>"
            status_sub = (
                f"<span style='color:#166534; font-size:12px;'>"
                f"Semua <b>{total_fields}</b> isian pada 13 tahapan telah terisi dan siap diekspor/divalidasi ke sistem BIG."
                f"</span>"
            )
        else:
            summary_card.setStyleSheet("""
                QFrame#summaryCard {
                    background-color: #fffbeb;
                    border: 1px solid #fde68a;
                    border-radius: 6px;
                }
            """)
            status_title = (
                f"<b style='font-size:14px; color:#b45309;'>"
                f"⚠ Ditemukan {total_empty} Isian Kosong pada {stages_with_empty} dari {len(stage_stats)} Tahapan"
                f"</b>"
            )
            status_sub = (
                f"<span style='color:#92400e; font-size:12px;'>"
                f"Terisi: <b>{total_filled}</b> dari <b>{total_fields}</b> isian &nbsp;|&nbsp; "
                f"Belum terisi (kosong): <b>{total_empty}</b> isian. "
                f"Anda tetap dapat menyimpan sebagai <b>Draft</b> menggunakan tombol <b>Simpan</b> atau <b>Simpan Sebagai...</b>"
                f"</span>"
            )

        sl = QVBoxLayout(summary_card)
        sl.setContentsMargins(14, 12, 14, 12)
        sl.setSpacing(4)
        lbl_t = QLabel(status_title)
        lbl_t.setWordWrap(True)
        lbl_s = QLabel(status_sub)
        lbl_s.setWordWrap(True)
        sl.addWidget(lbl_t)
        sl.addWidget(lbl_s)

        if format_problems:
            prob_txt = "<br>".join("• " + p for p in format_problems[:8])
            lbl_p = QLabel(f"<div style='margin-top:6px; color:#dc2626; font-size:11px;'><b>Peringatan Format Nilai ({len(format_problems)}):</b><br>{prob_txt}</div>")
            lbl_p.setWordWrap(True)
            sl.addWidget(lbl_p)

        lay.addWidget(summary_card)

        # Daftar per Tahapan dalam ScrollArea
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setStyleSheet("QScrollArea { border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff; }")
        container = QWidget()
        container.setStyleSheet("background-color: #ffffff;")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(10)

        for st in stage_stats:
            row_card = QFrame()
            obj_name = f"stageCard_{st['id']}"
            row_card.setObjectName(obj_name)
            if st["empty"] == 0:
                row_card.setStyleSheet(f"""
                    QFrame#{obj_name} {{
                        background-color: #f8fafc;
                        border: 1px solid #e2e8f0;
                        border-left: 4px solid #22c55e;
                        border-radius: 6px;
                    }}
                """)
                badge_html = (
                    f"<span style='color:#15803d; font-weight:bold; font-size:12px;'>"
                    f"✓ Lengkap ({st['filled']}/{st['total']} terisi)"
                    f"</span>"
                )
            else:
                row_card.setStyleSheet(f"""
                    QFrame#{obj_name} {{
                        background-color: #ffffff;
                        border: 1px solid #cbd5e1;
                        border-left: 4px solid #f59e0b;
                        border-radius: 6px;
                    }}
                """)
                badge_html = (
                    f"<span style='color:#d97706; font-weight:bold; font-size:12px;'>"
                    f"⚠ {st['empty']} kosong"
                    f"</span> "
                    f"<span style='color:#64748b; font-size:11px;'>"
                    f"(terisi {st['filled']} dari {st['total']} isian)"
                    f"</span>"
                )

            rl = QVBoxLayout(row_card)
            rl.setContentsMargins(12, 10, 12, 10)
            rl.setSpacing(6)

            top_row = QHBoxLayout()
            lbl_stage = QLabel(f"<b style='font-size:13px; color:#0f172a;'>Tahapan {st['id']}. {st['label']}</b>")
            lbl_badge = QLabel(badge_html)
            btn_go = QPushButton("Buka Tahapan →")
            btn_go.setStyleSheet("""
                QPushButton {
                    background-color: #f1f5f9;
                    color: #0284c7;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #e0f2fe;
                    border-color: #0284c7;
                    color: #0369a1;
                }
            """)
            btn_go.clicked.connect(lambda _=False, idx=st["index"]: self.jump_to_stage(idx, dlg))

            top_row.addWidget(lbl_stage)
            top_row.addStretch()
            top_row.addWidget(lbl_badge)
            top_row.addSpacing(8)
            top_row.addWidget(btn_go)
            rl.addLayout(top_row)

            if st["empty_labels"]:
                shown = st["empty_labels"][:12]
                more = len(st["empty_labels"]) - len(shown)
                items_str = ", ".join(shown)
                if more > 0:
                    items_str += f", ... (+{more} kolom lainnya)"
                lbl_empty_list = QLabel(
                    f"<span style='color:#475569; font-size:11px;'><b>Kolom belum diisi:</b> {items_str}</span>"
                )
                lbl_empty_list.setWordWrap(True)
                rl.addWidget(lbl_empty_list)

            cl.addWidget(row_card)

        cl.addStretch()
        sc.setWidget(container)
        lay.addWidget(sc, 1)

        # Tombol Bawah Dialog Validasi
        btn_bar = QHBoxLayout()
        btn_save_draft = QPushButton("💾 Simpan Draft Sekarang")
        btn_save_draft.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 5px;
                border: 1px solid #0284c7;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        def _save_from_val():
            dlg.accept()
            self.save_file()
        btn_save_draft.clicked.connect(_save_from_val)

        btn_close = QPushButton("Tutup")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                font-weight: 500;
                padding: 7px 16px;
                border-radius: 5px;
                border: 1px solid #cbd5e1;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
            }
        """)
        btn_close.clicked.connect(dlg.accept)

        btn_bar.addWidget(btn_save_draft)
        btn_bar.addStretch()
        btn_bar.addWidget(btn_close)
        lay.addLayout(btn_bar)

        dlg.exec()

    # ---------- simpan & simpan sebagai (mendukung simpan draft maupun final) ----------
    def _write_xml_to_path(self, path):
        if self.root is None:
            return False
        self.apply_values()
        if not path.lower().endswith(".xml"):
            path += ".xml"
        try:
            out = copy.deepcopy(self.root)
            big_compat.normalize_steps(out)
            if self.cb_prune.isChecked():
                model.prune_empty(out)
            if self.cb_big.isChecked():
                out = big_compat.to_big(out)
            model.save(out, path)
        except Exception as e:
            QMessageBox.warning(self, TITLE, "Gagal menyimpan berkas XML:\n%s" % e)
            return False

        self.src = path
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        stage_stats = self.compute_stage_validation()
        self.update_nav_validation_badges(stage_stats)
        total_empty = sum(s["empty"] for s in stage_stats)
        status_tag = "Draft (%d isian belum lengkap)" % total_empty if total_empty > 0 else "Lengkap"
        self.lbl.setText("Berkas Aktif: %s  —  [Tersimpan %s | Status: %s]" % (path, now_str, status_tag))
        if hasattr(self.iface, "messageBar") and self.iface.messageBar() is not None:
            self.iface.messageBar().pushSuccess(
                TITLE,
                "Metadata (%s) berhasil disimpan ke: %s" % (status_tag, path)
            )
        return True

    def _default_save_path(self):
        """Bentuk path default dengan format <metadataidentifier>_<yyyymmdd>.xml."""
        self.apply_values()
        md_id = ""
        f_id = layout.make_field(
            self.root,
            layout.F("metadataIdentifier", "Metadata Identifier", "metadataIdentifier/code")
        )
        if f_id is not None:
            md_id = (f_id.get() or "").strip()
        if not md_id:
            for f, w in self.items:
                if getattr(f, "section", "") == "metadataIdentifier" and "code" in getattr(f, "names", ()):
                    md_id = (self.read(w) or "").strip()
                    if md_id:
                        break
        clean_id = re.sub(r'[\\/:*?"<>|\s]+', "_", md_id).strip("_") if md_id else "metadata"
        if not clean_id:
            clean_id = "metadata"
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        filename = f"{clean_id}_{date_str}.xml"
        base_dir = os.path.dirname(self.src) if self.src else os.path.expanduser("~")
        return os.path.join(base_dir, filename)

    def save_file(self):
        """Simpan (Save): langsung simpan ke berkas aktif (self.src), atau buka Simpan Sebagai bila belum ada berkas."""
        if self.root is None:
            return
        if not self.src:
            self.save_file_as()
            return
        self._write_xml_to_path(self.src)

    def save_file_as(self):
        """Simpan Sebagai (Save As): pilih lokasi berkas baru, simpan, dan jadikan berkas aktif."""
        if self.root is None:
            return
        default = self._default_save_path()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Sebagai (Save As) XML Metadata / Draft",
            default,
            "XML Metadata (*.xml)"
        )
        if not path:
            return
        if not path.lower().endswith(".xml"):
            path += ".xml"
        self._write_xml_to_path(path)

    def export_iso19139(self):
        """Ekspor isian metadata saat ini ke berkas XML standar ISO 19139 (namespace http://www.isotc211.org/2005/gmd)."""
        if self.root is None:
            QMessageBox.information(self, TITLE, "Belum ada metadata yang dimuat untuk diekspor.")
            return

        self.apply_values()

        # Bentuk default nama berkas: <metadataidentifier>_<yyyymmdd>_iso19139.xml
        md_id = ""
        f_id = layout.make_field(
            self.root,
            layout.F("metadataIdentifier", "Metadata Identifier", "metadataIdentifier/code")
        )
        if f_id is not None:
            md_id = (f_id.get() or "").strip()
        if not md_id:
            for f, w in self.items:
                if getattr(f, "section", "") == "metadataIdentifier" and "code" in getattr(f, "names", ()):
                    md_id = (self.read(w) or "").strip()
                    if md_id:
                        break
        clean_id = re.sub(r'[\\/:*?"<>|\s]+', "_", md_id).strip("_") if md_id else "metadata"
        if not clean_id:
            clean_id = "metadata"
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        filename = f"{clean_id}_{date_str}_iso19139.xml"
        base_dir = os.path.dirname(self.src) if self.src else os.path.expanduser("~")
        default_path = os.path.join(base_dir, filename)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Ekspor XML Metadata Standar ISO 19139 (gmd)",
            default_path,
            "XML Metadata ISO 19139 (*.xml);;Semua file (*)"
        )
        if not path:
            return
        if not path.lower().endswith(".xml"):
            path += ".xml"

        try:
            gmd_tree = gmd_exporter.export_to_gmd(self.root)
            gmd_exporter.save_gmd_to_file(gmd_tree, path)
        except Exception as e:
            QMessageBox.warning(self, TITLE, "Gagal mengekspor XML ISO 19139:\n%s" % e)
            return

        if hasattr(self.iface, "messageBar") and self.iface.messageBar() is not None:
            self.iface.messageBar().pushSuccess(
                TITLE,
                "Metadata berhasil diekspor ke ISO 19139 (gmd): %s" % path
            )
        QMessageBox.information(
            self,
            "Ekspor ISO 19139 Berhasil",
            "Berkas metadata berhasil diekspor dengan standar <b>ISO 19139</b> "
            "(namespace <code>http://www.isotc211.org/2005/gmd</code>):<br><br>"
            f"<b>Lokasi:</b> {path}"
        )

    def export(self):
        """Alias kompatibilitas untuk Simpan Sebagai."""
        self.save_file_as()
