from openerp.osv import osv, fields
from openerp.addons.avancys_orm import avancys_orm


class res_company(osv.osv):
    _inherit = "res.company"

    _columns = {
        'aportante_exonerado': fields.boolean('Aportante Exonerado',
                                              help="Aportante exonerado de pago de aportes de parafiscales y salud, Ley 1607 de 2012, esto afecta la generacion de la planilla de pago de aportes"),
    }


class hr_centro_trabajo(osv.osv):
    _name = "hr.centro.trabajo"
    _description = "Centro de Trabajo"

    _columns = {
        'name': fields.char('Nombre', size=128, required=True),
        'code': fields.integer('Codigo', required=True),
    }

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codigo tiene que ser unico!'),
    ]


class account_analytic_account(osv.osv):
    _inherit = "account.analytic.account"

    _columns = {
        'centro_trabajo_id': fields.many2one('hr.centro.trabajo', 'Centro de trabajo'),
    }


class planilla_type(osv.osv):
    _name = "hr.planilla.type"
    _description = "Tipo de planilla"

    _columns = {
        'name': fields.char('Nombre', size=128, required=True),
        'code': fields.char('Codigo', size=1, required=True),
    }

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El Nombre tiene que ser unico!'),
        ('code_uniq', 'unique(code)', 'El Codigo tiene que ser unico!'),
    ]


class payslip_type(osv.osv):
    _inherit = "hr.payslip.type"

    _columns = {
        'planilla_type_id': fields.many2one('hr.planilla.type', 'Tipo de Planilla'),
    }


class hr_payslip(osv.osv):
    _inherit = 'hr.payslip'

    _columns = {
        'correcciones': fields.selection([('A', 'A'), ('C', 'C')], 'Correcciones'),  # TODO
        'ing': fields.selection([('X', 'X'), ('R', 'R')], 'ING - Ingreso'),
        'ret': fields.selection([('X', 'X'), ('P', 'P'), ('R', 'R')], 'RET - Retiro'),
        # TODO P, cuando se retira solo de pensiones
        'tde': fields.boolean('TDE - Traslado desde otra EPS'),  # TODO
        'tae': fields.boolean('TAE - Traslado a otra EPS'),  # TODO
        'tdp': fields.boolean('TDP - Traslado desde otra AFP'),  # TODO
        'tap': fields.boolean('TAP - Traslado a otra AFP'),  # TODO
        'vct': fields.boolean('VCT - Variacion centros de trabajo'),  # TODO
        'vst': fields.boolean('VST - Variacion transitoria del salario'),
        'vsp': fields.boolean('VSP - Variacion permanente del salario'),  # TODO
        'sln': fields.boolean('SLN - Licencia no remunerada'),
        'lma': fields.boolean('LMA - Licencia Maternidad/Paternidad'),
        'ige': fields.boolean('IGE - Incapacidad general'),
        'vac': fields.boolean('VAC - Vacaciones'),
        'avp': fields.boolean('AVP - Aporte voluntario pension'),
        'irp': fields.integer('IRP - Incapacidad por accidente de trabajo'),

    }

    def compute_sheet(self, cr, uid, ids, context=None):
        result = super(hr_payslip, self).compute_sheet(cr, uid, ids, context=context)

        def rule(slip, code, property):
            result = 0
            for line in slip.details_by_salary_rule_category:
                if line.code == code:
                    if property == 'quantity':
                        result = line.quantity
                    elif property == 'rate':
                        result = line.rate / 100
                    elif property == 'amount':
                        result = line.amount
                    else:
                        result = line.total
                    break
            return result

        for payslip in self.browse(cr, uid, ids, context=context):

            data = {'ing': False, 'ret': False, 'tde': False, 'tae': False, 'tdp': False, 'tap': False, 'vct': False,
                    'vst': False, 'vsp': False, 'sln': False, 'lma': False, 'ige': False, 'irp': 0, 'vac': False,
                    'avp': False}
            if payslip.contract_id.date_start[0:7] == payslip.payslip_period_id.end_period[0:7]:
                if payslip.contract_id.fiscal_type_id.code == '03':
                    data.update({'ing': 'R'})
                else:
                    data.update({'ing': 'X'})
            if payslip.contract_id.date_end:
                if payslip.contract_id.date_end[0:7] == payslip.payslip_period_id.end_period[0:7]:
                    if payslip.contract_id.fiscal_type_id.code == '03':
                        data.update({'ret': 'R'})
                    else:
                        data.update({'ret': 'X'})

            indicator = False
            for pays in payslip.contract_id.slip_ids.filtered(
                    lambda x: str(x.payslip_period_id.end_period)[0:7] == str(payslip.payslip_period_id.end_period)[
                                                                          0:7]):
                if len(pays.line_ids.filtered(lambda x: x.category_id.code in (
                        'DEVENGADO', 'INGCOM', 'OTRDER') and x.code not in ('BASICO', 'BASICOINT', 'BASICOCS'))) > 0:
                    indicator = True

            if int(payslip.contract_id.fiscal_type_id.code) not in (12,19) and (payslip.contract_id.wage < rule(payslip, 'IBCSS', 'amount') or indicator):
                data.update({'vst': True})

            for changes in payslip.contract_id.wage_historic_ids.filtered(
                    lambda x: str(x.date)[0:7] == str(payslip.payslip_period_id.end_period)[0:7]):
                if changes.date[8:] != '01':
                    data.update({'vsp': True})

            for leave in payslip.worked_days_line_ids:
                if leave.code == 'VAC1':
                    data.update({'vac': True})
                if leave.code == 'INCAPACIDAD_ENF_GENERAL1':
                    data.update({'ige': True})
                if leave.code == 'AT/EP1':
                    data.update({'irp': leave.number_of_days})
                    # del raise osv.except_osv(_('Atencion!'), _('numero dias %s')% (leave.number_of_days))
                if leave.code in ('LICENCIA_MATERNIDAD1','LICENCIA_PATERNIDAD1'):
                    data.update({'lma': True})
                if leave.code == 'LICENCIA_NO_REMUNERADA1':
                    data.update({'sln': True})
            for novedad in payslip.novedades_ids:
                if novedad.category_id.name == 'APORTE_VOLUNTARIO_PENSION':
                    data.update({'avp': True})
            avancys_orm.direct_update(cr, 'hr_payslip', data, ('id', payslip.id))

        return result


class hr_payslip_run(osv.osv):
    _inherit = "hr.payslip.run"
    _columns = {
        'time_of_process': fields.datetime('Fecha Transmisin', readonly=True),
        'file_text': fields.binary(string="Archivo Plano Aportes", readonly=True),
        'file_name': fields.char(size=64, string='Archivo Plano Aportes', track_visibility='onchange', readonly=True),
    }
