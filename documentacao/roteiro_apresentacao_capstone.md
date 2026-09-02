# Roteiro da apresentação final — Capstone

Tempo planejado: **9 minutos e 30 segundos**. Margem até o limite: 30 segundos.

Apresentadores:

- **Gustavo:** abertura, execução E2E, observabilidade e sabotagem sorteada.
- **Carlos:** problema, arquitetura, regras/ML, evidências e encerramento.

Ambos devem saber explicar o fluxo completo e executar qualquer sabotagem. A
divisão indica quem conduz cada parte, não conhecimento exclusivo.

## 0:00–0:40 — Problema e resultado esperado (Carlos)

“O processo reúne dados de estoque e fornecedores, aplica regras auditáveis,
usa ML somente para enriquecer a causa e entrega relatório e alertas. Uma falha
tolerável não pode apagar o resultado dos demais itens.”

Abrir: `documentacao/arquitetura_capstone.md`, seção de arquitetura.

## 0:40–1:50 — Arquitetura dos seis bots (Carlos)

```text
A Entrada ─┬─> B Desktop ─┐
           └─> C Web ─────┴─> D Regras -> E ML/fallback -> F Relatório/alertas
```

- A cria/preserva os IDs e valida a entrada.
- B e C coletam fontes independentes.
- D faz o fan-in e é a autoridade determinística.
- E sugere a causa; indisponibilidade não interrompe o lote.
- F publica relatório, logs e alerta.

Destacar que o E2E local executa seis etapas. O Maestro validado mantém três
pacotes por compatibilidade. Smart Office real continua pendente.

## 1:50–2:35 — Regras, ML e resiliência (Carlos)

- RN01–RN12 decidem a classificação oficial.
- O ML complementa com causa, confiança e versão; nunca sobrescreve as regras.
- `ErroDeItem` isola um registro; `ErroDeInfraestrutura` representa dependência.
- Retry possui limite e backoff; item definitivo vai para dead letter sanitizada.
- Telegram possui fallback por e-mail em eventos elegíveis.

Abrir, se perguntado: `src/politicas_resiliencia.py` e `src/dead_letter.py`.

## 2:35–4:35 — Demonstração E2E (Gustavo)

Executar:

```bash
python executar_pipeline_capstone.py --alertas console
```

Enquanto executa, explicar que o comando inicia desktop headless, portal web e
API ML locais, percorre seis etapas e encerra os auxiliares em `finally`.

Mostrar na saída:

- `sucesso: true`;
- 12 registros desktop, 12 web e 12 consolidados;
- `processos_encerrados: true`;
- `execution_id` e `correlation_id`.

## 4:35–5:30 — Evidências (Gustavo)

Abrir nesta ordem, sem navegar por pastas durante a fala:

1. `data/output/capstone_e2e/resumo_execucao.json` — IDs e totais;
2. `data/output/capstone_e2e/relatorio_final.xlsx` — 12 linhas finais;
3. `data/output/capstone_e2e/pipeline_capstone.jsonl` — seis `bot_id`;
4. `data/output/dead_letter.jsonl`, somente se existir na sabotagem;
5. GitHub Actions — JUnit, logs, screenshots, relatórios e estado da API.

Nunca abrir `.env`, tokens, cookies ou credenciais durante a apresentação.

## 5:30–7:10 — Sabotagem sorteada (Gustavo conduz; Carlos explica)

Copiar previamente os seis comandos abaixo para um bloco de notas. Executar
somente o cenário sorteado. Cada comando usa fake/simulador local determinístico.

```bash
# 1. Desktop indisponível
python -m pytest tests/integration/test_simulacao_crise_capstone.py::test_cenario_1_bot_desktop_indisponivel_falha_controlada -q -s

# 2. Dependência acima do timeout
python -m pytest tests/integration/test_simulacao_crise_capstone.py::test_cenario_2_dependencia_acima_timeout_encerra_espera -q -s

# 3. Serviço ML fora do ar
python -m pytest tests/integration/test_simulacao_crise_capstone.py::test_cenario_3_servico_ml_fora_ar_processa_todo_lote_com_fallback -q -s

# 4. Telegram indisponível
python -m pytest tests/integration/test_simulacao_crise_capstone.py::test_cenario_4_telegram_indisponivel_entrega_alerta_por_email -q -s

# 5. Dois orquestradores em coexistência simulada
python -m pytest tests/integration/test_simulacao_crise_capstone.py::test_cenario_5_dois_orquestradores_coexistem_em_simulacao -q -s

# 6. Item irrecuperável em dead letter
python -m pytest tests/integration/test_simulacao_crise_capstone.py::test_cenario_6_item_irrecuperavel_vai_dead_letter_e_lote_continua -q -s
```

