# Runbook operacional do Capstone

## Triagem inicial

1. Registre horário, `execution_id`, `correlation_id`, bot e ambiente.
2. Consulte `logs/`, `data/output/capstone_e2e/` e os artefatos do CI/Maestro.
3. Confirme se a falha é de item ou infraestrutura e preserve as evidências.
4. Nunca copie tokens, senhas ou payloads não sanitizados para chamados.

## Desktop

- Confirme `DISPLAY`, sessão gráfica e imagens em `resources/capstone_desktop`.
- No Fedora, valide `python3-tkinter`; no CI use Xvfb.
- Consulte screenshots em `screenshots/bot_desktop` e tentativas no log.
- Reinicie somente após verificar que o limite de retries foi atingido.

## Portal web

- Consulte `http://127.0.0.1:8010/health` e valide host/porta do `.env`.
- Confira Chromium (`python -m playwright install chromium`), screenshot e HTML.
- Se uma fonte continuar disponível, confirme `CONCLUIDO_DEGRADADO` no fan-in.

## API ML

- Local: `curl http://localhost:8000/health`.
- Docker: `docker compose ps api_ml` e `docker compose logs api_ml`.
- O estado esperado é `healthy` com `modelo_carregado=true`.
- Em falha, confirme fallback e que a classificação determinística não mudou.

## Telegram e e-mail

- Verifique flags, timeout e presença das credenciais no cofre/ambiente, sem
  imprimi-las.
- Telegram indisponível deve acionar e-mail para ERRO/CRÍTICO.
- Se ambos falharem, preserve relatório e log crítico; não reexecute o lote só
  para reenviar uma notificação.

## Dependências e timeout

- Localize `predecessor_task_id` e confira seu estado no orquestrador.
- Não aumente timeout sem evidência de que o tempo normal excede o limite.
- Após timeout, verifique se outra fonte permite continuidade degradada.

## Dead letter

- Arquivo padrão: `data/output/dead_letter.jsonl`.
- Localize pelo `dead_letter_id`, `execution_id`, `correlation_id` e `item_id`.
- Corrija a causa, mantenha o histórico append-only e use
  `reprocessar_pendentes`; nunca edite ou apague eventos anteriores.
- Confirme um evento de reprocessamento bem-sucedido antes de encerrar o caso.

## Relatórios, logs e evidências

- Compare as quantidades dos artefatos desktop, web, consolidados e relatório.
- Todos devem manter os mesmos IDs. Divergência indica mistura de execuções.
- No CI, baixe JUnit, logs, screenshots, dead letters e relatórios publicados
  mesmo em falha (`if: always()`).

## Encerramento e escalonamento

Registre causa, fallback, impacto, evidências e ação. Escale quando ambas as
fontes falharem, houver corrupção da dead letter, IDs divergirem ou a decisão
determinística for alterada pelo ML. Smart Office deve continuar marcado como
pendente até haver acesso e evidência real.
