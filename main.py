import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
from typing import Type, Optional, TextIO
from functools import partial
import numpy as np
from PIL import Image, ImageFilter
from PIL.ImageTk import PhotoImage
import io
import pathlib as pl

FREQ = 900  # MHz
RECV_SENSITIVITY = -90  # dBm
RECV_HEIGHT = 1.5  # m
GRID_SIZE = 1  # km

# Friis equation:
# P_r = P_t + G_t + G_r + L_f
# assume isotropic receiver antenna
# P_r = P_t + G_t - 32.5 - 20 * log10(f) - 20 * log10(d)
# we can use distance squared to ommit square root
# P_r = P_t + G_t - 32.5 - 20 * log10(f) - 10 * log10(d**2)
# UE has signal if P_r > RECV_SENSITIVITY:
# P_t + G_t - 10 * log10(d**2) > RECV_SENSITIVITY + 32.5 + 20 * log10(f)
# P_t + G_t - 10 * log10(d**2) > RECV_MAGIC

RECV_MAGIC = RECV_SENSITIVITY + 32.5 + 20 * np.log10(FREQ)

# radiation patterns are stored as gain value (in dBi) in 2x360 matrices
# row 0 stores gain parts for each azimuth, row 1 for each elevation angle from the main radiation direction
# pattern[0,i] + pattern[1,j] returns gain for horizontal angle {i} and vertical angle {j}
hw_dipole_radiation = np.cos(np.radians(np.ogrid[:360])) ** 2
hw_dipole_radiation = 10 * np.log10(hw_dipole_radiation) + 2.15  # dBi
# hw_dipole_radiation = np.tile(hw_dipole_radiation, (360, 1))
hw_dipole_radiation = np.vstack([np.zeros(360), hw_dipole_radiation])

