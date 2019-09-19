from kivy.clock import Clock
import time


class Timing:
    @staticmethod
    def linear(x):
        return x


class Smooth:
    def __init__(self, interval=1.0/60.0):
        self.objs = []
        self.running = False
        self.interval = interval

    def run(self):
        if self.running:
            return
        self.running = True
        Clock.schedule_interval(self.update, self.interval)

    def stop(self):
        if not self.running:
            return
        self.running = False
        Clock.unschedule(self.update)

    def setattr(self, obj, attr, value):
        exec("obj." + attr + " = " + str(value))

    def getattr(self, obj, attr):
        return float(eval("obj." + attr))

    def update(self, _):
        cur_time = time.time()
        for line in self.objs:
            obj, prop_name_x, prop_name_y, from_x, from_y, to_x, to_y, start_time, period, timing = line
            time_gone = cur_time - start_time
            if time_gone >= period:
                self.setattr(obj, prop_name_x, to_x)
                self.setattr(obj, prop_name_y, to_y)
                self.objs.remove(line)
            else:
                share = time_gone / period
                acs = timing(share)
                self.setattr(obj, prop_name_x, from_x * (1 - acs) + to_x * acs)
                self.setattr(obj, prop_name_y, from_y * (1 - acs) + to_y * acs)
        if len(self.objs) == 0:
            self.stop()

    def move_to(self, obj, prop_name_x, prop_name_y, to_x, to_y, t, timing=Timing.linear):
        self.objs.append((obj, prop_name_x, prop_name_y, self.getattr(obj, prop_name_x), self.getattr(obj, prop_name_y), to_x,
                          to_y, time.time(), t, timing))
        self.run()


class XSmooth(Smooth):
    def __init__(self, props, timing=Timing.linear, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.props = props
        self.timing = timing

    def move_to(self, obj, to_x, to_y, t):
        super().move_to(obj, *self.props, to_x, to_y, t, timing=self.timing)
