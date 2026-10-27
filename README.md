# jumbo-cl · skill de Claude para comprar en Jumbo

Skill para [Claude Code](https://claude.com/claude-code) que te deja hacer el súper en
[jumbo.cl](https://www.jumbo.cl) conversando:

- **Precios:** busca productos y compara por precio, por litro/kilo, por descuento o con Tarjeta Cencosud.
- **Tus compras:** revisa tus pedidos anteriores y los productos que compras más seguido.
- **El carro:** arma "el pedido de siempre", repite una compra o te dice qué te falta en el carro.
- **Ahorro:** recomienda alternativas más baratas para lo que tienes en el carro.
- **Pago:** deja todo listo en el checkout. El pago lo confirmas tú.

> ⚠️ **Proyecto no oficial.** No está afiliado a Jumbo ni a Cencosud. Usa la web pública de jumbo.cl
> y tu propia sesión, así que puede dejar de funcionar si el sitio cambia. Úsalo bajo tu responsabilidad.

## Ejemplos

```
cuánto sale la leche entera en el Jumbo, la más barata por litro
ármame el pedido de siempre
repite mi última compra
qué me falta en el carro
busca opciones más baratas para lo que tengo en el carro
```

## Instalación

**Como plugin (recomendado):**

```
/plugin marketplace add thesouthernk/jumbo-cl-skill
/plugin install jumbo-cl@jumbo-cl
```

**A mano:** copia `skills/jumbo-cl` a `~/.claude/skills/jumbo-cl`.

### Requisitos

| Para | Necesitas |
|---|---|
| Buscar y comparar precios | Python 3.8+ (solo stdlib) |
| Compras anteriores y carro | Además: Google Chrome y `pip install playwright` |

La primera vez que pidas algo de tu cuenta se abrirá una ventana de Chrome con un perfil propio
(`~/.jumbo-cl/profile`). Inicia sesión en Jumbo ahí, con Google o con tu correo. La sesión queda guardada.

En Linux o Windows, apunta a tu Chrome con `JUMBO_CHROME=/ruta/a/chrome`.

## Cómo funciona

- **Búsqueda:** lee los datos que la página `jumbo.cl/busqueda` ya trae embebidos. No usa login ni navegador.
- **Cuenta:** abre Chrome normal con `--remote-debugging-port=9333` (Google bloquea el login en navegadores
  automatizados) y llama a la API web de Jumbo desde una pestaña de jumbo.cl, con tu sesión. Tus credenciales
  nunca pasan por Claude.
- **Pago:** la skill nunca paga sin que confirmes explícitamente un resumen con el total.

**Privacidad:** tu sesión vive solo en tu computador. Ojo con que el puerto de depuración de Chrome da control
del navegador a cualquier programa local mientras esa ventana está abierta, así que ciérrala cuando no la uses.

## Licencia

MIT
