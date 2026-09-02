# Plano de migração do BotCity Orchestrator para Smart Office

## 1. Objetivo e estado deste documento

Este plano define uma migração reversível, sem processamento duplicado e sem
perda silenciosa de tarefas. Ele **não registra uma migração executada**.

Legenda obrigatória:

- **EVIDÊNCIA REAL:** comportamento observado em ambiente acessível e associado
  a data, execução e artefato.
- **CONFIGURAÇÃO PLANEJADA:** decisão aprovada, ainda não aplicada ou validada.
- **HIPÓTESE:** premissa que depende de documentação ou acesso à plataforma.

Estado em 2 de setembro de 2026:

| Item | Classificação | Situação |
| --- | --- | --- |
| Pipeline local com seis etapas | EVIDÊNCIA REAL | Coberto por E2E e simuladores locais. |
| Cadeia A → B → C no BotCity Maestro | EVIDÊNCIA REAL | Registrada na documentação técnica do projeto. |
| Contrato de coexistência com dois adaptadores | EVIDÊNCIA REAL | Teste com fakes; não comprova plataforma real. |
| Filas, runners, credenciais e estados Smart Office | HIPÓTESE | Aguardam acesso e documentação oficial. |
| Cutover, coexistência e rollback no Smart Office | CONFIGURAÇÃO PLANEJADA | Não executados. |

## 2. Princípios que não podem ser violados

1. Em cada fase existe uma única fonte oficial de novos agendamentos.
2. BotCity e Smart Office consultam o mesmo registro de idempotência antes de
   produzir qualquer efeito externo.
3. Uma troca de orquestrador não altera `execution_id`, `correlation_id`, schema
   ou regra de negócio.
4. Tarefas aceitas precisam terminar, ser canceladas explicitamente ou aparecer
   na reconciliação; nunca são abandonadas silenciosamente.
5. Rollback não reutiliza uma chave já concluída nem recria tarefas em voo.
6. Logs não contêm credenciais, e evidência simulada nunca recebe rótulo real.

## 3. Papéis e autoridade

Os nomes devem ser confirmados na reunião de *go/no-go*. Para este plano:

| Papel | Responsável primário | Substituto | Autoridade |
| --- | --- | --- | --- |
| Líder de migração | Gustavo | Carlos | Conduzir checklist e declarar início/fim da janela. |
| Operador BotCity/rollback | Carlos | Gustavo | Pausar/reativar agendas e drenar tarefas BotCity. |
| Operador Smart Office | Pessoa com acesso oficial, a designar | A designar | Configurar runner, filas e agendas Smart Office. |
| Validador de negócio | Dono do processo, a designar | A designar | Aceitar totais, relatório e regras do smoke test. |
| Segurança | Responsável de credenciais, a designar | A designar | Provisionar/revogar segredos e revisar logs. |

Sem operador Smart Office e validador de negócio nomeados, o cutover é **NO-GO**.

## 4. Fonte oficial de agendamento por fase

| Fase | BotCity | Smart Office | Fonte oficial |
| --- | --- | --- | --- |
| Estado atual | Ativo | Sem acesso | BotCity |
| Preparação | Ativo | Configurado, agendas desabilitadas | BotCity |
| Coexistência em sombra | Ativo e produz efeitos | Recebe cópia marcada `shadow`, sem efeitos | BotCity |
| Congelamento do cutover | Pausado; somente drena tarefas aceitas | Desabilitado | Nenhuma fonte cria tarefas novas |
| Cutover | Desabilitado | Habilitado após marco de troca | Smart Office |
| Estabilização | Pronto para rollback, sem agenda | Ativo | Smart Office |
| Rollback | Reativado após reconciliação | Desabilitado e drenado | BotCity |

Nunca haverá fase planejada em que os dois agendadores estejam autorizados a
criar trabalho produtivo. A coexistência é sombra ou contingência, não dual-write.

## 5. Idempotência e bloqueio compartilhado

### 5.1 Chave

Cada unidade de trabalho recebe uma chave imutável:

```text
idempotency_key = SHA-256(
  ambiente + processo + etapa + chave_negocio + janela_referencia + schema_version
)
```

Para o pipeline, `chave_negocio` identifica o arquivo/lote e
`janela_referencia` impede que reprocessamentos legítimos de períodos diferentes
colidam. O valor não inclui segredo.

### 5.2 Ledger compartilhado

**CONFIGURAÇÃO PLANEJADA:** disponibilizar um ledger durável acessível pelos
dois adaptadores, com restrição única em `idempotency_key`. A tecnologia será
escolhida após conhecer as integrações permitidas pelo Smart Office; pode ser
banco transacional ou serviço interno com operação atômica equivalente.

Campos mínimos:

```text
idempotency_key, execution_id, correlation_id, etapa, chave_negocio,
orquestrador_origem, estado, lease_owner, lease_expires_at,
task_id_origem, artifact_uri, created_at, updated_at
```

Fluxo antes de qualquer efeito:

1. o adaptador tenta `INSERT` atômico da chave com estado `RESERVADA`;
2. quem vencer recebe a lease e pode criar a tarefa;
3. conflito de unicidade retorna `DUPLICADA`, registra a origem perdedora e não
   cria tarefa, relatório, alerta ou nova chamada externa;
