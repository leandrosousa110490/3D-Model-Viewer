import sys
import os # Import os for path manipulation in screenshot
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QPushButton, QFileDialog, QMessageBox, QRadioButton, QButtonGroup,
    QColorDialog, QSlider, QLabel, QMenuBar, QMenu, QSizePolicy,
    QStatusBar # Added status bar
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
        self.current_filepath = None # Added to store the path of the loaded file

        self.setup_menu()
        self.setStatusBar(QStatusBar(self)) # Add Status Bar
        self.statusBar().showMessage("Ready") # Initial message
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget) 

        # Create the PyVista plotter
        self.plotter = QtInteractor(self) # Initialize without background kwarg
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
        
        # Save As Action
        save_as_action = QAction("Save &As...", self)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)
        
        # Screenshot Action
        screenshot_action = QAction("&Screenshot...", self)
        screenshot_action.triggered.connect(self.take_screenshot)
        file_menu.addAction(screenshot_action)
        
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

    def take_screenshot(self):
        if not self.plotter.renderer:
             self.statusBar().showMessage("Plotter not ready for screenshot.", 3000)
             return
             
        suggested_name = "screenshot.png"
        if self.current_filepath:
            try:
                base = os.path.basename(self.current_filepath)
                root, _ = os.path.splitext(base)
                suggested_name = f"{root}_screenshot.png"
            except Exception:
                pass
        
        filters = "PNG Images (*.png);;JPEG Images (*.jpg *.jpeg);;All Files (*)"
        fileName, selected_filter = QFileDialog.getSaveFileName(self, "Save Screenshot", suggested_name, filters)
        
        if fileName:
            axes_widget = self.plotter.renderer.axes_widget
            axes_were_present = False # Default to false
            if axes_widget: # Check if widget exists
                 axes_were_present = axes_widget.GetEnabled()
            
            # --- Temporarily disable axes for cleaner screenshot --- 
            if axes_widget and axes_were_present:
                axes_widget.SetEnabled(False)
                self.plotter.render() # Force render update
            # --- End temporary removal --- 
            
            try:
                # Take screenshot with transparent background
                self.plotter.screenshot(fileName, transparent_background=True)
                self.statusBar().showMessage(f"Screenshot saved to {fileName}", 5000)
            except Exception as e:
                error_message = f"Error saving screenshot: {str(e)}"
                print(error_message)
                QMessageBox.warning(self, "Screenshot Error", error_message)
                self.statusBar().showMessage("Screenshot failed.", 3000)
            finally:
                # --- Restore axes if they were disabled --- 
                if axes_widget and axes_were_present:
                    axes_widget.SetEnabled(True)
                    self.plotter.render() # Force render update
                # --- End restore --- 
        else:
             self.statusBar().showMessage("Screenshot cancelled.", 3000)

    def save_file_as(self):
        if self.current_mesh_tr is None:
            self.statusBar().showMessage("No mesh loaded to save.", 3000)
            QMessageBox.information(self, "Save As", "Please load a mesh before saving.")
            return

        suggested_name = "saved_mesh.ply"
        # Use self.current_filepath for suggestion
        if self.current_filepath:
            try:
                base = os.path.basename(self.current_filepath)
                root, _ = os.path.splitext(base)
                suggested_name = f"{root}_saved.ply"
            except Exception:
                 pass

        # Filters based on common trimesh export formats
        filters = (
            "PLY Files (*.ply);;"            # Good general purpose, supports color
            "STL Files (*.stl);;"            # Common for 3D printing, no color
            "OBJ Files (*.obj);;"            # Widely supported, can have material file
            "GLTF Binary (*.glb);;"        # Efficient web/modern format, supports PBR
            "GLTF Ascii (*.gltf);;"         # Text version of GLTF
            "COLLADA (*.dae);;"             # Older standard, supports animation/scenes
            "OFF Files (*.off);;"            # Simple ASCII format
            # "XYZ Point Cloud (*.xyz);;"    # Less common to export mesh as point cloud
            "All Files (*)"
        )

        fileName, selected_filter = QFileDialog.getSaveFileName(self, "Save Mesh As", suggested_name, filters)

        if fileName:
            self.statusBar().showMessage(f"Saving mesh to {os.path.basename(fileName)}...")
            QApplication.processEvents() # Allow UI update
            try:
                colors_to_export = None
                if 'RGB' in self.current_mesh_pv.point_data:
                    colors_to_export = self.current_mesh_pv.point_data['RGB']
                    if colors_to_export.shape[0] == self.current_mesh_tr.vertices.shape[0]:
                         print("Exporting with vertex colors from PyVista mesh.")
                         if colors_to_export.shape[1] == 3:
                            alpha = np.full((colors_to_export.shape[0], 1), 255, dtype=np.uint8)
                            colors_to_export = np.hstack((colors_to_export, alpha))
                    else:
                        print("Color array size mismatch, exporting without explicit colors.")
                        colors_to_export = None
                else:
                    print("No RGB data found in PyVista mesh for export.")
                    colors_to_export = None
                
                mesh_to_export = self.current_mesh_tr.copy()
                if colors_to_export is not None:
                    mesh_to_export.visual.vertex_colors = colors_to_export
                    
                export_result = mesh_to_export.export(fileName)
                
                if export_result is None or isinstance(export_result, str):
                     self.statusBar().showMessage(f"Mesh saved successfully to {fileName}", 5000)
                     print(f"Mesh saved via Trimesh to {fileName}")
                else: 
                     raise RuntimeError(f"Trimesh export returned unexpected type: {type(export_result)}")
            except Exception as e:
                error_message = f"Error saving file: {str(e)}"
                print(error_message)
                QMessageBox.critical(self, "Save Error", error_message)
                self.statusBar().showMessage("Mesh save failed.", 3000)
        else:
            self.statusBar().showMessage("Save As cancelled.", 3000)

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
        # Reset status bar at the start of loading
        self.statusBar().showMessage("Opening file dialog...")
        
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

        if not file_path:
            self.statusBar().showMessage("File load cancelled.", 3000)
            return # Exit if no file selected

        # Indicate loading
        self.statusBar().showMessage(f"Loading {os.path.basename(file_path)}...")
        QApplication.processEvents() # Allow UI to update
        
        try:
            print(f"Attempting to load with Trimesh: {file_path}")
            # Load mesh using trimesh
            # force='mesh' attempts to return a Trimesh object if possible
            mesh_tr = trimesh.load(file_path, force='mesh')
            print(f"Trimesh loaded object of type: {type(mesh_tr)}")

            # If trimesh returns a Scene object, try to extract the main geometry
            if isinstance(mesh_tr, trimesh.Scene):
                if len(mesh_tr.geometry) > 0:
                    print(f"Trimesh loaded a Scene. Attempting to concatenate geometry.")
                    # Consolidate scene geometry into one mesh if possible
                    mesh_tr = trimesh.util.concatenate(list(mesh_tr.geometry.values()))
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
            
            # Store the path in the instance variable
            self.current_filepath = file_path
            
            # Update status bar using the instance variable
            status_text = f"Loaded: {os.path.basename(self.current_filepath)} | Vertices: {self.current_mesh_pv.n_points} | Cells: {self.current_mesh_pv.n_cells}"
            self.statusBar().showMessage(status_text)
            print(f"Successfully loaded and displayed: {self.current_filepath}")

        except Exception as e:
            self.current_mesh_tr = None
            self.current_mesh_pv = None # Clear mesh on error
            self.current_filepath = None # Clear filepath on error
            error_message = f"Error loading file with Trimesh: {file_path}\n{str(e)}" # Use original file_path for error msg
            print(error_message)
            QMessageBox.critical(self, "Load Error", error_message)
            self.plotter.clear() # Clear plotter view on error
            self.statusBar().showMessage("File load failed.", 5000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
