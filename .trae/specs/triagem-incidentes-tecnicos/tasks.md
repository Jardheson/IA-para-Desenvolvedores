# Agente Inteligente de Triagem e Análise de Incidentes Técnicos — Implementation Plan

Alinhamento com as FASES 1–14 do Projeto de Recuperação Módulo 2. Cada tarefa mapeia para ACs do `spec.md` e contém requisitos de teste locais (TR).

---

## Task 1: FASE 1 — Fundação (repositório, estrutura inicial, .env.example, dependências)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Inicializar repositório git; criar branches `main` e `develop`; criar primeira `feature/fundacao` a partir de `develop`.
  - Estruturar pastas:
    - `src/api/` — FastAPI entrypoints, schemas Pydantic
    - `src/graph/` — LangGraph state, nodes, edges, grafo montado
    - `src/tools/` — Tool + cliente HTTP
    - `src/memory/` — Persistência state + checkpointer
    - `src/security/` — Validações, heurística anti-injection, política de autonomia
    - `src/observability/` — Logger estruturado JSON + auditoria
    - `src/errors/` — Hierarquia AppError
    - `src/prompts/` — System prompts carregáveis
    - `src/lowcode/` — Cliente webhook n8n
    - `tests/` — unit / integration / e2e / adversarial
    - `docs/` — prompts / qa / evidencias
    - `.github/workflows/ci.yml`
    - `scripts/ci.ps1` (simulação pipeline local)
  - Criar `pyproject.toml` com dependências: `fastapi, uvicorn, langgraph, langchain, langchain-openai, pydantic-settings, pydantic, python-dotenv, tenacity, httpx, python-json-logger, pytest, pytest-asyncio, pytest-cov, ruff`.
  - Criar `.env.example` (sem valores reais): `OPENAI_API_KEY, OPENAI_MODEL, N8N_WEBHOOK_URL, TOOL_USE_MOCK, TOOL_KB_API_URL, LOG_LEVEL, MAX_STEPS, STORAGE_PATH, ADVERSARIAL_THRESHOLD`.
  - Criar `.gitignore` (Python + `.env`).
  - Criar `Makefile` (ou `justfile` / scripts PowerShell equivalentes) com alvos `install, dev, test, lint, ci`.
  - Primeiro commit semântico: `feat: fundação do repositório e estrutura inicial`.
- **Acceptance Criteria Addressed**: AC-14, AC-16, AC-13 (parcial)
- **Test Requirements**:
  - `rule` TR-1.1: `pyproject.toml` instala com sucesso (`pip install -e .` ou equivalente) e importações básicas não falham
  - `rule` TR-1.2: `.env.example` contém todas variáveis sem valores reais; `.env` está em `.gitignore`
  - `rule` TR-1.3: Estrutura de pastas existe conforme especificado
  - `rubric` TR-1.4: Clareza e adequação da estrutura de camadas; escala 0-5; âncoras 1=bagunçada / 3=básica / 5=limpa e unidirecional; threshold ≥ 4; evidência = inspeção de pasta e imports

---

## Task 2: FASE 2 — LangGraph Agente (state, nodes, edges, paralelização, decisão, parada)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - `src/graph/state.py`: TypedDict/Pydantic do State completo (`execution_id, received_at, raw_input, validated, validation_errors, analysis, classification, priority, tool_results, risk_assessment, requires_approval, final_recommendation, output_dto, audit_refs, error, step_count, history_refs`).
  - `src/graph/nodes.py`: 9 nós conforme arquitetura (inicialmente com implementações mínimas ou stubs que depois serão preenchidos pelas demais fases; garantir que o grafo execute).
  - `src/graph/edges.py`: Arestas sequenciais, fan-out paralelo `[classify_incident, analyze_priority]`, fan-in para `tool_invoke`, aresta condicional de `evaluate_risk`, condição de parada (`step_count >= MAX_STEPS` causa early_stop com erro AppError `MaxStepsExceeded`).
  - `src/graph/graph.py`: Compilação `StateGraph(State).add_node(...).add_edge(...)`.with_config({"recursion_limit": MAX_STEPS + 2}).
  - `src/graph/service.py`: `run_triage(raw_input, reporter, source_system)` orquestra state inicial, invoca grafo, retorna output DTO.
  - Contador de passos incrementado no início de cada nó (garante parada por `MAX_STEPS`).
