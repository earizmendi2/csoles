from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


EXTRAORDINARY_TYPES = [
    ("advance", "Anticipo"),
    ("freight", "Flete"),
    ("import", "Importación"),
    ("service", "Servicio"),
    ("tax", "Impuestos / Derechos"),
    ("reimbursement", "Reembolso"),
    ("recurring", "Pago recurrente"),
    ("operational", "Urgencia operativa"),
    ("other", "Otro"),
]

PAYMENT_STATES = [
    ("draft", "Borrador"),
    ("submitted", "Por validar"),
    ("validated", "Listo para programar"),
    ("scheduled", "Programado"),
    ("due", "Por pagar"),
    ("paid", "Pagado"),
    ("closed", "Cerrado"),
    ("returned", "Devuelto"),
    ("cancelled", "Cancelado"),
]


class SolesTreasuryConfig(models.Model):
    _name = "soles.treasury.config"
    _description = "Configuración de Tesorería"
    _rec_name = "name"

    name = fields.Char(
        string="Nombre",
        default="Configuración de Tesorería",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    approval_category_ids = fields.Many2many(
        "approval.category",
        "soles_treasury_config_approval_category_rel",
        "config_id",
        "category_id",
        string="Tipos de aprobación habilitados",
        help=(
            "Solo las aprobaciones pertenecientes a estas categorías "
            "podrán vincularse con solicitudes de pago."
        ),
    )
    default_team_id = fields.Many2one(
        "soles.treasury.team",
        string="Equipo de Tesorería predeterminado",
        domain="[('company_id', '=', company_id)]",
    )
    alert_day_1 = fields.Integer(string="Primer aviso (días antes)", default=7)
    alert_day_2 = fields.Integer(string="Segundo aviso (días antes)", default=3)
    alert_day_3 = fields.Integer(string="Tercer aviso (días antes)", default=1)
    alert_on_due_date = fields.Boolean(string="Avisar el día del pago", default=True)

    _sql_constraints = [
        (
            "company_unique",
            "unique(company_id)",
            "Solo puede existir una configuración de Tesorería por compañía.",
        )
    ]

    @api.model
    def get_for_company(self, company=None):
        company = company or self.env.company
        return self.sudo().search([("company_id", "=", company.id)], limit=1)

    def get_alert_days(self):
        self.ensure_one()
        days = {self.alert_day_1, self.alert_day_2, self.alert_day_3}
        days = {day for day in days if day is not None and day >= 0}
        if self.alert_on_due_date:
            days.add(0)
        return sorted(days, reverse=True)


class SolesTreasuryTeam(models.Model):
    _name = "soles.treasury.team"
    _description = "Equipo de Tesorería"
    _order = "name"

    name = fields.Char(string="Nombre", required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    manager_id = fields.Many2one(
        "res.users",
        string="Responsable",
        domain=[("share", "=", False)],
    )
    member_ids = fields.Many2many(
        "res.users",
        "soles_treasury_team_user_rel",
        "team_id",
        "user_id",
        string="Miembros",
        domain=[("share", "=", False)],
    )
    description = fields.Text(string="Descripción")


class SolesPaymentRequest(models.Model):
    _name = "soles.payment.request"
    _description = "Solicitud de Pago"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "scheduled_payment_date asc, id desc"

    name = fields.Char(
        string="Folio",
        default="Nuevo",
        readonly=True,
        copy=False,
        tracking=True,
    )
    state = fields.Selection(
        PAYMENT_STATES,
        string="Estado",
        default="draft",
        tracking=True,
        copy=False,
    )
    origin_type = fields.Selection(
        [("approval", "Aprobación"), ("extraordinary", "Extraordinaria")],
        string="Origen",
        required=True,
        default="extraordinary",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Solicitante",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    department_id = fields.Many2one("hr.department", string="Departamento", tracking=True)

    # Aprobación
    allowed_approval_category_ids = fields.Many2many(
        "approval.category",
        compute="_compute_allowed_approval_categories",
        string="Tipos de aprobación permitidos",
    )
    approval_request_id = fields.Many2one(
        "approval.request",
        string="Aprobación vinculada",
        tracking=True,
        ondelete="restrict",
    )
    approval_category_id = fields.Many2one(
        "approval.category",
        related="approval_request_id.category_id",
        string="Tipo de aprobación",
        store=True,
        readonly=True,
    )
    approval_amount = fields.Float(string="Monto aprobado", compute="_compute_approval_amounts")
    approval_available_amount = fields.Float(
        string="Saldo disponible",
        compute="_compute_approval_amounts",
    )

    # Extraordinario
    extraordinary_type = fields.Selection(EXTRAORDINARY_TYPES, string="Tipo extraordinario", tracking=True)
    extraordinary_reason = fields.Text(string="Justificación", tracking=True)

    # Proveedor / concepto
    partner_id = fields.Many2one(
        "res.partner",
        string="Proveedor / Beneficiario",
        tracking=True,
    )
    description = fields.Html(string="Concepto / Descripción", tracking=True)
    reference = fields.Char(string="Referencia", tracking=True)
    amount = fields.Monetary(
        string="Monto solicitado",
        currency_field="currency_id",
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    # Factura / archivos
    invoice_number = fields.Char(string="Folio de factura", tracking=True)
    invoice_date = fields.Date(string="Fecha de factura", tracking=True)
    invoice_due_date = fields.Date(string="Vencimiento de factura", tracking=True)
    invoice_pdf = fields.Binary(string="Factura PDF", attachment=True)
    invoice_pdf_filename = fields.Char(string="Nombre PDF")
    invoice_xml = fields.Binary(string="XML CFDI", attachment=True)
    invoice_xml_filename = fields.Char(string="Nombre XML")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "soles_payment_request_attachment_rel",
        "request_id",
        "attachment_id",
        string="Otros documentos",
    )

    # Programación
    request_date = fields.Date(
        string="Fecha de solicitud",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    requested_payment_date = fields.Date(string="Fecha requerida", tracking=True)
    scheduled_payment_date = fields.Date(string="Fecha programada", tracking=True)
    actual_payment_date = fields.Date(string="Fecha real de pago", readonly=True, tracking=True)
    team_id = fields.Many2one("soles.treasury.team", string="Equipo de Tesorería", tracking=True)
    treasury_responsible_id = fields.Many2one(
        "res.users",
        string="Responsable de Tesorería",
        tracking=True,
        domain=[("share", "=", False)],
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Importante"), ("2", "Urgente")],
        string="Prioridad",
        default="0",
        tracking=True,
    )
    recurrence_id = fields.Many2one(
        "soles.payment.recurrence",
        string="Pago recurrente",
        readonly=True,
        copy=False,
    )
    last_alert_date = fields.Date(copy=False, readonly=True)
    overdue_alert_sent = fields.Boolean(copy=False, readonly=True)
    overdue = fields.Boolean(string="Vencido", compute="_compute_overdue")

    @api.depends("company_id")
    def _compute_allowed_approval_categories(self):
        Config = self.env["soles.treasury.config"]
        for record in self:
            config = Config.get_for_company(record.company_id or self.env.company)
            record.allowed_approval_category_ids = config.approval_category_ids if config else False

    @api.depends("approval_request_id", "approval_request_id.amount", "amount")
    def _compute_approval_amounts(self):
        for record in self:
            record.approval_amount = 0.0
            record.approval_available_amount = 0.0
            approval = record.approval_request_id
            if not approval:
                continue
            approval_amount = approval.amount or 0.0
            other_requests = approval.payment_request_ids.filtered(
                lambda request: request.id != record.id and request.state != "cancelled"
            )
            used_amount = sum(other_requests.mapped("amount"))
            record.approval_amount = approval_amount
            record.approval_available_amount = max(approval_amount - used_amount, 0.0)

    @api.depends("scheduled_payment_date", "state")
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.overdue = bool(
                record.scheduled_payment_date
                and record.scheduled_payment_date < today
                and record.state in ("scheduled", "due")
            )

    @api.model_create_multi
    def create(self, vals_list):
        Config = self.env["soles.treasury.config"]
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("soles.payment.request") or "Nuevo"

            approval = False
            if vals.get("approval_request_id"):
                approval = self.env["approval.request"].browse(vals["approval_request_id"])
                vals.setdefault("origin_type", "approval")
                vals.setdefault("requester_id", approval.request_owner_id.id or self.env.user.id)
                vals.setdefault("partner_id", approval.partner_id.id if approval.partner_id else False)
                vals.setdefault("amount", approval.amount or 0.0)
                vals.setdefault("description", approval.reason or approval.name)
                approval_company = approval.category_id.company_id
                if approval_company:
                    vals.setdefault("company_id", approval_company.id)

            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
            config = Config.get_for_company(company)
            if config and config.default_team_id and not vals.get("team_id"):
                vals["team_id"] = config.default_team_id.id
                if config.default_team_id.manager_id and not vals.get("treasury_responsible_id"):
                    vals["treasury_responsible_id"] = config.default_team_id.manager_id.id

        return super().create(vals_list)

    @api.onchange("origin_type")
    def _onchange_origin_type(self):
        if self.origin_type == "extraordinary":
            self.approval_request_id = False
        elif self.origin_type == "approval":
            self.extraordinary_type = False
            self.extraordinary_reason = False

    @api.onchange("approval_request_id")
    def _onchange_approval_request_id(self):
        approval = self.approval_request_id
        if not approval:
            return
        self.origin_type = "approval"
        if approval.category_id.company_id:
            self.company_id = approval.category_id.company_id
        self.requester_id = approval.request_owner_id or self.env.user
        self.partner_id = approval.partner_id
        self.amount = approval.amount
        self.description = approval.reason or approval.name
        employee = self.requester_id.employee_id
        if employee:
            self.department_id = employee.department_id

    @api.onchange("team_id")
    def _onchange_team_id(self):
        if self.team_id and self.team_id.manager_id:
            self.treasury_responsible_id = self.team_id.manager_id

    @api.constrains("origin_type", "approval_request_id", "company_id")
    def _check_approval_origin(self):
        Config = self.env["soles.treasury.config"]
        for record in self:
            if record.origin_type != "approval":
                continue
            if not record.approval_request_id:
                raise ValidationError(_("Debe seleccionar una aprobación para una solicitud con origen Aprobación."))
            approval = record.approval_request_id
            config = Config.get_for_company(record.company_id)
            if not config:
                raise ValidationError(_("No existe una configuración de Tesorería para esta compañía."))
            if approval.category_id not in config.approval_category_ids:
                raise ValidationError(
                    _("El tipo de aprobación '%s' no está habilitado para generar solicitudes de pago.")
                    % approval.category_id.display_name
                )
            if approval.request_status != "approved":
                raise ValidationError(_("Solo pueden vincularse aprobaciones que ya se encuentren aprobadas."))

    def _validate_approval_amount(self):
        for record in self:
            if record.origin_type != "approval" or not record.approval_request_id:
                continue
            approval = record.approval_request_id
            if not approval.amount:
                continue
            other_requests = approval.payment_request_ids.filtered(
                lambda request: request.id != record.id and request.state != "cancelled"
            )
            used_amount = sum(other_requests.mapped("amount"))
            if used_amount + record.amount > approval.amount + 0.01:
                raise ValidationError(
                    _(
                        "El monto solicitado excede el monto disponible de la aprobación.\n\n"
                        "Monto aprobado: %(approved).2f\n"
                        "Solicitado anteriormente: %(used).2f\n"
                        "Solicitud actual: %(current).2f"
                    )
                    % {
                        "approved": approval.amount,
                        "used": used_amount,
                        "current": record.amount,
                    }
                )

    def _validate_before_submit(self):
        for record in self:
            if not record.partner_id:
                raise UserError(_("Debe indicar el proveedor o beneficiario."))
            if record.amount <= 0:
                raise UserError(_("El monto de la solicitud debe ser mayor a cero."))
            if record.origin_type == "approval":
                if not record.approval_request_id:
                    raise UserError(_("Debe seleccionar una aprobación."))
                record._check_approval_origin()
                record._validate_approval_amount()
            elif record.origin_type == "extraordinary":
                if not record.extraordinary_type:
                    raise UserError(_("Seleccione el tipo de pago extraordinario."))
                if not record.extraordinary_reason:
                    raise UserError(_("Las solicitudes extraordinarias requieren una justificación."))

    def _require_treasury_user(self):
        if not self.env.user.has_group("soles_treasury.group_treasury_user"):
            raise AccessError(_("Esta acción está reservada para Tesorería."))

    def _require_finance_manager(self):
        if not self.env.user.has_group("soles_treasury.group_finance_manager"):
            raise AccessError(_("Esta acción requiere permisos de Administración y Finanzas."))

    def action_submit(self):
        for record in self:
            if record.state not in ("draft", "returned"):
                continue
            record._validate_before_submit()
            record.state = "submitted"
        return True

    def action_validate(self):
        self._require_treasury_user()
        for record in self:
            if record.state != "submitted":
                continue
            record._validate_before_submit()
            record.state = "validated"
        return True

    def action_schedule(self):
        self._require_treasury_user()
        today = fields.Date.context_today(self)
        for record in self:
            if record.state != "validated":
                continue
            if not record.scheduled_payment_date:
                raise UserError(_("Debe indicar una fecha programada antes de programar el pago."))
            if not record.treasury_responsible_id:
                raise UserError(_("Debe asignar un responsable de Tesorería."))
            record.write(
                {
                    "state": "due" if record.scheduled_payment_date <= today else "scheduled",
                    "last_alert_date": False,
                    "overdue_alert_sent": False,
                }
            )
        return True

    def action_mark_paid(self):
        self._require_treasury_user()
        for record in self:
            if record.state not in ("scheduled", "due"):
                continue
            record.write(
                {
                    "state": "paid",
                    "actual_payment_date": fields.Date.context_today(record),
                }
            )
        return True

    def action_close(self):
        self._require_finance_manager()
        for record in self:
            if record.state != "paid":
                raise UserError(_("Solo puede cerrarse una solicitud que ya esté pagada."))
            record.state = "closed"
        return True

    def action_return(self):
        self._require_treasury_user()
        for record in self:
            if record.state in ("submitted", "validated", "scheduled", "due"):
                record.state = "returned"
        return True

    def action_cancel(self):
        for record in self:
            if record.state in ("paid", "closed"):
                raise UserError(_("No puede cancelarse una solicitud que ya fue pagada."))
            if record.requester_id != self.env.user and not self.env.user.has_group(
                "soles_treasury.group_treasury_manager"
            ):
                raise AccessError(_("No tiene permiso para cancelar esta solicitud."))
            record.state = "cancelled"
        return True

    def action_view_approval(self):
        self.ensure_one()
        if not self.approval_request_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Aprobación"),
            "res_model": "approval.request",
            "view_mode": "form",
            "res_id": self.approval_request_id.id,
            "target": "current",
        }

    @api.model
    def _cron_process_payment_alerts(self):
        today = fields.Date.context_today(self)
        records = self.search(
            [
                ("state", "in", ["scheduled", "due"]),
                ("scheduled_payment_date", "!=", False),
            ]
        )
        Config = self.env["soles.treasury.config"]
        for record in records:
            payment_date = record.scheduled_payment_date
            if payment_date <= today and record.state == "scheduled":
                record.state = "due"
            delta = (payment_date - today).days
            config = Config.get_for_company(record.company_id)
            alert_days = config.get_alert_days() if config else [7, 3, 1, 0]
            responsible = record.treasury_responsible_id or record.team_id.manager_id
            if responsible and delta in alert_days and record.last_alert_date != today:
                record.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=responsible.id,
                    date_deadline=today,
                    summary=_("Pago próximo: %s") % record.name,
                    note=_(
                        "El pago a %(partner)s por %(amount).2f %(currency)s "
                        "está programado para %(date)s."
                    )
                    % {
                        "partner": record.partner_id.display_name,
                        "amount": record.amount,
                        "currency": record.currency_id.name,
                        "date": payment_date,
                    },
                )
                record.last_alert_date = today
            if responsible and delta < 0 and not record.overdue_alert_sent:
                record.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=responsible.id,
                    date_deadline=today,
                    summary=_("Pago vencido: %s") % record.name,
                    note=_("La solicitud de pago venció el %s y continúa pendiente.") % payment_date,
                )
                record.overdue_alert_sent = True
        return True


class SolesPaymentRecurrence(models.Model):
    _name = "soles.payment.recurrence"
    _description = "Pago Recurrente"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "next_date asc"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Proveedor / Beneficiario",
        required=True,
        tracking=True,
    )
    description = fields.Text(string="Concepto")
    estimated_amount = fields.Monetary(
        string="Monto estimado",
        currency_field="currency_id",
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    frequency = fields.Selection(
        [
            ("weekly", "Semanal"),
            ("biweekly", "Quincenal"),
            ("monthly", "Mensual"),
            ("bimonthly", "Bimestral"),
            ("quarterly", "Trimestral"),
            ("semiannual", "Semestral"),
            ("annual", "Anual"),
            ("custom", "Personalizada"),
        ],
        required=True,
        default="monthly",
        tracking=True,
    )
    custom_interval = fields.Integer(string="Cada", default=1)
    custom_interval_unit = fields.Selection(
        [("days", "Días"), ("weeks", "Semanas"), ("months", "Meses"), ("years", "Años")],
        string="Unidad",
        default="months",
    )
    start_date = fields.Date(
        string="Fecha inicial",
        required=True,
        default=fields.Date.context_today,
    )
    next_date = fields.Date(
        string="Próxima fecha",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    generation_mode = fields.Selection(
        [("alert", "Solo alerta"), ("draft", "Crear solicitud en borrador")],
        string="Acción automática",
        default="alert",
        required=True,
    )
    generation_lead_days = fields.Integer(
        string="Crear solicitud con anticipación (días)",
        default=7,
    )
    alert_days = fields.Char(
        string="Alertar días antes",
        default="7,3,1,0",
        help="Ejemplo: 30,15,7,3,1,0",
    )
    team_id = fields.Many2one("soles.treasury.team", string="Equipo")
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsable",
        tracking=True,
        domain=[("share", "=", False)],
    )
    extraordinary_type = fields.Selection(EXTRAORDINARY_TYPES, string="Tipo de pago", default="recurring")
    last_alert_date = fields.Date(readonly=True, copy=False)
    last_generated_for_date = fields.Date(readonly=True, copy=False)
    payment_request_ids = fields.One2many(
        "soles.payment.request",
        "recurrence_id",
        string="Solicitudes generadas",
    )
    payment_request_count = fields.Integer(
        string="Solicitudes generadas",
        compute="_compute_payment_request_count",
    )

    @api.depends("payment_request_ids")
    def _compute_payment_request_count(self):
        for record in self:
            record.payment_request_count = len(record.payment_request_ids)

    @api.onchange("team_id")
    def _onchange_team_id(self):
        if self.team_id and self.team_id.manager_id:
            self.responsible_id = self.team_id.manager_id

    @api.constrains("generation_lead_days", "custom_interval")
    def _check_positive_intervals(self):
        for record in self:
            if record.generation_lead_days < 0:
                raise ValidationError(_("Los días de anticipación no pueden ser negativos."))
            if record.frequency == "custom" and record.custom_interval <= 0:
                raise ValidationError(_("El intervalo personalizado debe ser mayor a cero."))

    def _parse_alert_days(self):
        self.ensure_one()
        result = []
        for value in (self.alert_days or "").split(","):
            value = value.strip()
            if not value:
                continue
            try:
                number = int(value)
            except ValueError:
                continue
            if number >= 0:
                result.append(number)
        return sorted(set(result), reverse=True)

    def _prepare_payment_request_vals(self):
        self.ensure_one()
        return {
            "origin_type": "extraordinary",
            "extraordinary_type": self.extraordinary_type or "recurring",
            "extraordinary_reason": _("Solicitud generada desde el pago recurrente '%s'.") % self.name,
            "partner_id": self.partner_id.id,
            "description": self.description or self.name,
            "amount": self.estimated_amount,
            "currency_id": self.currency_id.id,
            "company_id": self.company_id.id,
            "team_id": self.team_id.id,
            "treasury_responsible_id": self.responsible_id.id,
            "requested_payment_date": self.next_date,
            "recurrence_id": self.id,
        }

    def _create_payment_request(self):
        self.ensure_one()
        request = self.env["soles.payment.request"].create(self._prepare_payment_request_vals())
        self.last_generated_for_date = self.next_date
        return request

    def action_generate_payment_request(self):
        self.ensure_one()
        request = self._create_payment_request()
        return {
            "type": "ir.actions.act_window",
            "name": _("Solicitud de Pago"),
            "res_model": "soles.payment.request",
            "view_mode": "form",
            "res_id": request.id,
            "target": "current",
        }

    def action_view_payment_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Solicitudes generadas"),
            "res_model": "soles.payment.request",
            "view_mode": "list,form",
            "domain": [("recurrence_id", "=", self.id)],
            "context": {"create": False},
        }

    def _get_next_date(self):
        self.ensure_one()
        current = self.next_date
        if self.frequency == "weekly":
            return current + relativedelta(weeks=1)
        if self.frequency == "biweekly":
            return current + relativedelta(days=15)
        if self.frequency == "monthly":
            return current + relativedelta(months=1)
        if self.frequency == "bimonthly":
            return current + relativedelta(months=2)
        if self.frequency == "quarterly":
            return current + relativedelta(months=3)
        if self.frequency == "semiannual":
            return current + relativedelta(months=6)
        if self.frequency == "annual":
            return current + relativedelta(years=1)
        interval = max(self.custom_interval, 1)
        if self.custom_interval_unit == "days":
            return current + relativedelta(days=interval)
        if self.custom_interval_unit == "weeks":
            return current + relativedelta(weeks=interval)
        if self.custom_interval_unit == "years":
            return current + relativedelta(years=interval)
        return current + relativedelta(months=interval)

    @api.model
    def _cron_process_recurrences(self):
        today = fields.Date.context_today(self)
        records = self.search([("active", "=", True), ("next_date", "!=", False)])
        for record in records:
            delta = (record.next_date - today).days
            responsible = record.responsible_id or record.team_id.manager_id
            if responsible and delta in record._parse_alert_days() and record.last_alert_date != today:
                record.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=responsible.id,
                    date_deadline=today,
                    summary=_("Pago recurrente próximo: %s") % record.name,
                    note=_("%(partner)s tiene un pago recurrente programado para %(date)s.")
                    % {"partner": record.partner_id.display_name, "date": record.next_date},
                )
                record.last_alert_date = today

            if (
                record.generation_mode == "draft"
                and delta <= record.generation_lead_days
                and record.last_generated_for_date != record.next_date
            ):
                record._create_payment_request()

            if today >= record.next_date:
                new_next = record._get_next_date()
                while new_next <= today:
                    record.next_date = new_next
                    new_next = record._get_next_date()
                record.write({"next_date": new_next, "last_alert_date": False})
        return True


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    payment_request_ids = fields.One2many(
        "soles.payment.request",
        "approval_request_id",
        string="Solicitudes de pago",
    )
    payment_request_count = fields.Integer(compute="_compute_payment_requests", string="Solicitudes de pago")
    payment_requested_total = fields.Float(compute="_compute_payment_requests", string="Total solicitado")
    payment_paid_total = fields.Float(compute="_compute_payment_requests", string="Total pagado")
    treasury_payment_enabled = fields.Boolean(compute="_compute_treasury_payment_enabled")

    @api.depends("payment_request_ids", "payment_request_ids.amount", "payment_request_ids.state")
    def _compute_payment_requests(self):
        for approval in self:
            valid_requests = approval.payment_request_ids.filtered(lambda request: request.state != "cancelled")
            approval.payment_request_count = len(valid_requests)
            approval.payment_requested_total = sum(valid_requests.mapped("amount"))
            approval.payment_paid_total = sum(
                valid_requests.filtered(lambda request: request.state in ("paid", "closed")).mapped("amount")
            )

    @api.depends("category_id")
    def _compute_treasury_payment_enabled(self):
        Config = self.env["soles.treasury.config"]
        for approval in self:
            approval_company = approval.category_id.company_id or self.env.company
            config = Config.get_for_company(approval_company)
            approval.treasury_payment_enabled = bool(
                config and approval.category_id in config.approval_category_ids
            )

    def action_create_payment_request(self):
        self.ensure_one()
        if self.request_status != "approved":
            raise UserError(_("La aprobación debe estar completamente aprobada antes de generar una solicitud de pago."))
        if not self.treasury_payment_enabled:
            raise UserError(_("Este tipo de aprobación no está habilitado en la configuración de Tesorería."))
        approval_company = self.category_id.company_id or self.env.company
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva Solicitud de Pago"),
            "res_model": "soles.payment.request",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_origin_type": "approval",
                "default_approval_request_id": self.id,
                "default_company_id": approval_company.id,
                "default_requester_id": self.request_owner_id.id or self.env.user.id,
                "default_partner_id": self.partner_id.id if self.partner_id else False,
                "default_amount": self.amount,
                "default_description": self.reason or self.name,
            },
        }

    def action_view_payment_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Solicitudes de Pago"),
            "res_model": "soles.payment.request",
            "view_mode": "list,form",
            "domain": [("approval_request_id", "=", self.id)],
            "context": {
                "default_origin_type": "approval",
                "default_approval_request_id": self.id,
            },
        }
