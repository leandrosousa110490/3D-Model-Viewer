import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QPushButton, QFileDialog, QMessageBox, QRadioButton, QButtonGroup,
    QColorDialog, QSlider, QLabel, QMenuBar, QMenu, QSizePolicy
)
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtCore import Qt

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
        self.setGeometry(100, 100, 900, 700) # Slightly larger window

        self.current_mesh_pv = None # Store the currently loaded PyVista mesh
        self.current_mesh_tr = None # Store the currently loaded Trimesh mesh (optional, for editing)
        self.override_color = None # Store the user-selected mesh color override
        self.current_opacity = 1.0 # Store current opacity (1.0 = fully opaque)

        self.setup_menu()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget) 

        # Create the PyVista plotter
        self.plotter = QtInteractor(self) # Initialize without background kwarg
        self.plotter.set_background('#cccccc') # Set background afterwards
        main_layout.addWidget(self.plotter.interactor)

        # --- Control Layout Row 1 (File/Style) ---
        control_layout1 = QHBoxLayout() 

        # Button to load a file (Now handled by Menu)
        # self.load_button = QPushButton("Load File")
        # self.load_button.clicked.connect(self.load_file)
        # control_layout1.addWidget(self.load_button)

        control_layout1.addWidget(QLabel("Style:")) # Label for style
        # --- Representation Style Radio Buttons ---
        self.style_group = QButtonGroup(self) 

        self.radio_surface = QRadioButton("Surface")
        self.radio_surface.setChecked(True) 
        self.radio_surface.toggled.connect(self.update_representation)
        control_layout1.addWidget(self.radio_surface)
        self.style_group.addButton(self.radio_surface)

        self.radio_wireframe = QRadioButton("Wireframe")
        self.radio_wireframe.toggled.connect(self.update_representation)
        control_layout1.addWidget(self.radio_wireframe)
        self.style_group.addButton(self.radio_wireframe)

        self.radio_points = QRadioButton("Points")
        self.radio_points.toggled.connect(self.update_representation)
        control_layout1.addWidget(self.radio_points)
        self.style_group.addButton(self.radio_points)

        control_layout1.addStretch() # Push controls to the left
        main_layout.addLayout(control_layout1) # Add row 1 to main layout

        # --- Control Layout Row 2 (Color/Opacity) ---
        control_layout2 = QHBoxLayout()
        
        # Background Color Button
        self.bg_color_button = QPushButton("Background Color")
        self.bg_color_button.clicked.connect(self.set_background_color)
        control_layout2.addWidget(self.bg_color_button)
        
        # Mesh Color Button
        self.mesh_color_button = QPushButton("Mesh Color")
        self.mesh_color_button.clicked.connect(self.set_mesh_color)
        control_layout2.addWidget(self.mesh_color_button)
        
        # Reset Mesh Color Button
        self.reset_mesh_color_button = QPushButton("Reset Color")
        self.reset_mesh_color_button.clicked.connect(self.reset_mesh_color)
        control_layout2.addWidget(self.reset_mesh_color_button)
        
        control_layout2.addSpacing(20) # Add some space
        
        # Opacity Slider
        control_layout2.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setTickInterval(10)
        self.opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.opacity_slider.valueChanged.connect(self.set_opacity)
        # Make slider take up more space
        self.opacity_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control_layout2.addWidget(self.opacity_slider)
        
        # Optional: Label to show opacity value
        self.opacity_label = QLabel("1.0")
        control_layout2.addWidget(self.opacity_label)
        
        control_layout2.addStretch()
        main_layout.addLayout(control_layout2) # Add row 2 to main layout
        # --- End Control Layouts ---

        self.plotter.add_axes()
        self.plotter.show()

    def setup_menu(self):
        menu_bar = self.menuBar() 
        # File Menu
        file_menu = menu_bar.addMenu("&File")
        
        open_action = QAction("&Open...", self)
        open_action.triggered.connect(self.load_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close) # QMainWindow's close method
        file_menu.addAction(exit_action)
        
        # We could add a View menu here later for styles if desired

    def set_background_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.plotter.set_background(color.name())
            
    def set_mesh_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.override_color = color.name() # Store color as hex string (e.g., '#RRGGBB')
            self.update_representation()
            
    def reset_mesh_color(self):
        self.override_color = None
        self.update_representation()
        
    def set_opacity(self, value):
        self.current_opacity = value / 100.0 # Convert slider value (0-100) to 0.0-1.0
        self.opacity_label.setText(f"{self.current_opacity:.2f}") # Update label
        self.update_representation()

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
            show_edges = style == 'surface' 
            self.plotter.clear()
            
            plot_color = self.override_color # Start with override color
            scalars_to_use = None
            rgb_active = False
            
            # Only check for intrinsic colors if override is NOT set
            if plot_color is None:
                if 'RGB' in self.current_mesh_pv.point_data:
                    scalars_to_use = 'RGB'
                    rgb_active = True
                    plot_color = None # Ensure color arg isn't used if scalars provide color
                elif 'RGB' in self.current_mesh_pv.cell_data:
                     scalars_to_use = 'RGB'
                     rgb_active = True
                     plot_color = None # Ensure color arg isn't used if scalars provide color
                # If still no color, PyVista will use its default
            
            # Add mesh with updated color, scalars, and opacity
            self.plotter.add_mesh(
                self.current_mesh_pv, 
                style=style, 
                show_edges=show_edges, 
                color=plot_color, # Use override or None
                scalars=scalars_to_use, 
                rgb=rgb_active,
                opacity=self.current_opacity # Apply opacity
            )
            # self.plotter.reset_camera() # Optional: reset camera on update

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
                         if np.max(colors) <= 1.0: # Check if colors are in 0-1 range
                            colors = (colors * 255).astype(np.uint8)
                         else:
                             colors = colors.astype(np.uint8)
                     mesh_pv.point_data['RGB'] = colors
                     print("Transferred vertex colors from Trimesh to PyVista.")
                # --- End Color Transfer ---

                self.current_mesh_tr = mesh_tr # Store trimesh object (optional)
                self.current_mesh_pv = mesh_pv # Store pyvista object

                # Reset override color and opacity on new load
                self.override_color = None 
                self.current_opacity = 1.0
                self.opacity_slider.setValue(100)
                self.opacity_label.setText("1.0")

                self.plotter.clear() # Clear previous mesh
                self.update_representation() # Call update_representation to draw the mesh
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
