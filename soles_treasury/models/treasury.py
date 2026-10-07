from datetime import timedelta

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
    ("due", "Por pagar hoy"),
    ("overdue", "Atrasado"),
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
    reviewer_id = fields.Many2one(
        "res.users",
        string="Revisor predeterminado",
        domain=[("share", "=", False)],
        help="Usuario de Tesorería que recibirá las solicitudes nuevas para su revisión y validación.",
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
    payment_schedule_line_ids = fields.One2many(
        "soles.treasury.payment.schedule",
        "team_id",
        string="Fechas / días autorizados de pago",
    )
    payment_schedule_summary = fields.Char(
        string="Calendario de pagos",
        compute="_compute_payment_schedule_summary",
    )

    @api.depends(
        "payment_schedule_line_ids",
        "payment_schedule_line_ids.active",
        "payment_schedule_line_ids.schedule_type",
        "payment_schedule_line_ids.weekday",
        "payment_schedule_line_ids.day_of_month",
        "payment_schedule_line_ids.specific_date",
    )
    def _compute_payment_schedule_summary(self):
        for team in self:
            labels = team.payment_schedule_line_ids.filtered("active").mapped("name")
            team.payment_schedule_summary = ", ".join(labels) if labels else _("Sin restricción de fechas")

    def is_payment_date_allowed(self, payment_date):
        self.ensure_one()
        if not payment_date:
            return False
        lines = self.payment_schedule_line_ids.filtered("active")
        if not lines:
            return True
        return any(line.matches_date(payment_date) for line in lines)

    def get_next_allowed_payment_date(self, from_date, max_days=730):
        self.ensure_one()
        if not from_date:
            from_date = fields.Date.context_today(self)
        if not self.payment_schedule_line_ids.filtered("active"):
            return from_date
        for offset in range(max_days + 1):
            candidate = from_date + timedelta(days=offset)
            if self.is_payment_date_allowed(candidate):
                return candidate
        return False


class SolesTreasuryPaymentSchedule(models.Model):
    _name = "soles.treasury.payment.schedule"
    _description = "Calendario permitido de pagos de Tesorería"
    _order = "schedule_type, weekday, day_of_month, specific_date, id"

    WEEKDAYS = [
        ("0", "Lunes"),
        ("1", "Martes"),
        ("2", "Miércoles"),
        ("3", "Jueves"),
        ("4", "Viernes"),
        ("5", "Sábado"),
        ("6", "Domingo"),
    ]

    name = fields.Char(string="Descripción", compute="_compute_name")
    team_id = fields.Many2one(
        "soles.treasury.team",
        string="Equipo de Tesorería",
        required=True,
        ondelete="cascade",
    )
    active = fields.Boolean(default=True)
    schedule_type = fields.Selection(
        [
            ("weekday", "Día de la semana"),
            ("month_day", "Día del mes"),
            ("specific", "Fecha específica"),
        ],
        string="Tipo",
        required=True,
        default="weekday",
    )
    weekday = fields.Selection(WEEKDAYS, string="Día de la semana")
    day_of_month = fields.Integer(string="Día del mes")
    specific_date = fields.Date(string="Fecha específica")

    @api.depends("schedule_type", "weekday", "day_of_month", "specific_date")
    def _compute_name(self):
        weekday_labels = dict(self.WEEKDAYS)
        for line in self:
            if line.schedule_type == "weekday":
                line.name = weekday_labels.get(line.weekday, _("Día semanal sin definir"))
            elif line.schedule_type == "month_day":
                line.name = _(f"Día {line.day_of_month} de cada mes") if line.day_of_month else _("Día mensual sin definir")
            elif line.specific_date:
                line.name = fields.Date.to_string(line.specific_date)
            else:
                line.name = _("Fecha específica sin definir")

    @api.constrains("schedule_type", "weekday", "day_of_month", "specific_date")
    def _check_schedule_value(self):
        for line in self:
            if line.schedule_type == "weekday" and line.weekday is False:
                raise ValidationError(_("Seleccione un día de la semana."))
            if line.schedule_type == "month_day" and not 1 <= line.day_of_month <= 31:
                raise ValidationError(_("El día del mes debe estar entre 1 y 31."))
            if line.schedule_type == "specific" and not line.specific_date:
                raise ValidationError(_("Indique la fecha específica de pago."))

    def matches_date(self, payment_date):
        self.ensure_one()
        if not self.active or not payment_date:
            return False
        if self.schedule_type == "weekday":
            return self.weekday == str(payment_date.weekday())
        if self.schedule_type == "month_day":
            return self.day_of_month == payment_date.day
        return self.specific_date == payment_date


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
        [("approval", "Aprobación"), ("extraordinary", "Extraordinaria"), ("recurring", "Pago recurrente")],
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
    description = fields.Html(string="Concepto / Descripción")
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
    invoice_date = fields.Date(
        string="Fecha de factura",
        tracking=True,
        help="Fecha de emisión indicada en la factura o documento del proveedor.",
    )
    invoice_due_date = fields.Date(
        string="Vencimiento de factura",
        tracking=True,
        help="Fecha límite indicada por el proveedor para liquidar la factura. No necesariamente es la fecha en que Tesorería programará el pago.",
    )
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
        help="Fecha en que la solicitud de pago fue creada o enviada al proceso de Tesorería.",
    )
    requested_payment_date = fields.Date(
        string="Fecha requerida",
        tracking=True,
        help="Fecha en la que el solicitante necesita o propone que se realice el pago. Es una referencia para Tesorería y no garantiza que el pago se ejecute ese día.",
    )
    scheduled_payment_date = fields.Date(
        string="Fecha programada",
        tracking=True,
        help="Fecha definitiva asignada por Tesorería para ejecutar el pago. Solo los usuarios de Tesorería pueden modificarla.",
    )
    actual_payment_date = fields.Date(
        string="Fecha real de pago",
        readonly=True,
        tracking=True,
        help="Fecha en que Tesorería confirmó el pago y adjuntó el comprobante correspondiente.",
    )
    team_id = fields.Many2one("soles.treasury.team", string="Equipo de Tesorería", tracking=True)
    team_payment_schedule_summary = fields.Char(
        related="team_id.payment_schedule_summary",
        string="Fechas permitidas del equipo",
        readonly=True,
    )
    reviewer_id = fields.Many2one(
        "res.users",
        string="Revisor de Tesorería",
        tracking=True,
        domain=[("share", "=", False)],
        help="Persona encargada de revisar y validar la solicitud antes de que se programe el pago.",
    )
    treasury_responsible_id = fields.Many2one(
        "res.users",
        string="Responsable de Tesorería",
        tracking=True,
        domain=[("share", "=", False)],
        help="Persona encargada de programar y dar seguimiento a la ejecución del pago.",
    )
    schedule_exception = fields.Boolean(
        string="Pago fuera de calendario",
        tracking=True,
        help="Permite a Tesorería programar de forma extraordinaria el pago en una fecha distinta a los días de pago definidos para el equipo. Requiere justificación y queda auditado.",
    )
    schedule_exception_reason = fields.Text(
        string="Motivo del pago fuera de calendario",
        tracking=True,
    )
    schedule_exception_user_id = fields.Many2one(
        "res.users",
        string="Excepción registrada por",
        readonly=True,
        copy=False,
    )
    schedule_exception_date = fields.Datetime(
        string="Fecha de excepción",
        readonly=True,
        copy=False,
    )
    payment_receipt = fields.Binary(
        string="Comprobante de pago",
        attachment=True,
        copy=False,
        help="Comprobante bancario o evidencia de que el pago fue ejecutado. Es obligatorio antes de marcar la solicitud como pagada.",
    )
    payment_receipt_filename = fields.Char(
        string="Nombre del comprobante",
        copy=False,
    )
    payment_reference = fields.Char(
        string="Referencia de pago",
        tracking=True,
        copy=False,
        help="Referencia, folio, número de operación o dato bancario que permita identificar el pago realizado.",
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
                record.state == "overdue"
                or (
                    record.scheduled_payment_date
                    and record.scheduled_payment_date < today
                    and record.state in ("scheduled", "due", "overdue")
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        Config = self.env["soles.treasury.config"]
        is_treasury = self.env.user.has_group("soles_treasury.group_treasury_user")
        for vals in vals_list:
            if vals.get("scheduled_payment_date") and not is_treasury:
                raise AccessError(_("Solo Tesorería puede asignar la fecha programada de pago."))
            if vals.get("payment_receipt") and not is_treasury:
                raise AccessError(_("Solo Tesorería puede adjuntar o modificar el comprobante de pago."))
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
                default_reviewer = config.default_team_id.reviewer_id or config.default_team_id.manager_id
                if default_reviewer and not vals.get("reviewer_id"):
                    vals["reviewer_id"] = default_reviewer.id
                if config.default_team_id.manager_id and not vals.get("treasury_responsible_id"):
                    vals["treasury_responsible_id"] = config.default_team_id.manager_id.id

        records = super().create(vals_list)
        records._sync_date_state()
        return records

    def write(self, vals):
        vals = dict(vals)
        is_treasury = self.env.user.has_group("soles_treasury.group_treasury_user")
        internal_write = self.env.context.get("skip_treasury_permission_check")

        treasury_only_fields = {
            "scheduled_payment_date",
            "payment_receipt",
            "payment_receipt_filename",
            "payment_reference",
            "schedule_exception",
            "schedule_exception_reason",
        }
        if not internal_write and treasury_only_fields.intersection(vals) and not is_treasury:
            raise AccessError(
                _("Solo Tesorería puede modificar la programación, la excepción de calendario o el comprobante de pago.")
            )

        date_changed = "scheduled_payment_date" in vals
        team_changed = "team_id" in vals
        exception_changed = "schedule_exception" in vals or "schedule_exception_reason" in vals

        if date_changed:
            vals.setdefault("last_alert_date", False)
            vals.setdefault("overdue_alert_sent", False)

        result = super().write(vals)

        if not self.env.context.get("skip_treasury_date_sync") and (date_changed or team_changed or exception_changed):
            for record in self:
                if record.state not in ("scheduled", "due", "overdue"):
                    continue
                if not record.scheduled_payment_date:
                    super(SolesPaymentRequest, record.with_context(
                        skip_treasury_date_sync=True,
                        skip_treasury_permission_check=True,
                    )).write({"state": "validated"})
                    continue
                if record.team_id and not record.team_id.is_payment_date_allowed(record.scheduled_payment_date):
                    if not record.schedule_exception:
                        next_date = record.team_id.get_next_allowed_payment_date(
                            max(record.scheduled_payment_date, fields.Date.context_today(record))
                        )
                        message = _(
                            "La fecha %(date)s no está permitida para el equipo '%(team)s'.\n"
                            "Fechas permitidas: %(schedule)s. Para usar esa fecha, active 'Pago fuera de calendario' y capture el motivo."
                        ) % {
                            "date": record.scheduled_payment_date,
                            "team": record.team_id.display_name,
                            "schedule": record.team_id.payment_schedule_summary,
                        }
                        if next_date:
                            message += _("\nPróxima fecha permitida: %s") % next_date
                        raise UserError(message)
                    if not record.schedule_exception_reason:
                        raise UserError(_("Debe indicar el motivo del pago fuera de calendario."))
            self._sync_date_state()
        return result

    def _state_for_payment_date(self, payment_date, today=None):
        today = today or fields.Date.context_today(self)
        if not payment_date:
            return False
        if payment_date < today:
            return "overdue"
        if payment_date == today:
            return "due"
        return "scheduled"

    def _sync_date_state(self):
        today = fields.Date.context_today(self)
        for record in self:
            if not record.scheduled_payment_date:
                continue
            if record.state not in ("scheduled", "due", "overdue"):
                continue
            expected_state = record._state_for_payment_date(record.scheduled_payment_date, today=today)
            if expected_state and record.state != expected_state:
                super(SolesPaymentRequest, record.with_context(skip_treasury_date_sync=True)).write({
                    "state": expected_state
                })
        return True

    @api.onchange("origin_type")
    def _onchange_origin_type(self):
        if self.origin_type in ("extraordinary", "recurring"):
            self.approval_request_id = False
        if self.origin_type in ("approval", "recurring"):
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
        if self.team_id:
            self.reviewer_id = self.team_id.reviewer_id or self.team_id.manager_id
            if self.team_id.manager_id:
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
            elif record.origin_type == "recurring" and not record.recurrence_id:
                raise UserError(_("Las solicitudes con origen Pago recurrente deben estar vinculadas a una programación recurrente."))

    def _require_treasury_user(self):
        if not self.env.user.has_group("soles_treasury.group_treasury_user"):
            raise AccessError(_("Esta acción está reservada para Tesorería."))

    def _require_finance_manager(self):
        if not self.env.user.has_group("soles_treasury.group_finance_manager"):
            raise AccessError(_("Esta acción requiere permisos de Administración y Finanzas."))

    def _notification_users(self, include_requester=True, include_reviewer=True, include_responsible=True):
        self.ensure_one()
        users = self.env["res.users"]
        if include_requester and self.requester_id:
            users |= self.requester_id
        if include_reviewer and self.reviewer_id:
            users |= self.reviewer_id
        if include_responsible and self.treasury_responsible_id:
            users |= self.treasury_responsible_id
        return users

    def _notify_odoo_users(self, users, body):
        self.ensure_one()
        partners = users.mapped("partner_id").filtered(lambda partner: partner)
        if partners:
            self.message_post(
                body=body,
                partner_ids=partners.ids,
                message_type="notification",
                subtype_xmlid="mail.mt_comment",
            )
        return True

    def _schedule_review_activity(self):
        self.ensure_one()
        reviewer = self.reviewer_id or self.team_id.reviewer_id or self.team_id.manager_id
        if not reviewer:
            return False
        if not self.reviewer_id:
            self.with_context(skip_treasury_permission_check=True).reviewer_id = reviewer
        existing = self.activity_ids.filtered(
            lambda activity: activity.user_id == reviewer
            and activity.activity_type_id == self.env.ref("mail.mail_activity_data_todo")
            and activity.summary == _("Revisar solicitud de pago: %s") % self.name
        )
        if not existing:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=reviewer.id,
                date_deadline=fields.Date.context_today(self),
                summary=_("Revisar solicitud de pago: %s") % self.name,
                note=_("La solicitud %(folio)s fue enviada por %(requester)s y está pendiente de revisión de Tesorería.")
                % {"folio": self.name, "requester": self.requester_id.display_name},
            )
        return True

    def _close_review_activities(self):
        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not todo_type:
            return True
        for record in self:
            activities = record.activity_ids.filtered(
                lambda activity: activity.activity_type_id == todo_type
                and activity.summary == _("Revisar solicitud de pago: %s") % record.name
            )
            if activities:
                activities.action_feedback(feedback=_("Solicitud revisada por Tesorería."))
        return True

    def action_submit(self):
        for record in self:
            if record.state not in ("draft", "returned"):
                continue
            record._validate_before_submit()
            if not record.reviewer_id and record.team_id:
                record.reviewer_id = record.team_id.reviewer_id or record.team_id.manager_id
            if not record.reviewer_id:
                raise UserError(
                    _("No hay un revisor de Tesorería asignado. Configure un revisor predeterminado en el equipo de Tesorería antes de enviar la solicitud.")
                )
            record.state = "submitted"
            record._schedule_review_activity()
            record._notify_odoo_users(
                record._notification_users(include_responsible=False),
                _("La solicitud de pago <b>%(folio)s</b> fue enviada y se encuentra <b>Por validar</b>.")
                % {"folio": record.name},
            )
        return True

    def action_validate(self):
        self._require_treasury_user()
        for record in self:
            if record.state != "submitted":
                continue
            record._validate_before_submit()
            record.state = "validated"
            record._close_review_activities()
            record._notify_odoo_users(
                record._notification_users(),
                _("La solicitud de pago <b>%(folio)s</b> fue revisada y está <b>Lista para programar</b>.")
                % {"folio": record.name},
            )
        return True

    def action_schedule(self):
        self._require_treasury_user()
        today = fields.Date.context_today(self)
        for record in self:
            if record.state != "validated":
                continue
            if not record.scheduled_payment_date:
                raise UserError(_("Debe indicar una fecha programada antes de programar el pago."))
            if not record.team_id:
                raise UserError(_("Debe asignar un equipo de Tesorería."))
            if not record.treasury_responsible_id:
                raise UserError(_("Debe asignar un responsable de Tesorería."))
            date_allowed = record.team_id.is_payment_date_allowed(record.scheduled_payment_date)
            if not date_allowed and not record.schedule_exception:
                next_date = record.team_id.get_next_allowed_payment_date(
                    max(record.scheduled_payment_date, today)
                )
                message = _(
                    "La fecha %(date)s no está dentro de las fechas de pago configuradas para el equipo '%(team)s'.\n"
                    "Fechas permitidas: %(schedule)s. Para realizar un pago extraordinario fuera del calendario, active 'Pago fuera de calendario' e indique el motivo."
                ) % {
                    "date": record.scheduled_payment_date,
                    "team": record.team_id.display_name,
                    "schedule": record.team_id.payment_schedule_summary,
                }
                if next_date:
                    message += _("\nPróxima fecha permitida: %s") % next_date
                raise UserError(message)
            if not date_allowed and record.schedule_exception and not record.schedule_exception_reason:
                raise UserError(_("Debe indicar el motivo del pago fuera de calendario."))

            values = {
                "state": record._state_for_payment_date(record.scheduled_payment_date, today=today),
                "last_alert_date": False,
                "overdue_alert_sent": False,
            }
            if not date_allowed and record.schedule_exception:
                values.update({
                    "schedule_exception_user_id": self.env.user.id,
                    "schedule_exception_date": fields.Datetime.now(),
                })
            elif date_allowed:
                values.update({
                    "schedule_exception": False,
                    "schedule_exception_reason": False,
                    "schedule_exception_user_id": False,
                    "schedule_exception_date": False,
                })
            record.with_context(skip_treasury_permission_check=True).write(values)
            record._notify_odoo_users(
                record._notification_users(),
                _("La solicitud <b>%(folio)s</b> fue programada para el <b>%(date)s</b>.")
                % {"folio": record.name, "date": record.scheduled_payment_date},
            )
            if record.treasury_responsible_id:
                record.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=record.treasury_responsible_id.id,
                    date_deadline=record.scheduled_payment_date,
                    summary=_("Ejecutar pago: %s") % record.name,
                    note=_("Ejecutar el pago programado a %(partner)s por %(amount).2f %(currency)s.")
                    % {
                        "partner": record.partner_id.display_name,
                        "amount": record.amount,
                        "currency": record.currency_id.name,
                    },
                )
        return True

    def action_mark_paid(self):
        self._require_treasury_user()
        for record in self:
            if record.state not in ("scheduled", "due", "overdue"):
                continue
            if not record.payment_receipt:
                raise UserError(
                    _("Debe adjuntar el comprobante de pago antes de marcar la solicitud como pagada.")
                )
            record.with_context(skip_treasury_permission_check=True).write(
                {
                    "state": "paid",
                    "actual_payment_date": fields.Date.context_today(record),
                }
            )
            record._notify_requester_payment_done()
        return True

    def _notify_requester_payment_done(self):
        template = self.env.ref(
            "soles_treasury.mail_template_payment_completed",
            raise_if_not_found=False,
        )
        for record in self:
            requester = record.requester_id
            partner = requester.partner_id if requester else False
            if not partner:
                continue

            body = _(
                "El pago <b>%(folio)s</b> a <b>%(partner)s</b> por "
                "<b>%(amount).2f %(currency)s</b> fue realizado el %(date)s."
            ) % {
                "folio": record.name,
                "partner": record.partner_id.display_name,
                "amount": record.amount,
                "currency": record.currency_id.name,
                "date": record.actual_payment_date,
            }
            record._notify_odoo_users(record._notification_users(), body)

            if template and partner.email:
                template.send_mail(record.id, force_send=False)
            elif not partner.email:
                record.message_post(
                    body=_(
                        "No se envió correo al solicitante %(requester)s porque su contacto no tiene una dirección de correo configurada."
                    ) % {"requester": requester.display_name},
                    subtype_xmlid="mail.mt_note",
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
            if record.state in ("submitted", "validated", "scheduled", "due", "overdue"):
                record.state = "returned"
                record._notify_odoo_users(
                    record._notification_users(),
                    _("La solicitud <b>%(folio)s</b> fue <b>Devuelta</b> para revisión o corrección.")
                    % {"folio": record.name},
                )
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
    def _cron_sync_payment_statuses(self):
        records = self.search(
            [
                ("state", "in", ["scheduled", "due", "overdue"]),
                ("scheduled_payment_date", "!=", False),
            ]
        )
        records._sync_date_state()
        return True

    @api.model
    def _cron_process_payment_alerts(self):
        today = fields.Date.context_today(self)
        records = self.search(
            [
                ("state", "in", ["scheduled", "due", "overdue"]),
                ("scheduled_payment_date", "!=", False),
            ]
        )
        Config = self.env["soles.treasury.config"]
        records._sync_date_state()
        for record in records:
            payment_date = record.scheduled_payment_date
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
                record._notify_odoo_users(
                    record._notification_users(),
                    _("Recordatorio: el pago <b>%(folio)s</b> está programado para <b>%(date)s</b>.")
                    % {"folio": record.name, "date": payment_date},
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
                record._notify_odoo_users(
                    record._notification_users(),
                    _("La solicitud <b>%(folio)s</b> está <b>Atrasada</b>. La fecha programada era %(date)s.")
                    % {"folio": record.name, "date": payment_date},
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
    requester_id = fields.Many2one(
        "res.users",
        string="Solicitante / destinatario",
        domain=[("share", "=", False)],
        help="Usuario que aparecerá como solicitante en las solicitudes generadas y que recibirá la notificación cuando el pago sea realizado.",
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
            "origin_type": "recurring",
            "partner_id": self.partner_id.id,
            "description": self.description or self.name,
            "amount": self.estimated_amount,
            "currency_id": self.currency_id.id,
            "company_id": self.company_id.id,
            "team_id": self.team_id.id,
            "reviewer_id": (self.team_id.reviewer_id or self.team_id.manager_id).id if self.team_id else False,
            "treasury_responsible_id": self.responsible_id.id,
            "requester_id": (self.requester_id or self.responsible_id or self.team_id.manager_id or self.env.user).id,
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
    payment_request_count = fields.Integer(
        compute="_compute_payment_requests",
        string="Solicitudes de pago",
        help="Número total de solicitudes de pago vinculadas a esta aprobación, incluyendo canceladas para conservar la trazabilidad.",
    )
    payment_requested_total = fields.Float(
        compute="_compute_payment_requests",
        string="Total solicitado",
        help="Suma de las solicitudes de pago activas vinculadas a esta aprobación.",
    )
    payment_paid_total = fields.Float(
        compute="_compute_payment_requests",
        string="Total pagado",
        help="Suma de las solicitudes vinculadas que ya fueron marcadas como pagadas o cerradas.",
    )
    payment_pending_total = fields.Float(
        compute="_compute_payment_requests",
        string="Pendiente de pago",
        help="Importe solicitado que todavía no ha sido marcado como pagado.",
    )
    payment_available_amount = fields.Float(
        compute="_compute_payment_requests",
        string="Disponible para solicitar",
        help="Diferencia entre el monto aprobado y el total solicitado en solicitudes de pago activas.",
    )
    treasury_payment_enabled = fields.Boolean(compute="_compute_treasury_payment_enabled")

    @api.depends("amount", "payment_request_ids", "payment_request_ids.amount", "payment_request_ids.state")
    def _compute_payment_requests(self):
        for approval in self:
            all_requests = approval.payment_request_ids
            valid_requests = all_requests.filtered(lambda request: request.state != "cancelled")
            requested_total = sum(valid_requests.mapped("amount"))
            paid_total = sum(
                valid_requests.filtered(lambda request: request.state in ("paid", "closed")).mapped("amount")
            )

            approval.payment_request_count = len(all_requests)
            approval.payment_requested_total = requested_total
            approval.payment_paid_total = paid_total
            approval.payment_pending_total = max(requested_total - paid_total, 0.0)
            approval.payment_available_amount = max((approval.amount or 0.0) - requested_total, 0.0)

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

    def _payment_request_default_context(self):
        self.ensure_one()
        approval_company = self.category_id.company_id or self.env.company
        return {
            "default_origin_type": "approval",
            "default_approval_request_id": self.id,
            "default_company_id": approval_company.id,
            "default_requester_id": self.request_owner_id.id or self.env.user.id,
            "default_partner_id": self.partner_id.id if self.partner_id else False,
            "default_amount": self.payment_available_amount or self.amount,
            "default_description": self.reason or self.name,
        }

    def action_view_payment_requests(self):
        self.ensure_one()
        requests = self.payment_request_ids.sorted(key=lambda request: request.id, reverse=True)

        # Si todavía no hay solicitudes, el smart button funciona como acceso
        # directo para crear la primera, conservando todas las validaciones.
        if not requests:
            return self.action_create_payment_request()

        # Con una sola solicitud evitamos un clic adicional y abrimos el registro.
        if len(requests) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Solicitud de Pago"),
                "res_model": "soles.payment.request",
                "view_mode": "form",
                "res_id": requests.id,
                "target": "current",
            }

        context = self._payment_request_default_context()
        # Si la categoría dejó de estar habilitada o la aprobación dejó de estar
        # aprobada, el historial sigue siendo visible pero no se permite crear más.
        if self.request_status != "approved" or not self.treasury_payment_enabled:
            context["create"] = False

        return {
            "type": "ir.actions.act_window",
            "name": _("Solicitudes de Pago - %s") % self.display_name,
            "res_model": "soles.payment.request",
            "view_mode": "list,form",
            "domain": [("approval_request_id", "=", self.id)],
            "context": context,
            "target": "current",
        }