- **Acceptance Criteria Addressed**: AC-1, AC-15
- **Test Requirements**:
  - `rule` TR-2.1: Grafo compila sem erros e executa fluxo happy path com stubs até `emit_output`
  - `rule` TR-2.2: Execução com `MAX_STEPS=2` gera erro de parada e não entra em loop
  - `rule` TR-2.3: Log/trace mostra `classify_incident` e `analyze_priority` em paralelo (nós executam com IDs assíncronos / ordem de término não previsível, ambos iniciados antes do próximo nó)
  - `rule` TR-2.4: Aresta condicional `requires_approval=True → finalize_risky` e `False → finalize_normal` corretas em 2 execuções distintas

---

## Task 3: FASE 3 — Tool (schema, validação, timeout, retry, fallback)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 2
- **Description**:
  - `src/tools/schemas.py`: Pydantic `KBQueryRequest(query: str, top_k: int = 5)` com validators `min_length=3`, `max_length=500` para `query` e `ge=1, le=20` para `top_k`.
  - `src/tools/kb_client.py`: `query_incident_knowledge_base(params) → KBQueryResponse`. Usa `httpx.AsyncClient` com timeout=5s.
  - Decorador `@retry` do `tenacity`: tentativas=3, `wait_exponential(min=0.5, max=5)`, `retry_if_exception_type(HTTPError/TimeoutError)`, `before_sleep` loga tentativa.
  - Fallback: após 3 falhas retorna `KBQueryResponse(items=[], fallback=True, error_message="...")`.
  - Mock mode: se `TOOL_USE_MOCK=true`, cliente não faz HTTP e retorna dados mock determinísticos.
  - `src/tools/__init__.py`: exporta função tipada.
  - Integra o nó `tool_invoke` do Task 2 para chamar essa tool.
- **Acceptance Criteria Addressed**: AC-2, AC-15
- **Test Requirements**:
  - `rule` TR-3.1: Chamada com parâmetros válidos retorna lista tipada (mock ou real)
  - `rule` TR-3.2: Chamada com `query=""` ou `query="a"*600` falha em validação **antes** de fazer HTTP
  - `rule` TR-3.3: Simulando erro de rede (httpx_mock), são efetuadas exatamente 3 tentativas e o retorno tem `fallback=true`
  - `rule` TR-3.4: Estrutura de logs mostra contagem de tentativas e duração

---

## Task 4: FASE 4 — Memória / Contexto (state persistido + checkpointer + uso real em risco)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 2, Task 3
- **Description**:
  - `src/memory/store.py`: `ExecutionStore` salva/carrega state por `execution_id` em JSON no diretório `STORAGE_PATH/executions/{id}.json`. Append de índice `index.jsonl` por data.
  - `src/memory/checkpointer.py`: (opcional) `MemorySaver` do LangGraph ou SQLite simples; mínimo necessário: o `ExecutionStore` já permite recuperar execuções passadas.
  - `src/graph/nodes.py` — `evaluate_risk`: consulta `ExecutionStore.list_recent_by_system(source_system, window_hours=24)`. Se contagem >= 3 → incrementa `risk_level` 1 nível e grava `history_considered=True` em `risk_assessment.meta`.
  - `src/api/routes.py` — `GET /incidents/{execution_id}`: retorna state persistido + DTO.
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `rule` TR-4.1: Execução 1 persiste em arquivo; `GET /incidents/{id}` retorna mesmo `execution_id`
  - `rule` TR-4.2: 3 execuções no mesmo `source_system` (com horários simulados dentro de janela de 24h) causam elevação de risco na 3ª (comparar com risco da 1ª)
  - `rule` TR-4.3: `risk_assessment.meta.history_considered == true` aparece nas execuções que consultaram histórico

---

