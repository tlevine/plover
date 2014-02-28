# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

import wx
from wx.lib.utils import AdjustRectToScreen
import sys
from plover.steno import normalize_steno

if sys.platform.startswith('win32'):
    import win32gui
    GetForegroundWindow = win32gui.GetForegroundWindow
    SetForegroundWindow = win32gui.SetForegroundWindow

    def SetTopApp():
        # Nothing else is necessary for windows.
        pass

elif sys.platform.startswith('darwin'):
    from Foundation import NSAppleScript
    from AppKit import NSApp, NSApplication

    def GetForegroundWindow():
        return NSAppleScript.alloc().initWithSource_("""
tell application "System Events"
    return unix id of first process whose frontmost = true
end tell""").executeAndReturnError_(None)[0].int32Value()

    def SetForegroundWindow(pid):
        NSAppleScript.alloc().initWithSource_("""
tell application "System Events"
    set the frontmost of first process whose unix id is %d to true
end tell""" % pid).executeAndReturnError_(None)

    def SetTopApp():
        NSApplication.sharedApplication()
        NSApp().activateIgnoringOtherApps_(True)

elif sys.platform.startswith('linux'):
    from subprocess import call, check_output, CalledProcessError

    def GetForegroundWindow():
        try:
            output = check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'])
            return output.split()[-1]
        except CalledProcessError:
            return None

    def SetForegroundWindow(w):
        try:
            call(['wmctrl', '-i', '-a', w])
        except CalledProcessError:
            pass

    def SetTopApp():
        try:
            call(['wmctrl', '-a', TITLE])
        except CalledProcessError:
            pass

else:
    # These functions are optional so provide a non-functional default 
    # implementation.
    def GetForegroundWindow():
        return None

    def SetForegroundWindow(w):
        pass

    def SetTopApp():
        pass

TITLE = 'Plover: Lookup'

class LookupDialog(wx.Dialog):
    
    BORDER = 3
    TRANSLATION_TEXT = 'Text:'
    
    other_instances = []
    
    def __init__(self, parent, engine, config):
        pos = (config.get_translation_frame_x(), 
               config.get_translation_frame_y())
        wx.Dialog.__init__(self, parent, wx.ID_ANY, TITLE, 
                           pos, wx.DefaultSize, 
                           wx.DEFAULT_DIALOG_STYLE, wx.DialogNameStr)

        self.config = config

        # components
        self.translation_text = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        cancel = wx.Button(self, id=wx.ID_CANCEL)
        self.listbox = wx.ListBox(self, size=wx.Size(210, 200))
        
        # layout
        global_sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(self, label=self.TRANSLATION_TEXT)
        sizer.Add(label, 
                  flag=wx.TOP | wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, 
                  border=self.BORDER)
        sizer.Add(self.translation_text, 
                  flag=wx.TOP | wx.RIGHT | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, 
                  border=self.BORDER)
        sizer.Add(cancel, 
                  flag=wx.TOP | wx.RIGHT | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, 
                  border=self.BORDER)
        global_sizer.Add(sizer)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.listbox,
                  flag=wx.ALL | wx.FIXED_MINSIZE,
                  border=self.BORDER)

        global_sizer.Add(sizer)
        
        self.SetAutoLayout(True)
        self.SetSizer(global_sizer)
        global_sizer.Fit(self)
        global_sizer.SetSizeHints(self)
        self.Layout()
        self.SetRect(AdjustRectToScreen(self.GetRect()))
        
        # events

        # The reason for the focus event here is to skip focus on tab traversal
        # of the buttons. But it seems that on windows this prevents the button
        # from being pressed. Leave this commented out until that problem is
        # resolved.
        #button.Bind(wx.EVT_SET_FOCUS, self.on_button_gained_focus)
        cancel.Bind(wx.EVT_BUTTON, self.on_close)
        #cancel.Bind(wx.EVT_SET_FOCUS, self.on_button_gained_focus)
        self.translation_text.Bind(wx.EVT_TEXT, self.on_translation_change)
        self.translation_text.Bind(wx.EVT_SET_FOCUS, self.on_translation_gained_focus)
        self.translation_text.Bind(wx.EVT_KILL_FOCUS, self.on_translation_lost_focus)
        self.translation_text.Bind(wx.EVT_TEXT_ENTER, self.on_close)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_MOVE, self.on_move)
        
        self.engine = engine
        
        # TODO: add functions on engine for state
        self.previous_state = self.engine.translator.get_state()
        # TODO: use state constructor?
        self.engine.translator.clear_state()
        self.translation_state = self.engine.translator.get_state()
        self.engine.translator.set_state(self.previous_state)
        
        self.last_window = GetForegroundWindow()
        
        # Now that we saved the last window we'll close other instances. This 
        # may restore their original window but we've already saved ours so it's 
        # fine.
        for instance in self.other_instances:
            instance.Close()
        del self.other_instances[:]
        self.other_instances.append(self)

    def on_close(self, event=None):
        self.engine.translator.set_state(self.previous_state)
        try:
            SetForegroundWindow(self.last_window)
        except:
            pass
        self.other_instances.remove(self)
        self.Destroy()

    def on_translation_change(self, event):
        # TODO: normalize dict entries to make reverse lookup more reliable with 
        # whitespace.
        translation = event.GetString().strip()
        self.listbox.Clear()
        if translation:
            d = self.engine.get_dictionary()
            strokes_list = d.reverse_lookup(translation)
            if strokes_list:
                entries = ('/'.join(x) for x in strokes_list)
                for str in entries:
                    self.listbox.Append(str)
            else:
                self.listbox.Append('No entries')
                
        self.GetSizer().Layout()

    def on_translation_gained_focus(self, event):
        self.engine.translator.set_state(self.translation_state)
        
    def on_translation_lost_focus(self, event):
        self.engine.translator.set_state(self.previous_state)

    def on_button_gained_focus(self, event):
        self.strokes_text.SetFocus()

    def on_move(self, event):
        pos = self.GetScreenPositionTuple()
        self.config.set_translation_frame_x(pos[0]) 
        self.config.set_translation_frame_y(pos[1])
        event.Skip()

    def _normalized_strokes(self):
        strokes = self.strokes_text.GetValue().upper().replace('/', ' ').split()
        strokes = normalize_steno('/'.join(strokes))
        return strokes

def Show(parent, engine, config):
    dialog_instance = LookupDialog(parent, engine, config)
    dialog_instance.Show()
    dialog_instance.Raise()
    dialog_instance.translation_text.SetFocus()
    SetTopApp()
