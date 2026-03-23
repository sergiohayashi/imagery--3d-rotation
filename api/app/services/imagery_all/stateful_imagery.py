from pathlib import Path
from typing import Optional
import uuid

# from fastapi import Path
import numpy as np
import pyvista as pv
import os
import os
import tempfile
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import random


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


class StatefulImageryModule:
    def __init__(self, bounds, off_screen=True, show_grid=True):
        self.bounds = bounds
        self.init_pos = None
        self.init_focal = None
        self.init_up = None
        self.off_screen = off_screen
        self.show_grid = show_grid
        self.plotter = self._build()
        self.count = 0

    def _build(self):
        _plotter = pv.Plotter(
            window_size=(800, 600), off_screen=self.off_screen
        )  # off_screen=True for pure batch processing
        _plotter.set_background("white")

        for b in self.bounds:
            _plotter.add_mesh(pv.Cube(bounds=b), color="lightblue", show_edges=True)

        _plotter.reset_camera()
        _plotter.camera_position = "iso"

        if self.show_grid:
            _plotter.show_grid()

        # Save the initial camera state so we can reset before every new rotation type
        self.init_pos = _plotter.camera.position
        self.init_focal = _plotter.camera.focal_point
        self.init_up = _plotter.camera.up
        return _plotter

    def rotate(self, mode="yaw", step_size=360 / 12):
        step = np.deg2rad(step_size)
        cam = self.plotter.camera
        pos = np.array(cam.position)
        focal = np.array(cam.focal_point)
        up = np.array(cam.up)
        view = focal - pos
        view /= np.linalg.norm(view)

        # don´t use Azimuth, Elevation, Roll because in the pitch mode there is a abrupt point of view change
        if mode == "yaw":
            # rotate around global Z (or any axis you choose).
            # Azimuth rotates the camera around the focal point (horizontal orbit)
            axis = np.array([0.0, 0.0, 1.0])
        elif mode == "pitch":
            # rotate around the camera’s right vector
            # Elevation rotates the camera up/down over the object
            right = np.cross(view, up)
            right /= np.linalg.norm(right)
            axis = right
        elif mode == "roll":
            # roll spins the camera around its own view axis
            axis = view
        else:
            raise ValueError("mode must be 'yaw', 'pitch', or 'roll'")

        R = _rotation_matrix(axis, step)
        cam.position = tuple(focal + R @ (pos - focal))
        cam.up = tuple(R @ up)
        self.plotter.render()

    def reset(self):
        self.plotter.camera.position = self.init_pos
        self.plotter.camera.focal_point = self.init_focal
        self.plotter.camera.up = self.init_up

    def show(self):
        # self.plotter.show()
        self.plotter.show(auto_close=False, jupyter_backend="static")

    def save_image(self, output_path: str = None):
        # Save screenshot
        # filename = f"output_images/rotate_{mode}_{i:03d}.png"
        self.plotter.screenshot(output_path)
        print(f"Saved {output_path}")

    def rotate_full(self, mode, step, prefix):
        step_size = 360 / step
        files = []
        for i in range(step):
            self.rotate(mode, step_size)
            filename = f"output_images/{prefix}_{mode}_{i:03d}.png"
            self.plotter.screenshot(filename)
            files.append(filename)
        return files

    def run_sequence_and_save_image(
        self, action_sequence: str, output_path: str = None
    ):
        """
        Execute a sequence of rotations and generate a single image that contains
        all intermediary states as a tiled image.

        Args:
            action_sequence (str): Comma-separated string like "yaw:30,yaw:10,pitch:10,roll:10"
            output_path (str, optional): Path to save the composed image. If None, use self.output_path.
        """

        # Prepare output dir for temp individual images
        rand_part = f"{random.randint(1000,9999)}_{random.getrandbits(32)}"
        temp_dir = tempfile.mkdtemp(prefix=f"stateful_imagery_steps_{rand_part}_")
        steps = []
        cmds = [cmd.strip() for cmd in action_sequence.split(",") if cmd.strip()]
        for i, cmd in enumerate(cmds):
            if ":" not in cmd:
                raise ValueError(f"Invalid command fragment '{cmd}' in action sequence")
            mode, deg = cmd.split(":", 1)
            mode = mode.strip().lower()
            deg = float(deg)
            self.rotate(mode, deg)
            fname = os.path.join(temp_dir, f"step_{i:03d}_{mode}_{int(deg)}.png")
            self.plotter.screenshot(fname)

            # Get camera params for labeling
            cam = self.plotter.camera
            command_str = f"{mode}:{deg}"
            label = (
                f"seq:{i+1} command:{command_str},\n "
                f"pos:[{cam.position[0]:.1f},{cam.position[1]:.1f},{cam.position[2]:.1f}]\n "
                f"_az:{getattr(cam, 'azimuth', 0):.1f}° "
                f"_el:{getattr(cam, 'elevation', 0):.1f}°"
            )
            steps.append((fname, label))

        # Now create the composed image out of the steps (max 4 per row)
        n = len(steps)
        cols = 4
        rows = (n + cols - 1) // cols
        plt.figure(figsize=(16, 4 * rows))  # 800 pixel width
        for i, (fname, label) in enumerate(steps, 1):
            img = mpimg.imread(fname)
            plt.subplot(rows, cols, i)
            plt.imshow(img)
            plt.axis("off")
            plt.title(label, fontsize=10, color="black", wrap=True)
        plt.subplots_adjust(wspace=0.0, hspace=0.0)

        # Determine output file path
        composed_path = _ensure_output_path(output_path)
        plt.savefig(composed_path, bbox_inches="tight", pad_inches=0)
        plt.close()

        # Delete the temporary files and directory
        try:
            import shutil

            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Warning: failed to clean up temp_dir {temp_dir}: {e}")

        print(f"Composed summary image written to {composed_path}")
        return composed_path
