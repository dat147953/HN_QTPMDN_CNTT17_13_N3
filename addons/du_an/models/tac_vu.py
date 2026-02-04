from odoo import models, fields, api
from odoo.exceptions import ValidationError

class TacVu(models.Model):
    _name = 'tac.vu'
    _description = 'Tác vụ con'
    _order = 'sequence, id'

    name = fields.Char('Tên tác vụ', required=True)
    sequence = fields.Integer('Thứ tự', default=10)
    mo_ta = fields.Text('Mô tả')
    cong_viec_id = fields.Many2one('cong.viec', string='Công việc cha', required=True, ondelete='cascade')
    nguoi_thuc_hien_id = fields.Many2one('nhan_vien', string='Người thực hiện')
    trang_thai = fields.Selection([
        ('todo', 'Cần làm'),
        ('doing', 'Đang làm'),
        ('done', 'Hoàn thành')
    ], default='todo', string='Trạng thái')
    deadline = fields.Date('Hạn hoàn thành')
    thoi_gian_du_kien = fields.Float('Thời gian dự kiến (giờ)')
    thoi_gian_thuc_te = fields.Float('Thời gian thực tế (giờ)')
    ngay_hoan_thanh = fields.Date('Ngày hoàn thành')
    
    # Trọng số tác vụ (%)
    trong_so = fields.Float('Trọng số (%)', default=0.0, help="Tổng trọng số các tác vụ trong một công việc phải bằng 100%")
    
    # Related fields for easy access
    du_an_id = fields.Many2one(related='cong_viec_id.du_an_id', string='Dự án', store=True)

    @api.constrains('trong_so', 'cong_viec_id')
    def _check_tong_trong_so(self):
        for record in self:
            # Check sum of weights for all tasks in the same job
            tasks = self.search([('cong_viec_id', '=', record.cong_viec_id.id)])
            total_weight = sum(tasks.mapped('trong_so'))
            # Allow some floating point margin or warn user. Ideally strictly 100 or 0 (if no weights used yet).
            # But requirements say "Warning if not reached or exceeded".
            # Let's use a warning message action or just raise ValidationError if strict.
            # User request: "Cảnh báo nếu tổng trọng số các mục con chưa đạt hoặc vượt quá 100%."
            if total_weight > 100.01:
                 raise ValidationError(f"Tổng trọng số các tác vụ trong công việc '{record.cong_viec_id.name}' vượt quá 100% (Hiện tại: {total_weight}%)")
    
    @api.onchange('trang_thai')
    def _onchange_trang_thai(self):
        if self.trang_thai == 'done' and not self.ngay_hoan_thanh:
            self.ngay_hoan_thanh = fields.Date.today()

    def action_goi_y_nhan_su(self):
        """
        Gợi ý nhân sự sử dụng OpenAI (Smart Allocation).
        """
        self.ensure_one()
        openai_service = self.env['openai.service']
        
        # 1. Xác định pool nhân viên
        candidates = self.du_an_id.thanh_vien_ids
        if not candidates:
            candidates = self.env['nhan_vien'].search([], limit=20) # Limit to avoid token overflow
            
        if not candidates:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Không tìm thấy nhân viên', 'message': 'Chưa có nhân viên nào.', 'type': 'warning', 'sticky': False}
            }

        candidate_data = []
        for emp in candidates:
            # Hiệu suất
            efficiency = emp.ty_le_dung_deadline or 0
            # Tải công việc (Active tasks)
            current_tasks = self.env['tac.vu'].search_count([
                ('nguoi_thuc_hien_id', '=', emp.id),
                ('trang_thai', 'in', ['todo', 'doing'])
            ])
            candidate_data.append(f"- ID {emp.id}: {emp.ho_va_ten} (On-time Rate: {efficiency}%, Active Tasks: {current_tasks})")
            
        candidates_str = "\n".join(candidate_data)
        
        # OpenAI Prompt
        prompt = f"""
        Suggest the best employee for this task:
        Task Name: {self.name}
        Description: {self.mo_ta or 'N/A'}
        
        Candidates:
        {candidates_str}
        
        Criteria:
        - Prioritize high On-time Rate.
        - Avoid overloading employees with many Active Tasks.
        
        Output strictly in JSON:
        {{
            "recommended_id": <id>,
            "name": "<name>",
            "reasoning": "<short explanation in Vietnamese>",
            "avoid": "<name of someone to avoid if any>"
        }}
        """
        
        response = openai_service.get_chat_completion(
            prompt,
            system_prompt="You are an expert HR Manager AI. Response in JSON.",
            model="gpt-3.5-turbo"
        )
        
        msg = ""
        suggestion_success = False
        
        if response:
            try:
                import json
                clean_res = response.replace('```json', '').replace('```', '').strip()
                data = json.loads(clean_res)
                
                recommended_id = data.get('recommended_id')
                name = data.get('name')
                reason = data.get('reasoning')
                avoid = data.get('avoid')
                
                msg = f"AI Gợi ý: {name}\n{reason}"
                if avoid:
                    msg += f"\nTránh giao cho: {avoid}"
                
                # Auto assign logic (optional, users prefer suggestion first)
                if not self.nguoi_thuc_hien_id and recommended_id:
                     # Verify ID exists in candidates
                     if any(c.id == recommended_id for c in candidates):
                         self.nguoi_thuc_hien_id = recommended_id
                         msg = f"Đã tự động gán cho: {name} (Theo gợi ý AI)\n{reason}"

                suggestion_success = True
            except Exception as e:
                msg = f"Lỗi AI: {str(e)}. Sử dụng thuật toán cơ bản."
        
        if not suggestion_success:
             # FALLBACK to existing algorithm
             scores = []
             for emp in candidates:
                efficiency = emp.ty_le_dung_deadline or 0
                current_tasks = self.env['tac.vu'].search_count([
                    ('nguoi_thuc_hien_id', '=', emp.id),
                    ('trang_thai', 'in', ['todo', 'doing'])
                ])
                workload_score = max(0, 100 - (current_tasks * 15))
                total_score = (efficiency * 0.6) + (workload_score * 0.4)
                scores.append({'id': emp.id, 'name': emp.ho_va_ten, 'score': total_score, 
                               'details': f"Đúng hạn: {efficiency}%, Đang làm: {current_tasks} task"})
             
             scores.sort(key=lambda x: x['score'], reverse=True)
             top = scores[0]
             msg = f"Gợi ý (Cơ bản): {top['name']} ({round(top['score'], 1)} điểm)\n{top['details']}"
             if not self.nguoi_thuc_hien_id:
                 self.nguoi_thuc_hien_id = top['id']

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Gợi ý Phân công AI',
                'message': msg,
                'type': 'success',
                'sticky': False,
            }
        }
