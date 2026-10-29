#!/usr/bin/env python3
"""
deckd: exibe cartões periódicos como notificações do sistema.

Uso:
    deckd               # inicia o daemon normalmente
    deckd --test        # envia o próximo cartão imediatamente e sai
    deckd --list        # lista todos os cartões configurados e sai
    deckd --config PATH # usa um arquivo de configuração alternativo
"""

import argparse
import logging
import random
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# ─── Caminhos padrão ──────────────────────────────────────────────────────────

DEFAULT_CONFIG = Path.home() / ".config" / "deckd" / "config.toml"


# ─── Modelos de dados ─────────────────────────────────────────────────────────


@dataclass
class Card:
    title: str
    body: str


@dataclass
class Config:
    interval: int = 300
    expire_time: int = 8000
    icon: str = "dialog-information"
    order: str = "sequential"
    cards: list[Card] = field(default_factory=list)


# ─── Carregamento de configuração ─────────────────────────────────────────────


def load_config(path: Path) -> Config:
    """Carrega e valida o arquivo de configuração TOML."""
    with open(path, "rb") as f:
        data = tomllib.load(f)

    raw_cards = data.pop("cards", [])
    cards = []
    for i, raw in enumerate(raw_cards):
        try:
            cards.append(Card(title=raw["title"], body=raw["body"]))
        except KeyError as e:
            logging.warning(f"Cartão #{i+1} ignorado: campo obrigatório ausente: {e}")

    return Config(cards=cards, **{k: v for k, v in data.items() if k in Config.__dataclass_fields__})


# ─── Notificação ──────────────────────────────────────────────────────────────


def send_notification(card: Card, cfg: Config) -> None:
    """Envia uma notificação via notify-send."""
    cmd = [
        "notify-send",
        "--app-name=deckd",
        f"--expire-time={cfg.expire_time}",
        f"--icon={cfg.icon}",
        card.title,
        card.body,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"Erro ao enviar notificação: {result.stderr.strip()}")


# ─── Seleção de cartão ────────────────────────────────────────────────────────


class CardSelector:
    """Gerencia a seleção sequencial ou aleatória de cartões."""

    def __init__(self, cards: list[Card], order: str) -> None:
        self._cards = cards
        self._order = order
        self._index = 0

    def update(self, cards: list[Card], order: str) -> None:
        """Atualiza a lista sem resetar o índice se possível."""
        if order != self._order:
            self._order = order
            self._index = 0
        # Mantém índice válido após remoção de cartões
        if self._index >= len(cards):
            self._index = 0
        self._cards = cards

    def next(self) -> Card:
        if self._order == "random":
            return random.choice(self._cards)
        card = self._cards[self._index % len(self._cards)]
        self._index += 1
        return card


# ─── Loop principal ───────────────────────────────────────────────────────────


def run_daemon(config_path: Path) -> None:
    """Loop principal do daemon."""
    logging.info(f"Iniciando deckd. Config: {config_path}")

    try:
        cfg = load_config(config_path)
    except FileNotFoundError:
        logging.error(f"Arquivo de configuração não encontrado: {config_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Erro ao carregar configuração: {e}")
        sys.exit(1)

    if not cfg.cards:
        logging.error("Nenhum cartão encontrado na configuração. Encerrando.")
        sys.exit(1)

    selector = CardSelector(cfg.cards, cfg.order)
    logging.info(f"{len(cfg.cards)} cartão(s) carregado(s). Ordem: {cfg.order}. Intervalo: {cfg.interval}s.")

    while True:
        card = selector.next()
        logging.info(f"Exibindo: '{card.title}'")
        send_notification(card, cfg)

        time.sleep(cfg.interval)

        # Hot-reload: recarrega a config a cada ciclo
        try:
            new_cfg = load_config(config_path)
            if new_cfg.cards:
                selector.update(new_cfg.cards, new_cfg.order)
                cfg = new_cfg
            else:
                logging.warning("Config recarregada sem cartões válidos. Mantendo anterior.")
        except Exception as e:
            logging.warning(f"Falha ao recarregar config: {e}. Mantendo anterior.")


# ─── Comandos auxiliares ──────────────────────────────────────────────────────


def cmd_test(config_path: Path) -> None:
    """Envia o primeiro cartão imediatamente e sai."""
    cfg = load_config(config_path)
    if not cfg.cards:
        print("Nenhum cartão encontrado.", file=sys.stderr)
        sys.exit(1)
    card = cfg.cards[0]
    print(f"Enviando cartão de teste: '{card.title}'")
    send_notification(card, cfg)


def cmd_list(config_path: Path) -> None:
    """Lista todos os cartões configurados."""
    cfg = load_config(config_path)
    if not cfg.cards:
        print("Nenhum cartão encontrado.")
        return
    print(f"{'#':<4} {'Título':<30} {'Corpo'}")
    print("-" * 70)
    for i, card in enumerate(cfg.cards, 1):
        body_preview = card.body[:35] + "…" if len(card.body) > 35 else card.body
        print(f"{i:<4} {card.title:<30} {body_preview}")
    print(f"\nTotal: {len(cfg.cards)} cartão(s) | Intervalo: {cfg.interval}s | Ordem: {cfg.order}")


# ─── Ponto de entrada ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="deckd: notificações periódicas a partir de cartões configurados.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Caminho para o arquivo de configuração (padrão: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Envia o primeiro cartão imediatamente e sai",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista os cartões configurados e sai",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nível de log (padrão: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.test:
        cmd_test(args.config)
    elif args.list:
        cmd_list(args.config)
    else:
        run_daemon(args.config)


if __name__ == "__main__":
    main()
