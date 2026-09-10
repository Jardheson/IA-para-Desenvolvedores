# Análise de Tendência e Risco — Histórico de 5 Execuções (SIMULAÇÃO CONTROLADA)

> ⚠️ **Aviso:** Os dados abaixo são de **SIMULAÇÃO CONTROLADA**, gerados para fins de documentação de evidência e validação de regras de tendência. **Não correspondem a execuções reais de produção.**

---

## Tabela de Execuções Documentadas (n=5)

| execution_id  | risk_level | requires_approval | Cenário descritivo da execução                      |
|---------------|------------|-------------------|-----------------------------------------------------|
| EXEC-SIM-0001 | NORMAL     | ❌ False          | Sucesso padrão: incidente moderado, sem anomalias   |
| EXEC-SIM-0002 | NORMAL     | ❌ False          | Sucesso padrão: incidente de baixo impacto          |
| EXEC-SIM-0003 | ALTO       | ✅ True           | Incidente crítico P0: indisponibilidade DB produção |
| EXEC-SIM-0004 | ALTO       | ✅ True           | Incidente crítico P0: vazamento credenciais + adv   |
| EXEC-SIM-0005 | MODERADO   | ❌ False          | Incidente moderado P2: latência alta API gateway    |

---

## Cálculo de Tendência — Média Móvel 3 Janelas

**Método:** Média móvel de 3 observações deslizantes (rolling window = 3). Cada janela calcula a proporção de execuções de risco **ALTO com aprovação humana (`requires_approval=True`)**.

### Janela 1: EXEC-0001, EXEC-0002, EXEC-0003
- ALTO + requires_approval=True → 1 em 3
- Proporção W₁ = 1/3 ≈ **33,3%**

### Janela 2: EXEC-0002, EXEC-0003, EXEC-0004
- ALTO + requires_approval=True → 2 em 3
- Proporção W₂ = 2/3 ≈ **66,7%**

### Janela 3: EXEC-0003, EXEC-0004, EXEC-0005
- ALTO + requires_approval=True → 2 em 3
- Proporção W₃ = 2/3 ≈ **66,7%**

---

## Estimativa de Tendência para Próximas 3 Execuções

| Métrica                                                        | Valor |
|----------------------------------------------------------------|-------|
| Média das proporções (W₁ + W₂ + W₃) / 3                        | (0,333 + 0,667 + 0,667) / 3 ≈ 0,556 → **55,6%** |
| Fator de decaimento bayesiano (suavização Laplace +2/+2)       | (2 + 2) / (5 + 4) ≈ 44,4% → correção para ~45% |
| **Estimativa final reportada**                                 | **45%** |

> **Probabilidade de nas próximas 3 execuções pelo menos uma entrar em risco ALTO com aprovação humana = 45%**  
> baseado em padrão 2/5 recentes e média móvel 3 janelas com suavização.

---

## Justificativa do Método

1. **Frequência bruta:** 2 de 5 execuções recentes = 40% de chance a priori.
2. **Média móvel 3 janelas:** mostra tendência ascendente — W₁=33% → W₂=67% → W₃=67% (série crescente, estabilizando no patamar alto).
3. **Suavização (Laplace +2/+2):** como n=5 é amostra pequena, aplica-se correção para não sobreajustar em eventos raros. Reduz de ~56% para **45%**, evitando overconfidence.
4. **Janela deslizante:** últimos 3 pontos pesam mais que os pontos mais antigos (EXEC-0001 já saiu da janela mais recente W₃).

---

## Matriz de Risco Estimado

| Cenário das próximas 3 execuções | Probabilidade acumulada | Interpretação |
|----------------------------------|-------------------------|---------------|
| **Nenhuma em ALTO+approval**     | (1-0,45)³ ≈ 16,6%       | Baixo         |
| **1 execução em ALTO+approval**  | C(3,1)·0,45·0,55² ≈ 40,8% | Médio      |
| **2 execuções em ALTO+approval** | C(3,2)·0,45²·0,55 ≈ 33,4% | Alto       |
| **3 execuções em ALTO+approval** | 0,45³ ≈ 9,1%            | Crítico      |

---

## Conclusão e Recomendações

**Interpretação:** A sequência EXEC-0003 e EXEC-0004 sendo ambas ALTO/P0 seguidas de MODERADO indica **tendência de alta volatilidade**. A chance de novas aprovações humanas no short term (próximas 3 execuções) é **material (45%)**, justificando preparo do time de SRE/Ops.

**Recomendações imediatas:**
1. 🔔 **Alertar fila de aprovação:** notificar time que fluxo de aprovação manual deve ser monitorado.
2. 🧪 **Reforçar testes de P0:** incluir mais edge cases em `tests/adversarial/` para risco ALTO.
3. 📊 **Ampliar amostra:** reexecutar análise quando n≥20 execuções, intervalo de confiança reduz.
4. ⚙️ **Revisar thresholds de autonomia:** considerar se MODERADO P2 deve também exigir aprovação em cenário de tendência ascendente.
