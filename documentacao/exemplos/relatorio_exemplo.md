# Relatório de execução — exemplo sanitizado

> Documento ilustrativo. Não contém credenciais nem dados pessoais reais.

| Campo | Valor de exemplo |
| --- | --- |
| Execução | `exec-exemplo-001` |
| Correlação | `corr-exemplo-001` |
| Estado | `CONCLUIDO` |
| Registros desktop | 12 |
| Registros web | 12 |
| Registros consolidados | 12 |
| Modo degradado | Não |
| Canal do alerta | Console simulado |

## Amostra de registro

```json
{
  "lote_id": "LOTE-EXEMPLO-001",
  "produto": "Componente demonstrativo",
  "classificacao_deterministica": "Divergência",
  "causa_provavel": "erro_codigo",
  "confianca_ml": 0.87,
  "origem_decisao": "ml",
  "execution_id": "exec-exemplo-001",
  "correlation_id": "corr-exemplo-001"
}
```

Se o ML não responder, `origem_decisao` passa a `fallback` e
`motivo_fallback` registra a causa, sem modificar a classificação determinística.
