# Nohemi — tipografia oficial Open Heavens

O Manual de Identidade da Open Heavens Church (p. 26) define a **Nohemi** (Pangram Pangram Foundry) como a família tipográfica da marca.

## Como instalar (self-host)

A Nohemi **não é distribuída via Google Fonts**. Para obter os ficheiros:

1. Compra ou descarrega gratuitamente (conforme a oferta vigente) a partir do site oficial:
   - https://pangrampangram.com/products/nohemi
2. Extrai e converte para `.woff2` se necessário (ex.: [transfonter.org](https://transfonter.org/)).
3. Coloca os ficheiros **neste diretório** com **exactamente** estes nomes:

```
Nohemi-Regular.woff2
Nohemi-Medium.woff2
Nohemi-SemiBold.woff2
Nohemi-Bold.woff2
```

Assim que os ficheiros existirem, o gerador do guia Open Groups inclui automaticamente os `@font-face` correspondentes no HTML/PDF. Sem eles, o guia faz fallback para **Space Grotesk** (Google Fonts, livre) e por fim **Inter** — ambas mantêm o ar moderno/ousado pedido pelo manual.

## Licença

A Nohemi tem licença própria (Pangram Pangram). **Não inclui os ficheiros `.woff2` no repositório público** — mantêm-se só na máquina que gera a entrega. O `.gitignore` do repo já ignora este diretório (excepto este README).

## Verificar que está a ser usada

Abre `entrega/<video_id>/guia_open_groups.html` no browser e inspecciona o `h1` da capa. Em "Computed → font-family" deve aparecer `Nohemi`. Se aparecer `Space Grotesk` ou `Inter`, confirma os nomes dos ficheiros neste diretório.
