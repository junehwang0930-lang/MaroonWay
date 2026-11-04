import unittest
import pipeline as p
from test_integrity import GOOD

HEADER = 'Texas A&M University\nGRADE DISTRIBUTION REPORT\nSpring 2026\nCollege: AT - Arts & Sciences\n'

class MetadataTests(unittest.TestCase):
    def validate(self, text, **overrides):
        self.assertTrue(callable(getattr(p, 'validate_metadata', None)), 'metadata validation is required')
        args = dict(year=2026, semester='SPRING', college='AT', college_name='Arts & Sciences')
        args.update(overrides)
        return p.validate_metadata([text], **args)

    def test_valid_header(self):
        self.assertEqual(self.validate(HEADER+GOOD).term, '2026-SPRING')

    def test_supported_boundary_terms_and_other_college(self):
        for year, semester in [(2023,'FALL'),(2024,'SPRING'),(2024,'FALL'),(2025,'SPRING'),(2025,'FALL'),(2026,'SPRING')]:
            with self.subTest(year=year,semester=semester):
                text=HEADER.replace('Spring 2026', f'{semester} {year}').replace('AT - Arts & Sciences','EN - Engineering')
                self.assertEqual(self.validate(text,year=year,semester=semester,college='EN',college_name='Engineering').college,'EN')

    def test_wrong_or_unknown_metadata_rejected(self):
        for text in [HEADER.replace('2026','2025'), HEADER.replace('Spring','Fall'), HEADER.replace('AT - Arts & Sciences','EN - Engineering'), HEADER.replace('GRADE DISTRIBUTION','GPA DISTRIBUTION'), HEADER.replace('Spring 2026',''), HEADER.replace('College: AT - Arts & Sciences',''), '']:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    self.validate(text+GOOD)

    def test_summer_and_outside_range_rejected(self):
        for year, semester in [(2023,'SPRING'),(2026,'FALL'),(2022,'FALL'),(2025,'SUMMER')]:
            with self.subTest(year=year,semester=semester):
                with self.assertRaises(ValueError):
                    self.validate(HEADER.replace('Spring 2026',f'{semester} {year}'),year=year,semester=semester)

    def test_conflicting_headers_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(HEADER+HEADER.replace('2026','2025')+GOOD)

    def test_body_cannot_supply_missing_metadata(self):
        with self.assertRaises(ValueError):
            self.validate(GOOD+'\n'+HEADER)

    def test_uncoded_college_name_cannot_authorize_arbitrary_code(self):
        text=HEADER.replace('AT - Arts & Sciences','Arts & Sciences')
        with self.assertRaises(ValueError):
            self.validate(text,college='EN')
        self.assertEqual(self.validate(text).college,'AT')

    def test_valid_page_cannot_mask_unverifiable_other_page(self):
        self.assertTrue(callable(getattr(p,'validate_metadata',None)))
        for bad in ['WINTER 2025','2025','WINTER 2026','']:
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                p.validate_metadata([HEADER+GOOD,HEADER.replace('Spring 2026',bad)+GOOD],year=2026,semester='SPRING',college='AT',college_name='Arts & Sciences')

    def test_headerless_section_page_is_rejected(self):
        with self.assertRaises(ValueError):
            p.validate_metadata([HEADER+GOOD,GOOD],year=2026,semester='SPRING',college='AT',college_name='Arts & Sciences')