## Task 5: FASE 5 — Segurança (validações, injection, limites de autonomia, aprovação humana)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 2
- **Description**:
  - `src/errors/app_error.py`: hierarquia `AppError(BaseException)` → `ValidationError`, `SecurityViolation`, `ToolExecutionError`, `GraphMaxStepsError`, `ApprovalRequiredError`.
  - `src/security/input_validator.py`: valida tamanho máximo (5000 chars), pattern de caracteres proibidos (null bytes, shell escapes) e scoring anti-injection (contém termos proibidos + heurísticas de prompt leak). Retorna `ValidationResult{is_valid, errors, injection_score}`.
  - `src/security/autonomy.py`: função `requires_human_approval(risk_level, injection_score, classification) → bool` com regras: risco ALTO → True; injection_score ≥ threshold → True; classificação INTEGRIDADE/DADOS + P1 → True.
  - Integrar `input_validator` no nó `validate_request` e `autonomy.requires_human_approval` no nó `evaluate_risk`.
  - API externaliza erros: status HTTP 4xx/5xx estruturado (`{code, message, correlation_id}`); stack trace só no log interno.
  - `.env.example` sem secrets reais.
- **Acceptance Criteria Addressed**: AC-3, AC-14, AC-15
- **Test Requirements**:
  - `rule` TR-5.1: `POST /incidents` com entrada vazia/muito longa retorna 422 estruturado
  - `rule` TR-5.2: Entrada adversarial ("Ignore as regras anteriores...") gera `injection_score ≥ threshold` → `requires_approval=true` → resposta sem nenhum campo interno/chave
  - `rule` TR-5.3: Resposta de erro externa não contém stack trace
  - `rule` TR-5.4: Variáveis de ambiente (ex: `OPENAI_API_KEY`) não aparecem hardcoded no código, só via `PydanticSettings`

---

## Task 6: FASE 6 — Observabilidade (logs estruturados JSON + auditoria persistida + correlação)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - **Sinal 1 — Logs estruturados**: `src/observability/logging.py` configura `python-json-logger` com filtro para injetar `execution_id` por contexto (context vars). Campos mínimos: `ts, level, logger, execution_id, node, event, decision, tool, error, duration_ms`.
  - **Sinal 2 — Auditoria**: `src/observability/audit.py` classe `AuditLog.append(execution_id, etapa, payload_hash, antes, depois, decision, adversarial, approver)`. Escreve `STORAGE_PATH/audit_events.jsonl` em append (JSON Lines).
  - Decorator `@trace_node` que: mede duração, loga "node_started / node_finished", grava `audit.append`.
  - Aplicar `@trace_node` a todos os 9 nós do grafo e à tool.
  - `GET /incidents/{execution_id}/trace` endpoint: une S1 + S2 para aquele `execution_id` e retorna timeline.
- **Acceptance Criteria Addressed**: AC-5, AC-13 (parcial)
- **Test Requirements**:
  - `rule` TR-6.1: Execução de fluxo completa gera ≥ 1 entrada de log por nó em S1
  - `rule` TR-6.2: Mesma execução gera ≥ 1 entrada por etapa em S2 (`audit_events.jsonl`)
  - `rule` TR-6.3: Filtrando por um `execution_id` em ambos os arquivos, obtém-se a cadeia completa sem quebras
  - `rule` TR-6.4: Endpoint `/trace` retorna timeline com durações e decisões

---

## Task 7: FASE 7 — Resiliência (timeout, retry, fallback)
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 3
- **Description**:
  - Reforçar: timeout=5s na tool e também nas chamadas ao LLM (configurar `timeout` no cliente `langchain-openai`).
  - Mesma política de retry 3x com exponencial para LLM; fallback: se LLM falhar, usar modelo de regras determinístico para classificação/prioridade (menos preciso, mas fluxo não quebra). Sinalizar `llm_fallback=true` no state.
  - Nenhum `while True` sem break. `MAX_STEPS` verificado no início de cada nó via `@trace_node` (early-stop).
- **Acceptance Criteria Addressed**: AC-15
- **Test Requirements**:
  - `rule` TR-7.1: Chamada LLM simulada falhando → fallback determinístico é acionado (campo `llm_fallback=true` no state)
  - `rule` TR-7.2: Nenhum loop sem condição de saída clara em análise estática (grep `while True` / `for`)

---

