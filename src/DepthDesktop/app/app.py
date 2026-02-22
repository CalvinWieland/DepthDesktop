import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QLabel, QWidget, QHBoxLayout, QGraphicsOpacityEffect, QGraphicsDropShadowEffect)
from PyQt6.QtGui import QPixmap, QFont, QAction, QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QPoint, QEasingCurve
from faceTracking import runTracker
from datetime import datetime, timedelta
import platform
import subprocess

DISABLE_HEAD_NAV = False

class TrackerThread(QThread):
    data_received = pyqtSignal(float, float, float, int, int)

    def run(self):
        for update in runTracker(False):
            self.data_received.emit(*update)

class DesktopApp(QMainWindow):
    invalidTime = datetime.now()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyQt6 OS Simulator")
        self.resize(800, 500)
        #self.setStyleSheet("background-color: #981E32; color: white;")
        self.setStyleSheet("QMainWindow { background-color: qlineargradient( x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #981E32, stop: 1 #FF9249);} color: white;")

        self.tracker_thread = TrackerThread()
        self.tracker_thread.data_received.connect(self.handle_tracker_update)
        self.tracker_thread.start()

        self.current_index = 0
        self.card_width = 250
        self.spacing = 50
        
        self.apps = [
            {"name": "Browser", "icon":"icons/browser.png", "path": "Browser"},
            {"name": "Files", "icon":"icons/file_sys2.png", "path": Path.cwd()},
            {"name": "Terminal", "icon":"icons/terminal.png", "path": "Terminal"},
            {"name": "Settings", "icon":"icons/settings3.png", "path": "Settings"}
        ]

        self.viewport = QWidget(self)
        self.setCentralWidget(self.viewport)
        
        self.strip = QWidget(self.viewport)
        self.strip_layout = QHBoxLayout(self.strip)
        self.strip_layout.setSpacing(self.spacing)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)

        self.cards = []
        self.setup_cards()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


    def clear_layout(self, layout):
        """Physically deletes all widgets currently in the layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def setup_cards(self):
        self.clear_layout(self.strip_layout)
        self.cards.clear()

        # resize strip based on # of icons
        num_apps = len(self.apps)
        total_width = (num_apps * self.card_width) + (max(0, num_apps - 1) * self.spacing)
        self.strip.setFixedSize(total_width, 400)

        # create new cards
        for app in self.apps:
            card = QWidget()
            card.setFixedSize(self.card_width, 350)

            shadow_effect = QGraphicsDropShadowEffect()
            shadow_effect.setColor(QColor(0, 0, 0, 150))
            shadow_effect.setOffset(8, 8)
            shadow_effect.setBlurRadius(15)

            card.setGraphicsEffect(shadow_effect)

            layout = QVBoxLayout(card)
            
            icon_label = QLabel()
            icon_label.setFixedSize(200, 200)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # get actual icon image for widget
            pixmap = QPixmap(str(app['icon']))
            if pixmap.isNull():
                icon_label.setStyleSheet("background-color: #333; border-radius: 20px;")
                icon_label.setText("No Icon")
            else:
                scaled_pixmap = pixmap.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon_label.setPixmap(scaled_pixmap)
            
            # get/set icon label
            name_label = QLabel(str(app['name']))
            name_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setWordWrap(True)

            layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignCenter)
            
            self.strip_layout.addWidget(card)
            self.cards.append(card)

        self.current_index = 0
        self.update_carousel(animate=False)

    def handle_tracker_update(self, z, angleY, angleX, directionX, directionY):
        if (datetime.now() > self.invalidTime):
            if (not DISABLE_HEAD_NAV):
                if directionX == 1:
                    self.current_index = (self.current_index + 1) % len(self.apps)
                    self.update_carousel()
                    self.invalidTime = datetime.now() + timedelta(milliseconds=500)
                elif directionX == -1:
                    self.current_index = (self.current_index - 1) % len(self.apps)
                    self.update_carousel()
                    self.invalidTime = datetime.now() + timedelta(milliseconds=500)
                elif directionY == 1:
                    selected_app = self.apps[self.current_index]['path']
                    self.launch_app(selected_app)
                    self.invalidTime = datetime.now() + timedelta(milliseconds=800)
                elif directionY == -1:
                    sys.exit(app.exec())
        for curCard in self.cards:
            shadow_effect = QGraphicsDropShadowEffect()
            shadow_effect.setColor(QColor(0, 0, 0, 150))
            shadow_effect.setOffset(angleX * 1, angleY * 1)
            shadow_effect.setBlurRadius(15)

            curCard.setGraphicsEffect(shadow_effect)

    def update_carousel(self, animate=True):
        if not self.cards: return
        
        viewport_center = self.width() // 2
        target_card_pos = (self.current_index * (self.card_width + self.spacing)) + (self.card_width // 2)
        new_x = viewport_center - target_card_pos
        new_y = (self.height() // 2) - (self.strip.height() // 2)

        for i, card in enumerate(self.cards):
            #card.setGraphicsEffect(None)
            opacity = 1.0 if i == self.current_index else 0.4
            fade = QGraphicsOpacityEffect()
            fade.setOpacity(opacity)
            #card.setGraphicsEffect(fade)

        if animate:
            self.anim = QPropertyAnimation(self.strip, b"pos")
            self.anim.setDuration(400)
            self.anim.setEndValue(QPoint(int(new_x), int(new_y)))
            self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim.start()
        else:
            self.strip.move(int(new_x), int(new_y))

    def launch_app(self, name):
        # convert path to string
        name_str = str(name)
        
        # check if on Mac
        if platform.system() == 'Darwin':
            # choose where to go
            if name_str == "Browser":
                subprocess.run(["open", "-a", "Firefox"])
            # if selects files, take user to file system
            elif name_str == "Files":
                directory_path = Path.cwd()
                print("\n\n\n", directory_path)
                self.apps = []
                # create "app" icons for each file/folder
                self.apps.append({"name": "..", "icon":"icons/file_sys2.png", "path": directory_path.parent})
                for entry in directory_path.iterdir():
                    if entry.is_dir():
                        self.apps.append({"name": entry.name, "icon":"icons/file_sys2.png", "path":entry.absolute()})
                    else:
                        self.apps.append({"name": entry.name, "icon":"icons/file_icon.png", "path":entry.absolute()})

                self.setup_cards()
            elif name_str == "Terminal":
                subprocess.run(["open", "-a", "Terminal"])
            elif name_str == "Settings":
                subprocess.run(["open", "-a", "System Settings"])
            # if in the file system and user selects directroy, take the user to that directory
            elif isinstance(name, Path) and name.is_dir():
                print("is path lol\n\n\n")
                directory_path = name.absolute()
                print(directory_path)
                self.apps = []
                self.apps.append({"name": "..", "icon":"icons/file_sys2.png", "path": directory_path.parent})
                for entry in directory_path.iterdir():
                    if entry.is_dir():
                        self.apps.append({"name": entry.name, "icon":"icons/file_sys2.png", "path":entry.absolute()})
                    else:
                        self.apps.append({"name": entry.name, "icon":"icons/file_icon.png", "path":entry.absolute()})

                self.setup_cards()
            else:
                try:
                    subprocess.run(["open", name_str])
                except:
                    print(f"Clicked on: {name_str}")

    # for keyboard inputs
    def keyPressEvent(self, event):        
        if event.key() == Qt.Key.Key_Right:
            self.current_index = (self.current_index + 1) % len(self.apps)
            self.update_carousel()
        elif event.key() == Qt.Key.Key_Left:
            self.current_index = (self.current_index - 1) % len(self.apps)
            self.update_carousel()
        elif event.key() == Qt.Key.Key_Return:
            self.launch_app(self.apps[self.current_index]['path'])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DesktopApp()
    window.show()
    sys.exit(app.exec())