4. depois da criação, grava `task_id_origem` e estado `EM_EXECUCAO`;
5. ao terminar, grava `CONCLUIDA` e URI/hash do artefato;
6. leases expiradas vão para reconciliação, nunca para repetição automática
   sem consultar o estado no orquestrador de origem.

Estados válidos: `RESERVADA`, `EM_EXECUCAO`, `CONCLUIDA`, `FALHOU`, `CANCELADA`,
`RECONCILIACAO`. Transições usam comparação de versão para impedir atualização
concorrente.

### 5.3 Proteção contra perda

- O pedido de criação e sua intenção são persistidos antes da chamada externa.
- Um reconciliador compara ledger, BotCity e Smart Office por IDs.
- `RESERVADA` sem `task_id` exige consulta antes de liberar a lease.
- Tarefa em voo permanece no orquestrador que a aceitou; não é migrada no meio.
- Resultado só é concluído após hash/URI do artefato e contagem esperada.
- Toda diferença gera fila manual `RECONCILIACAO` e bloqueia o cutover.

## 6. Pré-migração

Prazo recomendado: concluir até D-1 da janela.

1. Nomear todos os papéis e abrir canal de operação.
2. Inventariar agendas, filas, prioridades, runners, timeouts, retries, alertas,
   calendários e tarefas em voo do BotCity.
3. Obter acesso oficial e documentação de API/SDK do Smart Office.
4. Mapear estados Smart Office para `CONCLUIDO`, `CONCLUIDO_DEGRADADO`,
   `FALHOU`, `CANCELADO` e `TIMEOUT`.
5. Implementar e testar o ledger compartilhado e o reconciliador.
6. Provisionar credenciais separadas por ambiente no cofre; nunca neste arquivo.
7. Publicar os seis bots com versão imutável e hash do pacote.
8. Configurar filas e runners Smart Office com agendas desabilitadas.
9. Executar testes contratuais e smoke não produtivo.
10. Rodar coexistência em sombra sem efeitos e comparar tarefas/artefatos.
11. Ensaiar rollback e medir o tempo total; deve caber no RTO de 30 minutos.
12. Registrar aprovação técnica, negócio, operação e segurança.

Critérios **GO**: zero divergência não explicada na sombra; ledger atômico
validado; smoke aprovado; alertas chegando; rollback ensaiado; nenhuma tarefa em
`RECONCILIACAO`; responsáveis presentes. Caso contrário, **NO-GO**.

## 7. Janela de cutover

Janela planejada: 60 minutos em período sem agendamento crítico. RTO máximo de
rollback: **30 minutos**. A janela e o fuso devem ser aprovados pelo negócio.

### Sequência minuto a minuto

1. **T-15:** congelar mudanças, salvar configuração, filas e tarefas em voo.
2. **T-10:** pausar agendas BotCity; registrar horário e usuário responsável.
3. **T-10 a T+10:** drenar tarefas aceitas pelo BotCity. Nenhuma tarefa nova.
4. **T+10:** executar reconciliação; contagens e chaves precisam fechar em zero
   pendência. Se não fecharem, abortar e reativar BotCity.
5. **T+15:** gravar no controle operacional `scheduler_of_record=smart_office`
   com versão e horário; este é o marco oficial de troca.
6. **T+16:** habilitar uma única agenda canário no Smart Office.
7. **T+20:** executar o smoke test da seção 10.
8. **T+30:** se aprovado, habilitar as demais agendas gradualmente.
9. **T+45:** reconciliar chaves, tarefas, artefatos e alertas novamente.
10. **T+60:** declarar estabilização ou acionar rollback.

Critérios de sucesso: uma reserva por chave; zero tarefa perdida/duplicada;
smoke completo; IDs contínuos; totais e hashes válidos; alertas recebidos;
latência dentro do limite aprovado; nenhuma credencial em logs.

## 8. Pós-migração e estabilização

Por 48 horas:

- manter agendas BotCity desabilitadas, mas configuração recuperável;
- reconciliar a cada 15 minutos nas primeiras 2 horas e depois a cada hora;
- acompanhar duplicidades recusadas, leases vencidas, backlog, timeout, dead
  letter, falhas por bot, latência e entrega de alertas;
- comparar contagem de entradas, chaves concluídas e relatórios;
- preservar evidências por execução e realizar revisão após 24 e 48 horas.

BotCity só pode ser descomissionado após aprovação formal do negócio, operação
e segurança. A remoção de credenciais ocorre depois do fim da janela de retorno.

## 9. Rollback

### Gatilhos

Qualquer um aciona avaliação imediata; os itens críticos acionam rollback:

- duplicidade com efeito externo ou perda de uma tarefa (**crítico**);
- ledger indisponível ou sem garantia atômica (**crítico**);
- smoke incompleto, IDs divergentes ou artefato inválido (**crítico**);
- backlog/erro acima do limite acordado por 10 minutos;
- runner indisponível sem recuperação em 10 minutos;
- alertas indisponíveis nos dois canais;
- solicitação do dono do processo ou incidente de segurança (**crítico**).

