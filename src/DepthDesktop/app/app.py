import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QLabel, QWidget, QStackedWidget, QHBoxLayout, QToolBar, QGraphicsOpacityEffect)
from PyQt6.QtGui import QIcon, QPixmap, QFont, QAction
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QPropertyAnimation, QPoint, QEasingCurve
from faceTracking import runTracker
from datetime import datetime, timedelta
import platform
import subprocess

class TrackerThread(QThread):
    # This signal will send: (z_depth, real_y, real_x, xDirection)
    data_received = pyqtSignal(float, float, float, int, int)

    def run(self):
        # This runs in the background
        for update in runTracker(False):
            # update is (corrected_z_depth, real_y, real_x, xDirection)
            self.data_received.emit(*update)

class DesktopApp(QMainWindow):
    invalidTime = datetime.now()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyQt6 OS Simulator")
        self.resize(800, 500)
        self.setStyleSheet("background-color: #981E32; color: white;")

        self.tracker_thread = TrackerThread()
        self.tracker_thread.data_received.connect(self.handle_tracker_update)
        self.tracker_thread.start()

        self.current_index = 0
        self.card_width = 250
        self.spacing = 50
        
        # 2. Define our "Apps" (Name, Placeholder Color/Icon)
        self.apps = [
            {"name": "Browser", "icon":"icons/browser.png"},
            {"name": "Files", "icon":"icons/file_sys.png"},
            {"name": "Terminal", "icon":"icons/terminal.png"},
            {"name": "Settings", "icon":"icons/settings.png"}
        ]

        # 2. The Viewport (A clip-box that stays still)
        self.viewport = QWidget(self)
        self.setCentralWidget(self.viewport)
        
        # 3. The Sliding Strip (The long row of apps)
        self.strip = QWidget(self.viewport)
        self.strip_layout = QHBoxLayout(self.strip)
        self.strip_layout.setSpacing(self.spacing)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)

        self.cards = []
        self.setup_cards()
        
        # Adjust the strip size to fit all cards
        total_width = (len(self.apps) * self.card_width) + ((len(self.apps)-1) * self.spacing)
        self.strip.setFixedSize(total_width, 400)

        # 4. Initial Positioning
        self.update_carousel(animate=False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def handle_tracker_update(self, z, y, x, directionX, directionY):
        # if direction is left or right, move icon left/right
        if (datetime.now() > self.invalidTime):
            if directionX == 1:
                self.current_index = (self.current_index + 1) % len(self.apps)
                self.update_carousel()
                self.invalidTime = datetime.now() + timedelta(milliseconds=500)
            elif directionX == -1:
                self.current_index = (self.current_index - 1) % len(self.apps)
                self.update_carousel()
                self.invalidTime = datetime.now() + timedelta(milliseconds=500)
            elif directionY == 1:
                selected_app = self.apps[self.current_index]['name']
                self.launch_app(selected_app)
                self.invalidTime = datetime.now() + timedelta(milliseconds=500)

    def create_actions(self):
        self.exit_action = QAction("&Exit", self)
        self.exit_action.triggered.connect(self.close)

    def setup_cards(self):
        """Creates the visual cards for the carousel."""
        for app in self.apps:
            card = QWidget()
            card.setFixedSize(self.card_width, 350)
            layout = QVBoxLayout(card)
            
            icon_label = QLabel()
            icon_label.setFixedSize(200, 200) # Bigger for high-res PNGs
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # 2. Load the PNG into a QPixmap
            pixmap = QPixmap(app['icon'])

            # Check if the image loaded correctly
            if pixmap.isNull():
                # Fallback if PNG is missing: just a gray box
                icon_label.setStyleSheet("background-color: #333; border-radius: 20px;")
                icon_label.setText("Image Not Found")
            else:
                # Scale the image to fit the label while keeping the aspect ratio
                scaled_pixmap = pixmap.scaled(
                    180, 180, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label.setPixmap(scaled_pixmap)
            
            name = QLabel(app['name'])
            name.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)

            layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(name, alignment=Qt.AlignmentFlag.AlignCenter)
            
            self.strip_layout.addWidget(card)
            self.cards.append(card)

    def update_carousel(self, animate=True):
        """Calculates where the strip should slide to center the active app."""
        # Math: Center of viewport - (center of the target card)
        viewport_center = self.width() // 2
        target_card_pos = (self.current_index * (self.card_width + self.spacing)) + (self.card_width // 2)
        new_x = viewport_center - target_card_pos
        new_y = (self.height() // 2) - (self.strip.height() // 2)

        # Update visual focus (Opacity effect)
        for i, card in enumerate(self.cards):
            card.setGraphicsEffect(None)

            if i == self.current_index:
                opacity = 1
            else:
                opacity = 0.5

            fade = QGraphicsOpacityEffect()
            fade.setOpacity(opacity)
            card.setGraphicsEffect(fade)

        if animate:
            self.anim = QPropertyAnimation(self.strip, b"pos")
            self.anim.setDuration(400)
            self.anim.setEndValue(QPoint(new_x, new_y))
            self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim.start()
        else:
            self.strip.move(new_x, new_y)

    def keyPressEvent(self, event):        
        if event.key() == Qt.Key.Key_Right:
            self.current_index = (self.current_index + 1) % len(self.apps)
            self.update_carousel()
        elif event.key() == Qt.Key.Key_Left:
            self.current_index = (self.current_index - 1) % len(self.apps)
            self.update_carousel()

        elif event.key() == Qt.Key.Key_Return:
            selected_app = self.apps[self.current_index]['name']
            self.launch_app(selected_app)

        else:
            # Let other keys behave normally
            super().keyPressEvent(event)

    def launch_app(self, name):
        
        if platform.system() == 'Darwin':
            if name == "Browser":
                subprocess.run(["open", "-a", "Firefox"])
            elif name == "Files":
                subprocess.run(["open", "-a", "Finder"])
            elif name == "Terminal":
                subprocess.run(["open", "-a", "Terminal"])
            elif name == "Settings":
                subprocess.run(["open", "-a", "System Settings"])
            else:
                print("Error")
        else:
            if name == "Browser":
                os.startfile("iexplore.exe")
            elif name == "Files":
                os.startfile("explorer.exe")
            elif name == "Terminal":
                os.startfile("wt.exe")
            elif name == "Settings":
                os.startfile("ms-settings:")
            else:
                print("Error")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DesktopApp()
    window.show()
    sys.exit(app.exec())