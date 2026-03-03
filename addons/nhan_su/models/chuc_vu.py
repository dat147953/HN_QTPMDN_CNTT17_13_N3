from odoo import models, fields, api


class ChucVu(models.Model):
    _name = 'chuc_vu'
    _description = 'Bảng chứa thông tin chức vụ'
    _rec_name = 'ten_chuc_vu'
    _sql_constraints = [
        ('ma_chuc_vu_unique', 'UNIQUE(ma_chuc_vu)', 'Mã chức vụ đã tồn tại trong hệ thống!')
    ]

    ma_chuc_vu = fields.Char("Mã chức vụ", required=True)
    ten_chuc_vu = fields.Char("Tên chức vụ", required=True)
    mo_ta = fields.Text("Mô tả")
    nhan_vien_ids = fields.One2many("nhan_vien", "chuc_vu_id", string="Danh sách nhân viên")
