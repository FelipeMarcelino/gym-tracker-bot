"""Serviço para gerenciar usuários e autorização"""
import logging
from typing import List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database.connection import db
from database.models import User
from services.exceptions import DatabaseError, ValidationError

logger = logging.getLogger(__name__)


class UserService:
    """Serviço para gerenciar usuários do sistema"""

    def __init__(self) -> None:
        self.db = db

    def is_user_authorized(self, user_id: str) -> bool:
        """Verifica se um usuário está autorizado a usar o bot
        
        Args:
            user_id: ID do usuário do Telegram
            
        Returns:
            True se autorizado, False caso contrário
        """
        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(
                user_id=user_id,
                is_active=True
            ).first()
            return user is not None
        except SQLAlchemyError as e:
            logger.exception("Erro ao verificar autorização do usuário")
            # Em caso de erro no banco, negar acesso por segurança
            return False
        finally:
            session.close()

    def is_user_admin(self, user_id: str) -> bool:
        """Verifica se um usuário é administrador
        
        Args:
            user_id: ID do usuário do Telegram
            
        Returns:
            True se é admin, False caso contrário
        """
        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(
                user_id=user_id,
                is_active=True,
                is_admin=True
            ).first()
            return user is not None
        except SQLAlchemyError as e:
            logger.exception("Erro ao verificar privilégios de admin")
            return False
        finally:
            session.close()

    def get_user(self, user_id: str) -> Optional[User]:
        """Busca um usuário pelo ID
        
        Args:
            user_id: ID do usuário do Telegram
            
        Returns:
            User ou None se não encontrado
        """
        session = self.db.get_session()
        try:
            return session.query(User).filter_by(user_id=user_id).first()
        except SQLAlchemyError as e:
            logger.exception("Erro ao buscar usuário")
            raise DatabaseError(
                "Erro ao buscar usuário",
                f"Erro SQLAlchemy: {e!s}"
            )
        finally:
            session.close()

    def add_user(
        self,
        user_id: str,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_admin: bool = False,
        created_by: Optional[str] = None
    ) -> User:
        """Adiciona um novo usuário ao sistema
        
        Args:
            user_id: ID do usuário do Telegram
            username: Username do Telegram (opcional)
            first_name: Primeiro nome
            last_name: Último nome (opcional)
            is_admin: Se é administrador
            created_by: ID do usuário que criou este usuário
            
        Returns:
            User criado
            
        Raises:
            ValidationError: Se dados inválidos
            DatabaseError: Se erro no banco
        """
        if not user_id or not user_id.strip():
            raise ValidationError("ID do usuário é obrigatório")

        session = self.db.get_session()
        try:
            # Verificar se usuário já existe
            existing_user = session.query(User).filter_by(user_id=user_id).first()
            if existing_user:
                raise ValidationError(f"Usuário {user_id} já existe")

            # Criar novo usuário
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                is_admin=is_admin,
                created_by=created_by
            )

            session.add(user)
            session.commit()
            session.refresh(user)

            logger.info(f"Usuário adicionado: {user_id} (admin: {is_admin})")
            return user

        except (ValidationError, DatabaseError):
            session.rollback()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.exception("Erro ao adicionar usuário")
            raise DatabaseError(
                "Erro ao adicionar usuário",
                f"Erro SQLAlchemy: {e!s}"
            )
        finally:
            session.close()

    def remove_user(self, user_id: str) -> bool:
        """Remove um usuário do sistema (marca como inativo)
        
        Args:
            user_id: ID do usuário do Telegram
            
        Returns:
            True se removido com sucesso
            
        Raises:
            ValidationError: Se usuário não encontrado
            DatabaseError: Se erro no banco
        """
        if not user_id or not user_id.strip():
            raise ValidationError("ID do usuário é obrigatório")

        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if not user:
                raise ValidationError(f"Usuário {user_id} não encontrado")

            user.is_active = False
            session.commit()

            logger.info(f"Usuário removido: {user_id}")
            return True

        except (ValidationError, DatabaseError):
            session.rollback()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.exception("Erro ao remover usuário")
            raise DatabaseError(
                "Erro ao remover usuário",
                f"Erro SQLAlchemy: {e!s}"
            )
        finally:
            session.close()

    def list_users(self, include_inactive: bool = False) -> List[User]:
        """Lista todos os usuários do sistema
        
        Args:
            include_inactive: Se incluir usuários inativos
            
        Returns:
            Lista de usuários
        """
        session = self.db.get_session()
        try:
            query = session.query(User)
            if not include_inactive:
                query = query.filter_by(is_active=True)
            
            return query.order_by(User.created_at).all()

        except SQLAlchemyError as e:
            logger.exception("Erro ao listar usuários")
            raise DatabaseError(
                "Erro ao listar usuários",
                f"Erro SQLAlchemy: {e!s}"
            )
        finally:
            session.close()

    def update_user_info(
        self,
        user_id: str,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> bool:
        """Atualiza informações do usuário (dados do Telegram)
        
        Args:
            user_id: ID do usuário
            username: Novo username
            first_name: Novo primeiro nome
            last_name: Novo último nome
            
        Returns:
            True se atualizado com sucesso
        """
        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if not user:
                return False

            if username is not None:
                user.username = username
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name

            session.commit()
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.exception("Erro ao atualizar usuário")
            return False
        finally:
            session.close()

    def make_admin(self, user_id: str) -> bool:
        """Torna um usuário administrador
        
        Args:
            user_id: ID do usuário
            
        Returns:
            True se sucesso
        """
        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(user_id=user_id, is_active=True).first()
            if not user:
                raise ValidationError(f"Usuário {user_id} não encontrado")

            user.is_admin = True
            session.commit()

            logger.info(f"Usuário {user_id} promovido a admin")
            return True

        except (ValidationError, DatabaseError):
            session.rollback()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.exception("Erro ao promover usuário")
            raise DatabaseError(
                "Erro ao promover usuário",
                f"Erro SQLAlchemy: {e!s}"
            )
        finally:
            session.close()

    def revoke_admin(self, user_id: str) -> bool:
        """Remove privilégios de admin de um usuário
        
        Args:
            user_id: ID do usuário
            
        Returns:
            True se sucesso
        """
        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(user_id=user_id, is_active=True).first()
            if not user:
                raise ValidationError(f"Usuário {user_id} não encontrado")

            user.is_admin = False
            session.commit()

            logger.info(f"Privilégios de admin removidos do usuário {user_id}")
            return True

        except (ValidationError, DatabaseError):
            session.rollback()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.exception("Erro ao revogar admin")
            raise DatabaseError(
                "Erro ao revogar admin",
                f"Erro SQLAlchemy: {e!s}"
            )
        finally:
            session.close()


# Service instantiation moved to container.py
# This module only defines the service class