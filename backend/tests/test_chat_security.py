import unittest

from backend.app.chat_service import fallback_plan, validate_sql


class SqlSecurityTests(unittest.TestCase):
    def test_accepts_read_only_aggregation(self):
        sql = validate_sql("select count(*) as total from ctrc")
        self.assertIn("select", sql.lower())

    def test_rejects_mutation(self):
        with self.assertRaises(ValueError):
            validate_sql("delete from ctrc")

    def test_rejects_multiple_statements(self):
        with self.assertRaises(ValueError):
            validate_sql("select count(*) from ctrc; select count(*) from manifesto")

    def test_rejects_sensitive_column(self):
        with self.assertRaises(ValueError):
            validate_sql("select cgc_dest from ctrc limit 10")

    def test_rejects_unknown_source(self):
        with self.assertRaises(ValueError):
            validate_sql("select count(*) from pg_user")

    def test_understands_branch_ranking(self):
        plan = fallback_plan("Quais filiais têm mais conhecimentos nos últimos 7 dias?")
        self.assertEqual(plan["title"], "Desempenho por filial")


if __name__ == "__main__":
    unittest.main()
