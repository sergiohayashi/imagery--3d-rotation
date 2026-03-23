from pathlib import Path
from typing import Optional, Union
import uuid
import numpy as np
import pyvista as pv
import os
import tempfile
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import random

try:
    from IPython import get_ipython

    if get_ipython():
        # Running inside a Jupyter notebook
        matplotlib.use("module://matplotlib_inline.backend_inline", force=True)
        notebook_mode = True
    else:
        # Running in a normal desktop Python process
        matplotlib.use("Qt5Agg", force=True)
        notebook_mode = False
except ImportError:
    # Fallback for headless servers (no display)
    matplotlib.use("Agg", force=True)
    notebook_mode = False


def _ensure_output_path(output_path: Optional[Path]) -> Path:
    """Create parent directories and return an absolute output path."""
    if output_path is None:
        output_path = (
            Path(tempfile.gettempdir()) / f"imagery_all_stateful_{uuid.uuid4().hex}.png"
        )

    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _rotation_matrix(axis, angle_rad):
    axis = axis / np.linalg.norm(axis)
    c = np.cos(angle_rad)
    s = np.sin(angle_rad)
    t = 1 - c
    x, y, z = axis
    return np.array(
        [
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
        ]
    )


class StatefulImageryModuleWithAltAndReset3:
    def __init__(self, bounds_map: dict, off_screen=True, show_grid=True):
        self.bounds_map = bounds_map
        self.off_screen = off_screen
        self.show_grid = show_grid
        self.plotter_map = self._build()
        self.count = 0

    def _build(self):
        p_map = {}
        # Ensure we can run headless on linux servers if needed
        # pv.start_xvfb() # Uncomment if running on a headless Linux server without X11

        for target, bounds_data in self.bounds_map.items():
            _plotter = pv.Plotter(window_size=(800, 600), off_screen=self.off_screen)
            _plotter.set_background("white")

            for b in bounds_data:
                _plotter.add_mesh(pv.Cube(bounds=b), color="lightblue", show_edges=True)

            _plotter.reset_camera()
            _plotter.camera_position = "iso"

            if self.show_grid:
                _plotter.show_grid()

            p_map[target] = _plotter
        return p_map

    def close(self):
        for plotter in self.plotter_map.values():
            try:
                plotter.close()
                plotter.deep_clean()
            except Exception:
                pass
        self.plotter_map.clear()
        pv.close_all()

    def rotate(self, target: str, mode="yaw", value: Union[float, str] = 30.0):
        """
        Rotates the camera or resets the view.

        Args:
            target: The key in bounds_map.
            mode: 'yaw', 'pitch', 'roll', or 'reset'.
            value:
                - If mode is rotation: degrees (float).
                - If mode is reset: axis string ('x', 'y', 'z').
        """
        cam = self.plotter_map[target].camera
        pos = np.array(cam.position)
        focal = np.array(cam.focal_point)
        up = np.array(cam.up)

        # Calculate current view vector and distance
        view = focal - pos
        distance = np.linalg.norm(view)
        view /= distance  # normalize

        if mode == "reset":
            if value == "iso":
                # Place the camera along the (1, 1, 1) direction at the current distance
                iso_dir = np.array([1.0, 1.0, 1.0])
                iso_dir /= np.linalg.norm(iso_dir)

                new_pos = focal + iso_dir * distance
                cam.position = tuple(new_pos)
                cam.up = (0.0, 0.0, 1.0)
            else:
                # Handle Axis Reset
                axis_char = str(value).lower()

                # We maintain the current focal point and distance (zoom level),
                # but move the position to align with the requested axis.
                if axis_char == "x":
                    # View from +X looking towards focal point
                    new_pos = focal + np.array([distance, 0, 0])
                    new_up = np.array([0, 0, 1])  # Z is up
                elif axis_char == "y":
                    # View from +Y looking towards focal point
                    new_pos = focal + np.array([0, distance, 0])
                    new_up = np.array([0, 0, 1])  # Z is up
                elif axis_char == "z":
                    # View from +Z looking down (Top view)
                    new_pos = focal + np.array([0, 0, distance])
                    new_up = np.array([0, 1, 0])  # Y is up usually for maps/top-down
                else:
                    print(f"Warning: Unknown reset axis '{axis_char}', ignoring.")
                    return

                cam.position = tuple(new_pos)
                cam.up = tuple(new_up)

        else:
            # Handle Rotations
            step = np.deg2rad(float(value))

            if mode == "yaw":
                # Rotate around global Z
                axis = np.array([0.0, 0.0, 1.0])
            elif mode == "pitch":
                # Rotate around the camera’s right vector
                right = np.cross(view, up)
                if np.linalg.norm(right) < 1e-6:
                    # Fallback if looking straight down/up
                    right = np.array([1.0, 0.0, 0.0])
                else:
                    right /= np.linalg.norm(right)
                axis = right
            elif mode == "roll":
                # Spin around view axis
                axis = view
            else:
                raise ValueError(
                    f"mode must be 'yaw', 'pitch', 'roll', or 'reset'. received {mode}"
                )

            R = _rotation_matrix(axis, step)
            cam.position = tuple(focal + R @ (pos - focal))
            cam.up = tuple(R @ up)

        # Force render update
        self.plotter_map[target].render()

    def show(self, target):
        self.plotter_map[target].show()

    def run_sequence_and_save_image(
        self, target, action_sequence: str, output_path: str = None
    ):
        """
        Execute a sequence of rotations/resets.
        Example: "reset:x, yaw:45, pitch:30, reset:z"
        """

        # Calculate azimuth/elevation from position
        def get_spherical_coords(cam):
            pos = np.array(cam.position) - np.array(cam.focal_point)
            r = np.linalg.norm(pos)
            el = np.degrees(np.arcsin(pos[2] / r))
            az = np.degrees(np.arctan2(pos[1], pos[0]))
            return az, el

        # Prepare output dir
        rand_part = f"{random.randint(1000,9999)}_{random.getrandbits(32)}"
        temp_dir = tempfile.mkdtemp(prefix=f"stateful_imagery_steps_{rand_part}_")
        steps = []
        cmds = [cmd.strip() for cmd in action_sequence.split(",") if cmd.strip()]

        for i, cmd in enumerate(cmds):
            if ":" not in cmd:
                raise ValueError(f"Invalid command fragment '{cmd}' in action sequence")

            mode, val_str = cmd.split(":", 1)
            mode = mode.strip().lower()
            val_str = val_str.strip()

            # Parse value: float for rotations, string for reset
            if mode == "reset":
                val = val_str  # keep as string 'x', 'y', 'z'
                display_val = val_str
            else:
                try:
                    val = float(val_str)
                    display_val = f"{int(val)}"  # formatted for label
                except ValueError:
                    raise ValueError(
                        f"Value for {mode} must be a number, got '{val_str}'"
                    )

            # Execute
            self.rotate(target, mode, val)

            # Save step image
            fname = os.path.join(
                temp_dir, f"step_{i:03d}_{mode}_{str(val).replace('.','_')}.png"
            )
            self.plotter_map[target].screenshot(fname)

            # Get camera params for labeling
            cam = self.plotter_map[target].camera
            command_str = f"{mode}:{display_val}"

            # Safely get azimuth/elevation if available (depends on vtk version/backend)
            # az = getattr(cam, 'azimuth', 0)
            # el = getattr(cam, 'elevation', 0)
            az, el = get_spherical_coords(cam)

            label = (
                f"seq:{i+1} [{command_str}]\n"
                f"pos:[{cam.position[0]:.1f},{cam.position[1]:.1f},{cam.position[2]:.1f}]\n"
                f"az:{az:.1f}° el:{el:.1f}°"
            )
            steps.append((fname, label))

        # Compose Grid Image
        n = len(steps)
        cols = 4
        rows = (n + cols - 1) // cols

        # Calculate figure size (heuristic)
        fig = plt.figure(figsize=(16, 4 * rows))

        for i, (fname, label) in enumerate(steps, 1):
            img = mpimg.imread(fname)
            ax = plt.subplot(rows, cols, i)
            ax.imshow(img)
            ax.axis("off")
            ax.set_title(label, fontsize=9, color="black", wrap=True)

        plt.subplots_adjust(wspace=0.1, hspace=0.3)
        plt.tight_layout()
        st = plt.suptitle(
            f"Target: {target}",
            fontsize=18,
            color="black",
            y=1.00 + (0.01 * rows),
            ha="left",
        )
        st.set_x(0.0)

        composed_path = _ensure_output_path(output_path)
        plt.savefig(composed_path, bbox_inches="tight", pad_inches=0.1)
        plt.close(fig)

        # Show if in notebook, safely ignore if background process
        if notebook_mode:
            try:
                # Re-open image to display in notebook output
                img_final = mpimg.imread(composed_path)
                plt.figure(figsize=(12, 12))
                plt.imshow(img_final)
                plt.axis("off")
                plt.show()
            except Exception:
                pass

        # Cleanup
        try:
            import shutil

            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Warning: failed to clean up temp_dir {temp_dir}: {e}")

        print(f"Composed summary image written to {composed_path}")
        return composed_path
