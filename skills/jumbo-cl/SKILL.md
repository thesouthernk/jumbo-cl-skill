---
name: jumbo-cl
description: Compra en jumbo.cl (supermercado Jumbo, Chile) con la cuenta del usuario — busca productos y compara precios, revisa sus compras anteriores y productos frecuentes, arma o repite el carro, detecta lo que falta y recomienda opciones más baratas, y lo deja listo para pagar. Úsala siempre que el usuario mencione Jumbo o jumbo.cl, el súper o supermercado, su pedido o compra del mes, "lo de siempre", repetir una compra, su carro, una lista de compras, ofertas, o cuánto cuesta algo — aunque no diga "jumbo.cl" explícitamente (ej. "ármame el pedido de siempre", "qué me falta en el carro", "cuánto sale la leche", "encuéntrame algo más barato").
---

# jumbo.cl

`<skill-dir>` = el directorio base de esta skill (se muestra al cargarla). Los scripts solo usan la stdlib de Python, salvo `jumbo_account.py`, que además necesita `playwright` (`pip install playwright`) y Google Chrome.

Jumbo (Cencosud) es un sitio Next.js. La página `https://www.jumbo.cl/busqueda?ft=<texto>&page=<n>` trae
40 productos por página con precios embebidos, así que buscar y comparar no necesita navegador ni login.

## Buscar y comparar precios

```bash
python3 -I <skill-dir>/scripts/jumbo_search.py "leche entera" [--pages 2] [--sort price|unit|discount]
```

Devuelve JSON, un objeto por SKU:

| campo | significado |
|---|---|
| `price` | precio actual (ya con oferta web) |
| `list_price` | precio normal si hay rebaja, si no `null` |
| `discount_pct` | % de rebaja vs `list_price` |
| `card_price` | precio con Tarjeta Cencosud (promo `TCENCO`), si existe |
| `unit_price` + `unit` | precio por lt/kg/un — **la métrica correcta para comparar formatos** |
| `in_stock` | disponibilidad online |
| `promos` | cabeceras de promo (`TMP OFERTA 4990`, `TCENCO OFERTA 11990`, …) |
| `url` | ficha del producto |

Cómo usarlo bien:

- **Compara por `unit_price`**, no por `price`: un pack de 12 parece caro y suele ser igual o más barato por litro. Usa `--sort unit`.
- **Revisa relevancia.** El buscador es difuso: "cerveza sol" trae también "Salchichón Cerveza Soler", y una búsqueda sin coincidencias devuelve productos al azar en vez de vacío. Filtra por nombre antes de concluir "el más barato es…".
- Descarta `in_stock: false` salvo que el usuario pregunte por ellos.
- Menciona `card_price` aparte: solo aplica pagando con Tarjeta Cencosud.
- Para una **lista de compras**, corre una búsqueda por ítem (en paralelo), elige el mejor match razonable por ítem (marca pedida si la hay, si no el menor `unit_price` en un formato sensato) y entrega una tabla con producto, formato, precio y subtotal, más el total. Di qué supuestos tomaste (marca, tamaño).
- Las ofertas cambian a fin de mes (el texto de las promos lo indica, ej. "29 SEP AL 26 OCT"). Los precios son los de la web en el momento de la consulta; pueden variar según tienda o comuna.

Si el script falla con "Sin resultados" para algo que claramente existe, puede que jumbo.cl haya cambiado su HTML.
Plan B: la página de búsqueda también trae un `<script type="application/ld+json">` con un `ItemList`
(nombre, marca, precio, url, disponibilidad), y si eso tampoco funciona, el navegador.

## Cuenta del usuario: compras anteriores y carro

```bash
A="python3 -I <skill-dir>/scripts/jumbo_account.py"
$A orders [--pages 3]     # pedidos (10 por página) con sus productos, sku y precio pagado
$A frequent [--pages 3]   # productos ordenados por cuántas veces los compra (+ cantidad promedio)
$A addresses              # direcciones guardadas, tienda que despacha a cada una y cuál usó la última vez
$A cart                   # carro actual: sku, cantidad, precio, stock, totales
$A missing [--min 2]      # productos que compra seguido y NO están en el carro
$A set 500=2 5870=1       # fija cantidades (no suma); 0 quita
$A repeat <ORDER_ID>      # suma al carro todos los productos de un pedido anterior
$A open [/mi-carro]       # muestra una página de jumbo.cl en su Chrome
```

Usa un Chrome normal con perfil propio (`~/.jumbo-cl/profile`, puerto 9333) y llama a la API web de Jumbo
desde una pestaña de jumbo.cl, con la sesión del usuario. El script abre Chrome si no está corriendo.
Si falla con "Sesión expirada" o los pedidos salen vacíos, corre `$A open /mis-compras` y pídele al usuario
que inicie sesión en esa ventana (Google funciona ahí porque no es un navegador automatizado). Tú no escribas credenciales.

`set` fija la cantidad final, así que para sumar lee el carro primero.

### Confirma la dirección antes de armar el carro

Al empezar a armar un pedido (antes del primer `set` o `repeat`), corre `addresses` y pregunta en una línea:
"¿Lo mando a **<alias o dirección con `last_used: true`>**, como la última vez?". Si tiene otras guardadas, menciónalas
como alternativa. Hazlo una vez por pedido, no en cada cambio del carro.

Esto importa porque la dirección decide la tienda (`store`), y los precios y el stock son por tienda: si arma el carro
para una dirección y despacha a otra, puede cambiar lo que hay y lo que cuesta. Usa siempre `--store <store de la
dirección elegida>` en `cart`, `set` y `missing` (por defecto se usa la tienda de su último pedido). Si la dirección
elegida tiene `delivers: false`, avísale que Jumbo no despacha ahí. Si quiere una dirección nueva, la agrega él
en el checkout de jumbo.cl.

### Flujos típicos

- **"Ármame el pedido de siempre"**: `frequent` → propón los que compra en ≥ ~1/3 de sus pedidos, con la cantidad promedio
  redondeada → muestra la lista y, cuando la apruebe, `set`. Las frutas y verduras a granel tienen cantidades en kg o
  unidades aproximadas; respeta lo que compró la última vez.
- **"Repite mi última compra"**: `orders --pages 1` → `repeat <id>` → `cart` para revisar stock.
- **"¿Me falta algo en el carro?"**: `missing`, y también `cart` para marcar los ítems con `status` distinto de `available`
  (sin stock) y sugerir un reemplazo con `jumbo_search.py`.
- **Mejores precios para su carro**: por cada ítem de `cart`, busca el nombre genérico con `jumbo_search.py --sort unit`
  y sugiere solo cambios razonables: mismo producto en otro formato más barato por unidad, una marca equivalente
  claramente más barata, una oferta o un `card_price`. Muestra el ahorro en $ por ítem y el total, y deja que el usuario elija.
  Ojo: la búsqueda pública muestra precios de una tienda por defecto (pueden diferir de la suya); el precio real
  es el que muestra `cart` después de agregar.
- Compra mínima: $19.990.

### Pagar

Deja todo listo y abre el checkout: `$A open /checkout`. Recuérdale que revise que la dirección del checkout
sea la que confirmó. Lo normal es que el usuario revise y pague él.
Si te pide que pagues tú: resume primero los productos, la dirección, la ventana de despacho, el medio de pago y el
**total exacto**, y espera un "sí" explícito a ese resumen en ese momento. Una aprobación anterior o general no cuenta,
porque el pago es plata real y no se deshace. Nunca escribas datos de tarjeta ni claves.