## Task 8: FASE 8 — QA (testes, code review IA, testes gerados por IA, priorização)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 2, Task 3, Task 4, Task 5, Task 6
- **Description**:
  - Escrever testes manuais:
    - `tests/unit/`: `test_errors.py`, `test_validator.py`, `test_autonomy.py`, `test_observability.py`.
    - `tests/integration/test_graph.py`: executa grafo com state tipado.
    - `tests/e2e/test_api_happy.py`: Cenário 1 (happy path).
    - `tests/e2e/test_api_risky.py`: Cenário 2 (alto risco + injection).
    - `tests/adversarial/test_injection.py`: 3 variações de injection (leak instruções, chave falsa, prioridade forçada).
  - **Geração / refinamento por IA**:
    - Executar prompt documentado para LLM gerar `tests/adversarial/test_injection_extras.py` com pelo menos 4 novos casos edge. Salvar prompt em `docs/prompts/qa_gerar_testes.md`.
  - **Code review por IA**:
    - Aplicar prompt ao diff do commit `feat: implementa tool` (Task 3). Análise aponta pelo menos 1 problema/risco e 1 oportunidade. Salvar em `docs/qa/code_review_tool.md`.
  - **Priorização por risco**:
    - Marcar `tests/adversarial/test_injection.py::test_injection_leak_and_priority` como TESTE PRIORITÁRIO. Justificar em `docs/qa/teste_prioritario_justificativa.md` (risco = segurança/integridade; impacto = alto; criticidade = crítico).
- **Acceptance Criteria Addressed**: AC-7, AC-8, AC-3, AC-4
- **Test Requirements**:
  - `rule` TR-8.1: Pelo menos 1 teste de cada tipo (unit, integration, e2e, adversarial) existe e executa
  - `rule` TR-8.2: Arquivo `docs/prompts/qa_gerar_testes.md` existe e `tests/adversarial/test_injection_extras.py` executa
  - `rule` TR-8.3: Arquivo `docs/qa/code_review_tool.md` existe com ≥ 1 problema e ≥ 1 sugestão
  - `rule` TR-8.4: Justificativa de teste prioritário documentada e teste passa
  - `rubric` TR-8.5: Cobertura e diversidade de casos; escala 0-5; âncoras 1=apenas happy / 3=razoável / 5=cobre edge adversário, falha de tool, risco, paralelismo, memória; threshold ≥ 4; evidência = relatório coverage + inspeção

---

## Task 9: FASE 9 — DevOps (lint, testes, build simulado, pipeline, logs, anomalia, tendência)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1, Task 8
- **Description**:
  - **Pipeline GitHub Actions `.github/workflows/ci.yml`**:
    - Trigger em push `develop` e PRs → jobs: lint → test → build-validate.
    - `lint`: `ruff check .`
    - `test`: instala dependências, roda `pytest --cov=src --cov-report=xml --cov-report=html`, publica `coverage` em artefatos.
    - `build-validate`: `python -m compileall src tests` + `python -c "import app"` smoke check.
  - **Script local `scripts/ci.ps1`**: replica os 3 passos.
  - **Análise de logs por IA**:
    - Coletar logs reais ou simulados de 2 etapas: (a) lint; (b) testes. Prompt LLM documentado explica logs, identifica problemas, interpreta comportamento. Salvar em `docs/evidencias/analise_logs_pipeline.md`.
  - **Anomalia**:
    - Durante execução do Cenário 2, a tool falha repetidamente. Gerar relatório `docs/evidencias/anomalia.md` com: sinal observado (↑ erro tool em 5min), dados (contador=3 falhas), análise, explicação (timeout/falta rede), conclusão.
  - **Tendência / Risco**:
    - Dados de ≥ 5 execuções documentadas (podem ser simulados **declarados explicitamente como simulados**). Aplicar método simples (taxa de erro em rolling window 5). Gerar `docs/evidencias/tendencia_risco.md` com dados, método, resultado, interpretação, justificativa. Declarar se dados são simulados.
