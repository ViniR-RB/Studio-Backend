---
name: estruturar-site-modelo
description: Estrutura um site modelo de e-commerce em um tema Shopify reutilizável, preservando layout, responsividade, assets e comportamento enquanto separa conteúdo e identidade do produto.
disable-model-invocation: true
---

# Estruturar site modelo

Converta um site de referência em uma implementação Shopify reproduzível. Trate o modelo como **sistema**, não como uma página para copiar literalmente: extraia estrutura, tokens visuais, componentes, assets e interações; substitua apenas o conteúdo dependente do produto.

## Fonte atual

O modelo local fica em `site modelo/` e segue esta forma:

- `layout/theme.liquid`: documento HTML, metadados, preload da fonte, CSS global e scripts de tracking.
- `templates/index.json`: página inicial que monta uma única seção principal.
- `sections/powerflex-escada.liquid`: ponto de montagem do app, mapa `window.SG_ASSETS` e carregamento do JavaScript da página.
- `assets/`: fontes, ícones, logos, imagens de produto, avatares e provas sociais.
- `config/settings_schema.json`: configurações do tema.

Antes de editar, leia esses quatro arquivos e liste os assets existentes. O critério de conclusão desta etapa é ter um inventário de dependências: cada arquivo referenciado pelo tema ou seção existe, e cada grupo de assets tem uma finalidade identificada.

## Processo

1. **Mapeie o modelo.** Identifique a ordem das seções visíveis, hierarquia de conversão, navegação, CTA principal, provas sociais, FAQ, garantia, oferta, rodapé e estados mobile. Use o HTML/CSS/JS real como fonte; não deduza cores ou fontes pelo nome do produto.
2. **Separe invariantes.** Preserve composição, espaçamento, tipografia, contraste, estados de interação, acessibilidade, responsividade e regras de carregamento. Marque como variável o nome, promessa, preço, imagens, depoimentos, reviews, garantia, pixel e links de checkout.
3. **Defina o contrato de conteúdo.** Organize variáveis por grupos: produto, oferta, benefícios, mídia, prova social, confiança, checkout e tracking. Toda variável deve ter fallback seguro ou ser obrigatória antes da publicação.
4. **Estruture o tema.** Mantenha `layout/`, `templates/`, `sections/`, `assets/` e `config/` no padrão Shopify. Prefira uma seção principal quando o modelo for uma landing page monolítica; divida em seções Shopify somente quando isso habilitar edição real, repetição ou configuração sem duplicar markup.
5. **Reaproveite assets com intenção.** Preserve nomes e caminhos quando a imagem continuar semanticamente válida. Para outro produto, troque imagens e textos correspondentes sem reutilizar depoimentos, claims ou fotos que possam sugerir experiência inexistente.
6. **Isole integrações.** Tracking, checkout, URLs externas e scripts de terceiros ficam em pontos explícitos. Não invente IDs, eventos ou credenciais. Se o valor não estiver disponível, deixe configuração pendente e informe isso.
7. **Implemente a menor mudança.** Evite framework ou dependência nova se Liquid, CSS e JavaScript nativo resolvem. Não crie abstrações para uma única ocorrência.
8. **Verifique o resultado.** Confirme que todos os assets referenciados existem, que o template renderiza sem placeholders não resolvidos, que a página possui título, CTA, imagens com `alt`, foco visível e layout funcional em viewport estreito e largo. Registre falhas reais em vez de afirmar que foram corrigidas.

## Regras de decisão

- **Fidelidade antes de criatividade:** copie a geometria e o comportamento do modelo; altere identidade e conteúdo de forma deliberada.
- **Dados antes de markup:** se um bloco é repetível ou configurável, modele seu conteúdo antes de duplicar HTML.
- **Uma fonte de verdade:** cada asset, token e variável deve ser definido uma vez e referenciado onde necessário.
- **Conversão sem engano:** preserve urgência, preço, garantia e depoimentos apenas quando forem fornecidos e verificáveis no briefing.
- **Mobile é caminho principal:** trate empilhamento, CTA fixo, tamanho de toque, legibilidade e carregamento de mídia como requisitos, não como acabamento.
- **Pronto significa publicável:** não encerre com arquivo parcial, referência quebrada, placeholder, evento de tracking inventado ou dependência ausente.

## Formato de entrega

Ao terminar, informe somente:

1. arquivos criados ou alterados;
2. estrutura preservada e conteúdo tornado variável;
3. verificação executada e qualquer pendência concreta.

Se o pedido for apenas análise, não edite o tema: entregue o inventário e o contrato de conteúdo proposto.
