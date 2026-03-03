from odoo import models, fields, api


class PhongBan(models.Model):
    _name = 'phong_ban'
    _description = 'Bảng chứa thông tin phòng ban'
    _rec_name = 'ten_phong_ban'
    _sql_constraints = [
        ('ma_phong_ban_unique', 'UNIQUE(ma_phong_ban)', 'Mã phòng ban đã tồn tại trong hệ thống!')
    ]

    ma_phong_ban = fields.Char("Mã phòng ban", required=True)
    ten_phong_ban = fields.Char("Tên phòng ban", required=True)
    mo_ta = fields.Text("Mô tả chức năng")
    
    # Quản lý phòng ban
    truong_phong_id = fields.Many2one('nhan_vien', string='Trưởng phòng')
    pho_phong_id = fields.Many2one('nhan_vien', string='Phó phòng')
    
    # Danh sách nhân viên - Many2many để chọn nhân viên hiện có
    nhan_vien_ids = fields.Many2many("nhan_vien", string="Danh sách nhân viên")
    so_nhan_vien = fields.Integer("Số nhân viên", compute='_compute_so_nhan_vien', store=True)
    
    @api.depends('nhan_vien_ids')
    def _compute_so_nhan_vien(self):
        for record in self:
            record.so_nhan_vien = len(record.nhan_vien_ids)