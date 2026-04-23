from collections import defaultdict
import tkinter as tk

from OpenGL.GL import glViewport
from pyopengltk import OpenGLFrame

from PyEngine3D.Common import logger
from .GameBackend import GameBackend, Keyboard, Event


class _PyOpenGLTkFrame(OpenGLFrame):
    def __init__(self, master, backend, **kwargs):
        self.backend = backend
        OpenGLFrame.__init__(self, master, **kwargs)
        self.animate = 0

    def initgl(self):
        width = getattr(self, "width", 0) or self.winfo_width() or self.backend.goal_width or 1
        height = getattr(self, "height", 0) or self.winfo_height() or self.backend.goal_height or 1
        self.width = width
        self.height = height
        self.backend.on_context_created(width, height)

    def redraw(self):
        # Rendering is driven by CoreManager.update().
        pass


class PyOpenGLTk(GameBackend):
    def __init__(self, core_manager):
        GameBackend.__init__(self, core_manager)

        logger.info("GameBackend : pyopengltk")

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("PyEngine3D - Tkinter + PyOpenGL")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.key_pressed = defaultdict(bool)
        self.key_released = defaultdict(bool)

        self._context_ready = False
        self._event_dispatch_enabled = False
        self._mouse_initialized = False
        self._resize_signature = None
        self._destroyed = False

        self._setup_keyboard_map()

        self.gl_frame = _PyOpenGLTkFrame(self.root, self, width=1, height=1)
        self.gl_frame.pack(fill=tk.BOTH, expand=True)
        self.gl_frame.bind("<Configure>", self.on_resize)
        self.gl_frame.bind("<ButtonPress>", self.on_mouse_press)
        self.gl_frame.bind("<ButtonRelease>", self.on_mouse_release)
        self.gl_frame.bind("<Motion>", self.on_mouse_move)
        self.gl_frame.bind("<B1-Motion>", self.on_mouse_move)
        self.gl_frame.bind("<B2-Motion>", self.on_mouse_move)
        self.gl_frame.bind("<B3-Motion>", self.on_mouse_move)
        self.gl_frame.bind("<MouseWheel>", self.on_mouse_wheel)
        self.gl_frame.bind("<Button-4>", self.on_mouse_wheel)
        self.gl_frame.bind("<Button-5>", self.on_mouse_wheel)

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)

        self.valid = True

    def _setup_keyboard_map(self):
        keyboard_map = {
            "BACKSPACE": "backspace",
            "TAB": "tab",
            "RETURN": "return",
            "ENTER": "return",
            "ESCAPE": "escape",
            "SPACE": "space",
            "HOME": "home",
            "LEFT": "left",
            "UP": "up",
            "RIGHT": "right",
            "DOWN": "down",
            "PAGEUP": "prior",
            "PAGEDOWN": "next",
            "END": "end",
            "DELETE": "delete",
            "INSERT": "insert",
            "F1": "f1",
            "F2": "f2",
            "F3": "f3",
            "F4": "f4",
            "F5": "f5",
            "F6": "f6",
            "F7": "f7",
            "F8": "f8",
            "F9": "f9",
            "F10": "f10",
            "F11": "f11",
            "F12": "f12",
            "LSHIFT": "shift_l",
            "RSHIFT": "shift_r",
            "LCTRL": "control_l",
            "RCTRL": "control_r",
            "LALT": "alt_l",
            "RALT": "alt_r",
            "CAPSLOCK": "caps_lock",
            "BACKQUOTE": "quoteleft",
            "COMMA": "comma",
            "MINUS": "minus",
            "PERIOD": "period",
            "SLASH": "slash",
            "SEMICOLON": "semicolon",
            "EQUAL": "equal",
            "BRACKETLEFT": "bracketleft",
            "BACKSLASH": "backslash",
            "BRACKETRIGHT": "bracketright",
            "QUOTELEFT": "quoteleft",
        }

        for index in range(10):
            keyboard_map["_%d" % index] = str(index)

        for char_code in range(ord("A"), ord("Z") + 1):
            char = chr(char_code)
            keyboard_map[char] = char.lower()

        for name, value in keyboard_map.items():
            setattr(Keyboard, name, value)
            self.key_pressed[value] = False

    def _normalize_key(self, event):
        keysym = (event.keysym or "").lower()
        char = event.char or ""

        keysym_alias = {
            "escape": "escape",
            "return": "return",
            "kp_enter": "return",
            "tab": "tab",
            "backspace": "backspace",
            "space": "space",
            "delete": "delete",
            "insert": "insert",
            "home": "home",
            "left": "left",
            "up": "up",
            "right": "right",
            "down": "down",
            "prior": "prior",
            "next": "next",
            "end": "end",
            "shift_l": "shift_l",
            "shift_r": "shift_r",
            "control_l": "control_l",
            "control_r": "control_r",
            "alt_l": "alt_l",
            "alt_r": "alt_r",
            "caps_lock": "caps_lock",
            "quoteleft": "quoteleft",
            "grave": "quoteleft",
            "comma": "comma",
            "minus": "minus",
            "period": "period",
            "slash": "slash",
            "semicolon": "semicolon",
            "equal": "equal",
            "bracketleft": "bracketleft",
            "backslash": "backslash",
            "bracketright": "bracketright",
        }

        if keysym in keysym_alias:
            return keysym_alias[keysym]
        if keysym.startswith("f") and keysym[1:].isdigit():
            return keysym

        if len(char) == 1:
            lower_char = char.lower()
            if lower_char.isalnum():
                return lower_char
            return {
                "`": "quoteleft",
                ",": "comma",
                "-": "minus",
                ".": "period",
                "/": "slash",
                ";": "semicolon",
                "=": "equal",
                "[": "bracketleft",
                "\\": "backslash",
                "]": "bracketright",
            }.get(char)

        return keysym or None

    def _update_keyboard_state(self):
        self.keyboard_pressed = any(self.key_pressed.values())

    def _update_mouse_position(self, x, y):
        current_height = self.gl_frame.winfo_height() or self.height or self.goal_height
        mouse_x = float(x)
        mouse_y = float(current_height - y)

        if not self._mouse_initialized:
            self.mouse_pos[0] = mouse_x
            self.mouse_pos[1] = mouse_y
            self.mouse_pos_old[...] = self.mouse_pos
            self._mouse_initialized = True
            return

        self.mouse_pos_old[...] = self.mouse_pos
        self.mouse_pos[0] = mouse_x
        self.mouse_pos[1] = mouse_y
        self.mouse_delta[...] += self.mouse_pos - self.mouse_pos_old

    def _clear_frame_state(self):
        self.btn_l_down = False
        self.btn_m_down = False
        self.btn_r_down = False
        self.btn_l_up = False
        self.btn_m_up = False
        self.btn_r_up = False
        self.wheel_up = False
        self.wheel_down = False
        self.keyboard_down = False
        self.keyboard_up = False
        self.key_released.clear()
        self.text = ""
        self.mouse_delta[...] = 0.0

    def on_context_created(self, width, height):
        self._context_ready = True
        if 0 < width and 0 < height:
            self.goal_width = width
            self.goal_height = height
            glViewport(0, 0, width, height)

    def set_mouse_grab(self, grab):
        GameBackend.set_mouse_grab(self, grab)
        self.set_mouse_visible(not grab)
        if grab:
            self.gl_frame.focus_force()

    def set_window_title(self, title):
        self.root.title(title)

    def set_mouse_visible(self, visible):
        cursor = "" if visible else "none"
        self.gl_frame.configure(cursor=cursor)

    def do_change_resolution(self):
        self.root.attributes("-fullscreen", self.full_screen)
        if not self.full_screen and 0 < self.width and 0 < self.height:
            self.root.geometry("%dx%d" % (self.width, self.height))

        self.root.deiconify()
        self.root.update_idletasks()
        if not self._context_ready or not self.running:
            self.root.update()
        self.gl_frame.focus_force()

    def create_window(self, width, height, fullscreen):
        GameBackend.create_window(self, width, height, fullscreen)
        self.goal_width = self.width
        self.goal_height = self.height
        self._resize_signature = (self.width, self.height, self.full_screen)

    def change_resolution(self, width, height, full_screen):
        GameBackend.change_resolution(self, width, height, full_screen)
        self.goal_width = self.width
        self.goal_height = self.height
        self._resize_signature = (self.width, self.height, self.full_screen)

    def on_key_press(self, event):
        if not self._event_dispatch_enabled:
            return

        key = self._normalize_key(event)
        if not key:
            return

        self.text = event.char if event.char and event.char.isprintable() else ""
        self.keyboard_down = True
        self.key_pressed[key] = True
        self.key_released[key] = False
        self._update_keyboard_state()

        if self.text:
            self.core_manager.update_event(Event.TEXT, self.text)
        self.core_manager.update_event(Event.KEYDOWN, key)

    def on_key_release(self, event):
        if not self._event_dispatch_enabled:
            return

        key = self._normalize_key(event)
        if not key:
            return

        self.text = ""
        self.keyboard_up = True
        self.key_pressed[key] = False
        self.key_released[key] = True
        self._update_keyboard_state()
        self.core_manager.update_event(Event.KEYUP, key)

    def on_mouse_press(self, event):
        if not self._event_dispatch_enabled:
            return

        self._update_mouse_position(event.x, event.y)

        if event.num == 1:
            self.btn_l_down = True
            self.btn_l_pressed = True
        elif event.num == 2:
            self.btn_m_down = True
            self.btn_m_pressed = True
        elif event.num == 3:
            self.btn_r_down = True
            self.btn_r_pressed = True

        self.core_manager.update_event(Event.MOUSE_BUTTON_DOWN)

    def on_mouse_release(self, event):
        if not self._event_dispatch_enabled:
            return

        self._update_mouse_position(event.x, event.y)

        if event.num == 1:
            self.btn_l_up = True
            self.btn_l_pressed = False
        elif event.num == 2:
            self.btn_m_up = True
            self.btn_m_pressed = False
        elif event.num == 3:
            self.btn_r_up = True
            self.btn_r_pressed = False

        self.core_manager.update_event(Event.MOUSE_BUTTON_UP)

    def on_mouse_move(self, event):
        if not self._event_dispatch_enabled:
            return

        self._update_mouse_position(event.x, event.y)
        self.core_manager.update_event(Event.MOUSE_MOVE)

    def on_mouse_wheel(self, event):
        if not self._event_dispatch_enabled:
            return

        if hasattr(event, "delta") and event.delta:
            if 0 < event.delta:
                self.wheel_up = True
            elif event.delta < 0:
                self.wheel_down = True
        elif getattr(event, "num", None) == 4:
            self.wheel_up = True
        elif getattr(event, "num", None) == 5:
            self.wheel_down = True

        self.core_manager.update_event(Event.MOUSE_BUTTON_DOWN)

    def on_resize(self, event):
        if event.widget is not self.gl_frame:
            return
        if event.width <= 0 or event.height <= 0:
            return

        self.goal_width = event.width
        self.goal_height = event.height

        if self._context_ready:
            self.gl_frame.tkMakeCurrent()
            glViewport(0, 0, event.width, event.height)

        resize_signature = (event.width, event.height, self.full_screen)
        if self._event_dispatch_enabled and resize_signature != self._resize_signature:
            self._resize_signature = resize_signature
            self.core_manager.update_event(Event.VIDEORESIZE, resize_signature)

    def on_close(self):
        if self._event_dispatch_enabled:
            self.core_manager.update_event(Event.QUIT)
        else:
            self.close()

    def update_event(self):
        # Tkinter dispatches events through callbacks.
        pass

    def get_keyboard_pressed(self):
        return self.key_pressed

    def flip(self):
        if self._context_ready:
            self.gl_frame.tkSwapBuffers()

    def _tick(self):
        if not self.running or self._destroyed:
            return

        if not self._context_ready:
            self.root.after(1, self._tick)
            return

        self.gl_frame.tkMakeCurrent()
        self.core_manager.update()
        self._clear_frame_state()
        self.root.after(1, self._tick)

    def run(self):
        self.running = True
        self._event_dispatch_enabled = True
        self.gl_frame.focus_force()
        self.root.after(0, self._tick)
        self.root.mainloop()

    def close(self):
        self.running = False
        try:
            self.root.quit()
        except tk.TclError:
            pass

    def quit(self):
        self.running = False
        self._event_dispatch_enabled = False
        if self._destroyed:
            return

        self._destroyed = True
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def create_sound_listner(self):
        return None

    def create_sound(self, filepath):
        return None

    def play_sound(self, sound, loop=False, volume=1.0, position=None):
        return None

    def stop_sound(self, sound):
        pass

    def is_sound_playing(self, sound):
        return False