Após o `passed`, Carlos responde em uma frase:

| Cenário | Defesa objetiva | Evidência comprovada pelo teste |
| --- | --- | --- |
| Desktop | Tentativas terminam e há artefato/screenshot de falha. | estado controlado, tentativas e screenshot |
| Timeout | A espera termina no limite; não existe loop infinito. | exceção tipada e evento `dependencia_timeout` |
| ML offline | Todos os itens continuam com fallback explícito. | três decisões `servico_indisponivel` |
| Telegram | O alerta é entregue pelo canal secundário. | tentativa Telegram e sucesso por e-mail fake |
| Coexistência | Os dois adaptadores preservam os mesmos IDs. | payloads correlacionados; Smart Office pendente |
| Dead letter | Só o item definitivo sai do fluxo. | dois itens processados e um evento auditável |

## 7:10–8:20 — CI e operação (Gustavo)

Abrir o último workflow verde. Mostrar os jobs de unitário, integração, crise,
E2E, desktop/Xvfb, portal, API ML e agregador. Explicar que os artefatos usam
`if: always()` e que qualquer camada obrigatória diferente de `success` bloqueia
o agregador.

## 8:20–9:10 — Defesa técnica e limites (Carlos)

- A rastreabilidade une tarefas, logs, relatórios e alertas pelos mesmos IDs.
- Payloads e exceções removem chaves sensíveis antes de persistir.
- O modo degradado é explícito; não é apresentado como sucesso integral.
- Smart Office não foi validado: o cenário 5 é simulação contratual e está
  marcado `PENDENTE_PLATAFORMA` e `evidencia_real=false`.

## 9:10–9:30 — Encerramento (Carlos)

“Entregamos um pipeline reproduzível, auditável e resiliente. A automação reduz
o trabalho manual sem delegar ao ML a decisão de negócio.”

## Plano de contingência

Se o ambiente externo, Docker, navegador ou rede falhar:

1. não improvisar credenciais nem alegar execução inexistente;
2. mostrar o último GitHub Actions verde e seus JUnit/artefatos;
3. abrir a gravação ou screenshots previamente gerados do mesmo commit;
4. executar a sabotagem isolada, que não depende de serviço real;
5. mostrar `resumo_execucao.json`, relatório e logs previamente copiados;
6. declarar data, commit e ambiente de geração da evidência;
7. marcar Smart Office como pendente, nunca como aprovado por fake.

Antes da banca, gerar uma pasta somente leitura com o hash do commit, vídeo
curto do E2E, saída dos seis cenários, relatório, logs e artefatos baixados do
CI. Se o E2E ao vivo falhar, essa pasta prova uma execução anterior, não uma
execução ao vivo.

## Checklist antes da banca

### Até o dia anterior

- [ ] PRs integrados e CI verde no commit que será apresentado.
- [ ] Suite completa e seis sabotagens executadas nesse commit.
- [ ] Evidências baixadas e identificadas com commit/data/ambiente.
- [ ] Nenhum `.env`, token, senha, chat ID ou e-mail pessoal nas telas.
- [ ] Fedora, Python, Chromium e dependências verificados.
- [ ] Relatório e logs abertos previamente nas abas corretas.
- [ ] Smart Office identificado como pendente em slides e fala.
- [ ] Gustavo e Carlos trocaram de papel em pelo menos um ensaio.
- [ ] Ensaio completo cronometrado abaixo de 9min30s.

### Trinta minutos antes

- [ ] Fechar serviços antigos e confirmar portas livres.
- [ ] Ativar o ambiente virtual e conferir a branch/commit.
- [ ] Executar o E2E uma vez e preservar sua saída.
- [ ] Conferir zoom, terminal, fonte, projetor e acesso offline às evidências.
- [ ] Colar os seis comandos de sabotagem em um bloco de notas.
- [ ] Silenciar notificações e ocultar favoritos/histórico sensíveis.

### Após a demonstração

- [ ] Encerrar processos auxiliares e executar `docker compose down`, se usado.
- [ ] Não apagar evidências antes da avaliação.
