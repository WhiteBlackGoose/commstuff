from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.properties import *
import random
import smooth


class Cell:
    def __init__(self, x, y):
        self.actual_pos = (x, y)

    def move_to(self, x, y):
        self.actual_pos = (x, y)

    def move_by(self, x, y):
        self.move_to(self.actual_pos[0] + x, self.actual_pos[1] + y)

    def get_pos(self):
        return self.actual_pos


class Fruit(Cell):
    def __init__(self, x, y):
        super().__init__(x, y)


class Worm(Widget):
    margin = NumericProperty(4)
    graphical_poses = ListProperty()
    inj_pos = ListProperty([-1000, -1000])
    graphical_size = NumericProperty(0)

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.cells = []
        self.config = config
        self.cell_size = config.CELL_SIZE
        self.head_init((self.config.CELL_SIZE * random.randint(3, 5), self.config.CELL_SIZE * random.randint(3, 5)))
        self.margin = config.MARGIN
        self.graphical_size = self.cell_size - self.margin
        for i in range(config.DEFAULT_LENGTH):
            self.lengthen()

    def destroy(self):
        self.cells = []
        self.graphical_poses = []
        self.inj_pos = [-1000, -1000]

    def cell_append(self, pos):
        self.cells.append(Cell(*pos))
        self.graphical_poses.extend([0, 0])
        self.cell_move_to(len(self.cells) - 1, pos)

    def lengthen(self, pos=None, direction=(0, 1)):
        if pos is None:
            px = self.cells[-1].get_pos()[0] + direction[0] * self.cell_size
            py = self.cells[-1].get_pos()[1] + direction[1] * self.cell_size
            pos = (px, py)
        self.cell_append(pos)

    def head_init(self, pos):
        self.lengthen(pos=pos)

    def cell_move_to(self, i, pos, smooth_motion=None):
        self.cells[i].move_to(*pos)
        to_x, to_y = pos[0], pos[1]
        if smooth_motion is None:
            self.graphical_poses[i * 2], self.graphical_poses[i * 2 + 1] = to_x, to_y
        else:
            smoother, t = smooth_motion
            smoother.move_to(self, "graphical_poses[" + str(i * 2) + "]", "graphical_poses[" + str(i * 2 + 1) + "]",
                             to_x, to_y, t)

    def move(self, direction, **kwargs):
        for i in range(len(self.cells) - 1, 0, -1):
            self.cell_move_to(i, self.cells[i - 1].get_pos(), **kwargs)
        self.cell_move_to(0, (self.cells[0].get_pos()[0] + self.cell_size * direction[0], self.cells[0].get_pos()[1] +
                              self.cell_size * direction[1]), **kwargs)

    def gather_positions(self):
        return [cell.get_pos() for cell in self.cells]

    def head_intersect(self, cell):
        return self.cells[0].get_pos() == cell.get_pos()


class Form(Widget):
    worm_len = NumericProperty(0)
    fruit_pos = ListProperty([0, 0])
    fruit_size = NumericProperty(0)

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.worm = None
        self.cur_dir = (0, 0)
        self.fruit = None
        self.game_on = True
        self.smooth = smooth.Smooth()

    def random_cell_location(self, offset):
        x_row = self.size[0] // self.config.CELL_SIZE
        x_col = self.size[1] // self.config.CELL_SIZE
        return random.randint(offset, x_row - offset), random.randint(offset, x_col - offset)

    def random_location(self, offset):
        x_row, x_col = self.random_cell_location(offset)
        return self.config.CELL_SIZE * x_row, self.config.CELL_SIZE * x_col

    def fruit_dislocate(self, xy=None):
        if xy is not None:
            x, y = xy
        else:
            x, y = self.random_location(2)
            while (x, y) in self.worm.gather_positions():
                x, y = self.random_location(2)
        self.fruit.move_to(x, y)
        self.fruit_pos = (x, y)

    def start(self):
        self.worm = Worm(self.config)
        self.add_widget(self.worm)
        self.fruit = Fruit(0, 0)
        self.fruit_size = self.config.APPLE_SIZE
        self.fruit_dislocate()
        self.game_on = True
        self.cur_dir = (0, -1)
        Clock.schedule_interval(self.update, self.config.INTERVAL)
        self.popup_label.text = ""

    def stop(self, text=""):
        self.game_on = False
        self.popup_label.text = text
        Clock.unschedule(self.update)

    def game_over(self):
        self.stop("GAME OVER" + " " * 5 + "\ntap to reset")

    def align_labels(self):
        self.popup_label.pos = ((self.size[0] - self.popup_label.width) / 2, self.size[1] / 2)
        self.score_label.pos = ((self.size[0] - self.score_label.width) / 2, self.size[1] - 80)

    def update(self, _):
        if not self.game_on:
            return
        self.worm.move(self.cur_dir, smooth_motion=(self.smooth, self.config.INTERVAL))
        if self.worm.head_intersect(self.fruit):
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            self.worm.lengthen(direction=random.choice(directions))
            self.fruit_dislocate()
        cell = self.worm_bite_self()
        if cell is not None:
            self.worm.inj_pos = cell.get_pos()
            self.game_over()
        self.worm_len = len(self.worm.cells)
        self.align_labels()

    def on_touch_down(self, touch):
        if not self.game_on:
            self.worm.destroy()
            self.start()
            return
        ws = touch.x / self.size[0]
        hs = touch.y / self.size[1]
        aws = 1 - ws
        if ws > hs and aws > hs:
            cur_dir = (0, -1)
        elif ws > hs >= aws:
            cur_dir = (1, 0)
        elif ws <= hs < aws:
            cur_dir = (-1, 0)
        else:
            cur_dir = (0, 1)
        self.cur_dir = cur_dir

    def worm_bite_self(self):
        for cell in self.worm.cells[1:]:
            if self.worm.head_intersect(cell):
                return cell
        return None


class Config:
    DEFAULT_LENGTH = 20
    CELL_SIZE = 26  # DO NOT FORGET THAT CELL_SIZE - MARGIN WILL BE DIVIDED BY 4
    APPLE_SIZE = 36
    MARGIN = 2
    INTERVAL = 0.3
    DEAD_CELL = (1, 0, 0, 1)
    APPLE_COLOR = (1, 1, 0, 1)


class WormApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.form = None

    def build(self, **kwargs):
        self.config = Config()
        self.form = Form(self.config, **kwargs)
        return self.form

    def on_start(self):
        self.form.start()


if __name__ == '__main__':
    WormApp().run()
