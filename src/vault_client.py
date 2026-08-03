"""Acesso às credenciais mantidas no Credentials Vault."""

from dataclasses import dataclass

from botcity.maestro import BotMaestroSDK

from .config import Configuracao


@dataclass(frozen=True)
class CredencialERP:
    usuario: str
    senha: str


def obter_credencial_erp(maestro: BotMaestroSDK, config: Configuracao) -> CredencialERP | None:
    """Obtém a credencial sem registrar seus valores em logs ou relatórios."""
    if not config.vault_enabled:
        return None
    usuario = maestro.get_credential(config.credential_label, config.credential_user_key)
    senha = maestro.get_credential(config.credential_label, config.credential_password_key)
    return CredencialERP(usuario=usuario, senha=senha)
