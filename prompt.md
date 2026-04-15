Quero que você faça uma revisão profunda da pipeline de conversação do Telegram, porque o resultado atual está ruim e desalinhado com o projeto.

## Problemas observados no comportamento real

1. O bot está usando branding errado:

   - respondeu como “Clínica Minutare Med”
   - mas a clínica definida no env é `climesa`
   - isso prova que o runtime real não está respeitando a configuração da clínica
2. O fluxo conversacional está incoerente:

   - responde perguntas simples
   - depois dispara handoff automático sem necessidade
   - depois volta a responder
   - depois quebra de novo
3. O handoff está entrando em momentos errados:

   - perguntas comuns sobre convênio
   - fluxo simples de agendamento
   - continuidade multi-turn
4. O contexto da conversa está se perdendo:

   - “quero marcar para ortopedia”
   - “amanhã”
   - deveria continuar o fluxo de agenda
   - mas cai em encaminhamento
5. A experiência está fragmentada:

   - saudação parece vir de template antigo
   - especialidades vêm de uma fonte
   - convênios vêm de outra
   - handoff vem de outra regra
   - tudo parece pouco unificado

---

## Objetivo

Quero que você faça uma análise profunda da pipeline conversacional e depois a corrija para que o Telegram funcione como um atendimento de IA realmente coeso, natural e alinhado à clínica configurada.

---

## O que você deve investigar

### 1. Configuração da clínica no runtime real

Verifique por que o Telegram ainda está usando “Minutare Med” mesmo com `CLINIC_ID` e `CLINIC_NAME` definidos para `climesa`.

Quero descobrir:

- de onde esse nome está vindo
- qual prompt/template/config antiga ainda está ativa
- se o env está sendo ignorado
- se a config da clínica não está conectada ao pipeline real

---

### 2. Pipeline completa de resposta

Mapeie o fluxo real:

- mensagem recebida
- classificação de intenção
- leitura de contexto
- uso de pending_action
- consulta de dados da clínica
- consulta de convênios/especialidades
- builder final de resposta
- decisão de handoff

Quero saber exatamente onde o fluxo está se fragmentando.

---

### 3. Handoff

Revise profundamente a política de handoff.

Quero que o sistema:

- não faça handoff em perguntas simples
- não faça handoff em multi-turn normal
- não use handoff como fallback padrão

Quero handoff apenas quando houver motivo real e explícito.

---

### 4. Multi-turn

Corrija o fluxo para que o contexto de agendamento continue corretamente.

Exemplo esperado:

- usuário: “quero marcar para ortopedia”
- IA: pede data
- usuário: “amanhã”
- IA: entende que isso é continuação e segue com disponibilidade

Sem resetar, sem cair em handoff.

---

### 5. Builder final

Quero que exista uma camada final unificada de resposta que combine:

- branding correto da clínica
- tom conversacional
- intenção
- contexto ativo
- estado da conversa
- política de handoff

Hoje parece que várias camadas respondem por conta própria. Isso precisa ser unificado.

---

### 6. Logs e diagnóstico

Adicione logs claros para mostrar:

- clínica carregada
- branding carregado
- intenção detectada
- pending_action atual
- fonte da resposta
- motivo do handoff
- se resposta veio de template, RAG, agenda ou fallback

---

## Entregas obrigatórias

Quero sua resposta final organizada assim:

### 1. Causa raiz dos problemas conversacionais

### 2. Por que a clínica errada apareceu

### 3. Onde a pipeline está fragmentada

### 4. Como o handoff foi corrigido

### 5. Como o multi-turn foi corrigido

### 6. Como a camada de resposta foi unificada

### 7. Arquivos alterados

### 8. Testes reais com exemplos de conversa

### 9. Commit e push
