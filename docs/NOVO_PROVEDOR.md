# Como adicionar uma nova empresa/plataforma

O Radar foi feito para trocar de fonte sem mexer no resto. **Só entra uma fonte nova se houver API oficial, parceria ou autorização clara.** Não implemente scraping que viole termos de uso, burle bloqueios ou sobrecarregue o site.

## O contrato

Um provedor é uma classe com `nome` e o método `search(rota, dia) -> list[Trip]` (veja `radar/providers/base.py`):

```python
class MeuProvedor:
    nome = "meu"                      # vira Trip.fonte e aparece no histórico e no site

    def search(self, route, day):     # viagens daquele dia, para aquela rota
        origem, destino = route.ids_para("meu")   # ids que ESTA plataforma usa
        ...
        return [Trip(data=..., saida=..., preco=..., empresa="Viação X", origem=route.origem,
                     destino=route.destino, link="https://...", vagas=..., fonte="meu")]
```

Regras: levantar exceção em falha (o motor registra e segue); devolver só viagens com preço; `empresa` é a viação, `fonte` é a plataforma; usar cache e pausa se uma requisição trouxer várias datas (veja `BuserProvider`).

## Checklist

1. **Autorização:** existe API oficial, programa de afiliados/parceiros ou permissão por escrito? Registre aqui como obteve acesso.
2. **Termos e limites:** leia os termos de uso e os limites de requisição; configure uma pausa conservadora.
3. **Credenciais:** só por variável de ambiente ou secret do GitHub, nunca no repositório.
4. **Mapeamento:** de onde vêm data, horário, preço, vagas, empresa e link de compra.
5. **Registro:** adicione a classe em `radar/providers/__init__.py` (função `criar_provedor`) e tire o nome de `NAO_IMPLEMENTADOS`, se estiver lá.
6. **Rotas:** acrescente os ids da plataforma em `ids = { meu = { origem = "...", destino = "..." } }` na `[[rota]]`.
7. **Testes:** use respostas gravadas em `tests/fixtures/` (sem internet) e cubra falha, esgotado, mudança de formato e virada de ano.
8. **Ativação:** `nome = ["buser", "meu"]` em `[provedor]`.

## Situação das fontes

| Fonte | Situação |
|---|---|
| **Buser** | Implementada lendo páginas públicas de busca, sem API oficial confirmada. Vale consultar a Buser sobre parceria/afiliados para uma fonte estável. |
| **ClickBus** | **Não implementada.** Uma reportagem de 2023 indica que a ClickBus distribui seu inventário a parceiros comerciais (agências, plataformas) por API. Não encontrei documentação pública para desenvolvedores individuais. Seria preciso contato comercial para acesso, a documentação oficial e as credenciais; só então implementar. |
| Outras | Mesmo critério: sem API ou autorização, só fica o registro aqui. |
