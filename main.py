import kivy
from kivy.app import App
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.lang import Builder

kivy.require("1.9.0")

print("success")

# Load the kv file
Builder.load_file('insert_screen.kv')

class InsertScreen(Screen):
    def clear_fields(self):
        self.ids.amount_input.text = ''
        self.ids.description_input.text = ''
        self.ids.date_input.text = ''

class FinanceMonitorApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(InsertScreen(name='insert'))
        return sm

if __name__ == '__main__':
    FinanceMonitorApp().run()

