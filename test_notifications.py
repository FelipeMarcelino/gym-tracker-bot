#!/usr/bin/env python3
"""
Script para testar notificações do Telegram

Uso:
    python test_notifications.py <CHAT_ID> <BOT_TOKEN>

Exemplo:
    python test_notifications.py -1001234567890 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
"""

import sys
import requests


def send_test_notification(chat_id, bot_token):
    """Envia notificação de teste"""

    message = """🧪 Teste de Notificação - Gym Tracker Bot

✅ Configuração OK!

Se você está vendo esta mensagem, significa que:
- Bot Token está correto
- Chat ID está correto
- Bot tem permissão para postar no canal

🎉 Notificações do CI/CD funcionarão corretamente!
"""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        print(f"📤 Enviando mensagem de teste...")
        print(f"   Chat ID: {chat_id}")
        print(f"   Bot Token: {bot_token[:10]}...")
        print()

        response = requests.post(url, json=payload)

        if response.status_code == 200:
            print("✅ Notificação enviada com sucesso!")
            print()
            print("Verifique o canal/grupo no Telegram!")
            return True
        else:
            print(f"❌ Erro ao enviar notificação!")
            print(f"   Status: {response.status_code}")
            print(f"   Resposta: {response.text}")
            print()
            print("Possíveis problemas:")
            print("- Chat ID incorreto")
            print("- Bot não está no canal/grupo")
            print("- Bot não tem permissão para postar")
            return False

    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


def main():
    if len(sys.argv) != 3:
        print("❌ Uso incorreto!")
        print()
        print("Uso:")
        print("    python test_notifications.py <CHAT_ID> <BOT_TOKEN>")
        print()
        print("Exemplo:")
        print("    python test_notifications.py -1001234567890 123456:ABC-DEF")
        print()
        sys.exit(1)

    chat_id = sys.argv[1]
    bot_token = sys.argv[2]

    print("🤖 Testando Notificações do Telegram")
    print("=" * 60)
    print()

    send_test_notification(chat_id, bot_token)


if __name__ == "__main__":
    main()
