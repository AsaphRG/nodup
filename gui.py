import os, sys, collections
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QMessageBox as QtQMessageBox,
    QFileDialog,
    QHeaderView,
    QDialog,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
    QFrame
)

# Importar lógica do main.py
from main import main as scan_images, buscar_duplicados, excluir_registro_e_arquivo

# Caixa de mensagem personalizada que não emite sons do sistema
class SilentMessageBox(QDialog):
    Yes = QtQMessageBox.Yes
    No = QtQMessageBox.No

    def __init__(self, parent, title, text, icon_type="info", buttons=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        self.setMinimumWidth(380)

        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Conteúdo do Ícone e Texto
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)

        self.lbl_icon = QLabel()
        self.lbl_icon.setStyleSheet("font-size: 24px;")
        if icon_type == "info":
            self.lbl_icon.setText("ℹ️")
        elif icon_type == "warning":
            self.lbl_icon.setText("⚠️")
        elif icon_type == "critical":
            self.lbl_icon.setText("❌")
        elif icon_type == "question":
            self.lbl_icon.setText("❓")

        content_layout.addWidget(self.lbl_icon)

        self.lbl_text = QLabel(text)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet("color: #E1E1E6; font-size: 13px;")
        content_layout.addWidget(self.lbl_text, 1)

        layout.addLayout(content_layout)

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if not buttons:
            buttons = [("OK", QtQMessageBox.Yes)]

        self.result_value = QtQMessageBox.No

        for btn_text, role in buttons:
            btn = QPushButton(btn_text)
            if role == QtQMessageBox.No:
                btn.setObjectName("btnNo")
            btn.clicked.connect(lambda checked=False, r=role: self.finish(r))
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

        # Estilizar o diálogo com o tema dark
        self.setStyleSheet("""
            QDialog {
                background-color: #202024;
                border: 1px solid #29292E;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #00ADB5;
                color: #EEEEEE;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #00F5FF;
                color: #121214;
            }
            QPushButton:pressed {
                background-color: #008B92;
            }
            QPushButton#btnNo {
                background-color: #29292E;
                color: #A8A8B3;
                border: 1px solid #4b5563;
            }
            QPushButton#btnNo:hover {
                background-color: #3e3e4a;
                color: #E1E1E6;
            }
        """)

    def finish(self, role):
        self.result_value = role
        if role == QtQMessageBox.Yes:
            self.accept()
        else:
            self.reject()

    @staticmethod
    def information(parent, title, text):
        dlg = SilentMessageBox(parent, title, text, "info")
        dlg.exec()

    @staticmethod
    def warning(parent, title, text):
        dlg = SilentMessageBox(parent, title, text, "warning")
        dlg.exec()

    @staticmethod
    def critical(parent, title, text):
        dlg = SilentMessageBox(parent, title, text, "critical")
        dlg.exec()

    @staticmethod
    def question(parent, title, text, buttons_mask=None):
        dlg = SilentMessageBox(parent, title, text, "question", [
            ("Sim", QtQMessageBox.Yes),
            ("Não", QtQMessageBox.No)
        ])
        if dlg.exec() == QDialog.Accepted:
            return QtQMessageBox.Yes
        return QtQMessageBox.No

# Redirecionar todas as chamadas de QMessageBox para a nossa classe silenciosa
QMessageBox = SilentMessageBox