O líder decide em até 10 minutos; recuperação deve terminar em até 30 minutos
após o gatilho.

### Passos

1. Líder declara rollback e bloqueia novas alterações.
2. Operador Smart Office desabilita todas as agendas e registra tarefas em voo.
3. Não cancelar automaticamente tarefas em voo: reconciliar chave e estado.
4. Definir no controle `scheduler_of_record=none` durante a drenagem.
5. Operador BotCity valida versão/configuração anterior e saúde dos runners.
6. Reconciliador classifica cada chave como concluída, em voo ou segura para
   reagendamento; nunca remove registros concluídos.
7. Reativar agendas BotCity e então definir `scheduler_of_record=botcity`.
8. Executar smoke test pelo BotCity com nova chave.
9. Confirmar relatório, IDs, alertas e ausência de duplicidade.
10. Comunicar restauração, preservar evidências e abrir análise de causa.

## 10. Smoke test pós-migração

### Entrada controlada

- ambiente não produtivo ou lote canário autorizado;
- arquivo/massa versionada com 12 lotes dos simuladores;
- `execution_id=exec-smoke-<data>-001`;
- `correlation_id=corr-smoke-<data>-001`;
- chave inédita e sem dados pessoais/credenciais.

### Execução e resultado esperado

| Verificação | Esperado |
| --- | --- |
| Agendamento | Smart Office cria somente uma cadeia para a chave. |
| Bot A | Entrada aceita e IDs preservados. |
| Bot B | 12 registros e `estoque_desktop.json`. |
| Bot C | 12 registros e `pedidos_fornecedores.json`. |
| Bot D | 12 consolidados; classificação determinística presente. |
| Bot E | 12 enriquecidos por ML ou fallback explicitamente auditado. |
| Bot F | Excel com 12 registros, resumo, logs e alerta de teste. |
| Ledger | Uma chave concluída, origem Smart Office e URIs/hashes preenchidos. |
| BotCity | Nenhuma nova tarefa para a chave do smoke. |
| Segurança | Nenhum segredo em parâmetros, logs ou artefatos. |

O smoke falha se qualquer quantidade divergir, um ID mudar, surgir duplicidade,
o relatório não abrir ou uma tarefa ficar sem estado final/reconciliação.

## 11. Checklist de prontidão

### Acessos e credenciais

- [ ] Acesso oficial Smart Office para operador e substituto.
- [ ] Contas de serviço separadas por ambiente e com privilégio mínimo.
- [ ] Segredos no cofre, rotação definida e valores ausentes de código/logs.
- [ ] Acesso BotCity preservado durante toda a janela de rollback.
- [ ] Permissão no ledger compartilhado testada pelos dois adaptadores.

### Runners e pacotes

- [ ] Runners online, capacidade/concorrência e fuso confirmados.
- [ ] Fedora e dependências desktop/Chromium validados.
- [ ] Seis pacotes imutáveis identificados por versão e SHA-256.
- [ ] Diretórios de logs, screenshots, dead letter e relatórios graváveis.
- [ ] Timeout, retry, backoff e encerramento de processos testados.

### Filas, agendas e prioridades

- [ ] Nomes e tipos reais das filas documentados com evidência.
- [ ] Mapeamento de prioridades e estados aprovado.
- [ ] Calendários, timezone, deadlines e política de cancelamento revisados.
- [ ] Agendas Smart Office desabilitadas até o marco de cutover.
- [ ] Lista de agendas BotCity e procedimento de pausa/retorno exportados.

### Observabilidade e alertas

- [ ] IDs pesquisáveis em ambos os orquestradores e no ledger.
- [ ] Métricas de backlog, erro, timeout, duplicidade e lease configuradas.
- [ ] Telegram/e-mail de teste entregues sem expor credenciais.
- [ ] JUnit, logs, screenshots, dead letters e relatórios preservados.
- [ ] Canal de incidente e contatos dos responsáveis confirmados.

### Go/no-go e rollback

- [ ] Sombra sem efeitos e sem divergências inexplicadas.
- [ ] Reconciliador e bloqueio atômico testados sob concorrência.
- [ ] Smoke test aprovado.
- [ ] Ensaio de rollback concluído em até 30 minutos.
- [ ] Aprovações de técnica, negócio, operação e segurança registradas.

## 12. Evidências que deverão ser anexadas

Somente após execução real, anexar sem segredos:

- export das agendas antes/depois e marco `scheduler_of_record`;
- IDs de tarefas BotCity/Smart Office e registros do ledger;
- log de conflito provando rejeição de uma chave duplicada;
- resultado da reconciliação com zero pendência;
- smoke: entrada, JUnit, logs, hashes, relatório e alerta;
- horários de cutover/rollback e aprovações dos responsáveis;
- versão dos runners, pacotes e configuração sanitizada.

Até esses anexos existirem, os itens continuam como **HIPÓTESE** ou
**CONFIGURAÇÃO PLANEJADA**. O teste com fakes demonstra o contrato esperado,
mas não valida filas, autenticação, consistência ou comportamento do Smart
Office real.
