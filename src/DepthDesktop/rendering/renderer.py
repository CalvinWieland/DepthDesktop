from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

try:
    moderngl = importlib.import_module("moderngl")
except ImportError:
    moderngl = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PIL import Image
except ImportError:
    Image = None


_VERT_SHADER = """
#version 330 core

in vec2 in_vert;
in vec2 in_uv;

uniform vec2 u_position;
uniform float u_size;
uniform vec2 u_viewport;

out vec2 v_uv;

void main() {
    vec2 pixel_pos = u_position + in_vert * u_size;
    vec2 ndc = (pixel_pos / u_viewport) * 2.0 - 1.0;
    ndc.y = -ndc.y;
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_uv = in_uv;
}
"""

_TOKEN_FRAG_SHADER = """
#version 330 core

in vec2 v_uv;

uniform sampler2D u_texture;

out vec4 fragColor;

void main() {
    fragColor = texture(u_texture, v_uv);
}
"""

_BORDER_FRAG_SHADER = """
#version 330 core

uniform vec4 u_color;

out vec4 fragColor;

void main() {
    fragColor = u_color;
}
"""

_ICONS_DIR = Path(__file__).parent.parent / "app" / "icons"
_ICON_NAMES = ["browser", "file_sys", "settings", "terminal"]

# Quad vertices: x, y, u, v — centered at origin, -0.5 to 0.5
_QUAD_VERTS = [
    -0.5, -0.5, 0.0, 0.0,
     0.5, -0.5, 1.0, 0.0,
     0.5,  0.5, 1.0, 1.0,
    -0.5,  0.5, 0.0, 1.0,
]
_QUAD_INDICES = [0, 1, 2, 0, 2, 3]

# Highlight border color (r, g, b, a)
_HIGHLIGHT_COLOR = (1.0, 0.85, 0.2, 0.9)
# Pixels to add on each side for the border quad
_BORDER_PAD = 10.0


