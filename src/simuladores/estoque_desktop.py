"""Aplicação desktop sem API utilizada pelo Bot B do Capstone."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
import sys
import time
from typing import Sequence

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # Permite importar o módulo em ambientes sem GUI.
    tk = None
    ttk = None

try:
    import customtkinter as ctk
except ImportError:  # O modo indisponível continua testável sem a biblioteca.
    ctk = None

from src.simuladores.dados_estoque import (
    ItemEstoqueSimulado,
    filtrar_registros,
    obter_massa_estoque,
    paginar_registros,
)


TITULO_JANELA = "Hyperautomation - Estoque Interno"
MODOS_VALIDOS = ("normal", "lento", "indisponivel")

COR_FUNDO = "#0B1120"
COR_CARTAO = "#111827"
COR_CARTAO_SECUNDARIO = "#172033"
COR_TEXTO = "#F8FAFC"
COR_TEXTO_SECUNDARIO = "#94A3B8"
COR_AZUL = "#2563EB"
COR_AZUL_HOVER = "#1D4ED8"
COR_VERDE = "#16A34A"
COR_AMARELO = "#D97706"
COR_VERMELHO = "#DC2626"


def _booleano_ambiente(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


@dataclass(frozen=True)
class ConfiguracaoSimulador:
    """Parâmetros usados para executar e sabotar o simulador."""

    modo: str = "normal"
    tamanho_pagina: int = 5
    atraso_segundos: float = 5.0
    fechar_apos_segundos: float = 0.0

    def __post_init__(self) -> None:
        if self.modo not in MODOS_VALIDOS:
            raise ValueError(
                "modo deve ser normal, lento ou indisponivel"
            )
        if self.tamanho_pagina <= 0:
            raise ValueError(
                "tamanho_pagina deve ser maior que zero"
            )
        if self.atraso_segundos < 0:
            raise ValueError(
                "atraso_segundos não pode ser negativo"
            )
        if self.fechar_apos_segundos < 0:
            raise ValueError(
                "fechar_apos_segundos não pode ser negativo"
            )


class AplicacaoEstoque:
    """Janela moderna, pesquisável e paginada do estoque interno."""

    def __init__(
        self,
        raiz,
        registros: Sequence[ItemEstoqueSimulado],
        *,
        tamanho_pagina: int = 5,
    ) -> None:
        self._raiz = raiz
        self._registros = tuple(registros)
        self._registros_filtrados = self._registros
        self._tamanho_pagina = tamanho_pagina
        self._pagina_atual = 1

        self._termo_busca = tk.StringVar(master=raiz)
        self._status = tk.StringVar(master=raiz)
        self._total = tk.StringVar(master=raiz)
        self._disponiveis = tk.StringVar(master=raiz)
        self._estoque_baixo = tk.StringVar(master=raiz)
        self._criticos = tk.StringVar(master=raiz)

        self._configurar_janela()
        self._construir_interface()
        self._atualizar_tabela()

    def _configurar_janela(self) -> None:
        self._raiz.title(TITULO_JANELA)
        self._raiz.geometry("1120x680")
        self._raiz.minsize(980, 620)
        self._raiz.configure(fg_color=COR_FUNDO)
        self._raiz.grid_columnconfigure(0, weight=1)
        self._raiz.grid_rowconfigure(3, weight=1)

    def _construir_interface(self) -> None:
        self._construir_cabecalho()
        self._construir_cartoes()
        self._construir_busca()
        self._construir_tabela()
        self._construir_rodape()

        self._raiz.bind(
            "<Return>",
            lambda _evento: self.aplicar_filtro(),
        )
        self._raiz.bind(
            "<Control-f>",
            self._focar_busca,
        )

        self._raiz.bind(
            "<Control-e>",
            self._copiar_pagina_visivel,
        )

        self._campo_busca.focus_set()

    def _construir_cabecalho(self) -> None:
        cabecalho = ctk.CTkFrame(
            self._raiz,
            fg_color="transparent",
            corner_radius=0,
        )
        cabecalho.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=28,
            pady=(24, 14),
        )
        cabecalho.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cabecalho,
            text="Estoque interno",
            text_color=COR_TEXTO,
            font=ctk.CTkFont(size=26, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            cabecalho,
            text=(
                "Consulta operacional de lotes para o pipeline "
                "Hyperautomation"
            ),
            text_color=COR_TEXTO_SECUNDARIO,
            font=ctk.CTkFont(size=13),
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(4, 0),
        )

        ctk.CTkLabel(
            cabecalho,
            text="SISTEMA ONLINE",
            text_color="#DCFCE7",
            fg_color="#14532D",
            corner_radius=12,
            padx=14,
            pady=6,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(
            row=0,
            column=1,
            rowspan=2,
            sticky="e",
        )

    def _criar_cartao(
        self,
        mestre,
        *,
        coluna: int,
        titulo: str,
        variavel,
        cor_destaque: str,
    ) -> None:
        cartao = ctk.CTkFrame(
            mestre,
            fg_color=COR_CARTAO,
            corner_radius=14,
            border_width=1,
            border_color=COR_CARTAO_SECUNDARIO,
        )
        cartao.grid(
            row=0,
            column=coluna,
            sticky="ew",
            padx=(
                0 if coluna == 0 else 6,
                0 if coluna == 3 else 6,
            ),
        )
        cartao.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cartao,
            text=titulo,
            text_color=COR_TEXTO_SECUNDARIO,
            font=ctk.CTkFont(size=12),
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=16,
            pady=(12, 0),
        )

        ctk.CTkLabel(
            cartao,
            textvariable=variavel,
            text_color=cor_destaque,
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=16,
            pady=(2, 12),
        )

    def _construir_cartoes(self) -> None:
        cartoes = ctk.CTkFrame(
            self._raiz,
            fg_color="transparent",
        )
        cartoes.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=28,
            pady=(0, 14),
        )

        for coluna in range(4):
            cartoes.grid_columnconfigure(coluna, weight=1)

        self._criar_cartao(
            cartoes,
            coluna=0,
            titulo="Total de lotes",
            variavel=self._total,
            cor_destaque=COR_AZUL,
        )
        self._criar_cartao(
            cartoes,
            coluna=1,
            titulo="Disponíveis",
            variavel=self._disponiveis,
            cor_destaque=COR_VERDE,
        )
        self._criar_cartao(
            cartoes,
            coluna=2,
            titulo="Estoque baixo",
            variavel=self._estoque_baixo,
            cor_destaque=COR_AMARELO,
        )
        self._criar_cartao(
            cartoes,
            coluna=3,
            titulo="Críticos",
            variavel=self._criticos,
            cor_destaque=COR_VERMELHO,
        )

    def _construir_busca(self) -> None:
        busca = ctk.CTkFrame(
            self._raiz,
            fg_color=COR_CARTAO,
            corner_radius=14,
        )
        busca.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=28,
            pady=(0, 14),
        )
        busca.grid_columnconfigure(0, weight=1)

        self._campo_busca = ctk.CTkEntry(
            busca,
            textvariable=self._termo_busca,
            placeholder_text=(
                "Buscar por lote, produto, localização ou status"
            ),
            height=42,
            corner_radius=10,
            border_color="#334155",
            fg_color="#0F172A",
            text_color=COR_TEXTO,
        )
        self._campo_busca.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(14, 8),
            pady=14,
        )

        ctk.CTkButton(
            busca,
            text="Buscar",
            command=self.aplicar_filtro,
            width=110,
            height=42,
            corner_radius=10,
            fg_color=COR_AZUL,
            hover_color=COR_AZUL_HOVER,
            font=ctk.CTkFont(weight="bold"),
        ).grid(
            row=0,
            column=1,
            padx=(0, 8),
            pady=14,
        )

        ctk.CTkButton(
            busca,
            text="Limpar",
            command=self.limpar_filtro,
            width=100,
            height=42,
            corner_radius=10,
            fg_color="#334155",
            hover_color="#475569",
        ).grid(
            row=0,
            column=2,
            padx=(0, 14),
            pady=14,
        )

    def _configurar_estilo_tabela(self) -> None:
        estilo = ttk.Style(self._raiz)
        estilo.theme_use("clam")
        estilo.configure(
            "Estoque.Treeview",
            background="#0F172A",
            foreground=COR_TEXTO,
            fieldbackground="#0F172A",
            borderwidth=0,
            rowheight=38,
            font=("TkDefaultFont", 11),
        )
        estilo.configure(
            "Estoque.Treeview.Heading",
            background="#1E293B",
            foreground="#CBD5E1",
            borderwidth=0,
            relief="flat",
            font=("TkDefaultFont", 10, "bold"),
        )
        estilo.map(
            "Estoque.Treeview",
            background=[("selected", COR_AZUL)],
            foreground=[("selected", "#FFFFFF")],
        )
        estilo.map(
            "Estoque.Treeview.Heading",
            background=[("active", "#334155")],
        )

    def _construir_tabela(self) -> None:
        self._configurar_estilo_tabela()

        corpo = ctk.CTkFrame(
            self._raiz,
            fg_color=COR_CARTAO,
            corner_radius=14,
        )
        corpo.grid(
            row=3,
            column=0,
            sticky="nsew",
            padx=28,
            pady=(0, 10),
        )
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            corpo,
            text="Lotes cadastrados",
            text_color=COR_TEXTO,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=16,
            pady=(14, 10),
        )

        colunas = (
            "lote_id",
            "produto",
            "quantidade",
            "localizacao",
            "status",
        )
        self._tabela = ttk.Treeview(
            corpo,
            columns=colunas,
            show="headings",
            height=self._tamanho_pagina,
            style="Estoque.Treeview",
            selectmode="browse",
        )

        definicoes = {
            "lote_id": ("LOTE", 120, "center"),
            "produto": ("PRODUTO", 330, "w"),
            "quantidade": ("QUANTIDADE", 110, "center"),
            "localizacao": ("LOCALIZAÇÃO", 120, "center"),
            "status": ("STATUS", 170, "center"),
        }
        for coluna, (titulo, largura, alinhamento) in definicoes.items():
            self._tabela.heading(coluna, text=titulo)
            self._tabela.column(
                coluna,
                width=largura,
                minwidth=80,
                anchor=alinhamento,
            )

        barra_vertical = ctk.CTkScrollbar(
            corpo,
            command=self._tabela.yview,
            fg_color=COR_CARTAO,
            button_color="#334155",
            button_hover_color="#475569",
        )
        self._tabela.configure(
            yscrollcommand=barra_vertical.set
        )
        self._tabela.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(16, 4),
            pady=(0, 16),
        )
        barra_vertical.grid(
            row=1,
            column=1,
            sticky="ns",
            padx=(0, 12),
            pady=(0, 16),
        )

        self._tabela.tag_configure(
            "baixo",
            background="#422006",
            foreground="#FEF3C7",
        )
        self._tabela.tag_configure(
            "critico",
            background="#450A0A",
            foreground="#FECACA",
        )

    def _construir_rodape(self) -> None:
        rodape = ctk.CTkFrame(
            self._raiz,
            fg_color="transparent",
        )
        rodape.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=28,
            pady=(0, 22),
        )
        rodape.grid_columnconfigure(1, weight=1)

        self._botao_anterior = ctk.CTkButton(
            rodape,
            text="Anterior",
            command=self.pagina_anterior,
            width=110,
            height=38,
            corner_radius=10,
            fg_color="#334155",
            hover_color="#475569",
        )
        self._botao_anterior.grid(row=0, column=0)

        ctk.CTkLabel(
            rodape,
            textvariable=self._status,
            text_color=COR_TEXTO_SECUNDARIO,
            font=ctk.CTkFont(size=12),
        ).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=12,
        )

        self._botao_proximo = ctk.CTkButton(
            rodape,
            text="Próxima",
            command=self.proxima_pagina,
            width=110,
            height=38,
            corner_radius=10,
            fg_color=COR_AZUL,
            hover_color=COR_AZUL_HOVER,
        )
        self._botao_proximo.grid(row=0, column=2)
        ctk.CTkLabel(
            rodape,
            text="Ctrl+E: copiar página visível",
            text_color=COR_TEXTO_SECUNDARIO,
            font=ctk.CTkFont(size=11),
        ).grid(
            row=1,
            column=0,
            columnspan=3,
            pady=(8, 0),
        )

    def _focar_busca(self, _evento=None) -> str:
        self._campo_busca.focus_set()
        self._campo_busca.select_range(0, "end")
        return "break"

    def aplicar_filtro(self) -> None:
        self._registros_filtrados = filtrar_registros(
            self._registros,
            self._termo_busca.get(),
        )
        self._pagina_atual = 1
        self._atualizar_tabela()

    def limpar_filtro(self) -> None:
        self._termo_busca.set("")
        self._registros_filtrados = self._registros
        self._pagina_atual = 1
        self._atualizar_tabela()
        self._campo_busca.focus_set()

    def _copiar_pagina_visivel(
            self,
            _evento=None,
    ) -> str:
        """
        Copia para o clipboard somente os registros
        apresentados na página atual.
        """

        pagina = paginar_registros(
            self._registros_filtrados,
            pagina=self._pagina_atual,
            tamanho_pagina=self._tamanho_pagina,
        )

        cabecalho = (
            "lote_id",
            "produto",
            "quantidade_disponivel",
            "localizacao",
            "status_estoque",
        )

        linhas = [
            "\t".join(cabecalho)
        ]

        for registro in pagina.registros:
            linha = (
                registro.lote_id,
                registro.produto,
                str(
                    registro.quantidade_disponivel
                ),
                registro.localizacao,
                registro.status_estoque,
            )

            linhas.append(
                "\t".join(linha)
            )

        conteudo = "\n".join(linhas)

        self._raiz.clipboard_clear()
        self._raiz.clipboard_append(conteudo)

        # Garante que o conteúdo permaneça no clipboard
        # depois que o evento terminar.
        self._raiz.update()

        self._status.set(
            f"Página {pagina.pagina_atual} copiada | "
            f"{len(pagina.registros)} registro(s)"
        )

        return "break"

    def pagina_anterior(self) -> None:
        if self._pagina_atual > 1:
            self._pagina_atual -= 1
            self._atualizar_tabela()

    def proxima_pagina(self) -> None:
        pagina = paginar_registros(
            self._registros_filtrados,
            pagina=self._pagina_atual,
            tamanho_pagina=self._tamanho_pagina,
        )
        if self._pagina_atual < pagina.total_paginas:
            self._pagina_atual += 1
            self._atualizar_tabela()

    def _atualizar_indicadores(self) -> None:
        registros = self._registros_filtrados
        disponiveis = sum(
            registro.status_estoque == "DISPONIVEL"
            for registro in registros
        )
        estoque_baixo = sum(
            registro.status_estoque == "ESTOQUE_BAIXO"
            for registro in registros
        )
        criticos = sum(
            registro.status_estoque
            in {"INDISPONIVEL", "BLOQUEADO"}
            for registro in registros
        )

        self._total.set(str(len(registros)))
        self._disponiveis.set(str(disponiveis))
        self._estoque_baixo.set(str(estoque_baixo))
        self._criticos.set(str(criticos))

    def _tag_status(self, status: str) -> tuple[str, ...]:
        if status == "ESTOQUE_BAIXO":
            return ("baixo",)
        if status in {"INDISPONIVEL", "BLOQUEADO"}:
            return ("critico",)
        return ()

    def _atualizar_tabela(self) -> None:
        for item in self._tabela.get_children():
            self._tabela.delete(item)

        pagina = paginar_registros(
            self._registros_filtrados,
            pagina=self._pagina_atual,
            tamanho_pagina=self._tamanho_pagina,
        )

        for registro in pagina.registros:
            self._tabela.insert(
                "",
                "end",
                values=(
                    registro.lote_id,
                    registro.produto,
                    registro.quantidade_disponivel,
                    registro.localizacao,
                    registro.status_estoque,
                ),
                tags=self._tag_status(
                    registro.status_estoque
                ),
            )

        self._atualizar_indicadores()
        self._status.set(
            f"{pagina.total_registros} registro(s) | "
            f"Página {pagina.pagina_atual} de {pagina.total_paginas}"
        )

        self._botao_anterior.configure(
            state=(
                "normal"
                if pagina.pagina_atual > 1
                else "disabled"
            )
        )
        possui_proxima_pagina = (
                pagina.pagina_atual
                < pagina.total_paginas
        )

        if possui_proxima_pagina:
            self._botao_proximo.configure(
                state="normal",
                text="Próxima",
                fg_color=COR_AZUL,
                hover_color=COR_AZUL_HOVER,
            )

            # Restaura o botão caso ele tenha sido
            # ocultado anteriormente.
            self._botao_proximo.grid()

        else:
            # Na última página o botão desaparece.
            # Assim, o BotCity não encontra a imagem
            # botao_proximo.png e encerra a coleta.
            self._botao_proximo.grid_remove()


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modo",
        choices=MODOS_VALIDOS,
        default=os.getenv("DESKTOP_SIMULADOR_MODO", "normal"),
        help="Comportamento usado na demonstração de falhas.",
    )
    parser.add_argument(
        "--tamanho-pagina",
        type=int,
        default=int(
            os.getenv("DESKTOP_SIMULADOR_TAMANHO_PAGINA", "5")
        ),
    )
    parser.add_argument(
        "--atraso-segundos",
        type=float,
        default=float(
            os.getenv("DESKTOP_SIMULADOR_ATRASO_SECONDS", "5")
        ),
    )
    parser.add_argument(
        "--fechar-apos-segundos",
        type=float,
        default=float(
            os.getenv("DESKTOP_SIMULADOR_FECHAR_APOS_SECONDS", "0")
        ),
        help="Fecha a janela automaticamente; zero mantém aberta.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    configuracao = ConfiguracaoSimulador(
        modo=(
            "indisponivel"
            if _booleano_ambiente("DESKTOP_SIMULADOR_INDISPONIVEL")
            else args.modo
        ),
        tamanho_pagina=args.tamanho_pagina,
        atraso_segundos=args.atraso_segundos,
        fechar_apos_segundos=args.fechar_apos_segundos,
    )

    if configuracao.modo == "indisponivel":
        print(
            "Sistema desktop indisponível por configuração de teste.",
            file=sys.stderr,
        )
        return 2

    if configuracao.modo == "lento":
        time.sleep(configuracao.atraso_segundos)

    if tk is None or ttk is None:
        print(
            "Tkinter não está instalado. No Fedora, execute: "
            "sudo dnf install python3-tkinter",
            file=sys.stderr,
        )
        return 3

    if ctk is None:
        print(
            "CustomTkinter não está instalado. Execute: "
            "python -m pip install customtkinter",
            file=sys.stderr,
        )
        return 3

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    try:
        raiz = ctk.CTk()
    except tk.TclError as erro:
        print(
            f"Não foi possível abrir a interface desktop: {erro}",
            file=sys.stderr,
        )
        return 4

    AplicacaoEstoque(
        raiz,
        obter_massa_estoque(),
        tamanho_pagina=configuracao.tamanho_pagina,
    )

    if configuracao.fechar_apos_segundos > 0:
        raiz.after(
            int(configuracao.fechar_apos_segundos * 1_000),
            raiz.destroy,
        )

    raiz.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

