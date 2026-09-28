APP_QSS = r"""
* { font-family: "Segoe UI"; }
QMainWindow, QWidget { background: #F4F7FC; color: #16233F; }
QWidget#Shell { background: #F4F7FC; }
QLabel#Title { font-size: 30px; font-weight: 900; color: #102A56; }
QLabel#Subtitle { color: #66758F; font-size: 13px; }
QLabel#SectionTitle { color: #142B52; font-size: 16px; font-weight: 900; }
QLabel#Muted { color: #7A879D; font-size: 11px; }
QFrame#Card, QFrame#GlassCard { background: #FFFFFF; border: 1px solid #DDE6F3; border-radius: 18px; }
QFrame#KpiCard { background: #FFFFFF; border: 1px solid #DCE6F4; border-radius: 18px; }
QFrame#KpiCard:hover { border: 1px solid #6E8DFF; background: #FBFDFF; }
QFrame#Panel { background: #FFFFFF; border: 1px solid #DCE6F2; border-radius: 20px; }
QFrame#TopRank { background: #FFFFFF; border: 1px solid #DCE6F2; border-radius: 18px; }
QFrame#TopRank:hover { border: 1px solid #8CA4FF; background: #FBFCFF; }
QPushButton { background: #2F5BEA; color: white; border: none; border-radius: 12px; padding: 11px 18px; font-weight: 800; }
QPushButton:hover { background: #244DD0; }
QPushButton:pressed { background: #1B3EAF; }
QPushButton#Secondary { background: #E8EEFF; color: #2854D9; }
QPushButton#Secondary:hover { background: #DCE6FF; }
QPushButton#Ghost { background: #FFFFFF; color: #40516E; border: 1px solid #D8E2F0; }
QPushButton#Ghost:hover { background: #EEF4FF; color: #2854D9; border-color: #AFC2FF; }
QPushButton#Danger { background: #FFF0F2; color: #D9284B; border: 1px solid #FFD0D9; }
QPushButton#AddStore { background: #08A88F; }
QPushButton#AddStore:hover { background: #078F7A; }
QLineEdit, QComboBox, QDateEdit { background: #FFFFFF; border: 1px solid #D6E0EE; border-radius: 12px; padding: 10px 12px; min-height: 20px; color: #172846; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 1px solid #718FFF; }
QComboBox::drop-down { border: none; width: 28px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 9px; background: transparent; margin: 2px; }
QScrollBar::handle:vertical { background: #B7C8EA; border-radius: 4px; min-height: 45px; }
QScrollBar::handle:vertical:hover { background: #7C9BDE; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QTableWidget { background: #FFFFFF; border: 1px solid #DCE5F1; border-radius: 14px; gridline-color: #E8EDF5; alternate-background-color: #F7F9FD; selection-background-color: #E9EEFF; selection-color: #17326F; }
QTableWidget::item { padding: 9px; }
QHeaderView::section { background: #EFF4FF; color: #24446F; padding: 11px 8px; border: none; border-bottom: 2px solid #C8D7F5; font-weight: 900; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #E9EEF7; color: #66738A; padding: 9px 15px; border-radius: 10px; margin-right: 5px; font-weight: 700; }
QTabBar::tab:selected { background: #2854D9; color: white; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { border-radius: 18px; padding: 12px; margin: 5px; color: #152846; border: 1px solid #DCE5F2; }
QListWidget::item:hover { border: 1px solid #7594F5; background: #F7FAFF; }
QListWidget::item:selected { border: 2px solid #4C6FFF; background: #EEF3FF; color: #132E63; }
"""
