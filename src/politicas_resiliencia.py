"""Contratos comuns de resiliência usados pelas integrações dos bots."""

from __future__ import annotations

from dataclasses import dataclass
import re
from time import sleep
from typing import Any, Callable, Mapping, TypeVar


T = TypeVar("T")
VALOR_PROTEGIDO = "[REDACTED]"

_CHAVES_SENSIVEIS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "password",
        "passwd",
        "senha",
        "secret",
        "client_secret",
    }
)
_SEGREDO_EM_TEXTO = re.compile(
    r"(?i)\b(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"token|password|passwd|senha|secret|client[_-]?secret)\b"
    r"(\s*[:=]\s*|\s+)(bearer\s+)?([^\s,;]+)"
)


class ErroDeItem(Exception):
    """Falha determinística restrita ao item atualmente processado."""


class ErroDeInfraestrutura(Exception):
    """Falha temporária de uma dependência ou recurso externo."""


@dataclass(frozen=True)
class PoliticaResiliencia:
    """Limites explícitos de uma integração; evita retries infinitos."""

    max_tentativas: int
    backoff_seconds: float
    timeout_seconds: float

    def __post_init__(self) -> None:
        if self.max_tentativas < 1:
            raise ValueError("max_tentativas deve ser maior ou igual a 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds não pode ser negativo")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser maior que zero")

    def atraso(self, tentativa: int) -> float:
        """Backoff exponencial antes da tentativa seguinte."""

        if tentativa < 1:
            raise ValueError("tentativa deve ser maior ou igual a 1")
        return self.backoff_seconds * (2 ** (tentativa - 1))


# Uma fonte única documenta os limites de cada integração do capstone.
POLITICAS_POR_INTEGRACAO: Mapping[str, PoliticaResiliencia] = {
    "item": PoliticaResiliencia(3, 0.1, 10.0),
    "base_referencia": PoliticaResiliencia(3, 1.0, 10.0),
    "ml": PoliticaResiliencia(1, 0.0, 3.0),
    "desktop": PoliticaResiliencia(3, 1.0, 10.0),
    "portal_web": PoliticaResiliencia(3, 1.0, 10.0),
    "telegram": PoliticaResiliencia(1, 0.0, 5.0),
    "email": PoliticaResiliencia(1, 0.0, 10.0),
}

# Nomes descritivos mantidos para consumidores que tratam a política como
# configuração de integração ou de retry.
PoliticaIntegracao = PoliticaResiliencia
PoliticaRetry = PoliticaResiliencia
POLITICAS_INTEGRACAO = POLITICAS_POR_INTEGRACAO


def obter_politica(integracao: str) -> PoliticaResiliencia:
    """Obtém uma política conhecida sem criar defaults silenciosos."""

    try:
        return POLITICAS_POR_INTEGRACAO[integracao]
    except KeyError as erro:
        raise ValueError(f"integração sem política: {integracao}") from erro


def sanitizar_dados(valor: Any) -> Any:
    """Copia uma estrutura removendo segredos por chave e por texto."""

    if isinstance(valor, Mapping):
        return {
            str(chave): (
                VALOR_PROTEGIDO
                if str(chave).strip().lower() in _CHAVES_SENSIVEIS
                else sanitizar_dados(conteudo)
            )
            for chave, conteudo in valor.items()
        }
    if isinstance(valor, (list, tuple, set, frozenset)):
        itens = [sanitizar_dados(item) for item in valor]
        return tuple(itens) if isinstance(valor, tuple) else itens
    if isinstance(valor, str):
        return _SEGREDO_EM_TEXTO.sub(
            lambda encontrado: (
                f"{encontrado.group(1)}{encontrado.group(2)}{VALOR_PROTEGIDO}"
            ),
            valor,
        )
    return valor


sanitizar_payload = sanitizar_dados


def calcular_backoff(politica: PoliticaResiliencia, tentativa: int) -> float:
    """Expõe o cálculo para logs, métricas e testes sem executar espera."""

    return politica.atraso(tentativa)


def mensagem_erro_segura(erro: BaseException) -> str:
    """Retorna somente tipo e mensagem sanitizada de uma exceção."""

    mensagem = str(sanitizar_dados(str(erro)))
    return f"{type(erro).__name__}: {mensagem}" if mensagem else type(erro).__name__


def executar_com_retry(
    operacao: Callable[[], T],
    *,
    politica: PoliticaResiliencia,
    sleeper: Callable[[float], None] = sleep,
) -> tuple[T, int]:
    """Executa uma operação com limite e backoff, preservando seu erro final."""

    for tentativa in range(1, politica.max_tentativas + 1):
        try:
            return operacao(), tentativa
        except (ErroDeItem, ErroDeInfraestrutura):
            if tentativa == politica.max_tentativas:
                raise
            sleeper(politica.atraso(tentativa))
    raise AssertionError("política validada sempre executa ao menos uma tentativa")
