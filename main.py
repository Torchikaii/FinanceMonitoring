import kivy
from kivy.app import App
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
import os
import threading
import json
try:
    import ntplib
except ImportError:
    ntplib = None
from datetime import datetime
import pytz

SETTINGS_FILE = 'settings.json'
SETTINGS_KEY = 'imported_file'

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f)

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

def get_timezone_from_settings():
    settings = load_settings()
    tz_str = settings.get('time', '').strip().upper()
    if tz_str.startswith('UTC'):
        try:
            offset = int(tz_str[3:].replace('+', ''))
            return pytz.FixedOffset(offset * 60)
        except Exception:
            pass
    return pytz.UTC

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
        elif option == 'Dismount':
            self.dismount_file()
        elif option == 'Adjust time':
            self.adjust_time()
        self.close_menu()

    def import_data(self):
        def on_file_selected(path):
            if not os.path.exists(path):
                # Create empty file if not exists
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('')
            self.imported_file = path
            self.imported = True
            # Save to settings.json
            settings = load_settings()
            settings[SETTINGS_KEY] = path
            save_settings(settings)
            self.ids.error_label.text = ''
        popup = FileChooserPopup(select_callback=on_file_selected)
        popup.open()

    def dismount_file(self):
        self.imported_file = None
        self.imported = False
        settings = load_settings()
        settings[SETTINGS_KEY] = ''
        save_settings(settings)
        self.ids.error_label.text = ''

    def export_data(self):
        imported_file = self.get_imported_file()
        if not imported_file:
            self.ids.error_label.text = 'Import data first!'
            return
        try:
            # Generate export file name
            from datetime import datetime
            base_dir = os.path.dirname(imported_file)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_name = f'exported_{timestamp}.txt'
            export_path = os.path.join(base_dir, export_name)
            # On Android, use external storage if possible
            if hasattr(os, 'environ') and 'ANDROID_ARGUMENT' in os.environ:
                try:
                    from android.storage import primary_external_storage_path
                    base_dir = primary_external_storage_path()
                    export_path = os.path.join(base_dir, export_name)
                except Exception:
                    pass
            with open(imported_file, 'r', encoding='utf-8') as src:
                data = src.read()
            with open(export_path, 'w', encoding='utf-8') as dst:
                dst.write(data.rstrip() + '\n')
            self.ids.error_label.text = f'Exported to {export_path}'
        except Exception as e:
            self.ids.error_label.text = f'Export failed: {e}'

    def get_imported_file(self):
        # Always check settings.json for the imported file
        settings = load_settings()
        path = settings.get(SETTINGS_KEY, '')
        if path:
            return path
        return None

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
        imported_file = self.get_imported_file()
        if not imported_file:
            self.ids.error_label.text = 'Import data first!'
            return
        # If date is just 'a' (with optional spaces), fetch current date and time from NTP or system, with timezone
        if date.lower() == 'a':
            actual_datetime = None
            tz = get_timezone_from_settings()
            try:
                c = ntplib.NTPClient()
                response = c.request('pool.ntp.org', version=3, timeout=2)
                dt_utc = datetime.utcfromtimestamp(response.tx_time).replace(tzinfo=pytz.UTC)
                dt = dt_utc.astimezone(tz)
                actual_datetime = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                dt_utc = datetime.now(pytz.UTC)
                dt = dt_utc.astimezone(tz)
                actual_datetime = dt.strftime('%Y-%m-%d %H:%M:%S')
            date = actual_datetime
        # Append to file, ensuring new entry is always on a new line
        try:
            needs_newline = False
            if os.path.getsize(imported_file) > 0:
                with open(imported_file, 'rb') as f:
                    f.seek(-1, os.SEEK_END)
                    last_char = f.read(1)
                    if last_char != b'\n':
                        needs_newline = True
            with open(imported_file, 'a', encoding='utf-8') as f:
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

    def adjust_time(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        input_box = TextInput(hint_text='Enter UTC offset (e.g. UTC+2, UTC-3)', multiline=False, size_hint_y=None, height='40dp')
        # Load current value
        settings = load_settings()
        input_box.text = settings.get('time', '')
        btn_layout = BoxLayout(size_hint_y=None, height='40dp')
        ok_btn = Button(text='OK')
        cancel_btn = Button(text='Cancel')
        btn_layout.add_widget(ok_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(input_box)
        content.add_widget(btn_layout)
        popup = Popup(title='Adjust Time Offset', content=content, size_hint=(0.7, 0.4), auto_dismiss=False)
        def on_ok(instance):
            value = input_box.text.strip().upper()
            if value.startswith('UTC'):
                try:
                    int(value[3:].replace('+', ''))
                    settings['time'] = value
                    save_settings(settings)
                    popup.dismiss()
                    self.ids.error_label.text = ''
                    return
                except Exception:
                    pass
            self.ids.error_label.text = 'Invalid UTC offset! Use e.g. UTC+2 or UTC-3.'
        ok_btn.bind(on_release=on_ok)
        cancel_btn.bind(on_release=lambda *a: popup.dismiss())
        popup.open()

class FinanceMonitorApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(InsertScreen(name='insert'))
        return sm

    def on_start(self):
        # Prompt for import on start if not already imported
        screen = self.root.get_screen('insert')
        if not screen.get_imported_file():
            screen.import_data()

if __name__ == '__main__':
    FinanceMonitorApp().run()

