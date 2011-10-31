import serial
import pyglet
import time
import threading
import Queue
import numpy as np
import measure_latency.primitives as primitives
import sys

__version__ = '1.0' # keep in sync with setup.py

if sys.platform.startswith('win'):
    time_func = time.clock
else:
    time_func = time.time

class SerialWatcher(object):
    def __init__(self,serial=None):
        self.ser=serial
        self.queue = Queue.Queue()
        self.watch_thread = threading.Thread(target=self.watch_func,args=(self.queue,))
        self.watch_thread.setDaemon(True)
        self.watch_thread.start()

    def watch_func(self, queue):
        while 1:
            line = self.ser.readline()
            if line=='':
                continue
            line = line.split()
            if len(line) != 2:
                continue
            cnt,val = map(int,line)
            queue.put( val )

    def get(self):
        result = []
        while 1:
            try:
                result.append( self.queue.get_nowait() )
            except Queue.Empty:
                break
        return result

class State(object):
    def __init__(self,window=None,patch=None,serial_watcher=None):
        self.window=window
        self.patch=patch
        self.serial_watcher=serial_watcher
    def quit_state(self,NextStateClass=None,kwargs=None):
        self.window.exit_state(NextStateClass=NextStateClass,kwargs=kwargs)
    def draw(self):
        pass
    def on_key_press(self, symbol, modifiers):
        pass

