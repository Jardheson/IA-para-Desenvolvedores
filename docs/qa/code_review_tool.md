# Code Review Manual — Tool `kb_client.py` (Knowledge Base Client)

## 1. Resumo do Diff Revisado

| Item | Valor |
|---|---|
| Arquivo alvo | `src/tools/kb_client.py` |
| Função principal | `query_incident_knowledge_base` — L117-158 |
| Auxiliares | `_mock_search` L50-66, `_http_search` L80-110 |
| Revisor | Trae AI Code Review (registro QA) |
| Data da revisão | 2025-09-10 |
| Escopo | Retry/fallback, schema de saída, tratamento de erro, vazamento de dados |

---

## 2. Trechos de código sob análise

### 2.1 Decorator `@retry` em `_http_search` (L73-79)

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=0.3, max=5.0),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _http_search(query: str, top_k: int) -> KBQueryResponse:
```

### 2.2 Entrada pública (L117-158)

```python
def query_incident_knowledge_base(params: KBQueryRequest | dict[str, Any]) -> KBQueryResponse:
    if isinstance(params, dict):
        params = KBQueryRequest(**params)
    if not isinstance(params, KBQueryRequest):
        raise ToolExecutionError("params KB invalidos",
                                 context={"type": type(params).__name__})
    ...
    try:
        return _http_search(params.query, params.top_k)
    except RetryError as exc:
        ...
        return KBQueryResponse(
            query=params.query, items=[], fallback=True,
            error_message=f"RetryError: 3 tentativas falharam ({exc.__cause__!r})",
            retry_count=3, duration_ms=dur,
            meta={"source": "fallback_after_retry_error"},
        )
    except Exception as exc:
        ...
        return KBQueryResponse(
            query=params.query, items=[], fallback=True,
            error_message=repr(exc), retry_count=0, duration_ms=dur,
            meta={"source": "fallback_unexpected"},
        )
```

---

## 3. Achados do Code Review

### CR-01 — ALTO: `except Exception` genérico mascara erro de tipagem em L147

**Local**: `src/tools/kb_client.py:147-157`

**Descrição**:
Após o bloco `except RetryError`, há um `except Exception` genérico que captura QUALQUER exceção (incluindo `ValidationError`, `ToolExecutionError`, `TypeError` de schema Pydantic) e retorna um `KBQueryResponse` vazio marcado como fallback. Embora a resiliência seja boa, erros de *validação* devem propagar para cima, não serem "engolidos" como indisponibilidade de rede.

**Risco**:
Um erro de programador passando parâmetros inválidos (ex: `top_k=1000` fora do range) retorna `fallback=true` sem nenhum aviso forte. O time fica sem saber se o problema é rede ou código.

**Sugestão de mudança**:
```python
    except RetryError as exc:
        # ... fallback por rede — OK
        return KBQueryResponse(...)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        # Demais erros de rede sem retry (não passou pelo decorator)
        dur = int((time.perf_counter() - t0) * 1000)
        logger.warning("tool KB fallback por erro de rede não retry: %r", exc)
        return KBQueryResponse(
            query=params.query, items=[], fallback=True,
            error_message=repr(exc), retry_count=0, duration_ms=dur,
            meta={"source": "fallback_network_no_retry"},
        )
    # DEMÁIS EXCEÇÕES (ValidationError, TypeError, ToolExecutionError, etc.)
    # DEVEM PROPAGAR — não engolir.
```

---

### CR-02 — MÉDIO: `retry_count=0` no fallback genérico é inconsistente (L155)

**Local**: `src/tools/kb_client.py:155`

**Descrição**:
O fallback de `RetryError` marca `retry_count=3`. O fallback genérico marca `retry_count=0`. Se o decorator fez 2 retries e levantou `TypeError` dentro da resposta, `retry_count=0` mente para o observador.

**Sugestão**:
Ler `_http_search.retry.statistics.attempt_number` também no catch genérico.

---

### CR-03 — BAIXO: Mock `_MOCK_DB` não tem categoria "Operacional" (L28-47)

**Local**: `src/tools/kb_client.py:28-47`

**Descrição**:
Categorias mockadas: Disponibilidade, Integridade, Segurança, Performance. Falta "Operacional". Incidentes classificados como Operacional nunca encontram matches e sempre recebem similaridade baixa — enviesa o `evaluate_risk` no teste de memória/histórico.

**Sugestão**:
Adicionar um item KB com `category="Operacional"`.

---

### CR-04 — POSITIVO (feito corretamente)

| Item | Como está implementado | Avaliação |
|---|---|---|
| Timeout HTTP | `httpx.Client(timeout=settings.http_timeout_seconds)` L85 | ✅ Usa variável de configuração, não hardcoded |
| Retry count máximo | `stop_after_attempt(3)` + `reraise=True` | ✅ <= 3, sem retry infinito (AC-15) |
| Fallback tipado | Sempre retorna `KBQueryResponse`, nunca `None` | ✅ Compatibilidade com `ToolResult` TypedDict |
| Validação de entrada | `KBQueryRequest(**params)` L125 | ✅ Pydantic valida query vazia/longa |
| Logging estruturado | `logger.warning` em todos os catch | ✅ Sincroniza com observabilidade (AC-5) |

---

## 4. Conclusão da revisão

| Severidade | Quantidade | Status |
|---|---|---|
| Alto | 1 (CR-01) | Recomenda-se correção antes do merge de feature branches que alterem tool |
| Médio | 1 (CR-02) | Backlog de tech debt |
| Baixo | 1 (CR-03) | Backlog |
| Positivos | 5 | Mantidos como boas práticas |

**Parecer final**: O desenho geral da tool está correto (3-pilares: validação → HTTP com retry → fallback tipado). O único item que bloqueia release de produção é o CR-01, porque mascara erros de validação como indisponibilidade e impede QA de identificar defeitos de integração.

---

## 5. Evidência vinculada ao fluxo de IA Code Review

- Prompt de revisão: estruturado como "problema → risco → sugestão".
- Este documento cumpre **AC-7 (IA realizando code review registrado)**, linkando diretamente o diff de `src/tools/kb_client.py` a achados concretos.
- Para reproduzir a revisão, basta abrir `src/tools/kb_client.py` e comparar com os 4 itens acima.
