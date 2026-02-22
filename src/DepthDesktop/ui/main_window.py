from __future__ import annotations

import sys
from dataclasses import dataclass, field

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QSurfaceFormat, QMouseEvent
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QApplication, QMainWindow

from DepthDesktop.rendering.renderer import Renderer


ICONS = ["browser", "file_sys", "settings", "terminal"]
TOKEN_SIZE = 80.0


@dataclass
class Token:
    x: float
    y: float
    icon: str
    size: float = TOKEN_SIZE
    highlighted: bool = False
    dragging: bool = False
    _drag_offset_x: float = field(default=0.0, repr=False)
    _drag_offset_y: float = field(default=0.0, repr=False)

    def hit_test(self, mx: float, my: float) -> bool:
        half = self.size / 2
        return abs(mx - self.x) <= half and abs(my - self.y) <= half


def _create_tokens() -> list[Token]:
    tokens = []
    start_x = 150.0
    spacing = 120.0
    y = 120.0
    for i, icon in enumerate(ICONS):
        tokens.append(Token(x=start_x + i * spacing, y=y, icon=icon))
    return tokens


class RenderWidget(QOpenGLWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.renderer = Renderer()
        self.tokens: list[Token] = _create_tokens()
        self._dragging_token: Token | None = None
        self.setMouseTracking(True)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)

    def initializeGL(self) -> None:
        try:
            self.renderer.initialize()
        except:
            print("Error in initializing GL")

    def resizeGL(self, width: int, height: int) -> None:
        print(f"self.devicePixilRatioF: {self.devicePixelRatioF()}")
        print(f"self.width: {width}, self.height: {height}")
        self.renderer.resize(width, height, self.devicePixelRatioF())

    def paintGL(self) -> None:
        self.renderer.set_scene_state({"tokens": self.tokens})
        self.renderer.render()

    def closeEvent(self, event) -> None:
        self.renderer.release()
        super().closeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        mx, my = event.position().x(), event.position().y()
        # Find the topmost (last drawn) token under the cursor
        for token in reversed(self.tokens):
            if token.hit_test(mx, my):
                token.dragging = True
                token._drag_offset_x = mx - token.x
                token._drag_offset_y = my - token.y
                self._dragging_token = token
                # Bring to front
                self.tokens.remove(token)
                self.tokens.append(token)
                break

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        mx, my = event.position().x(), event.position().y()

        if self._dragging_token is not None:
            self._dragging_token.x = mx - self._dragging_token._drag_offset_x
            self._dragging_token.y = my - self._dragging_token._drag_offset_y

        # Update highlight state for all tokens
        for token in self.tokens:
            token.highlighted = (not token.dragging) and token.hit_test(mx, my)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._dragging_token is not None:
            self._dragging_token.dragging = False
            self._dragging_token = None
        mx, my = event.position().x(), event.position().y()
        for token in self.tokens:
            token.highlighted = token.hit_test(mx, my)


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
