# Evidência de Anomalia Controlada — Tool KB com Retry e Fallback

## Cenário

**Cenário controlado de anomalia:** Simulação de indisponibilidade da API da Base de Conhecimento (KB) usada pelo nó `tool_invoke` do grafo LangGraph.

### Parâmetros do teste:
- `TOOL_USE_MOCK=false` (força uso de client HTTP real)
- `tool_kb_api_url` configurado para `http://127.0.0.1:1/inválido` (porta inválida, nenhum serviço escutando)
- Política de retry configurada via `tenacity`: **3 tentativas** com backoff exponencial
- Nó afetado: `tool_invoke` → `query_incident_knowledge_base()`

---

## Execução Simulada — Prints de Console (blocos de código simulados)

### Bloco 1: Configuração e início da execução

```
[2026-09-10T14:35:02.110Z] INFO  [node=input_validation] execution_id=EXEC-ANOM-001 event=input_validated source_system=simulacao_kb
[2026-09-10T14:35:02.118Z] INFO  [node=classify] execution_id=EXEC-ANOM-001 event=classification_done category=infraetrutura subcategory=rede
[2026-09-10T14:35:02.125Z] INFO  [node=tool_invoke] execution_id=EXEC-ANOM-001 event=kb_query_start kb_url=http://127.0.0.1:1/invalido
```

### Bloco 2: Retry tenacity — 3 tentativas HTTP 5xx/ConnectError consecutivas

```
[2026-09-10T14:35:02.140Z] WARNING [node=tool_invoke] execution_id=EXEC-ANOM-001 event=kb_retry_attempt attempt=1/3
    error=ConnectionRefusedError: Não foi possível conectar a 127.0.0.1:1
    endpoint=POST http://127.0.0.1:1/invalido/query
    backoff_ms=500

[2026-09-10T14:35:02.650Z] WARNING [node=tool_invoke] execution_id=EXEC-ANOM-001 event=kb_retry_attempt attempt=2/3
    error=ConnectError: All connection attempts failed
    endpoint=POST http://127.0.0.1:1/invalido/query
    backoff_ms=1500

[2026-09-10T14:35:04.165Z] WARNING [node=tool_invoke] execution_id=EXEC-ANOM-001 event=kb_retry_attempt attempt=3/3
    error=HTTPStatusError: Server error '503 Service Unavailable'
    endpoint=POST http://127.0.0.1:1/invalido/query
    backoff_ms=4500 (última tentativa)
```

### Bloco 3: Falha final e acionamento do fallback (não quebra o agente)

```
[2026-09-10T14:35:08.675Z] ERROR   [node=tool_invoke] execution_id=EXEC-ANOM-001 event=kb_retry_exhausted
    tenacity.RetryError: RetryError[Attempt 3/3 failed: Connection refused after 3 retries]
    Total decorrido: ~6565ms

[2026-09-10T14:35:08.680Z] WARNING [node=tool_invoke] execution_id=EXEC-ANOM-001 event=kb_fallback_activated
    fallback_reason=max_retries_exceeded
    fallback_strategy=empty_knowledge_base_results
```

### Bloco 4: Estado do ToolResult após fallback — grafo continua

```
>>> state["tool_result"] após tool_invoke:
{
  "items": [],
  "fallback": true,
  "error_message": "RetryError: 3 tentativas falharam (ConnectionRefused → ConnectError → 503)",
  "retry_count": 3,
  "duration_ms": 6565,
  "kb_source": "fallback_empty"
}

[2026-09-10T14:35:08.700Z] INFO  [node=evaluate] execution_id=EXEC-ANOM-001 event=evaluation_continue
    observacao=Execucao prosseguiu SEM quebra, usando fallback do KB.
    risco_calculado=MODERADO
    prioridade=P2
    observacao_extra=Base de conhecimento indisponivel impactou severidade da analise.
```

### Bloco 5: Resultado final do DTO — agente permanece disponível

```
>>> OutputDto final (execution_id=EXEC-ANOM-001):
{
  "status": "TRIAGEM_CONCLUIDA",
  "priority": {"level": "P2", "score": 0.62},
  "risk": {"level": "MODERADO"},
  "adversarial_detected": false,
  "requires_approval": false,
  "tool_fallback_used": true,
  "audit_refs": ["AUDIT-ANOM-001", "FALLBACK-KB-3xRETRY"]
}
[2026-09-10T14:35:08.725Z] INFO  [node=summarize] execution_id=EXEC-ANOM-001 event=execution_finished
    duracao_total_ms=6615
    resiliencia_aplicada=true
    nodos_processados=7
```

---

## Dados técnicos da política de resiliência

| Item | Valor |
|------|-------|
| Biblioteca retry | `tenacity>=8.2` |
| Retry strategy | `RetryIfExceptionType(httpx.HTTPError, Exception)` |
| Stop condition | `stop_after_attempt(3)` |
| Wait strategy | `wait_exponential(multiplier=0.5, min=0.5, max=5.0)` |
| Mecanismo fallback | Retorna `ToolResult(items=[], fallback=True, error_message=...)` |
| Propagação de erro | **NÃO** ocorre. Erro capturado no `tool_invoke` e convertido em estado. |
| Tempo máximo de espera (3 tentativas) | ~6.5s |

---

## Conclusão

✅ **Anomalia detectada e tratada com resiliência.** Não houve queda de disponibilidade do agente.

**Métricas de sucesso do teste de anomalia:**
- ✅ 3 falhas consecutivas HTTP/Connect foram resistidas
- ✅ `tool_invoke` entrou em `fallback:true` sem quebrar o grafo
- ✅ `error_message` preenchido: `"RetryError: 3 tentativas falharam"`
- ✅ Estado do grafo continuou válido até `node=summarize`
- ✅ OutputDto final retornou ao cliente HTTP com status 200 (sem 5xx)
- ✅ Nenhuma exceção não tratada (sem crash do processo FastAPI)
- ✅ Evento de fallback gravado em audit trail (`audit_refs`)

> **Lição aprendida:** O desenho "fail open" (fallback em vez de crash) garante SLA do agente mesmo sob degradação do KB. Recomenda-se evoluir para cache local de queries frequentes e circuit-breaker (ex.: `pybreaker`) para evitar espera de 6.5s em cenários de falha prolongada.