- **Acceptance Criteria Addressed**: AC-6, AC-9, AC-10
- **Test Requirements**:
  - `rule` TR-9.1: `scripts/ci.ps1` executa com return code 0 (lint / tests / build-validate)
  - `rule` TR-9.2: `.github/workflows/ci.yml` sintaxe YAML válida (validação local ou yamllint)
  - `rule` TR-9.3: Arquivos `analise_logs_pipeline.md`, `anomalia.md`, `tendencia_risco.md` existem em `docs/evidencias/` e preenchidos
  - `rule` TR-9.4: Dados de tendência claramente rotulados como SIMULADOS ou REAIS

---

## Task 10: FASE 10 — Low-code / No-code (n8n webhook trigger → integração → saída observável)
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 2, Task 6
- **Description**:
  - `src/lowcode/n8n_client.py`: `post_webhook(payload) → Response` usa `httpx` com timeout 10s; se `N8N_WEBHOOK_URL` vazia → log warning e continua (não falha).
  - Nó `emit_output` chama `post_webhook(output_dto)` apenas quando `risk_level in {moderado, alto}` OU `priority in {P1,P0}`.
  - Configuração: `N8N_WEBHOOK_URL` em `.env.example`.
  - Documentar passo-a-passo reproduzível no README seção "Low-code / No-code":
    1. Iniciar n8n local (`docker run ... n8nio/n8n`)
    2. Criar workflow → nó **Webhook trigger** (POST) → copiar URL
    3. Adicionar nó **Execute Command** ou **Send Email (mock)** como saída observável
    4. Setar `N8N_WEBHOOK_URL` no `.env` e rodar Cenário 2
    5. Evidência: captura do recebimento no n8n
  - Salvar evidência de webhook recebido em `docs/evidencias/n8n_webhook.log` (ou screenshot path).
- **Acceptance Criteria Addressed**: AC-11
- **Test Requirements**:
  - `rule` TR-10.1: `emit_output` com risco alto dispara `post_webhook`; com risco baixo não dispara (verificado via mock client em teste)
  - `rule` TR-10.2: README contém passo a passo reproduzível da integração
  - `rule` TR-10.3: `docs/evidencias/n8n_webhook.log` existe com conteúdo

---

## Task 11: FASE 11 — Prompts (system prompts, regras, ciclo de refinamento antes/depois)
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 2
- **Description**:
  - `src/prompts/analyze_request.md` (system prompt carregável como string)
  - `src/prompts/classify_and_priority.md` (system prompt compartilhado ou 2 arquivos separados)
  - `src/prompts/evaluate_risk.md`
  - `src/prompts/finalize_normal.md`
  - Cada prompt contém: objetivo, restrições, formato de saída JSON estrito, proibições (ex: "nunca invente").
  - **Ciclo de refinamento documentado**:
    - Versão ANTES (`docs/prompts/evaluate_risk_v1.md`) não pede JSON estrito → teste gera saída markdown ocasional e parse falha.
    - Versão DEPOIS (`docs/prompts/evaluate_risk_v2.md`) adiciona: "RESPONDA APENAS JSON SEM ```json```; SCHEMA OBRIGATÓRIO: {risk_level, requires_approval, justification, meta}".
    - Justificativa + resultado em `docs/prompts/refinamento.md` (antes → problema → alteração → resultado: parse passa 10/10).
- **Acceptance Criteria Addressed**: AC-12, AC-13 (parcial)
- **Test Requirements**:
  - `rule` TR-11.1: Pelo menos 4 arquivos `.md` de prompt em `src/prompts/` são carregáveis
  - `rule` TR-11.2: `docs/prompts/refinamento.md` existe com antes/depois/justificativa/resultado
  - `rule` TR-11.3: Parse da saída JSON do evaluate_risk passa em ≥ 10 execuções (mock se LLM real)

---

## Task 12: FASE 12 — Documentação / README
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1–11
- **Description**:
  - Preencher `README.md` com TODAS seções obrigatórias especificadas no PDF (item 20): Descrição, Classificação, Arquitetura (diagrama Mermaid + LangGraph nodes/edges/rotas/paralelização/componentes), Tool, Memória/contexto, Segurança (.env.example, validações, autonomia, bloqueios, injection), Instalação (dependências, configuração, execução, testes), QA (code review, testes, priorização por risco), Observabilidade (logs, 2º sinal, correlação, investigação), DevOps (pipeline, logs, anomalia, tendência/risco), Low-code (trigger, integração, saída, reprodução), Cenários (principal, risco/falha/exceção), Refinamento (problema, alteração, justificativa, resultado), Limitações (limitações atuais e evoluções), Vídeo (link YouTube não listado / placeholder "A SER GRAVADO").
  - Incluir diagrama Mermaid do LangGraph.
