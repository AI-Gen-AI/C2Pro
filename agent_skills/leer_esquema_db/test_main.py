"""Tests for the database schema reader skill."""
import importlib.util
import tempfile
import unittest
from pathlib import Path


MAIN_PATH = Path(__file__).with_name("main.py")
SPEC = importlib.util.spec_from_file_location("leer_esquema_db", MAIN_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
_extraer_de_modelo = MODULE._extraer_de_modelo
_extraer_de_migracion = MODULE._extraer_de_migracion


class ExtraerDeModeloTest(unittest.TestCase):
    def test_extrae_clases_que_heredan_de_base(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            model = Path(temp_dir) / "models.py"
            model.write_text(
                """class Document(TimestampMixin, Base):
    id = Column("id")
    title = Column('title')

class Other(Base):
    name = Column("name")
""",
                encoding="utf-8",
            )

            self.assertEqual(
                _extraer_de_modelo(model),
                [
                    {"nombre": "Document", "columnas": ["id", "title"]},
                    {"nombre": "Other", "columnas": ["name"]},
                ],
            )

    def test_inheritance_scan_is_bounded_to_single_class_header(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            model = Path(temp_dir) / "models.py"
            parents = ", ".join(["Mixin"] * 5000 + ["Base"])
            model.write_text(
                f"class LargeModel({parents}):\n"
                '    id = Column("id")\n',
                encoding="utf-8",
            )

            self.assertEqual(
                _extraer_de_modelo(model),
                [{"nombre": "LargeModel", "columnas": ["id"]}],
            )


class ExtraerDeMigracionTest(unittest.TestCase):
    def test_extrae_columnas_de_create_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            migration = Path(temp_dir) / "migration.sql"
            migration.write_text(
                """CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL
);""",
                encoding="utf-8",
            )

            self.assertEqual(
                _extraer_de_migracion(migration),
                [{"nombre": "documents", "columnas": ["id", "title"]}],
            )


if __name__ == "__main__":
    unittest.main()
