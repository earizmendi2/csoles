from odoo import http, _
from io import StringIO, BytesIO
from odoo.http import request, content_disposition, Response
from .csv_writer import CsvWriter
from odoo.exceptions import UserError


class ReportIncidences(http.Controller):
   

    @http.route('/report/incidence', type='http', auth='user', methods=['GET'], csrf=False)
    def get_incidence_report(self, **params):
        startdate = params.get('startdate')
        enddate = params.get('enddate')
        payrolltype = params.get('payrolltype')
        company_id = params.get('company_id')                
        rows, header = request.env['wizard.incidence.csv'].create_incidence_report(
            startdate, enddate, payrolltype, company_id) 
                 
        if len(rows) > 0  and len(header) > 0:
            
            file_data = BytesIO()
            writer = CsvWriter(file_data)
            writer.writerow(header)
            writer.writerows(rows)
            file_value = file_data.getvalue()
            filecontent = file_value
            csvhttpheaders = [
                ("Content-Type", "text/csv"),
                ("Content-Length", len(filecontent)),
                ("Content-Disposition", content_disposition('employee_incidences.csv')),
            ]
            
            file_data.close()
            
            return request.make_response(filecontent, headers=csvhttpheaders)
            
        else:

            return Response("No hay incidencias de tipo {}".format(payrolltype),content_type='text/html;charset=utf-8',status=500)