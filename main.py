import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QFileDialog, QMessageBox, QRadioButton, QButtonGroup

import pyvista as pv
from pyvistaqt.plotting import QtInteractor

# Allow plotting empty meshes (might suppress errors for bad files, but won't fix them)
pv.global_theme.allow_empty_mesh = True

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.current_mesh = None # Store the currently loaded mesh

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
        if self.current_mesh:
            style = self.get_selected_style()
            show_edges = style == 'surface' # Show edges only for surface view by default
            self.plotter.clear()
            self.plotter.add_mesh(self.current_mesh, style=style, color='green', show_edges=show_edges)
            # Keep camera position if possible, otherwise reset
            # self.plotter.reset_camera() # Resetting might be jarring, let's try without first

    def load_file(self):
        file_dialog = QFileDialog(self)
        # Updated filter string
        filters = [
            "3D Files (*.obj *.stl *.ply *.vtk *.gltf *.glb *.fbx)", # Common mesh formats
            "CAD Files (*.step *.iges)", # Common CAD formats (might need extra libs)
            "All Files (*)"
        ]
        file_path, _ = file_dialog.getOpenFileName(self, "Open 3D File", "", ";;".join(filters))

        if file_path:
            try:
                mesh = pv.read(file_path)
                self.current_mesh = mesh # Store the loaded mesh
                self.plotter.clear() # Clear previous mesh
                # Use the current style setting when loading
                style = self.get_selected_style()
                show_edges = style == 'surface'
                self.plotter.add_mesh(self.current_mesh, style=style, color='green', show_edges=show_edges)
                self.plotter.reset_camera()
                print(f"Loaded file: {file_path}")
            except Exception as e:
                self.current_mesh = None # Clear mesh on error
                # More specific error feedback
                error_message = f"Error loading file: {file_path}\n{str(e)}\nPlease check the file format and integrity. Some formats might require additional libraries (e.g., meshio, trimesh)."
                print(error_message)
                # Display this in a message box in the GUI
                QMessageBox.critical(self, "Load Error", error_message)
                self.plotter.clear() # Clear plotter view on error


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