class Renderer:
    """Core ModernGL renderer for embedding in a Qt OpenGL widget.

    Prerequisite: when `initialize()` is called, a valid and current
    OpenGL context from Qt already exists.

    The renderer owns GPU-side resources:
    - `ctx` (ModernGL context created from the active Qt context)
    - shader programs
    - VAOs / VBOs
    - textures
    - framebuffers
    """

    def __init__(self) -> None:
        """Create an empty renderer shell."""
        self.ctx: Any = None

        self.programs: dict[str, Any] = {}
        self.vaos: dict[str, Any] = {}
        self.vbos: dict[str, Any] = {}
        self.textures: dict[str, Any] = {}
        self.framebuffers: dict[str, Any] = {}

        self.width: int = 0
        self.height: int = 0
        self.device_pixel_ratio: float = 1.0

        self.pose: Any = None
        self.scene_state: Any = None
        self._initialized: bool = False

    def initialize(self) -> None:
        """Create ModernGL context and allocate renderer resources.

        Expected Qt usage:
        - Call from widget initialization path once a Qt GL context is current
        - Safe to call once; repeated calls currently no-op.
        """
        if self._initialized:
            return

        self.ctx = moderngl.create_context()
        self._screen = self.ctx.detect_framebuffer()

        self._build_programs()
        self._build_geometry()
        self._build_textures()
        self._build_framebuffers()

        self._initialized = True

    def resize(self, width: int, height: int, device_pixel_ratio: float = 1.0) -> None:
        """Handle viewport and framebuffer size changes.

        Args:
            width: Logical widget width in pixels.
            height: Logical widget height in pixels.
            device_pixel_ratio: Scale factor for HiDPI displays.

        Notes:
            Physical render size is `logical_size * device_pixel_ratio`.
        """
        self.width = max(0, int(width))
        self.height = max(0, int(height))
        self.device_pixel_ratio = float(device_pixel_ratio)

        if not self.ctx:
            return

        physical_width = int(self.width * self.device_pixel_ratio)
        physical_height = int(self.height * self.device_pixel_ratio)
        self.ctx.viewport = (0, 0, physical_width, physical_height)

    def bind_current_framebuffer(self) -> None:
        """Bind whatever framebuffer is currently bound in the GL context."""
        self.framebuffers["screen"] = self.ctx.detect_framebuffer()
        self.framebuffers["screen"].use()

    def set_pose(self, pose: Any) -> None:
        """Update camera/object pose consumed by shaders during `render()`."""
        self.pose = pose

    def set_scene_state(self, state: Any) -> None:
        """Update render-relevant scene state consumed by `render()`."""
        self.scene_state = state

    def render(self) -> None:
        """Draw one frame using current pose/scene state and GPU resources."""
        if not self.ctx:
            raise RuntimeError("Renderer is not initialized. Call initialize() first.")

        self.bind_current_framebuffer()

        self._prepare_frame()
        self._draw_scene()
        self._finalize_frame()

    def release(self) -> None:
        """Release GPU resources."""
        self._release_collection(self.framebuffers)
        self._release_collection(self.textures)
        self._release_collection(self.vaos)
        self._release_collection(self.vbos)
        self._release_collection(self.programs)

        self.ctx = None
        self._initialized = False

    def _build_programs(self) -> None:
        """Create and cache shader programs."""
        self.programs["token"] = self.ctx.program(
            vertex_shader=_VERT_SHADER,
            fragment_shader=_TOKEN_FRAG_SHADER,
        )
        self.programs["border"] = self.ctx.program(
            vertex_shader=_VERT_SHADER,
            fragment_shader=_BORDER_FRAG_SHADER,
        )

    def _build_geometry(self) -> None:
        """Create VBO/VAO resources for scene geometry."""
        verts = np.array(_QUAD_VERTS, dtype="f4")
        indices = np.array(_QUAD_INDICES, dtype="i4")

        vbo = self.ctx.buffer(verts.tobytes())
        ibo = self.ctx.buffer(indices.tobytes())
        self.vbos["quad"] = vbo
        self.vbos["quad_ibo"] = ibo

        self.vaos["token"] = self.ctx.vertex_array(
            self.programs["token"],
            [(vbo, "2f 2f", "in_vert", "in_uv")],
            ibo,
        )
        self.vaos["border"] = self.ctx.vertex_array(
            self.programs["border"],
            [(vbo, "2f 2f", "in_vert", "in_uv")],
            ibo,
        )

    def _build_textures(self) -> None:
        """Load icon PNGs and upload them as GPU textures."""
        for name in _ICON_NAMES:
            path = _ICONS_DIR / f"{name}.png"
            if not path.exists():
                continue
            img = Image.open(path).convert("RGBA")
            # Flip vertically: PIL is top-to-bottom, OpenGL expects bottom-to-top
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            tex = self.ctx.texture(img.size, 4, img.tobytes())
            tex.filter = moderngl.LINEAR, moderngl.LINEAR
            self.textures[name] = tex

    def _build_framebuffers(self) -> None:
        """Create render targets/framebuffers."""

    def _prepare_frame(self) -> None:
        """Bind targets, clear buffers, and upload frame uniforms/state."""
        self.ctx.clear(0.08, 0.08, 0.10, 1.0)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

    def _draw_scene(self) -> None:
        """Issue draw calls for the current scene."""
        if not self.scene_state or self.width == 0 or self.height == 0:
            return

        tokens = self.scene_state.get("tokens", [])
        if not tokens:
            return

        viewport = (float(self.width), float(self.height))
        prog_token = self.programs["token"]
        prog_border = self.programs["border"]
        vao_token = self.vaos["token"]
        vao_border = self.vaos["border"]

        for token in tokens:
            if True:#token.highlighted or token.dragging:
                prog_border["u_position"].value = (token.x, token.y)
                prog_border["u_size"].value = token.size + _BORDER_PAD * 2
                prog_border["u_viewport"].value = viewport
                prog_border["u_color"].value = _HIGHLIGHT_COLOR
                vao_border.render()

            tex = self.textures.get(token.icon)
            if tex is None:
                continue

            prog_token["u_position"].value = (token.x, token.y)
            prog_token["u_size"].value = token.size
            prog_token["u_viewport"].value = viewport
            prog_token["u_texture"].value = 0
            tex.use(0)
            vao_token.render()

    def _finalize_frame(self) -> None:
        """Run post-processing/present steps if required."""
        return

    @staticmethod
    def _release_collection(resources: dict[str, Any]) -> None:
        """Best-effort release of objects that implement a `release()` method."""
        for resource in resources.values():
            release_fn = getattr(resource, "release", None)
            if callable(release_fn):
                release_fn()
        resources.clear()
