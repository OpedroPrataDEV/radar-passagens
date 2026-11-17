# 🚌 Radar de Passagens

Projeto pessoal desenvolvido para resolver um problema comum: **encontrar passagens rodoviárias com preços acessíveis sem precisar pesquisar manualmente todos os dias.**

O Radar permite configurar uma rota, dias da semana e um preço máximo. A partir dessas informações, o sistema monitora as passagens disponíveis, identifica oportunidades e envia notificações quando encontra algo que atende aos critérios definidos.

Exemplo ilustrativo: Niterói → Cabo Frio, às quintas-feiras, com preço máximo de R$ 30.

```text
🚌 Niterói → Cabo Frio — até R$ 30,00

qui 19/11
  • 15:40  R$ 22,89  Expresso Demo

qui 26/11
  • 12:00  R$ 28,85  Viação Exemplo
```

*Os dados acima são demonstrativos.*

## Como funciona

```text
config.toml ─► datas da janela ─► provedor (consulta) ─► filtro (preço/horário/já saiu)
                                                              │
                                SQLite (histórico + "já avisei") ─► console / Telegram / e-mail
```

| Parte | Arquivo |
|---|---|
| Datas (todas as quintas dos próximos 30 dias) | `radar/dates.py` |
| Fontes de dados plugáveis (`buser`, `json`, `mock`) | `radar/providers/` |
| Busca + filtros, tolerante a falhas | `radar/core.py` |
| Histórico real de preços (JSON versionado) | `radar/registro.py` |
| Anti-repetição dos avisos | `radar/history.py` |
| Lógica do site (estatísticas e gráficos, testada) | `site/radar-core.js` |
| Avisos (terminal, Telegram, e-mail) | `radar/notifiers.py` |
| Automação diária | `.github/workflows/radar.yml` |

## Rodando

Precisa de Python 3.11+.

```bash
pip install -r requirements.txt
cp config.example.toml config.toml
python -m radar --datas      # mostra quais datas seriam consultadas
python -m radar              # consulta a Buser (use --provedor mock para dados de teste)
pytest                       # testes do robô (Python)
node --test tests/js/radar-core.test.js  # testes da lógica do site (Node 20+, sem dependências)
```

Opções úteis: `--tudo` (ignora o que já foi avisado), `--sem-aviso` (só imprime), `-v` (log detalhado).

## O site (Busão Barato)

A pasta `site/` contém um site estático: `index.html` + `dados.json`. Nele, o usuário pode escolher a rota, os dias da semana e o preço máximo para visualizar apenas as passagens que atendem aos filtros. O site também direciona o usuário à plataforma de origem para realizar a compra.

- **Dados:** o radar gera o `site/dados.json` e o `site/historico.json` (`python -m radar --exportar site/dados.json --historico site/historico.json`). O `dados.json` incluído no projeto contém dados de **demonstração**, coletados em 13/11/2026, e apresenta um aviso na interface até ser substituído por dados reais.
- **Atualização automática:** o workflow do GitHub Actions roda diariamente, atualiza o `dados.json` e faz commit. A hospedagem republica automaticamente a cada commit.
- **Publicar (Vercel):** envie o projeto para o GitHub, importe o repositório na Vercel e defina **Root Directory = `site`**. Não é necessário configurar um processo de build. O GitHub Pages também pode ser utilizado, publicando a pasta `site/`.
- **Coleta de dados:** por padrão, o robô coleta os sete dias da semana para alimentar o site (`dias_site = "todos"`), mas os avisos por Telegram/e-mail consideram apenas os dias definidos em `dias`. Cada dia da semana pode gerar uma requisição à Buser. Para reduzir as consultas, use `dias_site = ["quinta", "sexta"]`.
- Para monitorar a viagem de volta, adicione uma segunda configuração `[[rota]]` (Cabo Frio → Niterói) no `config.toml`.

## Histórico de preços

A cada execução, o robô registra **todas as passagens futuras encontradas**, não apenas as que estão abaixo do preço máximo, em `site/historico.json`. Esse arquivo é versionado no repositório e funciona como fonte do histórico. Para cada viagem, são armazenados os dias em que o preço mudou; o site reconstrói as informações restantes.

