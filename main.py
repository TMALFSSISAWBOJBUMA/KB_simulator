import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
from typing import Type
from functools import partial

FREQ = 900  # MHz


class app_object:
    x: int = 10
    y: int = 10
    height: float = 1.5
    angle: float = 0.0
    canvas: tk.Canvas
    id: int
    outline_id: int = None

    def __init__(self, name) -> None:
        self.name = name

    def handle_keys(self, event: tk.Event):
        if event.keysym == "Escape":
            return self.deselect()
        elif not self.outline_id:
            return
        step = 5 * (10 if event.state & 4 != 0 else 1)  # check if CTRL is pressed
        if event.keysym == "Down":
            self.set_position(self.x, self.y + step)
        elif event.keysym == "Up":
            self.set_position(self.x, self.y - step)
        elif event.keysym == "Left":
            self.set_position(self.x - step, self.y)
        elif event.keysym == "Right":
            self.set_position(self.x + step, self.y)

    def select(self, event: tk.Event):
        if not self.outline_id:
            self.outline_id = self.canvas.create_oval(
                *self.canvas.bbox(self.id), outline="red"
            )
        self.canvas.focus_set()
        self.canvas.bind("<Key>", self.handle_keys)

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
                fill="red",
            )
        )

    def make_movable(self, id: int) -> int:
        self.id = id
        self.canvas.tag_bind(id, "<Button-1>", self.select)
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


class BTS(app_object):
    def draw(self, canvas: tk.Canvas) -> int:
        from icons import BTS_ICON as icon

        self.canvas = canvas
        return self.make_movable(canvas.create_image(self.x, self.y, image=icon))

    def set_position(self, x: int, y: int):
        self.x, self.y = self.limit_position(x, y)
        self.canvas.coords(self.id, self.x, self.y)
        if self.outline_id:
            self.canvas.coords(self.outline_id, *self.canvas.bbox(self.id))


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


class Obstacle(app_object):
    pass


class object_manager(ttk.Frame):
    objects: dict[str, list[Type[app_object]]] = {}
    obj_lists: dict[str, tk.StringVar] = {}

    def __init__(self, master, canvas: tk.Canvas):
        self.canvas = canvas
        super().__init__(master)
        self.pack(fill=tk.BOTH, pady=5, expand=True)

    def register_class(self, cls: Type[app_object]):
        if len(self.objects.keys()) > 0:
            s = ttk.Separator(self, orient=tk.HORIZONTAL)
            s.pack(side=tk.TOP, fill=tk.X, pady=5)
        self.obj_lists[cls.__name__] = tk.StringVar()
        self.objects[cls.__name__] = list()
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
        frame.rowconfigure(1, weight=1)

    def add_new(self, cls: Type[app_object]):
        name = simpledialog.askstring(
            "Object Name", f"Enter name for new {cls.__name__}:"
        )
        if name:
            obj = cls(name)
            self.objects[cls.__name__].append(obj)
            self.obj_lists[cls.__name__].set(
                [str(obj) for obj in self.objects[cls.__name__]]
            )
            obj.draw(self.canvas)

    def handle_right_click(self, event: tk.Event):
        print(event.widget, event.widget.find_closest(event.x, event.y))

        # selected_id = self.canvas.find_closest(event.x, event.y)[0]
        # for obj in objects:
        #     if obj.id == selected_id:
        #         menu = tk.Menu(root, tearoff=0)
        #         menu.add_command(label="Edit Properties", command=obj.edit_properties)
        #         if obj.obj_type == "Obstacle":
        #             menu.add_command(label="Load File", command=obj.load_file)
        #         menu.post(event.x_root, event.y_root)


class App(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.pack(padx=5, pady=5, expand=True, fill=tk.BOTH)
        self.canvas = tk.Canvas(self, bg="white")
        self.canvas.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        # self.bind("<Configure>", self.resize_canvas)
        s = ttk.Separator(self, orient=tk.VERTICAL)
        s.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        self.OM = object_manager(self, self.canvas)
        self.OM.register_class(BTS)
        self.OM.register_class(UE)
        self.OM.register_class(Obstacle)

        self.canvas.bind("<Button-3>", self.OM.handle_right_click)

    def get_minsize(self):
        return (
            self.winfo_reqwidth() + 10,
            self.winfo_reqheight() + 10,
        )

    # def resize_canvas(self, event):
    #     self.canvas.config(width=event.width, height=event.height)


if __name__ == "__main__":
    root = tk.Tk()
    root.option_add("*tearOff", tk.FALSE)
    root.title("Ugabugejszyn")
    myapp = App(root)
    root.update_idletasks()  # Update the window to get accurate sizing
    root.minsize(*myapp.get_minsize())
    root.mainloop()
