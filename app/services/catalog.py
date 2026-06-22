from enum import Enum
from typing import List, Dict, Optional


class FieldType(str, Enum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"


class FieldKind(str, Enum):
    PLAIN = "PLAIN"
    DIMENSION = "DIMENSION"
    MEASURE = "MEASURE"


class ReportCategory(str, Enum):
    QBE = "QBE"
    ANALYTICAL = "ANALYTICAL"
    MANAGERIAL = "MANAGERIAL"


class FilterOperator(str, Enum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    LT = "LT"
    GTE = "GTE"
    LTE = "LTE"
    LIKE = "LIKE"
    IS_NULL = "IS_NULL"
    IS_NOT_NULL = "IS_NOT_NULL"

    def sql_template(self) -> str:
        templates = {
            FilterOperator.EQ: "= :p",
            FilterOperator.NE: "!= :p",
            FilterOperator.GT: "> :p",
            FilterOperator.LT: "< :p",
            FilterOperator.GTE: ">= :p",
            FilterOperator.LTE: "<= :p",
            FilterOperator.LIKE: "LIKE :p",
            FilterOperator.IS_NULL: "IS NULL",
            FilterOperator.IS_NOT_NULL: "IS NOT NULL"
        }
        return templates.get(self, "= :p")

    def needs_value(self) -> bool:
        return self not in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL)


class ReportField:
    def __init__(self, key: str, label: str, sql: str, type: FieldType, kind: FieldKind = FieldKind.PLAIN, joins: List[str] = None):
        self.key = key
        self.label = label
        self.sql = sql
        self.type = type
        self.kind = kind
        self.joins = joins or []

    @classmethod
    def plain(cls, key: str, label: str, sql: str, type: FieldType, joins: List[str] = None):
        return cls(key, label, sql, type, FieldKind.PLAIN, joins)

    @classmethod
    def dimension(cls, key: str, label: str, sql: str, type: FieldType, joins: List[str] = None):
        return cls(key, label, sql, type, FieldKind.DIMENSION, joins)

    @classmethod
    def measure(cls, key: str, label: str, sql: str, type: FieldType, joins: List[str] = None):
        return cls(key, label, sql, type, FieldKind.MEASURE, joins)

    def to_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type.value,
            "kind": self.kind.value
        }


class ReportType:
    def __init__(self, key: str, label: str, category: ReportCategory, required_authority: str,
                 from_clause: str, date_field: Optional[str],
                 joins: Dict[str, str], fields: List[ReportField]):
        self.key = key
        self.label = label
        self.category = category
        self.required_authority = required_authority
        self.from_clause = from_clause
        self.date_field = date_field
        self.joins = joins
        self.fields = {f.key: f for f in fields}

    @property
    def is_aggregated(self) -> bool:
        return self.category in (ReportCategory.ANALYTICAL, ReportCategory.MANAGERIAL)

    def to_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category.value,
            "isAggregated": self.is_aggregated,
            "fields": [f.to_dict() for f in self.fields.values()]
        }