# def get_signal_map(dista)
SIM_SIZE = (1000, 700)
CALC_SIZE = float(max(SIM_SIZE) // 2)
X, Y = np.ogrid[-CALC_SIZE:CALC_SIZE, -CALC_SIZE:CALC_SIZE]
X *= GRID_SIZE
Y *= GRID_SIZE
DISTANCE = X**2 + Y**2
DISTANCE_SQRT = np.sqrt(DISTANCE)
AZIMUTH = np.rad2deg(np.arctan2(X, Y)).astype(int)


def center_Toplevel(top: tk.Toplevel):
    # Update the main window and Toplevel window to ensure they have a size
    top.master.update_idletasks()
    top.update_idletasks()
    # Calculate the position to center the Toplevel window on the main window
    position_right = (
        top.master.winfo_rootx()
        + (top.master.winfo_width() - top.winfo_reqwidth()) // 2
    )
    position_down = (
        top.master.winfo_rooty()
        + (top.master.winfo_height() - top.winfo_reqheight()) // 2
    )

    # Set the geometry of the Toplevel window to place it at the calculated position
    top.geometry(f"+{position_right}+{position_down}")
    top.minsize(top.winfo_reqwidth(), top.winfo_reqheight())


def parse_msi_file(fp: TextIO) -> np.ndarray:  # simple parser
    gain = 0.0
    pattern = np.empty((2, 360))
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


class app_object:
    x: int = 10
    y: int = 10
    canvas: tk.Canvas
    id: int = None
    outline_id: int = None
    _editable: list[str] = []

    def __init__(self, name) -> None:
        self.name = name

    def handle_keys(self, event: tk.Event):
        step = 5 * (10 if event.state & 4 != 0 else 1)  # check if CTRL is pressed
        if event.keysym == "Down":
            self.set_position(self.x, self.y + step)
        elif event.keysym == "Up":
            self.set_position(self.x, self.y - step)
        elif event.keysym == "Left":
            self.set_position(self.x - step, self.y)
        elif event.keysym == "Right":
            self.set_position(self.x + step, self.y)

    def _save_editables(self, window):
        try:
            for param in self._editable:
                setattr(
                    self, param, type(getattr(self, param))(window.entries[param].get())
                )
            return True
        except ValueError:
            return False

    def save_properties(self, window):
        prop = window.prop
        self.name = prop("name")
        self.set_position(int(prop("x")), int(prop("y")))
        if self._save_editables(window):
            window.destroy()
            if hasattr(self, "on_update"):
                self.on_update(self)

    def _edit_editables(self, window: tk.Toplevel):
        for i, param in enumerate(self._editable, start=window.grid_size()[1]):
            tk.Label(window, text=f"{param}:").grid(row=i, column=1, sticky="W")
            e = tk.Entry(window)
            e.grid(row=i, column=2)
            e.insert(0, getattr(self, param))
            window.entries[param] = e

    def edit(self):
        window = tk.Toplevel(self.canvas.master, padx=10, pady=5)
        window.entries = dict()
        window.prop = lambda property: window.entries[property].get()
        tk.Label(window, text="Edit Properties").grid(column=1, columnspan=2)
        for i, param in enumerate(("name", "x", "y"), 1):
            tk.Label(window, text=f"{param}:").grid(row=i, column=1, sticky="W")
            e = tk.Entry(window)
            e.grid(row=i, column=2)
            e.insert(0, getattr(self, param))
            window.entries[param] = e

        self._edit_editables(window)
        i = window.grid_size()[1]

        save_button = tk.Button(
            window, text="Save", command=lambda: self.save_properties(window)
        )
        save_button.grid(row=i + 1, column=1, columnspan=2)

        window.grid_columnconfigure([0, window.grid_size()[1] - 1], weight=1, pad=10)
        window.grid_rowconfigure(tuple(range(i + 1)), pad=5)
        center_Toplevel(window)
        window.focus_set()
        return window

    def delete(self):
        self.deselect()
        self.canvas.delete(self.id)

    def select(self):
        if not self.outline_id:
            self.outline_id = self.canvas.create_oval(
                *self.canvas.bbox(self.id), outline="red"
            )
        self.canvas.focus_set()

    def deselect(self):
        self.canvas.delete(self.outline_id)
        self.outline_id = None

    def drag(self, event: tk.Event):
        self.set_position(event.x, event.y)

    def draw(self, canvas: tk.Canvas) -> int:
        self.canvas = canvas
        self.size = 4
        return self.make_movable(
            canvas.create_oval(
                self.x - self.size,
                self.y - self.size,
                self.x + self.size,
                self.y + self.size,
                fill="black",
            )
        )

    def make_movable(self, id: int) -> int:
        self.id = id
        self.canvas.tag_bind(id, "<B1-Motion>", self.drag)
        return id

    def limit_position(self, x: int, y: int):
        margin = 5
        # {func: getattr(self.canvas, func)() for func in dir(self.canvas) if 'width' in func}
        return max(margin, min(x, self.canvas.winfo_width() - margin)), max(
            margin, min(y, self.canvas.winfo_height() - margin)
        )

    def set_position(self, x: int, y: int):
        self.x, self.y = self.limit_position(x, y)
        self.canvas.coords(
            self.id,
            self.x - self.size,
            self.y - self.size,
            self.x + self.size,
            self.y + self.size,
        )
        if self.outline_id:
            self.canvas.coords(self.outline_id, *self.canvas.bbox(self.id))

    def __str__(self):
        return self.name


class UE(app_object):
    def draw(self, canvas: tk.Canvas) -> int:
        from icons import UE_ICON as icon

        self.canvas = canvas
        return self.make_movable(canvas.create_image(self.x, self.y, image=icon))

    def set_position(self, x: int, y: int):
        self.x, self.y = self.limit_position(x, y)
        self.canvas.coords(self.id, self.x, self.y)
        if self.outline_id:
            self.canvas.coords(self.outline_id, *self.canvas.bbox(self.id))


def get_cropped_matrix(mat):
    idx = np.where(mat)
    if not idx[0].size:
        return np.zeros((3, 3), "bool")
    p = np.array(mat.shape) // 2
    mx, my = (max(abs(p[i] - idx[i].min()), abs(idx[i].max() - p[i])) for i in range(2))
    return mat[p[0] - mx : p[0] + mx + 1, p[1] - my : p[1] + my + 1]


def reorganize_array(arr):
    # Determine the midpoints for rows and columns
    mid_row = arr.shape[0] // 2
    mid_col = arr.shape[1] // 2

    # Split the array into four subarrays
    top_left = arr[:mid_row, :mid_col]
    top_right = arr[:mid_row, mid_col:]
    bottom_left = arr[mid_row:, :mid_col]
    bottom_right = arr[mid_row:, mid_col:]

    # Reorganize the subarrays
    return np.block([[bottom_right, bottom_left], [top_right, top_left]])


def compare_entry_value(entry, value):
    try:
        return type(value)(entry.get()) == value
    except ValueError:
        return False


class BTS(app_object):
    def __init__(self, name) -> None:
        super().__init__(name)
        self.radiation_pattern = hw_dipole_radiation
        self.antenna_name = tk.StringVar(value="half-wave dipole")

    _radiation_pattern: np.ndarray

    @property
    def radiation_pattern(self):
        return self._radiation_pattern

    @radiation_pattern.setter
    def radiation_pattern(self, value):
        self._radiation_pattern = value
        self.calc_signal_map()

    _signal_map: np.ndarray

    def calc_signal_map(self):
        tmp = self.power - 10 * np.log10(DISTANCE + (self.height - RECV_HEIGHT) ** 2)
        elevation = np.arctan2(DISTANCE_SQRT, (self.height - RECV_HEIGHT)).astype(int)
        tmp += (
            self.radiation_pattern[0, ((AZIMUTH + self.angle) % 360)]
            + self.radiation_pattern[1, elevation]
        )
        self.signal_map = get_cropped_matrix(tmp > RECV_MAGIC)

    @property
    def signal_map(self):
        return self._signal_map

    @signal_map.setter
    def signal_map(self, value):
        self._signal_map = value
        self.plot_signal()

    sig_plot_id: int = None
    img: PhotoImage = None

    def plot_signal(self):
        if not self.id:
            return
        img = (
            Image.fromarray(self._signal_map)
            .filter(ImageFilter.FIND_EDGES)
            .convert("P")
        )
        img.putpalette([0, 0, 0, 0, 0, 255, 0, 255] * 128, rawmode="RGBA")
        self.img = PhotoImage(img)
        if self.sig_plot_id:
            self.canvas.itemconfig(self.sig_plot_id, image=self.img)
        else:
            self.sig_plot_id = self.canvas.create_image(self.x, self.y, image=self.img)
            self.canvas.tag_lower(self.sig_plot_id)

    power: float = 30.0  # dBm
    height: float = 20.0
    angle: int = 0
    _editable: list[str] = ["power", "height", "angle"]

    def check_signal(self, obstacle_map: np.ndarray, ue: UE) -> bool:
        """Checks wheter the UEs' signal is good enough for transmission

        Args:
            obstacle_map (np.ndarray): mask with ones set where obstacles are present
            ue (UE): user device
        Returns:
            bool: True if UE has signal from this BTS
        """
        d = [ue.x - self.x, ue.y - self.y]
        s = self.signal_map.shape
        if (
            abs(d[0]) > s[1] / 2
            or abs(d[1]) > s[0] / 2
            or (
                not self.signal_map[
                    (d[1] + s[0] // 2) % s[0], (d[0] + s[1] // 2) % s[1]
                ]
            )
        ):
            return False

        if abs(d[1]) > abs(d[0]):  # more range over y
            a = d[0] / d[1]
            for y in range(self.y, ue.y, -1 if self.y > ue.y else 1):
                if obstacle_map[round(self.x + (y - self.y) * a), y]:
                    return False
        else:
            a = d[1] / d[0]
            for x in range(self.x, ue.x, -1 if self.x > ue.x else 1):
                if obstacle_map[x, round(self.y + a * (x - self.x))]:
                    return False
        return True

    def draw(self, canvas: tk.Canvas) -> int:
        from icons import BTS_ICON as icon

        self.canvas = canvas
        self.make_movable(canvas.create_image(self.x, self.y, image=icon))
        self.plot_signal()
        return self.id

    def delete(self):
        super().delete()
        if self.sig_plot_id:
            self.canvas.delete(self.sig_plot_id)

    def set_position(self, x: int, y: int):
        self.x, self.y = self.limit_position(x, y)
        self.canvas.coords(self.id, self.x, self.y)
        self.canvas.coords(self.sig_plot_id, self.x, self.y)
        if self.outline_id:
            self.canvas.coords(self.outline_id, *self.canvas.bbox(self.id))

    def _save_editables(self, window):
        changed = not all(
            compare_entry_value(window.entries[param], getattr(self, param))
            for param in self._editable
        )
        if not super()._save_editables(window):
            return False
        if "pattern" in window.entries:
            if not window.entries["pattern"]:
                self.radiation_pattern = hw_dipole_radiation
            else:
                with open(window.entries["pattern"], "r") as fp:
                    self.radiation_pattern = parse_msi_file(fp)
        elif changed:
            self.calc_signal_map()
        return True

    def _edit_editables(self, window: tk.Toplevel):
        super()._edit_editables(window)
        row = window.grid_size()[1]
        frame = tk.LabelFrame(window, relief="ridge", text="Antenna pattern")
        frame.grid(row=row + 1, column=1, columnspan=2, sticky="EW")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, pad=5)
        frame.rowconfigure(1, pad=5)
        tk.Label(frame, textvariable=self.antenna_name).grid(
            column=0, rowspan=2, sticky="NSW"
        )

        def file_pattern():
            file = filedialog.askopenfilename(
                filetypes=[("Radiation pattern files", "*.msi")],
                title="Select radiation pattern file",
            )
            window.entries["pattern"] = file
            self.antenna_name.set(pl.Path(file).name or "half-wave dipole")
            window.focus_set()

        file_button = tk.Button(frame, text="Loud", command=file_pattern)

        file_button.grid(row=0, column=1, sticky="EW")

        def reset_pattern():
            window.entries["pattern"] = None
            self.antenna_name.set("half-wave dipole")

        reset_button = tk.Button(frame, text="Reset", command=reset_pattern)
        reset_button.grid(row=1, column=1, sticky="EW")


class Obstacle(app_object):
    size: int = 4
    _editable = ["size"]

    def _save_editables(self, window):
        if not super()._save_editables(window):
            return False
        self.set_position(self.x, self.y)
        return True

    def add_self_to_map(self, ob_map: np.ndarray):
        X, Y = np.ogrid[: ob_map.shape[0], : ob_map.shape[1]]
        dist = (X - self.x) ** 2 + (Y - self.y) ** 2
        ob_map[dist <= self.size**2] = 1


class object_manager(ttk.Frame):
    objects: list[Type[app_object]] = []
    obj_lists: dict[str, tk.StringVar] = {}
    selected: Type[app_object] = None

    def __init__(self, master, canvas: tk.Canvas):
        self.canvas = canvas
        super().__init__(master)

    def register_class(self, cls: Type[app_object]):
        if len(self.obj_lists.keys()) > 0:
            s = ttk.Separator(self, orient=tk.HORIZONTAL)
            s.pack(side=tk.TOP, fill=tk.X, pady=5)
        self.obj_lists[cls.__name__] = tk.StringVar()
        frame = ttk.Frame(self)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        label = ttk.Label(frame, text=cls.__name__, padding=[5, 0])
        label.grid(row=0, column=0, sticky="W")
        add_button = ttk.Button(
            frame, text="+", command=partial(self.add_new, cls), width=2, padding=[0]
        )
        add_button.grid(row=0, column=1, sticky="E")
        listbox = tk.Listbox(frame, listvariable=self.obj_lists[cls.__name__], height=5)
        listbox.grid(row=1, columnspan=2, sticky="NSEW")
        listbox.bind("<Button-1>", self.handle_click)
        frame.rowconfigure(1, weight=1)

    def object_updated(self, obj):
        cls = type(obj)
        self.obj_lists[cls.__name__].set(
            [str(obj) for obj in self.objects if type(obj) is cls]
        )

    def add_new(self, cls: Type[app_object]):
        name = simpledialog.askstring(
            "Object Name", f"Enter name for new {cls.__name__}:"
        )
        if name:
            obj = cls(name)
            obj.on_update = self.object_updated
            self.objects.append(obj)
            self.object_updated(obj)
            obj.draw(self.canvas)

    def remove_object(self, obj: Type[app_object]):
        if not obj:
            return
        obj.delete()
        self.objects.remove(obj)
        self.obj_lists[type(obj).__name__].set(
            [str(o) for o in self.objects if type(o) is type(obj)]
        )
        if self.selected is obj:
            self.selected = None

    def object_from_attr(
        self,
        **kwargs,
        # id: Optional[int] = None,
        # name: Optional[str]=None,
    ) -> Type[app_object] | None:
        attr = tuple(kwargs.keys())[0]
        for obj in self.objects:
            if getattr(obj, attr) == kwargs[attr]:
                return obj
        return None

    def select_object(self, obj):
        if self.selected and self.selected is not obj:
            self.selected.deselect()
        self.selected = obj
        if obj:
            obj.select()
        return obj

    def handle_keys(self, event: tk.Event):
        if self.selected is None:
            return
        if event.keysym == "Escape":
            self.selected = self.selected.deselect()
        elif event.keysym == "e":
            self.selected.edit()
        elif event.keysym == "Delete":
            self.selected = self.remove_object(self.selected)
        else:
            self.selected.handle_keys(event)

    def find_closest_limited(self, x: int, y: int, limit: int = 10):
        id = self.canvas.find_closest(x, y)
        if not id:
            return None
        item_coords = self.canvas.coords(id)
        if not item_coords:
            return None

        # Calculate the center of the item
        if len(item_coords) == 4:
            item_x = (item_coords[0] + item_coords[2]) / 2
            item_y = (item_coords[1] + item_coords[3]) / 2
        else:
            item_x, item_y = item_coords
        # Calculate the distance between the given coordinates and the item's center
        distance = np.linalg.norm((item_x - x, item_y - y))

        # Check if the distance is within the specified radius
        return None if distance > limit else id[0]

    def handle_click(self, event: tk.Event):
        if event.widget is self.canvas:
            self.canvas.focus_set()
            id = self.find_closest_limited(event.x, event.y)
            if id is None:
                return
            self.select_object(self.object_from_attr(id=id))
        else:
            lb: tk.Listbox = event.widget
            if len(lb.curselection()) == 0:
                return
            self.select_object(self.object_from_attr(name=lb.get(lb.curselection()[0])))

    def handle_right_click(self, event: tk.Event):
        if event.widget is self.canvas:
            self.canvas.focus_set()
            id = self.find_closest_limited(event.x, event.y)
            if id is None:
                return
            obj = self.select_object(self.object_from_attr(id=id))
        else:
            lb: tk.Listbox = event.widget
            if len(lb.curselection()) == 0:
                return
            obj = self.select_object(
                self.object_from_attr(name=lb.get(lb.curselection()[0]))
            )
        if obj:
            obj.edit()


class sim_frame(ttk.Frame):
    OM: object_manager = None
    p_strim = io.StringIO()

    def __init__(self, master, OM: object_manager):
        super().__init__(master)
        self.OM = OM
        label = ttk.Label(self, text="Simulation", font=("Segoe UI", 14, "bold"))
        label.grid(row=0, column=0, sticky="W")
        add_button = ttk.Button(
            self, text="RUN", command=self.run_sim, width=4, padding=[0]
        )
        add_button.grid(row=0, column=1, sticky="E")
        lf = ttk.Labelframe(self, text="Select UEs to connect:", relief="sunken")
        lf.grid(row=1, columnspan=2, pady=5, sticky="EW")
        self.listbox = tk.Listbox(
            lf, listvariable=self.OM.obj_lists["UE"], height=5, selectmode=tk.MULTIPLE
        )
        self.listbox.pack(fill=tk.BOTH)

        self.printout = tk.StringVar()
        self.printout.set("Choose two UEs and press RUN")

        lf = ttk.Labelframe(self, text="Output:", relief="sunken")
        lf.grid(row=2, columnspan=2, sticky="NSEW")
        self.update_idletasks()
        txt = tk.Message(lf, textvariable=self.printout, width=190, anchor="nw")
        txt.pack(fill=tk.BOTH, side=tk.LEFT)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, minsize=170)

    def print(self, *args, clear=False, **kwargs):
        if clear:
            self.p_strim.truncate(0)
            self.p_strim.seek(0)
        print(*args, file=self.p_strim, **kwargs)
        self.printout.set(self.p_strim.getvalue())

    def run_sim(self):
        self.print("Starting analysis...", clear=True)
        ues = self.listbox.curselection()
        if len(ues) != 2:
            return self.print("ERR: Select two UEs!")
        # create obstacle map
        ob_map = np.zeros(
            (self.OM.canvas.winfo_height(), self.OM.canvas.winfo_width()), "bool"
        )
        for obj in filter(lambda o: isinstance(o, Obstacle), self.OM.objects):
            obj: Obstacle
            obj.add_self_to_map(ob_map)

        # check bts availability
        ue1, ue2 = (self.OM.object_from_attr(name=self.listbox.get(idx)) for idx in ues)
        l_ue1, l_ue2 = list(), list()
        for bts in filter(lambda o: isinstance(o, BTS), self.OM.objects):
            bts: BTS
            if bts.check_signal(ob_map, ue1):
                l_ue1.append(bts.name)
            if bts.check_signal(ob_map, ue2):
                l_ue2.append(bts.name)

        # check connection, optimize route
        def check_lue(ue, l_ue):
            if len(l_ue) < 1:
                self.print(f"ERR: {ue} has no signal!")
                return False
            self.print(f"UE {ue} can connect to: {l_ue}")
            return True

        if not (check_lue(ue1, l_ue1) and check_lue(ue2, l_ue2)):
            return

        self.print("Connection established!")
        for bts in l_ue1:
            if bts in l_ue2:
                self.print(ue1, bts, bts, ue2, sep="->")
                return
        self.print(ue1, l_ue1[0], l_ue2[0], ue2, sep="->")


