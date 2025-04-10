# Simple 3D/2D Viewer

A basic 3D model and 2D image viewer application built with Python, PyQt6, PyVista, Trimesh, and Rembg.

## Features

*   **3D Models:**
    *   Loads various 3D mesh file formats (OBJ, STL, PLY, GLTF, etc.) using Trimesh via `File > Open 3D Model...`.
    *   Displays 3D meshes using PyVista.
    *   Supports basic visualization styles (Surface, Wireframe, Points).
    *   Allows changing background color.
    *   Allows overriding mesh color (for 3D models only).
    *   Allows adjusting mesh/image opacity.
    *   Uses vertex colors if present in the loaded 3D model file.
    *   Displays basic mesh info (vertex/cell count) in status bar.
    *   Saves the loaded 3D mesh to various formats (PLY, STL, OBJ, GLB, etc.) via `File > Save As (3D Model)...`.
*   **2D Images:**
    *   Loads various 2D image formats (PNG, JPG, BMP, TIFF, etc.) via `File > Open 2D Image...`.
    *   Displays loaded 2D images on a flat plane within the 3D viewer.
    *   Allows removing the background from the loaded 2D image using the "Remove Background" button (powered by `rembg`).
*   **General:**
    *   Saves screenshots of the current view (PNG with transparent background, JPG) via `File > Screenshot...`.

## Setup

1.  **Clone the repository (Optional - if already on GitHub):**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    *   **Crucial for Windows Users:** The background removal feature uses `onnxruntime`, which requires the **Microsoft Visual C++ Redistributable**. Please download and install the latest **X64** version from [here](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170) and **restart your computer** before proceeding.
    *   Install Python packages:
        ```bash
        pip install -r requirements.txt
        ```
        *Note: The first time you use the "Remove Background" feature, the `rembg` library might automatically download necessary AI models.*

## Running the Application

```bash
python main.py
```

## Generating Test Files (Optional)

The `generate_test_files.py` script (if present) can create some sample `.ply` files (a colored prism, cone, and sphere) and uncolored versions of the sphere in other formats inside a `test_files` directory.

```bash
python generate_test_files.py
``` 