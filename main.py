import kivy
from kivy.app import App
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.button import Button
from kivy.uix.label import Label
import os
import threading
try:
    import ntplib
except ImportError:
    ntplib = None
from datetime import datetime

kivy.require("1.9.0")

# Load the kv file
Builder.load_file('insert_screen.kv')

class FileChooserPopup(Popup):
    def __init__(self, select_callback, **kwargs):
        super().__init__(**kwargs)
        self.title = 'Select file'
        self.size_hint = (0.9, 0.9)
        self.auto_dismiss = False
        layout = BoxLayout(orientation='vertical')
        self.filechooser = FileChooserIconView()
        layout.add_widget(self.filechooser)
        btn_layout = BoxLayout(size_hint_y=None, height='40dp')
        select_btn = Button(text='Select')
        cancel_btn = Button(text='Cancel')
        select_btn.bind(on_release=lambda *a: self._select(select_callback))
        cancel_btn.bind(on_release=self.dismiss)
        btn_layout.add_widget(select_btn)
        btn_layout.add_widget(cancel_btn)
        layout.add_widget(btn_layout)
        self.add_widget(layout)

    def _select(self, callback):
        if self.filechooser.selection:
            callback(self.filechooser.selection[0])
            self.dismiss()

class InsertScreen(Screen):
    imported_file = None
    imported = False

    def clear_fields(self):
        self.ids.amount_input.text = ''
        self.ids.description_input.text = ''
        self.ids.date_input.text = ''
        self.ids.error_label.text = ''

    def open_menu(self):
        self.ids.menu_dropdown.opacity = 1
        self.ids.menu_dropdown.disabled = False
        self.ids.menu_overlay.opacity = 1
        self.ids.menu_overlay.disabled = False

    def close_menu(self):
        self.ids.menu_dropdown.opacity = 0
        self.ids.menu_dropdown.disabled = True
        self.ids.menu_overlay.opacity = 0
        self.ids.menu_overlay.disabled = True

    def menu_option_selected(self, option):
        if option == 'Import data':
            self.import_data()
        elif option == 'Export data':
            self.export_data()
        self.close_menu()

    def import_data(self):
        def on_file_selected(path):
            if not os.path.exists(path):
                # Create empty file if not exists
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('')
            self.imported_file = path
            self.imported = True
            self.ids.error_label.text = ''
        popup = FileChooserPopup(select_callback=on_file_selected)
        popup.open()

    def export_data(self):
        if not self.imported_file:
            self.ids.error_label.text = 'Import data first!'
            return
        def on_file_selected(path):
            try:
                with open(self.imported_file, 'r', encoding='utf-8') as src:
                    data = src.read()
                with open(path, 'w', encoding='utf-8') as dst:
                    dst.write(data.rstrip() + '\n')
                self.ids.error_label.text = ''
            except Exception as e:
                self.ids.error_label.text = f'Export failed: {e}'
        popup = FileChooserPopup(select_callback=on_file_selected)
        popup.title = 'Export file as...'
        popup.open()

    def process_entry(self):
        amount = self.ids.amount_input.text.strip()
        description = self.ids.description_input.text.strip()
        date = self.ids.date_input.text.strip()
        if not (amount and description and date):
            self.ids.error_label.text = 'All fields are required!'
            return
        try:
            float(amount)
        except ValueError:
            self.ids.error_label.text = 'Amount must be a number!'
            return
        if not self.imported_file:
            self.ids.error_label.text = 'Import data first!'
            return
        # If date is just 'a' (with optional spaces), fetch current date from NTP or system
        if date.lower() == 'a':
            actual_date = None
            try:
                c = ntplib.NTPClient()
                response = c.request('pool.ntp.org', version=3, timeout=2)
                dt = datetime.utcfromtimestamp(response.tx_time)
                actual_date = dt.strftime('%Y-%m-%d')
            except Exception:
                actual_date = datetime.now().strftime('%Y-%m-%d')
            date = actual_date
        # Append to file, ensuring new entry is always on a new line
        try:
            needs_newline = False
            if os.path.getsize(self.imported_file) > 0:
                with open(self.imported_file, 'rb') as f:
                    f.seek(-1, os.SEEK_END)
                    last_char = f.read(1)
                    if last_char != b'\n':
                        needs_newline = True
            with open(self.imported_file, 'a', encoding='utf-8') as f:
                if needs_newline:
                    f.write('\n')
                f.write(f'{amount}, {description}, {date};\n')
            self.ids.error_label.text = ''
            self.clear_fields()
        except Exception as e:
            self.ids.error_label.text = f'Write failed: {e}'

    def on_date_text(self, text):
        if text.strip().lower() == 'a':
            def set_date():
                date_str = None
                if ntplib:
                    try:
                        c = ntplib.NTPClient()
                        response = c.request('pool.ntp.org', version=3, timeout=2)
                        dt = datetime.utcfromtimestamp(response.tx_time)
                        date_str = dt.strftime('%Y-%m-%d')
                    except Exception:
                        pass
                if not date_str:
                    # fallback to system time
                    date_str = datetime.now().strftime('%Y-%m-%d')
                def update_field():
                    self.ids.date_input.text = date_str
                self.ids.date_input.focus = False
                self.ids.date_input.focus = True
                self.ids.date_input.text = ''  # clear to trigger update
                self.ids.date_input.text = date_str
            threading.Thread(target=set_date, daemon=True).start()

class FinanceMonitorApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(InsertScreen(name='insert'))
        return sm

    def on_start(self):
        # Prompt for import on start if not already imported
        screen = self.root.get_screen('insert')
        if not screen.imported_file:
            screen.import_data()

if __name__ == '__main__':
    FinanceMonitorApp().run()

