import unittest

from services.cad_identity import normalize_name, normalize_phone, normalize_cpf, normalize_cnpj


class CadIdentityTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(normalize_name('  Ana  '), 'Ana')
        self.assertEqual(len(normalize_name('a' * 200)), 200)
        for value in ('  ', 'a' * 201):
            with self.assertRaises(ValueError):
                normalize_name(value)

    def test_phone(self):
        self.assertEqual(normalize_phone('+55 (41) 99999-1234'), '41999991234')
        self.assertEqual(normalize_phone('(41) 3333-1234'), '4133331234')
        for value in ('0012345678', '41889991234', '55419999912345', '119999912345', '٤١٩٩٩٩٩١٢٣٤'):
            with self.assertRaises(ValueError):
                normalize_phone(value)

    def test_documents(self):
        self.assertEqual(normalize_cpf('529.982.247-25'), '52998224725')
        self.assertEqual(normalize_cnpj('04.252.011/0001-10'), '04252011000110')
        for value in ('11111111111', '52998224726', '123', '٥٢٩٩٨٢٢٤٧٢٥'):
            with self.assertRaises(ValueError):
                normalize_cpf(value)
        for value in ('00000000000000', '04252011000111', '123', '٠٤٢٥٢٠١١٠٠٠١١٠'):
            with self.assertRaises(ValueError):
                normalize_cnpj(value)


if __name__ == '__main__':
    unittest.main()