class App(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.pack(padx=5, pady=5, expand=True, fill=tk.BOTH)
        self.canvas = tk.Canvas(self, bg="white")
        # self.bind("<Configure>", self.resize_canvas)
        self.OM = object_manager(self, self.canvas)
        self.OM.register_class(BTS)
        self.OM.register_class(UE)
        self.OM.register_class(Obstacle)
        self.sim = sim_frame(self, self.OM)

        s = ttk.Separator(self, orient=tk.VERTICAL)

        self.OM.pack(side=tk.LEFT, fill=tk.Y, pady=5)
        s.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        self.canvas.pack(
            side=tk.LEFT,
            expand=True,
            fill=tk.BOTH,
        )
        s = ttk.Separator(self, orient=tk.VERTICAL)
        s.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        self.sim.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind("<Button-1>", self.OM.handle_click)
        self.canvas.bind("<Button-3>", self.OM.handle_right_click)
        self.canvas.bind("<Key>", self.OM.handle_keys)
        master.update_idletasks()
        master.minsize(self.winfo_reqwidth() + 10, self.winfo_reqheight() + 10)
        master.maxsize(
            self.OM.winfo_reqwidth()
            + self.sim.winfo_reqwidth()
            + 2 * s.winfo_reqwidth()
            + 10
            + SIM_SIZE[0],
            10 + SIM_SIZE[1],
        )


if __name__ == "__main__":
    root = tk.Tk()
    root.option_add("*tearOff", tk.FALSE)
    root.title("Ugabugejszyn")
    myapp = App(root)
    root.mainloop()