- No site: menor, média e maior preço registrados, última atualização, gráfico de **evolução no tempo** (menor preço disponível em cada dia de coleta, acompanhado da média) e, por passagem, um botão **Histórico** com a evolução daquela viagem e um indicador que compara o preço atual com os valores já registrados.
- **Nada é inventado.** A Buser informa o preço atual, não os preços passados. Portanto, o histórico só começa a existir a partir da primeira coleta. Com menos de três dias de coleta (ou cinco observações), o site apresenta a mensagem "coletando histórico" em vez de desenhar uma curva ou emitir uma avaliação.
- Para oferecer informações úteis desde o primeiro acesso, a aba **Hoje, por data** mostra o menor preço encontrado para cada data nos dados atuais. É um retrato da coleta mais recente, identificado como tal.
- Dados de demonstração nunca se misturam com o histórico real: o histórico é ignorado quando `demo` é verdadeiro, e executar com `--provedor mock` não grava dados. O único gráfico fictício é acessado pelo botão "Ver exemplo ilustrativo", disponível apenas na demonstração e identificado como **EXEMPLO ILUSTRATIVO**.
- Crescimento estimado: cerca de 100 KB por rota por ano. Viagens já realizadas são removidas depois de 365 dias.
- O SQLite (`radar.db`) armazena apenas o controle dos avisos enviados. Se o cache do GitHub Actions for apagado, o pior cenário é receber uma notificação repetida; o histórico de preços não depende desse banco.

## Filtros e personalização

No site, estão disponíveis filtros de origem, destino, dias da semana, preço máximo e faixa de horário. As escolhas ficam salvas **somente no navegador utilizado** (`localStorage`), e essa limitação é informada na própria interface.

- O site só apresenta rotas que o robô coleta. Para adicionar uma nova cidade, inclua uma configuração `[[rota]]` no `config.toml`. Cada rota pode gerar até sete requisições à Buser por execução.
- Alertas individuais por usuário, permitindo que cada pessoa escolha suas próprias rotas, exigiriam servidor, banco de dados, autenticação e cuidados com a LGPD, já que e-mails e identificadores do Telegram são dados pessoais. Para um projeto de uso pessoal, essa infraestrutura não faz parte do escopo atual.

## Várias empresas

O campo `Trip.fonte` (plataforma) é separado de `Trip.empresa` (viação). A configuração aceita uma lista de provedores (`nome = ["buser", "outra"]`) e cada rota pode ter identificadores específicos por fonte.

Atualmente, **somente a Buser está integrada**. Nenhuma outra empresa possui integração funcional no projeto. Consulte `docs/NOVO_PROVEDOR.md` para conhecer o contrato de implementação, o checklist e a situação de cada empresa, incluindo os motivos pelos quais a ClickBus ainda não foi integrada.

## Como ele lê a Buser

O provedor `buser` consulta as **páginas públicas de busca**, sem necessidade de login, e extrai do conteúdo de cada viagem informações como data, horário, preço e disponibilidade de vagas.

- `modo = "dia_da_semana"` (padrão): consulta uma página como `https://www.buser.com.br/onibus/quinta-feira/niteroi-rj/cabo-frio-rj`. Uma única requisição pode retornar as próximas semanas daquele dia. Assim, para uma janela de 30 dias, o radar pode realizar apenas uma requisição por rota. Os resultados ficam em cache durante a execução.
- `modo = "por_data"`: consulta uma página específica para cada data, utilizando o parâmetro `?ida=AAAA-MM-DD`.
- Se a página por dia da semana não existir (erro 404), o sistema tenta automaticamente utilizar a consulta por data.

**O que foi verificado e o que ainda precisa ser validado:**

| Item | Situação |
|---|---|
| Página por dia da semana (testada com `segunda-feira`) retorna aproximadamente 12 semanas com preços | ✅ Verificado em página real |
| Formato do texto de cada viagem (horário, data, duração, tipo de poltrona, preço e vagas) | ✅ Verificado em página real; o parser é testado com uma réplica em `tests/fixtures/` |
| Parâmetro de data `?ida=AAAA-MM-DD` | ✅ Identificado em endereços reais |
| Endereço da página de quinta-feira (`quinta-feira`) e dos demais dias (`terca-feira`, `sabado` etc.) | ⚠️ Deduzido do padrão; precisa ser conferido no navegador |
| Funcionamento a partir de um servidor (GitHub Actions) sem bloqueios | ⚠️ Ainda não testado; depende das condições de acesso da Buser |
| Disponibilidade do texto no HTML bruto, sem depender da renderização no navegador | ⚠️ Ainda não testado; se o conteúdo não estiver disponível, o robô poderá apresentar erro |

