from odoo import models, fields, api

class DuAn(models.Model):
    _name = 'du.an'
    _description = 'Dự Án'

    name = fields.Char(string="Tên dự án", required=True)
    ngay_bat_dau = fields.Date(string="Ngày bắt đầu")
    ngay_ket_thuc = fields.Date(string="Ngày kết thúc")
    mo_ta = fields.Text(string="Mô tả")
    cong_viec_ids = fields.One2many('cong.viec', 'du_an_id', string='Công việc')
    thanh_vien_ids = fields.Many2many('nhan_vien', string='Thành viên')
    chi_phi_ids = fields.One2many('chi.phi', 'du_an_id', string='Chi phí')
    moc_du_an_ids = fields.One2many('moc.du.an', 'du_an_id', string='Mốc dự án')
    trang_thai = fields.Selection([
        ('new', 'Mới'),
        ('progress', 'Đang thực hiện'),
        ('done', 'Hoàn thành')
    ], default='new', string='Trạng thái')
    phan_tram_hoan_thanh = fields.Float(string="Phần trăm hoàn thành", compute='_compute_phan_tram_hoan_thanh', store=True)
    tong_chi_phi = fields.Float(compute='_compute_tong_chi_phi', string='Tổng chi phí', store=True)
    
    @api.depends('chi_phi_ids')
    def _compute_tong_chi_phi(self):
        for record in self:
            record.tong_chi_phi = sum(record.chi_phi_ids.mapped('so_tien'))
        pass

    @api.depends('cong_viec_ids', 'cong_viec_ids.phan_tram_hoan_thanh', 'cong_viec_ids.trong_so')
    def _compute_phan_tram_hoan_thanh(self):
        for record in self:
            if record.cong_viec_ids:
                total_weight = sum(record.cong_viec_ids.mapped('trong_so'))
                
                if total_weight > 0:
                    sum_weighted_progress = 0.0
                    for job in record.cong_viec_ids:
                        # Job progress (0-100) * Weight (%) / 100
                        sum_weighted_progress += (job.phan_tram_hoan_thanh * job.trong_so / 100.0)
                    record.phan_tram_hoan_thanh = round(sum_weighted_progress, 2)
                else:
                    # Fallback to average if no weights set
                    total_jobs = len(record.cong_viec_ids)
                    sum_percent = sum(record.cong_viec_ids.mapped('phan_tram_hoan_thanh'))
                    record.phan_tram_hoan_thanh = round(sum_percent / total_jobs, 2) if total_jobs > 0 else 0
            else:
                record.phan_tram_hoan_thanh = 0

    # --- Predictive Analytics ---
    muc_do_rui_ro = fields.Selection([
        ('thap', 'Thấp'),
        ('trung_binh', 'Trung bình'),
        ('cao', 'Cao')
    ], string='Mức độ rủi ro', default='thap')
    
    phan_tich_rui_ro = fields.Text(string='Phân tích rủi ro')

    def action_du_bao_rui_ro(self):
        """
        Dự báo rủi ro & Tiến độ sử dụng OpenAI (Predictive Analytics).
        """
        openai_service = self.env['openai.service']
        
        for record in self:
            if not record.ngay_bat_dau or not record.ngay_ket_thuc:
                record.muc_do_rui_ro = 'thap'
                record.phan_tich_rui_ro = 'Chưa đủ dữ liệu thời gian để phân tích.'
                continue
            
            today = fields.Date.today()
            total_days = (record.ngay_ket_thuc - record.ngay_bat_dau).days
            if total_days <= 0: continue
            elapsed_days = (today - record.ngay_bat_dau).days
            
            # Base stats
            time_percent = (elapsed_days / total_days) * 100 if elapsed_days > 0 else 0
            if time_percent > 100: time_percent = 100
            work_percent = record.phan_tram_hoan_thanh
            gap = work_percent - time_percent
            
            # Team stats
            team_stats = []
            for member in record.thanh_vien_ids:
                team_stats.append(f"{member.ho_va_ten} (Deadline Completion Rate: {member.ty_le_dung_deadline}%)")
            team_info = "; ".join(team_stats)
            
            # OpenAI Prompt
            prompt = f"""
            Analyze the risk of delay for the following project:
            - Project Name: {record.name}
            - Timeline: {elapsed_days} days elapsed out of {total_days} total days ({round(time_percent, 1)}% time passed).
            - Actual Progress: {work_percent}% completed.
            - Gap (Progress - Time): {round(gap, 1)}%.
            - Team Performance History: {team_info}
            
            Task:
            1. Predict the risk level (High, Medium, Low).
            2. Estimate potential delay in days (if any).
            3. Provide a probability of delay (0-100%).
            
            Output strictly in JSON format:
            {{
                "risk_level": "low/medium/high",
                "delay_days": <number>,
                "probability": <number>,
                "reasoning": "<short explanation in Vietnamese>"
            }}
            """
            
            # Call OpenAI
            response = openai_service.get_chat_completion(
                prompt, 
                system_prompt="You are an expert Project Manager AI specialized in predictive analytics. Response in JSON.",
                model="gpt-3.5-turbo"
            )
            
            if response:
                try:
                    import json
                    # Clean response if needed (remove markdown)
                    clean_res = response.replace('```json', '').replace('```', '').strip()
                    data = json.loads(clean_res)
                    
                    # Map risk level
                    risk_map = {'low': 'thap', 'medium': 'trung_binh', 'high': 'cao'}
                    record.muc_do_rui_ro = risk_map.get(data.get('risk_level', 'low').lower(), 'thap')
                    
                    # Format analysis
                    detail = f"Dự báo AI:\n- Nguy cơ trễ hạn: {data.get('probability')}%"
                    if data.get('delay_days', 0) > 0:
                        detail += f"\n- Dự kiến trễ: {data.get('delay_days')} ngày"
                    detail += f"\n- Phân tích: {data.get('reasoning')}"
                    
                    record.phan_tich_rui_ro = detail
                    
                    # Auto-create Risk alert if High
                    if record.muc_do_rui_ro == 'cao':
                        self.env['rui_ro'].create({
                            'name': f"Cảnh báo Rủi ro AI: {record.name}",
                            'project_id': record.id,
                            'risk_level': 'high',
                            'likelihood': 'high',
                            'impact': 'high',
                            'description': detail,
                            'status': 'identified'
                        })
                        
                except Exception as e:
                    record.phan_tich_rui_ro = f"Lỗi phân tích AI: {str(e)}. (Fallback: Gap {round(gap, 1)}%)"
            else:
                # Fallback logic if AI fails or no key
                if gap < -15:
                    record.muc_do_rui_ro = 'cao'
                elif gap < -5:
                    record.muc_do_rui_ro = 'trung_binh'
                else:
                    record.muc_do_rui_ro = 'thap'
                record.phan_tich_rui_ro = f"Tiến độ: {work_percent}%. Thời gian trôi qua: {round(time_percent, 1)}%. Chênh lệch: {round(gap, 1)}%. (AI không khả dụng)"