class ReportCatalog:
    def __init__(self):
        self.types = {}
        self.register(self.build_ventas())
        self.register(self.build_detalle_ventas())
        self.register(self.build_compras())
        self.register(self.build_inventario())
        self.register(self.build_productos())
        self.register(self.build_usuarios())
        self.register(self.build_ventas_por_mes())
        self.register(self.build_ventas_por_sucursal())
        self.register(self.build_ventas_por_producto())
        self.register(self.build_productos_por_categoria())
        self.register(self.build_comandas())
        self.register(self.build_ventas_por_empleado())
        self.register(self.build_clientes_frecuentes())
        self.register(self.build_caja())
        self.register(self.build_reservas())
        self.register(self.build_mesas())
        self.register(self.build_proveedores())
        self.register(self.build_ventas_por_metodo_pago())
        self.register(self.build_ventas_por_hora())
        self.register(self.build_reservas_por_estado())

    def register(self, t: ReportType):
        self.types[t.key] = t

    def require(self, key: str) -> ReportType:
        if key not in self.types:
            raise ValueError(f"Tipo de reporte no encontrado: {key}")
        return self.types[key]

    def all(self) -> List[ReportType]:
        return list(self.types.values())

    # ── QBE / Detalle ──────────────────────────────────────────

    def build_ventas(self) -> ReportType:
        return ReportType(
            key="ventas",
            label="Notas de Venta",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="nota_venta nv",
            date_field="nv.fecha_emision",
            joins={
                "cliente": "LEFT JOIN cliente c ON c.id_cliente = nv.id_cliente LEFT JOIN usuario uc ON uc.id_usuario = c.id_usuario",
                "empleado": "LEFT JOIN empleado e ON e.id_empleado = nv.id_empleado LEFT JOIN usuario ue ON ue.id_usuario = e.id_usuario",
                "sucursal": "LEFT JOIN sucursal s ON s.id_sucursal = nv.id_sucursal",
                "metodo_pago": "LEFT JOIN metodo_pago mp ON mp.id_metodo_pago = nv.id_metodo_pago"
            },
            fields=[
                ReportField.plain("idNotaVenta", "Nro. Venta", "nv.id_nota_venta", FieldType.NUMBER),
                ReportField.plain("fechaEmision", "Fecha emisión", "nv.fecha_emision", FieldType.DATE),
                ReportField.plain("estado", "Estado", "CAST(nv.estado AS TEXT)", FieldType.STRING),
                ReportField.plain("subTotal", "Subtotal", "nv.sub_total", FieldType.NUMBER),
                ReportField.plain("descuento", "Descuento", "nv.descuento", FieldType.NUMBER),
                ReportField.plain("impuesto", "Impuesto", "nv.impuesto", FieldType.NUMBER),
                ReportField.plain("propina", "Propina", "nv.propina", FieldType.NUMBER),
                ReportField.plain("total", "Total", "nv.total", FieldType.NUMBER),
                ReportField.plain("nit", "NIT", "nv.nit", FieldType.STRING),
                ReportField.plain("observaciones", "Observaciones", "nv.observaciones", FieldType.STRING),
                ReportField.plain("clienteNombre", "Cliente", "(uc.nombre || ' ' || uc.apellido)", FieldType.STRING, ["cliente"]),
                ReportField.plain("empleadoNombre", "Empleado", "(ue.nombre || ' ' || ue.apellido)", FieldType.STRING, ["empleado"]),
                ReportField.plain("sucursalNombre", "Sucursal", "s.nombre", FieldType.STRING, ["sucursal"]),
                ReportField.plain("metodoPago", "Método de pago", "mp.nombre", FieldType.STRING, ["metodo_pago"]),
                ReportField.plain("fechaPago", "Fecha pago", "nv.fecha_pago", FieldType.DATE),
            ]
        )

    def build_detalle_ventas(self) -> ReportType:
        return ReportType(
            key="detalle_ventas",
            label="Detalle de Ventas",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="detalle_nota_venta dnv",
            date_field="nv.fecha_emision",
            joins={
                "nota_venta": "LEFT JOIN nota_venta nv ON nv.id_nota_venta = dnv.id_nota_venta",
                "producto": "LEFT JOIN producto_final pf ON pf.id_producto_final = dnv.producto_final",
                "categoria": "LEFT JOIN categoria cat ON cat.id_categoria = pf.id_categoria"
            },
            fields=[
                ReportField.plain("idNotaVenta", "Nro. Venta", "dnv.id_nota_venta", FieldType.NUMBER, ["nota_venta"]),
                ReportField.plain("productoNombre", "Producto", "pf.nombre", FieldType.STRING, ["producto"]),
                ReportField.plain("categoriaNombre", "Categoría", "cat.nombre", FieldType.STRING, ["producto", "categoria"]),
                ReportField.plain("cantidad", "Cantidad", "dnv.cantidad", FieldType.NUMBER),
                ReportField.plain("precioU", "Precio unitario", "dnv.precio_u", FieldType.NUMBER),
                ReportField.plain("costoU", "Costo unitario", "dnv.costo_u", FieldType.NUMBER),
                ReportField.plain("descuento", "Descuento", "dnv.descuento", FieldType.NUMBER),
                ReportField.plain("subtotal", "Subtotal", "dnv.subtotal", FieldType.NUMBER),
                ReportField.plain("descripcion", "Descripción", "dnv.descripcion", FieldType.STRING),
                ReportField.plain("fechaEmision", "Fecha venta", "nv.fecha_emision", FieldType.DATE, ["nota_venta"]),
                ReportField.plain("estadoVenta", "Estado venta", "CAST(nv.estado AS TEXT)", FieldType.STRING, ["nota_venta"]),
            ]
        )

    def build_compras(self) -> ReportType:
        return ReportType(
            key="compras",
            label="Compras",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="compra co",
            date_field="co.fecha_compra",
            joins={
                "proveedor": "LEFT JOIN proveedor prov ON prov.id_proveedor = co.id_proveedor",
                "empleado": "LEFT JOIN empleado e ON e.id_empleado = co.id_empleado LEFT JOIN usuario ue ON ue.id_usuario = e.id_usuario"
            },
            fields=[
                ReportField.plain("idCompra", "Nro. Compra", "co.id_compra", FieldType.NUMBER),
                ReportField.plain("nroFactura", "Nro. Factura", "co.nro_factura", FieldType.STRING),
                ReportField.plain("fechaCompra", "Fecha compra", "co.fecha_compra", FieldType.DATE),
                ReportField.plain("proveedorNombre", "Proveedor", "prov.empresa", FieldType.STRING, ["proveedor"]),
                ReportField.plain("proveedorNit", "NIT Proveedor", "prov.nit", FieldType.STRING, ["proveedor"]),
                ReportField.plain("empleadoNombre", "Responsable", "(ue.nombre || ' ' || ue.apellido)", FieldType.STRING, ["empleado"]),
                ReportField.plain("subTotal", "Subtotal", "co.sub_total", FieldType.NUMBER),
                ReportField.plain("descuento", "Descuento", "co.descuento", FieldType.NUMBER),
                ReportField.plain("impuesto", "Impuesto", "co.impuesto", FieldType.NUMBER),
                ReportField.plain("total", "Total", "co.total", FieldType.NUMBER),
                ReportField.plain("estadoPago", "Estado pago", "CAST(co.estado_pago AS TEXT)", FieldType.STRING),
                ReportField.plain("fechaLimitePago", "Fecha límite pago", "co.fecha_limite_pago", FieldType.DATE),
                ReportField.plain("observaciones", "Observaciones", "co.observaciones", FieldType.STRING),
            ]
        )

    def build_inventario(self) -> ReportType:
        return ReportType(
            key="inventario",
            label="Inventario (Insumos)",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="inventario inv",
            date_field="inv.fecha_creacion",
            joins={},
            fields=[
                ReportField.plain("codigo", "Código", "inv.codigo", FieldType.STRING),
                ReportField.plain("nombre", "Nombre", "inv.nombre", FieldType.STRING),
                ReportField.plain("descripcion", "Descripción", "inv.descripcion", FieldType.STRING),
                ReportField.plain("unidadMedida", "Unidad medida", "CAST(inv.unidad_medida AS TEXT)", FieldType.STRING),
                ReportField.plain("marca", "Marca", "inv.marca", FieldType.STRING),
                ReportField.plain("esRehutilizable", "Reutilizable", "inv.es_rehutilizable", FieldType.BOOLEAN),
                ReportField.plain("activo", "Activo", "inv.activo", FieldType.BOOLEAN),
                ReportField.plain("fechaCreacion", "Fecha creación", "inv.fecha_creacion", FieldType.DATE),
            ]
        )

    def build_productos(self) -> ReportType:
        return ReportType(
            key="productos",
            label="Productos (Menú)",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="producto_final pf",
            date_field="pf.fecha_creacion",
            joins={
                "categoria": "LEFT JOIN categoria cat ON cat.id_categoria = pf.id_categoria"
            },
            fields=[
                ReportField.plain("codigo", "Código", "pf.codigo", FieldType.STRING),
                ReportField.plain("nombre", "Nombre", "pf.nombre", FieldType.STRING),
                ReportField.plain("descripcion", "Descripción", "pf.descripcion", FieldType.STRING),
                ReportField.plain("categoriaNombre", "Categoría", "cat.nombre", FieldType.STRING, ["categoria"]),
                ReportField.plain("tiempoPreparacion", "Tiempo prep. (min)", "pf.tiempo_preparacion", FieldType.NUMBER),
                ReportField.plain("activo", "Activo", "pf.activo", FieldType.BOOLEAN),
                ReportField.plain("fechaCreacion", "Fecha creación", "pf.fecha_creacion", FieldType.DATE),
            ]
        )

    def build_usuarios(self) -> ReportType:
        return ReportType(
            key="usuarios",
            label="Usuarios",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="usuario u",
            date_field="u.fecha_registro",
            joins={},
            fields=[
                ReportField.plain("ci", "CI", "u.ci", FieldType.STRING),
                ReportField.plain("nombre", "Nombre", "u.nombre", FieldType.STRING),
                ReportField.plain("apellido", "Apellido", "u.apellido", FieldType.STRING),
                ReportField.plain("nombreCompleto", "Nombre completo", "(u.nombre || ' ' || u.apellido)", FieldType.STRING),
                ReportField.plain("username", "Username", "u.username", FieldType.STRING),
                ReportField.plain("correo", "Correo", "u.correo", FieldType.STRING),
                ReportField.plain("telefono", "Teléfono", "u.telefono", FieldType.STRING),
                ReportField.plain("sexo", "Sexo", "u.sexo", FieldType.STRING),
                ReportField.plain("tipoUsuario", "Tipo", "u.tipo_usuario", FieldType.STRING),
                ReportField.plain("activo", "Activo", "u.activo", FieldType.BOOLEAN),
                ReportField.plain("estadoAcceso", "Estado acceso", "u.estado_acceso", FieldType.STRING),
                ReportField.plain("fechaRegistro", "Fecha registro", "u.fecha_registro", FieldType.DATE),
                ReportField.plain("roles", "Roles",
                    "(SELECT string_agg(r.nombre, ', ') FROM rol_usuario ru JOIN rol r ON r.id_rol = ru.id_rol WHERE ru.id_usuario = u.id_usuario)",
                    FieldType.STRING),
            ]
        )

    def build_comandas(self) -> ReportType:
        return ReportType(
            key="comandas",
            label="Estado de Pedidos/Comandas",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="comanda c",
            date_field="c.fecha_apertura",
            joins={
                "mesa": "LEFT JOIN mesa m ON m.id_mesa = c.id_mesa",
                "sucursal": "LEFT JOIN sucursal s ON s.id_sucursal = c.id_sucursal",
                "empleado": "LEFT JOIN empleado e ON e.id_empleado = c.id_empleado LEFT JOIN usuario ue ON ue.id_usuario = e.id_usuario",
                "cliente": "LEFT JOIN cliente cl ON cl.id_cliente = c.id_cliente LEFT JOIN usuario ucl ON ucl.id_usuario = cl.id_usuario"
            },
            fields=[
                ReportField.plain("numeroComanda", "Nro. Comanda", "c.numero_comanda", FieldType.STRING),
                ReportField.plain("tipoServicio", "Tipo servicio", "c.tipo_servicio", FieldType.STRING),
                ReportField.plain("estado", "Estado", "c.estado", FieldType.STRING),
                ReportField.plain("fechaApertura", "Fecha apertura", "c.fecha_apertura", FieldType.DATE),
                ReportField.plain("fechaCierre", "Fecha cierre", "c.fecha_cierre", FieldType.DATE),
                ReportField.plain("sucursal", "Sucursal", "s.nombre", FieldType.STRING, ["sucursal"]),
                ReportField.plain("mesa", "Nro. Mesa", "m.numero_mesa", FieldType.STRING, ["mesa"]),
                ReportField.plain("empleado", "Atendido por", "(ue.nombre || ' ' || ue.apellido)", FieldType.STRING, ["empleado"]),
                ReportField.plain("cliente", "Cliente", "(ucl.nombre || ' ' || ucl.apellido)", FieldType.STRING, ["cliente"]),
                ReportField.plain("numeroPersonas", "Personas", "c.numero_personas", FieldType.NUMBER)
            ]
        )

    # ── Analíticos / Gerenciales (agregados) ───────────────────

    def build_ventas_por_mes(self) -> ReportType:
        return ReportType(
            key="ventas_por_mes",
            label="Ventas por mes",
            category=ReportCategory.ANALYTICAL,
            required_authority="REPORT_READ",
            from_clause="nota_venta nv",
            date_field="nv.fecha_emision",
            joins={},
            fields=[
                ReportField.dimension("mes", "Mes", "to_char(nv.fecha_emision, 'YYYY-MM')", FieldType.STRING),
                ReportField.measure("totalVentas", "Total ventas (Bs)", "SUM(nv.total)", FieldType.NUMBER),
                ReportField.measure("cantidadVentas", "Cantidad de ventas", "COUNT(*)", FieldType.NUMBER),
                ReportField.measure("promedioVenta", "Promedio por venta", "ROUND(AVG(nv.total), 2)", FieldType.NUMBER),
            ]
        )

    def build_ventas_por_sucursal(self) -> ReportType:
        return ReportType(
            key="ventas_por_sucursal",
            label="Ventas por sucursal",
            category=ReportCategory.MANAGERIAL,
            required_authority="REPORT_READ",
            from_clause="nota_venta nv",
            date_field="nv.fecha_emision",
            joins={
                "sucursal": "LEFT JOIN sucursal s ON s.id_sucursal = nv.id_sucursal"
            },
            fields=[
                ReportField.dimension("sucursal", "Sucursal", "s.nombre", FieldType.STRING, ["sucursal"]),
                ReportField.measure("totalVentas", "Total ventas (Bs)", "SUM(nv.total)", FieldType.NUMBER),
                ReportField.measure("cantidadVentas", "Cantidad de ventas", "COUNT(*)", FieldType.NUMBER),
                ReportField.measure("promedioVenta", "Promedio por venta", "ROUND(AVG(nv.total), 2)", FieldType.NUMBER),
            ]
        )

    def build_ventas_por_producto(self) -> ReportType:
        return ReportType(
            key="ventas_por_producto",
            label="Ventas por producto",
            category=ReportCategory.MANAGERIAL,
            required_authority="REPORT_READ",
            from_clause="detalle_nota_venta dnv",
            date_field="nv.fecha_emision",
            joins={
                "nota_venta": "LEFT JOIN nota_venta nv ON nv.id_nota_venta = dnv.id_nota_venta",
                "producto": "LEFT JOIN producto_final pf ON pf.id_producto_final = dnv.producto_final"
            },
            fields=[
                ReportField.dimension("producto", "Producto", "pf.nombre", FieldType.STRING, ["producto"]),
                ReportField.measure("cantidadVendida", "Cantidad vendida", "SUM(dnv.cantidad)", FieldType.NUMBER),
                ReportField.measure("ingresoTotal", "Ingreso total (Bs)", "SUM(dnv.subtotal)", FieldType.NUMBER),
                ReportField.measure("costoTotal", "Costo total (Bs)", "SUM(dnv.costo_u * dnv.cantidad)", FieldType.NUMBER),
                ReportField.measure("ganancia", "Ganancia (Bs)", "SUM(dnv.subtotal - (dnv.costo_u * dnv.cantidad))", FieldType.NUMBER),
            ]
        )

    def build_productos_por_categoria(self) -> ReportType:
        return ReportType(
            key="productos_por_categoria",
            label="Productos por categoría",
            category=ReportCategory.ANALYTICAL,
            required_authority="REPORT_READ",
            from_clause="producto_final pf",
            date_field="pf.fecha_creacion",
            joins={
                "categoria": "LEFT JOIN categoria cat ON cat.id_categoria = pf.id_categoria"
            },
            fields=[
                ReportField.dimension("categoria", "Categoría", "COALESCE(cat.nombre, '(sin categoría)')", FieldType.STRING, ["categoria"]),
                ReportField.measure("totalProductos", "Total productos", "COUNT(*)", FieldType.NUMBER),
            ]
        )

    def build_ventas_por_empleado(self) -> ReportType:
        return ReportType(
            key="ventas_por_empleado",
            label="Desempeño de Empleados",
            category=ReportCategory.ANALYTICAL,
            required_authority="REPORT_READ",
            from_clause="nota_venta nv",
            date_field="nv.fecha_emision",
            joins={
                "empleado": "JOIN empleado e ON e.id_empleado = nv.id_empleado JOIN usuario u ON u.id_usuario = e.id_usuario"
            },
            fields=[
                ReportField.dimension("empleado", "Empleado", "(u.nombre || ' ' || u.apellido)", FieldType.STRING, ["empleado"]),
                ReportField.measure("cantidadVentas", "Notas de Venta", "COUNT(nv.id_nota_venta)", FieldType.NUMBER),
                ReportField.measure("ingresoGenerado", "Ingreso Generado (Bs)", "SUM(nv.total)", FieldType.NUMBER)
            ]
        )

    def build_clientes_frecuentes(self) -> ReportType:
        return ReportType(
            key="clientes_frecuentes",
            label="Clientes Frecuentes",
            category=ReportCategory.MANAGERIAL,
            required_authority="REPORT_READ",
            from_clause="nota_venta nv",
            date_field="nv.fecha_emision",
            joins={
                "cliente": "JOIN cliente c ON c.id_cliente = nv.id_cliente JOIN usuario u ON u.id_usuario = c.id_usuario"
            },
            fields=[
                ReportField.dimension("cliente", "Cliente", "(u.nombre || ' ' || u.apellido)", FieldType.STRING, ["cliente"]),
                ReportField.dimension("ci", "CI / Documento", "u.ci", FieldType.STRING, ["cliente"]),
                ReportField.measure("visitas", "Cantidad de Compras", "COUNT(nv.id_nota_venta)", FieldType.NUMBER),
                ReportField.measure("totalGastado", "Total Gastado (Bs)", "SUM(nv.total)", FieldType.NUMBER)
            ]
        )

    # ── QBE / Detalle (nuevos) ─────────────────────────────────

    def build_caja(self) -> ReportType:
        return ReportType(
            key="caja",
            label="Cierre de Caja",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="caja cj",
            date_field="cj.fecha_apertura",
            joins={
                "sucursal": "LEFT JOIN sucursal s ON s.id_sucursal = cj.id_sucursal",
                "empleado_apertura": "LEFT JOIN empleado ea ON ea.id_empleado = cj.id_empleado_apertura LEFT JOIN usuario uea ON uea.id_usuario = ea.id_usuario",
                "empleado_cierre": "LEFT JOIN empleado ec ON ec.id_empleado = cj.id_empleado_cierre LEFT JOIN usuario uec ON uec.id_usuario = ec.id_usuario"
            },
            fields=[
                ReportField.plain("idCaja", "Nro. Caja", "cj.id_caja", FieldType.NUMBER),
                ReportField.plain("fechaApertura", "Fecha apertura", "cj.fecha_apertura", FieldType.DATE),
                ReportField.plain("fechaCierre", "Fecha cierre", "cj.fecha_cierre", FieldType.DATE),
                ReportField.plain("estado", "Estado", "cj.estado", FieldType.STRING),
                ReportField.plain("montoInicial", "Monto inicial (Bs)", "cj.monto_inicial", FieldType.NUMBER),
                ReportField.plain("montoFinal", "Monto final (Bs)", "cj.monto_final", FieldType.NUMBER),
                ReportField.plain("saldoEsperado", "Saldo esperado (Bs)", "cj.saldo_esperado", FieldType.NUMBER),
                ReportField.plain("diferencia", "Diferencia (Bs)", "cj.diferencia", FieldType.NUMBER),
                ReportField.plain("sucursalNombre", "Sucursal", "s.nombre", FieldType.STRING, ["sucursal"]),
                ReportField.plain("empleadoApertura", "Abierto por", "(uea.nombre || ' ' || uea.apellido)", FieldType.STRING, ["empleado_apertura"]),
                ReportField.plain("empleadoCierre", "Cerrado por", "(uec.nombre || ' ' || uec.apellido)", FieldType.STRING, ["empleado_cierre"]),
                ReportField.plain("observacionApertura", "Obs. apertura", "cj.observacion_apertura", FieldType.STRING),
                ReportField.plain("observacionCierre", "Obs. cierre", "cj.observacion_cierre", FieldType.STRING),
            ]
        )

    def build_reservas(self) -> ReportType:
        return ReportType(
            key="reservas",
            label="Reservas",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="reserva r",
            date_field="r.fecha_reserva",
            joins={
                "sucursal": "LEFT JOIN sucursal s ON s.id_sucursal = r.id_sucursal"
            },
            fields=[
                ReportField.plain("idReserva", "Nro. Reserva", "r.id_reserva", FieldType.NUMBER),
                ReportField.plain("fechaReserva", "Fecha", "r.fecha_reserva", FieldType.DATE),
                ReportField.plain("horaInicio", "Hora inicio", "r.hora_inicio", FieldType.STRING),
                ReportField.plain("horaFin", "Hora fin", "r.hora_fin", FieldType.STRING),
                ReportField.plain("cantidadPersonas", "Personas", "r.cantidad_personas", FieldType.NUMBER),
                ReportField.plain("estado", "Estado", "r.estado", FieldType.STRING),
                ReportField.plain("clienteNombre", "Cliente", "r.cliente_nombre", FieldType.STRING),
                ReportField.plain("clienteTelefono", "Teléfono", "r.cliente_telefono", FieldType.STRING),
                ReportField.plain("clienteCorreo", "Correo", "r.cliente_correo", FieldType.STRING),
                ReportField.plain("sucursalNombre", "Sucursal", "s.nombre", FieldType.STRING, ["sucursal"]),
                ReportField.plain("observaciones", "Observaciones", "r.observaciones", FieldType.STRING),
                ReportField.plain("fechaCreacion", "Fecha creación", "r.fecha_creacion", FieldType.DATE),
                ReportField.plain("motivoCancelacion", "Motivo cancelación", "r.motivo_cancelacion", FieldType.STRING),
            ]
        )

    def build_mesas(self) -> ReportType:
        return ReportType(
            key="mesas",
            label="Estado de Mesas",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="mesa m",
            date_field=None,
            joins={
                "sector": "LEFT JOIN sector sec ON sec.id_sector = m.id_sector",
                "sucursal": "LEFT JOIN sucursal s ON s.id_sucursal = sec.id_sucursal"
            },
            fields=[
                ReportField.plain("idMesa", "Nro. Mesa", "m.id_mesa", FieldType.NUMBER),
                ReportField.plain("numeroMesa", "Código mesa", "m.numero_mesa", FieldType.STRING),
                ReportField.plain("capacidadPersonas", "Capacidad", "m.capacidad_personas", FieldType.NUMBER),
                ReportField.plain("disponibilidad", "Estado", "m.disponibilidad", FieldType.STRING),
                ReportField.plain("sectorNombre", "Sector", "sec.nombre", FieldType.STRING, ["sector"]),
                ReportField.plain("sucursalNombre", "Sucursal", "s.nombre", FieldType.STRING, ["sucursal"]),
                ReportField.plain("activo", "Activo", "m.activo", FieldType.BOOLEAN),
            ]
        )

    def build_proveedores(self) -> ReportType:
        return ReportType(
            key="proveedores",
            label="Proveedores",
            category=ReportCategory.QBE,
            required_authority="REPORT_READ",
            from_clause="proveedor prov",
            date_field="prov.created_at",
            joins={},
            fields=[
                ReportField.plain("idProveedor", "Nro. Proveedor", "prov.id_proveedor", FieldType.NUMBER),
                ReportField.plain("empresa", "Empresa", "prov.empresa", FieldType.STRING),
                ReportField.plain("nit", "NIT", "prov.nit", FieldType.STRING),
                ReportField.plain("nombreContacto", "Contacto", "prov.nombre_contacto", FieldType.STRING),
                ReportField.plain("telefono", "Teléfono", "prov.telefono", FieldType.STRING),
                ReportField.plain("correo", "Correo", "prov.correo", FieldType.STRING),
                ReportField.plain("direccion", "Dirección", "prov.direccion", FieldType.STRING),
                ReportField.plain("categoriaProductos", "Categoría", "prov.categoria_productos", FieldType.STRING),
                ReportField.plain("activo", "Activo", "prov.activo", FieldType.BOOLEAN),
                ReportField.plain("createdAt", "Fecha creación", "prov.created_at", FieldType.DATE),
            ]
        )

    # ── Analíticos / Gerenciales (nuevos) ──────────────────────

    def build_ventas_por_metodo_pago(self) -> ReportType:
        return ReportType(
            key="ventas_por_metodo_pago",
            label="Ventas por Método de Pago",
            category=ReportCategory.MANAGERIAL,
            required_authority="REPORT_READ",
            from_clause="nota_venta nv",
            date_field="nv.fecha_emision",
            joins={
                "metodo_pago": "LEFT JOIN metodo_pago mp ON mp.id_metodo_pago = nv.id_metodo_pago"
            },
            fields=[
                ReportField.dimension("metodoPago", "Método de pago", "mp.nombre", FieldType.STRING, ["metodo_pago"]),
                ReportField.measure("totalVentas", "Total ventas (Bs)", "SUM(nv.total)", FieldType.NUMBER),
                ReportField.measure("cantidadVentas", "Cantidad de ventas", "COUNT(*)", FieldType.NUMBER),
                ReportField.measure("promedioVenta", "Promedio por venta (Bs)", "ROUND(AVG(nv.total), 2)", FieldType.NUMBER),
            ]
        )

    def build_ventas_por_hora(self) -> ReportType:
        return ReportType(
            key="ventas_por_hora",
            label="Ventas por Hora del Día",
            category=ReportCategory.MANAGERIAL,
            required_authority="REPORT_READ",
            from_clause="nota_venta nv",
            date_field="nv.fecha_emision",
            joins={},
            fields=[
                ReportField.dimension("hora", "Hora", "to_char(nv.fecha_emision, 'HH24') || ':00'", FieldType.STRING),
                ReportField.measure("totalVentas", "Total ventas (Bs)", "SUM(nv.total)", FieldType.NUMBER),
                ReportField.measure("cantidadVentas", "Cantidad de ventas", "COUNT(*)", FieldType.NUMBER),
                ReportField.measure("promedioVenta", "Promedio por venta (Bs)", "ROUND(AVG(nv.total), 2)", FieldType.NUMBER),
            ]
        )

    def build_reservas_por_estado(self) -> ReportType:
        return ReportType(
            key="reservas_por_estado",
            label="Reservas por Estado",
            category=ReportCategory.ANALYTICAL,
            required_authority="REPORT_READ",
            from_clause="reserva r",
            date_field="r.fecha_reserva",
            joins={},
            fields=[
                ReportField.dimension("estado", "Estado", "r.estado", FieldType.STRING),
                ReportField.measure("totalReservas", "Total reservas", "COUNT(*)", FieldType.NUMBER),
            ]
        )
