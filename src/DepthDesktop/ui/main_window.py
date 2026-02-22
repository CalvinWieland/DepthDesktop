from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QSurfaceFormat
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QApplication, QMainWindow

from DepthDesktop.rendering.renderer import Renderer

class RenderWidget(QOpenGLWidget):
	def __init__(self, parent=None) -> None:
		super().__init__(parent)
		self.renderer = Renderer()

		self._timer = QTimer(self)
		self._timer.timeout.connect(self.update)
		self._timer.start(16)

	def initializeGL(self) -> None:
		self.renderer.initialize()

	def resizeGL(self, width: int, height: int) -> None:
		self.renderer.resize(width, height, self.devicePixelRatioF())

	def paintGL(self) -> None:
		self.renderer.render()

	def closeEvent(self, event) -> None:
		self.renderer.release()
		super().closeEvent(event)

class MainWindow(QMainWindow):
	def __init__(self) -> None:
		super().__init__()
		self.setWindowTitle("Depth Desktop")
		self.resize(1280, 800)
		self.setCentralWidget(RenderWidget(self))

def configure_opengl_format() -> None:
	format_ = QSurfaceFormat()
	format_.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
	format_.setVersion(3, 3)
	format_.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
	format_.setDepthBufferSize(24)
	format_.setStencilBufferSize(8)
	QSurfaceFormat.setDefaultFormat(format_)


def main() -> int:
	configure_opengl_format()
	app = QApplication(sys.argv)
	window = MainWindow()
	window.show()
	return app.exec()


if __name__ == "__main__":
	raise SystemExit(main())