Antes de depender do sistema, execute uma vez no computador:

```bash
python -m radar --tudo -v
```

Compare os resultados obtidos com as informações exibidas no site da Buser.

**Se algo falhar:**

- "O layout mudou" significa que a Buser alterou a estrutura da página. Nesse caso, pode ser necessário ajustar `radar/providers/buser.py`.
- "Nenhuma viagem foi lida" significa que o conteúdo esperado não foi encontrado. Uma alternativa a investigar é utilizar `modo = "por_data"`.

## Provedor genérico `json` (alternativa)

O projeto também possui um provedor genérico para fontes que disponibilizem dados em JSON.

Para integrar outra plataforma, priorize uma API oficial, documentação pública ou uma fonte de dados cujo acesso seja expressamente autorizado.

Caso exista uma integração autorizada, configure a URL, os parâmetros e o mapeamento dos campos retornados de acordo com as instruções do README e a estrutura definida em `[provedor.json]`.

Não dependa de endpoints privados, não documentados ou de acesso restrito. A disponibilidade de uma fonte de dados precisa ser verificada antes de implementar uma integração.

## Avisos no celular

### Telegram (gratuito)

Para configurar notificações pelo Telegram:

1. Crie um bot utilizando o [@BotFather](https://t.me/BotFather).
2. Obtenha o token do bot.
3. Envie uma mensagem ao bot.
4. Descubra seu `chat_id`, por exemplo, utilizando o método `getUpdates` da API do Telegram.

Configure as variáveis de ambiente:

```bash
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
```

### E-mail

Para notificações por e-mail, configure as seguintes variáveis de ambiente:

```text
SMTP_HOST
SMTP_USER
SMTP_PASSWORD
SMTP_PORT (opcional)
EMAIL_TO (opcional)
```

**Importante:** nunca publique tokens, senhas ou credenciais no repositório. Utilize variáveis de ambiente e os recursos de gerenciamento de segredos da plataforma de hospedagem.

## Rodando sozinho todos os dias (GitHub Actions)

O projeto possui automação diária utilizando GitHub Actions.

Para configurá-la:

1. Envie o projeto para um repositório no GitHub.
2. Acesse **Settings → Secrets and variables → Actions**.
3. Configure os seguintes secrets, conforme necessário:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `RADAR_CONFIG_TOML` (conteúdo do seu `config.toml`)
4. O workflow está configurado para executar diariamente às 08:00 (horário de Brasília) e também permite execução manual pelo botão **Run workflow**.

Se todas as consultas falharem, por exemplo, devido a uma alteração no site da Buser, o job será marcado como falha no GitHub Actions.

## Decisões de projeto

Algumas decisões técnicas importantes adotadas durante o desenvolvimento:

- **Provedor plugável:** o restante do código não depende diretamente da Buser. Para adicionar uma nova fonte, basta implementar o contrato de consulta esperado pelo sistema.
- **Parser tolerante e verificável:** interpreta o texto visível da página, sem depender diretamente de classes CSS. Descarta passagens esgotadas, parcelas (como "3x R$") e viagens que cruzam a meia-noite, além de informar quando identifica alterações inesperadas no layout.
- **Falha parcial não derruba tudo:** um dia com erro não impede que as demais consultas sejam executadas. Apenas uma falha total provoca erro na execução.
- **Anti-repetição:** o sistema envia avisos apenas para passagens novas ou que ficaram mais baratas, evitando notificações repetitivas.
- **Gentileza com o site:** utiliza uma requisição por rota no modo padrão, cache durante a execução, intervalo entre consultas e novas tentativas com espera.
- **Testes sem internet:** o provedor `mock` permite testar o fluxo do sistema sem acessar serviços externos. O parser também é testado com respostas de exemplo.

## Ideias para evoluir

- Análises sobre o histórico de preços: em quais dias da semana e com qual antecedência aparecem as passagens mais baratas?
- Interface web para editar e cadastrar rotas.
- Integração com outras empresas, utilizando APIs oficiais, parcerias ou fontes de dados autorizadas.
- Notificações via WhatsApp utilizando a API oficial.

## Aviso

Projeto pessoal de estudo e experimentação, desenvolvido para monitoramento de passagens em baixo volume.

O funcionamento depende da disponibilidade e da estrutura das fontes consultadas. Antes de utilizar o sistema, confira os termos de uso da plataforma de origem e, sempre que disponível, prefira APIs oficiais ou programas de parceiros.