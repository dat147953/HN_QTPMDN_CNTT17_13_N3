from odoo import models, fields, api

class MocDuAn(models.Model):
    _name = 'moc.du.an'
    _description = 'Mốc dự án'
    _order = 'ngay_du_kien, id'

    name = fields.Char('Tên mốc', required=True)
    du_an_id = fields.Many2one('du.an', string='Dự án', required=True, ondelete='cascade')
    ngay_du_kien = fields.Date('Ngày dự kiến', required=True)
    ngay_hoan_thanh = fields.Date('Ngày hoàn thành thực tế')
    trang_thai = fields.Selection([
        ('pending', 'Chưa đạt'),
        ('achieved', 'Đã đạt'),
        ('delayed', 'Trễ hạn')
    ], default='pending', string='Trạng thái', compute='_compute_trang_thai', store=True, readonly=False)
    mo_ta = fields.Text('Mô tả')
    cong_viec_ids = fields.One2many('cong.viec', 'moc_id', string='Công việc liên quan')
    
    # Computed fields
    so_cong_viec = fields.Integer('Số công việc', compute='_compute_tien_do')
    so_cong_viec_hoan_thanh = fields.Integer('Công việc hoàn thành', compute='_compute_tien_do')
    phan_tram_hoan_thanh = fields.Float('% Hoàn thành', compute='_compute_tien_do')
    
    @api.depends('cong_viec_ids', 'cong_viec_ids.trang_thai', 'trang_thai')
    def _compute_tien_do(self):
        for record in self:
            if record.trang_thai == 'achieved':
                record.phan_tram_hoan_thanh = 100.0
                record.so_cong_viec = len(record.cong_viec_ids)
                record.so_cong_viec_hoan_thanh = len(record.cong_viec_ids.filtered(lambda c: c.trang_thai == 'done'))
            else:
                record.so_cong_viec = len(record.cong_viec_ids)
                record.so_cong_viec_hoan_thanh = len(record.cong_viec_ids.filtered(lambda c: c.trang_thai == 'done'))
                if record.so_cong_viec > 0:
                    record.phan_tram_hoan_thanh = (record.so_cong_viec_hoan_thanh / record.so_cong_viec) * 100
                else:
                    record.phan_tram_hoan_thanh = 0
    
    @api.depends('ngay_du_kien', 'ngay_hoan_thanh', 'phan_tram_hoan_thanh')
    def _compute_trang_thai(self):
        today = fields.Date.today()
        for record in self:
            if record.ngay_hoan_thanh:
                record.trang_thai = 'achieved'
            elif record.ngay_du_kien and record.ngay_du_kien < today and record.phan_tram_hoan_thanh < 100:
                record.trang_thai = 'delayed'
            else:
                record.trang_thai = 'pending'
    
    def action_mark_achieved(self):
        self.write({
            'trang_thai': 'achieved',
            'ngay_hoan_thanh': fields.Date.today()
        })
