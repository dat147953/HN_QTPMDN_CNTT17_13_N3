# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BaoCaoTienDo(models.Model):
    _name = 'bao.cao.tien.do'
    _description = 'Báo cáo tiến độ đa phương tiện'
    _order = 'ngay_bao_cao desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # 1. Định danh (Cấp 1)
    name = fields.Char('Tiêu đề báo cáo', required=True, tracking=True)
    nguoi_bao_cao_id = fields.Many2one('nhan_vien', string='Người báo cáo', 
                                        required=True, tracking=True, 
                                        default=lambda self: self.env['nhan_vien'].search([('user_id', '=', self.env.user.id)], limit=1))
    ngay_bao_cao = fields.Datetime('Ngày báo cáo', default=fields.Datetime.now, 
                                    required=True, tracking=True)

    # 2. Phân cấp dữ liệu (Cascading Selection)
    # Cấp 2: Dự án (Lọc theo Nhân sự)
    du_an_id = fields.Many2one('du.an', string='Dự án', required=True, tracking=True, 
                                domain="[('thanh_vien_ids', 'in', nguoi_bao_cao_id)]")
    
    # Cấp 3: Công việc (Lọc theo Dự án)
    cong_viec_id = fields.Many2one('cong.viec', string='Công việc', required=True, 
                                    domain="[('du_an_id', '=', du_an_id)]")

    # Cấp 4: Tác vụ (Lọc theo Công việc)
    tac_vu_id = fields.Many2one('tac.vu', string='Tác vụ', required=True, 
                                 domain="[('cong_viec_id', '=', cong_viec_id)]")
    
    # 3. Nội dung (Cấp 5 - Chỉ hiện khi có Task)
    noi_dung = fields.Html('Nội dung báo cáo', sanitize=True, strip_style=False,
                           help='Nhập nội dung chi tiết với định dạng văn bản phong phú')
    
    hinh_anh_ids = fields.One2many('bao.cao.hinh.anh', 'bao_cao_id', 
                                    string='Hình ảnh minh chứng')
    so_hinh_anh = fields.Integer('Số hình ảnh', compute='_compute_so_hinh_anh')
    
    # Trạng thái
    trang_thai = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Đã gửi'),
        ('reviewed', 'Đã xem')
    ], default='draft', string='Trạng thái', tracking=True)
    
    # --- AI Auditor Fields ---
    ai_consistency_score = fields.Integer('Điểm nhất quán (AI)', readonly=True, help="AI đánh giá mức độ khớp giữa văn bản và hình ảnh (0-100)")
    ai_efficiency_eval = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao')
    ], string='Đánh giá Hiệu suất (AI)', readonly=True)
    ai_manager_feedback = fields.Text('Nhận xét của AI Manager', readonly=True, help="Nhận xét tự động dành cho quản lý")
    ai_risk_flag = fields.Boolean('Cảnh báo rủi ro', readonly=True, help="AI phát hiện dấu hiệu bất thường hoặc chậm trễ")
    ai_audit_time = fields.Datetime('Thời gian Audit', readonly=True)

    # --- Onchange Logic for Cascading ---

    @api.onchange('nguoi_bao_cao_id')
    def _onchange_nguoi_bao_cao_id(self):
        """Khi đổi người báo cáo -> Reset và lọc lại Dự án"""
        self.du_an_id = False
        self.cong_viec_id = False
        self.tac_vu_id = False
        if self.nguoi_bao_cao_id:
            return {'domain': {'du_an_id': [('thanh_vien_ids', 'in', self.nguoi_bao_cao_id.id)]}}
        return {'domain': {'du_an_id': []}}

    @api.onchange('du_an_id')
    def _onchange_du_an_id(self):
        """Khi đổi dự án -> Reset và lọc lại Công việc"""
        self.cong_viec_id = False
        self.tac_vu_id = False
        if self.du_an_id:
            domain = [('du_an_id', '=', self.du_an_id.id)]
            if self.nguoi_bao_cao_id:
               domain.append(('thanh_vien_ids', 'in', self.nguoi_bao_cao_id.id))
            
            return {'domain': {'cong_viec_id': domain}}
        return {'domain': {'cong_viec_id': []}}

    @api.onchange('cong_viec_id')
    def _onchange_cong_viec_id(self):
        """Khi đổi công việc -> Reset và lọc lại Tác vụ"""
        self.tac_vu_id = False
        if self.cong_viec_id:
            domain = [('cong_viec_id', '=', self.cong_viec_id.id)]
            if self.nguoi_bao_cao_id:
                domain.append(('nguoi_thuc_hien_id', '=', self.nguoi_bao_cao_id.id))
            
            return {'domain': {'tac_vu_id': domain}}
        return {'domain': {'tac_vu_id': []}}

    # --- Compute / Action ---

    @api.depends('hinh_anh_ids')
    def _compute_so_hinh_anh(self):
        for record in self:
            record.so_hinh_anh = len(record.hinh_anh_ids)
    
    def action_gui_bao_cao(self):
        """Gửi báo cáo và thông báo cho quản lý dự án. Tự động chạy AI Audit."""
        self.ensure_one()
        
        # 1. Automatic AI Audit
        try:
            self._run_ai_audit()
            audit_msg = "<p><em>AI Auditor đã tự động kiểm tra báo cáo này.</em></p>"
        except Exception as e:
            audit_msg = f"<p><em>Lỗi AI Audit: {str(e)}</em></p>"

        # 2. Update Status and Send Notification
        self.trang_thai = 'submitted'
        
        message = f"""
        <p><strong>Báo cáo tiến độ mới:</strong> {self.name}</p>
        <p><strong>Người báo cáo:</strong> {self.nguoi_bao_cao_id.ho_va_ten}</p>
        <p><strong>Dự án:</strong> {self.du_an_id.name}</p>
        <p><strong>Công việc:</strong> {self.cong_viec_id.name}</p>
        <p><strong>Tác vụ:</strong> {self.tac_vu_id.name}</p>
        <p><strong>Số hình ảnh đính kèm:</strong> {self.so_hinh_anh}</p>
        <hr/>
        {audit_msg}
        """
        
        self.message_post(
            body=message,
            subject=f"Báo cáo tiến độ: {self.name}",
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đã gửi báo cáo',
                'message': 'Báo cáo đã được gửi và đã được AI kiểm tra!',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_danh_dau_da_xem(self):
        """Quản lý đánh dấu đã xem báo cáo"""
        self.ensure_one()
        self.trang_thai = 'reviewed'

    def action_ai_audit(self):
        """Manual Action for AI Audit"""
        self.ensure_one()
        try:
            self._run_ai_audit()
            msg_type = 'warning' if self.ai_risk_flag else 'success'
            title = 'Cảnh báo Rủi ro!' if self.ai_risk_flag else 'Audit Hoàn tất'
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': title, 'message': 'AI đã hoàn thành đánh giá báo cáo.', 'type': msg_type, 'sticky': False}
            }
        except Exception as e:
            raise ValidationError(f"AI Error: {str(e)}")

    def _run_ai_audit(self):
        """Internal method to execute AI Audit logic"""
        openai_service = self.env['openai.service']
        
        # Prepare Data Payload
        images_info = []
        for img in self.hinh_anh_ids:
            images_info.append(f"- Image: {img.name} (Caption: {img.chu_thich})")
        images_str = "\n".join(images_info)
        
        task_info = f"Task: {self.tac_vu_id.name} (Weight: {self.tac_vu_id.trong_so}%, Deadline: {self.tac_vu_id.deadline})"
        employee_info = f"Employee: {self.nguoi_bao_cao_id.ho_va_ten} (On-time Rate: {self.nguoi_bao_cao_id.ty_le_dung_deadline}%)"
        
        # Build Prompt
        prompt = f"""
        You are an AI Auditor for Project Reports. Analyze this report:
        
        {task_info}
        {employee_info}
        
        Report Content: "{self.noi_dung}"
        Attached Images:
        {images_str}
        
        Your Mission:
        1. Consistency Check: Does the text content match the image descriptions? (Score 0-100)
        2. Efficiency Eval: Based on deadline and weight, how is the efficiency? (Low/Medium/High)
        3. Manager Feedback: Write a 30-50 word professional review for the manager about this employee's performance/attitude.
        4. Risk Flag: Set True if you detect inconsistency, cheating, or serious delay risks.
        
        Output strictly in JSON:
        {{
            "consistency_score": <int>,
            "efficiency_evaluation": "low/medium/high",
            "manager_feedback": "<text>",
            "risk_flag": <bool>,
            "risk_reason": "<text if flag is true>"
        }}
        """
        
        # Call AI
        response = openai_service.get_chat_completion(
            prompt,
            system_prompt="You are a strict professional AI Auditor. Response in JSON.",
            model="gpt-3.5-turbo"
        )
        
        # Process Response
        if response:
            import json
            clean_res = response.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_res)
            
            self.ai_consistency_score = data.get('consistency_score', 0)
            self.ai_efficiency_eval = data.get('efficiency_evaluation', 'medium').lower()
            self.ai_manager_feedback = data.get('manager_feedback', "No feedback generated.")
            self.ai_risk_flag = data.get('risk_flag', False)
            self.ai_audit_time = fields.Datetime.now()
        else:
             raise ValidationError("AI Service returned empty response.")


class BaoCaoHinhAnh(models.Model):
    _name = 'bao.cao.hinh.anh'
    _description = 'Hình ảnh báo cáo tiến độ'
    _order = 'sequence, id'

    name = fields.Char('Tên hình ảnh', required=True)
    sequence = fields.Integer('Thứ tự', default=10)
    hinh_anh = fields.Binary('Hình ảnh', required=True, attachment=True,
                              help='Tải lên hình ảnh JPG hoặc PNG')
    hinh_anh_filename = fields.Char('Tên file')
    chu_thich = fields.Text('Chú thích', 
                             help='Mô tả chi tiết về hình ảnh này')
    bao_cao_id = fields.Many2one('bao.cao.tien.do', string='Báo cáo', 
                                  required=True, ondelete='cascade')
    
    @api.constrains('hinh_anh_filename')
    def _check_file_extension(self):
        """Kiểm tra định dạng file ảnh"""
        for record in self:
            if record.hinh_anh_filename:
                ext = record.hinh_anh_filename.lower().split('.')[-1]
                if ext not in ['jpg', 'jpeg', 'png']:
                    raise ValidationError(
                        'Chỉ chấp nhận file ảnh định dạng JPG hoặc PNG!'
                    )
