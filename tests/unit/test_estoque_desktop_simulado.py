from src.simuladores.estoque_desktop import (
    AplicacaoEstoque,
    ConfiguracaoSimulador,
    main,
    obter_massa_estoque,
)

class RaizClipboardControlada:
    def __init__(self):
        self.conteudo = None
        self.atualizacoes = 0

    def clipboard_clear(self):
        self.conteudo = ""

    def clipboard_append(self, conteudo):
        self.conteudo = conteudo

    def update(self):
        self.atualizacoes += 1


class VariavelTextoControlada:
    def __init__(self):
        self.valor = ""

    def set(self, valor):
        self.valor = valor

def test_copia_somente_a_pagina_visivel():
    aplicacao = object.__new__(
        AplicacaoEstoque
    )

    aplicacao._registros_filtrados = (
        obter_massa_estoque()
    )
    aplicacao._pagina_atual = 1
    aplicacao._tamanho_pagina = 5
    aplicacao._raiz = (
        RaizClipboardControlada()
    )
    aplicacao._status = (
        VariavelTextoControlada()
    )

    retorno = (
        aplicacao._copiar_pagina_visivel()
    )

    conteudo = aplicacao._raiz.conteudo

    assert retorno == "break"
    assert conteudo is not None

    assert conteudo.startswith(
        "lote_id\tproduto\t"
        "quantidade_disponivel\t"
        "localizacao\tstatus_estoque"
    )

    assert "LOTE-001" in conteudo
    assert "LOTE-005" in conteudo

    # O sexto lote pertence à segunda página.
    assert "LOTE-006" not in conteudo

    assert (
        aplicacao._status.valor
        == "Página 1 copiada | "
        "5 registro(s)"
    )

    assert (
        aplicacao._raiz.atualizacoes
        == 1
    )