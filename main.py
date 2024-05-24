import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
from typing import Type, Optional
from functools import partial
import numpy as np
from PIL import Image, ImageFilter
from PIL.ImageTk import PhotoImage


FREQ = 900  # MHz
SIM_SIZE = (700, 1000)


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
        for param in self._editable:
            setattr(
                self, param, type(getattr(self, param))(window.entries[param].get())
            )
        return True

    def save_properties(self, window):
        prop = window.prop
        self.name = prop("name")
        self.set_position(int(prop("x")), int(prop("y")))
        if self._save_editables(window):
            window.destroy()

    def _edit_editables(self, window: tk.Toplevel):
        for i, param in enumerate(self._editable, start=window.grid_size()[0]):
            tk.Label(window, text=f"{param}:").grid(row=i, column=1)
            e = tk.Entry(window)
            e.grid(row=i, column=2)
            e.insert(0, getattr(self, param))
            window.entries[param] = e

    def edit(self):
        window = tk.Toplevel(self.canvas.master, padx=10, pady=5)
        window.entries = dict()
        window.prop = lambda property: window.entries[property].get()
        tk.Label(window, text="Edit Properties").grid(columnspan=4)
        for i, param in enumerate(("name", "x", "y"), 1):
            tk.Label(window, text=f"{param}:").grid(row=i, column=1)
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


class BTS(app_object):
    def __init__(self, name) -> None:
        super().__init__(name)
        X, Y = np.ogrid[: self.range * 2, : self.range * 2]
        dist = (X - self.range) ** 2 + (Y - self.range) ** 2
        self.signal_map = dist <= self.range**2

    _radiation_pattern: np.ndarray

    @property
    def radiation_pattern(self):
        return self._radiation_pattern

    @radiation_pattern.setter
    def radiation_pattern(self, value):
        self._radiation_pattern = value
        self.calc_signal_map()

    _signal_map: np.ndarray

    @property
    def signal_map(self):
        return self._signal_map

    @signal_map.setter
    def signal_map(self, value):
        self._signal_map = value
        self.plot_signal()
        # update view

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

    power: float = 30  # dBm
    range: int = 50
    height: float = 1.5
    angle: float = 0.0
    _editable: list[str] = ["range", "height", "angle"]

    def check_signal(self, obstacle_map: np.ndarray, ue: UE) -> np.ndarray:
        """Checks wheter the UEs' signal is good enough for transmission

        Args:
            obstacle_map (np.ndarray): mask with ones set where obstacles are present
            ue (UE): user device
        Returns:
            bool: True if UE has signal from this BTS
        """
        d = [ue.x - self.x, ue.y - self.y]
        if (
            abs(d(0)) > self.signal_map.shape(0) / 2
            or abs(d(1)) > self.signal_map.shape(1) / 2
            or (not self.signal_map[d(0), d(1)])
        ):
            return False

        a = d(1) / d(0)  # slope

        if d(1) > d(0):  # more range over y
            return obstacle_map[
                [
                    [round(self.y + (y - self.y) / a), y]
                    for y in range(self.y, ue.y, -1 if self.y > ue.y else 1)
                ]
            ].any()

        return obstacle_map[
            [
                [x, round(self.x + a * (x - self.x))]
                for x in range(self.x, ue.x, -1 if self.x > ue.x else 1)
            ]
        ].any()

    def draw(self, canvas: tk.Canvas) -> int:
        from icons import BTS_ICON as icon

        self.canvas = canvas
        self.make_movable(canvas.create_image(self.x, self.y, image=icon))
        self.plot_signal()
        return self.id

    def set_position(self, x: int, y: int):
        self.x, self.y = self.limit_position(x, y)
        self.canvas.coords(self.id, self.x, self.y)
        self.canvas.coords(self.sig_plot_id, self.x, self.y)
        if self.outline_id:
            self.canvas.coords(self.outline_id, *self.canvas.bbox(self.id))

    def _save_editables(self, window):
        if not super()._save_editables(window):
            return False
        X, Y = np.ogrid[: self.range * 2, : self.range * 2]
        dist = (X - self.range) ** 2 + (Y - self.range) ** 2
        self.signal_map = dist <= self.range**2
        return True


class Obstacle(app_object):
    size: int = 4
    _editable = ["size"]

    def _save_editables(self, window):
        if not super()._save_editables(window):
            return False
        self.set_position(self.x, self.y)
        return True


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

    def add_new(self, cls: Type[app_object]):
        name = simpledialog.askstring(
            "Object Name", f"Enter name for new {cls.__name__}:"
        )
        if name:
            obj = cls(name)
            self.objects.append(obj)
            self.obj_lists[cls.__name__].set(
                [str(obj) for obj in self.objects if type(obj) is cls]
            )
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
            self.select_object(self.object_from_attr(
                name=lb.get(lb.curselection()[0])))

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

    def __init__(self, master, OM: object_manager):
        super().__init__(master)
        self.OM = OM
        label = ttk.Label(self, text='Simulation',
                          font=('Segoe UI', 14, 'bold'))
        label.grid(row=0, column=0, sticky="W")
        add_button = ttk.Button(
            self, text="RUN", command=self.run_sim, width=4, padding=[0]
        )
        add_button.grid(row=0, column=1, sticky="E")
        lf = ttk.Labelframe(
            self, text='Select UEs to connect:', relief='sunken')
        lf.grid(row=1, columnspan=2, pady=5, sticky="EW")
        self.listbox = tk.Listbox(
            lf, listvariable=self.OM.obj_lists['UE'], height=5, selectmode=tk.MULTIPLE)
        self.listbox.pack(fill=tk.BOTH)

        self.printout = tk.StringVar()
        self.printout.set('Choose two UEs and press RUN')

        lf = ttk.Labelframe(self, text='Output:', relief='sunken')
        lf.grid(row=2, columnspan=2, sticky="NSEW")
        self.update_idletasks()
        txt = tk.Message(lf, textvariable=self.printout,
                         width=190, anchor="nw")
        txt.pack(fill=tk.BOTH, side=tk.LEFT)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, minsize=170)

    def run_sim(self):
        self.print("Starting analysis...", clear=True)
        ues = self.listbox.curselection()
        if len(ues) != 2:
            return self.print("ERR: Select two UEs!")
        return

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
        self.canvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH,)
        s = ttk.Separator(self, orient=tk.VERTICAL)
        s.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        self.sim.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind("<Button-1>", self.OM.handle_click)
        self.canvas.bind("<Button-3>", self.OM.handle_right_click)
        self.canvas.bind("<Key>", self.OM.handle_keys)
        master.update_idletasks()
        master.minsize(self.winfo_reqwidth() + 10, self.winfo_reqheight() + 10)
        master.maxsize(
            self.OM.winfo_reqwidth()+self.sim.winfo_reqwidth() + 2 *
            s.winfo_reqwidth() + 10 + SIM_SIZE[1],
            10 + SIM_SIZE[0],
        )


if __name__ == "__main__":
    root = tk.Tk()
    root.option_add("*tearOff", tk.FALSE)
    root.title("Ugabugejszyn")
    myapp = App(root)
    root.mainloop()
