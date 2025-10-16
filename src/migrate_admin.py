#!/usr/bin/env python3
"""Script para criar o primeiro usuário admin no sistema

Este script deve ser executado uma vez para criar o primeiro admin.
Depois disso, novos usuários podem ser adicionados via comandos do bot.
"""

import os
import sys
from typing import Optional

# Adicionar o diretório src ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
import asyncio
from services.async_user_service import AsyncUserService
from services.exceptions import ValidationError, DatabaseError


def get_admin_user_id() -> str:
    """Obtém o ID do primeiro admin a partir das variáveis de ambiente ou input do usuário"""
    
    # Tentar pegar da env var primeiro
    admin_id = os.getenv("FIRST_ADMIN_USER_ID")
    if admin_id:
        print(f"🔧 Usando FIRST_ADMIN_USER_ID da variável de ambiente: {admin_id}")
        return admin_id.strip()
    
    # Se não tem na env var, tentar pegar da lista de usuários autorizados (primeiro da lista)
    if settings.AUTHORIZED_USER_IDS:
        admin_id = str(settings.AUTHORIZED_USER_IDS[0])
        print(f"🔧 Usando primeiro usuário da AUTHORIZED_USER_IDS: {admin_id}")
        return admin_id
    
    # Se não tem nada configurado, pedir para o usuário digitar
    print("❌ Nenhum usuário admin configurado.")
    print("\nPara encontrar seu ID do Telegram:")
    print("1. Envie /myid para @userinfobot no Telegram")
    print("2. Ou use /start no seu bot e veja o erro (mostrará seu ID)")
    print()
    
    while True:
        admin_id = input("Digite o ID do usuário que será o primeiro admin: ").strip()
        if admin_id and admin_id.isdigit():
            return admin_id
        print("❌ ID inválido. Digite apenas números.")


async def create_first_admin():
    """Cria o primeiro usuário administrador"""
    
    print("=" * 60)
    print("🔧 CRIAÇÃO DO PRIMEIRO ADMIN - GYM TRACKER BOT")
    print("=" * 60)
    
    try:
        user_service = AsyncUserService()
        
        # Obter ID do admin
        admin_id = get_admin_user_id()
        
        # Verificar se usuário já existe
        existing_user = await user_service.get_user(admin_id)
        if existing_user:
            if existing_user.is_admin:
                print(f"✅ Usuário {admin_id} já é administrador!")
                print(f"   Nome: {existing_user.first_name or 'N/A'}")
                print(f"   Username: @{existing_user.username or 'não definido'}")
                print(f"   Criado em: {existing_user.created_at.strftime('%d/%m/%Y %H:%M')}")
                return
            else:
                # Promover usuário existente a admin
                await user_service.make_admin(admin_id)
                print(f"✅ Usuário {admin_id} promovido a administrador!")
                print(f"   Nome: {existing_user.first_name or 'N/A'}")
                return
        
        # Criar novo usuário admin
        print(f"🔧 Criando novo usuário administrador: {admin_id}")
        
        user = await user_service.add_user(
            user_id=admin_id,
            is_admin=True,
            created_by="system"  # Criado pelo sistema de migração
        )
        
        print(f"✅ Primeiro administrador criado com sucesso!")
        print(f"   ID: {user.user_id}")
        print(f"   Admin: {user.is_admin}")
        print(f"   Ativo: {user.is_active}")
        print()
        print("🎉 Agora você pode usar o bot!")
        print("💡 Use os comandos /adduser e /removeuser para gerenciar outros usuários.")
        
    except (ValidationError, DatabaseError) as e:
        print(f"❌ Erro ao criar administrador: {e.message}")
        if e.details:
            print(f"   Detalhes: {e.details}")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        sys.exit(1)


def main():
    """Função principal"""
    try:
        asyncio.run(create_first_admin())
    except KeyboardInterrupt:
        print("\n\n👋 Operação cancelada pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()