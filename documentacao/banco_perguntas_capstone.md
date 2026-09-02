# Banco de perguntas e respostas — defesa do Capstone

Respostas planejadas para 20–40 segundos. Quando a pergunta exigir evidência,
mostrar o arquivo ou teste indicado em vez de apenas afirmar.

## Arquitetura e processo

### Por que dividir em seis bots?

Para separar entrada, duas fontes, decisão determinística, enriquecimento e
saída. Isso permite retry, timeout, evidência e manutenção por responsabilidade,
além de impedir que a falha do ML ou de uma coleta contamine todo o fluxo.

### Por que B e C são independentes?

Desktop e portal têm tecnologias e falhas diferentes. O fan-out reduz
acoplamento; o Bot D faz o fan-in e decide se há dados suficientes para modo
normal ou degradado.

### Qual é o contrato entre bots?

Artefatos versionados preservam `execution_id`, `correlation_id`, `bot_id`,
`task_id`, estado, predecessor e horário com fuso. Os modelos estão em
`src/contratos_capstone.py` e rejeitam campos inválidos.

### Como evitam mistura entre execuções?

Os mesmos IDs seguem em tarefas, artefatos, logs, alertas e dead letters. O E2E
verifica que todos os eventos e arquivos pertencem à mesma execução.

## Regras e Machine Learning

### Por que usar ML se já existem regras?

As regras determinam o status oficial. O ML acrescenta uma causa provável para
priorizar investigação. Ele resolve um problema diferente e não substitui a
decisão auditável das RN01–RN12.

### O que ocorre se o ML errar ou ficar fora do ar?

A saída determinística permanece intacta. Timeout, indisponibilidade, resposta
inválida e baixa confiança produzem fallback explícito, e o lote continua.

### Por que Logistic Regression?

É uma baseline pequena, rápida e explicável para o dataset controlado. Produz
probabilidades úteis ao limiar de confiança. A escolha futura deve ser guiada
por métricas reproduzíveis, não por complexidade do algoritmo.

### Como evitam aceitar previsão fraca?

`ML_MIN_CONFIDENCE` define o limiar. Abaixo dele a causa não é aceita, a origem
vira fallback e o motivo `baixa_confianca` é auditado.

## Resiliência

### Qual a diferença entre erro de item e infraestrutura?

`ErroDeItem` é determinístico e restrito ao registro. Após o limite ele vai para
dead letter. `ErroDeInfraestrutura` representa recurso externo potencialmente
temporário e segue a política limitada de retry/backoff da integração.

### Como garantem que não existe retry infinito?

Toda política valida `max_tentativas >= 1`, backoff não negativo e timeout
positivo. Os loops usam intervalos finitos e os testes conferem chamadas e
esperas exatas.

### O que é dead letter e como reprocessar?

É um JSONL append-only com motivo, payload sanitizado, tentativas e IDs. Após
corrigir a causa, `reprocessar_pendentes` acrescenta outro evento ao histórico;
o original não é apagado ou editado.

### Um item inválido interrompe o lote?

Não. O processador isola o item, persiste a dead letter e continua. O cenário 6
comprova dois itens processados apesar de um registro irrecuperável.

### O que ocorre se desktop ou web falhar?

Cada coleta registra falha, tentativas e evidência. Se a outra fonte permitir
uma decisão segura, o fan-in pode prosseguir como `CONCLUIDO_DEGRADADO`; sem
fonte utilizável, encerra com falha controlada.

### Como o timeout é tratado?

A espera consulta o predecessor até um deadline. Ao atingir o limite registra
`dependencia_timeout` e lança uma exceção tipada, evitando bloqueio infinito.

## Alertas, logs e segurança

### O que ocorre se o Telegram falhar?

Para eventos elegíveis o sistema tenta e-mail. Se ambos falharem, o relatório
continua válido e o erro é registrado; comunicação não desfaz processamento.

### Como protegem dados sensíveis?

Segredos ficam em variáveis/cofre, não nos payloads. Antes de persistir, chaves
como token, password, senha, secret e API key são substituídas por `[REDACTED]`.
O `.env` não é versionado.

### Quais evidências são produzidas?

JUnit, logs JSONL, screenshots, HTML de falha, dead letters, JSONs intermediários
e relatório Excel. O CI publica artefatos com `if: always()`, inclusive em falha.

## Testes, CI e demonstração

### Os testes dependem de serviços reais?

Não. Unitários e crise usam mocks/fakes; o E2E inicia os simuladores desktop,
portal e API ML locais. Credenciais e Smart Office reais não são necessários.

### Como uma falha bloqueia o merge?

Os jobs obrigatórios executam por camada. Um agregador com `if: always()` lê o
resultado de cada dependência e falha se qualquer uma não for `success`.

### Por que publicar evidências quando o job falha?

Sem logs e artefatos, o defeito fica difícil de reproduzir. `if: always()`
preserva o diagnóstico sem transformar falha em sucesso; o agregador continua
bloqueando o merge.

### Como comprovam encerramento dos processos auxiliares?

O executor guarda os subprocessos e encerra todos em ordem reversa dentro de
`finally`, usando terminate, espera limitada e kill como último recurso. O E2E
confirma `processos_encerrados=true`.

## Orquestração e limitações

### O Smart Office foi validado?

Não. A coexistência é somente teste contratual com fake local e registra
`PENDENTE_PLATAFORMA` e `evidencia_real=false`. Filas, credenciais, cutover e
rollback exigem acesso real antes de qualquer afirmação de validação.

### O que foi validado no BotCity Maestro?

A cadeia compatível A → B → C, com publicação e transferência de artefatos. No
E2E local, as responsabilidades são mostradas em seis etapas. São contextos de
execução distintos e isso deve ser dito claramente.

### Como evitariam duplicidade entre dois orquestradores reais?

Usaríamos chave idempotente por execução/etapa, armazenamento compartilhado e
auditoria da origem vencedora. O contrato e a preservação de IDs foram testados;
a eficácia no Smart Office ainda depende de validação real.

### Por que Fedora é a referência?

É o ambiente previsto para Runner e demonstração desktop. A documentação lista
Tkinter, Docker, Xvfb e Chromium necessários; no CI Ubuntu, Xvfb oferece display
virtual equivalente para os componentes visuais.

## Manutenção e decisão de negócio

### Como adicionar uma integração?

Definir contrato, política finita de retry/backoff/timeout, exceções tipadas,
sanitização, logs correlacionados, fallback e testes por camada antes de incluí-la
no agregador obrigatório do CI.

### Como alterar uma regra RN?

Atualizar a função determinística, testes parametrizados, PDD e exemplos. Não
ajustar o ML para mascarar a mudança: a regra continua sendo a autoridade.

### Qual é o ganho entregue?

O pipeline transforma fontes separadas em uma fila auditável de decisões,
mantém o lote fluindo diante de falhas toleráveis e reduz investigação manual
com causas sugeridas, sem perder rastreabilidade ou controle humano.

### Qual é o principal risco restante?

A integração real e a coexistência com Smart Office. O risco está declarado e
não é ocultado por simulação; o próximo passo é executar testes de plataforma
com evidência real, critérios de cutover e rollback.
