# Ativa Command Center

Dashboard operacional da Ativa Logística com backend Python/FastAPI, frontend
React/Node, gráficos ECharts e chat em linguagem natural.

## O que está incluído

- **Visão geral:** conhecimentos, entregas, SLA, receita, tendência, pendências,
  filiais e estados.
- **Operações:** volume, peso, horários, rotas e desempenho por filial.
- **Entregas:** evolução do SLA, faixas de atraso, ocorrências e cidades.
- **Receita & clientes:** receita, ticket médio, segmentos e maiores pagadores.
- **Frota:** manifestos, veículos, motoristas, rotas e custos do relatório 220.
- **Fontes de dados:** monitoramento do PostgreSQL e das cinco pastas do BI2.
- **Pergunte aos dados:** transforma perguntas em consultas SQL seguras, executa
  em modo somente leitura e apresenta resposta, tabela e gráfico.

Os indicadores usam o PostgreSQL do SSW. A tela de frota também lê o CSV mais
recente de custos de transferência no SFTP, sem modificar os arquivos remotos.

## Executar

1. Instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   cd frontend
   npm install
   cd ..
   ```

2. Copie `.env.example` para `.env` e preencha as credenciais do BI e BI2.

3. Inicie os dois serviços:

   ```powershell
   .\run_dashboard.ps1
   ```

4. Abra [http://localhost:5173](http://localhost:5173).

A documentação interativa da API fica em
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Chat em linguagem natural

Sem `OPENAI_API_KEY`, o analisador local responde às perguntas operacionais mais
comuns sobre SLA, atrasos, receita, clientes, filiais, rotas e frota. Para
perguntas livres, preencha `OPENAI_API_KEY` e, se necessário, altere
`OPENAI_MODEL`.

Toda consulta gerada passa por validação de sintaxe, lista de tabelas permitidas,
bloqueio de campos sensíveis, limite de linhas, timeout e transação de banco em
modo somente leitura. A interface permite inspecionar o SQL executado.

## Testes rápidos

```powershell
python testar_conexao.py
python -m unittest discover -s backend/tests -v
cd frontend
npm run build
```
