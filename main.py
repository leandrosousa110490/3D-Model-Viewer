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

# Imports for 2D to 3D conversion
import cv2
from PIL import Image # PIL is often used with transformers

# Import for Background Removal
from rembg import remove as remove_background
import io # For handling image bytes with rembg

# Allow plotting empty meshes (might suppress errors for bad files, but won't fix them)
pv.global_theme.allow_empty_mesh = True

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D/2D Viewer") # Updated title
        self.setGeometry(100, 100, 900, 700) 

        # --- State Variables (Removed depth estimator and device) ---
        self.current_mesh_pv = None # Can be 3D model or flat plane with image
        self.current_mesh_tr = None # Only used for original 3D models
        self.current_image_pil = None # Stores the currently loaded PIL Image
        self.is_2d_image_loaded = False # Flag to track if a 2D image is active
        
        self.override_color = None 
        self.current_opacity = 1.0 
        self.current_filepath = None # Path to loaded 3D model OR 2D image
        # --- End State Variables ---

        self.setup_menu()
        self.setStatusBar(QStatusBar(self)) 
        self.statusBar().showMessage("Ready") 
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget) 

        # Create the PyVista plotter
        self.plotter = QtInteractor(self) 
        main_layout.addWidget(self.plotter.interactor)

        # --- Control Layout Row 1 (Style/Color/Opacity - Unchanged) ---
        control_layout_top = QHBoxLayout() 
        control_layout_top.addWidget(QLabel("Style:")) 
        self.style_group = QButtonGroup(self) 
        self.radio_surface = QRadioButton("Surface")
        self.radio_surface.setChecked(True) 
        self.radio_surface.toggled.connect(self.update_representation)
        control_layout_top.addWidget(self.radio_surface)
        self.style_group.addButton(self.radio_surface)
        self.radio_wireframe = QRadioButton("Wireframe")
        self.radio_wireframe.toggled.connect(self.update_representation)
        control_layout_top.addWidget(self.radio_wireframe)
        self.style_group.addButton(self.radio_wireframe)
        self.radio_points = QRadioButton("Points")
        self.radio_points.toggled.connect(self.update_representation)
        control_layout_top.addWidget(self.radio_points)
        self.style_group.addButton(self.radio_points)
        control_layout_top.addSpacing(20)
        self.bg_color_button = QPushButton("BG Color")
        self.bg_color_button.clicked.connect(self.set_background_color)
        control_layout_top.addWidget(self.bg_color_button)
        self.mesh_color_button = QPushButton("Mesh Color")
        self.mesh_color_button.clicked.connect(self.set_mesh_color)
        control_layout_top.addWidget(self.mesh_color_button)
        self.reset_mesh_color_button = QPushButton("Reset Color")
        self.reset_mesh_color_button.clicked.connect(self.reset_mesh_color)
        control_layout_top.addWidget(self.reset_mesh_color_button)
        control_layout_top.addSpacing(20) 
        control_layout_top.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setTickInterval(10)
        self.opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.opacity_slider.valueChanged.connect(self.set_opacity)
        self.opacity_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control_layout_top.addWidget(self.opacity_slider)
        self.opacity_label = QLabel("1.0")
        control_layout_top.addWidget(self.opacity_label)
        control_layout_top.addStretch()
        main_layout.addLayout(control_layout_top) 

        # --- Control Layout Row 2 (Image Actions - Modified) ---
        control_layout_image = QHBoxLayout()
        
        self.remove_bg_button = QPushButton("Remove Background") 
        self.remove_bg_button.clicked.connect(self.remove_image_background)
        self.remove_bg_button.setEnabled(False) # Initially disabled
        control_layout_image.addWidget(self.remove_bg_button)
        
        control_layout_image.addStretch()
        main_layout.addLayout(control_layout_image)
        # --- End Control Layouts ---

        self.plotter.add_axes()
        self.plotter.show()
        # Call initially to set button states correctly
        self.update_button_states()

    def setup_menu(self):
        menu_bar = self.menuBar() 
        file_menu = menu_bar.addMenu("&File")
        
        open_model_action = QAction("Open &3D Model...", self)
        open_model_action.triggered.connect(self.load_3d_model) 
        file_menu.addAction(open_model_action)
        
        open_image_action = QAction("Open &2D Image...", self) 
        open_image_action.triggered.connect(self.load_2d_image) 
        file_menu.addAction(open_image_action)
                
        save_as_action = QAction("Save &As (3D Model)...", self)
        save_as_action.triggered.connect(self.save_file_as)
        save_as_action.setEnabled(False) 
        self.save_as_action = save_as_action 
        file_menu.addAction(save_as_action)
        
        screenshot_action = QAction("&Screenshot...", self)
        screenshot_action.triggered.connect(self.take_screenshot)
        file_menu.addAction(screenshot_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close) 
        file_menu.addAction(exit_action)
        
    def update_button_states(self):
        # Enable/disable based on whether a 2D image is loaded
        self.remove_bg_button.setEnabled(self.is_2d_image_loaded)
        
        # Save As only enabled if a Trimesh object exists (original 3D model loaded)
        self.save_as_action.setEnabled(self.current_mesh_tr is not None)
        
        # Mesh color/reset only makes sense if something is loaded
        # For 2D images on plane, color override doesn't apply, so disable
        can_color_mesh = (self.current_mesh_pv is not None and not self.is_2d_image_loaded)
        self.mesh_color_button.setEnabled(can_color_mesh)
        self.reset_mesh_color_button.setEnabled(can_color_mesh)
        
        # Opacity slider enabled if anything is loaded
        can_set_opacity = self.current_mesh_pv is not None
        self.opacity_slider.setEnabled(can_set_opacity)

    def load_2d_image(self):
        self.statusBar().showMessage("Opening file dialog for 2D image...")
        filters = "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Open 2D Image File", "", filters)

        if not file_path:
            self.statusBar().showMessage("Image load cancelled.", 3000)
            return

        self.statusBar().showMessage(f"Loading image {os.path.basename(file_path)}...")
        QApplication.processEvents() 

        try:
            img_pil = Image.open(file_path).convert("RGBA") 
            self.current_image_pil = img_pil 
            self.current_filepath = file_path
            self.is_2d_image_loaded = True
            self.current_mesh_tr = None 
            self.display_image_on_plane() 
            self.statusBar().showMessage(f"Loaded image: {os.path.basename(self.current_filepath)}", 5000)
            self.update_button_states() 
        except Exception as e:
            self.reset_viewer_state() 
            error_message = f"Error loading image: {file_path}\\n{str(e)}"
            self._handle_error("Image Load Error", error_message)

    def display_image_on_plane(self):
         if self.current_image_pil is None:
             return 
         self.statusBar().showMessage("Displaying image on plane...")
         QApplication.processEvents()
         try:
             w, h = self.current_image_pil.size
             plane = pv.Plane(center=(w/2, h/2, 0), direction=(0, 0, 1), 
                             i_size=w, j_size=h, 
                             i_resolution=1, j_resolution=1) 
             image_np = np.array(self.current_image_pil)
             texture = pv.numpy_to_texture(image_np)
             self.current_mesh_pv = plane 
             self.plotter.clear() 
             self.plotter.add_mesh(self.current_mesh_pv, texture=texture, rgb=False, scalars=None) 
             self.plotter.camera_position = 'xy' 
             self.plotter.reset_camera() 
             self.override_color = None
             self.current_opacity = 1.0
             self.opacity_slider.setValue(100)
             self.opacity_label.setText("1.0")
             print(f"Displayed image {os.path.basename(self.current_filepath)} on a plane.")
             self.statusBar().showMessage(f"Image displayed: {os.path.basename(self.current_filepath)}", 5000)
             # Update button states AFTER display is successful
             self.update_button_states() 
         except Exception as e:
             self.reset_viewer_state()
             error_message = f"Error displaying image on plane: {str(e)}"
             self._handle_error("Display Error", error_message)

    def remove_image_background(self):
        if not self.is_2d_image_loaded or self.current_image_pil is None:
            self.statusBar().showMessage("No 2D image loaded to remove background from.", 3000)
            return
        self.statusBar().showMessage("Removing background (using rembg)...")
        QApplication.processEvents()
        try:
            img_byte_arr = io.BytesIO()
            self.current_image_pil.save(img_byte_arr, format='PNG') 
            img_byte_arr = img_byte_arr.getvalue()
            print("Running rembg.remove...")
            result_bytes = remove_background(img_byte_arr) 
            print("rembg processing complete.")
            result_img_pil = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
            self.current_image_pil = result_img_pil
            self.display_image_on_plane() 
            self.statusBar().showMessage("Background removed.", 5000)
            # self.update_button_states() # Already called by display_image_on_plane
        except Exception as e:
            error_message = f"Error removing background: {str(e)}\\nCheck rembg installation and model download."
            self._handle_error("Background Removal Error", error_message, reset_state=False)

    def load_3d_model(self):
        self.statusBar().showMessage("Opening file dialog for 3D model...")
        filters = [
            "Mesh Files (*.obj *.stl *.ply *.gltf *.glb *.dae *.off)",
            "Point Clouds (*.xyz)",
            "All Files (*)"
        ]
        file_path, _ = QFileDialog.getOpenFileName(self, "Open 3D Model File", "", ";;".join(filters))
        if not file_path:
            self.statusBar().showMessage("File load cancelled.", 3000)
            return 
        self.statusBar().showMessage(f"Loading {os.path.basename(file_path)}...")
        QApplication.processEvents() 
        try:
            print(f"Attempting to load with Trimesh: {file_path}")
            mesh_tr = trimesh.load(file_path, force='mesh')
            print(f"Trimesh loaded object of type: {type(mesh_tr)}")
            if isinstance(mesh_tr, trimesh.Scene):
                if len(mesh_tr.geometry) > 0:
                    print(f"Trimesh loaded a Scene. Concatenating geometry.")
                    mesh_tr = trimesh.util.concatenate(list(mesh_tr.geometry.values()))
                else:
                    raise ValueError("Trimesh loaded an empty scene.")
            if not isinstance(mesh_tr, trimesh.Trimesh):
                 raise TypeError(f"Loaded object is not a Trimesh mesh (type: {type(mesh_tr)}).")
            mesh_pv = pv.wrap(mesh_tr)
            print(f"Converted Trimesh to PyVista mesh.")
            if hasattr(mesh_tr, 'visual') and hasattr(mesh_tr.visual, 'vertex_colors') and len(mesh_tr.visual.vertex_colors) == mesh_tr.vertices.shape[0]:
                 colors = np.array(mesh_tr.visual.vertex_colors)
                 if colors.shape[1] == 4: colors = colors[:, :3]
                 if colors.dtype != np.uint8:
                     if np.max(colors) <= 1.0: colors = (colors * 255).astype(np.uint8)
                     else: colors = colors.astype(np.uint8)
                 mesh_pv.point_data['RGB'] = colors
                 print("Transferred vertex colors from Trimesh to PyVista.")
            self.current_mesh_tr = mesh_tr 
            self.current_mesh_pv = mesh_pv 
            self.current_image_pil = None 
            self.is_2d_image_loaded = False
            self.current_filepath = file_path
            self.override_color = None 
            self.current_opacity = 1.0
            self.opacity_slider.setValue(100)
            self.opacity_label.setText("1.0")
            self.plotter.clear() 
            self.update_representation() 
            self.plotter.reset_camera()
            status_text = f"Loaded: {os.path.basename(self.current_filepath)} | Vertices: {self.current_mesh_pv.n_points} | Cells: {self.current_mesh_pv.n_cells}"
            self.statusBar().showMessage(status_text)
            self.update_button_states() 
            print(f"Successfully loaded and displayed: {self.current_filepath}")
        except Exception as e:
            self.reset_viewer_state() 
            error_message = f"Error loading file with Trimesh: {file_path}\\n{str(e)}"
            self._handle_error("Load Error", error_message)

    def update_representation(self):
        if self.current_mesh_pv is None:
            self.plotter.clear() 
            return

        style = self.get_selected_style()
        is_flat_plane = (self.is_2d_image_loaded and isinstance(self.current_mesh_pv, pv.Plane))
        
        texture_to_use = None 

        if is_flat_plane:
            style = 'surface' 
            if self.current_image_pil:
                 try:
                     image_np = np.array(self.current_image_pil.convert("RGBA"))
                     texture_to_use = pv.numpy_to_texture(image_np)
                     print("Applying texture to plane.")
                 except Exception as tex_e:
                     print(f"Warning: Could not create texture from image: {tex_e}")
            else:
                 print("Warning: is_2d_image_loaded is True but current_image_pil is None.")
        # --- Removed structured grid style forcing ---
        # elif is_structured_grid and style != 'surface':
        #      print(f"Note: Forcing 'surface' style for generated grid (was {style}).")
        #      style = 'surface' 
        
        # --- Simplified show_edges logic ---
        show_edges = style == 'surface' and not is_flat_plane
        
        self.plotter.clear()
        
        # Disable color override for textured plane
        plot_color = self.override_color if not is_flat_plane else None 
        scalars_to_use = None
        rgb_active = False
        
        # Check for intrinsic colors if override is NOT set and not using texture
        if plot_color is None and texture_to_use is None:
            if 'RGB' in self.current_mesh_pv.point_data:
                scalars_to_use = 'RGB'
                rgb_active = True
                plot_color = None 
                print("Using RGB point data for coloring.")
            elif 'RGB' in self.current_mesh_pv.cell_data: 
                 scalars_to_use = 'RGB'
                 rgb_active = True
                 plot_color = None 
                 print("Using RGB cell data for coloring.")
        
        print(f"Adding mesh/plane: style='{style}', color={plot_color}, scalars='{scalars_to_use}', rgb={rgb_active}, opacity={self.current_opacity}, texture={texture_to_use is not None}")
        
        try:
             self.plotter.add_mesh(
                 self.current_mesh_pv, 
                 style=style, 
                 show_edges=show_edges, 
                 color=plot_color, 
                 scalars=scalars_to_use, 
                 rgb=rgb_active, 
                 opacity=self.current_opacity,
                 texture=texture_to_use 
             )
        except Exception as add_mesh_e:
             error_message = f"Error adding mesh to plotter: {add_mesh_e}"
             self._handle_error("Render Error", error_message, reset_state=True) 

    def reset_viewer_state(self):
        print("Resetting viewer state.")
        self.current_mesh_pv = None
        self.current_mesh_tr = None
        self.current_image_pil = None
        self.is_2d_image_loaded = False
        self.current_filepath = None
        self.override_color = None
        self.current_opacity = 1.0
        self.opacity_slider.setValue(100)
        self.opacity_label.setText("1.0")
        self.plotter.clear()
        self.statusBar().showMessage("Ready")
        self.update_button_states() 

    def _handle_error(self, title, message, reset_state=True):
        print(f"--- ERROR: {title} ---")
        import traceback
        traceback.print_exc()
        print(f"Error Message: {message}")
        print("----------------------")
        QMessageBox.critical(self, title, message)
        if reset_state:
             self.reset_viewer_state()
        else:
             self.statusBar().showMessage(f"{title} failed.", 5000)
             self.update_button_states()

    def set_background_color(self):
        color = QColorDialog.getColor()
        if color.isValid(): self.plotter.set_background(color.name())
    def set_mesh_color(self):
        # Disable if 2D image is loaded
        if self.is_2d_image_loaded:
             self.statusBar().showMessage("Mesh color cannot be applied to 2D images.", 3000)
             return
        color = QColorDialog.getColor()
        if color.isValid():
            self.override_color = color.name() 
            self.update_representation()
    def reset_mesh_color(self):
        # Disable if 2D image is loaded
        if self.is_2d_image_loaded:
             self.statusBar().showMessage("Mesh color cannot be applied to 2D images.", 3000)
             return
        self.override_color = None
        self.update_representation()
    def set_opacity(self, value):
        if self.current_mesh_pv is None: return
        self.current_opacity = value / 100.0 
        self.opacity_label.setText(f"{self.current_opacity:.2f}") 
        self.update_representation() 
    def get_selected_style(self):
        # Style doesn't apply to 2D image plane, but keep method for 3D models
        if self.radio_surface.isChecked(): return 'surface'
        elif self.radio_wireframe.isChecked(): return 'wireframe'
        elif self.radio_points.isChecked(): return 'points'
        return 'surface' 
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
                self._handle_error("Screenshot Error", error_message, reset_state=False)
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
            self.statusBar().showMessage("No original 3D model loaded to save.", 3000)
            QMessageBox.information(self, "Save As", "Can only save original 3D models loaded via 'Open 3D Model...'.")
            return

        suggested_name = "saved_mesh.ply"
        # Use self.current_filepath for suggestion
        if self.current_filepath:
            try:
                base = os.path.basename(self.current_filepath)
                root, _ = os.path.splitext(base)
                # Ensure suggestion is based on the original model path, not an image path
                if self.current_mesh_tr: # Double check we have trimesh obj
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
                # --- Color Export Logic (unchanged) ---
                colors_to_export = None
                if self.current_mesh_pv and 'RGB' in self.current_mesh_pv.point_data: # Check pv mesh exists too
                    colors_pv = self.current_mesh_pv.point_data['RGB']
                    # Check if pv colors match trimesh vertices count BEFORE attempting hstack
                    if colors_pv.shape[0] == self.current_mesh_tr.vertices.shape[0]:
                         print("Exporting with vertex colors from PyVista mesh.")
                         colors_to_export = colors_pv
                         # Trimesh export often needs RGBA
                         if colors_to_export.shape[1] == 3:
                            alpha = np.full((colors_to_export.shape[0], 1), 255, dtype=np.uint8)
                            colors_to_export = np.hstack((colors_to_export, alpha))
                    else:
                        print(f"Color array size mismatch (PV: {colors_pv.shape[0]}, TR: {self.current_mesh_tr.vertices.shape[0]}), exporting without explicit colors.")
                        colors_to_export = None
                else:
                    print("No RGB data found in PyVista mesh for export.")
                    colors_to_export = None
                # --- End Color Export Logic ---
                
                mesh_to_export = self.current_mesh_tr.copy()
                if colors_to_export is not None:
                    # Ensure color shape is correct (e.g., N x 4 for RGBA)
                    if colors_to_export.shape == (mesh_to_export.vertices.shape[0], 4):
                         mesh_to_export.visual.vertex_colors = colors_to_export
                    else:
                         print(f"Warning: Color array shape {colors_to_export.shape} not suitable for export, saving without colors.")

                export_result = mesh_to_export.export(fileName)
                
                if export_result is None or isinstance(export_result, str):
                     self.statusBar().showMessage(f"Mesh saved successfully to {fileName}", 5000)
                     print(f"Mesh saved via Trimesh to {fileName}")
                else: 
                     raise RuntimeError(f"Trimesh export returned unexpected type: {type(export_result)}")
            except Exception as e:
                error_message = f"Error saving file: {str(e)}"
                self._handle_error("Save Error", error_message, reset_state=False) # Don't reset on save fail
        else:
            self.statusBar().showMessage("Save As cancelled.", 3000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Ensure PIL settings allow large images if needed
    Image.MAX_IMAGE_PIXELS = None 

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