# Thread para rodar o scanner em segundo plano
class ScanWorker(QThread):
    total_found = Signal(int)
    progress_updated = Signal(int)
    scan_finished = Signal(dict)
    scan_error = Signal(str)

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def check_cancelled(self):
        return self._is_cancelled

    def run(self):
        try:
            # Executa a varredura com callback para atualizar a interface e checar cancelamento
            resultado = scan_images(
                self.folder_path, 
                progress_callback=self.progress_updated.emit,
                total_callback=self.total_found.emit,
                cancel_callback=self.check_cancelled
            )
            self.scan_finished.emit(resultado)
        except Exception as e:
            self.scan_error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NoDup")
        self.resize(950, 680)
        self.current_duplicate_group = None # Armazena o grupo atualmente em exibição
        
        # Definir ícone da janela
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.setup_ui()
        self.apply_styles()
        self.carregar_dados() # Carrega os dados iniciais do banco se houver

    def setup_ui(self):
        # Widget Central e Layout Principal
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)

        # Abas (Tab Widget)
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # --- ABA 1: Varredura ---
        self.tab_scan = QWidget()
        self.scan_layout = QVBoxLayout(self.tab_scan)
        self.scan_layout.setContentsMargins(20, 20, 20, 20)
        self.scan_layout.setSpacing(20)

        # Instruções
        self.lbl_intro = QLabel(
            "Selecione uma pasta para escanear. O programa irá varrer todas as imagens nas subpastas, "
            "gerar o hash SHA-256 e salvar no banco de dados SQLite para identificar duplicatas."
        )
        self.lbl_intro.setWordWrap(True)
        self.scan_layout.addWidget(self.lbl_intro)

        # Campo de seleção de pasta
        self.folder_layout = QHBoxLayout()
        self.txt_folder = QLineEdit()
        self.txt_folder.setPlaceholderText("Selecione o diretório a ser varrido...")
        self.btn_browse = QPushButton("Selecionar Pasta")
        self.btn_browse.clicked.connect(self.select_folder)
        self.folder_layout.addWidget(self.txt_folder)
        self.folder_layout.addWidget(self.btn_browse)
        self.scan_layout.addLayout(self.folder_layout)

        # Botões de Ação
        self.scan_actions_layout = QHBoxLayout()
        self.btn_scan = QPushButton("Iniciar Varredura")
        self.btn_scan.setFixedHeight(45)
        self.btn_scan.clicked.connect(self.start_scan)
        
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setFixedHeight(45)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.clicked.connect(self.cancel_scan)
        
        self.scan_actions_layout.addWidget(self.btn_scan, 2)
        self.scan_actions_layout.addWidget(self.btn_cancel, 1)
        self.scan_layout.addLayout(self.scan_actions_layout)

        # Status e Progresso
        self.status_layout = QVBoxLayout()
        self.lbl_status = QLabel("Status: Aguardando pasta...")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% (%v/%m)")
        
        self.status_layout.addWidget(self.lbl_status)
        self.status_layout.addWidget(self.progress_bar)
        self.scan_layout.addLayout(self.status_layout)
        
        # Espaçador
        self.scan_layout.addStretch()

        # --- ABA 2: Resultados e Duplicados (Stacked Widget) ---
        self.tab_results = QWidget()
        self.results_layout = QVBoxLayout(self.tab_results)
        self.results_layout.setContentsMargins(15, 15, 15, 15)

        self.results_stack = QStackedWidget()
        self.results_layout.addWidget(self.results_stack)

        # ================= SUB-TELA A: Grid de Miniaturas =================
        self.page_grid = QWidget()
        self.grid_layout = QVBoxLayout(self.page_grid)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)

        # Barra de Ações do Grid
        self.grid_actions = QHBoxLayout()
        self.lbl_grid_title = QLabel("Imagens Duplicadas Encontradas")
        self.lbl_grid_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00ADB5;")
        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self.carregar_dados)
        self.grid_actions.addWidget(self.lbl_grid_title)
        self.grid_actions.addStretch()
        self.grid_actions.addWidget(self.btn_refresh)
        self.grid_layout.addLayout(self.grid_actions)

        # QListWidget no Modo Ícones
        self.thumbnail_grid = QListWidget()
        self.thumbnail_grid.setViewMode(QListWidget.IconMode)
        self.thumbnail_grid.setIconSize(QSize(120, 120))
        self.thumbnail_grid.setResizeMode(QListWidget.Adjust)
        self.thumbnail_grid.setMovement(QListWidget.Static)
        self.thumbnail_grid.setSpacing(20)
        self.thumbnail_grid.itemDoubleClicked.connect(self.mostrar_detalhes_duplicado)
        self.grid_layout.addWidget(self.thumbnail_grid)

        self.results_stack.addWidget(self.page_grid)

        # ================= SUB-TELA B: Detalhes do Duplicado =================
        self.page_details = QWidget()
        self.details_layout = QVBoxLayout(self.page_details)
        self.details_layout.setSpacing(15)
        self.details_layout.setContentsMargins(0, 0, 0, 0)

        # Cabeçalho da página de detalhes
        self.details_header = QHBoxLayout()
        self.btn_back = QPushButton("← Voltar")
        self.btn_back.clicked.connect(self.voltar_para_grid)
        self.lbl_details_title = QLabel("Locais onde a imagem foi encontrada")
        self.lbl_details_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.details_header.addWidget(self.btn_back)
        self.details_header.addWidget(self.lbl_details_title)
        self.details_header.addStretch()
        self.details_layout.addLayout(self.details_header)

        # Info de Visualização (Preview e Metadados)
        self.preview_info_frame = QFrame()
        self.preview_info_frame.setObjectName("previewInfoFrame")
        self.preview_info_layout = QHBoxLayout(self.preview_info_frame)
        self.preview_info_layout.setContentsMargins(15, 15, 15, 15)
        self.preview_info_layout.setSpacing(20)

        # Preview da imagem
        self.lbl_preview = QLabel("Carregando visualização...")
        self.lbl_preview.setFixedSize(220, 220)
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setObjectName("lblPreview")
        self.preview_info_layout.addWidget(self.lbl_preview)

        # Metadados à direita
        self.meta_layout = QVBoxLayout()
        self.meta_layout.setSpacing(10)
        
        self.lbl_meta_name = QLabel("Nome: N/A")
        self.lbl_meta_name.setStyleSheet("font-size: 14px; font-weight: bold; color: #EEEEEE;")
        self.lbl_meta_size = QLabel("Tamanho: N/A")
        self.lbl_meta_hash = QLabel("Hash SHA-256: N/A")
        self.lbl_meta_hash.setWordWrap(True)
        
        self.btn_open_full = QPushButton("Visualizar Imagem")
        self.btn_open_full.clicked.connect(self.visualizar_imagem_cheia)
        self.btn_open_full.setFixedWidth(150)
        
        self.meta_layout.addWidget(self.lbl_meta_name)
        self.meta_layout.addWidget(self.lbl_meta_size)
        self.meta_layout.addWidget(self.lbl_meta_hash)
        self.meta_layout.addWidget(self.btn_open_full)
        self.meta_layout.addStretch()

        self.preview_info_layout.addLayout(self.meta_layout, 1)
        self.details_layout.addWidget(self.preview_info_frame)

        # Tabela de localizações
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(5)
        self.detail_table.setHorizontalHeaderLabels(["ID", "Selecionar", "Pasta", "Nome do Arquivo", "Ações"])
        self.detail_table.setColumnHidden(0, True) # Esconde ID
        
        detail_header = self.detail_table.horizontalHeader()
        detail_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(2, QHeaderView.Stretch)
        detail_header.setSectionResizeMode(3, QHeaderView.Stretch)
        detail_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.detail_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.details_layout.addWidget(self.detail_table)

        # Botão de exclusão das cópias
        self.details_actions = QHBoxLayout()
        self.btn_delete_copies = QPushButton("Excluir Cópias Selecionadas")
        self.btn_delete_copies.setObjectName("btnDelete")
        self.btn_delete_copies.clicked.connect(self.excluir_copias_selecionadas)
        self.details_actions.addStretch()
        self.details_actions.addWidget(self.btn_delete_copies)
        self.details_layout.addLayout(self.details_actions)

        self.results_stack.addWidget(self.page_details)

        # Adicionar abas
        self.tabs.addTab(self.tab_scan, "Varredura")
        self.tabs.addTab(self.tab_results, "Imagens Duplicadas")

    def apply_styles(self):
        # QSS Estilizado para Dark Theme Premium
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121214;
                color: #E1E1E6;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #29292E;
                background-color: #202024;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #121214;
                color: #A8A8B3;
                padding: 12px 24px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                border: 1px solid #29292E;
                border-bottom: none;
            }
            QTabBar::tab:hover {
                background-color: #202024;
                color: #E1E1E6;
            }
            QTabBar::tab:selected {
                background-color: #202024;
                color: #00ADB5;
                font-weight: bold;
                border-bottom: 2px solid #00ADB5;
            }
            QLineEdit {
                background-color: #121214;
                color: #E1E1E6;
                border: 1px solid #29292E;
                border-radius: 6px;
                padding: 10px;
                selection-background-color: #00ADB5;
            }
            QLineEdit:focus {
                border: 1px solid #00ADB5;
            }
            QPushButton {
                background-color: #00ADB5;
                color: #EEEEEE;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00F5FF;
                color: #121214;
            }
            QPushButton:pressed {
                background-color: #008B92;
            }
            QPushButton#btnDelete {
                background-color: #E04343;
            }
            QPushButton#btnDelete:hover {
                background-color: #FF5A5A;
                color: #EEEEEE;
            }
            QPushButton#btnCancel {
                background-color: #29292E;
                color: #A8A8B3;
                border: 1px solid #4b5563;
            }
            QPushButton#btnCancel:hover {
                background-color: #E04343;
                color: #EEEEEE;
            }
            QPushButton#btnCancel:disabled {
                background-color: #1a1a1e;
                color: #555555;
                border: 1px solid #29292E;
            }
            QProgressBar {
                border: 1px solid #29292E;
                border-radius: 6px;
                text-align: center;
                background-color: #121214;
                color: #EEEEEE;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #00ADB5;
                border-radius: 5px;
            }
            QListWidget {
                background-color: #121214;
                border: 1px solid #29292E;
                border-radius: 8px;
                padding: 15px;
            }
            QListWidget::item {
                background-color: #202024;
                border: 1px solid #29292E;
                border-radius: 6px;
                padding: 10px;
                color: #E1E1E6;
                margin: 5px;
            }
            QListWidget::item:hover {
                background-color: #29292E;
                border: 1px solid #00ADB5;
            }
            QListWidget::item:selected {
                background-color: #00ADB5;
                color: #121214;
                border: 1px solid #00ADB5;
            }
            QFrame#previewInfoFrame {
                background-color: #121214;
                border: 1px solid #29292E;
                border-radius: 8px;
            }
            QLabel#lblPreview {
                background-color: #202024;
                border: 1px solid #29292E;
                border-radius: 6px;
            }
            QTableWidget {
                background-color: #202024;
                color: #E1E1E6;
                gridline-color: #29292E;
                border: 1px solid #29292E;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #121214;
                color: #A8A8B3;
                padding: 10px;
                border: 1px solid #29292E;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #293845;
                color: #ffffff;
            }
            QLabel {
                color: #C4C4CC;
            }
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                border: 2px solid #555555;
                width: 14px;
                height: 14px;
                background-color: #121214;
                border-radius: 3px;
            }
            QCheckBox::indicator:hover {
                border-color: #00ADB5;
            }
            QCheckBox::indicator:checked {
                background-color: #00ADB5;
                border-color: #00ADB5;
            }
        """)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Diretório")
        if folder:
            self.txt_folder.setText(folder)
            self.lbl_status.setText("Status: Pasta selecionada. Pronto para iniciar.")

    def start_scan(self):
        folder = self.txt_folder.text().strip()
        if not folder:
            QMessageBox.warning(self, "Erro", "Por favor, selecione uma pasta para varrer.")
            return

        self.btn_scan.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.lbl_status.setText("Status: Mapeando arquivos...")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(0) # Modo indeterminado inicialmente
        self.progress_bar.setFormat("Analisando diretório...")

        # Iniciar thread do scanner
        self.worker = ScanWorker(folder)
        self.worker.total_found.connect(self.set_progress_max)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.scan_finished.connect(self.scan_completed)
        self.worker.scan_error.connect(self.scan_failed)
        self.worker.start()

    def cancel_scan(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.btn_cancel.setEnabled(False)
            self.lbl_status.setText("Status: Cancelando varredura...")
            self.worker.cancel()

    @Slot(int)
    def update_progress(self, val):
        self.progress_bar.setValue(val)

    @Slot(dict)
    def scan_completed(self, result):
        self.btn_scan.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        
        if result.get("interrompido", False):
            self.lbl_status.setText(f"Status: Cancelado. {result['total_processado']} imagens salvas.")
            QMessageBox.information(
                self, 
                "Varredura Interrompida", 
                f"Varredura interrompida pelo usuário.\nImagens processadas e salvas até o momento: {result['total_processado']}"
            )
        else:
            self.lbl_status.setText(f"Status: Concluído! {result['total_processado']} imagens processadas.")
            num_erros = len(result['erros'])
            msg = f"Varredura concluída!\nImagens lidas e salvas: {result['total_processado']}"
            if num_erros > 0:
                msg += f"\nErros de leitura: {num_erros}"
            QMessageBox.information(self, "Varredura Concluída", msg)

        # Recarrega o grid e vai para a aba de resultados
        self.carregar_dados()
        self.results_stack.setCurrentIndex(0) # Força ir pro Grid de miniaturas
        self.tabs.setCurrentIndex(1)

    @Slot(str)
    def scan_failed(self, error_msg):
        self.btn_scan.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_status.setText("Status: Erro na varredura.")
        QMessageBox.critical(self, "Erro na Varredura", f"Ocorreu um erro: {error_msg}")

    @Slot()
    def carregar_dados(self):
        dados = buscar_duplicados()
        self.thumbnail_grid.clear()

        # Agrupar itens por hash
        self.grupos_duplicados = collections.defaultdict(list)
        for d in dados:
            self.grupos_duplicados[d['hash']].append(d)

        # Preencher a grade de miniaturas
        for h, items in self.grupos_duplicados.items():
            if not items:
                continue
            
            represetante = items[0]
            caminho_completo = os.path.join(represetante['caminho'], represetante['nome'])
            
            # Criar item
            item = QListWidgetItem()
            # Nome exibido: Nome do arquivo + quantidade de cópias
            item.setText(f"{represetante['nome']}\n({len(items)} cópias)")
            item.setTextAlignment(Qt.AlignCenter)
            
            # Carregar miniatura
            pixmap = QPixmap(caminho_completo)
            if not pixmap.isNull():
                thumbnail = pixmap.scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item.setIcon(QIcon(thumbnail))
            else:
                # Placeholder para imagem corrompida ou inacessível
                item.setText(f"[Sem visualização]\n{represetante['nome']}\n({len(items)} cópias)")

            # Armazenar o hash desse grupo no item
            item.setData(Qt.UserRole, h)
            self.thumbnail_grid.addItem(item)

    @Slot(QListWidgetItem)
    def mostrar_detalhes_duplicado(self, item):
        hash_val = item.data(Qt.UserRole)
        self.current_duplicate_group = hash_val
        
        copies = self.grupos_duplicados.get(hash_val, [])
        if not copies:
            return

        represetante = copies[0]
        caminho_img = os.path.join(represetante['caminho'], represetante['nome'])

        # Atualizar imagem de preview
        pixmap = QPixmap(caminho_img)
        if not pixmap.isNull():
            self.lbl_preview.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.lbl_preview.setText("[Sem prévia]")

        # Metadados
        self.lbl_meta_name.setText(f"Nome: {represetante['nome']}")
        self.lbl_meta_hash.setText(f"Hash SHA-256: {hash_val}")
        
        # Calcular tamanho formatado
        tamanho_str = "Tamanho: Desconhecido"
        if os.path.exists(caminho_img):
            tamanho_bytes = os.path.getsize(caminho_img)
            if tamanho_bytes < 1024:
                tamanho_str = f"Tamanho: {tamanho_bytes} B"
            elif tamanho_bytes < 1024 * 1024:
                tamanho_str = f"Tamanho: {tamanho_bytes / 1024:.1f} KB"
            else:
                tamanho_str = f"Tamanho: {tamanho_bytes / (1024 * 1024):.1f} MB"
        self.lbl_meta_size.setText(tamanho_str)

        # Preencher tabela de localizações
        self.detail_table.setRowCount(0)
        row_count = 0
        for copy in copies:
            self.detail_table.insertRow(row_count)

            # Coluna 0: ID (oculto)
            id_item = QTableWidgetItem(str(copy['id']))
            self.detail_table.setItem(row_count, 0, id_item)

            # Coluna 1: Checkbox
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            chk.setProperty("id_registro", copy['id'])
            chk.setProperty("caminho_arquivo", os.path.join(copy['caminho'], copy['nome']))
            chk_layout.addWidget(chk)
            chk_widget.setStyleSheet("background-color: transparent;")
            self.detail_table.setCellWidget(row_count, 1, chk_widget)

            # Coluna 2: Pasta
            caminho_item = QTableWidgetItem(copy['caminho'])
            caminho_item.setFlags(caminho_item.flags() ^ Qt.ItemIsEditable)
            self.detail_table.setItem(row_count, 2, caminho_item)

            # Coluna 3: Nome do Arquivo
            nome_item = QTableWidgetItem(copy['nome'])
            nome_item.setFlags(nome_item.flags() ^ Qt.ItemIsEditable)
            self.detail_table.setItem(row_count, 3, nome_item)

            # Coluna 4: Ação (Abrir pasta no Windows Explorer)
            btn_open_dir = QPushButton("Abrir Pasta")
            btn_open_dir.setStyleSheet("""
                QPushButton {
                    background-color: #29292E;
                    color: #FFFFFF;
                    border: 1px solid #4b5563;
                    padding: 0px 0px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #3e3e4a;
                    color: #00ADB5;
                }
            """)
            btn_open_dir.clicked.connect(lambda checked=False, p=copy['caminho']: self.abrir_pasta(p))
            self.detail_table.setCellWidget(row_count, 4, btn_open_dir)

            row_count += 1

        # Mudar para a tela de detalhes
        self.results_stack.setCurrentIndex(1)

    def abrir_pasta(self, caminho_pasta):
        if os.path.exists(caminho_pasta):
            try:
                os.startfile(caminho_pasta)
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Não foi possível abrir a pasta: {e}")
        else:
            QMessageBox.warning(self, "Erro", f"A pasta não existe mais no disco:\n{caminho_pasta}")

    def visualizar_imagem_cheia(self):
        # Abre a imagem atual no visualizador do sistema
        if not self.current_duplicate_group:
            return
        
        copies = self.grupos_duplicados.get(self.current_duplicate_group, [])
        if copies:
            caminho_img = os.path.join(copies[0]['caminho'], copies[0]['nome'])
            if os.path.exists(caminho_img):
                try:
                    os.startfile(caminho_img)
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Não foi possível abrir a imagem: {e}")
            else:
                QMessageBox.warning(self, "Erro", "A imagem selecionada não existe mais no disco.")

    @Slot()
    def voltar_para_grid(self):
        self.results_stack.setCurrentIndex(0)
        self.carregar_dados()

    def excluir_copias_selecionadas(self):
        selecionadas = []
        for r in range(self.detail_table.rowCount()):
            chk_widget = self.detail_table.cellWidget(r, 1)
            if chk_widget:
                chk = chk_widget.findChild(QCheckBox)
                if chk and chk.isChecked():
                    id_reg = chk.property("id_registro")
                    caminho_arq = chk.property("caminho_arquivo")
                    selecionadas.append((id_reg, caminho_arq))

        if not selecionadas:
            QMessageBox.information(self, "Nenhuma Seleção", "Marque as checkboxes dos caminhos que deseja excluir.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Você selecionou {len(selecionadas)} cópia(s) desta imagem.\n\n"
            "Deseja excluir permanentemente estes arquivos físicos do disco?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            erros = []
            sucessos = 0
            for id_reg, caminho_arq in selecionadas:
                try:
                    excluir_registro_e_arquivo(id_reg)
                    sucessos += 1
                except Exception as e:
                    erros.append(f"{os.path.basename(caminho_arq)}: {e}")

            if erros:
                msg_erros = "\n".join(erros[:5])
                if len(erros) > 5:
                    msg_erros += "\n..."
                QMessageBox.warning(
                    self,
                    "Concluído com Alertas",
                    f"Excluídas {sucessos} cópias com sucesso.\n\nFalhas:\n{msg_erros}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Exclusão Concluída",
                    f"Todas as {sucessos} cópias selecionadas foram excluídas com sucesso do disco e do banco!"
                )

            # Recarrega o banco e verifica se esse grupo ainda possui duplicados
            self.carregar_dados()
            
            # Se restou apenas 1 cópia (ou nenhuma), o grupo não é mais considerado duplicado! Voltar ao grid.
            copies_restantes = self.grupos_duplicados.get(self.current_duplicate_group, [])
            if len(copies_restantes) <= 1:
                QMessageBox.information(
                    self, 
                    "Grupo Limpo", 
                    "Este arquivo não possui mais duplicatas (restou apenas uma cópia ou nenhuma).\nRetornando à grade principal."
                )
                self.voltar_para_grid()
            else:
                # Caso contrário, recarregar a própria tela de detalhes
                # Simula um clique no mesmo grupo para reconstruir os detalhes das cópias restantes
                mock_item = QListWidgetItem()
                mock_item.setData(Qt.UserRole, self.current_duplicate_group)
                self.mostrar_detalhes_duplicado(mock_item)

    @Slot(int)
    def set_progress_max(self, total):
        self.progress_bar.setMaximum(total if total > 0 else 100)
        self.progress_bar.setFormat("%p% (%v/%m)")
        self.lbl_status.setText(f"Status: Processando {total} imagens...")

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.lbl_status.setText("Aguardando finalização das tarefas...")
            self.worker.cancel()
            self.worker.wait()
        event.accept()

if __name__ == "__main__":
    # Evita que o ícone do terminal/python substitua o ícone customizado na barra de tarefas do Windows
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("nodup.imageduplicatesfinder.1.0")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
