from odoo import models, fields, api


class SuKien(models.Model):
    _name = 'su_kien'
    _description = 'Sự kiện phòng ban'
    _order = 'ngay_bat_dau desc'

    name = fields.Char('Tên sự kiện', required=True)
    loai = fields.Selection([
        ('hop', 'Họp'),
        ('nghi', 'Nghỉ'),
        ('deadline', 'Deadline'),
        ('khac', 'Khác')
    ], default='hop', string='Loại sự kiện', required=True)
    
    mo_ta = fields.Text('Mô tả')
    phong_ban_id = fields.Many2one('phong_ban', string='Phòng ban')
    
    ngay_bat_dau = fields.Datetime('Bắt đầu', required=True)
    ngay_ket_thuc = fields.Datetime('Kết thúc', required=True)
    ca_ngay = fields.Boolean('Cả ngày', default=False)
    
    thanh_vien_ids = fields.Many2many('nhan_vien', string='Thành viên tham gia')
    nguoi_tao_id = fields.Many2one('nhan_vien', string='Người tạo')
    
    # Màu sắc cho calendar
    color = fields.Integer('Màu', compute='_compute_color')
    
    @api.depends('loai')
    def _compute_color(self):
        color_map = {
            'hop': 4,      # Xanh lá
            'nghi': 1,     # Đỏ
            'deadline': 3, # Vàng
            'khac': 6      # Xám
        }
        for record in self:
            record.color = color_map.get(record.loai, 0)
