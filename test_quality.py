import unittest
from osint_engine.quality import EmailValidator

class TestEmailQuality(unittest.TestCase):
    def test_invalid_email(self):
        self.assertEqual(EmailValidator.classify("bademail", 0.9, "PERSONAL"), "INVALID")
        self.assertEqual(EmailValidator.classify("bad@email@com", 0.9, "PERSONAL"), "INVALID")

    def test_disposable_email(self):
        self.assertEqual(EmailValidator.classify("test@mailinator.com", 0.95, "PERSONAL"), "SUPPRESSED")

    def test_low_confidence(self):
        self.assertEqual(EmailValidator.classify("info@company.com", 0.4, "ROLE_BASED"), "LOW_CONFIDENCE")
        self.assertEqual(EmailValidator.classify("john@company.com", 0.55, "PERSONAL"), "LOW_CONFIDENCE")

    def test_role_based(self):
        self.assertEqual(EmailValidator.classify("admin@company.com", 0.8, "ROLE_BASED"), "ROLE_BASED")

    def test_valid(self):
        self.assertEqual(EmailValidator.classify("john.doe@company.com", 0.95, "PERSONAL"), "VALID")
        self.assertEqual(EmailValidator.classify("jane@company.com", 0.99, "PERSONAL"), "VALID")

    def test_likely_valid(self):
        self.assertEqual(EmailValidator.classify("mike@company.com", 0.85, "PERSONAL"), "LIKELY_VALID")

if __name__ == '__main__':
    unittest.main()
