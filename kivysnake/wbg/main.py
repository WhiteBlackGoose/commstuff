from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.properties import *
import random
import smooth


class Cell(Widget):
    graphical_size = ListProperty([1, 1])
    graphical_pos = ListProperty([1, 1])
    color = ListProperty([1, 1, 1, 1])

    def __init__(self, x, y, size, margin=4):
        super().__init__()
        self.actual_size = (size, size)
        self.graphical_size = (size - margin, size - margin)
        self.margin = margin
        self.actual_pos = (x, y)
        self.graphical_pos_attach()
        self.color = (0.2, 1.0, 0.2, 1.0)

    def graphical_pos_attach(self, smooth_motion=None):
        to_x, to_y = self.actual_pos[0] - self.graphical_size[0] / 2, self.actual_pos[1] - self.graphical_size[1] / 2
        if smooth_motion is None:
            self.graphical_pos = to_x, to_y
        else:
            smoother, t = smooth_motion
            smoother.move_to(self, to_x, to_y, t)

    def move_to(self, x, y, **kwargs):
        self.actual_pos = (x, y)
        self.graphical_pos_attach(**kwargs)

    def move_by(self, x, y, **kwargs):
        self.move_to(self.actual_pos[0] + x, self.actual_pos[1] + y, **kwargs)

    def get_pos(self):
        return self.actual_pos

    def step_by(self, direction, **kwargs):
        self.move_by(self.actual_size[0] * direction[0], self.actual_size[1] * direction[1], **kwargs)


class Worm(Widget):
    def __init__(self, config):
        super().__init__()
        self.cells = []
        self.config = config
        self.cell_size = config.CELL_SIZE
        self.head_init((100, 100))
        for i in range(config.DEFAULT_LENGTH):
            self.lengthen()

    def destroy(self):
        for i in range(len(self.cells)):
            self.remove_widget(self.cells[i])
        self.cells = []

    def lengthen(self, pos=None, direction=(0, 1)):
        if pos is None:
            px = self.cells[-1].get_pos()[0] + direction[0] * self.cell_size
            py = self.cells[-1].get_pos()[1] + direction[1] * self.cell_size
            pos = (px, py)
        self.cells.append(Cell(*pos, self.cell_size, margin=self.config.MARGIN))
        self.add_widget(self.cells[-1])

    def head_init(self, pos):
        self.lengthen(pos=pos)

    def move(self, direction, **kwargs):
        for i in range(len(self.cells) - 1, 0, -1):
            self.cells[i].move_to(*self.cells[i - 1].get_pos(), **kwargs)
        self.cells[0].step_by(direction, **kwargs)

    def gather_positions(self):
        return [cell.get_pos() for cell in self.cells]

    def head_intersect(self, cell):
        return self.cells[0].get_pos() == cell.get_pos()


class Form(Widget):
    worm_len = NumericProperty(0)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.worm = None
        self.cur_dir = (0, 0)
        self.fruit = None
        self.game_on = True
        self.smooth = smooth.XSmooth(["graphical_pos[0]", "graphical_pos[1]"])

    def random_cell_location(self, offset):
        x_row = self.size[0] // self.config.CELL_SIZE
        x_col = self.size[1] // self.config.CELL_SIZE
        return random.randint(offset, x_row - offset), random.randint(offset, x_col - offset)

    def random_location(self, offset):
        x_row, x_col = self.random_cell_location(offset)
        return self.config.CELL_SIZE * x_row, self.config.CELL_SIZE * x_col

    def fruit_dislocate(self):
        x, y = self.random_location(2)
        while (x, y) in self.worm.gather_positions():
            x, y = self.random_location(2)
        self.fruit.move_to(x, y)

    def start(self):
        self.worm = Worm(self.config)
        self.add_widget(self.worm)
        if self.fruit is not None:
            self.remove_widget(self.fruit)
        self.fruit = Cell(0, 0, self.config.APPLE_SIZE)
        self.fruit.color = (1.0, 0.2, 0.2, 1.0)
        self.fruit_dislocate()
        self.add_widget(self.fruit)
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
        try:
            self.popup_label.pos = ((self.size[0] - self.popup_label.width) / 2, self.size[1] / 2)
            self.score_label.pos = ((self.size[0] - self.score_label.width) / 2, self.size[1] - 80)
        except:
            print(self.__dict__)
            assert False

    def update(self, _):
        if not self.game_on:
            return
        self.worm.move(self.cur_dir, smooth_motion=(self.smooth, self.config.INTERVAL))
        if self.worm.head_intersect(self.fruit):
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            self.worm.lengthen(direction=random.choice(directions))
            self.fruit_dislocate()
        cell = self.worm_bite_self()
        if cell:
            cell.color = (1.0, 0.2, 0.2, 1.0)
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
        return False


class Config:
    DEFAULT_LENGTH = 20
    CELL_SIZE = 25
    APPLE_SIZE = 35
    MARGIN = 4
    INTERVAL = 0.3
    DEAD_CELL = (1, 0, 0, 1)
    APPLE_COLOR = (1, 1, 0, 1)


class WormApp(App):
    def build(self):
        self.config = Config()
        self.form = Form(self.config)
        return self.form

    def on_start(self):
        self.form.start()


if __name__ == '__main__':
    WormApp().run()
