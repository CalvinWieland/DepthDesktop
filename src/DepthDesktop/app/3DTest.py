import sys
import subprocess
import platform
from datetime import datetime, timedelta

# PyQt6 Core Imports
from PyQt6.QtCore import (Qt, QThread, pyqtSignal, pyqtProperty, QObject, 
                          QUrl, QTimer, QSize)

# PyQt6 GUI & 3D Imports
from PyQt6.QtGui import (QGuiApplication, QVector3D, QColor, QQuaternion, QMatrix4x4)
from PyQt6.Qt3DCore import QEntity, QTransform
from PyQt6.Qt3DRender import QTextureImage, QTexture2D
from PyQt6.Qt3DExtras import (Qt3DWindow, QPhongMaterial, QTorusMesh, 
                              QPlaneMesh, QText2DEntity, QTextureMaterial)

# Your custom tracker (Ensure faceTracking.py is in the same folder)
from faceTracking import runTracker

class TrackerThread(QThread):
    # Sends: (z_depth, real_y, real_x, directionX, directionY)
    data_received = pyqtSignal(float, float, float, int, int)

    def run(self):
        # Pass False to avoid CV2 window popping up
        for update in runTracker(False):
            self.data_received.emit(*update)

class OrbitController(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self._target = None
        self._matrix = QMatrix4x4()
        self._angle = 0

    def setTarget(self, t): self._target = t

    @pyqtProperty(float)
    def angle(self): return self._angle
    
    @angle.setter
    def angle(self, val):
        self._angle = val
        self.updateMatrix()

    def updateMatrix(self):
        if self._target:
            m = QMatrix4x4()
            m.rotate(self._angle, QVector3D(0, 1, 0))
            self._target.setMatrix(m)

class SpatialWindow(Qt3DWindow):
    def __init__(self):
        super().__init__()
        self.invalidTime = datetime.now()
        self.current_index = 0
        
        self.apps = [
            {"name": "Browser", "icon": "icons/browser.png"},
            {"name": "Files", "icon": "icons/file_sys.png"},
            {"name": "Terminal", "icon": "icons/terminal.png"},
            {"name": "Settings", "icon": "icons/settings.png"}
        ]

        # Camera Setup
        self.camera().lens().setPerspectiveProjection(45, 16/9, 0.1, 1000)
        self.camera().setPosition(QVector3D(0, 0, 40))
        self.camera().setViewCenter(QVector3D(0, 0, 0))

        # Root Scene
        self.rootEntity = QEntity()
        self.create_spatial_scene()
        self.setRootEntity(self.rootEntity)

        # Start Tracking
        self.tracker = TrackerThread()
        self.tracker.data_received.connect(self.handle_tracker_update)
        self.tracker.start()

    def create_spatial_scene(self):
        import math
        from PyQt6.Qt3DRender import QPointLight
        
        # 1. The Light Source (Parented to the Camera or Root)
        # We'll create a "Headlamp" that follows your face
        self.lightEntity = QEntity(self.rootEntity)
        self.light = QPointLight(self.lightEntity)
        self.light.setColor(QColor("white"))
        self.light.setIntensity(1.2) # Adjust brightness here
        
        self.lightTransform = QTransform()
        self.lightEntity.addComponent(self.light)
        self.lightEntity.addComponent(self.lightTransform)

        # 2. Background Torus (The "Engine Core")
        self.torusEntity = QEntity(self.rootEntity)
        self.torusMesh = QTorusMesh()
        self.torusMesh.setRadius(5)
        self.torusMesh.setMinorRadius(1)
        
        self.torusTransform = QTransform()
        self.torusTransform.setRotation(QQuaternion.fromAxisAndAngle(QVector3D(1,0,0), 45))
        
        self.torusEntity.addComponent(self.torusMesh)
        self.torusEntity.addComponent(self.torusTransform)
        
        # Using a Shinier material to show off the light
        self.torusMaterial = QPhongMaterial(self.rootEntity)
        self.torusMaterial.setDiffuse(QColor("#981E32"))
        self.torusMaterial.setShininess(50.0) 
        self.torusEntity.addComponent(self.torusMaterial)

        # 3. App Orbit Container
        self.appGroupEntity = QEntity(self.rootEntity)
        self.groupTransform = QTransform()
        self.appGroupEntity.addComponent(self.groupTransform)
        
        self.controller = OrbitController(self.rootEntity)
        self.controller.setTarget(self.groupTransform)

        # 4. Build App Cards in a circle
        radius = 18 
        for i, app in enumerate(self.apps):
            angle_deg = (360 / len(self.apps)) * i
            angle_rad = math.radians(angle_deg)
            x_pos = radius * math.sin(angle_rad)
            z_pos = radius * math.cos(angle_rad)
            
            card = QEntity(self.appGroupEntity)
            mesh = QPlaneMesh()
            mesh.setWidth(8); mesh.setHeight(8)
            
            trans = QTransform()
            trans.setTranslation(QVector3D(x_pos, 0, z_pos))
            
            # Orientation logic
            rot_x = QQuaternion.fromAxisAndAngle(QVector3D(1, 0, 0), 90)
            rot_y = QQuaternion.fromAxisAndAngle(QVector3D(0, 1, 0), angle_deg)
            trans.setRotation(rot_y * rot_x)
            
            card.addComponent(mesh)
            card.addComponent(trans)
            
            # App Card Material
            cardMat = QPhongMaterial(self.rootEntity)
            cardMat.setDiffuse(QColor("#ffffff"))
            cardMat.setAmbient(QColor("#222222")) # Subtle glow even in shadows
            card.addComponent(cardMat)
            
            # Text Label
            text = QText2DEntity(card)
            text.setText(app["name"])
            text.setHeight(1.5); text.setWidth(6)
            text.setColor(QColor("white"))
            textTrans = QTransform()
            textTrans.setTranslation(QVector3D(-3, -6, 0.1)) 
            text.addComponent(textTrans)

    def handle_tracker_update(self, z, y, x, dx, dy):
        # --- 1. Perspective Shift (The Hologram Effect) ---
        # As you move your head, the camera shifts slightly
        new_cam_pos = QVector3D(x * 10, y * 10, 40 + (z * 5))
        self.camera().setPosition(new_cam_pos)

        # --- 2. Menu Navigation ---
        if datetime.now() > self.invalidTime:
            if dx != 0:
                self.current_index = (self.current_index + dx) % len(self.apps)
                target_angle = self.current_index * (360 / len(self.apps))
                self.controller.angle = target_angle
                self.invalidTime = datetime.now() + timedelta(milliseconds=600)
            
            elif dy == 1: # Head nod / Up gesture
                self.launch_app(self.apps[self.current_index]["name"])
                self.invalidTime = datetime.now() + timedelta(milliseconds=1000)

        # ... your existing camera move code ...
        new_cam_pos = QVector3D(x * 10, y * 10, 40 + (z * 5))
        self.camera().setPosition(new_cam_pos)

        # --- THE LIGHT FOLLOWS YOU ---
        self.lightTransform.setTranslation(new_cam_pos)

    def launch_app(self, name):
        if platform.system() == 'Darwin':
            mac_map = {"Browser": "Safari", "Files": "Finder", "Terminal": "Terminal", "Settings": "System Settings"}
            subprocess.run(["open", "-a", mac_map.get(name, "Finder")])

if __name__ == "__main__":
    # For Qt3D on Mac, QGuiApplication is required instead of QApplication
    app = QGuiApplication(sys.argv)
    view = SpatialWindow()
    view.show()
    sys.exit(app.exec())