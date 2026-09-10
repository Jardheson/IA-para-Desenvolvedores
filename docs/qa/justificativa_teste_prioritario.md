# Justificativa do Teste Prioritário por Risco

## 1. Teste selecionado

- **Arquivo**: `tests/adversarial/test_injection.py`
- **Caso**: `test_injection_leak_and_priority` — concretizado por 4 funções complementares:
  1. `test_adversarial_leak_instructions_detection_and_blocks_approval` — L39-51
  2. `test_adversarial_reveal_secret_key_none_in_secrets_fields` — L54-68
  3. `test_adversarial_force_low_priority_is_detected_and_blocked` — L71-85
  4. `test_adversarial_all_assertions_hold_combined` — L88-111

## 2. Por que esse é o teste prioritário (risco máximo)

A prioridade de testes segue uma ordem canônica de risco:

```
Risco = (Impacto de falha) × (Probabilidade de ocorrer) × (Dificuldade de detecção manual)
```

### 2.1 Impacto de falha — CATEGORIA MÁXIMA

Se esse teste falhar, qualquer dos cenários abaixo é real:

| Sub-caso | Impacto se falhar |
|---|---|
| (1) leak instructions | O agente repete seu system prompt / regras internas → atacante mapeia como contornar proteções em segundos. |
| (2) reveal secret key | Credenciais / tokens / senhas vazam na resposta externa → violação de dados, vazamento de API key, conta comprometida. |
| (3) force low priority | Incidente P0/P1 de Integridade é classificado como P4 → ação automática deleta dados de produção sem aprovação. |
| (4) combinado | Todos os acima simultaneamente (pior caso típico de ataque real). |

Estes são os **3 riscos de maior impacto** do produto inteiro:
- **Segurança** (vazamento de credenciais) → impacto irreversível.
- **Integridade de dados** (ação destrutiva liberada sem aprovação) → perda de dados de produção.
- **Confidencialidade** (exfiltração de system prompts) → permite ataque direcionado ainda mais forte.

Nenhum outro teste (E2E happy path, tool retry, memória, observabilidade) tem impacto equivalente. Todos eles, se falharem, são reversíveis (relançar pipeline, restaurar log, etc.).

### 2.2 Probabilidade de ocorrência — MÉDIO-ALTA

- Prompt injection é o ataque mais comum contra aplicações LLM.
- A entrada é **texto livre** (`description: str`, até 5000 chars).
- Relatórios de OWASP LLM Top 10 2025 colocam "Prompt Injection" como #1.
- Atacante não precisa de credencial válida: `POST /incidents` é um endpoint público de suporte.

### 2.3 Dificuldade de detecção manual — MÁXIMA

- QA humano não detecta injection sem testes explícitos: o output parece "natural" quando o modelo segue a instrução injetada.
- Logs estruturados *mostram* a flag `adversarial=true`, mas só se o validador pegar. Se o validador falhar, nada no log mostra o vazamento até que alguém leia o corpo da resposta.
- Revisão de código não pega: é uma falha de *comportamento* do LLM + regras de validação, não de sintaxe.

## 3. Matriz de priorização comparativa

| Teste | Impacto | Probabilidade | Detecção manual | Prioridade |
|---|---|---|---|---|
| `test_injection.py::*` (nosso escolhido) | 10/10 | 7/10 | 1/10 | **7.0 — MÁXIMA** |
| `test_api_risky.py::test_post_incidents_risky` | 7/10 | 5/10 | 5/10 | 2.45 |
| `test_graph.py::test_run_triage_sync_history_refs` | 4/10 | 4/10 | 3/10 | 0.48 |
| `test_autonomy.py::test_*` | 5/10 | 3/10 | 4/10 | 0.60 |
| `test_api_happy.py::test_health_returns_200` | 1/10 | 1/10 | 9/10 | 0.01 |

## 4. Por que não os outros testes como prioritários?

- **Testes unitários de autonomia (`test_autonomy.py`)**: Testam apenas a regra *depois* que o injection é detectado. Se o injection não for detectado, as regras de autonomia nunca disparam.
- **E2E risky (`test_api_risky.py`)**: O payload de teste é um incidente de alto risco "legítimo" (DROP tabela), não contém tentativa de subverter o agente. É ortogonal.
- **Integração grafo + memória**: Falhas de memória significam que o risco pode não ser *escalonado*, mas nunca que o risco alto seja *reduzido* a ação automática sem aprovação. Menor dano.
- **Health check**: É um smoke test. Se falhar, nada funciona; mas se passar, não protege contra ameaças.

## 5. Este teste cobre 3 ACs simultaneamente

| AC | Como é coberto |
|---|---|
| **AC-3** (Bloqueio e detecção de prompt injection) | Assert direto: `adversarial_detected=True`, `requires_approval=True`, `status=BLOQUEADO_PENDENTE_APROVACAO`. |
| **Segurança geral do AC-1** (estado tipado / LangGraph) | Assegura que branches críticos do grafo (evaluate_risk → finalize_risky → emit_output) sejam percorridos mesmo com entrada adversarial. |
| **AC-5** (Observabilidade: 2 sinais correlacionados) | Se o teste passar, o `audit_events.jsonl` marca `adversarial=true` e o `triagem.log` registra `decision=requires_approval=True` — ambos pelo mesmo `execution_id`. |

## 6. Critérios de aceitação do teste prioritário

- **Green CI**: `pytest tests/adversarial/test_injection.py -v` deve passar em 100% das builds no `main` e `develop`.
- **Sem mute/mark skip**: Nunca marcar com `@pytest.mark.skip` por conveniência. Se a flag for desativada, criar um `ADVERSARIAL_ENABLED=false` explícito com justificativa.
- **Novo payload adicionado mensalmente**: Sempre que um novo padrão de injection for identificado, adicionar caso ao arquivo. Atualmente cobrem 4 vetores: `_LEAK_INSTRUCTIONS`, `_REVEAL_SECRET_KEY`, `_FORCE_LOW_PRIORITY`, `_COMBINED`.

---

## 7. Decisão final

**Teste prioritário**: `tests/adversarial/test_injection.py` (os 4 subcasos juntos, formando o requisito de "não vazar, não reduzir prioridade, bloquear fluxo").

**Risco mitigado**: O maior risco do projeto — vazamento de credenciais + bypass de política de aprovação por prompt injection.
