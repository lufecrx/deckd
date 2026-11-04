import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Adiciona o diretório raiz para importar deckd
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import deckd


class TestDeckdCardInsertion(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.toml"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cmd_add_to_existing_config(self):
        initial_content = (
            'interval = 300\n'
            'expire_time = 8000\n'
            'icon = "dialog-information"\n'
            'order = "sequential"\n\n'
            '[[cards]]\n'
            'title = "Card 1"\n'
            'body  = "Corpo 1"\n'
        )
        self.config_path.write_text(initial_content, encoding="utf-8")

        deckd.cmd_add(self.config_path, "Card 2", "Corpo 2")

        cfg = deckd.load_config(self.config_path)
        self.assertEqual(len(cfg.cards), 2)
        self.assertEqual(cfg.cards[0].title, "Card 1")
        self.assertEqual(cfg.cards[0].body, "Corpo 1")
        self.assertEqual(cfg.cards[1].title, "Card 2")
        self.assertEqual(cfg.cards[1].body, "Corpo 2")

    def test_cmd_add_to_non_existent_file(self):
        nested_config = Path(self.temp_dir.name) / "sub" / "dir" / "config.toml"
        self.assertFalse(nested_config.exists())

        deckd.cmd_add(nested_config, "Primeiro Card", "Corpo do primeiro card")

        self.assertTrue(nested_config.exists())
        cfg = deckd.load_config(nested_config)
        self.assertEqual(len(cfg.cards), 1)
        self.assertEqual(cfg.cards[0].title, "Primeiro Card")
        self.assertEqual(cfg.cards[0].body, "Corpo do primeiro card")
        self.assertEqual(cfg.interval, 300)

    def test_cmd_add_special_characters_and_emojis(self):
        title = 'Card com "aspas", barras \\ e emojis 💧 🧘 📋'
        body = 'Linha 1\nLinha 2 com "aspas duplas" e \'simples\'\ne tab:\t!'

        deckd.cmd_add(self.config_path, title, body)

        cfg = deckd.load_config(self.config_path)
        self.assertEqual(len(cfg.cards), 1)
        self.assertEqual(cfg.cards[0].title, title)
        self.assertEqual(cfg.cards[0].body, body)

    def test_cmd_add_empty_validation(self):
        with self.assertRaises(SystemExit) as cm:
            deckd.cmd_add(self.config_path, "   ", "Corpo válido")
        self.assertEqual(cm.exception.code, 1)

        with self.assertRaises(SystemExit) as cm:
            deckd.cmd_add(self.config_path, "Título válido", "   ")
        self.assertEqual(cm.exception.code, 1)

    def test_cli_execution_with_flag(self):
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "deckd.py"),
            "--config",
            str(self.config_path),
            "-n",
            "Card via CLI 🚀",
            "Corpo inserido pelo terminal",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Stderr: {res.stderr}")
        self.assertIn("✔ Cartão adicionado com sucesso", res.stdout)
        self.assertIn("Card via CLI 🚀", res.stdout)

        # Verifica com --list
        list_cmd = [
            sys.executable,
            str(PROJECT_ROOT / "deckd.py"),
            "--config",
            str(self.config_path),
            "--list",
        ]
        list_res = subprocess.run(list_cmd, capture_output=True, text=True)
        self.assertEqual(list_res.returncode, 0)
        self.assertIn("Card via CLI 🚀", list_res.stdout)

    def test_cli_mutual_exclusion(self):
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "deckd.py"),
            "--list",
            "-n",
            "Título",
            "Corpo",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not allowed with argument", res.stderr)


if __name__ == "__main__":
    unittest.main()
