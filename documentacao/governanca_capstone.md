# Governança de Desenvolvimento — Projeto Capstone

## 1. Objetivo

Este documento define como as alterações do projeto Hyperautomation devem ser planejadas, implementadas, revisadas e integradas durante o Capstone.

O processo deve garantir:

- rastreabilidade entre issue, branch, commit e Pull Request;
- revisão por outro integrante;
- proteção das branches de integração e produção;
- execução obrigatória dos testes;
- histórico de mudanças compreensível;
- ausência de credenciais e dados sensíveis no repositório.

## 2. Branches permanentes

| Branch | Finalidade | Recebe alterações por |
|---|---|---|
| `main` | Versão estável e demonstrável | PR vindo de `develop/capstone` |
| `develop/capstone` | Integração das issues do projeto final | PR vindo de branch específica |

Não é permitido desenvolver diretamente em `main` ou `develop/capstone`.

## 3. Branches temporárias

| Prefixo | Uso | Exemplo |
|---|---|---|
| `feature/` | Nova funcionalidade | `feature/capstone-bot-desktop` |
| `fix/` | Correção de defeito | `fix/capstone-timeout-desktop` |
| `test/` | Testes e evidências | `test/capstone-simulacao-crise` |
| `docs/` | Documentação | `docs/capstone-governanca` |
| `refactor/` | Refatoração sem mudar comportamento | `refactor/capstone-resiliencia` |
| `ci/` | Integração contínua | `ci/capstone-evidencias` |
| `chore/` | Manutenção e release | `chore/capstone-release` |

Cada branch temporária deve tratar somente uma issue ou um objetivo claramente delimitado.

## 4. Fluxo obrigatório

1. Atualizar `develop/capstone`.
2. Criar uma branch específica a partir dela.
3. Implementar código e testes da issue.
4. Executar as validações locais.
5. Criar commits semânticos.
6. Enviar a branch para o repositório remoto.
7. Abrir PR para `develop/capstone`.
8. Solicitar revisão do outro integrante.
9. Corrigir os apontamentos da revisão.
10. Fazer merge somente com CI aprovada e aceite do revisor.
11. Excluir a branch temporária após o merge.

Exemplo:

```bash
git switch develop/capstone
git pull origin develop/capstone
git switch -c feature/capstone-bot-desktop
```

## 5. Rastreabilidade da issue

Toda alteração deve possuir:

- issue com objetivo e critérios de aceite;
- branch específica;
- commits relacionados ao objetivo;
- PR com `Closes #NUMERO` ou `Refs #NUMERO`;
- testes e evidências informados no PR.

Use `Closes` quando o merge concluir completamente a issue. Use `Refs` quando o PR representar somente uma parte dela.

Exemplo de título:

```text
feat: implementar coleta desktop do Capstone
```

Exemplo no corpo do PR:

```text
Closes #135
```

## 6. Commits semânticos

Formato:

```text
tipo: descrição curta no infinitivo
```

| Tipo | Quando utilizar | Exemplo |
|---|---|---|
| `feat` | Nova funcionalidade | `feat: implementar coleta do portal` |
| `fix` | Correção de defeito | `fix: preservar task id do predecessor` |
| `test` | Criação ou ajuste de teste | `test: cobrir timeout da coleta desktop` |
| `docs` | Documentação | `docs: definir arquitetura do capstone` |
| `refactor` | Mudança interna sem novo comportamento | `refactor: separar adaptador do maestro` |
| `ci` | Pipeline de integração contínua | `ci: publicar evidencias de crise` |
| `chore` | Manutenção técnica | `chore: preparar release do capstone` |

Regras:

- escrever uma descrição objetiva;
- evitar mensagens como `ajustes`, `correção`, `teste` ou `a` sem contexto;
- não misturar várias issues independentes no mesmo commit;
- não incluir arquivos gerados, credenciais ou alterações de IDE sem necessidade;
- corrigir o commit antes do push quando ele contiver segredo ou arquivo indevido.

## 7. Pull Requests

Todo PR deve informar:

- issue relacionada;
- contexto do problema;
- objetivo da mudança;
- alterações realizadas;
- itens fora do escopo;
- comandos utilizados na validação;
- resultado dos testes;
- evidências relevantes;
- riscos e impactos conhecidos.

O autor não deve aprovar o próprio PR como única revisão. O outro integrante deve verificar o código e os critérios de aceite.

## 8. Responsabilidades

### Autor

- manter a branch atualizada;
- implementar somente o escopo da issue;
- adicionar ou atualizar testes;
- executar as validações locais;
- revisar o próprio diff antes do push;
- responder aos comentários do revisor;
- garantir que o PR não exponha segredos.

