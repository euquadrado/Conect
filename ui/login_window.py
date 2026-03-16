from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .dashboard_window import DashboardWindow


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.dashboard = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Conect - Login")
        self.resize(430, 540)
        self.setStyleSheet(
            "QWidget { background-color: #f4f8fc; font-family: Segoe UI, Arial; }"
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(18)

        title = QLabel("Conect")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 26, QFont.Bold))
        title.setStyleSheet("color: #0f4c8a;")

        subtitle = QLabel("Acesso remoto com nova interface")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #5f7892; font-size: 14px;")

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: white; border: 1px solid #d6e2f0; border-radius: 18px; }"
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(26, 26, 26, 26)
        card_layout.setSpacing(14)

        login_label = QLabel("Entrar no sistema")
        login_label.setStyleSheet("color: #0f4c8a; font-size: 20px; font-weight: 700;")

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Usuário")
        self.user_input.setStyleSheet(self.input_style())

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(self.input_style())

        login_button = QPushButton("Entrar")
        login_button.setCursor(Qt.PointingHandCursor)
        login_button.setStyleSheet(self.primary_button_style())
        login_button.clicked.connect(self.login)

        info = QLabel("Usuário de teste: admin | Senha: 1234")
        info.setStyleSheet("color: #6f879f; font-size: 12px;")

        card_layout.addWidget(login_label)
        card_layout.addWidget(self.user_input)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(login_button)
        card_layout.addWidget(info)

        footer = QLabel("Conect UI - PySide6")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #8aa0b7; font-size: 12px;")

        main_layout.addStretch()
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(card)
        main_layout.addWidget(footer)
        main_layout.addStretch()

    def input_style(self):
        return (
            "QLineEdit { background-color: #f8fbfe; border: 1px solid #d1deec; border-radius: 12px; "
            "padding: 12px; font-size: 14px; color: #1f2d3a; }"
            "QLineEdit:focus { border: 2px solid #1565c0; background-color: white; }"
        )

    def primary_button_style(self):
        return (
            "QPushButton { background-color: #1565c0; color: white; border: none; border-radius: 12px; "
            "padding: 12px; font-size: 15px; font-weight: 700; }"
            "QPushButton:hover { background-color: #0f56a7; }"
            "QPushButton:pressed { background-color: #0b4788; }"
        )

    def login(self):
        user = self.user_input.text().strip()
        password = self.password_input.text().strip()
        if user == "admin" and password == "1234":
            self.dashboard = DashboardWindow()
            self.dashboard.show()
            self.close()
        else:
            QMessageBox.warning(self, "Login inválido", "Usuário ou senha incorretos.")
