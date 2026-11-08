"""Estilo geral do app.

Hierarquia de botões (do mais forte para o mais discreto), usada em todas as telas:
- padrão (sem objectName) ou "Primary": a ação principal da tela — só uma por área;
- "AddStore"/"Success": criar ou adicionar algo (verde);
- "Secondary": ação de apoio (azul claro);
- "Ghost": navegação e cancelar (branco com borda);
- "Link": ação pequena em texto;
- "Danger": excluir/remover.
"""

APP_QSS = r"""
* { font-family: "Segoe UI"; }
QMainWindow, QWidget { background: #F4F7FC; color: #16233F; }
QDialog { background: #F4F7FC; }
QWidget#Shell { background: #F4F7FC; }
/* Textos e caixas de marcação nunca pintam fundo próprio: assim não aparecem faixas
   cinza atrás dos textos dentro dos cards brancos. */
QLabel, QCheckBox, QRadioButton { background: transparent; }
QWidget#PanelBody, QWidget#Transparent { background: transparent; }

QLabel#Title { font-size: 30px; font-weight: 900; color: #102A56; }
QLabel#PageTitle { font-size: 24px; font-weight: 900; color: #12213D; }
QLabel#Subtitle { color: #66758F; font-size: 13px; }
QLabel#Crumb { color: #64728A; font-size: 12px; font-weight: 800; }
QLabel#SectionTitle { color: #142B52; font-size: 16px; font-weight: 900; }
QLabel#SectionHint { color: #7A879D; font-size: 11px; font-weight: 600; }
QLabel#Eyebrow { color: #2854D9; font-size: 11px; font-weight: 900; letter-spacing: 1.5px; }
QLabel#Muted { color: #7A879D; font-size: 11px; }
QLabel#FieldLabel { color: #40516E; font-size: 11px; font-weight: 900; letter-spacing: 0.6px; }
QLabel#StepBadge { background: #2F5BEA; color: #FFFFFF; border-radius: 13px; font-size: 12px; font-weight: 900; }
QLabel#StepTitle { color: #12213D; font-size: 15px; font-weight: 900; }

QFrame#Card, QFrame#GlassCard { background: #FFFFFF; border: 1px solid #DDE6F3; border-radius: 18px; }
QFrame#KpiCard { background: #FFFFFF; border: 1px solid #DCE6F4; border-radius: 18px; }
QFrame#KpiCard:hover { border: 1px solid #6E8DFF; background: #FBFDFF; }
QFrame#Panel { background: #FFFFFF; border: 1px solid #DCE6F2; border-radius: 20px; }
QFrame#TopRank { background: #FFFFFF; border: 1px solid #DCE6F2; border-radius: 16px; }
QFrame#TopRank:hover { border: 1px solid #8CA4FF; background: #FBFCFF; }
QFrame#Divider { background: #E3EAF4; border: none; max-height: 1px; min-height: 1px; }

QPushButton { background: #2F5BEA; color: white; border: none; border-radius: 12px; padding: 11px 18px; font-weight: 800; }
QPushButton:hover { background: #244DD0; }
QPushButton:pressed { background: #1B3EAF; }
QPushButton:disabled { background: #DCE3EF; color: #8C99AE; }
QPushButton:focus { outline: none; }
QPushButton#Primary { background: #2F5BEA; color: #FFFFFF; }
QPushButton#Primary:hover { background: #244DD0; }
QPushButton#Secondary { background: #E8EEFF; color: #2854D9; }
QPushButton#Secondary:hover { background: #DCE6FF; }
QPushButton#Secondary:disabled { background: #F1F4FA; color: #A3AEC0; }
QPushButton#Ghost { background: #FFFFFF; color: #40516E; border: 1px solid #D8E2F0; }
QPushButton#Ghost:hover { background: #EEF4FF; color: #2854D9; border-color: #AFC2FF; }
QPushButton#Ghost:disabled { background: #FFFFFF; color: #B4BECD; border-color: #E6ECF4; }
QPushButton#Link { background: transparent; color: #2F5BEA; border: none; padding: 6px 8px; font-weight: 900; }
QPushButton#Link:hover { color: #1B3EAF; text-decoration: underline; }
QPushButton#Link:disabled { color: #B4BECD; }
QPushButton#Danger { background: #FFF0F2; color: #D9284B; border: 1px solid #FFD0D9; }
QPushButton#Danger:hover { background: #FFE0E6; border-color: #F5A3B3; }
QPushButton#AddStore, QPushButton#Success { background: #08A88F; color: #FFFFFF; }
QPushButton#AddStore:hover, QPushButton#Success:hover { background: #078F7A; }
QPushButton#AddStore:disabled, QPushButton#Success:disabled { background: #D8E0E9; color: #8793A5; }

QLineEdit, QComboBox, QDateEdit { background: #FFFFFF; border: 1px solid #D6E0EE; border-radius: 12px; padding: 10px 12px; min-height: 20px; color: #172846; }
QLineEdit:hover, QComboBox:hover, QDateEdit:hover { border: 1px solid #B8C8E6; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 1px solid #718FFF; }
QComboBox::drop-down, QDateEdit::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView { background: #FFFFFF; border: 1px solid #D6E0EE; border-radius: 10px; padding: 4px;
    selection-background-color: #EEF3FF; selection-color: #17326F; outline: none; }
QCheckBox { color: #233451; spacing: 7px; }

QToolTip { background: #12213D; color: #FFFFFF; border: none; border-radius: 8px; padding: 7px 10px; font-size: 11px; }
QMenu { background: #FFFFFF; border: 1px solid #D6E0EE; border-radius: 10px; padding: 5px; }
QMenu::item { padding: 7px 18px; border-radius: 6px; color: #16233F; background: transparent; }
QMenu::item:selected { background: #EEF3FF; color: #17326F; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 9px; background: transparent; margin: 2px; }
QScrollBar::handle:vertical { background: #B7C8EA; border-radius: 4px; min-height: 45px; }
QScrollBar::handle:vertical:hover { background: #7C9BDE; }
QScrollBar:horizontal { height: 9px; background: transparent; margin: 2px; }
QScrollBar::handle:horizontal { background: #B7C8EA; border-radius: 4px; min-width: 45px; }
QScrollBar::handle:horizontal:hover { background: #7C9BDE; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

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
/* Grade de cards (exploradores): o card já desenha borda e hover; o item da lista fica invisível. */
QListWidget#CardGrid::item, QListWidget#CardGrid::item:hover, QListWidget#CardGrid::item:selected
    { border: none; background: transparent; padding: 0; margin: 0; }
"""
