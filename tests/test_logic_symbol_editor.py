import unittest

from streamlit.testing.v1 import AppTest

from components.logic_symbol_editor import append_logic_symbol


class LogicSymbolEditorTest(unittest.TestCase):
    def test_append_preserves_existing_content(self):
        self.assertEqual(append_logic_symbol("P → Q", "∧"), "P → Q∧")

    def test_symbol_button_appends_to_form_text(self):
        app = AppTest.from_string('''
import streamlit as st
from components.logic_symbol_editor import logic_symbol_editor

with st.form("logic_editor_test"):
    logic_symbol_editor("Problem", "logic_problem", "P")
    st.form_submit_button("Save")
''')

        app.run()
        self.assertFalse(app.exception)
        app.text_area(key="logic_problem").set_value("P → Q")
        app.button(key="logic_problem__logic_symbol_0").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key="logic_problem").value, "P → Q¬")


if __name__ == "__main__":
    unittest.main()