class FindMinMaxValues( State ):
    def __init__(self,**kwargs):
        super(FindMinMaxValues,self).__init__(**kwargs)
        self.flicker_freq_hz = 5.0
        self.label = pyglet.text.Label(('Detecting min/max. '
                                        'Press "c" to clear, <space> to continue.'
                                        ),
                                       font_name='Times New Roman',
                                       font_size=20,
                                       x=self.window.width//2, y=self.window.height//2,
                                       anchor_x='center', anchor_y='center',
                                       #multiline=True,
                                       width=self.window.width//2)

        self.min_label = pyglet.text.Label('min',
                                           font_name='Times New Roman',
                                           font_size=20,
                                           x=1*self.window.width//4, y=3*self.window.height//4,
                                           anchor_x='center', anchor_y='center')
        self.max_label = pyglet.text.Label('max',
                                           font_name='Times New Roman',
                                           font_size=20,
                                           x=3*self.window.width//4, y=3*self.window.height//4,
                                           anchor_x='center', anchor_y='center')

        self.clear_min_max()
        pyglet.clock.schedule(self.update)

    def clear_min_max(self):
        self.min = np.inf
        self.max = -np.inf
        self._update_labels()

    def draw(self):
        self.label.draw()
        self.min_label.draw()
        self.max_label.draw()

    def update(self,dt):
        t = time_func()
        x = (np.sin(t*2*np.pi*self.flicker_freq_hz)+1)*0.5
        self.patch.color=(x,x,x,1.0)
        if self.serial_watcher is not None:
            this_samples = self.serial_watcher.get()
            changed = False
            for sample in this_samples:
                if sample < self.min:
                    self.min = sample
                    changed = True
                if sample > self.max:
                    self.max = sample
                    changed = True
            if changed:
                self._update_labels()

    def _update_labels(self):
        self.min_label.document.text = str(self.min)
        self.max_label.document.text = str(self.max)

    def on_key_press(self, symbol, modifiers):
        if symbol==pyglet.window.key.C:
            self.clear_min_max()
        elif symbol==pyglet.window.key.SPACE:
            self.quit_state(NextStateClass=MeasureLatency,kwargs=dict(min=self.min,
                                                                      max=self.max))

    def quit_state(self,*args,**kwargs):
        pyglet.clock.unschedule(self.update)
        super(FindMinMaxValues,self).quit_state(**kwargs)

class MeasureLatency( State ):
    def __init__(self,min=None,max=None,**kwargs):
        super(MeasureLatency,self).__init__(**kwargs)
        self.patch.color=(0,0,0,1.)
        self.thresh = (min + max)/2.0
        self.holdoff_time = 0.1 # 100 msec
        self.substate = dict(cmd='wait until',
                             old_cmd='white->black',
                             until=time_func()+self.holdoff_time)
        self._clear_latencies()
        self.label = pyglet.text.Label(('Detecting latencies. '
                                        'Press "c" to clear measured values.'
                                        ),
                                       font_name='Times New Roman',
                                       font_size=20,
                                       x=10, y=self.window.height-10,
                                       anchor_y='top')

        self.bw_label = pyglet.text.Label('black->white',
                                          font_name='Times New Roman',
                                          font_size=20,
                                          x=10, y=3*self.window.height//4)

        self.wb_label = pyglet.text.Label('white->black',
                                          font_name='Times New Roman',
                                          font_size=20,
                                          x=10, y=3*self.window.height//4-100)

        pyglet.clock.schedule_interval(self.update, 0.001) # every msec

    def on_key_press(self, symbol, modifiers):
        if symbol==pyglet.window.key.C:
            self._clear_latencies()

    def _clear_latencies(self):
        self.latencies_msec = {'white->black':[],
                               'black->white':[],
                               }

    def update(self,dt):
        t = time_func()
        cmd = self.substate['cmd']
        this_samples = self.serial_watcher.get()
        if cmd == 'wait until':
            until = self.substate['until']
            if t >= until:
                if self.substate['old_cmd']=='white->black':
                    self.patch.color=(1,1,1,1)
                    self.substate = dict(cmd='black->white', t_cmd=t)
                else:
                    assert self.substate['old_cmd']=='black->white'
                    self.patch.color=(0,0,0,1)
                    self.substate = dict(cmd='white->black', t_cmd=t)

        elif cmd in ['black->white','white->black']:
            for sample in this_samples:
                if ((cmd == 'black->white' and sample >= self.thresh) or
                    (cmd == 'white->black' and sample < self.thresh)):
                    t_cmd = self.substate['t_cmd']
                    latency = t-t_cmd
                    self.record( cmd, latency )
                    self.substate=dict(cmd='wait until',old_cmd=cmd,until=t+self.holdoff_time)
                    break
        else:
            raise ValueError('unknown command %s'%cmd)

    def record( self, cmd, latency_sec ):
        self.latencies_msec[cmd].append(latency_sec*1000.0)
        self._update_text()

    def _update_text(self):
        def stats_str( vals ):
            if len(vals) >= 1:
                arr = np.array(vals)
                if len(arr) >= 2:
                    med = np.median(arr)
                    mean = np.mean(arr)
                    min = np.min(arr)
                    max = np.max(arr)
                    return '%.1f - %.1f (median: %.1f, mean: %.1f)'%(min,max,med,mean)
                else:
                    return '%.1f msec'%(vals[0],)
            else:
                return ''

        self.bw_label.document.text = 'black -> white : '+stats_str(self.latencies_msec['black->white'])
        self.wb_label.document.text = 'white -> black : '+stats_str(self.latencies_msec['white->black'])

    def draw(self):
        self.label.draw()
        self.bw_label.draw()
        self.wb_label.draw()

    def quit_state(self,*args,**kwargs):
        pyglet.clock.unschedule(self.update)
        super(MeasureLatency,self).quit_state(**kwargs)

class MyAppWindow(pyglet.window.Window):
    def __init__(self,port = '/dev/ttyUSB0',baudrate = 2000000,**kwargs):
        super(MyAppWindow, self).__init__(**kwargs)
        time.sleep(0.1) # reduce seg fault frequency on Ubuntu 10.04 with nvidia drivers
        ser = serial.Serial(port,baudrate)
        self.sw = SerialWatcher(serial=ser)
        self.patch = primitives.Circle(x=100,y=100,width=200)#,w=200,h=200)
        self.patch.color=(1,1,1,1)
        self._make_state(klass=FindMinMaxValues)

        self.f_count = -1
        self.first_t = None
        self.fps = 0.0
        lines = [ pyglet.gl.gl_info.get_vendor(),
                  pyglet.gl.gl_info.get_renderer(),
                  pyglet.gl.gl_info.get_version() ]
        self.gl_info_label = pyglet.text.Label( '\n'.join(lines),
                                           font_name='Times New Roman',
                                           font_size=20,
                                           x=self.width-10, y=90,
                                           anchor_x='right', anchor_y='bottom',
                                           multiline=True,
                                           width=self.width//2)

        self.instruction_label = pyglet.text.Label('press "v" to toggle vsync',
                                                   font_name='Times New Roman',
                                                   font_size=20,
                                                   x=self.width-10, y=50,
                                                   anchor_x='right', anchor_y='bottom')
        self.status_label = pyglet.text.Label(self._get_str(),
                                              font_name='Times New Roman',
                                              font_size=20,
                                              x=self.width-10, y=10,
                                              anchor_x='right', anchor_y='bottom')

    def _get_str(self):
        return 'vsync: %s, fps: %.1f'%( self.vsync, self.fps )

    def _make_state(self,klass,kwargs=None):
        if kwargs is None:
            kwargs = {}
        self.state = klass(window=self,
                           serial_watcher=self.sw,
                           patch=self.patch,
                           **kwargs)

    def on_draw(self):
        self.clear()
        self.state.draw()
        self.patch.render()
        self.gl_info_label.draw()
        self.instruction_label.draw()
        self.status_label.draw()

        t = time_func()
        self.f_count += 1
        if self.f_count==0:
            self.first_t = t
        else:
            dur = t-self.first_t
            if dur >= 1.0:
                self.fps = self.f_count/dur
                self.f_count = -1
                self.update_status_label()

    def update_status_label(self):
        self.status_label.document.text = self._get_str()

    def on_key_press(self, symbol, modifiers):
        if symbol==pyglet.window.key.ESCAPE:
            # pass escape through to pyglet for quitting
            super(MyAppWindow,self).on_key_press(symbol,modifiers)
        elif symbol==pyglet.window.key.V:
            self.set_vsync( not self.vsync )
            self.update_status_label()
        else:
            self.state.on_key_press(symbol,modifiers)

    def exit_state(self,NextStateClass=None,kwargs=None):
        assert NextStateClass is not None
        self._make_state(NextStateClass,kwargs=kwargs)

def main():
    if sys.platform.startswith('win'):
        port = 'COM3'
    elif sys.platform.startswith('linux'):
        port = '/dev/ttyUSB0'

    window = MyAppWindow(port=port,vsync=False)
    pyglet.app.run()

if __name__=='__main__':
    main()
