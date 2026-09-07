from odoo import fields,api,models,_


class RejectReason(models.TransientModel):
    _name = 'xf.reject.reason'
    _description = 'Reject Reason'

    name = fields.Text(string='Reason')
    res_model = fields.Char('Model', readonly=True)
    res_id = fields.Many2oneReference('Document', model_field='res_model', readonly=True)

    def action_reject(self):
        id = self.env[self.res_model].browse(self.res_id)
        if id:
            message = f'This Order has been refused \n Reason : {self.name}'
            id.message_post(body=message)


class RejectWiz(models.TransientModel):
    _name = 'reject.reason'
    _description = 'Reject Reason Wizard'

    name = fields.Text(string='Reject Reason')

    res_model = fields.Char('Model', readonly=True)
    res_id = fields.Many2oneReference('Document', model_field='res_model', readonly=True)

    def reject(self):
        id = self.env[self.res_model].browse(self.res_id)
        if id:
            id.with_context(reject_reason=self.name).action_reject_button()
