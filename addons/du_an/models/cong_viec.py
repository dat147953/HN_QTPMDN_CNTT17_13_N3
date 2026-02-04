from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CongViec(models.Model):
    _name = 'cong.viec'
    _description = 'Công việc'

    name = fields.Char('Tên công việc', required=True)
    mo_ta = fields.Text('Mô tả công việc')
    du_an_id = fields.Many2one('du.an', string='Thuộc dự án', required=True)
    thanh_vien_ids = fields.Many2many('nhan_vien', string='Thành viên')
    phan_tram_hoan_thanh = fields.Float('Phần trăm hoàn thành', compute='_compute_phan_tram_hoan_thanh', store=True, readonly=False)
    trang_thai = fields.Selection([
        ('not_started', 'Chưa bắt đầu'),
        ('in_progress', 'Đang thực hiện'),
        ('done', 'Hoàn thành')
    ], default='not_started', string='Trạng thái')
    uu_tien = fields.Selection([
        ('high', 'Cao'),
        ('medium', 'Trung bình'),
        ('low', 'Thấp')
    ], default='medium', string='Ưu tiên')
    thoi_gian_du_kien = fields.Float('Thời gian dự kiến (giờ)')
    thoi_gian_thuc_te = fields.Float('Thời gian thực tế (giờ)', compute='_compute_thoi_gian_thuc_te', store=True)
    deadline = fields.Date('Hạn hoàn thành')
    
    # Trọng số công việc (%) trong dự án
    trong_so = fields.Float('Trọng số (%)', default=0.0, help="Tổng trọng số các công việc trong một dự án phải bằng 100%")

    # Tác vụ con
    tac_vu_ids = fields.One2many('tac.vu', 'cong_viec_id', string='Tác vụ con')
    so_tac_vu = fields.Integer('Số tác vụ', compute='_compute_so_tac_vu')
    so_tac_vu_hoan_thanh = fields.Integer('Tác vụ hoàn thành', compute='_compute_so_tac_vu')
    
    # Mốc dự án
    moc_id = fields.Many2one('moc.du.an', string='Mốc dự án')
    
    @api.constrains('trong_so', 'du_an_id')
    def _check_tong_trong_so(self):
        for record in self:
            jobs = self.search([('du_an_id', '=', record.du_an_id.id)])
            total_weight = sum(jobs.mapped('trong_so'))
            if total_weight > 100.01:
                 raise ValidationError(f"Tổng trọng số các công việc trong dự án '{record.du_an_id.name}' vượt quá 100% (Hiện tại: {total_weight}%)")

    @api.depends('tac_vu_ids', 'tac_vu_ids.trang_thai')
    def _compute_so_tac_vu(self):
        for record in self:
            record.so_tac_vu = len(record.tac_vu_ids)
            record.so_tac_vu_hoan_thanh = len(record.tac_vu_ids.filtered(lambda t: t.trang_thai == 'done'))

    @api.depends('trang_thai', 'tac_vu_ids', 'tac_vu_ids.trang_thai', 'tac_vu_ids.trong_so')
    def _compute_phan_tram_hoan_thanh(self):
        for record in self:
            # Nếu có tác vụ con, tính % theo trọng số tác vụ
            if record.tac_vu_ids:
                total_progress = 0.0
                total_weight = sum(record.tac_vu_ids.mapped('trong_so'))
                
                # Nếu tổng trọng số = 0 (chưa thiết lập), dùng cách chia đều cũ hoặc return 0?
                # User yêu cầu hệ thống trọng số. Nếu chưa set trọng số, logic này sẽ trả về 0.
                # Có thể làm fallback: nếu tổng trọng số = 0, tính weight đều = 100 / item_count
                
                if total_weight > 0:
                     for task in record.tac_vu_ids:
                         task_progress = 100.0 if task.trang_thai == 'done' else 0.0
                         # Tính đóng góp của task này: (Progress * Weight) / 100
                         # Nhưng user nói công thức: Tổng (Progress * Weight). 
                         # Giả sử Weight là %, e.g., 50. Progress 100% -> 50. 
                         # Tổng sẽ là 0-100.
                         total_progress += (task_progress * task.trong_so / 100.0)
                     
                     # Normalize if total weight is not 100? No, constraint checks 100.
                     # If total < 100, progress will max out at total weight. This acts as "Weighted contribution".
                     record.phan_tram_hoan_thanh = total_progress
                else:
                    # Fallback old logic (count based) if no weights used yet
                    total = len(record.tac_vu_ids)
                    done = len(record.tac_vu_ids.filtered(lambda t: t.trang_thai == 'done'))
                    record.phan_tram_hoan_thanh = (done / total) * 100 if total > 0 else 0
            else:
                # Nếu không có tác vụ con, tính từ trạng thái
                if record.trang_thai == 'not_started':
                    record.phan_tram_hoan_thanh = 0
                elif record.trang_thai == 'done':
                    record.phan_tram_hoan_thanh = 100
                    
    @api.depends('thoi_gian_du_kien', 'thoi_gian_thuc_te')
    def _compute_thoi_gian_thuc_te(self):
        for record in self:
            if record.tac_vu_ids:
                 record.thoi_gian_thuc_te = sum(record.tac_vu_ids.mapped('thoi_gian_thuc_te'))
            else:
                 record.thoi_gian_thuc_te = record.thoi_gian_du_kien if record.trang_thai == 'done' else 0
    
    def action_view_tac_vu(self):
        """Open a view of related sub-tasks"""
        self.ensure_one()
        return {
            'name': 'Tác vụ của ' + self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'tac.vu',
            'view_mode': 'kanban,tree,form',
            'domain': [('cong_viec_id', '=', self.id)],
            'context': {'default_cong_viec_id': self.id},
        }