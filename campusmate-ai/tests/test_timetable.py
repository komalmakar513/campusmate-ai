import unittest

from app import format_timetable


def ocr_line(text, x, y):
    return {
        "text": text,
        "boundingBox": [
            x - 10, y - 5, x + 10, y - 5,
            x + 10, y + 5, x - 10, y + 5
        ]
    }


class FormatTimetableTests(unittest.TestCase):
    def setUp(self):
        days = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"
        ]
        self.lines = [
            ocr_line(day, 100 + index * 100, 40)
            for index, day in enumerate(days)
        ]
        self.lines.extend([
            ocr_line("9:00 AM - 10:00 AM", 30, 100),
            ocr_line("10:00 AM - 11:00 AM", 30, 200)
        ])

    def parse(self):
        text = "\n".join(line["text"] for line in self.lines)
        return format_timetable(text, self.lines)

    def test_entries_use_their_geometry_instead_of_defaulting_to_sunday(self):
        self.lines.append(ocr_line("Algorithms", 100, 100))
        self.lines.append(ocr_line("Physics", 200, 100))

        timetable = self.parse()

        self.assertTrue(timetable["valid"])
        self.assertEqual(
            timetable["rows"][0]["cells"]["Monday"]["subject"],
            "Algorithms"
        )
        self.assertEqual(
            timetable["rows"][0]["cells"]["Tuesday"]["subject"],
            "Physics"
        )
        self.assertEqual(
            timetable["rows"][0]["cells"]["Sunday"]["subject"], ""
        )

    def test_subject_code_suffix_is_not_a_room_and_location_codes_are(self):
        self.lines.extend([
            ocr_line("24CS", 300, 100),
            ocr_line("P-337", 300, 110),
            ocr_line("Dr Asha Rao", 300, 120),
            ocr_line("Block-D2-501", 400, 100),
            ocr_line("D2-301", 500, 100),
            ocr_line("24CSP-337", 600, 100)
        ])

        timetable = self.parse()
        cells = timetable["rows"][0]["cells"]

        self.assertEqual(cells["Wednesday"]["room"], "")
        self.assertEqual(cells["Wednesday"]["subject"], "24CS P-337")
        self.assertEqual(cells["Wednesday"]["teacher"], "Dr Asha Rao")
        self.assertEqual(cells["Thursday"]["room"], "Block-D2-501")
        self.assertEqual(cells["Friday"]["room"], "D2-301")
        self.assertEqual(cells["Saturday"]["subject"], "24CSP-337")
        self.assertEqual(cells["Saturday"]["room"], "")

    def test_entry_outside_confident_weekday_columns_stays_unassigned(self):
        self.lines.append(ocr_line("Seminar", 900, 100))

        timetable = self.parse()

        self.assertEqual(timetable["rows"][0]["unknown_day"]["subject"], "Seminar")
        self.assertTrue(all(
            timetable["rows"][0]["cells"][day]["subject"] == ""
            for day in timetable["days"]
        ))


if __name__ == "__main__":
    unittest.main()
