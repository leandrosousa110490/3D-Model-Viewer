# Simple 3D Viewer

A basic 3D model viewer application built with Python, PyQt6, PyVista, and Trimesh.

## Features

*   Loads various 3D mesh file formats (OBJ, STL, PLY, GLTF, etc.) using Trimesh.
*   Displays meshes using PyVista.
*   Supports basic visualization styles (Surface, Wireframe, Points).
*   Allows changing background color.
*   Allows overriding mesh color.
*   Allows adjusting mesh opacity.
*   Uses vertex colors if present in the loaded file.

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

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

```bash
python main.py
```

## Generating Test Files (Optional)

The `generate_test_files.py` script can create some sample `.ply` files (a colored prism, cone, and sphere) and uncolored versions of the sphere in other formats inside a `test_files` directory.

```bash
python generate_test_files.py
``` 