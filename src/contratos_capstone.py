"""Contratos de dados independentes do orquestrador do Capstone."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


VERSAO_SCHEMA = "1.0"

TextoObrigatorio = Annotated[str, Field(min_length=1)]
InteiroNaoNegativo = Annotated[int, Field(ge=0)]


class ContratoInvalidoError(ValueError):
    """Indica que um JSON não atende ao contrato informado."""


class EstadoExecucao(str, Enum):
    """Estados comuns produzidos pelas etapas do pipeline."""

    CONCLUIDO = "CONCLUIDO"
    CONCLUIDO_DEGRADADO = "CONCLUIDO_DEGRADADO"
    FALHOU = "FALHOU"
    CANCELADO = "CANCELADO"
    TIMEOUT = "TIMEOUT"


class FonteDados(str, Enum):
    """Fontes que participam da consolidação."""

    DESKTOP = "desktop"
    WEB = "web"


class ContratoBase(BaseModel):
    """Configuração e serialização compartilhadas pelos contratos."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    schema_version: str = VERSAO_SCHEMA

    @field_validator("schema_version")
    @classmethod
    def validar_schema_version(cls, valor: str) -> str:
        if valor != VERSAO_SCHEMA:
            raise ValueError(
                "schema_version não suportada: "
                f"{valor!r}; esperada {VERSAO_SCHEMA!r}"
            )
        return valor

    def para_json(self) -> str:
        """Serializa o contrato como JSON UTF-8 legível."""

        return self.model_dump_json(indent=2)

    @classmethod
    def de_json(cls, conteudo: str | bytes | bytearray) -> Self:
        """Valida e desserializa JSON com erro de domínio compreensível."""

        try:
            return cls.model_validate_json(conteudo)
        except (ValidationError, ValueError, TypeError) as erro:
            raise ContratoInvalidoError(
                f"Contrato {cls.__name__} inválido: {erro}"
            ) from erro


class EnvelopeAuditoria(ContratoBase):
    """Metadados que correlacionam tarefas, logs e artefatos."""

    execution_id: TextoObrigatorio
    correlation_id: TextoObrigatorio
    bot_id: TextoObrigatorio
    task_id: TextoObrigatorio
    estado: EstadoExecucao
    predecessor: TextoObrigatorio | None = None
    predecessor_task_id: TextoObrigatorio | None = None
    resultado_predecessor: TextoObrigatorio | None = None
    registrado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("registrado_em")
    @classmethod
    def validar_registrado_em(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("registrado_em deve possuir fuso horário")
        return valor

    @model_validator(mode="after")
    def validar_predecessor(self) -> Self:
        possui_nome = self.predecessor is not None
        possui_task_id = self.predecessor_task_id is not None

        if possui_nome != possui_task_id:
            raise ValueError(
                "predecessor e predecessor_task_id devem ser "
                "informados em conjunto"
            )

        if not possui_nome and self.resultado_predecessor is not None:
            raise ValueError(
                "resultado_predecessor exige um predecessor"
            )

        return self


class RegistroEstoqueDesktop(ContratoBase):
    """Registro coletado visualmente do sistema interno de estoque."""

    lote_id: TextoObrigatorio
    produto: TextoObrigatorio
    quantidade_disponivel: InteiroNaoNegativo
    localizacao: TextoObrigatorio
    status_estoque: TextoObrigatorio
    coletado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("coletado_em")
    @classmethod
    def validar_coletado_em(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("coletado_em deve possuir fuso horário")
        return valor


class PedidoFornecedor(ContratoBase):
    """Pedido coletado do portal web de fornecedores."""

    pedido_id: TextoObrigatorio
    lote_id: TextoObrigatorio
    fornecedor: TextoObrigatorio
    produto: TextoObrigatorio
    quantidade_pedida: InteiroNaoNegativo
    status_pedido: TextoObrigatorio
    previsao_entrega: date | None = None
    coletado_em: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("coletado_em")
    @classmethod
    def validar_coletado_em(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("coletado_em deve possuir fuso horário")
        return valor


class RegistroConsolidado(ContratoBase):
    """Resultado determinístico da junção entre desktop e web."""

    lote_id: TextoObrigatorio
    produto: TextoObrigatorio
    quantidade_estoque: InteiroNaoNegativo | None = None
    quantidade_pedida: InteiroNaoNegativo | None = None
    status_estoque: TextoObrigatorio | None = None
    status_pedido: TextoObrigatorio | None = None
    classificacao_deterministica: TextoObrigatorio
    motivo: TextoObrigatorio
    regras_aplicadas: tuple[TextoObrigatorio, ...] = ()
    fontes_disponiveis: tuple[FonteDados, ...]
    modo_degradado: bool = False

    @model_validator(mode="after")
    def validar_fontes(self) -> Self:
        fontes = set(self.fontes_disponiveis)

        if not fontes:
            raise ValueError(
                "fontes_disponiveis deve possuir ao menos uma fonte"
            )

        todas_as_fontes = {FonteDados.DESKTOP, FonteDados.WEB}

        if not self.modo_degradado and fontes != todas_as_fontes:
            raise ValueError(
                "execução não degradada exige as fontes desktop e web"
            )

        if self.modo_degradado and fontes == todas_as_fontes:
            raise ValueError(
                "modo_degradado só deve ser usado quando uma fonte "
                "não estiver disponível"
            )

        if FonteDados.DESKTOP not in fontes and any(
            valor is not None
            for valor in (
                self.quantidade_estoque,
                self.status_estoque,
            )
        ):
            raise ValueError(
                "dados de estoque exigem a fonte desktop"
            )

        if FonteDados.WEB not in fontes and any(
            valor is not None
            for valor in (
                self.quantidade_pedida,
                self.status_pedido,
            )
        ):
            raise ValueError(
                "dados de pedido exigem a fonte web"
            )

        return self


class ArtefatoEstoqueDesktop(ContratoBase):
    """Artefato produzido pelo Bot B."""

    auditoria: EnvelopeAuditoria
    registros: tuple[RegistroEstoqueDesktop, ...] = ()

    @property
    def total_registros(self) -> int:
        return len(self.registros)


class ArtefatoPedidosFornecedor(ContratoBase):
    """Artefato produzido pelo Bot C."""

    auditoria: EnvelopeAuditoria
    registros: tuple[PedidoFornecedor, ...] = ()

    @property
    def total_registros(self) -> int:
        return len(self.registros)


class ArtefatoConsolidacao(ContratoBase):
    """Artefato produzido pelo Bot D e entregue ao Bot E."""

    auditoria: EnvelopeAuditoria
    registros: tuple[RegistroConsolidado, ...] = ()

    @property
    def total_registros(self) -> int:
        return len(self.registros)

