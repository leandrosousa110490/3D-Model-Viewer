import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QFileDialog, QMessageBox, QRadioButton, QButtonGroup

import pyvista as pv
from pyvistaqt.plotting import QtInteractor
import trimesh # Import trimesh
import numpy as np # Often needed with trimesh/pyvista

# Allow plotting empty meshes (might suppress errors for bad files, but won't fix them)
pv.global_theme.allow_empty_mesh = True

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.current_mesh_pv = None # Store the currently loaded PyVista mesh
        self.current_mesh_tr = None # Store the currently loaded Trimesh mesh (optional, for editing)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget) # Renamed for clarity

        # Create the PyVista plotter
        self.plotter = QtInteractor(self)
        main_layout.addWidget(self.plotter.interactor)

        # --- Control Layout ---
        control_layout = QHBoxLayout() # Horizontal layout for controls

        # Button to load a file
        self.load_button = QPushButton("Load File")
        self.load_button.clicked.connect(self.load_file)
        control_layout.addWidget(self.load_button)

        # --- Representation Style Radio Buttons ---
        self.style_group = QButtonGroup(self) # Group buttons

        self.radio_surface = QRadioButton("Surface")
        self.radio_surface.setChecked(True) # Default style
        self.radio_surface.toggled.connect(self.update_representation)
        control_layout.addWidget(self.radio_surface)
        self.style_group.addButton(self.radio_surface)

        self.radio_wireframe = QRadioButton("Wireframe")
        self.radio_wireframe.toggled.connect(self.update_representation)
        control_layout.addWidget(self.radio_wireframe)
        self.style_group.addButton(self.radio_wireframe)

        self.radio_points = QRadioButton("Points")
        self.radio_points.toggled.connect(self.update_representation)
        control_layout.addWidget(self.radio_points)
        self.style_group.addButton(self.radio_points)

        control_layout.addStretch() # Push controls to the left

        main_layout.addLayout(control_layout) # Add control layout to main layout
        # --- End Control Layout ---


        self.plotter.add_axes()
        self.plotter.show()

    def get_selected_style(self):
        if self.radio_surface.isChecked():
            return 'surface'
        elif self.radio_wireframe.isChecked():
            return 'wireframe'
        elif self.radio_points.isChecked():
            return 'points'
        return 'surface' # Default fallback

    def update_representation(self):
        if self.current_mesh_pv:
            style = self.get_selected_style()
            show_edges = style == 'surface' # Show edges only for surface view by default
            self.plotter.clear()
            # Check for RGB scalars and use them if available
            # Note: Color data needs careful handling when converting trimesh -> pyvista
            # For now, we rely on pyvista wrap to handle it if possible
            scalars_to_use = None
            rgb_active = False
            if 'RGB' in self.current_mesh_pv.point_data:
                scalars_to_use = 'RGB'
                rgb_active = True
            elif 'RGB' in self.current_mesh_pv.cell_data:
                 scalars_to_use = 'RGB'
                 rgb_active = True

            self.plotter.add_mesh(self.current_mesh_pv, style=style, show_edges=show_edges, scalars=scalars_to_use, rgb=rgb_active)
            # Keep camera position if possible, otherwise reset
            # self.plotter.reset_camera() # Resetting might be jarring, let's try without first

    def load_file(self):
        file_dialog = QFileDialog(self)
        # Use trimesh supported formats potentially, or keep broad filter
        # trimesh supports many: obj, stl, ply, gltf, glb, dae, off, xyz, etc.
        filters = [
            "Mesh Files (*.obj *.stl *.ply *.gltf *.glb *.dae *.off)",
            "Point Clouds (*.xyz)",
            # "CAD Files (*.step *.iges)", # Trimesh uses external libs for STEP/IGES, may fail
            "All Files (*)"
        ]
        file_path, _ = file_dialog.getOpenFileName(self, "Open 3D File", "", ";;".join(filters))

        if file_path:
            try:
                print(f"Attempting to load with Trimesh: {file_path}")
                # Load mesh using trimesh
                # force='mesh' attempts to return a Trimesh object if possible
                mesh_tr = trimesh.load(file_path, force='mesh')
                print(f"Trimesh loaded object of type: {type(mesh_tr)}")

                # If trimesh returns a Scene object, try to extract the main geometry
                if isinstance(mesh_tr, trimesh.Scene):
                    if len(mesh_tr.geometry) > 0:
                        # Attempt to combine geometries or take the largest
                        # This simplistic approach takes the first one
                        # A more robust method might merge or handle multiple geometries
                        print(f"Trimesh loaded a Scene. Extracting first geometry.")
                        mesh_tr = list(mesh_tr.geometry.values())[0]
                    else:
                        raise ValueError("Trimesh loaded an empty scene.")

                # Ensure we have a Trimesh object now
                if not isinstance(mesh_tr, trimesh.Trimesh):
                     raise TypeError(f"Loaded object is not a Trimesh mesh (type: {type(mesh_tr)}). May be a point cloud or unsupported type.")

                # Convert trimesh mesh to pyvista PolyData
                # pv.wrap intelligently handles trimesh objects
                mesh_pv = pv.wrap(mesh_tr)
                print(f"Converted Trimesh to PyVista mesh.")

                # --- Transfer Vertex Colors if they exist --- 
                # trimesh stores vertex colors in mesh.visual.vertex_colors
                if hasattr(mesh_tr, 'visual') and hasattr(mesh_tr.visual, 'vertex_colors') and len(mesh_tr.visual.vertex_colors) == mesh_tr.vertices.shape[0]:
                     # PyVista expects uint8 RGB, trimesh often stores RGBA float/uint8
                     colors = np.array(mesh_tr.visual.vertex_colors)
                     if colors.shape[1] == 4:
                         # Assume RGBA, take first 3 channels
                         colors = colors[:, :3]
                     # Convert to uint8 if needed (PyVista prefers this for 'RGB')
                     if colors.dtype != np.uint8:
                         if colors.max() <= 1.0:
                            colors = (colors * 255).astype(np.uint8)
                         else:
                             colors = colors.astype(np.uint8)
                     mesh_pv.point_data['RGB'] = colors
                     print("Transferred vertex colors from Trimesh to PyVista.")
                # --- End Color Transfer ---

                self.current_mesh_tr = mesh_tr # Store trimesh object (optional)
                self.current_mesh_pv = mesh_pv # Store pyvista object

                self.plotter.clear() # Clear previous mesh

                style = self.get_selected_style()
                show_edges = style == 'surface'
                # Check if RGB scalars were successfully transferred/wrapped
                scalars_to_use = 'RGB' if 'RGB' in mesh_pv.point_data else None
                self.plotter.add_mesh(self.current_mesh_pv, style=style, show_edges=show_edges, scalars=scalars_to_use, rgb=True if scalars_to_use else False)
                self.plotter.reset_camera()
                print(f"Successfully loaded and displayed: {file_path}")

            except Exception as e:
                self.current_mesh_tr = None
                self.current_mesh_pv = None # Clear mesh on error
                error_message = f"Error loading file with Trimesh: {file_path}\n{str(e)}"
                print(error_message)
                QMessageBox.critical(self, "Load Error", error_message)
                self.plotter.clear() # Clear plotter view on error


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
