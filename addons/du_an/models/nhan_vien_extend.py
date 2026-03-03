from odoo import models, fields, api

class NhanVienExtend(models.Model):
    _inherit = 'nhan_vien'

    user_id = fields.Many2one('res.users', string='Tài khoản liên kết', help='Liên kết nhân viên với tài khoản đăng nhập hệ thống')
    cong_viec_ids = fields.Many2many('cong.viec', string='Công việc tham gia')
    
    # Tác vụ được giao
    tac_vu_ids = fields.One2many('tac.vu', 'nguoi_thuc_hien_id', string='Tác vụ được giao')
    
    # Thống kê hiệu suất
    tong_tac_vu = fields.Integer("Tổng tác vụ", compute='_compute_hieu_suat')
    tac_vu_hoan_thanh = fields.Integer("Tác vụ hoàn thành", compute='_compute_hieu_suat')
    ty_le_hoan_thanh = fields.Float("Tỷ lệ hoàn thành (%)", compute='_compute_hieu_suat')
    # tong_gio_lam_viec = fields.Float("Tổng giờ làm việc", compute='_compute_hieu_suat') # Removed timesheet
    tac_vu_dung_han = fields.Integer("Tác vụ đúng hạn", compute='_compute_hieu_suat')
    ty_le_dung_deadline = fields.Float("Tỷ lệ đúng deadline (%)", compute='_compute_hieu_suat')

    @api.depends('tac_vu_ids', 'tac_vu_ids.trang_thai', 'tac_vu_ids.deadline', 'tac_vu_ids.ngay_hoan_thanh')
    def _compute_hieu_suat(self):
        for record in self:
            tac_vu = record.tac_vu_ids
            record.tong_tac_vu = len(tac_vu)
            
            done_tasks = tac_vu.filtered(lambda t: t.trang_thai == 'done')
            record.tac_vu_hoan_thanh = len(done_tasks)
            
            record.ty_le_hoan_thanh = (record.tac_vu_hoan_thanh / record.tong_tac_vu * 100) if record.tong_tac_vu > 0 else 0
            
            # record.tong_gio_lam_viec = sum(record.cham_cong_ids.mapped('so_gio')) # Removed timesheet
            
            # Tính tỷ lệ đúng deadline
            on_time = done_tasks.filtered(
                lambda t: t.deadline and t.ngay_hoan_thanh and t.ngay_hoan_thanh <= t.deadline
            )
            record.tac_vu_dung_han = len(on_time)
            record.ty_le_dung_deadline = (record.tac_vu_dung_han / record.tac_vu_hoan_thanh * 100) if record.tac_vu_hoan_thanh > 0 else 0
