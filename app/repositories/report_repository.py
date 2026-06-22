from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status

from app.models.report_template import ReportTemplateModel
from app.services.catalog import ReportType, ReportField, FieldKind, FieldType, FilterOperator


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_db_details(self, uid: int) -> Dict[str, Any]:
        query = text("SELECT id_usuario, nombre, apellido, username FROM usuario WHERE id_usuario = :uid")
        result = self.db.execute(query, {"uid": uid}).fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario autenticado no existe en la base de datos"
            )
        return {
            "id": result[0],
            "nombre": result[1],
            "apellido": result[2],
            "username": result[3],
            "full_name": f"{result[1]} {result[2]}"
        }

    def list_templates(self, owner_id: int) -> List[Any]:
        query = text("""
            SELECT t.*, (u.nombre || ' ' || u.apellido) as owner_name 
            FROM report_templates t
            JOIN usuario u ON u.id_usuario = t.owner_id
            WHERE t.owner_id = :owner_id OR t.is_shared = true
            ORDER BY t.updated_at DESC
        """)
        results = self.db.execute(query, {"owner_id": owner_id}).fetchall()
        return results

    def create_template(self, model: ReportTemplateModel) -> ReportTemplateModel:
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def get_template_by_id(self, template_id: int) -> Optional[ReportTemplateModel]:
        return self.db.query(ReportTemplateModel).filter(
            ReportTemplateModel.id == template_id
        ).first()

    def update_template(self) -> None:
        self.db.commit()

    def delete_template(self, model: ReportTemplateModel) -> None:
        self.db.delete(model)
        self.db.commit()

    def execute_report_query(
        self,
        report_type: ReportType,
        selected_fields: List[str],
        filters: List[Any],
        sort_field: Optional[str] = None,
        sort_order: str = "asc",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[str], Dict[str, str], List[Dict[str, Any]], int, List[str]]:

        def resolve_selected_fields(rt: ReportType, sf: List[str]) -> List[ReportField]:
            if rt.is_aggregated:
                dims = []
                for key in sf:
                    field = rt.fields.get(key)
                    if field and field.kind == FieldKind.DIMENSION:
                        dims.append(field)
                if not dims:
                    for field in rt.fields.values():
                        if field.kind == FieldKind.DIMENSION:
                            dims.append(field)
                measures = [f for f in rt.fields.values() if f.kind == FieldKind.MEASURE]
                return dims + measures
            out = []
            for key in sf:
                field = rt.fields.get(key)
                if field and field.kind == FieldKind.PLAIN:
                    out.append(field)
            if not out:
                out = [f for f in rt.fields.values() if f.kind == FieldKind.PLAIN]
            return out

        def build_comparator(field: ReportField, op: FilterOperator, pname: str) -> Optional[str]:
            tpl = op.sql_template().replace(":p", f":{pname}")
            if field.type == FieldType.NUMBER:
                return tpl.replace(f":{pname}", f"CAST(:{pname} AS numeric)")
            elif field.type == FieldType.DATE:
                if op == FilterOperator.LIKE:
                    return None
                return tpl.replace(f":{pname}", f"CAST(:{pname} AS date)")
            elif field.type == FieldType.BOOLEAN:
                if op in (FilterOperator.EQ, FilterOperator.NE):
                    return tpl.replace(f":{pname}", f"CAST(:{pname} AS boolean)")
                return None
            return tpl

        def coerce_value(field: ReportField, op: FilterOperator, raw_val: Any) -> Any:
            s = str(raw_val)
            if field.type == FieldType.NUMBER:
                return Decimal(s)
            elif field.type == FieldType.BOOLEAN:
                return s.lower() in ("true", "1", "yes")
            elif field.type == FieldType.STRING:
                if op == FilterOperator.LIKE:
                    return f"%{s}%"
                return s
            elif field.type == FieldType.DATE:
                return s
            return raw_val

        def describe_op(op: FilterOperator) -> str:
            desc = {
                FilterOperator.EQ: "=",
                FilterOperator.NE: "≠",
                FilterOperator.GT: ">",
                FilterOperator.LT: "<",
                FilterOperator.GTE: "≥",
                FilterOperator.LTE: "≤",
                FilterOperator.LIKE: "contiene",
                FilterOperator.IS_NULL: "es nulo",
                FilterOperator.IS_NOT_NULL: "no es nulo"
            }
            return desc.get(op, str(op.value))

        selected = resolve_selected_fields(report_type, selected_fields)

        needed_joins = set()
        for f in selected:
            needed_joins.update(f.joins)
        for flt in filters:
            f_key = flt.field if hasattr(flt, "field") else flt.get("field")
            f_field = report_type.fields.get(f_key)
            if f_field:
                needed_joins.update(f_field.joins)

        # Also resolve joins needed by date_field (e.g. "nv.fecha_emision" needs the "nota_venta" join)
        if report_type.date_field:
            date_alias = report_type.date_field.split(".")[0].strip()
            for j_key, j_sql in report_type.joins.items():
                parts = j_sql.split()
                for i, part in enumerate(parts):
                    if part.upper() in ("JOIN", "INNER", "LEFT", "RIGHT", "CROSS") and i + 2 < len(parts):
                        alias = parts[i + 2]
                        if alias == date_alias and j_key not in needed_joins:
                            needed_joins.add(j_key)
                            break

        join_sql = ""
        for j_key in report_type.joins.keys():
            if j_key in needed_joins:
                j_sql = report_type.joins[j_key]
                join_sql += f" {j_sql}"

        select_parts = []
        for i, field in enumerate(selected):
            select_parts.append(f"{field.sql} AS c{i}")

        where_clauses = []
        having_clauses = []
        params = {}
        applied_filters = []

        if report_type.date_field and date_from and date_from.strip():
            where_clauses.append(f"{report_type.date_field} >= CAST(:p_date_from AS date)")
            params["p_date_from"] = date_from.strip()
            applied_filters.append(f"Desde: {date_from}")

        if report_type.date_field and date_to and date_to.strip():
            where_clauses.append(f"{report_type.date_field} < (CAST(:p_date_to AS date) + INTERVAL '1 day')")
            params["p_date_to"] = date_to.strip()
            applied_filters.append(f"Hasta: {date_to}")

        for idx, flt in enumerate(filters):
            f_key = flt.field if hasattr(flt, "field") else flt.get("field")
            op_str = flt.operator if hasattr(flt, "operator") else flt.get("operator")
            val = flt.value if hasattr(flt, "value") else flt.get("value")

            field = report_type.fields.get(f_key)
            if not field or not op_str:
                continue

            try:
                op = FilterOperator(op_str)
            except ValueError:
                continue

            target_list = having_clauses if field.kind == FieldKind.MEASURE else where_clauses

            if not op.needs_value():
                target_list.append(f"{field.sql} {op.sql_template()}")
                applied_filters.append(f"{field.label} {describe_op(op)}")
                continue

            if val is None or (op.needs_value() and str(val).strip() == ""):
                continue

            pname = f"p_f{idx}"
            comparator = build_comparator(field, op, pname)
            if not comparator:
                continue

            target_list.append(f"{field.sql} {comparator}")
            params[pname] = coerce_value(field, op, val)
            applied_filters.append(f"{field.label} {describe_op(op)} {val}")

        group_by_sql = ""
        if report_type.is_aggregated:
            dims = [f.sql for f in selected if f.kind == FieldKind.DIMENSION]
            if dims:
                group_by_sql = f" GROUP BY {', '.join(dims)}"

        order_by_sql = ""
        if sort_field:
            sf = report_type.fields.get(sort_field)
            if sf and sf in selected:
                direction = "DESC" if sort_order.lower() == "desc" else "ASC"
                order_by_sql = f" ORDER BY {sf.sql} {direction}"

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        having_sql = f" HAVING {' AND '.join(having_clauses)}" if having_clauses else ""

        base_from = f" FROM {report_type.from_clause}{join_sql}{where_sql}{group_by_sql}{having_sql}"

        sql_main = f"SELECT {', '.join(select_parts)}{base_from}{order_by_sql} LIMIT {limit} OFFSET {offset}"

        if report_type.is_aggregated:
            sql_count = f"SELECT COUNT(*) FROM (SELECT 1{base_from}) AS grp"
        else:
            sql_count = f"SELECT COUNT(*){base_from}"

        res = self.db.execute(text(sql_main), params).fetchall()

        rows = []
        columns = [f.key for f in selected]
        column_labels = {f.key: f.label for f in selected}

        for row in res:
            row_dict = {}
            for i, val in enumerate(row):
                if val is None:
                    row_dict[columns[i]] = ""
                elif isinstance(val, (int, float, Decimal)):
                    row_dict[columns[i]] = str(val)
                elif isinstance(val, bool):
                    row_dict[columns[i]] = "Sí" if val else "No"
                else:
                    row_dict[columns[i]] = str(val)
            rows.append(row_dict)

        total = self.db.execute(text(sql_count), params).scalar() or 0

        if not applied_filters:
            applied_filters.append("Sin filtros aplicados (SELECT *)")

        return columns, column_labels, rows, total, applied_filters
