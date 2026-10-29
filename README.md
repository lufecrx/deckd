# deckd

Sistema leve de notificações periódicas baseadas em cartões configurados pelo usuário.

## Como funciona

O daemon lê um arquivo `config.toml`, exibe cada cartão como uma notificação do sistema e aguarda o intervalo configurado antes de exibir o próximo. As mudanças no arquivo de configuração são aplicadas automaticamente no próximo ciclo, sem necessidade de reiniciar.

## Requisitos

- Linux com `notify-send` instalado (`libnotify`)
- Python 3.11+ (usa `tomllib` da stdlib)
- systemd (para execução como serviço)

## Instalação

```bash
bash install.sh
```

O script instala o executável, cria a configuração de exemplo e registra o serviço systemd do usuário.

## Configuração

Edite `~/.config/deckd/config.toml`:

```toml
# Intervalo entre notificações (segundos)
interval = 300

# Tempo de exibição da notificação (milissegundos)
expire_time = 8000

# Ícone do sistema para todas as notificações
icon = "dialog-information"

# Ordem: "sequential" (em ordem) ou "random" (aleatória)
order = "sequential"

[[cards]]
title = "Beba água 💧"
body  = "Lembre-se de se hidratar!"

[[cards]]
title = "Pausa ativa 🧘"
body  = "Levante-se e alongue por 2 minutos."
```

## Comandos úteis

```bash
# Listar cartões configurados
deckd --list

# Enviar o primeiro cartão agora (para testar)
deckd --test

# Ver logs em tempo real
journalctl --user -u deckd -f

# Gerenciar o serviço
systemctl --user status  deckd
systemctl --user stop    deckd
systemctl --user start   deckd
systemctl --user restart deckd
```

## Campos de configuração

| Campo | Tipo | Descrição |
| - | - | - |
| `interval` | inteiro (s) | Intervalo entre notificações |
| `expire_time` | inteiro (ms) | Tempo de exibição da notificação |
| `icon` | string | Nome de ícone do sistema ou caminho absoluto |
| `order` | string | `"sequential"` ou `"random"` |

### Campos por cartão

| Campo | Tipo | Obrigatório | Descrição |
| - | - | - | - |
| `title` | string | ✅ | Título da notificação |
| `body` | string | ✅ | Corpo do texto |