- **Acceptance Criteria Addressed**: AC-13, AC-16, AC-17
- **Test Requirements**:
  - `rule` TR-12.1: Checklist manual de todas as seções do item 20 do PDF → 100% preenchidas (marcar "INFORMAÇÃO NÃO DEFINIDA NO ESCOPO" ou "A SER GRAVADO" quando aplicável)
  - `rule` TR-12.2: README contém diagrama Mermaid e diagrama renderiza
  - `rubric` TR-12.3: Clareza, completude e rastreabilidade do README; escala 0-5; âncoras 1=simplório / 3=médio / 5=exaustivo; threshold ≥ 4

---

## Task 13: FASE 13 — Evidências / docs organizados + matriz de rastreabilidade
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1–12
- **Description**:
  - Organizar `docs/` com:
    - `docs/prompts/` (todos prompts + refinamento)
    - `docs/qa/` (code review, justificativa teste prioritário)
    - `docs/evidencias/` (observabilidade, tool, adversarial, pipeline logs, anomalia, tendência, n8n, matriz.md)
  - Matriz `docs/evidencias/matriz.md` em formato Markdown: 5 colunas — **Requisito** (FR/NFR + item PDF), **Implementação** (arquivo + linha inicial), **Teste** (caminho teste), **Evidência** (caminho arquivo em docs), **Documentação** (README seção / docs).
  - Nenhum requisito marcado concluído sem evidência correspondente. Marcar "INFORMAÇÃO NÃO DEFINIDA NO ESCOPO" quando aplicável.
- **Acceptance Criteria Addressed**: AC-13, AC-17
- **Test Requirements**:
  - `rule` TR-13.1: Estrutura de pastas `docs/prompts`, `docs/qa`, `docs/evidencias` existe e tem arquivos
  - `rule` TR-13.2: Matriz de rastreabilidade tem ≥ 15 linhas (≥ por AC) e colunas preenchidas

---

## Task 14: FASE 14 — Validação Final (rodar tudo, checklist)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1–13
- **Description**:
  - Rodar `scripts/ci.ps1` completo (lint + tests + build).
  - Executar manualmente Cenário 1 e Cenário 2, capturar: (a) resposta HTTP; (b) logs; (c) arquivo auditoria; (d) state JSON por ID.
  - Endpoint `/trace` investiga um execution_id real.
  - Verificar checklist final baseado nos ACs:
    - LangGraph paralelo e condicional (AC-1)
    - Tool com retry/fallback (AC-2)
    - Injection bloqueado (AC-3)
    - Memória influencia risco (AC-4)
    - 2 sinais observabilidade (AC-5)
    - Pipeline passa (AC-6)
    - Code review IA (AC-7)
    - Testes IA + prioritário (AC-8)
    - Anomalia (AC-9)
    - Tendência/risco (AC-10)
    - n8n (AC-11)
    - Prompts + refinamento (AC-12)
    - README + matriz (AC-13)
    - AppError (AC-14)
    - Sem loops infinitos (AC-15)
  - Resultados de validação gravados em `docs/evidencias/validacao_final.md`.
  - Placeholder vídeo no README atualizado de "A SER GRAVADO" → link se fornecido, senão manter como "A SER GRAVADO" com observação.
- **Acceptance Criteria Addressed**: AC-1 até AC-17
- **Test Requirements**:
  - `rule` TR-14.1: `scripts/ci.ps1` retorna 0
  - `rule` TR-14.2: `docs/evidencias/validacao_final.md` existe com checklist dos ACs e status PASS / FAIL / BLOCKED
  - `rubric` TR-14.3: Fidelidade global do fluxo Entrada→Processamento→Agente→Decisões→Tools→Contexto→Validações→Saída→Observabilidade; escala 0-5; âncoras 1=cadeia quebrada / 3=parcial / 5=cadeia completa e rastreável; threshold ≥ 5
