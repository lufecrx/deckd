#!/usr/bin/env bash
# install.sh — Instala deckd como serviço systemd do usuário
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/deckd"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "🃏 Instalando deckd..."

# Cria diretórios necessários
mkdir -p "$CONFIG_DIR" "$BIN_DIR" "$SYSTEMD_DIR"

# Instala o executável
cp "$SCRIPT_DIR/deckd.py" "$BIN_DIR/deckd"
chmod +x "$BIN_DIR/deckd"
echo "  ✔ Executável instalado em $BIN_DIR/deckd"

# Copia config de exemplo apenas se não existir
if [ ! -f "$CONFIG_DIR/config.toml" ]; then
    cp "$SCRIPT_DIR/config.toml" "$CONFIG_DIR/config.toml"
    echo "  ✔ Configuração de exemplo criada em $CONFIG_DIR/config.toml"
else
    echo "  ℹ  Configuração existente mantida em $CONFIG_DIR/config.toml"
fi

# Cria o serviço systemd
cat > "$SYSTEMD_DIR/deckd.service" << EOF
[Unit]
Description=deckd — notificações periódicas de cartões
Documentation=https://github.com/lufecrx/deckd
PartOf=graphical-session.target
After=graphical-session.target
Requisite=graphical-session.target

[Service]
ExecStart=$BIN_DIR/deckd
Restart=on-failure
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target
EOF
echo "  ✔ Serviço systemd criado em $SYSTEMD_DIR/deckd.service"

# Habilita e inicia o serviço
systemctl --user daemon-reload
systemctl --user reenable --now deckd.service 2>/dev/null || systemctl --user enable --now deckd.service
echo "  ✔ Serviço habilitado e iniciado"

echo ""
echo "✅ deckd instalado com sucesso!"
echo ""
echo "   📝 Edite seus cartões:  $CONFIG_DIR/config.toml"
echo "   📋 Ver cartões ativos:  deckd --list"
echo "   🧪 Testar agora:        deckd --test"
echo "   📜 Ver logs:            journalctl --user -u deckd -f"
echo "   ⏹  Parar o serviço:     systemctl --user stop deckd"
echo "   ▶  Iniciar o serviço:   systemctl --user start deckd"
echo "   🔄 Reiniciar:           systemctl --user restart deckd"
