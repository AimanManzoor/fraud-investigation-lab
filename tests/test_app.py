import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from tests import test_explorer


class AppTests(unittest.TestCase):
    def setUp(self):
        fixture = test_explorer.ExplorerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.app = AppTest.from_string(
            "from app import main\nmain("
            + repr(str(fixture.database)) + ")\n"
        ).run()

    def submit(self):
        self.app.button[0].click().run()
        self.assertFalse(self.app.exception)

    def test_filter_details_and_empty_results(self):
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.metric), 0)

        self.submit()
        self.assertEqual(self.app.metric[0].value, "4")

        self.app.selectbox[1].select("1")
        self.submit()
        self.assertEqual(self.app.metric[0].value, "2")

        self.app.selectbox[3].select(4).run()
        self.assertIn('"record_id": 4', self.app.json[0].value)

        self.app.text_input[1].set_value("10")
        self.submit()
        self.assertEqual(self.app.metric[0].value, "0")
        self.assertEqual(len(self.app.dataframe), 0)
        self.assertTrue(self.app.warning)

    def test_invalid_amount_clears_old_results(self):
        self.submit()
        self.app.text_input[1].set_value("0.001")
        self.submit()
        self.assertTrue(self.app.error)
        self.assertEqual(len(self.app.metric), 0)

    def test_missing_database_message(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.db"
            app = AppTest.from_string(
                "from app import main\nmain("
                + repr(str(missing)) + ")"
            ).run()
            app.button[0].click().run()

            self.assertFalse(app.exception)
            self.assertIn(
                "Typed database missing", app.error[0].value
            )
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
