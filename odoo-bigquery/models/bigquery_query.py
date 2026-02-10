import logging
import psycopg2
import json
import time
from datetime import datetime, timedelta
import pandas as pd
from odoo import models, fields, api
import ast
from odoo.osv import expression
from google.cloud import bigquery
from google.oauth2 import service_account
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)


class BigQueryQuery(models.Model):
    _name = 'bigquery.connector.query'
    _description = 'BigQuery Query Builder'

    name = fields.Char(string="Query Name", required=True)
    table_name = fields.Selection(selection='_get_table_options', string="Table", required=True)
    column_ids = fields.Many2many(
        'bigquery.connector.column',
        'bigquery_query_column_rel',
        'query_id',
        'column_id',
        string="Columns"
    )
    domain_filter = fields.Text(string="Domain Filter")
    last_sync = fields.Datetime(string="Last Sync Timestamp")
    last_sync_id = fields.Integer(string="Last Synced ID")
    is_locked = fields.Boolean(string="Cron Lock", default=False)
    export_complete = fields.Boolean(string="Export Complete", default=False)
    incremental_sync_enabled = fields.Boolean(string="Enable Incremental Sync", default=False)
    interval_minutes = fields.Integer(
        string="Sync Interval (Minutes)",
        default=15,
        help="Minimum time between successful sync runs for this query."
    )

    _sql_constraints = [
        (
            'my_model_bqname_uniq',          # constraint name (must be unique)
            'UNIQUE(name)',                # SQL constraint
            'The name must be unique.'     # user-friendly error message
        ),
    ]

    @api.model
    def _get_table_options(self):
        self.env.cr.execute("SELECT relname FROM pg_stat_user_tables ORDER BY relname")
        return [(table[0], table[0]) for table in self.env.cr.fetchall()]

    @api.onchange('table_name')
    def _onchange_table_name(self):
        if self.table_name:
            self.env.cr.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
            """, (self.table_name,))
            columns_data = self.env.cr.fetchall()
            column_ids = []
            for col_name, in columns_data:
                existing = self.env['bigquery.connector.column'].search([('name', '=', col_name)], limit=1)
                if not existing:
                    existing = self.env['bigquery.connector.column'].create({'name': col_name})
                column_ids.append(existing.id)
            self.column_ids = [(6, 0, column_ids)]
        else:
            self.column_ids = [(5, 0, 0)]

    def get_bigquery_client(self):
        ICP = self.env['ir.config_parameter'].sudo()
        credentials_json = ICP.get_param('bigquery.credentials_json')
        project_id = ICP.get_param('bigquery.project_id')
        if not credentials_json or not project_id:
            raise ValueError("BigQuery credentials or project ID not set.")
        credentials = service_account.Credentials.from_service_account_info(json.loads(credentials_json))
        return bigquery.Client(project=project_id, credentials=credentials)

    def write(self, vals):
        res = super().write(vals)
        try:
            for record in res:
                if 'incremental_sync_enabled' in vals or 'interval_minutes' in vals:
                    self._update_cron_state_based_on_queries()
        except Exception as e:
            if 'incremental_sync_enabled' in vals or 'interval_minutes' in vals:
                self._update_cron_state_based_on_queries()
        return res

    @api.model
    def create(self, vals):
        res = super().create(vals)
        try:
            for record in res:
                self._update_cron_state_based_on_queries()
        except Exception as e:
            self._update_cron_state_based_on_queries()
        return res

    def _update_cron_state_based_on_queries(self):
        _logger.info("Updating cron state based on queries...", self.name)
        cron = self.env['ir.cron'].search([('name', '=', self.name)])

        if self.incremental_sync_enabled == True:
            if cron:
                cron.unlink()
            try:
                model_id = self.env['ir.model'].search([('model', '=', 'bigquery.connector.query')], limit=1).id
                interval_minutes = max(self.interval_minutes or 0, 1)
                next_run = datetime.now() + timedelta(minutes=interval_minutes)
                self.env['ir.cron'].create({
                    'name': self.name,
                    'model_id': model_id,
                    'model_name': 'bigquery.connector.query',
                    'state': 'code',
                    'code': f"model.browse({self.id}).run_query()",
                    'interval_number': self.interval_minutes,
                    'interval_type': 'minutes',
                    'nextcall': next_run.strftime('%Y-%m-%d %H:%M:%S'),
                    'active': True,
                    'user_id': self.env.ref('base.user_root').id,
                    # 'numbercall': -1,
                })
                _logger.info(f"✅ Created new cron to run every {self.interval_minutes} minute(s).")
            except Exception as e:
                _logger.error(f"❌ Failed to create cron: {e}")
        else:
            if cron:
                cron.unlink()
                _logger.info("🛑 Existing cron removed due to incremental sync disabled.")

    def _get_cron_lock(self):
        self.env.cr.execute(
            'SELECT is_locked FROM bigquery_connector_query WHERE id = %s', (self.id,))
        res = self.env.cr.fetchone()
        return res[0] if res else False

    def _set_cron_lock(self, value):
        try:
            self.env.cr.execute(
                "SELECT id FROM bigquery_connector_query WHERE id = %s FOR UPDATE NOWAIT", (self.id,))
            self.write({'is_locked': value})
            self.env.cr.commit()
        except psycopg2.errors.LockNotAvailable:
            self.env.cr.rollback()
            _logger.warning(f"🔒 Lock not available for query {self.id} - skipping for now.")
            raise
        except psycopg2.errors.SerializationFailure:
            self.env.cr.rollback()
            _logger.warning(f"⚠️ Serialization failure while locking query {self.id}")
            raise
        except Exception as e:
            self.env.cr.rollback()
            _logger.error(f"💥 Unexpected error in cron lock for query {self.id}: {e}")
            raise

    def unlink(self):
        for record in self:
            if record.incremental_sync_enabled:
                raise UserError(
                    "You cannot delete this export query while Incremental Sync is enabled.\n"
                    "Disable Incremental Sync first, then delete."
                )

            cron = self.env['ir.cron'].search([('name', '=', record.name)], limit=1)
            if cron:
                cron.unlink()

        return super().unlink()

    def run_query(self, time_limit_seconds=100):
        client = self.get_bigquery_client()
        for record in self:
            if record._get_cron_lock():
                continue
            try:
                record._set_cron_lock(True)
                start_time = time.time()
                batch_counter = 0
                while True:
                    if time.time() - start_time >= time_limit_seconds:
                        _logger.info("⏱ Time limit reached for %s", record.name)
                        break
                    has_more = record.process_sub_batch(client)
                    if not has_more:
                        break
                    batch_counter += 1
                    if batch_counter >= 5:
                        time.sleep(0.5)
                        batch_counter = 0
            finally:
                record._set_cron_lock(False)

    def hard_refresh(self):
        self.last_sync = '1970-01-01 00:00:00'
        self.last_sync_id = 0
        self._update_cron_state_based_on_queries()
        self.export_complete = False
        self.write({
            'last_sync': self.last_sync,
            'last_sync_id': self.last_sync_id,
        })
        self.run_query()

    def _build_query_parts(self):
        if self.table_name.endswith('_rel'):
            self.env.cr.execute(f"SELECT * FROM {self.table_name} LIMIT 0")
            columns = [col[0] for col in self.env.cr.description]
            selected_columns = sorted(columns)
            safe_column_names = [f'"{col}"' for col in selected_columns if col.isalnum() or '_' in col]
            if not safe_column_names:
                raise ValueError("No valid columns selected or found.")
            select_clause = ", ".join(safe_column_names)
            last_sync = self.last_sync or '1970-01-01 00:00:00'
            last_id = self.last_sync_id or 0
            where_clause = f'"{selected_columns[0]}" > {last_id}'
            params = {'last_sync': last_sync, 'last_id': last_id, 'first_sorted_column': selected_columns[0], 'main_table': self.table_name}
            quoted_table = f'"{self.table_name}"'
            return select_clause, quoted_table, where_clause, params, params
        else:
            domain_params = []
            required_columns = {'id', 'write_date'}
            selected_columns = {col.name for col in self.column_ids} | required_columns
            safe_column_names = [f'"{col}"' for col in selected_columns if col.isalnum() or '_' in col]
            if not safe_column_names:
                raise ValueError("No valid columns selected or found.")
            select_clause = ", ".join(safe_column_names)

            last_sync = self.last_sync or '1970-01-01 00:00:00'
            last_id = self.last_sync_id or 0
            incremental_where = "(write_date > %s OR (write_date = %s AND id > %s))"

            model_name_for_orm = self.table_name.replace('_', '.')
            params = {'last_sync': last_sync, 'last_id': last_id, 'main_table': self.table_name}
            inc_params = [last_sync, last_sync, last_id]

            domain_where = ""
            if self.domain_filter and self.domain_filter.strip() != '[]':
                table_model = self.env[model_name_for_orm].sudo()
                domain = ast.literal_eval(self.domain_filter)
                domain_sql = expression.expression(domain, table_model).query
                domain_where = domain_sql.where_clause.code
                domain_params = list(domain_sql.where_clause.params)

            where_clause = incremental_where
            if domain_where:
                where_clause = f"({where_clause}) AND ({domain_where})"

            all_params = inc_params + domain_params
            _logger.info(f" =>>>>>>all_params {all_params}")

            quoted_table = f'"{self.table_name}"'
            return select_clause, quoted_table, where_clause, params, all_params

    # -------------------- START: STABLE SCHEMA (NO PANDAS DTYPE INFERENCE) --------------------
    def _pg_column_type_map(self, table_name: str):
        self.env.cr.execute("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
        """, (table_name,))
        return {r[0]: {"data_type": r[1], "udt_name": r[2]} for r in self.env.cr.fetchall()}

    def _stable_schema_map_and_fields(self, client, target_table_id: str, columns: list):
        """
        Single source of truth:
        1) If target table exists in BigQuery -> reuse its schema types (so domain filter can never change them)
        2) Else -> derive schema from Postgres information_schema (stable across batches)
        """
        schema_map = {}

        # 1) Reuse BigQuery schema if table exists
        try:
            table = client.get_table(target_table_id)
            for f in table.schema:
                schema_map[f.name] = f.field_type
        except Exception:
            pass

        # 2) Fill missing columns from Postgres column types
        pg_types = self._pg_column_type_map(self.table_name)

        for col in columns:
            if col in schema_map:
                continue

            info = pg_types.get(col) or {}
            data_type = (info.get("data_type") or "").lower()
            udt_name = (info.get("udt_name") or "").lower()
            c = (col or "").lower()

            # ids -> INTEGER
            if c == "id" or c.endswith(("_id", "_uid", "_ref")):
                schema_map[col] = "INTEGER"
                continue

            # booleans
            if data_type == "boolean":
                schema_map[col] = "BOOLEAN"
                continue

            # timestamps / dates
            if data_type in ("timestamp without time zone", "timestamp with time zone"):
                schema_map[col] = "TIMESTAMP"
                continue
            if data_type == "date":
                schema_map[col] = "DATE"
                continue

            # numbers
            if data_type in ("smallint", "integer", "bigint"):
                schema_map[col] = "INTEGER"
                continue
            if data_type in ("numeric", "decimal", "real", "double precision"):
                schema_map[col] = "FLOAT"
                continue

            # json / arrays -> STRING
            if data_type in ("json", "jsonb", "array") or udt_name.endswith("[]"):
                schema_map[col] = "STRING"
                continue

            # default
            schema_map[col] = "STRING"

        schema_fields = [bigquery.SchemaField(col, schema_map[col]) for col in columns]
        return schema_map, schema_fields

    def _transform_dataframe(self, df: pd.DataFrame, schema_map: dict):
        """
        Transform df strictly according to schema_map.
        This prevents domain filtering from creating a different schema.
        """
        for col in df.columns:
            bq_type = schema_map.get(col, 'STRING')

            if bq_type == 'STRING':
                df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
                df[col] = df[col].where(pd.notna(df[col]), None)
                df[col] = df[col].astype(str).where(df[col].notna(), None)

            elif bq_type == 'FLOAT':
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

            elif bq_type == 'INTEGER':
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')

            elif bq_type == 'BOOLEAN':
                def _to_bool(x):
                    if x is None or (isinstance(x, float) and pd.isna(x)):
                        return None
                    s = str(x).strip().lower()
                    if s in ('1', 'true', 't', 'yes', 'y'):
                        return True
                    if s in ('0', 'false', 'f', 'no', 'n'):
                        return False
                    return bool(x)
                df[col] = df[col].apply(_to_bool)

            elif bq_type in ('TIMESTAMP', 'DATETIME', 'DATE'):
                dt = pd.to_datetime(df[col], errors='coerce')
                if bq_type == 'DATE':
                    df[col] = dt.dt.date
                else:
                    df[col] = dt

            else:
                df[col] = df[col].where(pd.notna(df[col]), None)
                df[col] = df[col].astype(str).where(df[col].notna(), None)
    # -------------------- END: STABLE SCHEMA (NO PANDAS DTYPE INFERENCE) --------------------

    def process_sub_batch(self, client, batch_size=50000):
        ICP = self.env['ir.config_parameter'].sudo()
        dataset_id = ICP.get_param('bigquery.dataset_id')

        select_clause, quoted_table, where_clause, params, all_params = self._build_query_parts()

        if params['main_table'].endswith('_rel'):
            order_clause = f"{params['first_sorted_column']} ASC"
        else:
            order_clause = f"write_date ASC, id ASC"

        query = f"""
            SELECT {select_clause}
            FROM {quoted_table}
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT {int(batch_size)}
        """

        _logger.debug(f"Executing query for '{self.name}': {query} with params {params}")
        try:
            self.env.cr.execute(query, all_params)
            data_chunk = self.env.cr.dictfetchall()
        except Exception as e:
            _logger.error(f"Database query failed for '{self.name}': {e}")
            self.env.cr.rollback()
            return False

        if not data_chunk:
            self.write({'export_complete': True})
            _logger.info("🛑 No more records to sync for %s. Marked as complete.", self.name)
            return False

        df = pd.DataFrame(data_chunk)

        if params['main_table'].endswith('_rel'):
            last_row = max(data_chunk, key=lambda r: r[params['first_sorted_column']])
            latest_write_date = fields.Datetime.now()
            latest_id = last_row[params['first_sorted_column']]
        else:
            last_row = max(data_chunk, key=lambda r: (r['write_date'], r['id']))
            latest_write_date = last_row['write_date']
            latest_id = last_row['id']

        sanitized_table = self.name.replace('.', '_').replace('-', '_').replace(' ', '_')
        target_table_id = f"{client.project}.{dataset_id}.{sanitized_table}"
        staging_table_id = f"{target_table_id}_staging_{int(time.time())}"

        # ✅ Stable schema (reuse BQ if exists, else from Postgres)
        schema_map, schema_fields = self._stable_schema_map_and_fields(
            client, target_table_id, df.columns.tolist()
        )

        # ✅ Transform strictly using the stable schema (no pandas dtype inference)
        self._transform_dataframe(df, schema_map)

        job_config_staging = bigquery.LoadJobConfig(
            schema=schema_fields,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        )

        load_job = client.load_table_from_dataframe(df, staging_table_id, job_config=job_config_staging)
        load_job.result()
        _logger.info(f"Staging table {staging_table_id} loaded. Job ID: {load_job.job_id}")

        table_ref = bigquery.Table(target_table_id, schema=schema_fields)
        client.create_table(table_ref, exists_ok=True)

        all_columns = df.columns.tolist()

        if params['main_table'].endswith('_rel'):
            update_columns = [col for col in all_columns if col != params['first_sorted_column']]
            set_clause = ", ".join([f"Target.{col} = Source.{col}" for col in update_columns])
            insert_columns_clause = ", ".join([f"{col}" for col in all_columns])
            source_columns_clause = ", ".join([f"Source.{col}" for col in all_columns])
            merge_sql = f"""
                MERGE {target_table_id} AS Target
                USING {staging_table_id} AS Source
                ON CAST(Target.{params['first_sorted_column']} AS STRING) = CAST(Source.{params['first_sorted_column']} AS STRING)
                WHEN MATCHED THEN
                    UPDATE SET {set_clause}
                WHEN NOT MATCHED THEN
                    INSERT ({insert_columns_clause})
                    VALUES ({source_columns_clause})
            """
        else:
            update_columns = [col for col in all_columns if col != 'id']
            set_clause = ", ".join([f"Target.{col} = Source.{col}" for col in update_columns])
            insert_columns_clause = ", ".join([f"{col}" for col in all_columns])
            source_columns_clause = ", ".join([f"Source.{col}" for col in all_columns])
            merge_sql = f"""
                MERGE {target_table_id} AS Target
                USING {staging_table_id} AS Source
                ON CAST(Target.id AS STRING) = CAST(Source.id AS STRING)
                WHEN MATCHED THEN
                    UPDATE SET {set_clause}
                WHEN NOT MATCHED THEN
                    INSERT ({insert_columns_clause})
                    VALUES ({source_columns_clause})
            """

        _logger.info(f"Executing MERGE from {staging_table_id} to {target_table_id}...")
        _logger.debug(f"MERGE SQL: {merge_sql}")
        query_job = client.query(merge_sql)
        query_job.result()
        _logger.info(f"MERGE completed. Job ID: {query_job.job_id}. Rows affected: {query_job.num_dml_affected_rows}")

        self.write({
            'last_sync': latest_write_date,
            'last_sync_id': latest_id
        })

        try:
            _logger.info(f"Dropping staging table {staging_table_id}...")
            client.delete_table(staging_table_id, not_found_ok=True)
        except Exception as cleanup_err:
            _logger.error(f"Failed to drop staging table {staging_table_id}: {cleanup_err}")

        return True


    def _has_new_records(self):
        last_sync = self.last_sync or '1970-01-01 00:00:00'
        last_id = self.last_sync_id or 0
        quoted_table = '.'.join(f'"{part.strip()}"' for part in self.table_name.split('.'))

        if self.table_name.endswith('_rel'):
            self.env.cr.execute(f"SELECT * FROM {self.table_name} LIMIT 0")
            columns = [col[0] for col in self.env.cr.description]
            rel_id = sorted(columns)[0]
            query = f"""
                SELECT {rel_id} FROM {quoted_table}
                WHERE ({rel_id} > %s)
                LIMIT 1
            """
            self.env.cr.execute(query, (last_id))
        else:
            query = f"""
                SELECT id FROM {quoted_table}
                WHERE (write_date > %s)
                OR (write_date = %s AND id > %s)
                LIMIT 1
            """
            self.env.cr.execute(query, (last_sync, last_sync, last_id))
        res = self.env.cr.fetchone()
        return bool(res)

    def cron_run_queries(self):
        now = fields.Datetime.now()
        all_queries = self.search([
            ('is_locked', '=', False),
            ('incremental_sync_enabled', '=', True)
        ])

        for query in all_queries:
            last_sync = query.last_sync or datetime(1970, 1, 1)
            interval = query.interval_minutes or 15
            if now >= last_sync + timedelta(minutes=interval):
                if query._has_new_records():
                    query.write({'export_complete': False})
                    query.run_query()
            else:
                _logger.info(f"⏳ Skipping query '{query.name}' - waiting for interval ({interval} min)")
