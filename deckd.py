#!/usr/bin/env python3
"""
deckd: exibe cartões periódicos como notificações do sistema.

Uso:
    deckd               # inicia o daemon normalmente
    deckd --test        # envia o próximo cartão imediatamente e sai
    deckd --list        # lista todos os cartões configurados e sai
    deckd --config PATH # usa um arquivo de configuração alternativo
"""

import abc
import argparse
import logging
import random
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ─── Constantes ───────────────────────────────────────────────────────────────

DEFAULT_CONFIG = Path.home() / ".config" / "deckd" / "config.toml"
_RETRY_DELAY_S = 2  
_MAX_RETRIES = 2


# ─── Tipos enumerados ─────────────────────────────────────────────────────────


class OrderMode(str, Enum):                  
    """Modos de ordenação dos cartões."""
    SEQUENTIAL = "sequential"
    RANDOM = "random"


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
    order: OrderMode = OrderMode.SEQUENTIAL
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

    # Converte a string de ordem para o Enum, mantendo o padrão em caso de valor inválido
    raw_order = data.pop("order", OrderMode.SEQUENTIAL.value)
    try:
        order = OrderMode(raw_order)
    except ValueError:
        logging.warning(f"Valor de 'order' inválido: '{raw_order}'. Usando 'sequential'.")
        order = OrderMode.SEQUENTIAL

    known_fields = {k for k in Config.__dataclass_fields__ if k not in ("order", "cards")}
    extra = {k: v for k, v in data.items() if k in known_fields}
    return Config(cards=cards, order=order, **extra)


def _load_initial_config(config_path: Path) -> Config:   
    """Carrega a config inicial; encerra o processo em caso de falha fatal."""
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

    return cfg


# ─── Notificação ──────────────────────────────────────────────────────────────


@dataclass
class NotificationRequest:                  
    """Agrupa os dados necessários para disparar uma notificação."""
    card: Card
    expire_time: int
    icon: str

    @staticmethod
    def from_config(card: Card, cfg: Config) -> "NotificationRequest":
        return NotificationRequest(
            card=card,
            expire_time=cfg.expire_time,
            icon=cfg.icon,
        )


def send_notification(request: NotificationRequest) -> bool:   
    """Envia uma notificação via notify-send com até _MAX_RETRIES tentativas."""
    cmd = [
        "notify-send",
        "--app-name=deckd",
        f"--expire-time={request.expire_time}",
        f"--icon={request.icon}",
        request.card.title,
        request.card.body,
    ]
    for attempt in range(_MAX_RETRIES):     
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        if attempt < _MAX_RETRIES - 1:
            time.sleep(_RETRY_DELAY_S)

    logging.error(f"Erro ao enviar notificação: {result.stderr.strip()}")
    return False


# ─── Seleção de cartão ────────────────────────────────────────────────────────


class CardSelector(abc.ABC):                   
    """Interface de seleção de cartões."""

    @abc.abstractmethod
    def next(self) -> Card:
        """Retorna o próximo cartão a exibir."""

    @abc.abstractmethod
    def update(self, cards: list[Card]) -> None:
        """Atualiza a lista de cartões disponíveis."""


class SequentialSelector(CardSelector):        
    """Seleciona cartões em ordem cíclica."""

    def __init__(self, cards: list[Card]) -> None:
        self._cards = cards
        self._index = 0

    def next(self) -> Card:
        card = self._cards[self._index % len(self._cards)]
        self._index += 1
        return card

    def update(self, cards: list[Card]) -> None:
        if self._index >= len(cards):
            self._index = 0
        self._cards = cards


class RandomSelector(CardSelector):            
    """Seleciona cartões aleatoriamente."""

    def __init__(self, cards: list[Card]) -> None:
        self._cards = cards

    def next(self) -> Card:
        return random.choice(self._cards)

    def update(self, cards: list[Card]) -> None:
        self._cards = cards


def make_selector(cards: list[Card], order: OrderMode) -> CardSelector:   
    """Instancia o seletor correto para o modo de ordem informado."""
    if order == OrderMode.RANDOM:
        return RandomSelector(cards)
    return SequentialSelector(cards)


# ─── Loop principal ───────────────────────────────────────────────────────────


def _try_hot_reload(config_path: Path, selector: CardSelector, cfg: Config) -> Config:
    """Tenta recarregar a config; em caso de falha, mantém a config anterior."""  
    try:
        new_cfg = load_config(config_path)
        if not new_cfg.cards:
            logging.warning("Config recarregada sem cartões válidos. Mantendo anterior.")
            return cfg
        if new_cfg.order != cfg.order:
            return new_cfg  # troca de modo → o daemon recria o seletor no próximo ciclo
        selector.update(new_cfg.cards)
        return new_cfg
    except Exception as e:
        logging.warning(f"Falha ao recarregar config: {e}. Mantendo anterior.")
        return cfg


def run_daemon(config_path: Path) -> None:
    """Loop principal do daemon."""
    logging.info(f"Iniciando deckd. Config: {config_path}")

    cfg = _load_initial_config(config_path)
    selector = make_selector(cfg.cards, cfg.order)
    logging.info(
        f"{len(cfg.cards)} cartão(s) carregado(s). "
        f"Ordem: {cfg.order.value}. Intervalo: {cfg.interval}s."
    )

    while True:
        card = selector.next()
        logging.info(f"Exibindo: '{card.title}'")
        send_notification(NotificationRequest.from_config(card, cfg))

        time.sleep(cfg.interval)

        prev_order = cfg.order
        cfg = _try_hot_reload(config_path, selector, cfg)

        # Recria o seletor se o modo de ordem mudou
        if cfg.order != prev_order:
            selector = make_selector(cfg.cards, cfg.order)
            logging.info(f"Modo de ordem alterado para: {cfg.order.value}")


# ─── Comandos auxiliares ──────────────────────────────────────────────────────


def _require_cards(cfg: Config) -> None:     
    """Encerra o processo se não houver cartões carregados."""
    if not cfg.cards:
        print("Nenhum cartão encontrado.", file=sys.stderr)
        sys.exit(1)


def cmd_test(config_path: Path) -> None:
    """Envia o primeiro cartão imediatamente e sai."""
    cfg = load_config(config_path)
    _require_cards(cfg)
    card = cfg.cards[0]
    print(f"Enviando cartão de teste: '{card.title}'")
    send_notification(NotificationRequest.from_config(card, cfg))


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
    print(f"\nTotal: {len(cfg.cards)} cartão(s) | Intervalo: {cfg.interval}s | Ordem: {cfg.order.value}")


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
