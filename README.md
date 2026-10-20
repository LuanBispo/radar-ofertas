# 📊 Radar de Ofertas Tech

Todo dia às 8h, este robô procura na **Shopee** os produtos de tecnologia mais
baratos (ESP32, Arduino, sensores, kits educacionais e automação residencial),
de vendedores do Brasil e com boa comissão de afiliado, e publica tudo numa página:

👉 **https://luanbispo.github.io/radar-ofertas/**

Os links da página já são links de afiliado.

## O que aparece na página
- **🆕 Novidades**: produtos que surgiram hoje
- **📉 Quedas de preço**: queda de 10% ou mais desde ontem
- **Mais baratos de cada categoria**, com preço, comissão e quanto você ganha por venda

O arquivo `.csv` de cada dia (pasta `reports/`) tem a lista completa e abre no Excel.

## Como ligar (uma vez só)
1. Pegue o **AppID** e a **Senha** da API no painel de afiliados da Shopee (menu *Open API*).
2. Aqui no GitHub, vá em **Settings → Secrets and variables → Actions → New repository secret** e crie:
   - `SHOPEE_APP_ID` com o AppID
   - `SHOPEE_SECRET` com a Senha
3. Vá em **Actions → Radar de Ofertas Tech → Run workflow** para rodar na hora.

As chaves ficam num cofre secreto: ninguém vê, nem quem abre este projeto.

## Opcional: receber também por e-mail
Crie os secrets `SMTP_USER` (o Gmail que envia), `SMTP_PASSWORD` (senha de app do Gmail)
e `EMAIL_TO` (quem recebe; vários separados por vírgula).

## Personalizar
- **O que pesquisar**: edite a lista `buscas` no `config.yaml` (clique no arquivo e no lápis ✏️).
- **Comissão mínima, faixa de preço, palavras proibidas**: seção `filtros` do `config.yaml`.
- **Horário**: linha `cron` em `.github/workflows/radar-diario.yml`. O número da hora está em UTC,
  3 horas à frente de Brasília: `11` = 8h, `14` = 11h, `21` = 18h.

## Testar sem a chave da Shopee
Em **Actions → Radar de Ofertas Tech → Run workflow**, marque **Modo teste**.
A página mostra produtos de exemplo, só para conferir o visual.

## Mercado Livre e Amazon
Já estão preparados no código, mas desligados:
- **Amazon**: a API só é liberada depois de 3 vendas em 180 dias como associado.
- **Mercado Livre**: precisa criar um aplicativo em developers.mercadolivre.com.br.
  O ML não gera link de afiliado pela API, então os links precisam ser convertidos na barra de afiliados.