### Revisor

- comparar a implementação com os critérios da issue;
- verificar clareza e responsabilidade do código;
- confirmar tratamento de falhas;
- conferir os testes e evidências;
- verificar alterações fora do escopo;
- aprovar ou solicitar mudanças com justificativa técnica.

## 9. Critérios para merge

Um PR somente pode ser integrado quando:

- [ ] está direcionado para a branch correta;
- [ ] possui issue relacionada;
- [ ] não contém conflito;
- [ ] recebeu revisão do outro integrante;
- [ ] todos os comentários obrigatórios foram resolvidos;
- [ ] os testes locais passaram;
- [ ] o GitHub Actions passou;
- [ ] a documentação foi atualizada quando necessário;
- [ ] não contém credenciais ou dados sensíveis;
- [ ] atende aos critérios de aceite da issue.

O método recomendado é **Squash and merge** quando a branch possui commits intermediários que não acrescentam valor ao histórico. O título final deve seguir o padrão de commit semântico.

## 10. Proteção das branches

Configuração recomendada para `main` e `develop/capstone`:

- exigir Pull Request antes do merge;
- exigir pelo menos uma aprovação;
- invalidar aprovação quando houver novos commits relevantes;
- exigir resolução das conversas;
- exigir aprovação dos status checks do CI;
- impedir force push;
- impedir exclusão da branch;
- aplicar as regras aos administradores quando possível.

A branch `main` deve aceitar somente PR originado de `develop/capstone`, salvo hotfix documentado.

## 11. Hotfix

Um hotfix somente deve ser criado para defeito urgente na versão estável.

Fluxo:

```text
main → fix/nome-do-problema → main
```

Depois do merge na `main`, a mesma correção deve ser integrada em `develop/capstone` para evitar regressão futura.

## 12. Testes obrigatórios

Durante o desenvolvimento, execute primeiro os testes diretamente relacionados à issue.

Exemplo:

```bash
python -m pytest tests/unit/test_arquivo_alterado.py -q
```

Antes do PR, execute a suíte compatível com a mudança:

```bash
python -m pytest -q
```

Para mudanças exclusivamente documentais:

```bash
git diff --check
```

O CI continua sendo obrigatório mesmo quando os testes locais passam.

## 13. Evidências

Quando a issue tratar de integração, falha controlada ou automação visual, o PR deve incluir ou indicar:

- log estruturado;
- relatório gerado;
- arquivo JUnit;
- screenshot;
- artefato do orquestrador;
- IDs utilizados na rastreabilidade;
- comando de reprodução.

Evidências não podem expor token, senha, email secreto, cookie, chave de API ou conteúdo pessoal.

## 14. Segredos e variáveis de ambiente

- O arquivo `.env` não deve ser versionado.
- O `.env.example` deve possuir apenas nomes e valores fictícios.
- Tokens revogados não devem permanecer em documentação ou logs.
- Segredos do CI devem ser configurados em GitHub Secrets.
- Segredos dos bots devem ser configurados no ambiente autorizado do runner.
- O revisor deve procurar alterações suspeitas antes de aprovar.

Comando auxiliar:

```bash
git diff --cached
```

## 15. Versionamento e release

O projeto utiliza versionamento semântico:

```text
MAJOR.MINOR.PATCH
```

- `MAJOR`: mudança incompatível na arquitetura ou nos contratos públicos;
- `MINOR`: nova funcionalidade compatível;
- `PATCH`: correção compatível.

Toda release deve atualizar `CHANGELOG.MD` e corresponder a um commit validado da `main`.

## 16. GitHub, GitLab e The DX Way

O desenvolvimento atual ocorre no GitHub. Como o enunciado menciona GitLab/The DX Way, a equipe deve confirmar formalmente com o professor se:

1. o histórico e os PRs do GitHub serão aceitos; ou
2. será necessário espelhar ou migrar o repositório para o GitLab institucional.

Até existir confirmação, não se deve declarar esse requisito como concluído. Se houver migração, devem ser preservados commits, branches, tags e evidências de revisão sempre que possível.

## 17. Definition of Done

Uma issue está concluída quando:

- [ ] o objetivo foi implementado;
- [ ] todos os critérios de aceite foram comprovados;
- [ ] os testes foram criados ou atualizados;
- [ ] as validações passaram;
- [ ] a documentação necessária foi atualizada;
- [ ] o PR foi revisado por outro integrante;
- [ ] o CI foi aprovado;
- [ ] o merge ocorreu na branch correta;
- [ ] a issue foi encerrada pelo PR;
- [ ] a branch temporária foi removida.

