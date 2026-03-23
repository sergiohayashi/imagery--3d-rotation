import pyvista as pv

plotter = pv.Plotter(window_size=(800, 600))
plotter.set_background("white")

bounds = "BOUNDS_PLACEHOLDER"

for b in bounds:
    plotter.add_mesh(pv.Cube(bounds=b), color="lightblue", show_edges=True)

plotter.reset_camera()
plotter.camera.position = (4.17, -1.02, 5.19)
plotter.camera.focal_point = (1.35, 1.7, 0.35)
plotter.camera.up = (-0.51, 0.57, 0.62)
plotter.camera.view_angle = 60.0     # perspective zoom
plotter.camera.parallel_scale = 3.10  # parallel zoom
plotter.camera.clipping_range = (2.47, 10.37)
plotter.camera.zoom(1.0)

plotter.show_grid()
plotter.show()

