from vispy.plot import Fig
from vispy.plot import PlotWidget
import numpy as np
from functools import cache
import matplotlib.tri as mtri
import matplotlib
from typing import TextIO, Optional
import pathlib as pl

try:
    from vispy.plot import Fig
    from vispy.plot import PlotWidget
except ImportError:
    print("Vispy not found, plotting disabled")

# radiation patterns are stored as gain value (in dBi) in 2x360 matrices
# row 0 stores gain parts for each azimuth, row 1 for each elevation angle from the main radiation direction
# (pattern[0,i] + pattern[1,j]) represents gain for horizontal angle {i} and vertical angle {j}
HALF_WAVE_DIPOLE = np.cos(np.radians(np.ogrid[:360]))**2
HALF_WAVE_DIPOLE = 10 * np.log10(HALF_WAVE_DIPOLE) + 2.15  # dBi
# hw_dipole_radiation = np.tile(hw_dipole_radiation, (360, 1))
HALF_WAVE_DIPOLE = np.vstack([np.zeros(360), HALF_WAVE_DIPOLE])
"""Half-wave dipole radiation pattern"""


def normalize_linear(x: np.ndarray) -> np.ndarray:
    """Normalizes the input array to the range <0,1>

    Args:
        x (np.ndarray): input array

    Returns:
        np.ndarray: normalized array
    """
    return (x - np.min(x)) / (np.max(x) - np.min(x))


# @cache
def generate_mesh(angles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Creates a mesh of a unity sphere with the given angles

    Args:
        angles (np.ndarray): a vector of angles in degrees

    Returns:
        (np.ndarray,np.ndarray): vertices (Nv,3) and faces(Nf,3) of the mesh
    """
    rads = np.radians(angles)
    azimuth, elevation = np.meshgrid(rads, rads)
    tri = mtri.Triangulation(azimuth.flatten(), elevation.flatten())
    vol = np.empty((3, *angles.shape * 2))
    vol[0] = np.cos(elevation) * np.cos(azimuth)
    vol[1] = np.cos(elevation) * np.sin(azimuth)
    vol[2] = np.sin(elevation)
    return vol.reshape(3, -1).T, tri.triangles


def visualize_pattern(
    pattern: np.ndarray, plot: Optional[PlotWidget] = None, cmap: Optional[str] = "jet"
) -> None | Fig:
    """Displays a 3D plot of a radiation pattern

    Args:
        pattern (np.ndarray): array (2,N) of gain values
        plot (PlotWidget, optional): parent plotwidget for the mesh.
        If None a new `Fig` will be created.
        cmap (str, optional): colormap name. Defaults to "jet".

    Returns:
        None | Fig: created figure if plot is None, else None
    """
    if plot is None:
        fig = Fig(show=False)
        ax: PlotWidget = fig[0, 0]
    else:
        ax = plot

    step = 360 // pattern.shape[1]
    angles = np.arange(-180, 181, step)
    plt_data: np.ndarray = pattern[0, angles // step] + pattern[
        1, angles // step
    ].reshape(-1, 1)
    plt_data = plt_data.flatten().astype(np.float32)
    plt_data = np.clip(plt_data, -80, 100)
    # clim = (plt_data.min(), plt_data.max())
    plt_data -= plt_data.min()
    colour = matplotlib.colormaps[cmap](plt_data / plt_data.max())

    vertices, faces = generate_mesh(angles)
    vertices *= plt_data.reshape(-1, 1)

    ax.title.text = "3D radiation pattern"
    ax.mesh(vertices=vertices, faces=faces, vertex_colors=colour)
    # colorbar isn't visualized correctly, so skip for now
    # ax.colorbar(clim=clim, cmap=cmap, position='right',label='Gain [dBi]')
    return fig if plot is None else None

def plot_flat_pattern(
    pattern: np.ndarray, plot: Optional[PlotWidget] = None, cmap: Optional[str] = "jet"
) -> None | Fig:
    """Displays a 2d color plot of a radiation pattern

    Args:
        pattern (np.ndarray): array (2,N) of gain values
        plot (PlotWidget, optional): parent plotwidget for the mesh.
        If None a new `Fig` will be created.
        cmap (str, optional): colormap name. Defaults to "jet".

    Returns:
        None | Fig: created figure if plot is None, else None
    """
    if plot is None:
        fig = Fig(show=False)
        ax: PlotWidget = fig[0, 0]
    else:
        ax = plot

    step = 360 // pattern.shape[1]
    angles = np.arange(-180, 181, step)
    plt_data: np.ndarray = pattern[0, angles // step] + pattern[
        1, angles // step
    ].reshape(-1, 1)
    plt_data = np.clip(plt_data.astype(np.float32), -80, 100)
    clim = (plt_data.min(), plt_data.max())
    ax.image(plt_data, cmap=cmap)
    ax.colorbar(clim=[f"{x:.2f}" for x in clim], cmap=cmap, label='Gain [dBi]')
    ax.title.text = "Flattened radiation pattern"
    ax.xlabel.text = "Azimuth [deg]"
    ax.ylabel.text = "Elevation [deg]"
    return fig if plot is None else None

def pattern_from_msi_file(fp: TextIO) -> np.ndarray:  # simple parser
    gain = 0.0
    pattern = np.empty((2, 360))  # assume 360 points in file from 0 to 359 degrees
    reading_index = -1
    for line in fp.readlines():
        if line.startswith("GAIN"):
            gain = float(line.split()[1])
        elif line.startswith("HORIZONTAL"):
            reading_index = 0
            i = 0
        elif line.startswith("VERTICAL"):
            reading_index = 1
            i = 0
        elif reading_index != -1:
            pattern[reading_index, i] = -float(line.split()[1])
            i += 1
    if reading_index == -1:
        raise ValueError("Invalid file format")
    return pattern + gain / 2


def demo():
    fig = Fig(show=False, title="Radiation patterns demo")

    visualize_pattern(HALF_WAVE_DIPOLE, fig[1, 0])
    plot_flat_pattern(HALF_WAVE_DIPOLE, fig[1, 1])

    with open(pl.Path(__file__).parent.joinpath("-45 Port_898_T0.msi")) as f:
        pat = pattern_from_msi_file(f)
    visualize_pattern(pat, fig[0, 0])
    plot_flat_pattern(pat, fig[0, 1])

    fig.show(run=True)


if __name__ == "__main__":
    demo()
